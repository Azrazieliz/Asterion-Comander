package com.asterion.control;

import android.content.Context;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.PowerManager;
import android.app.KeyguardManager;
import android.os.SystemClock;
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
 * remote backup/export route is allowed to read these secrets.
 * Owner-local portable archives are separately encrypted with a passphrase.
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
    private static final String AUTH_TIMEOUT="device_auth_timeout_minutes";
    private static long unlockedUntilElapsed=0L;
    private static boolean screenReceiverRegistered=false;
    // Keep the receiver only for this process. A screen-off event invalidates
    // the lease even if the device is unlocked again before the next vault read.
    private static final BroadcastReceiver SCREEN_LOCK=new BroadcastReceiver(){
        @Override public void onReceive(Context context,Intent intent){
            if(Intent.ACTION_SCREEN_OFF.equals(intent.getAction()))lock();
        }
    };
    private static void watchScreen(Context c){
        if(screenReceiverRegistered)return;
        Context app=c.getApplicationContext();
        IntentFilter filter=new IntentFilter(Intent.ACTION_SCREEN_OFF);
        if(Build.VERSION.SDK_INT>=33)app.registerReceiver(SCREEN_LOCK,filter,Context.RECEIVER_NOT_EXPORTED);
        else app.registerReceiver(SCREEN_LOCK,filter);
        screenReceiverRegistered=true;
    }
    private static boolean deviceInteractive(Context c){
        PowerManager manager=c.getSystemService(PowerManager.class);
        return manager!=null&&manager.isInteractive();
    }
    // Application-level gate over the existing Keystore-encrypted vault.
    // No password or reusable authentication token is written to preferences.
    static int authTimeout(Context c){
        return preferences(c).getInt(AUTH_TIMEOUT,0);
    }
    static boolean canAccess(Context c){
        synchronized(LOCK){
            if(authTimeout(c)==0)return true;
            KeyguardManager manager=c.getSystemService(KeyguardManager.class);
            if(manager==null||!manager.isDeviceSecure()||manager.isDeviceLocked()||!deviceInteractive(c)){
                unlockedUntilElapsed=0L;return false;
            }
            return unlockedUntilElapsed>SystemClock.elapsedRealtime();
        }
    }
    private static void requireAccess(Context c){
        if(!canAccess(c))throw new SecurityException("Vault locked");
    }
    // BrowserActivity calls this only after a successful Android credential
    // confirmation result. The authenticated lease is process-local.
    static void confirmDeviceAuth(Context c,int newTimeout){
        synchronized(LOCK){
            KeyguardManager manager=c.getSystemService(KeyguardManager.class);
            if(manager==null||!manager.isDeviceSecure()||manager.isDeviceLocked()||!deviceInteractive(c))
                throw new SecurityException("Device authentication unavailable");
            if(newTimeout!=-1){
                if(newTimeout!=0&&newTimeout!=1&&newTimeout!=5&&newTimeout!=15)
                    throw new IllegalArgumentException("Invalid vault timeout");
                if(!preferences(c).edit().putInt(AUTH_TIMEOUT,newTimeout).commit())
                    throw new IllegalStateException("Vault policy write failed");
            }
            unlockedUntilElapsed=0L;
            if(authTimeout(c)>0){
                watchScreen(c);
                unlockedUntilElapsed=SystemClock.elapsedRealtime()+authTimeout(c)*60_000L;
            }
        }
    }
    static void lock(){synchronized(LOCK){unlockedUntilElapsed=0L;}}
    static String generatePassword(){
        final String[] groups={"ABCDEFGHJKLMNPQRSTUVWXYZ","abcdefghijkmnopqrstuvwxyz",
            "23456789","!@#$%&*+-=?"};
        String alphabet=String.join("",groups);
        char[] result=new char[24];
        for(int i=0;i<groups.length;i++)result[i]=groups[i].charAt(RNG.nextInt(groups[i].length()));
        for(int i=groups.length;i<result.length;i++)result[i]=alphabet.charAt(RNG.nextInt(alphabet.length()));
        for(int i=result.length-1;i>0;i--){
            int j=RNG.nextInt(i+1);char swap=result[i];result[i]=result[j];result[j]=swap;
        }
        return new String(result);
    }
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
            requireAccess(context);
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
            requireAccess(context);
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
            requireAccess(context);
            String id=itemKey(origin,username);
            if(!preferences(context).contains(id))return false;
            if(!preferences(context).edit().remove(id).commit())
                throw new IllegalStateException("Vault delete not committed");
            return true;
        }
    }
    /** Local UI only, after a fresh Android credential confirmation. No plaintext file. */
    static byte[] exportEncrypted(Context c,char[] passphrase)throws Exception{
        byte[] plain;
        synchronized(LOCK){
            requireAccess(c);
            org.json.JSONArray items=new org.json.JSONArray();
            for(Map.Entry<String,?> entry:preferences(c).getAll().entrySet()){
                if(!entry.getKey().startsWith(PREFIX))continue;
                if(!(entry.getValue() instanceof String)||items.length()>=256)
                    throw new IllegalStateException("Vault archive entry budget exceeded");
                JSONObject data=new JSONObject(decrypt((String)entry.getValue()));
                if(!entry.getKey().equals(itemKey(exactOrigin(data.getString("origin")),data.getString("username"))))
                    throw new IllegalStateException("Vault entry identity mismatch");
                items.put(data);
            }
            plain=new JSONObject().put("schema","asterion.control.vault-portable/1").put("entries",items)
                .toString().getBytes(StandardCharsets.UTF_8);
        }
        try{return VaultArchive.seal(plain,passphrase);}
        finally{java.util.Arrays.fill(plain,(byte)0);}
    }
    /** Verify/decrypt entire archive and prepare every new sealed entry before
     * committing one merge. Never replace existing credentials or cookie state. */
    static int[] importEncrypted(Context c,byte[] archive,char[] passphrase)throws Exception{
        byte[] plain=VaultArchive.open(archive,passphrase);
        try{
            JSONObject data=new JSONObject(new String(plain,StandardCharsets.UTF_8));
            if(data.length()!=2||!"asterion.control.vault-portable/1".equals(data.getString("schema")))
                throw new IllegalArgumentException("Unsupported archive schema");
            org.json.JSONArray items=data.getJSONArray("entries");
            if(items.length()>256)throw new IllegalArgumentException("Archive entry budget exceeded");
            synchronized(LOCK){
                requireAccess(c);
                SharedPreferences prefs=preferences(c);
                java.util.LinkedHashMap<String,String> additions=new java.util.LinkedHashMap<>();
                java.util.HashSet<String> seen=new java.util.HashSet<>();
                int skipped=0;
                for(int i=0;i<items.length();i++){
                    JSONObject item=items.getJSONObject(i);
                    if(!(item.opt("origin") instanceof String)||!(item.opt("username") instanceof String)||
                       !(item.opt("password") instanceof String)||item.length()!=4||
                       !(item.opt("updated_ms") instanceof Number))
                        throw new IllegalArgumentException("Invalid archive entry");
                    String origin=exactOrigin(item.getString("origin")),user=item.getString("username"),
                        password=item.getString("password");
                    if(!origin.equals(item.getString("origin"))||user.isBlank()||user.length()>256||
                        password.isBlank()||password.length()>4096)
                        throw new IllegalArgumentException("Invalid archived credential");
                    String id=itemKey(origin,user);
                    if(!seen.add(id))throw new IllegalArgumentException("Duplicate archive credential");
                    if(prefs.contains(id)){skipped++;continue;}
                    additions.put(id,encrypt(item.toString()));
                }
                // Refuse to start a write if device auth expired while validating.
                requireAccess(c);
                SharedPreferences.Editor editor=prefs.edit();
                for(Map.Entry<String,String> item:additions.entrySet())editor.putString(item.getKey(),item.getValue());
                if(!editor.commit())throw new IllegalStateException("Vault merge could not be confirmed");
                return new int[]{additions.size(),skipped};
            }
        }finally{java.util.Arrays.fill(plain,(byte)0);}
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
