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
      Signature[] signed=info.hasMultipleSigners()?info.getApkContentsSigners():info.getSigningCertificateHistory();
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
      Bundle result=ctx.getContentResolver().call(Uri.parse("content://"+authority(pkg)),
        "asterion.v1.invoke",null,args);
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
}
