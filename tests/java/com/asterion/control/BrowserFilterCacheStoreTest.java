package com.asterion.control;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;

/** Real JVM filesystem regressions for atomic two-list browser refresh. */
public final class BrowserFilterCacheStoreTest {
    private static final String[] NAMES={"easylist.txt","easyprivacy.txt"};
    private static int checks=0;

    private static void check(boolean yes,String message) {
        checks++;
        if(!yes)throw new AssertionError(message);
    }
    private static void write(File root,String first,String second)throws Exception{
        Files.writeString(new File(root,NAMES[0]).toPath(),first,StandardCharsets.UTF_8);
        Files.writeString(new File(root,NAMES[1]).toPath(),second,StandardCharsets.UTF_8);
    }
    private static String read(File file)throws Exception{
        return Files.readString(file.toPath(),StandardCharsets.UTF_8);
    }
    private static void expectFailure(Checked action,String explanation)throws Exception{
        boolean failed=false;
        try{action.run();}catch(IOException expected){failed=true;}
        check(failed,explanation);
    }
    private interface Checked{void run()throws Exception;}
    public static void main(String[] args)throws Exception{
        Path scratch=Files.createTempDirectory("asterion-browser-atomic-");
        File root=scratch.toFile();
        write(root,"legacy-A\n","legacy-B\n");
        File[] legacy=BrowserFilterCacheStore.activeFiles(root,NAMES,1024);
        check(read(legacy[0]).equals("legacy-A\n"),"read valid old EasyList");
        check(read(legacy[1]).equals("legacy-B\n"),"read valid old EasyPrivacy");

        File stage=BrowserFilterCacheStore.newStagingDirectory(root);
        write(stage,"first-new-A\n","first-new-B\n");
        String id=BrowserFilterCacheStore.commit(root,stage,NAMES,1024);
        check(id.matches("[a-f0-9]{64}"),"immutable generation identity");
        File[] first=BrowserFilterCacheStore.activeFiles(root,NAMES,1024);
        check(read(first[0]).equals("first-new-A\n"),"new EasyList selected");
        check(read(first[1]).equals("first-new-B\n"),"new EasyPrivacy selected");
        check(read(new File(root,NAMES[0])).equals("legacy-A\n"),"legacy cache not overwritten");
        check(read(new File(root,NAMES[1])).equals("legacy-B\n"),"other legacy cache not overwritten");
        check(read(new File(root,"active-generation.txt")).trim().equals(id),
              "single committed pointer owns both subscriptions");

        // A crash mid-download must never replace only the first list.
        File missing=BrowserFilterCacheStore.newStagingDirectory(root);
        Files.writeString(new File(missing,NAMES[0]).toPath(),"incomplete");
        expectFailure(()->BrowserFilterCacheStore.commit(root,missing,NAMES,1024),
                "reject incomplete pair");
        File[] afterFailure=BrowserFilterCacheStore.activeFiles(root,NAMES,1024);
        check(read(afterFailure[0]).equals("first-new-A\n"),"failed refresh preserves list A");
        check(read(afterFailure[1]).equals("first-new-B\n"),"failed refresh preserves list B");
        BrowserFilterCacheStore.discardStaging(root,missing,NAMES);
        check(!missing.exists(),"orphan stage cleaned without affecting active cache");

        File unused=BrowserFilterCacheStore.newStagingDirectory(root);
        write(unused,"orphan-A\n","orphan-B\n");
        File[] beforeCommit=BrowserFilterCacheStore.activeFiles(root,NAMES,1024);
        check(read(beforeCommit[0]).equals("first-new-A\n"),"staging cannot become active");
        check(read(beforeCommit[1]).equals("first-new-B\n"),"staging cannot mix lists");
        BrowserFilterCacheStore.discardStaging(root,unused,NAMES);

        // A damaged committed generation is detected instead of silently
        // mixing with stale/legacy files or reporting an updated subscription.
        Files.writeString(first[0].toPath(),"tampered-A\n");
        expectFailure(()->BrowserFilterCacheStore.activeFiles(root,NAMES,1024),
                "reject modified active generation bytes");

        File repair=BrowserFilterCacheStore.newStagingDirectory(root);
        write(repair,"repaired-A\n","repaired-B\n");
        BrowserFilterCacheStore.commit(root,repair,NAMES,1024);
        File[] restored=BrowserFilterCacheStore.activeFiles(root,NAMES,1024);
        check(read(restored[0]).equals("repaired-A\n"),"recover after bad generation");
        check(read(restored[1]).equals("repaired-B\n"),"recovery preserves pair");

        File replay=BrowserFilterCacheStore.newStagingDirectory(root);
        write(replay,"repaired-A\n","repaired-B\n");
        BrowserFilterCacheStore.commit(root,replay,NAMES,1024);
        BrowserFilterCacheStore.discardStaging(root,replay,NAMES);
        check(read(BrowserFilterCacheStore.activeFiles(root,NAMES,1024)[1])
                .equals("repaired-B\n"),"same-hash idempotent cache update");

        expectFailure(()->BrowserFilterCacheStore.activeFiles(
                root,new String[]{"../easylist.txt","easyprivacy.txt"},1024),
                "reject path traversal in subscription names");
        File outsider=Files.createTempDirectory("browser-other-stage-").toFile();
        write(outsider,"bad-A","bad-B");
        expectFailure(()->BrowserFilterCacheStore.commit(root,outsider,NAMES,1024),
                "reject staging outside Browser's private root");

        Files.writeString(new File(root,"active-generation.txt").toPath(),"not-an-id");
        expectFailure(()->BrowserFilterCacheStore.activeFiles(root,NAMES,1024),
                "invalid pointer fails closed rather than reads legacy");
        System.out.println("BROWSER_ATOMIC_CACHE_PASS "+checks+" assertions");
    }
}
