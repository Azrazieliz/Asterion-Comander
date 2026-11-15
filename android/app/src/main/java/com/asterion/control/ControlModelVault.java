package com.asterion.control;

import android.app.Activity;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.AtomicMoveNotSupportedException;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/**
 * Download manager for the actual owner-approved, free GGUF MODEL WEIGHTS,
 * not an AI inference engine. Uses app-private storage, immutable HF revision
 * and SHA-256 published by Hugging Face, exact byte size and GGUF magic.
 *
 * No startup downloads, no mandatory cloud service, no hardcoded third-party
 * API token, no Google Play subscriptions. The user must explicitly request
 * download in the foreground. Downloads can resume after interrupted network
 * activity if the hash/revision manifest still matches. A file is NEVER
 * reported installed until byte-for-byte verified.
 *
 * Native on-device runtime integration is separate. Verified weights do not
 * imply that a model has been loaded, benchmarked, trained or accepted.
 */
final class ControlModelVault {
  private static final ExecutorService WORK=Executors.newSingleThreadExecutor();
  private static final Handler MAIN=new Handler(Looper.getMainLooper());
  private static final AtomicBoolean CANCEL=new AtomicBoolean(false);
  private static volatile boolean busy=false;
  private static volatile String phase="idle", lastError="";
  private static volatile long completed=0, expected=0, startedMs=0;
  private static volatile String artifactSha="", artifactRevision="";
  private static final String REPO=ModelDownloadPolicy.DEFAULT_REPOSITORY;
  private static final String FILE=ModelDownloadPolicy.DEFAULT_FILENAME;
  private ControlModelVault(){}

  private static void requireOwner(Activity a){
    if(a==null||a!=MainActivity.foregroundActivity()||a.isFinishing())
      throw new SecurityException("Owner must approve from foreground Control");
  }
  private static File directory(Context context)throws IOException{
    File root=new File(context.getFilesDir(),"ai-models");
    if(!root.isDirectory()&&!root.mkdirs())
      throw new IOException("Private model directory unavailable");
    return root;
  }

  private static void notify(Consumer<String> callback,String message){
    MAIN.post(()->callback.accept(message));
  }

  static void requestDefaultModel(Activity owner,Consumer<String> callback){
    requireOwner(owner);
    if(busy){callback.accept("Model download already active");return;}
    busy=true;
    CANCEL.set(false);
    completed=0;expected=0;startedMs=SystemClock.elapsedRealtime();
    phase="resolving_immutable_model_metadata";lastError="";
    artifactSha="";artifactRevision="";
    Context context=owner.getApplicationContext();
    WORK.execute(()->{
      try{
        ModelDownloadPolicy.Manifest model=resolveKnownArtifact();
        artifactSha=model.sha256;artifactRevision=model.revision;
        expected=model.sizeBytes;
        File root=directory(context);
        StatFs stat=new StatFs(root.getAbsolutePath());
        long required=ModelDownloadPolicy.freeSpaceRequired(model.sizeBytes);
        if(stat.getAvailableBytes()<required)
          throw new IOException("Insufficient staged model storage");
        File finished=new File(root,model.privateFilename());
        if(finished.isFile()){
          phase="verifying_previous_weights";
          if(ModelDownloadPolicy.verifiedFile(finished,model)){
            completed=expected;phase="weights_verified";
            notify(callback,"Verified GGUF weights already installed. Inference engine pending.");
            return;
          }
          throw new IOException("Existing model file failed integrity check");
        }
        File partial=new File(root,model.privateFilename()+".part");
        File receipt=new File(root,model.privateFilename()+".receipt");
        String stamp=model.revision+":"+model.sha256+":"+model.sizeBytes;
        if(!receipt.isFile()||!stamp.equals(
            new String(Files.readAllBytes(receipt.toPath()),
                       StandardCharsets.US_ASCII).trim())||
            partial.length()>model.sizeBytes){
          Files.deleteIfExists(partial.toPath());
          Files.deleteIfExists(receipt.toPath());
        }
        if(!receipt.isFile()){
          Files.write(receipt.toPath(),stamp.getBytes(StandardCharsets.US_ASCII));
        }
        long initial=partial.isFile()?partial.length():0;
        completed=initial;
        phase="downloading_verified_model";
        if(initial<model.sizeBytes)streamPinned(model,partial,initial);
        if(CANCEL.get()){
          phase="paused";notify(callback,"Model download paused");return;
        }
        phase="verifying_sha256_and_gguf";
        if(!ModelDownloadPolicy.verifiedFile(partial,model)){
          Files.deleteIfExists(partial.toPath());
          Files.deleteIfExists(receipt.toPath());
          throw new IOException("Downloaded model has wrong SHA/size/GGUF magic");
        }
        try{
          Files.move(partial.toPath(),finished.toPath(),
                     StandardCopyOption.ATOMIC_MOVE);
        }catch(AtomicMoveNotSupportedException e){
          Files.move(partial.toPath(),finished.toPath());
        }
        Files.deleteIfExists(receipt.toPath());
        completed=expected;phase="weights_verified";
        notify(callback,"GGUF model weights downloaded and SHA-256 verified.");
      }catch(Exception e){
        lastError=e.getClass().getSimpleName();
        phase=CANCEL.get()?"paused":"failed";
        notify(callback,"Model weights unavailable: "+lastError);
      }finally{
        busy=false;
      }
    });
  }

  static void cancel(Activity owner){
    requireOwner(owner);
    CANCEL.set(true);
  }

  private static ModelDownloadPolicy.Manifest resolveKnownArtifact()
      throws Exception{
    // NO remote arbitrary-repository execution or private tokens. The official
    // Hub returns immutable repository commit, actual LFS SHA and byte size.
    URL source=new URL("https://huggingface.co/"+REPO+
                       "/resolve/main/"+FILE);
    if(!ModelDownloadPolicy.trustedArtifactUrl(source,true))
      throw new SecurityException("Untrusted model source");
    HttpURLConnection conn=(HttpURLConnection)source.openConnection();
    conn.setInstanceFollowRedirects(false);
    conn.setRequestMethod("HEAD");
    conn.setConnectTimeout(12000);conn.setReadTimeout(12000);
    try{
      int code=conn.getResponseCode();
      if(code!=200&&code!=302&&code!=307)
        throw new IOException("No verified public model metadata");
      String commit=conn.getHeaderField("X-Repo-Commit");
      String sha=ModelDownloadPolicy.normalizeHashHeader(
          conn.getHeaderField("X-Linked-Etag"));
      long size=ModelDownloadPolicy.sizeHeader(
          conn.getHeaderField("X-Linked-Size"));
      if(size<0||sha.isEmpty()||commit==null)
        throw new IOException("Model SHA/size/immutable revision unavailable");
      return new ModelDownloadPolicy.Manifest(
          REPO,commit.toLowerCase(Locale.ROOT),FILE,sha,size,"apache-2.0");
    }finally{conn.disconnect();}
  }

  private static HttpURLConnection openTrusted(URL initial,long offset)
      throws Exception{
    URL location=initial;
    for(int redirect=0;redirect<8;redirect++){
      if(!ModelDownloadPolicy.trustedArtifactUrl(location,redirect==0))
        throw new SecurityException("Model server redirect outside approved HF CDN");
      HttpURLConnection conn=(HttpURLConnection)location.openConnection();
      conn.setInstanceFollowRedirects(false);
      conn.setRequestMethod("GET");
      conn.setConnectTimeout(12000);conn.setReadTimeout(30000);
      conn.setRequestProperty("Accept","application/octet-stream");
      if(offset>0)conn.setRequestProperty("Range","bytes="+offset+"-");
      int status=conn.getResponseCode();
      if(status==301||status==302||status==303||
         status==307||status==308){
        String next=conn.getHeaderField("Location");
        if(next==null||next.length()>8192)
          throw new IOException("Missing secure model CDN redirect");
        URL target=new URL(location,next);
        if(!ModelDownloadPolicy.trustedArtifactUrl(target,false))
          throw new SecurityException("Model redirect not Hugging Face CDN");
        conn.disconnect();
        location=target;
        continue;
      }
      if(status!=200&&status!=206){
        conn.disconnect();
        throw new IOException("Model CDN HTTP status "+status);
      }
      if(offset>0&&status==206){
        String range=conn.getHeaderField("Content-Range");
        if(range==null||!range.startsWith("bytes "+offset+"-")){
          conn.disconnect();
          throw new IOException("Model resume range does not match verified offset");
        }
      }
      return conn;
    }
    throw new IOException("Exceeded trusted CDN redirect limit");
  }

  private static void streamPinned(ModelDownloadPolicy.Manifest manifest,
                                   File partial,long offset)throws Exception{
    HttpURLConnection conn=openTrusted(manifest.downloadUrl(),offset);
    try{
      int status=conn.getResponseCode();
      boolean append=status==206&&offset>0;
      if(!append&&offset>0){
        // Endpoint ignored Range. Only safe response is restart from ZERO,
        // never append full response after existing weights.
        offset=0;
      }
      completed=offset;
      try(InputStream in=conn.getInputStream();
          FileOutputStream out=new FileOutputStream(partial,append)){
        byte[] chunk=new byte[256*1024];
        long count=offset;
        long lastProgress=SystemClock.elapsedRealtime();
        while(!CANCEL.get()){
          int n=in.read(chunk);
          if(n<0)break;
          count+=n;
          if(count>manifest.sizeBytes)
            throw new IOException("Model exceeded pinned expected byte count");
          out.write(chunk,0,n);
          completed=count;
          long now=SystemClock.elapsedRealtime();
          if(now-lastProgress>2500){
            lastProgress=now;
            // Internal volatile progress only; no raw URL, token or model
            // contents exported to logs or outside application storage.
          }
        }
        out.getFD().sync();
      }
    }finally{conn.disconnect();}
  }

  static JSONObject status(Context context)throws Exception{
    boolean present=false;
    File root=new File(context.getFilesDir(),"ai-models");
    if(root.isDirectory()&&artifactSha.length()==64)
      present=new File(root,artifactSha.substring(0,18)+"-"+FILE).isFile();
    return new JSONObject()
      .put("ok",true).put("phase",phase)
      .put("download_active",busy)
      .put("downloaded_bytes",completed)
      .put("expected_bytes",expected)
      .put("verified_weight_file_present",
           "weights_verified".equals(phase)&&present)
      .put("model_sha256",artifactSha)
      .put("revision",artifactRevision)
      .put("download_requires_foreground_owner_approval",true)
      .put("native_inference_engine_loaded",false)
      .put("model_benchmarked",false)
      .put("model_trained",false)
      .put("error_code",lastError);
  }
}
