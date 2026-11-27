package com.asterion.control;

import android.content.ContentValues;
import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.AtomicFile;
import android.util.Log;
import android.database.Cursor;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
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
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Authenticated, chunked Wi-Fi receive. Android owns the files; no ADB is used. */
final class TransferStore {
  static final int CHUNK_MAX = 1024 * 1024;
  private static final long FILE_MAX = 2L * 1024 * 1024 * 1024;
  private final Context app;
  private final File journalDir;
  private final File stagingDir;
  private boolean journalHealthy=true;
  private final Map<String, Job> jobs = new HashMap<>();
  private final SecureRandom random = new SecureRandom();
  // Dedicated original TransferStore commit worker. An APK ~505 MB must not
  // occupy a network request for re-hashing + MediaStore publication.
  private final ExecutorService publisher=Executors.newSingleThreadExecutor(r->{
    Thread thread=new Thread(r,"asterion-android-transfer-publisher");
    thread.setDaemon(false);
    return thread;
  });

  private static final class Job {
    String id, name, expected;
    File path;
    long size, written, created;
    String publicationUri="";
    String phase="receiving";
    String failureCode="";
    JSONObject finalReceipt=null;
    long completedAt=0;
    boolean commitStarted=false;
  }

  TransferStore(Context context){
    app=context.getApplicationContext();
    journalDir=new File(app.getNoBackupFilesDir(),"transfer-receipts-v1");
    stagingDir=new File(app.getCacheDir(),"incoming-asterion");
    restoreJournal();
  }

  private AtomicFile record(Job job){
    return new AtomicFile(new File(journalDir,job.id+".json"));
  }
  private void persist(Job job)throws Exception{
    if(!journalDir.isDirectory()&&!journalDir.mkdirs())
      throw new IllegalStateException("Transfer receipt storage unavailable");
    JSONObject value=new JSONObject().put("schema",1).put("id",job.id)
      .put("name",job.name).put("sha256",job.expected).put("size",job.size)
      .put("written",job.written).put("created",job.created).put("phase",job.phase)
      .put("publication_uri",job.publicationUri).put("error_code",job.failureCode)
      .put("completed_at",job.completedAt);
    if(job.finalReceipt!=null)value.put("result",job.finalReceipt);
    AtomicFile disk=record(job);FileOutputStream stream=disk.startWrite();
    try{
      stream.write(value.toString().getBytes(StandardCharsets.UTF_8));
      stream.flush();disk.finishWrite(stream);
    }catch(Exception e){disk.failWrite(stream);throw e;}
  }
  private void persistOrClose(Job job){
    try{persist(job);}catch(Exception e){journalHealthy=false;}
  }
  private void restoreJournal(){
    if(!journalDir.exists())return;
    File[] entries=journalDir.listFiles();
    if(entries==null){journalHealthy=false;return;}
    HashSet<String> ids=new HashSet<>();
    for(File entry:entries){
      String name=entry.getName();
      if(name.matches("[A-Za-z0-9_-]{24}\\.json(\\.bak)?"))
        ids.add(name.substring(0,24));
    }
    for(String id:ids){
      try{
        Job job=new Job();job.id=id;
        byte[] raw=record(job).readFully();
        if(raw.length>16384)throw new IllegalStateException("Invalid receipt length");
        JSONObject saved=new JSONObject(new String(raw,StandardCharsets.UTF_8));
        if(saved.getInt("schema")!=1||!id.equals(saved.getString("id")))
          throw new IllegalStateException("Receipt identity mismatch");
        job.name=filename(saved.getString("name"));job.expected=saved.getString("sha256");
        job.size=saved.getLong("size");job.written=saved.getLong("written");
        job.created=saved.getLong("created");job.phase=saved.getString("phase");
        job.completedAt=saved.optLong("completed_at",0);
        job.failureCode=saved.optString("error_code","");
        job.publicationUri=saved.optString("publication_uri","");
        job.finalReceipt=saved.optJSONObject("result");
        job.path=new File(stagingDir,id+".part");
        if(job.size<0||job.size>FILE_MAX||job.written<0||job.written>job.size||
           !job.expected.matches("[a-f0-9]{64}"))
          throw new IllegalStateException("Invalid saved transfer identity");
        String action=TransferCapacityPolicy.recoveryAction(job.phase,
          job.path.isFile(),job.path.length(),job.written,job.size,
          !job.publicationUri.isEmpty(),job.finalReceipt!=null);
        jobs.put(id,job);
        if("receive".equals(action)){
          job.written=job.path.length();persist(job);
        }else if("verify".equals(action)){
          job.commitStarted=true;publisher.submit(()->commitInBackground(job));
        }else if("reconcile".equals(action)){
          // Read the original URI only; never insert another MediaStore row.
          job.phase="publishing";job.commitStarted=true;
          publisher.submit(()->recoverPublication(job));
        }else if("unknown".equals(action)){
          job.phase="outcome_unknown";job.failureCode="publication_outcome_unknown_after_restart";
          persist(job);
        }else if("failed".equals(action)){
          job.phase="failed";job.failureCode="staging_missing_or_changed_after_restart";persist(job);
        }else if(!"retain".equals(action)){
          throw new IllegalStateException("Unrecognized persisted transfer phase");
        }
      }catch(Exception e){journalHealthy=false;}
    }
  }

  private JSONObject verifiedPublication(Job job,Uri uri)throws Exception{
    if(!"content".equals(uri.getScheme())||!"media".equals(uri.getAuthority()))
      throw new IllegalStateException("Invalid MediaStore receipt URI");
    String actualName,relative;
    try(Cursor row=app.getContentResolver().query(uri,new String[]{
      MediaStore.MediaColumns.DISPLAY_NAME,MediaStore.MediaColumns.RELATIVE_PATH,
      MediaStore.MediaColumns.IS_PENDING},null,null,null)){
      if(row==null||!row.moveToFirst()||row.getInt(2)!=0)
        throw new IllegalStateException("MediaStore publication not verified");
      actualName=filename(row.getString(0));relative=row.getString(1);
      if(!"Downloads/Asterion Control/".equals(relative)&&
         !("Download/Asterion Control/").equals(relative))
        throw new IllegalStateException("Unexpected publication directory");
    }
    MessageDigest digest=MessageDigest.getInstance("SHA-256");long size=0;
    try(InputStream input=app.getContentResolver().openInputStream(uri)){
      if(input==null)throw new IllegalStateException("Published file unavailable");
      byte[] block=new byte[256*1024];int count;
      while((count=input.read(block))!=-1){
        size+=count;if(size>job.size)throw new IllegalStateException("Published file size changed");
        digest.update(block,0,count);
      }
    }
    if(size!=job.size||!job.expected.equals(hex(digest.digest())))
      throw new IllegalStateException("Published file integrity mismatch");
    return new JSONObject().put("ok",true).put("name",actualName)
      .put("size",size).put("sha256",job.expected)
      .put("location","Downloads/Asterion Control/"+actualName).put("uri",uri.toString());
  }
  private void recoverPublication(Job job){
    try{
      JSONObject receipt=verifiedPublication(job,Uri.parse(job.publicationUri));
      synchronized(this){
        job.finalReceipt=receipt;job.phase="completed";job.failureCode="";
        job.completedAt=System.currentTimeMillis();job.created=job.completedAt;
        persist(job);job.commitStarted=false;
      }
      if(job.path.exists())job.path.delete();
    }catch(Exception e){
      synchronized(this){
        job.finalReceipt=null;job.phase="outcome_unknown";job.commitStarted=false;
        job.failureCode="publication_outcome_unknown_after_restart";persistOrClose(job);
      }
    }
  }
  private static String hex(byte[] buf){
    StringBuilder s=new StringBuilder(buf.length*2);
    for(byte b:buf)s.append(String.format(Locale.ROOT,"%02x",b&255));
    return s.toString();
  }
  private void cleanup(){
    long now=System.currentTimeMillis();
    jobs.entrySet().removeIf(e->{
      Job j=e.getValue();
      if("publishing".equals(j.phase)||"verifying".equals(j.phase)||"outcome_unknown".equals(j.phase))
        return false;
      // Keep final SHA receipts 24h to reconcile a lost HTTP response and
      // avoid duplicate MediaStore downloads. Pending files retain 1h TTL.
      long expiry="completed".equals(j.phase)?86400000L:3600000L;
      if(now-j.created>expiry){
        if(j.path!=null&&j.path.exists()&&!j.path.delete())return false;
        record(j).delete();
        return true;
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
    if(!journalHealthy)throw new IllegalStateException("Transfer journal requires local review");
    cleanup();
    String name=filename(request.optString("name",""));
    // Retry of the SAME original must resume the existing staging file,
    // not create another download after an uncertain reply.
    // Do not guess equivalence from filenames alone.
    long size=request.getLong("size");
    String digest=request.getString("sha256").toLowerCase(Locale.ROOT);
    if(size<0||size>FILE_MAX||!digest.matches("^[a-f0-9]{64}$"))
      throw new IllegalArgumentException("Invalid transfer size/checksum");
    for(Job existing:jobs.values()){
      if(existing.name.equals(name)&&existing.size==size &&
         existing.expected.equals(digest)){
        existing.created=System.currentTimeMillis();persist(existing);
        return new JSONObject().put("id",existing.id)
          .put("received",existing.written).put("size",size)
          .put("sha256",digest).put("resumed",true)
          .put("phase",existing.phase)
          .put("chunk_max",CHUNK_MAX)
          .put("stored_location","Downloads/Asterion Control");
      }
    }
    // Completed/failed receipts are retained for reconciliation, but never
    // consume an active receive/publish slot.
    long active=jobs.values().stream().filter(j->TransferCapacityPolicy.isActive(j.phase)).count();
    if(active>=4)throw new IllegalStateException("Too many active transfers");
    byte[] bytes=new byte[18];random.nextBytes(bytes);
    String id=Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    File dir=stagingDir;
    if(!dir.isDirectory()&&!dir.mkdirs())throw new IllegalStateException("Cannot create transfer cache");
    Job job=new Job();
    job.id=id;job.name=name;job.size=size;job.expected=digest;
    job.created=System.currentTimeMillis();
    job.path=new File(dir,id+".part");
    if(!job.path.createNewFile())throw new IllegalStateException("Transfer path already exists");
    persist(job); // No accepted transfer ID before its identity is durable.
    jobs.put(id,job);
    return new JSONObject().put("id",id).put("chunk_max",CHUNK_MAX)
      .put("received",0).put("size",size).put("sha256",digest)
      .put("resumed",false).put("stored_location","Downloads/Asterion Control");
  }

  synchronized JSONObject append(String id,long offset,InputStream in,int length)throws Exception {
    if(!journalHealthy)throw new IllegalStateException("Transfer journal requires local review");
    Job job=get(id);
    if(!"receiving".equals(job.phase))
      throw new IllegalStateException("Transfer is not accepting additional chunks");
    if(offset!=job.written)throw new IllegalArgumentException("Unexpected chunk offset");
    if(length<1||length>CHUNK_MAX||job.written+length>job.size)
      throw new IllegalArgumentException("Invalid chunk size");
    byte[] buf=new byte[65536];int remaining=length;
    if(!job.path.isFile()||job.path.length()!=job.written)
      throw new IllegalStateException("Transfer staging length changed");
    try(FileOutputStream out=new FileOutputStream(job.path,true)){
      try{
        while(remaining>0){
          int n=in.read(buf,0,Math.min(buf.length,remaining));
          if(n<0)throw new IllegalArgumentException("Truncated file chunk");
          if(n==0)continue;
          out.write(buf,0,n);remaining-=n;
        }
      }finally{
        try{
          out.getFD().sync();
          job.written=job.path.length();job.created=System.currentTimeMillis();
          persist(job);
        }catch(Exception failure){
          journalHealthy=false;throw failure;
        }
      }
    }
    return new JSONObject().put("id",id).put("received",job.written).put("total",job.size);
  }

  synchronized JSONObject status(String id)throws Exception {
    Job job=get(id);
    JSONObject response=new JSONObject().put("id",job.id)
      .put("received",job.written).put("size",job.size)
      .put("sha256",job.expected).put("name",job.name)
      .put("phase",job.phase).put("last_progress_ms",job.created)
      .put("chunk_max",CHUNK_MAX);
    if("completed".equals(job.phase)&&job.finalReceipt!=null){
      response.put("result",job.finalReceipt);
      response.put("verified",true);
    }
    if("failed".equals(job.phase)||"outcome_unknown".equals(job.phase))
      response.put("error_code",job.failureCode);
    return response;
  }

  /**
   * Idempotent, quick-ACK publication. No 500MB hashing/copying while an HTTP
   * handler waits (the previous 30s caller timeout lost genuine finalization
   * outcomes). Repeated finish returns the same job state and never creates a
   * second Android Downloads item. Source remains staged on failure.
   */
  synchronized JSONObject finish(String id)throws Exception {
    Job job=get(id);
    if(job.written!=job.size)
      throw new IllegalArgumentException("File transfer incomplete");
    if("completed".equals(job.phase)&&job.finalReceipt!=null)
      return status(id);
    if(job.commitStarted||"verifying".equals(job.phase)||
       "publishing".equals(job.phase))
      return status(id);
    if("failed".equals(job.phase)||"outcome_unknown".equals(job.phase))
      return status(id); // No blind replay of uncertain MediaStore publication.
    if(!"receiving".equals(job.phase))
      throw new IllegalStateException("Transfer has an invalid phase");
    if(!journalHealthy)throw new IllegalStateException("Transfer journal requires local review");
    job.phase="verifying";
    job.created=System.currentTimeMillis();
    try{persist(job);}catch(Exception e){job.phase="receiving";journalHealthy=false;throw e;}
    job.commitStarted=true;
    publisher.submit(()->commitInBackground(job));
    return status(id);
  }

  private void commitInBackground(Job job){
    String failure="unknown_publication_failure";
    Uri uri=null;
    boolean published=false,releaseAttempted=false;
    try{
      // Re-hash stable private staging; MessageDigest.digest() consumes state
      // and cannot safely be reused after an ambiguous final HTTP response.
      MessageDigest digest=MessageDigest.getInstance("SHA-256");
      long bytes=0;
      try(InputStream source=new FileInputStream(job.path)){
        byte[] block=new byte[256*1024];int n;
        while((n=source.read(block))!=-1){
          digest.update(block,0,n);
          bytes+=n;
        }
      }
      String actual=hex(digest.digest());
      if(bytes!=job.size||!MessageDigest.isEqual(
          actual.getBytes(java.nio.charset.StandardCharsets.US_ASCII),
          job.expected.getBytes(java.nio.charset.StandardCharsets.US_ASCII))){
        failure="staged_sha256_or_size_mismatch";
        return;
      }
      synchronized(this){
        job.phase="publishing";
        job.created=System.currentTimeMillis();
        persist(job); // Record intent BEFORE any MediaStore insertion.
      }
      ContentValues values=new ContentValues();
      values.put(MediaStore.MediaColumns.DISPLAY_NAME,job.name);
      values.put(MediaStore.MediaColumns.MIME_TYPE,
        job.name.toLowerCase(Locale.ROOT).endsWith(".apk")?
          "application/vnd.android.package-archive":
        job.name.toLowerCase(Locale.ROOT).endsWith(".txt")?
          "text/plain":"application/octet-stream");
      values.put(MediaStore.MediaColumns.RELATIVE_PATH,
        Environment.DIRECTORY_DOWNLOADS+"/Asterion Control/");
      values.put(MediaStore.MediaColumns.IS_PENDING,1);
      uri=app.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,values);
      if(uri==null){
        failure="downloads_insert_denied";
        return;
      }
      synchronized(this){job.publicationUri=uri.toString();persist(job);}
      long count=0;
      try(InputStream source=new FileInputStream(job.path);
          OutputStream dest=app.getContentResolver().openOutputStream(uri,"w")){
        if(dest==null){
          failure="downloads_write_denied";
          return;
        }
        byte[] block=new byte[256*1024];int n;
        while((n=source.read(block))!=-1){
          dest.write(block,0,n);count+=n;
          if(count>job.size){
            failure="publication_size_mismatch";
            return;
          }
        }
      }
      if(count!=job.size){
        failure="publication_size_mismatch";
        return;
      }
      ContentValues release=new ContentValues();
      release.put(MediaStore.MediaColumns.IS_PENDING,0);
      releaseAttempted=true;
      if(app.getContentResolver().update(uri,release,null,null)!=1){
        failure="downloads_commit_denied";
        return;
      }
      published=true;
      JSONObject receipt=verifiedPublication(job,uri);
      synchronized(this){
        job.finalReceipt=receipt;
        job.phase="completed";
        job.completedAt=System.currentTimeMillis();
        job.created=job.completedAt;
        try{persist(job);}catch(Exception e){job.finalReceipt=null;throw e;}
      }
      // Only after final Android MediaStore ACK is private staging deleted.
      job.path.delete();
    }catch(Exception problem){
      // A source file may be private. Never log exception messages, paths,
      // content, credentials or partial APK bytes.
      failure="publication_"+problem.getClass().getSimpleName();
    }finally{
      // After an attempted release, deletion could destroy a successfully
      // published file. Reconcile read-only; never delete or republish it.
      boolean uncertain=releaseAttempted&&(!published||job.finalReceipt==null);
      if(!releaseAttempted&&uri!=null){
        try{if(app.getContentResolver().delete(uri,null,null)!=1)uncertain=true;}
        catch(Exception ignored){uncertain=true;}
      }
      synchronized(this){
        if(!published||job.finalReceipt==null){
          job.phase=uncertain?"outcome_unknown":"failed";
          job.failureCode=uncertain?"publication_outcome_unknown":failure;
          job.created=System.currentTimeMillis();
          persistOrClose(job);
        }
        job.commitStarted=false;
      }
    }
  }

  synchronized JSONObject cancel(String id)throws Exception {
    Job job=jobs.get(id);
    if(job==null)return new JSONObject().put("cancelled",false);
    if(job.commitStarted||"verifying".equals(job.phase)||
       "publishing".equals(job.phase)||"completed".equals(job.phase)||"outcome_unknown".equals(job.phase))
      return new JSONObject().put("cancelled",false)
        .put("reason","finalization_in_progress_or_completed");
    if(job.path!=null&&job.path.exists()&&!job.path.delete())
      throw new IllegalStateException("Transfer cancellation could not remove private staging");
    record(job).delete();jobs.remove(id);
    return new JSONObject().put("cancelled",true);
  }
}
