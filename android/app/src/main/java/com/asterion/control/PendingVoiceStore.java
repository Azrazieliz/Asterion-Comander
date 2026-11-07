package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** One encrypted owner voice command pending Android unlock; never stores raw audio.
 * Clear after verified or uncertain submission to prevent replay.
 */
final class PendingVoiceStore {
  private PendingVoiceStore(){}
  private static final String PREF="pending_voice_owner_v1";
  private static final String ALIAS="AsterionControlPendingSpeechV1";
  private static final long MAX_AGE_MS=2L*60L*60L*1000L;
  private static final int MAX_TEXT=2000;
  private static SharedPreferences prefs(Context c){
    return c.getSharedPreferences(PREF,Context.MODE_PRIVATE);
  }
  private static SecretKey key()throws Exception{
    KeyStore ks=KeyStore.getInstance("AndroidKeyStore");
    ks.load(null);
    if(ks.containsAlias(ALIAS))return (SecretKey)ks.getKey(ALIAS,null);
    KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
    generator.init(new KeyGenParameterSpec.Builder(ALIAS,
      KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
      .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
      .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
      .setKeySize(256).build());
    return generator.generateKey();
  }
  static synchronized void save(Context context,String message)throws Exception{
    if(message==null||message.isBlank()||message.length()>MAX_TEXT)
      throw new IllegalArgumentException("Invalid voice command");
    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.ENCRYPT_MODE,key());
    byte[] encrypted=cipher.doFinal(message.getBytes(StandardCharsets.UTF_8));
    byte[] nonce=cipher.getIV();
    if(nonce.length!=12)throw new IllegalStateException("Unexpected AES nonce");
    byte[] combined=new byte[nonce.length+encrypted.length];
    System.arraycopy(nonce,0,combined,0,nonce.length);
    System.arraycopy(encrypted,0,combined,nonce.length,encrypted.length);
    if(!prefs(context).edit().putString("ciphertext",
        Base64.encodeToString(combined,Base64.NO_WRAP))
      .putLong("created",System.currentTimeMillis()).commit())
      throw new IllegalStateException("Could not persist pending voice command");
    Arrays.fill(combined,(byte)0);
  }
  static synchronized String restore(Context context){
    SharedPreferences p=prefs(context);
    long created=p.getLong("created",0L);
    if(created<=0||System.currentTimeMillis()<created||
       System.currentTimeMillis()-created>MAX_AGE_MS){
      clear(context);return "";
    }
    try{
      String raw=p.getString("ciphertext","");
      if(raw.isEmpty())return "";
      byte[] bytes=Base64.decode(raw,Base64.NO_WRAP);
      if(bytes.length<=12||bytes.length>MAX_TEXT*4+64)throw new IllegalArgumentException("Invalid record");
      byte[] iv=Arrays.copyOfRange(bytes,0,12);
      byte[] ciphertext=Arrays.copyOfRange(bytes,12,bytes.length);
      Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,iv));
      String message=new String(cipher.doFinal(ciphertext),StandardCharsets.UTF_8);
      return message.length()<=MAX_TEXT?message:"";
    }catch(Exception invalid){
      clear(context);return "";
    }
  }
  static synchronized boolean hasSaved(Context context){
    return !prefs(context).getString("ciphertext","").isEmpty();
  }
  static synchronized void clear(Context context){
    prefs(context).edit().remove("ciphertext").remove("created").commit();
  }
}
