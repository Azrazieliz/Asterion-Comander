package com.asterion.control;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.util.Log;

/** Restore only previously user-enabled phone control after reboot or app update.
 * Android may reject a background foreground-service launch; the notification and
 * main activity remain the supported manual recovery paths.
 */
public final class RestoreReceiver extends BroadcastReceiver {
  @Override public void onReceive(Context context, Intent event) {
    if(event==null)return;
    final String action=event.getAction();
    if(!Intent.ACTION_BOOT_COMPLETED.equals(action) &&
       !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action))return;
    if(!context.getSharedPreferences("agent",Context.MODE_PRIVATE)
       .getBoolean(AgentService.PREF_REMOTE_ENABLED,false))return;
    try {
      Intent start=new Intent(context,AgentService.class);
      if(Build.VERSION.SDK_INT>=26)context.startForegroundService(start);
      else context.startService(start);
    }catch(RuntimeException e){
      Log.w("AsterionRestore","Android requires user to reopen Control",e);
    }
  }
}
