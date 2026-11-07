package com.asterion.control;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.util.Log;

/** Restore previously enabled private phone control, never bypass Android's
 * while-in-use microphone or MediaProjection consent restrictions after reboot.
 */
public final class RestoreReceiver extends BroadcastReceiver {
  static final int VOICE_RECOVERY_NOTIFICATION=2112;
  private static void notifyVoiceRecovery(Context context){
    if(Build.VERSION.SDK_INT>=33&&context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
        !=PackageManager.PERMISSION_GRANTED)return;
    NotificationManager nm=context.getSystemService(NotificationManager.class);
    if(nm==null)return;
    String channel="asterion_voice_resume";
    nm.createNotificationChannel(new NotificationChannel(channel,
      "Resume Asterion voice",NotificationManager.IMPORTANCE_DEFAULT));
    Intent open=new Intent(context,MainActivity.class)
      .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent action=PendingIntent.getActivity(context,2112,open,
      PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    Notification message=new Notification.Builder(context,channel)
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentTitle("Resume Asterion hands-free voice")
      .setContentText("Android requires a visible app to restart microphone access after reboot")
      .setContentIntent(action).setAutoCancel(true).build();
    nm.notify(VOICE_RECOVERY_NOTIFICATION,message);
  }
  @Override public void onReceive(Context context,Intent event){
    if(event==null)return;
    String action=event.getAction();
    if(!Intent.ACTION_BOOT_COMPLETED.equals(action)&&
       !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action))return;
    if(context.getSharedPreferences("agent",Context.MODE_PRIVATE)
        .getBoolean(AgentService.PREF_REMOTE_ENABLED,false)){
      try{
        Intent start=new Intent(context,AgentService.class);
        if(Build.VERSION.SDK_INT>=26)context.startForegroundService(start);
        else context.startService(start);
      }catch(RuntimeException e){
        Log.w("AsterionRestore","Android deferred private phone agent",e);
      }
    }
    if(context.getSharedPreferences("voice_style",Context.MODE_PRIVATE)
       .getBoolean(VoiceDialogueService.ALWAYS_ON_PREF,false)){
      // No background startForegroundService(MICROPHONE) here. Android 14+
      // denies while-in-use microphone access and Android 17 also hardens audio.
      notifyVoiceRecovery(context);
    }
  }
}
