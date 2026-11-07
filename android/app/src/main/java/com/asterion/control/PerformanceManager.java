package com.asterion.control;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.os.BatteryManager;
import android.os.PowerManager;
import android.os.SystemClock;
import org.json.JSONObject;

/**
 * Active, bounded Android Control resource manager.
 *
 * It changes REAL app workloads: screenshot encoding cadence/quality and
 * optional observation sampling. Never force-stops unrelated applications,
 * changes CPU/GPU clocks, erases user data or pauses checkpoint/voice/control.
 */
final class PerformanceManager {
  private static final String PREFS="performance_manager";
  private static volatile int captureIntervalMs=90, jpegQuality=62;
  private static volatile long observationIntervalMs=3000;
  private static volatile String activeMode="automatic",reason="normal";
  private static volatile int lastThermal=-1;
  private static volatile long lastSampleElapsed=0,lastActionMs=0;
  private static volatile long lastAvailable=0,lastTotal=0;
  private static volatile boolean lastLowMemory=false;
  private static volatile int lastBattery=-1;
  private static final long SAMPLE_INTERVAL_MS=5000;
  private static final long BOOST_DURATION_MS=20*60*1000L;
  private static final String[] MODES={"automatic","foreground","full","quiet"};
  private PerformanceManager(){}

  private static SharedPreferences prefs(Context c){
    return c.getApplicationContext().getSharedPreferences(PREFS,Context.MODE_PRIVATE);
  }
  private static boolean valid(String mode){
    if(mode==null)return false;
    for(String item:MODES)if(item.equals(mode))return true;
    return false;
  }
  static int captureIntervalMs(){return captureIntervalMs;}
  static int jpegQuality(){return jpegQuality;}
  static long observationIntervalMs(){return observationIntervalMs;}

  static synchronized JSONObject setMode(Context c,String mode)throws Exception{
    if(!valid(mode))throw new IllegalArgumentException("Unsupported performance mode");
    prefs(c).edit().putString("mode",mode).remove("temporary_until").apply();
    lastSampleElapsed=0;
    sample(c,true);
    return status(c);
  }
  static synchronized JSONObject prioritizeForegroundNow(Context c)throws Exception{
    long until=System.currentTimeMillis()+BOOST_DURATION_MS;
    prefs(c).edit().putString("mode","foreground")
      .putLong("temporary_until",until).apply();
    lastSampleElapsed=0;
    sample(c,true);
    return status(c);
  }
  static synchronized void tick(Context c){
    sample(c,false);
  }
  private static void tune(int interval,int quality,long observation,String mode,String because){
    if(interval!=captureIntervalMs||quality!=jpegQuality||
       observation!=observationIntervalMs||!mode.equals(activeMode)||!because.equals(reason)){
      captureIntervalMs=interval;
      jpegQuality=quality;
      observationIntervalMs=observation;
      activeMode=mode;
      reason=because;
      lastActionMs=System.currentTimeMillis();
    }
  }
  private static void sample(Context c,boolean force){
    long now=SystemClock.elapsedRealtime();
    if(!force&&now-lastSampleElapsed<SAMPLE_INTERVAL_MS)return;
    lastSampleElapsed=now;
    String mode=prefs(c).getString("mode","automatic");
    if(!valid(mode))mode="automatic";
    long until=prefs(c).getLong("temporary_until",0);
    if(until>0&&System.currentTimeMillis()>=until){
      prefs(c).edit().putString("mode","automatic").remove("temporary_until").apply();
      mode="automatic";
    }

    PowerManager power=(PowerManager)c.getSystemService(Context.POWER_SERVICE);
    int thermal=power==null?-1:power.getCurrentThermalStatus();
    ActivityManager activity=(ActivityManager)c.getSystemService(Context.ACTIVITY_SERVICE);
    ActivityManager.MemoryInfo memory=new ActivityManager.MemoryInfo();
    if(activity!=null)activity.getMemoryInfo(memory);
    boolean pressure=memory.lowMemory||
      (memory.totalMem>0&&memory.availMem*100/memory.totalMem<12);
    Intent battery=c.registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
    int level=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_LEVEL,-1);
    int scale=battery==null?-1:battery.getIntExtra(BatteryManager.EXTRA_SCALE,-1);
    int percent=level>=0&&scale>0?level*100/scale:-1;
    boolean plugged=battery!=null&&battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0)!=0;

    lastThermal=thermal;lastAvailable=memory.availMem;lastTotal=memory.totalMem;
    lastLowMemory=pressure;lastBattery=percent;

    // Thermal safety overrides all user modes; do not attempt OS throttling bypass.
    if(thermal>=PowerManager.THERMAL_STATUS_SEVERE){
      tune(950,43,18000,mode,"thermal_severe");
    }else if(thermal>=PowerManager.THERMAL_STATUS_MODERATE||pressure){
      tune(440,50,9000,mode,pressure?"memory_pressure":"thermal_moderate");
    }else if("foreground".equals(mode)){
      tune(430,48,11000,mode,"prioritize_foreground_app");
    }else if("quiet".equals(mode)){
      tune(800,45,16000,mode,"quiet_control");
    }else if("full".equals(mode)){
      tune(65,62,3000,mode,"full_observation");
    }else if(percent>=0&&percent<15&&!plugged){
      tune(400,52,9000,mode,"low_battery");
    }else{
      tune(65,62,3000,mode,"normal");
    }
  }

  static synchronized JSONObject status(Context c)throws Exception{
    sample(c,false);
    long until=prefs(c).getLong("temporary_until",0);
    return new JSONObject()
      .put("ok",true).put("requested_mode",activeMode)
      .put("reason",reason)
      .put("capture_interval_ms",captureIntervalMs)
      .put("jpeg_quality",jpegQuality)
      .put("observation_interval_ms",observationIntervalMs)
      .put("last_applied_at_ms",lastActionMs)
      .put("temporary_until_ms",until)
      .put("thermal_status",lastThermal)
      .put("memory_pressure",lastLowMemory)
      .put("available_memory_bytes",lastAvailable)
      .put("total_memory_bytes",lastTotal)
      .put("battery_percent",lastBattery)
      .put("capture_active",CaptureService.active)
      .put("frames_encoded",CaptureService.framesEncoded)
      .put("frames_skipped",CaptureService.framesSkipped)
      .put("last_encode_ms",CaptureService.lastEncodeDurationMs)
      .put("direct_control_preserved",true)
      .put("voice_and_cycles_preserved",true)
      .put("system_clock_control",false)
      .put("other_app_process_control",false);
  }
}
