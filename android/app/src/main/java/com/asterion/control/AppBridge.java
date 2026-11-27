package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ProviderInfo;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import android.content.pm.SigningInfo;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import org.json.JSONArray;
import org.json.JSONObject;
import java.security.MessageDigest;
import java.util.Map;
import java.util.regex.Pattern;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/** Opt-in cross-app protocol. Asterion Control is a transport, never a replacement engine.
 * Partner applications MUST independently verify the caller and authorize each action.
 * Only a provider with the exact package + ".asterion.bridge" authority is admitted.
 */
final class AppBridge {
  private AppBridge(){}
  private static final String PREF="app_bridge_v1";
  private static final Pattern PACKAGE=Pattern.compile(
      "[a-zA-Z][a-zA-Z0-9_]*(\\.[a-zA-Z][a-zA-Z0-9_]*){1,12}");
  private static final Pattern ACTION=Pattern.compile("[a-z][a-z0-9_.-]{0,79}");
  private static final Pattern REQUEST_ID=Pattern.compile("[A-Za-z0-9_.:-]{8,100}");
  private static final Object LOCK=new Object();
  private static final ExecutorService CALLS=Executors.newFixedThreadPool(2);
  private static SharedPreferences prefs(Context ctx){
    return ctx.getSharedPreferences(PREF,Context.MODE_PRIVATE);
  }
  private static String authority(String pkg){return pkg+".asterion.bridge";}
  private static ProviderInfo provider(Context ctx,String pkg) throws Exception {
    if(pkg==null||!PACKAGE.matcher(pkg).matches()||!AppCatalog.launchable(ctx).containsKey(pkg))
      throw new IllegalArgumentException("App not installed or not visible in owner launcher");
    ProviderInfo info=ctx.getPackageManager().resolveContentProvider(authority(pkg),0);
    if(info==null||!pkg.equals(info.packageName)||!info.exported)
      throw new IllegalStateException("App does not provide an exported Asterion v1 bridge");
    return info;
  }
  private static String signer(Context ctx,String pkg)throws Exception{
    PackageManager pm=ctx.getPackageManager();
    byte[] cert;
    if(Build.VERSION.SDK_INT>=28){
      PackageInfo details=pm.getPackageInfo(pkg,PackageManager.GET_SIGNING_CERTIFICATES);
      SigningInfo info=details.signingInfo;
      if(info==null)throw new SecurityException("Application signature unavailable");
      Signature[] signed=info.getApkContentsSigners(); // Pin current APK signer, not historical rotation ancestors.
      if(signed==null||signed.length==0)throw new SecurityException("Application signing identity unavailable");
      cert=signed[0].toByteArray();
    }else{
      PackageInfo details=pm.getPackageInfo(pkg,PackageManager.GET_SIGNATURES);
      if(details.signatures==null||details.signatures.length==0)
        throw new SecurityException("Application signing identity unavailable");
      cert=details.signatures[0].toByteArray();
    }
    byte[] sha=MessageDigest.getInstance("SHA-256").digest(cert);
    StringBuilder hex=new StringBuilder();
    for(byte b:sha)hex.append(String.format(java.util.Locale.US,"%02x",b&255));
    return hex.toString();
  }
  static JSONObject list(Context ctx)throws Exception{
    JSONArray found=new JSONArray();
    for(Map.Entry<String,String> app:AppCatalog.launchable(ctx).entrySet()){
      String pkg=app.getKey();
      ProviderInfo info=ctx.getPackageManager().resolveContentProvider(authority(pkg),0);
      if(info==null||!pkg.equals(info.packageName)||!info.exported)continue;
      String fingerprint;
      try{fingerprint=signer(ctx,pkg);}catch(Exception e){continue;}
      boolean allowed=fingerprint.equals(prefs(ctx).getString("approved:"+pkg,""));
      found.put(new JSONObject().put("package",pkg).put("name",app.getValue())
        .put("authority",authority(pkg)).put("protocol","asterion.v1")
        .put("approved",allowed).put("requires_local_approval",!allowed));
      if(found.length()>=100)break;
    }
    return new JSONObject().put("protocol","asterion.v1").put("apps",found)
      .put("approval","on_device_only")
      .put("notes","An empty list means partner repositories have not yet installed the v1 bridge");
  }
  /** Signed specialist-defined capability pack, read-only and versioned.
   * Capabilities are declarative. Control NEVER reconstructs specialist engines
   * or speculatively invokes an action not explicitly advertised by that app.
   * Legacy providers missing this contract remain visible but not routable.
   */
  static JSONObject capabilities(Context ctx,String pkg)throws Exception{
    provider(ctx,pkg);
    String expected=prefs(ctx).getString("approved:"+pkg,"");
    if(expected.isEmpty()||!expected.equals(signer(ctx,pkg)))
      throw new SecurityException("Partner is not locally approved or signing identity changed");
    Bundle arg=new Bundle();
    arg.putInt("protocol_version",1);
    Bundle response;
    try{
      Future<Bundle> task=CALLS.submit(()->ctx.getContentResolver().call(
        Uri.parse("content://"+authority(pkg)),"asterion.v1.capabilities",null,arg));
      try{response=task.get(4,TimeUnit.SECONDS);}
      catch(TimeoutException timeout){
        task.cancel(true);
        return new JSONObject().put("ok",false).put("package",pkg)
            .put("capabilities_available",false).put("reason","signed_partner_capability_timeout");
      }
    }catch(Exception failure){
      return new JSONObject().put("ok",false).put("package",pkg)
          .put("capabilities_available",false)
          .put("reason","signed_partner_did_not_publish_capabilities");
    }
    if(response==null)
      return new JSONObject().put("ok",false).put("package",pkg)
          .put("capabilities_available",false).put("reason","no_partner_capabilities");
    String raw=response.getString("result_json","");
    if(raw.length()>8192)throw new IllegalStateException("Partner capability pack too large");
    JSONObject pack;
    try{pack=new JSONObject(raw);}
    catch(Exception invalid){
      return new JSONObject().put("ok",false).put("package",pkg)
          .put("capabilities_available",false).put("reason","invalid_partner_capabilities");
    }
    int version=pack.optInt("pack_version",0);
    JSONArray offered=pack.optJSONArray("actions");
    if(version<1||version>1000||offered==null||offered.length()>80)
      return new JSONObject().put("ok",false).put("package",pkg)
          .put("capabilities_available",false).put("reason","unsupported_partner_pack");
    JSONArray vetted=new JSONArray();
    for(int i=0;i<offered.length();i++){
      JSONObject entry=offered.optJSONObject(i);
      if(entry==null)continue;
      String action=entry.optString("name","");
      String intent=entry.optString("intent","");
      if(!ACTION.matcher(action).matches()||!ACTION.matcher(intent).matches())continue;
      vetted.put(new JSONObject().put("name",action).put("intent",intent));
    }
    // Optional partner-authored declarative knowledge. Legacy providers remain
    // valid and explicitly incomplete. Only bounded non-executable metadata is
    // retained; no arbitrary schema, URI, shell operation or private app file.
    JSONArray published=pack.optJSONArray("knowledge"),knowledge=new JSONArray();
    java.util.HashSet<String> seen=new java.util.HashSet<>();
    java.util.Set<String> categories=java.util.Set.of("mode","model","limit","known_issue","data_format","owner_change");
    if(published!=null&&published.length()<=40){
      for(int i=0;i<published.length();i++){
        JSONObject entry=published.optJSONObject(i);
        if(entry==null||entry.length()!=3)continue;
        if(!(entry.opt("category") instanceof String)||!(entry.opt("id") instanceof String)||
           !(entry.opt("description") instanceof String))continue;
        String category=entry.getString("category"),id=entry.getString("id"),description=entry.getString("description");
        if(!categories.contains(category)||!ACTION.matcher(id).matches()||
           description.isBlank()||description.length()>300||
           description.codePoints().anyMatch(x->Character.isISOControl(x)&&x!=10&&x!=9)||
           !seen.add(category+":"+id))continue;
        knowledge.put(new JSONObject().put("category",category).put("id",id).put("description",description));
      }
    }
    String installedVersion="unknown";long installedCode=0;
    try{
      PackageInfo installed=ctx.getPackageManager().getPackageInfo(pkg,0);
      installedVersion=installed.versionName==null?"unknown":installed.versionName;
      installedCode=installed.getLongVersionCode();
    }catch(Exception ignored){}
    JSONArray missing=new JSONArray();
    for(String category:new String[]{"mode","model","limit","known_issue","data_format","owner_change"}){
      boolean found=false;
      for(int i=0;i<knowledge.length();i++)if(category.equals(knowledge.getJSONObject(i).getString("category"))){found=true;break;}
      if(!found)missing.put(category);
    }
    return new JSONObject().put("ok",true).put("package",pkg)
        .put("protocol","asterion.v1")
        .put("capabilities_available",true)
        .put("owner_approved",true)
        .put("pack_version",version)
        .put("installed_version",installedVersion)
        .put("installed_version_code",installedCode)
        .put("observed_at_ms",System.currentTimeMillis())
        .put("knowledge",knowledge)
        .put("unpublished_knowledge_categories",missing)
        .put("actions",vetted)
        .put("actions_count",vetted.length());
  }

  static JSONObject approveLocally(Context ctx,String pkg,boolean approve)throws Exception{
    // This function is intentionally NOT accessible through network or MCP commands.
    if(MainActivity.foregroundActivity()==null)throw new SecurityException("Local owner screen required");
    provider(ctx,pkg);
    String fingerprint=signer(ctx,pkg);
    boolean saved=prefs(ctx).edit().putString("approved:"+pkg,approve?fingerprint:"").commit();
    if(!saved)throw new IllegalStateException("Could not persist local owner approval");
    return new JSONObject().put("package",pkg).put("approved",approve)
      .put("protocol","asterion.v1");
  }
  static JSONObject invoke(Context ctx,JSONObject input)throws Exception{
    String pkg=input.getString("package"),action=input.getString("action"),
      requestId=input.getString("request_id");
    if(!ACTION.matcher(action).matches()||!REQUEST_ID.matcher(requestId).matches())
      throw new IllegalArgumentException("Invalid app action or idempotency request ID");
    JSONObject data=input.optJSONObject("payload");
    if(data==null)data=new JSONObject();
    if(data.toString().length()>4096)throw new IllegalArgumentException("Payload exceeds 4096 characters");
    provider(ctx,pkg);
    String expected=prefs(ctx).getString("approved:"+pkg,"");
    if(expected.isEmpty()||!expected.equals(signer(ctx,pkg)))
      throw new SecurityException("App bridge not approved on device or its signature has changed");
    String receiptKey="request:"+requestId;
    String binding=pkg+"/"+action;
    synchronized(LOCK){
      String old=prefs(ctx).getString(receiptKey,"");
      if(!old.isEmpty())return new JSONObject().put("ok",false)
        .put("duplicate",true).put("status",old.startsWith(binding+"|")?
          old.substring(binding.length()+1):"request_id_collision")
        .put("request_id",requestId);
      // Commit prior to Binder call: an uncertain timeout MUST NOT replay a side effect.
      if(!prefs(ctx).edit().putString(receiptKey,binding+"|submitted_unknown").commit())
        throw new IllegalStateException("Unable to save durable operation receipt");
    }
    Bundle args=new Bundle();
    args.putInt("protocol_version",1);
    args.putString("request_id",requestId);
    args.putString("action",action);
    args.putString("payload_json",data.toString());
    String status="outcome_unknown";
    try{
      Future<Bundle> executing=CALLS.submit(()->ctx.getContentResolver().call(
        Uri.parse("content://"+authority(pkg)),"asterion.v1.invoke",null,args));
      Bundle result;
      try{result=executing.get(7L,TimeUnit.SECONDS);}
      catch(TimeoutException timeout){
        executing.cancel(true);
        throw new IllegalStateException("Partner bridge timed out; outcome uncertain");
      }
      if(result==null)throw new IllegalStateException("App returned no result");
      String raw=result.getString("result_json","");
      if(raw.length()>8192)throw new IllegalStateException("Partner result exceeds size limit");
      JSONObject receipt=raw.isEmpty()?new JSONObject():new JSONObject(raw);
      status=receipt.optString("status",receipt.optBoolean("ok")?"completed":"rejected");
      if(!status.matches("[a-z_]{2,35}"))status="outcome_unknown";
      synchronized(LOCK){
        prefs(ctx).edit().putString(receiptKey,binding+"|"+status).commit();
      }
      return new JSONObject().put("ok",receipt.optBoolean("ok"))
        .put("package",pkg).put("request_id",requestId)
        .put("status",status).put("result",receipt);
    }catch(Exception e){
      // Do NOT retry, including after a remote Binder failure.
      return new JSONObject().put("ok",false)
        .put("package",pkg).put("request_id",requestId)
        .put("status","outcome_unknown")
        .put("reason","Partner bridge failed or result was uncertain: "+e.getClass().getSimpleName())
        .put("retry_safe",false);
    }
  }
  /** Query an already submitted operation; no action replay occurs. */
  static JSONObject operation(Context ctx,String pkg,String requestId,boolean cancel)throws Exception{
    if(!REQUEST_ID.matcher(requestId).matches())throw new IllegalArgumentException("Invalid request ID");
    provider(ctx,pkg);
    String cert=prefs(ctx).getString("approved:"+pkg,"");
    if(cert.isEmpty()||!cert.equals(signer(ctx,pkg)))
      throw new SecurityException("Bridge approval missing or signing identity changed");
    String saved=prefs(ctx).getString("request:"+requestId,"");
    if(!saved.startsWith(pkg+"/")||saved.indexOf('|')<0)
      throw new IllegalArgumentException("No matching previously submitted request");
    Bundle extras=new Bundle();
    extras.putInt("protocol_version",1);
    extras.putString("request_id",requestId);
    String operation=cancel?"asterion.v1.cancel":"asterion.v1.status";
    try{
      Future<Bundle> executing=CALLS.submit(()->ctx.getContentResolver().call(
        Uri.parse("content://"+authority(pkg)),operation,requestId,extras));
      Bundle reply;
      try{reply=executing.get(6L,TimeUnit.SECONDS);}
      catch(TimeoutException timeout){
        executing.cancel(true);
        throw new IllegalStateException("Partner outcome uncertain");
      }
      if(reply==null)throw new IllegalStateException("No partner response");
      String raw=reply.getString("result_json","");
      if(raw.length()>8192)throw new IllegalStateException("Partner response too long");
      JSONObject result=raw.isEmpty()?new JSONObject():new JSONObject(raw);
      String outcome=result.optString("status",cancel?"cancel_requested":"status_unknown");
      if(!outcome.matches("[a-z_]{2,35}"))outcome="status_unknown";
      if(!cancel){
        String action=saved.substring(pkg.length()+1,saved.indexOf('|'));
        synchronized(LOCK){
          prefs(ctx).edit().putString("request:"+requestId,pkg+"/"+action+"|"+outcome).commit();
        }
      }
      return new JSONObject().put("ok",result.optBoolean("ok",true))
        .put("package",pkg).put("request_id",requestId)
        .put("status",outcome).put("result",result);
    }catch(Exception e){
      return new JSONObject().put("ok",false).put("package",pkg)
        .put("request_id",requestId).put("status","outcome_unknown")
        .put("reason","Partner did not confirm "+(cancel?"cancellation":"status")+
          ": "+e.getClass().getSimpleName()).put("retry_safe",false);
    }
  }

}
