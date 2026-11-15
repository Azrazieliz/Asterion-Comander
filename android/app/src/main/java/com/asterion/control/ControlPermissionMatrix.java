package com.asterion.control;

import android.Manifest;
import android.app.AppOpsManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Build;
import android.provider.Settings;
import org.json.JSONObject;

/** Actual OS capability matrix. Diagnostic permission absence is reported, not bypassed. */
final class ControlPermissionMatrix {
  private ControlPermissionMatrix(){}
  static JSONObject status(Context context)throws Exception{
    JSONObject result=new JSONObject().put("ok",true)
      .put("scope","owner_control_app_only")
      .put("android",Build.VERSION.SDK_INT)
      .put("accessibility_enabled",ControlAccessibilityService.active!=null)
      .put("media_projection_active",CaptureService.active)
      .put("developer_options_enabled",false)
      .put("root_privileges_claimed",false)
      .put("other_app_private_logs_available",false);
    try{
      result.put("developer_options_enabled",Settings.Global.getInt(
        context.getContentResolver(),Settings.Global.DEVELOPMENT_SETTINGS_ENABLED,0)!=0);
    }catch(Exception ignored){}
    boolean notifications=Build.VERSION.SDK_INT<33||
      context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)==PackageManager.PERMISSION_GRANTED;
    result.put("notifications_granted",notifications);
    boolean usage=false;
    try{
      AppOpsManager a=(AppOpsManager)context.getSystemService(Context.APP_OPS_SERVICE);
      usage=a!=null && a.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,
        android.os.Process.myUid(),context.getPackageName())==AppOpsManager.MODE_ALLOWED;
    }catch(Exception ignored){}
    result.put("usage_stats_granted",usage);
    boolean vpnActive=false;
    try{
      ConnectivityManager cm=(ConnectivityManager)context.getSystemService(
        Context.CONNECTIVITY_SERVICE);
      Network network=cm==null?null:cm.getActiveNetwork();
      NetworkCapabilities caps=network==null?null:cm.getNetworkCapabilities(network);
      vpnActive=caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
    }catch(Exception ignored){}
    JSONObject tunnel=ControlPrivateVpn.status(context);
    result.put("other_vpn_or_active_vpn",vpnActive)
      .put("asterion_vpn_active",tunnel.optBoolean("active",false))
      .put("asterion_vpn_implemented",true)
      .put("vpn_requires_android_system_consent",true)
      .put("own_app_exit_history_available",Build.VERSION.SDK_INT>=30)
      .put("partner_engine_diagnostics_requires_signed_approval",true);
    return result;
  }
}
