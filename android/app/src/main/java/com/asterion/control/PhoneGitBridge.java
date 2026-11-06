package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.AtomicFile;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import javax.net.ssl.HttpsURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * OPTIONAL phone-owned private GitHub command relay.
 *
 * This reuses the owner's existing private Asterion-Control-Bridge command/result
 * schema when a direct ChatGPT MCP connector is unavailable. No model/AI runs in
 * Control, and no Windows process is required. It is NOT the low-latency primary
 * channel. The owner explicitly enables it and enters a repo-scoped GitHub token
 * locally; the token never enters GitHub, app logs, ChatGPT or a result payload.
 */
final class PhoneGitBridge {
  private static final String REPO="Azrazieliz/Asterion-Control-Bridge";
  private static final String API="https://api.github.com/repos/"+REPO+"/contents/";
  private static final String ALIAS="asterion-phone-github-bridge-aes-v1";
  private static final int MAX_BYTES=2_000_000, MAX_ITEMS=1000;
  private static final Map<String,String> OPS=new HashMap<>();
  static {
    String[] names={"status","health","screen","ui","input","apps","app_launch",
      "continuation_status","continuation_queue","continuation_dispatch",
      "continuation_ack","continuation_cancel","observation_status",
      "observation_events","observation_frame","voice_status","voice_question"};
    for(String name:names) OPS.put("phone_"+name,"control_phone_"+name);
  }
  private static volatile boolean busy=false;
  private static volatile String lastError="",lastCommand="";
  private static volatile long lastPollMs=0,lastSuccessMs=0;
  private static volatile long completed=0;
  private static volatile String commandsEtag="";
  private static volatile String phoneCommandsEtag="";
  private PhoneGitBridge(){}
  private static SharedPreferences pref(Context ctx){
    return ctx.getSharedPreferences("asterion_phone_git_bridge",Context.MODE_PRIVATE);
  }
  static boolean enabled(Context ctx){return pref(ctx).getBoolean("enabled",false);}
  static synchronized JSONObject status(Context ctx)throws Exception{
    return new JSONObject().put("enabled",enabled(ctx)).put("busy",busy)
      .put("last_poll_ms",lastPollMs).put("last_success_ms",lastSuccessMs)
      .put("completed",completed).put("last_command",lastCommand)
      .put("last_error",lastError).put("token_present",tokenExists(ctx))
      .put("repository",REPO).put("poll_interval_seconds",15);
  }
  private static File secretFile(Context ctx){
    return new File(ctx.getNoBackupFilesDir(),"phone-github-token.enc");
  }
  private static File outbox(Context ctx){
    File dir=new File(ctx.getNoBackupFilesDir(),"phone-github-outbox");
    if(!dir.exists())dir.mkdirs();
    return dir;
  }
  private static SecretKey key()throws Exception{
    KeyStore store=KeyStore.getInstance("AndroidKeyStore");
    store.load(null);
    SecretKey key=(SecretKey)store.getKey(ALIAS,null);
    if(key!=null)return key;
    KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
    generator.init(new KeyGenParameterSpec.Builder(ALIAS,
      KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
      .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
      .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
      .setKeySize(256).build());
    return generator.generateKey();
  }
  private static void saveSecret(Context ctx,String token)throws Exception{
    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.ENCRYPT_MODE,key());
    byte[] iv=cipher.getIV(), sealed=cipher.doFinal(token.getBytes(StandardCharsets.UTF_8));
    byte[] all=new byte[1+iv.length+sealed.length];
    all[0]=(byte)iv.length;
    System.arraycopy(iv,0,all,1,iv.length);
    System.arraycopy(sealed,0,all,1+iv.length,sealed.length);
    AtomicFile file=new AtomicFile(secretFile(ctx));
    FileOutputStream out=file.startWrite();
    try{out.write(all);file.finishWrite(out);}
    catch(Exception e){file.failWrite(out);throw e;}
  }
  private static String token(Context ctx)throws Exception{
    File file=secretFile(ctx);
    if(!file.isFile())return "";
    byte[] stored;
    try(FileInputStream in=new FileInputStream(file)){stored=in.readAllBytes();}
    int ivLen=stored.length==0?0:(stored[0]&255);
    if(ivLen!=12||stored.length<ivLen+18)throw new IllegalStateException("Invalid stored bridge credential");
    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Arrays.copyOfRange(stored,1,1+ivLen)));
    return new String(cipher.doFinal(Arrays.copyOfRange(stored,1+ivLen,stored.length)),StandardCharsets.UTF_8);
  }
  private static boolean tokenExists(Context ctx){return secretFile(ctx).isFile();}
  static synchronized JSONObject configure(Context ctx,String token,boolean enabled)throws Exception{
    if(enabled){
      if(token!=null&&!token.trim().isEmpty()){
        String normalized=token.trim();
        if(normalized.length()<30||normalized.length()>300||normalized.contains(" "))
          throw new IllegalArgumentException("A restricted GitHub token is required");
        saveSecret(ctx,normalized);
      }
      if(!tokenExists(ctx))throw new IllegalStateException("Enter a repository-scoped GitHub token");
    }
    pref(ctx).edit().putBoolean("enabled",enabled).commit();
    lastError="";
    return status(ctx);
  }
  static synchronized JSONObject revoke(Context ctx)throws Exception{
    pref(ctx).edit().putBoolean("enabled",false).commit();
    secretFile(ctx).delete();
    lastError="";return status(ctx);
  }
  private static byte[] readBounded(InputStream in)throws Exception{
    try(InputStream stream=in;ByteArrayOutputStream buf=new ByteArrayOutputStream()){
      byte[] bytes=new byte[8192];int n;
      while((n=stream.read(bytes))!=-1){
        if(buf.size()+n>MAX_BYTES)throw new IllegalArgumentException("GitHub API response exceeded size limit");
        buf.write(bytes,0,n);
      }
      return buf.toByteArray();
    }
  }
  private static JSONObject connect(String url,String token,String method,JSONObject payload)throws Exception{
    if(!url.startsWith(API)||url.indexOf('#')>=0)throw new SecurityException("Non-bridge API URL");
    HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();
    c.setRequestMethod(method);c.setConnectTimeout(5500);c.setReadTimeout(8000);
    c.setInstanceFollowRedirects(false);
    c.setRequestProperty("Authorization","Bearer "+token);
    c.setRequestProperty("Accept","application/vnd.github+json");
    c.setRequestProperty("X-GitHub-Api-Version","2022-11-28");
    c.setRequestProperty("User-Agent","Asterion-Control-Android");
    if(payload!=null){
      c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");
      byte[] b=payload.toString().getBytes(StandardCharsets.UTF_8);
      c.setFixedLengthStreamingMode(b.length);
      try(OutputStream out=c.getOutputStream()){out.write(b);}
    }
    int code=c.getResponseCode();
    byte[] body=readBounded(code>=400?c.getErrorStream():c.getInputStream());
    c.disconnect();
    if(code==404)return null;
    if(code!=200&&code!=201)throw new IllegalStateException("Private GitHub bridge returned HTTP "+code);
    return new JSONObject(new String(body,StandardCharsets.UTF_8));
  }
  private static JSONObject getFile(String path,String pat)throws Exception{
    return connect(API+path+"?ref=main",pat,"GET",null);
  }
  private static String[] previous(Context ctx){
    return pref(ctx).getString("handled","").split(",");
  }
  private static boolean handled(Context ctx,String id){
    for(String name:previous(ctx))if(id.equals(name))return true;
    return false;
  }
  private static void markHandled(Context ctx,String id){
    String[] prior=previous(ctx);
    StringBuilder out=new StringBuilder();
    for(String earlier:prior)
      if(!earlier.isEmpty())out.append(earlier).append(',');
    if(out.length()>500_000)
      throw new IllegalStateException("Local bridge receipt history is full; archive before continuing");
    out.append(id);
    if(!pref(ctx).edit().putString("handled",out.toString()).commit())
      throw new IllegalStateException("Cannot durably mark command as handled");
  }
  private static File pendingFile(Context ctx,String id){
    return new File(outbox(ctx),id+".json");
  }
  private static void savePending(File path,JSONObject json)throws Exception{
    AtomicFile store=new AtomicFile(path);
    FileOutputStream out=store.startWrite();
    try{out.write(json.toString().getBytes(StandardCharsets.UTF_8));store.finishWrite(out);}
    catch(Exception e){store.failWrite(out);throw e;}
  }
  private static JSONObject readPending(File f)throws Exception{
    try(FileInputStream in=new FileInputStream(f)){
      return new JSONObject(new String(in.readAllBytes(),StandardCharsets.UTF_8));
    }
  }
  private static boolean publish(Context ctx,String pat,File file)throws Exception{
    if(!file.getName().matches("(?:android|phone)-[A-Za-z0-9_.-]{3,90}\\.json"))
      return false;
    String id=file.getName().substring(0,file.getName().length()-5);
    String remote=(id.startsWith("phone-")?"results/android/":"results/")+id+".json";
    if(getFile(remote,pat)!=null){file.delete();return true;}
    JSONObject result=readPending(file);
    byte[] value=result.toString().getBytes(StandardCharsets.UTF_8);
    if(value.length>900_000)throw new IllegalArgumentException("Command result too large for GitHub Contents");
    JSONObject put=new JSONObject()
      .put("message","Asterion Android private Control response "+id)
      .put("content",Base64.encodeToString(value,Base64.NO_WRAP)).put("branch","main");
    connect(API+remote,pat,"PUT",put);
    file.delete();
    return true;
  }
  private static void flush(Context ctx,String pat)throws Exception{
    File[] files=outbox(ctx).listFiles((dir,name)->(name.startsWith("android-")||name.startsWith("phone-"))&&name.endsWith(".json"));
    if(files==null)return;
    Arrays.sort(files,(a,b)->a.getName().compareTo(b.getName()));
    for(int i=0;i<Math.min(files.length,4);i++)publish(ctx,pat,files[i]);
  }
  private static JSONObject execute(AgentService owner,String id,JSONObject instruction)throws Exception{
    String op=instruction.optString("op","");
    String tool=OPS.get(op);
    if(tool==null)throw new SecurityException("Disallowed Android bridge operation");
    JSONObject params=instruction.optJSONObject("params");
    if(params==null)params=new JSONObject();
    JSONObject request=new JSONObject().put("jsonrpc","2.0").put("id",id)
      .put("method","tools/call").put("params",
        new JSONObject().put("name",tool).put("arguments",params));
    JSONObject response=AndroidMcp.handle(owner,request);
    JSONObject error=response.optJSONObject("error");
    if(error!=null)return new JSONObject().put("id",id).put("ok",false)
      .put("status","failed").put("error",error.optString("message","Native tool error"));
    JSONObject data=response.optJSONObject("result");
    JSONArray content=data==null?null:data.optJSONArray("content");
    JSONObject output=data==null?new JSONObject():data;
    if(content!=null&&content.length()>0){
      JSONObject first=content.optJSONObject(0);
      if(first!=null&&"text".equals(first.optString("type"))){
        String text=first.optString("text","");
        try{output=new JSONObject(text);}catch(Exception ignored){output=new JSONObject().put("text",text);}
      }else if(first!=null&&"image".equals(first.optString("type"))){
        output=new JSONObject().put("mime",first.optString("mimeType"))
          .put("jpeg_b64",first.optString("data"));
      }
    }
    return new JSONObject().put("id",id).put("ok",true)
      .put("status","complete").put("result",output);
  }
  static void poll(AgentService owner){
    if(!enabled(owner)||busy)return;
    busy=true;lastPollMs=System.currentTimeMillis();
    try{
      String pat=token(owner);
      if(pat.isEmpty())throw new IllegalStateException("Missing private GitHub credential");
      flush(owner,pat);
      // Prefer the isolated phone-owned queue. The legacy android-* queue
      // remains supported for commands already issued before this upgrade.
      boolean processed=processDirectory(owner,pat,"commands/android/",true);
      if(!processed)processDirectory(owner,pat,"commands/",false);
      lastSuccessMs=System.currentTimeMillis();lastError="";
    }catch(Exception e){
      lastError=e.getClass().getSimpleName()+": "+String.valueOf(e.getMessage());
      if(lastError.length()>190)lastError=lastError.substring(0,190);
    }finally{busy=false;}
  }
  private static boolean processDirectory(AgentService owner,String pat,String folder,boolean isolated)throws Exception{
    JSONArray files=directory(pat,folder,isolated);
    if(files==null)return false;
    int examined=0;
    for(int i=0;i<files.length()&&examined<MAX_ITEMS;i++){
      JSONObject entry=files.optJSONObject(i);
      if(entry==null||!"file".equals(entry.optString("type")))continue;
      String name=entry.optString("name","");
      String pattern=isolated?"phone-[A-Za-z0-9_.-]{3,90}\\.json":
        "android-[A-Za-z0-9_.-]{3,90}\\.json";
      if(!name.matches(pattern))continue;
      examined++;
      String id=name.substring(0,name.length()-5);
      if(handled(owner,id))continue;
      String remote=(isolated?"results/android/":"results/")+id+".json";
      if(getFile(remote,pat)!=null){
        markHandled(owner,id);continue;
      }
      JSONObject raw=getFile(folder+name,pat);
      if(raw==null)continue;
      String content=raw.optString("content","").replace("\\n","");
      JSONObject command=new JSONObject(new String(Base64.decode(content,Base64.DEFAULT),
        StandardCharsets.UTF_8));
      if(!id.equals(command.optString("id")))continue;
      File pending=pendingFile(owner,id);
      // A restart cannot replay a partially executed remote command.
      savePending(pending,new JSONObject().put("id",id).put("ok",false)
        .put("status","uncertain").put("error",
          "Android worker was interrupted; inspect before retrying"));
      markHandled(owner,id);
      JSONObject receipt;
      try{receipt=execute(owner,id,command);}
      catch(Exception e){
        receipt=new JSONObject().put("id",id).put("ok",false).put("status","failed")
          .put("error",e.getClass().getSimpleName()+": "+String.valueOf(e.getMessage()));
      }
      savePending(pending,receipt);
      lastCommand=id;
      publish(owner,pat,pending);
      completed++;
      return true;
    }
    return false;
  }
  private static JSONArray directory(String pat,String folder,boolean isolated)throws Exception{
    String url=API+folder.substring(0,folder.length()-1)+"?ref=main";
    HttpsURLConnection c=(HttpsURLConnection)new URL(url).openConnection();
    c.setConnectTimeout(5500);c.setReadTimeout(8000);
    c.setInstanceFollowRedirects(false);
    c.setRequestProperty("Authorization","Bearer "+pat);
    c.setRequestProperty("Accept","application/vnd.github+json");
    c.setRequestProperty("X-GitHub-Api-Version","2022-11-28");
    c.setRequestProperty("User-Agent","Asterion-Control-Android");
    String etag=isolated?phoneCommandsEtag:commandsEtag;
    if(!etag.isEmpty())c.setRequestProperty("If-None-Match",etag);
    int code=c.getResponseCode();
    if(code==304){c.disconnect();return null;}
    byte[] data=readBounded(code>=400?c.getErrorStream():c.getInputStream());
    String receivedEtag=c.getHeaderField("ETag");
    c.disconnect();
    if(code==404)return null;
    if(code!=200)throw new IllegalStateException("Private command listing returned HTTP "+code);
    if(receivedEtag!=null&&receivedEtag.length()<256){
      if(isolated)phoneCommandsEtag=receivedEtag;else commandsEtag=receivedEtag;
    }
    return new JSONArray(new String(data,StandardCharsets.UTF_8));
  }

}
