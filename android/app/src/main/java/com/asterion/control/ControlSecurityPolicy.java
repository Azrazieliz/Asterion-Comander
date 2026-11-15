package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.app.Activity;
import org.json.JSONObject;
import java.util.Locale;

/** Per-device security policy; only an actually foreground owner UI may change it.
 * All remote writes pass through this app's already authenticated agent.
 * No self-elevation, OS permission grant, or network-exposed policy mutation.
 */
final class ControlSecurityPolicy {
  static final String NORMAL="normal", DEVELOPER="developer",
                      LOCKDOWN="lockdown", CUSTOM="custom";
  private static final String PREF="owner_security_policy_v1";
  private static final String[] CAPABILITIES={
    "remote_input","app_launch","app_bridge","file_transfer",
    "cycle_automation","developer_diagnostics"
  };
  private ControlSecurityPolicy(){}
  private static SharedPreferences storage(Context c){
    return c.getSharedPreferences(PREF,Context.MODE_PRIVATE);
  }
  static String level(Context c){
    SharedPreferences p=storage(c);
    String current=p.getString("mode",NORMAL);
    if(DEVELOPER.equals(current) && System.currentTimeMillis()>=p.getLong("expires_at",0))
      return NORMAL; // Expired Developer consent never renews remotely.
    if(!NORMAL.equals(current)&&!DEVELOPER.equals(current)&&
       !LOCKDOWN.equals(current)&&!CUSTOM.equals(current))return LOCKDOWN;
    return current;
  }
  static boolean canRemote(Context c,String method,String path){
    if(path.equals("/diagnostics/logcat")&&!developerAuthorized(c))return false;
    String lvl=level(c);
    if(NORMAL.equals(lvl)||DEVELOPER.equals(lvl))return true;
    if(LOCKDOWN.equals(lvl))
      return "GET".equals(method) && !path.equals("/diagnostics/logcat");
    // Custom mode: deny operations without a known allowlisted category.
    if("GET".equals(method))return !path.equals("/diagnostics/logcat") ||
       storage(c).getBoolean("allow:developer_diagnostics",false);
    String cap;
    if(path.equals("/input"))cap="remote_input";
    else if(path.equals("/apps/launch"))cap="app_launch";
    else if(path.startsWith("/app-bridge/"))cap="app_bridge";
    else if(path.startsWith("/transfer/"))cap="file_transfer";
    else if(path.startsWith("/cycles/")||path.startsWith("/continuation/")||
            path.startsWith("/chat/"))cap="cycle_automation";
    else return false;
    return storage(c).getBoolean("allow:"+cap,false);
  }
  static boolean canTool(Context c,String name){
    if(name.equals("control_phone_own_logcat"))return developerAuthorized(c);
    if(NORMAL.equals(level(c))||DEVELOPER.equals(level(c)))return true;
    String path;
    if(name.equals("control_phone_input"))path="/input";
    else if(name.equals("control_phone_app_launch"))path="/apps/launch";
    else if(name.startsWith("control_phone_app_invoke")||
            name.startsWith("control_phone_app_operation"))path="/app-bridge/invoke";
    else if(name.contains("transfer"))path="/transfer/chunk";
    else if(name.contains("cycle")||name.contains("continuation")||
            name.contains("chat_"))path="/cycles/start";
    else if(name.matches("control_phone_(status|health|ui|screen|stream_status|apps|app_bridges|bridge_status|direct_status|network_status|own_logcat|diagnostic_events|exit_history|performance_status|security_status|permission_matrix|observation_status|observation_events|observation_timeline)"))
      path="/health";
    else path="/restricted-operation";
    return canRemote(c,path.equals("/health")?"GET":"POST",path);
  }
  static boolean developerAuthorized(Context c){
    return DEVELOPER.equals(level(c)) ||
      (CUSTOM.equals(level(c)) && storage(c).getBoolean("allow:developer_diagnostics",false));
  }
  static boolean configureLocally(Context c,String mode,boolean[] allow,long developerDurationMs){
    Activity foreground=MainActivity.foregroundActivity();
    if(foreground==null || !foreground.getPackageName().equals(c.getPackageName()))
      throw new SecurityException("Physical owner Control screen required");
    if(!NORMAL.equals(mode)&&!DEVELOPER.equals(mode)&&!LOCKDOWN.equals(mode)&&
       !CUSTOM.equals(mode))throw new IllegalArgumentException("Unknown security level");
    if(DEVELOPER.equals(mode) && (developerDurationMs<60000L || developerDurationMs>3600000L))
      throw new IllegalArgumentException("Developer access must be short-lived");
    if(CUSTOM.equals(mode) && (allow==null || allow.length!=CAPABILITIES.length))
      throw new IllegalArgumentException("Custom capability choices required");
    SharedPreferences.Editor editor=storage(c).edit().putString("mode",mode);
    editor.putLong("expires_at",DEVELOPER.equals(mode)?
         System.currentTimeMillis()+developerDurationMs:0);
    if(CUSTOM.equals(mode))
      for(int i=0;i<CAPABILITIES.length;i++)
        editor.putBoolean("allow:"+CAPABILITIES[i],allow[i]);
    boolean committed=editor.commit();
    if(committed)ControlEventJournal.write(c,"security_policy_changed","owner_ui",
      "completed",mode,0);
    return committed;
  }
  static JSONObject status(Context c)throws Exception{
    SharedPreferences p=storage(c);
    String lvl=level(c);
    JSONObject flags=new JSONObject();
    for(String cap:CAPABILITIES){
      boolean active=!(LOCKDOWN.equals(lvl)) &&
        (!CUSTOM.equals(lvl) || p.getBoolean("allow:"+cap,false));
      if("developer_diagnostics".equals(cap))
        active=developerAuthorized(c);
      flags.put(cap,active);
    }
    return new JSONObject().put("ok",true).put("level",lvl)
      .put("owner_local_only",true).put("capabilities",flags)
      .put("expires_at_ms",DEVELOPER.equals(lvl)?p.getLong("expires_at",0):0)
      .put("android_permission_bypass",false)
      .put("external_access_granted",false)
      .put("vpn_enabled",false);
  }
}
