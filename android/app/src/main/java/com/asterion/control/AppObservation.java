package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.view.accessibility.AccessibilityEvent;
import org.json.JSONObject;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Comparator;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Phone-native evidence recorder for user-selected Asterion applications.
 * Records Android events and bounded MediaProjection samples; no AI inference,
 * no third-party upload and no access to non-target app content.
 */
final class AppObservation {
  private static final ExecutorService IO=Executors.newSingleThreadExecutor();
  private static final long MIN_FRAME_MS=5000L, MAX_FRAMES_BYTES=256L*1024*1024;
  private static volatile String foreground="";
  private static volatile long lastEventMs=0L, lastFrameMs=0L;
  private static volatile String latestFrame="";
  private static volatile long eventCount=0, frameCount=0;
  private AppObservation(){}
  private static SharedPreferences prefs(Context c){
    return c.getSharedPreferences("asterion_observation",Context.MODE_PRIVATE);
  }
  static boolean enabled(Context c){return prefs(c).getBoolean("enabled",false);}
  static String target(Context c){return prefs(c).getString("target","");}
  static synchronized JSONObject configure(Context c,boolean enabled,String packageName) throws Exception {
    if(enabled && (packageName==null || !packageName.matches("com\\.asterion\\.[A-Za-z0-9_.]{2,100}")))
      throw new IllegalArgumentException("Choose an Asterion application package (com.asterion.*)");
    if(!enabled)packageName=target(c);
    prefs(c).edit().putBoolean("enabled",enabled).putString("target",packageName)
      .putLong("started_ms",System.currentTimeMillis()).apply();
    latestFrame="";lastFrameMs=0;eventCount=0;frameCount=0;
    return status(c);
  }
  private static File folder(Context c){
    File base=new File(c.getExternalFilesDir(null),"observations");
    File dir=new File(base,target(c).replace('.','_'));
    if(!dir.exists())dir.mkdirs();
    return dir;
  }
  static JSONObject status(Context c)throws Exception {
    return new JSONObject().put("enabled",enabled(c)).put("target",target(c))
      .put("capture",CaptureService.active)
      .put("foreground",foreground)
      .put("frames_sampled_this_session",frameCount)
      .put("events_sampled_this_session",eventCount)
      .put("latest_frame",latestFrame)
      .put("started_ms",prefs(c).getLong("started_ms",0));
  }
  private static void append(File file,JSONObject item) {
    try (FileOutputStream stream=new FileOutputStream(file,true)) {
      stream.write((item.toString()+"\\n").getBytes(StandardCharsets.UTF_8));
    }catch(Exception ignored){}
  }
  static void event(Context c,AccessibilityEvent e) {
    if(e==null)return;
    String pkg=e.getPackageName()==null?"":e.getPackageName().toString();
    foreground=pkg;
    if(!enabled(c)||!pkg.equals(target(c)))return;
    long now=System.currentTimeMillis();
    if(now-lastEventMs<800)return; // cap noisy accessibility event writes
    lastEventMs=now;
    int type=e.getEventType();
    long epoch=now;
    IO.execute(()->{
      try{
        append(new File(folder(c),"events.jsonl"),new JSONObject()
          .put("time_ms",epoch).put("package",pkg)
          .put("event_type",type));
        eventCount++;
      }catch(Exception ignored){}
    });
  }
  static void sample(Context c) {
    if(!enabled(c)||!target(c).equals(foreground)||!CaptureService.active)return;
    long now=System.currentTimeMillis();
    if(now-lastFrameMs<MIN_FRAME_MS)return;
    byte[] frame=CaptureService.latest;
    if(frame==null||frame.length<2048)return;
    lastFrameMs=now;
    byte[] bytes=frame.clone();
    IO.execute(()->{
      try {
        File dir=folder(c);
        File file=new File(dir,"frame-"+now+".jpg");
        try(FileOutputStream out=new FileOutputStream(file)){out.write(bytes);}
        byte[] digest=MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder sha=new StringBuilder();
        for(byte b:digest)sha.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
        append(new File(dir,"frames.jsonl"),new JSONObject()
          .put("time_ms",now).put("package",target(c))
          .put("frame",file.getName()).put("bytes",bytes.length).put("sha256",sha.toString()));
        latestFrame=file.getName();frameCount++;
        trim(dir);
      }catch(Exception ignored){}
    });
  }
  private static void trim(File dir) {
    File[] frames=dir.listFiles((d,name)->name.startsWith("frame-")&&name.endsWith(".jpg"));
    if(frames==null)return;
    Arrays.sort(frames,Comparator.comparing(File::getName));
    long total=0;for(File frame:frames)total+=frame.length();
    for(File frame:frames){
      if(total<=MAX_FRAMES_BYTES)break;
      long bytes=frame.length();
      if(frame.delete())total-=bytes;
    }
  }
}
