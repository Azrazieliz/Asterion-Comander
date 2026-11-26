package com.asterion.control;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Binder;
import android.os.Bundle;
import android.os.Process;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Internal same-UID adapter to the ORIGINAL AppBridge in its owning main process.
 * Browser's isolated WebView process must not cache or independently mutate the
 * main-process approval/idempotency preferences. No exported or network endpoint.
 */
public final class BrowserDownloadProvider extends ContentProvider {
    static Uri uri(Context context){return Uri.parse("content://"+context.getPackageName()+".browser.download.internal");}
    @Override public boolean onCreate(){return true;}
    @Override public Bundle call(String method,String arg,Bundle extras){
        if(Binder.getCallingUid()!=Process.myUid())throw new SecurityException("Same application only");
        try{
            Context c=getContext();
            if(c==null)throw new IllegalStateException("Control context unavailable");
            JSONObject result;
            if("discover".equals(method))result=discover(c);
            else{
                if(extras==null)throw new IllegalArgumentException("Missing request");
                String pkg=extras.getString("package","");
                String id=extras.getString("request_id","");
                if(!BrowserDownloadContract.ownerPackage(pkg)||!BrowserDownloadContract.requestId(id))
                    throw new IllegalArgumentException("Not a Browser download operation");
                if("submit".equals(method)){
                    String url=extras.getString("url","");
                    String action=extras.getString("action","");
                    if(!BrowserDownloadContract.canDispatch(pkg,"download",url,id))
                        throw new IllegalArgumentException("Invalid download request");
                    // Revalidate the actual signed capability immediately before submission.
                    JSONObject pack=AppBridge.capabilities(c,pkg);
                    if(!pack.optBoolean("ok")||!pack.optBoolean("owner_approved")||
                        !advertised(pack,action))throw new SecurityException("Signed download capability unavailable");
                    result=AppBridge.invoke(c,new JSONObject().put("package",pkg).put("action",action)
                        .put("request_id",id).put("payload",new JSONObject().put("url",url)));
                }else if("status".equals(method)||"cancel".equals(method)){
                    result=AppBridge.operation(c,pkg,id,"cancel".equals(method));
                }else throw new IllegalArgumentException("Unknown internal method");
            }
            return reply(result);
        }catch(Exception e){
            JSONObject error=new JSONObject();
            try{error.put("ok",false).put("status","unavailable").put("reason",e.getClass().getSimpleName());}
            catch(Exception ignored){}
            return reply(error);
        }
    }
    private static boolean advertised(JSONObject pack,String action){
        JSONArray actions=pack.optJSONArray("actions");
        if(actions!=null)for(int i=0;i<actions.length();i++){
            JSONObject row=actions.optJSONObject(i);
            if(row!=null&&"download".equals(row.optString("intent"))&&action.equals(row.optString("name")))return true;
        }
        return false;
    }
    private static JSONObject discover(Context c)throws Exception{
        JSONArray installed=AppBridge.list(c).getJSONArray("apps");
        JSONArray choices=new JSONArray(),unavailable=new JSONArray();
        for(int i=0;i<installed.length();i++){
            JSONObject app=installed.optJSONObject(i);if(app==null)continue;
            String pkg=app.optString("package");
            if(!BrowserDownloadContract.ownerPackage(pkg))continue;
            if(!app.optBoolean("approved")){
                unavailable.put(new JSONObject().put("package",pkg).put("reason","owner_approval_required"));continue;
            }
            try{
                JSONObject pack=AppBridge.capabilities(c,pkg);
                JSONArray actions=pack.optJSONArray("actions");
                boolean found=false;
                if(pack.optBoolean("ok")&&pack.optBoolean("owner_approved")&&actions!=null)
                    for(int j=0;j<actions.length();j++){
                        JSONObject row=actions.optJSONObject(j);
                        if(row==null||!"download".equals(row.optString("intent")))continue;
                        choices.put(new JSONObject().put("package",pkg).put("name",app.optString("name",pkg))
                            .put("action",row.getString("name")));found=true;
                    }
                if(!found)unavailable.put(new JSONObject().put("package",pkg).put("reason","signed_download_not_advertised"));
            }catch(Exception e){unavailable.put(new JSONObject().put("package",pkg).put("reason","capability_unavailable"));}
        }
        return new JSONObject().put("ok",true).put("choices",choices).put("unavailable",unavailable);
    }
    private static Bundle reply(JSONObject data){Bundle out=new Bundle();out.putString("result_json",data.toString());return out;}
    @Override public Cursor query(Uri u,String[] p,String s,String[] a,String sort){return null;}
    @Override public String getType(Uri u){return null;}
    @Override public Uri insert(Uri u,ContentValues values){throw new UnsupportedOperationException();}
    @Override public int delete(Uri u,String s,String[] a){throw new UnsupportedOperationException();}
    @Override public int update(Uri u,ContentValues values,String s,String[] a){throw new UnsupportedOperationException();}
}
