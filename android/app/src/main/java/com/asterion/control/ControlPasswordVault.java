package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;

import java.net.IDN;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * The ONE Control password vault. All username, password and site information
 * is encrypted at rest with a private AndroidKeyStore AES-256-GCM key.
 * No AI tool, Windows RPC, browser JavaScript bridge, HTTP request, log or
 * backup/export route is allowed to read these secrets.
 *
 * Deliberately local: OS Autofill is separate, opt-in through system Settings.
 * Android CredentialManager/passkey-provider behavior must be accepted on
 * the owner's OS before being claimed; this class does not counterfeit that.
 */
final class ControlPasswordVault {
    static final class Entry {
        final String origin, username, password;
        Entry(String o,String u,String p){origin=o;username=u;password=p;}
    }
    private static final String STORE="asterion_control_secure_passwords_v1";
    private static final String KEY="asterion_control_vault_aes256_v1";
    private static final String PREFIX="credential:";
    private static final byte[] AAD="Asterion.Control.Vault.v1"
        .getBytes(StandardCharsets.UTF_8);
    private static final SecureRandom RNG=new SecureRandom();
    private static final Object LOCK=new Object();
    private ControlPasswordVault(){}

    /** Refuse insecure HTTP and all non-web or credential-bearing origins. */
    static String exactOrigin(String url){
        if(url==null||url.length()>2048)throw new IllegalArgumentException("Invalid site");
        try{
            Uri u=Uri.parse(url);
            if(!"https".equalsIgnoreCase(u.getScheme())||u.getUserInfo()!=null)
                throw new IllegalArgumentException("Passwords require verified HTTPS origin");
            String raw=u.getHost();
            if(raw==null||raw.isBlank())throw new IllegalArgumentException("Missing hostname");
            String host=IDN.toASCII(raw.toLowerCase(Locale.ROOT));
            if(host.length()>180||!host.contains(".")||
               !host.matches("[a-z0-9.-]+")||host.contains(".."))
                throw new IllegalArgumentException("Invalid site hostname");
            int port=u.getPort();
            if(port<-1||port==0||port>65535)throw new IllegalArgumentException("Bad site port");
            return "https://"+host+(port>0&&port!=443?":"+port:"");
        }catch(IllegalArgumentException invalid){throw invalid;}
        catch(Exception failure){throw new IllegalArgumentException("Invalid HTTPS origin");}
    }
    private static SharedPreferences preferences(Context c){
        return c.getApplicationContext().getSharedPreferences(STORE,Context.MODE_PRIVATE);
    }
    private static SecretKey key()throws Exception{
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        java.security.Key current=store.getKey(KEY,null);
        if(current instanceof SecretKey)return(SecretKey)current;
        KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,
            "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY,
            KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)
            .setUserAuthenticationRequired(false)
            .build());
        return generator.generateKey();
    }
    private static String hex(byte[] bytes){
        StringBuilder out=new StringBuilder(bytes.length*2);
        for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    private static String itemKey(String origin,String user)throws Exception{
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        String material=origin+"\u0000"+user;
        return PREFIX+hex(digest.digest(material.getBytes(StandardCharsets.UTF_8)));
    }
    private static String encrypt(String plain)throws Exception{
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE,key());
        cipher.updateAAD(AAD);
        byte[] iv=cipher.getIV();
        byte[] ciphertext=cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
        if(iv.length!=12)throw new IllegalStateException("Unexpected Android nonce length");
        return Base64.encodeToString(iv,Base64.NO_WRAP)+":"+
            Base64.encodeToString(ciphertext,Base64.NO_WRAP);
    }
    private static String decrypt(String payload)throws Exception{
        if(payload==null||payload.length()>16384)
            throw new IllegalStateException("Invalid vault entry");
        int delimiter=payload.indexOf(':');
        if(delimiter<1)throw new IllegalStateException("Invalid vault ciphertext");
        byte[] iv=Base64.decode(payload.substring(0,delimiter),Base64.NO_WRAP);
        byte[] encrypted=Base64.decode(payload.substring(delimiter+1),Base64.NO_WRAP);
        if(iv.length!=12||encrypted.length<16)
            throw new IllegalStateException("Invalid vault authentication tag");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,iv));
        cipher.updateAAD(AAD);
        return new String(cipher.doFinal(encrypted),StandardCharsets.UTF_8);
    }
    static void save(Context context,String url,String username,String password)throws Exception{
        String origin=exactOrigin(url);
        if(username==null||username.isBlank()||username.length()>256||
            password==null||password.isBlank()||password.length()>4096)
            throw new IllegalArgumentException("Invalid credential length");
        synchronized(LOCK){
            JSONObject value=new JSONObject().put("origin",origin)
                .put("username",username).put("password",password)
                .put("updated_ms",System.currentTimeMillis());
            String id=itemKey(origin,username);
            String sealed=encrypt(value.toString());
            if(!preferences(context).edit().putString(id,sealed).commit())
                throw new IllegalStateException("Vault write failed");
        }
    }
    static List<Entry> accounts(Context context,String url)throws Exception{
        String origin=exactOrigin(url);
        synchronized(LOCK){
            List<Entry> found=new ArrayList<>();
            for(Map.Entry<String,?> item:preferences(context).getAll().entrySet()){
                if(!item.getKey().startsWith(PREFIX)||!(item.getValue() instanceof String))
                    continue;
                JSONObject value=new JSONObject(decrypt((String)item.getValue()));
                if(!origin.equals(value.optString("origin")))continue;
                found.add(new Entry(origin,value.getString("username"),
                    value.getString("password")));
            }
            found.sort(Comparator.comparing(a->a.username.toLowerCase(Locale.ROOT)));
            return Collections.unmodifiableList(found);
        }
    }
    static boolean delete(Context context,String url,String username)throws Exception{
        String origin=exactOrigin(url);
        if(username==null||username.isBlank())return false;
        synchronized(LOCK){
            String id=itemKey(origin,username);
            if(!preferences(context).contains(id))return false;
            if(!preferences(context).edit().remove(id).commit())
                throw new IllegalStateException("Vault delete not committed");
            return true;
        }
    }
    static int count(Context context)throws Exception{
        synchronized(LOCK){
            int total=0;
            for(String key:preferences(context).getAll().keySet())
                if(key.startsWith(PREFIX))total++;
            return total;
        }
    }
}
