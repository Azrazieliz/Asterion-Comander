package com.asterion.control;

import android.content.Context;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/**
 * R04: deterministic no-model fast routing into EXISTING signer-approved
 * specialist ContentProviders. Control never generates images/music, downloads
 * files, writes specialist documents or runs any other specialist engine.
 *
 * The signed provider owns and advertises exact operations in its versioned
 * Asterion v1 capabilities pack. A missing contract is UNAVAILABLE, never a
 * placeholder action. A live signed-provider receipt is required for dispatch.
 */
final class AppIntentFastPath {
  private AppIntentFastPath(){}
  private static final ExecutorService PROBES=Executors.newFixedThreadPool(4);
  private static final java.util.regex.Pattern TYPE=
      java.util.regex.Pattern.compile("[a-z][a-z0-9_.-]{0,79}");
  private static final java.util.regex.Pattern REQUEST=
      java.util.regex.Pattern.compile("[A-Za-z0-9_.:-]{8,100}");
  private static final int MAX_PROBES=24;
  private static final long PROBE_BUDGET_MS=5500;

  private static final class Choice {
    final String pkg,action;
    final int version;
    Choice(String p,String a,int v){pkg=p;action=a;version=v;}
  }

  static JSONObject route(Context owner,JSONObject input)throws Exception {
    String intent=input.optString("intent","").toLowerCase(java.util.Locale.ROOT);
    String requestId=input.optString("request_id","");
    String selected=input.optString("package","");
    JSONObject payload=input.optJSONObject("payload");
    if(payload==null)payload=new JSONObject();
    if(!TYPE.matcher(intent).matches()||!REQUEST.matcher(requestId).matches())
      throw new IllegalArgumentException("Invalid intent or durable request identifier");
    if(payload.toString().length()>4096)
      throw new IllegalArgumentException("Specialist payload exceeds 4096 characters");
    if(!selected.isEmpty()&&!selected.matches(
        "[a-zA-Z][a-zA-Z0-9_]*(\\.[a-zA-Z][a-zA-Z0-9_]*){1,12}"))
      throw new IllegalArgumentException("Invalid installed specialist package");

    JSONArray providers=AppBridge.list(owner).getJSONArray("apps");
    List<String> packages=new ArrayList<>();
    for(int i=0;i<providers.length();i++){
      JSONObject app=providers.optJSONObject(i);
      if(app==null||!app.optBoolean("approved",false))continue;
      String name=app.optString("package","");
      if(!selected.isEmpty()&&!selected.equals(name))continue;
      packages.add(name);
      if(packages.size()>=MAX_PROBES)break;
    }
    if(!selected.isEmpty()&&packages.isEmpty())
      return new JSONObject().put("routed",false).put("intent",intent)
        .put("status","partner_not_approved").put("package",selected)
        .put("requires_owner_local_approval",true);

    long begin=SystemClock.elapsedRealtime();
    List<Future<JSONObject>> tasks=new ArrayList<>();
    for(String pkg:packages){
      tasks.add(PROBES.submit(new Callable<JSONObject>(){
        @Override public JSONObject call() throws Exception{
          return AppBridge.capabilities(owner,pkg);
        }
      }));
    }
    List<Choice> matches=new ArrayList<>();
    int checked=0;
    long deadline=begin+PROBE_BUDGET_MS;
    try{
      for(int i=0;i<tasks.size();i++){
        long remaining=deadline-SystemClock.elapsedRealtime();
        if(remaining<=0)break;
        JSONObject pack;
        try{pack=tasks.get(i).get(remaining,TimeUnit.MILLISECONDS);}
        catch(Exception unavailable){continue;}
        checked++;
        if(!pack.optBoolean("ok",false)||!pack.optBoolean("owner_approved",false))
          continue;
        JSONArray actions=pack.optJSONArray("actions");
        if(actions==null)continue;
        for(int j=0;j<actions.length();j++){
          JSONObject operation=actions.optJSONObject(j);
          if(operation==null||!intent.equals(operation.optString("intent","")))continue;
          matches.add(new Choice(pack.getString("package"),
            operation.getString("name"),pack.optInt("pack_version",0)));
        }
      }
    }finally{
      for(Future<JSONObject> future:tasks)if(!future.isDone())future.cancel(true);
    }
    int observedMs=(int)(SystemClock.elapsedRealtime()-begin);
    if(matches.isEmpty())
      return new JSONObject().put("routed",false).put("intent",intent)
        .put("status","no_approved_signed_specialist_capability")
        .put("providers_checked",checked)
        .put("discovery_complete",checked==packages.size()&&
             providers.length()<=MAX_PROBES)
        .put("lookup_ms",observedMs);
    if(matches.size()>1){
      JSONArray alternatives=new JSONArray();
      for(Choice c:matches)
        alternatives.put(new JSONObject().put("package",c.pkg)
          .put("action",c.action).put("pack_version",c.version));
      return new JSONObject().put("routed",false).put("intent",intent)
        .put("status","ambiguous_signed_capabilities")
        .put("choices",alternatives).put("lookup_ms",observedMs);
    }
    Choice approved=matches.get(0);
    JSONObject invocation=new JSONObject().put("package",approved.pkg)
        .put("action",approved.action)
        .put("payload",payload)
        .put("request_id",requestId);
    // Single, owner-approved typed action, already idempotent before Binder.
    JSONObject receipt=AppBridge.invoke(owner,invocation);
    return new JSONObject().put("routed",true).put("intent",intent)
        .put("package",approved.pkg).put("action",approved.action)
        .put("pack_version",approved.version)
        .put("status",receipt.optString("status","outcome_unknown"))
        .put("ok",receipt.optBoolean("ok",false))
        .put("request_id",requestId).put("result",receipt)
        .put("lookup_ms",observedMs);
  }
}
