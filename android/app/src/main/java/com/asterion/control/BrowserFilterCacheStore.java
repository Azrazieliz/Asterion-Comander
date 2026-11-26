package com.asterion.control;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Locale;
import java.util.UUID;

/**
 * Crash-consistent pair of EasyList and EasyPrivacy files in the original
 * BrowserProtection private storage. An immutable generation directory is
 * selected by ONE atomically-replaced pointer after both files are verified.
 *
 * Earlier code renamed the two active files independently: a crash or failure
 * after the first rename permanently mixed two unrelated subscription versions.
 * Missing/corrupt generation metadata fails closed to BrowserProtection's seed
 * rules; a legacy, pre-migration cache is read only when no pointer exists.
 *
 * No Android APIs or alternative Browser engine are involved.
 */
final class BrowserFilterCacheStore {
    private static final String POINTER = "active-generation.txt";
    private static final String PREFIX = "generation-";
    private static final String STAGE = "filter-stage-";
    private static final String[] EXPECTED = {"easylist.txt", "easyprivacy.txt"};
    private BrowserFilterCacheStore() {}

    private static void validateNames(String[] names) throws IOException {
        if (names == null || names.length != EXPECTED.length)
            throw new IOException("Browser subscription pair required");
        for (int i = 0; i < EXPECTED.length; i++)
            if (!EXPECTED[i].equals(names[i]))
                throw new IOException("Unknown browser subscription file");
    }

    private static void validateFile(File file, long maxBytes) throws IOException {
        if (Files.isSymbolicLink(file.toPath()) || !file.isFile()
                || file.length() <= 0 || file.length() > maxBytes)
            throw new IOException("Missing, empty or oversized browser list");
    }

    /** Digest binds exact file names, lengths and bytes in a fixed order. */
    private static String hashPair(File directory, String[] names, long maxBytes)
            throws IOException {
        final MessageDigest digest;
        try {
            digest = MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException ex) {
            throw new IOException("SHA-256 unavailable", ex);
        }
        byte[] buffer = new byte[32768];
        for (String name : names) {
            File file = new File(directory, name);
            validateFile(file, maxBytes);
            digest.update(name.getBytes(StandardCharsets.US_ASCII));
            digest.update((byte) 0);
            long length = file.length();
            for (int n = 7; n >= 0; n--)
                digest.update((byte)(length >>> (8 * n)));
            try (FileInputStream input = new FileInputStream(file)) {
                for (int read; (read = input.read(buffer)) != -1;)
                    digest.update(buffer, 0, read);
            }
        }
        StringBuilder result = new StringBuilder(64);
        for (byte value : digest.digest())
            result.append(String.format(Locale.ROOT, "%02x", value & 255));
        return result.toString();
    }

    static File newStagingDirectory(File root) throws IOException {
        if (!root.isDirectory() && !root.mkdirs())
            throw new IOException("Unable to create browser subscription directory");
        if (Files.isSymbolicLink(root.toPath()))
            throw new IOException("Browser subscription directory is symbolic link");
        return Files.createTempDirectory(root.toPath(), STAGE).toFile();
    }

    /** Resolve exactly one validated generation (or one untouched legacy pair). */
    static File[] activeFiles(File root, String[] names, long maxBytes)
            throws IOException {
        validateNames(names);
        if (!root.isDirectory() || Files.isSymbolicLink(root.toPath()))
            throw new IOException("Browser subscriptions missing");
        File pointer = new File(root, POINTER);
        File directory;
        if (!pointer.exists()) {
            directory = root; // Previous app versions stored both lists here.
        } else {
            if (Files.isSymbolicLink(pointer.toPath())
                    || !pointer.isFile() || pointer.length() > 80
                    || pointer.length() < 64)
                throw new IOException("Invalid browser generation pointer");
            String id = new String(Files.readAllBytes(pointer.toPath()),
                    StandardCharsets.US_ASCII).trim();
            if (!id.matches("[0-9a-f]{64}"))
                throw new IOException("Invalid browser generation identity");
            directory = new File(root, PREFIX + id);
            if (!directory.isDirectory() || Files.isSymbolicLink(directory.toPath())
                    || !id.equals(hashPair(directory, names, maxBytes)))
                throw new IOException("Browser subscription generation integrity failure");
        }
        File[] files = new File[names.length];
        for (int i = 0; i < files.length; i++) {
            files[i] = new File(directory, names[i]);
            validateFile(files[i], maxBytes);
        }
        return files;
    }

    /**
     * Promote the *pair*, not individual files. On failure the previous
     * pointer remains readable. Unreferenced complete generations after an
     * interrupted refresh are harmless and can be collected separately.
     */
    static String commit(File root, File stage, String[] names, long maxBytes)
            throws IOException {
        validateNames(names);
        if (stage == null || !stage.isDirectory() || Files.isSymbolicLink(stage.toPath())
                || !stage.getName().startsWith(STAGE)
                || !stage.getParentFile().getCanonicalFile().equals(root.getCanonicalFile()))
            throw new IOException("Browser refresh must use its own staging directory");
        String id = hashPair(stage, names, maxBytes);
        File generation = new File(root, PREFIX + id);
        if (!generation.exists()) {
            try {
                Files.move(stage.toPath(), generation.toPath(),
                        StandardCopyOption.ATOMIC_MOVE);
            } catch (IOException failure) {
                // A non-atomic directory swap cannot guarantee consistency.
                throw new IOException("Atomic browser generation rename unavailable", failure);
            }
        }
        if (!generation.isDirectory() || Files.isSymbolicLink(generation.toPath())
                || !id.equals(hashPair(generation, names, maxBytes)))
            throw new IOException("Existing browser generation failed integrity check");
        File candidate = new File(root, "active-generation-" + UUID.randomUUID() + ".partial");
        try {
            try (FileOutputStream stream = new FileOutputStream(candidate)) {
                stream.write((id + "\n").getBytes(StandardCharsets.US_ASCII));
                stream.getFD().sync();
            }
            Files.move(candidate.toPath(), new File(root, POINTER).toPath(),
                    StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(candidate.toPath());
        }
        return id;
    }

    /** Only delete files in a known uncommitted staging directory. */
    static void discardStaging(File root, File stage, String[] names) {
        try {
            validateNames(names);
            if (stage == null || !stage.isDirectory()
                    || Files.isSymbolicLink(stage.toPath())
                    || !stage.getName().startsWith(STAGE)
                    || !stage.getParentFile().getCanonicalFile().equals(root.getCanonicalFile()))
                return;
            for (String name : names)
                Files.deleteIfExists(new File(stage, name).toPath());
            Files.deleteIfExists(stage.toPath());
        } catch (IOException ignored) {
            // Unreferenced staging files cannot affect an active generation.
        }
    }
}
