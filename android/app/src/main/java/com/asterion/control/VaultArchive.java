package com.asterion.control;

import java.nio.ByteBuffer;
import java.security.SecureRandom;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.PBEKeySpec;
import javax.crypto.spec.SecretKeySpec;

/** Password-protected portable archive, independent of the device-local key.
 * Fixed versioned KDF parameters; never execute archive contents.
 */
final class VaultArchive {
    private static final byte[] MAGIC={'A','S','T','V','L','T',1,0};
    private static final int SALT=16,NONCE=12,TAG=16,HEADER=MAGIC.length+SALT+NONCE;
    private static final int MAX_PLAIN=512*1024;
    static final int MAX_BYTES=MAX_PLAIN+HEADER+TAG;
    private static final int ITERATIONS=600000;
    private static final SecureRandom RANDOM=new SecureRandom();
    private static byte[] derive(char[] passphrase,byte[] salt)throws Exception{
        if(passphrase==null||passphrase.length<12||passphrase.length>256)
            throw new IllegalArgumentException("Archive passphrase must have 12–256 characters");
        PBEKeySpec spec=new PBEKeySpec(passphrase,salt,ITERATIONS,256);
        try{return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).getEncoded();}
        finally{spec.clearPassword();}
    }
    static byte[] seal(byte[] plaintext,char[] passphrase)throws Exception{
        if(plaintext==null||plaintext.length==0||plaintext.length>MAX_PLAIN)
            throw new IllegalArgumentException("Archive size outside limits");
        byte[] salt=new byte[SALT],nonce=new byte[NONCE];
        RANDOM.nextBytes(salt);RANDOM.nextBytes(nonce);
        byte[] header=ByteBuffer.allocate(HEADER).put(MAGIC).put(salt).put(nonce).array();
        byte[] key=derive(passphrase,salt);
        try{
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));
            cipher.updateAAD(header);
            byte[] encrypted=cipher.doFinal(plaintext);
            return ByteBuffer.allocate(header.length+encrypted.length).put(header).put(encrypted).array();
        }finally{Arrays.fill(key,(byte)0);}
    }
    static byte[] open(byte[] archive,char[] passphrase)throws Exception{
        if(archive==null||archive.length<=HEADER+TAG||archive.length>MAX_BYTES||
            !Arrays.equals(MAGIC,Arrays.copyOf(archive,MAGIC.length)))
            throw new IllegalArgumentException("Unsupported or damaged vault archive");
        byte[] salt=Arrays.copyOfRange(archive,MAGIC.length,MAGIC.length+SALT);
        byte[] nonce=Arrays.copyOfRange(archive,MAGIC.length+SALT,HEADER);
        byte[] key=derive(passphrase,salt);
        try{
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE,new SecretKeySpec(key,"AES"),new GCMParameterSpec(128,nonce));
            cipher.updateAAD(archive,0,HEADER);
            return cipher.doFinal(archive,HEADER,archive.length-HEADER);
        }finally{Arrays.fill(key,(byte)0);}
    }
}
