package com.asterion.control;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/** Authenticated, chunked Wi-Fi receive. Android owns the files; no ADB is used. */
final class TransferStore {
  static final int CHUNK_MAX = 1024 * 1024;
  private static final long FILE_MAX = 2L * 1024 * 1024 * 1024;
  private final Context app;
  private final Map<String, Job> jobs = new HashMap<>();
  private final SecureRandom random = new SecureRandom();

  private static final class Job {
    String id, name, expected;
    File path;
    long size, written, created;
    MessageDigest digest;
  }

  TransferStore(Context context){app=context.getApplicationContext();}
  private static String hex(byte[] buf){
    StringBuilder s=new StringBuilder(buf.length*2);
    for(byte b:buf)s.append(String.format(Locale.ROOT,"%02x",b&255));
    return s.toString();
  }
  private void cleanup(){
    long now=System.currentTimeMillis();
    jobs.entrySet().removeIf(e->{
      if(now-e.getValue().created>3600000L){
        e.getValue().path.delete();return true;
      }
      return false;
    });
  }
  private Job get(String id) {
    Job j=jobs.get(id);
    if(j==null)throw new IllegalArgumentException("Unknown or expired transfer ID");
    return j;
  }
  private static String filename(String name){
    if(name==null||name.length()<1||name.length()>180||
       name.contains("/")||name.contains("\\")||name.contains(":")||
       name.equals(".")||name.equals("..")||name.startsWith(".")||
       name.chars().anyMatch(c->c<32||c==127))throw new IllegalArgumentException("Unsafe filename");
    return name;
  }
  synchronized JSONObject start(JSONObject request)throws Exception {
    cleanup();
    if(jobs.size()>=4)throw new IllegalStateException("Too many active transfers");
    String name=filename(request.optString("name",""));
    long size=request.getLong("size");
    String digest=request.getString("sha256").toLowerCase(Locale.ROOT);
    if(size<0||size>FILE_MAX||!digest.matches("^[a-f0-9]{64}$"))
      throw new IllegalArgumentException("Invalid transfer size/checksum");
    byte[] bytes=new byte[18];random.nextBytes(bytes);
    String id=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    File dir=new File(app.getCacheDir(),"incoming-asterion");
    if(!dir.isDirectory()&&!dir.mkdirs())throw new IllegalStateException("Cannot create transfer cache");
    Job job=new Job();
    job.id=id;job.name=name;job.size=size;job.expected=digest;
    job.created=System.currentTimeMillis();
    job.digest=MessageDigest.getInstance("SHA-256");
    job.path=new File(dir,id+".part");
    if(!job.path.createNewFile())throw new IllegalStateException("Transfer path already exists");
    jobs.put(id,job);
    return new JSONObject().put("id",id).put("chunk_max",CHUNK_MAX)
      .put("stored_location","Downloads/Asterion Control");
  }

  synchronized JSONObject append(String id,long offset,InputStream in,int length)throws Exception {
    Job job=get(id);
    if(offset!=job.written)throw new IllegalArgumentException("Unexpected chunk offset");
    if(length<1||length>CHUNK_MAX||job.written+length>job.size)
      throw new IllegalArgumentException("Invalid chunk size");
    byte[] buf=new byte[65536];int remaining=length;
    try(OutputStream out=new FileOutputStream(job.path,true)){
      while(remaining>0){
        int n=in.read(buf,0,Math.min(buf.length,remaining));
        if(n<0)throw new IllegalArgumentException("Truncated file chunk");
        out.write(buf,0,n);job.digest.update(buf,0,n);job.written+=n;
        remaining-=n;
      }
    }
    return new JSONObject().put("id",id).put("received",job.written).put("total",job.size);
  }

  synchronized JSONObject finish(String id)throws Exception {
    Job job=get(id);
    if(job.written!=job.size)throw new IllegalArgumentException("File transfer incomplete");
    String actual=hex(job.digest.digest());
    if(!MessageDigest.isEqual(actual.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
         job.expected.getBytes(java.nio.charset.StandardCharsets.US_ASCII))){
      jobs.remove(id);job.path.delete();throw new IllegalArgumentException("SHA-256 mismatch; discarded");
    }
    ContentValues values=new ContentValues();
    values.put(MediaStore.MediaColumns.DISPLAY_NAME,job.name);
    values.put(MediaStore.MediaColumns.MIME_TYPE,
      job.name.toLowerCase(Locale.ROOT).endsWith(".txt")?"text/plain":"application/octet-stream");
    values.put(MediaStore.MediaColumns.RELATIVE_PATH,Environment.DIRECTORY_DOWNLOADS+"/Asterion Control/");
    values.put(MediaStore.MediaColumns.IS_PENDING,1);
    Uri uri=null;
    try{
      uri=app.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
      if(uri==null)throw new IllegalStateException("Android Downloads could not be opened");
      try(InputStream source=new FileInputStream(job.path);
          OutputStream dest=app.getContentResolver().openOutputStream(uri,"w")){
        if(dest==null)throw new IllegalStateException("Android Downloads write denied");
        byte[] buffer=new byte[131072];int n;long count=0;
        while((n=source.read(buffer))!=-1){dest.write(buffer,0,n);count+=n;}
        if(count!=job.size)throw new IllegalStateException("Transferred file size changed");
      }
      ContentValues show=new ContentValues();show.put(MediaStore.MediaColumns.IS_PENDING,0);
      app.getContentResolver().update(uri,show,null,null);
      jobs.remove(id);job.path.delete();
      return new JSONObject().put("ok",true).put("name",job.name)
        .put("size",job.size).put("sha256",actual)
        .put("location","Downloads/Asterion Control/"+job.name)
        .put("uri",uri.toString());
    }catch(Exception problem){
      if(uri!=null)try{app.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}
      throw problem;
    }
  }
  synchronized JSONObject cancel(String id)throws Exception {
    Job job=jobs.remove(id);
    if(job!=null)job.path.delete();
    return new JSONObject().put("cancelled",job!=null);
  }
}
