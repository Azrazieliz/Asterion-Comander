package com.asterion.control;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;

/** One explicit MediaProjection grant yields a continuously updated compressed frame. */
public final class CaptureService extends Service {
  public static volatile byte[] latest;
  public static volatile long latestAtMs = 0L;
  public static volatile int width = 0, height = 0;
  public static volatile boolean active = false;
  public static volatile long framesEncoded=0L, framesSkipped=0L, lastEncodeDurationMs=0L;
  private ImageReader reader;
  private VirtualDisplay display;
  private MediaProjection projection;
  private HandlerThread thread;
  private long lastFrame;
  private Notification notification(){
    NotificationManager mgr=getSystemService(NotificationManager.class);
    mgr.createNotificationChannel(new NotificationChannel("asterion_capture","Asterion screen sharing",NotificationManager.IMPORTANCE_LOW));
    return new Notification.Builder(this,"asterion_capture").setSmallIcon(android.R.drawable.ic_menu_camera)
      .setContentTitle("Asterion Control").setContentText("Screen sharing active — stop in Asterion Control").setOngoing(true).build();
  }
  @Override public int onStartCommand(Intent intent,int flags,int startId){
    if(intent==null){stopSelf();return START_NOT_STICKY;}
    if("STOP".equals(intent.getAction())){stopSelf();return START_NOT_STICKY;}
    startForeground(2102,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
    try {
      if(active) stopCapture();
      Intent result;
      if(Build.VERSION.SDK_INT>=33) result=intent.getParcelableExtra("data",Intent.class);
      else result=(Intent)intent.getParcelableExtra("data");
      if(result==null)throw new IllegalStateException("Missing screen-sharing authorization");
      MediaProjectionManager manager=(MediaProjectionManager)getSystemService(Context.MEDIA_PROJECTION_SERVICE);
      projection=manager.getMediaProjection(intent.getIntExtra("result",0),result);
      if(projection==null)throw new IllegalStateException("Permission denied");
      projection.registerCallback(new MediaProjection.Callback(){@Override public void onStop(){stopCapture();stopSelf();}},new Handler(getMainLooper()));
      DisplayMetrics metrics=new DisplayMetrics();((WindowManager)getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(metrics);
      int nativeW=metrics.widthPixels,nativeH=metrics.heightPixels;
      width=Math.max(360,Math.min(900,nativeW));height=(int)Math.max(1,Math.round((double)nativeH*width/nativeW));
      reader=ImageReader.newInstance(width,height,PixelFormat.RGBA_8888,2);
      thread=new HandlerThread("asterion-capture");thread.start();
      reader.setOnImageAvailableListener(r->{Image im=null;try {
        im=r.acquireLatestImage();if(im==null)return;
        long now=System.currentTimeMillis();
        if(now-lastFrame<PerformanceManager.captureIntervalMs()){
          framesSkipped++;return;
        }
        lastFrame=now;
        long encodeStart=android.os.SystemClock.elapsedRealtime();
        Image.Plane plane=im.getPlanes()[0];ByteBuffer buf=plane.getBuffer();
        int padded=plane.getRowStride()/plane.getPixelStride();
        Bitmap raw=Bitmap.createBitmap(padded,height,Bitmap.Config.ARGB_8888);
        raw.copyPixelsFromBuffer(buf);
        Bitmap cropped=Bitmap.createBitmap(raw,0,0,width,height);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream(width*height/4);
        boolean encoded=cropped.compress(Bitmap.CompressFormat.JPEG,
          PerformanceManager.jpegQuality(),bytes);
        if(!encoded)throw new IllegalStateException("Capture JPEG encode failed");
        latest=bytes.toByteArray();latestAtMs=now;
        framesEncoded++;
        lastEncodeDurationMs=android.os.SystemClock.elapsedRealtime()-encodeStart;
        cropped.recycle();raw.recycle();
      }catch(Exception ignored){}finally {if(im!=null)im.close();}},new Handler(thread.getLooper()));
      display=projection.createVirtualDisplay("AsterionScreen",width,height,metrics.densityDpi,
        DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,reader.getSurface(),null,new Handler(thread.getLooper()));
      active=true;
    }catch(Exception e){android.util.Log.e("AsterionCapture","Capture failed",e);stopCapture();stopSelf();}
    return START_NOT_STICKY;
  }
  private void stopCapture(){active=false;latest=null;latestAtMs=0L;try{if(display!=null)display.release();}catch(Exception ignored){}display=null;
    try{if(reader!=null)reader.close();}catch(Exception ignored){}reader=null;
    try{if(thread!=null)thread.quitSafely();}catch(Exception ignored){}thread=null;
    MediaProjection old=projection;projection=null;try{if(old!=null)old.stop();}catch(Exception ignored){}
  }
  @Override public void onDestroy(){stopCapture();super.onDestroy();}
  @Override public IBinder onBind(Intent i){return null;}
}
