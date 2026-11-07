package com.asterion.control;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Small generic installed-app integration adapter.
 * Asterion Control can discover and request opening any OWNER-installed launchable
 * application; it does not reimplement the application engine or infer actions.
 */
final class AppCatalog {
  private AppCatalog(){}
  private static final Handler MAIN=new Handler(Looper.getMainLooper());

  static Map<String,String> launchable(Context context) {
    PackageManager pm=context.getPackageManager();
    Intent launchable=new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
    List<ResolveInfo> matches=pm.queryIntentActivities(launchable,0);
    Map<String,String> result=new TreeMap<>();
    for(ResolveInfo item:matches) {
      if(item.activityInfo==null||item.activityInfo.packageName==null)continue;
      String pkg=item.activityInfo.packageName;
      if(!pkg.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*){1,12}"))continue;
      CharSequence label=item.loadLabel(pm);
      String name=label==null?pkg:label.toString();
      result.putIfAbsent(pkg,name);
    }
    return result;
  }

  static JSONObject list(Context context)throws Exception {
    JSONArray items=new JSONArray();
    for(Map.Entry<String,String> app:launchable(context).entrySet()){
      if(items.length()>=300)break;
      items.put(new JSONObject().put("package",app.getKey()).put("label",app.getValue()));
    }
    return new JSONObject().put("apps",items).put("truncated",items.length()>=300);
  }

  static JSONObject requestLaunch(Context context,String packageName)throws Exception {
    if(packageName==null||!launchable(context).containsKey(packageName))
      throw new IllegalArgumentException("App is not an installed visible launcher application");
    final Activity foreground=MainActivity.foregroundActivity();
    if(foreground==null)
      return new JSONObject().put("intent_dispatched",false)
        .put("reason","Open the Asterion Control screen before requesting a new application");
    Intent intent=foreground.getPackageManager().getLaunchIntentForPackage(packageName);
    if(intent==null)throw new IllegalArgumentException("Application has no launch intent");
    final boolean[] accepted={false};
    final String[] reason={""};
    final CountDownLatch completed=new CountDownLatch(1);
    MAIN.post(()->{
      try {
        // Android background starts are restricted; only act from a visible
        // Control Activity. Foreground outcome is NOT guaranteed by this return.
        if(MainActivity.foregroundActivity()!=foreground){
          reason[0]="Control is no longer foreground";
        } else {
          foreground.startActivity(intent);
          accepted[0]=true;
        }
      }catch(Exception e){reason[0]=e.getClass().getSimpleName();}
      finally{completed.countDown();}
    });
    if(!completed.await(5,TimeUnit.SECONDS))
      return new JSONObject().put("intent_dispatched",false).put("reason","Android UI launch timed out");
    return new JSONObject().put("intent_dispatched",accepted[0])
      .put("verified_foreground",false).put("package",packageName)
      .put("reason",reason[0]);
  }
}
