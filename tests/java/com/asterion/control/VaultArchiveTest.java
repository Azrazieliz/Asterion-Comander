package com.asterion.control;
public final class VaultArchiveTest {
    static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args)throws Exception{
        byte[] content="synthetic credential fixture".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        char[] pass="fixture-passphrase-only".toCharArray();
        byte[] sealed=VaultArchive.seal(content,pass),second=VaultArchive.seal(content,pass);
        check(!java.util.Arrays.equals(sealed,second));
        check(java.util.Arrays.equals(content,VaultArchive.open(sealed,pass)));
        try{VaultArchive.open(sealed,"different-passphrase".toCharArray());throw new AssertionError();}
        catch(javax.crypto.AEADBadTagException expected){}
        sealed[sealed.length-1]^=1;
        try{VaultArchive.open(sealed,pass);throw new AssertionError();}
        catch(javax.crypto.AEADBadTagException expected){}
        try{VaultArchive.seal(content,"short".toCharArray());throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        try{VaultArchive.open(new byte[VaultArchive.MAX_BYTES+1],pass);throw new AssertionError();}
        catch(IllegalArgumentException expected){}
        System.out.println("Vault archive authenticated encryption passed");
    }
}
