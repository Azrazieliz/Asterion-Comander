package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import java.text.DateFormat;
import java.util.Date;

/** Local, redacted connection receipts. Never stores bearer tokens, addresses or screen data. */
public final class ConnectionDiagnostics {
  private static final String PREFS="control_connection_diagnostics";
  private ConnectionDiagnostics(){}
  public static void failure(Context context,String code,String explanation){
    String safe=(explanation==null?"Unknown connection failure":explanation)
      .replace('\n',' ').replace('\r',' ').trim();
    if(safe.length()>220)safe=safe.substring(0,220);
    context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit()
      .putString("last_code",code==null?"unknown":code)
      .putString("last_reason",safe)
      .putLong("last_failure_time",System.currentTimeMillis()).apply();
  }
  public static void success(Context context){
    context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).edit()
      .putLong("last_success_time",System.currentTimeMillis()).apply();
  }
  public static String lastFailure(Context context){
    SharedPreferences p=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
    String reason=p.getString("last_reason","");
    if(reason.isEmpty())return "No disconnection reason recorded yet.";
    long when=p.getLong("last_failure_time",0);
    String at=when>0?DateFormat.getTimeInstance(DateFormat.SHORT).format(new Date(when)):"unknown time";
    return "Last failure ("+at+"): "+reason;
  }
  public static long lastSuccess(Context context){
    return context.getSharedPreferences(PREFS,Context.MODE_PRIVATE)
      .getLong("last_success_time",0);
  }
}
