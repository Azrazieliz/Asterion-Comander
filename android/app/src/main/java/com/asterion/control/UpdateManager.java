package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.Settings;
import android.webkit.MimeTypeMap;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** User-initiated Android updates and user-selected APK installs without ADB.
 * All installation is submitted to the Android package installer for owner approval.
 * Asterion never silently installs or elevates privileges.
 */
final class UpdateManager {
  interface Feedback {void show(String message);}
  // Release manifest is canonical. Old v0.8.8 clients still consume
  // latest.json with an alias pointing to the SAME release-signed APK bytes.
  private static final String INDEX="https://raw.githubusercontent.com/Azrazieliz/Asterion-Comander/main/dist/latest-release.json";
  private static final String PREFIX="https://raw.githubusercontent.com/Azrazieliz/Asterion-Comander/main/dist/";
  private static final String APK_TYPE="application/vnd.android.package-archive";
  private static final ExecutorService IO=Executors.newSingleThreadExecutor();
  private static final Handler UI=new Handler(Looper.getMainLooper());

  private static void post(Feedback feedback,String message){UI.post(()->feedback.show(message));}
  private static boolean installAllowed(Activity owner,Feedback feedback){
    if(Build.VERSION.SDK_INT>=26&&!owner.getPackageManager().canRequestPackageInstalls()){
      new AlertDialog.Builder(owner).setTitle("Allow Asterion Control APK updates")
        .setMessage("Android requires your permission before this app can request APK installs. This does not enable silent installation.")
        .setPositiveButton("Open Android settings",(d,w)->{
          Intent i=new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:"+owner.getPackageName()));
          owner.startActivity(i);
        }).setNegativeButton("Cancel",null).show();
      post(feedback,"Enable 'Allow from this source', then tap Check for updates again.");
      return false;
    }
    return true;
  }

  static void check(Activity owner,Feedback feedback){
    post(feedback,"Checking signed release metadata…");
    IO.execute(()->{
      try{
        HttpURLConnection link=(HttpURLConnection)new URL(INDEX).openConnection();
        link.setConnectTimeout(5000);link.setReadTimeout(10000);
        link.setInstanceFollowRedirects(false);link.setUseCaches(false);
        int status=link.getResponseCode();
        if(status!=200)throw new IllegalStateException("Update index HTTP "+status);
        byte[] index;
        try(InputStream in=link.getInputStream()){
          index=in.readNBytes(8193);
        }finally{link.disconnect();}
        if(index.length>8192)throw new IllegalStateException("Update index too large");
        JSONObject meta=new JSONObject(new String(index,StandardCharsets.UTF_8));
        int version=meta.getInt("version_code");
        String name=meta.getString("version_name");
        String url=meta.getString("apk_url");
        String sha=meta.getString("sha256").toLowerCase(Locale.ROOT);
        long size=meta.getLong("size_bytes");
        if(!name.matches("[0-9]+\\.[0-9]+\\.[0-9]+")
          ||!(url.equals(PREFIX+"Asterion-Control-v"+name+"-release.apk") ||
               url.equals(PREFIX+"Asterion-Control-v"+name+"-debug.apk"))
          ||!sha.matches("[0-9a-f]{64}")||size<20000||size>300000000)
          throw new IllegalStateException("Invalid update signature metadata");
        long current=owner.getPackageManager().getPackageInfo(owner.getPackageName(),0).getLongVersionCode();
        if(version<=current){
          post(feedback,"Asterion Control is current. Installed version code "+current+".");
          return;
        }
        UI.post(()->new AlertDialog.Builder(owner)
          .setTitle("Update Asterion Control to "+name)
          .setMessage("Download "+(size/1024)+" KB over HTTPS, verify SHA-256, then request installation through Android. Existing pairing and settings are preserved.")
          .setPositiveButton("Download update",(d,w)->{
             if(installAllowed(owner,feedback))download(owner,feedback,url,sha,size,name);
          })
          .setNegativeButton("Cancel",null).show());
      }catch(Exception e){post(feedback,"Update check failed: "+e.getMessage());}
    });
  }

  private static void download(Activity owner,Feedback feedback,String url,String expected,long expectedSize,String version){
    post(feedback,"Downloading Asterion Control "+version+"…");
    IO.execute(()->{
      Uri uri=null;
      try{
        MessageDigest sha=MessageDigest.getInstance("SHA-256");
        HttpURLConnection connection=(HttpURLConnection)new URL(url).openConnection();
        connection.setConnectTimeout(6000);connection.setReadTimeout(15000);
        connection.setInstanceFollowRedirects(false);
        if(connection.getResponseCode()!=200)throw new IllegalStateException("Release download failed");
        ContentValues v=new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME,"Asterion-Control-v"+version+"-release.apk");
        v.put(MediaStore.MediaColumns.MIME_TYPE,APK_TYPE);
        v.put(MediaStore.MediaColumns.RELATIVE_PATH,Environment.DIRECTORY_DOWNLOADS+"/Asterion Control/Updates/");
        v.put(MediaStore.MediaColumns.IS_PENDING,1);
        uri=owner.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI,v);
        if(uri==null)throw new IllegalStateException("Android Downloads unavailable");
        long received=0;
        try(InputStream in=connection.getInputStream();
            OutputStream out=owner.getContentResolver().openOutputStream(uri,"w")){
          if(out==null)throw new IllegalStateException("Android cannot write update");
          byte[] buf=new byte[65536];int length;
          while((length=in.read(buf))!=-1){
            sha.update(buf,0,length);out.write(buf,0,length);
            received+=length;
            if(received>expectedSize)throw new IllegalStateException("Update size mismatch");
          }
        }finally{connection.disconnect();}
        if(received!=expectedSize)throw new IllegalStateException("Update download incomplete");
        StringBuilder actual=new StringBuilder(64);
        for(byte b:sha.digest())actual.append(String.format(Locale.ROOT,"%02x",b&255));
        if(!MessageDigest.isEqual(actual.toString().getBytes(StandardCharsets.US_ASCII),
           expected.getBytes(StandardCharsets.US_ASCII)))
          throw new IllegalStateException("Update checksum mismatch");
        ContentValues committed=new ContentValues();
        committed.put(MediaStore.MediaColumns.IS_PENDING,0);
        owner.getContentResolver().update(uri,committed,null,null);
        Uri ready=uri;
        post(feedback,"Downloaded and SHA-256 verified. Requesting Android installation…");
        UI.post(()->requestInstall(owner,ready,feedback));
      }catch(Exception e){
        if(uri!=null)try{owner.getContentResolver().delete(uri,null,null);}catch(Exception ignored){}
        post(feedback,"Update failed: "+e.getMessage());
      }
    });
  }

  static void installReceived(Activity owner,Uri uri,Feedback feedback){
    if(uri==null){post(feedback,"Select an APK from Downloads");return;}
    if(!installAllowed(owner,feedback))return;
    requestInstall(owner,uri,feedback);
  }

  private static void requestInstall(Activity owner,Uri uri,Feedback feedback){
    try{
      Intent install=new Intent(Intent.ACTION_VIEW);
      install.setDataAndType(uri,APK_TYPE);
      install.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
      install.setClipData(ClipData.newUri(owner.getContentResolver(),"Asterion Control APK",uri));
      owner.startActivity(install);
      feedback.show("Android package installer opened. Review and approve the installation.");
    }catch(Exception e){feedback.show("Android installer unavailable: "+e.getClass().getSimpleName());}
  }
}
