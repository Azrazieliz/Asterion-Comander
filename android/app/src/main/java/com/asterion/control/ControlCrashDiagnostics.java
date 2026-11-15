package com.asterion.control;

import android.app.ActivityManager;
import android.app.ApplicationExitInfo;
import android.content.Context;
import android.os.Build;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.List;

/**
 * Bounded same-app process exit history for authorized Control diagnostics.
 * Developer Options do not grant access to private crash logs of other apps.
 * Partner apps must explicitly provide their own diagnostic adapters.
 */
final class ControlCrashDiagnostics {
  private ControlCrashDiagnostics(){}

  static JSONObject recentExitHistory(Context context) throws Exception {
    JSONObject response=new JSONObject()
      .put("ok",true)
      .put("package",context.getPackageName())
      .put("scope","own_process_only")
      .put("global_logcat",false)
      .put("schema_version",1);
    JSONArray exits=new JSONArray();
    if(Build.VERSION.SDK_INT < 30){
      return response.put("supported",false).put("exits",exits);
    }
    ActivityManager manager=(ActivityManager)context.getSystemService(Context.ACTIVITY_SERVICE);
    if(manager==null){
      return response.put("supported",false).put("reason","activity_manager_unavailable")
        .put("exits",exits);
    }
    List<ApplicationExitInfo> items=manager.getHistoricalProcessExitReasons(
      context.getPackageName(),0,12);
    if(items!=null)for(ApplicationExitInfo e:items){
      JSONObject row=new JSONObject()
        .put("timestamp_ms",e.getTimestamp())
        .put("reason_code",e.getReason())
        .put("status",e.getStatus())
        .put("importance",e.getImportance())
        .put("pss_kb",e.getPss())
        .put("rss_kb",e.getRss())
        .put("process",e.getProcessName());
      // Do not disclose process traces or potentially private descriptions
      // in a broad health endpoint. Dedicated consented incident export
      // can provide richer evidence in a later version.
      exits.put(row);
    }
    return response.put("supported",true).put("exits",exits);
  }
}
