package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Browser UI for the original signed transfer engine; it never downloads bytes itself. */
final class BrowserDownloadPanel {
    private static final ExecutorService IO=Executors.newSingleThreadExecutor();
    private final Activity owner;
    private final SharedPreferences journal;
    BrowserDownloadPanel(Activity a){
        owner=a;journal=a.getSharedPreferences("asterion_browser_session_v1",Context.MODE_PRIVATE);
    }
    private boolean alive(){return !owner.isFinishing()&&!owner.isDestroyed();}
    private void notice(String text){if(alive())Toast.makeText(owner,text,Toast.LENGTH_SHORT).show();}
    private JSONObject call(String method,Bundle args)throws Exception{
        Bundle result=owner.getContentResolver().call(BrowserDownloadProvider.uri(owner),method,null,args);
        if(result==null)throw new IllegalStateException("No internal transfer response");
        return new JSONObject(result.getString("result_json","{}"));
    }
    private TextView button(String title,Runnable action){
        TextView v=DesignSystem.text(owner,title,14,DesignSystem.TEXT,true);
        v.setGravity(Gravity.CENTER);v.setMinHeight(DesignSystem.dp(owner,48));
        v.setPadding(DesignSystem.dp(owner,12),0,DesignSystem.dp(owner,12),0);
        DesignSystem.clickable(v,owner,DesignSystem.SURFACE2,DesignSystem.EDGE,12);
        v.setOnClickListener(w->action.run());return v;
    }
    void choose(String url){
        if(!BrowserNavigationPolicy.isWeb(url)||url.length()>3500){notice("Unsupported specialist download address");return;}
        notice("Checking signed transfer engines");
        IO.execute(()->{
            try{
                JSONObject result=call("discover",new Bundle());
                JSONArray choices=result.optJSONArray("choices");
                owner.runOnUiThread(()->{
                    if(!alive())return;
                    if(choices==null||choices.length()==0){
                        JSONArray reasons=result.optJSONArray("unavailable");
                        StringBuilder details=new StringBuilder("No approved installed Downloader or Nexus provider advertises a download action.");
                        if(reasons!=null)for(int i=0;i<reasons.length();i++){
                            JSONObject reason=reasons.optJSONObject(i);
                            if(reason!=null)details.append("\n").append(reason.optString("package")).append(": ").append(reason.optString("reason").replace('_',' '));
                        }
                        new AlertDialog.Builder(owner).setTitle("Specialist transfer unavailable")
                            .setMessage(details.toString()).setPositiveButton("Close",null).show();return;
                    }
                    List<JSONObject> offered=new ArrayList<>();List<String> names=new ArrayList<>();
                    for(int i=0;i<choices.length();i++){
                        JSONObject item=choices.optJSONObject(i);
                        if(item==null)continue;offered.add(item);
                        names.add(item.optString("name")+" · "+item.optString("action"));
                    }
                    new AlertDialog.Builder(owner).setTitle("Send link to transfer engine")
                        .setItems(names.toArray(new String[0]),(d,n)->submit(url,offered.get(n)))
                        .setNegativeButton("Cancel",null).show();
                });
            }catch(Exception e){owner.runOnUiThread(()->notice("Signed transfer discovery unavailable"));}
        });
    }
    private JSONArray records(){
        try{return new JSONArray(journal.getString("specialist_download_receipts","[]"));}
        catch(Exception e){return new JSONArray();}
    }
    private JSONObject find(String id){
        JSONArray all=records();
        for(int i=0;i<all.length();i++){JSONObject row=all.optJSONObject(i);if(row!=null&&id.equals(row.optString("request_id")))return row;}
        return null;
    }
    private boolean store(JSONObject item){
        JSONArray old=records(),next=new JSONArray();
        next.put(item);
        for(int i=0;i<old.length();i++){
            JSONObject row=old.optJSONObject(i);
            if(row!=null&&!item.optString("request_id").equals(row.optString("request_id")))next.put(row);
        }
        // Never evict active or uncertain operation receipts.
        return journal.edit().putString("specialist_download_receipts",next.toString()).commit();
    }
    private void submit(String url,JSONObject engine){
        final String pkg=engine.optString("package"),action=engine.optString("action"),id="browser-"+UUID.randomUUID();
        if(!BrowserDownloadContract.canDispatch(pkg,"download",url,id)){notice("Invalid signed transfer");return;}
        IO.execute(()->{
            try{
                JSONObject row=new JSONObject().put("request_id",id).put("package",pkg)
                    .put("host",Uri.parse(url).getHost()).put("created_ms",System.currentTimeMillis())
                    .put("status","submission_unknown");
                if(!store(row))throw new IllegalStateException("Cannot save durable transfer receipt");
                Bundle request=args(row);request.putString("url",url);request.putString("action",action);
                JSONObject result=call("submit",request);
                row.put("status",result.optString("status","outcome_unknown"));
                store(row);
                owner.runOnUiThread(()->notice("Transfer: "+row.optString("status").replace('_',' ')));
            }catch(Exception e){owner.runOnUiThread(()->notice("Transfer outcome unavailable; check receipts before retrying"));}
        });
    }
    private Bundle args(JSONObject row){
        Bundle b=new Bundle();b.putString("package",row.optString("package"));b.putString("request_id",row.optString("request_id"));return b;
    }
    void show(){
        if(!alive())return;
        LinearLayout rows=DesignSystem.vertical(owner);rows.setPadding(DesignSystem.dp(owner,16),DesignSystem.dp(owner,8),DesignSystem.dp(owner,16),DesignSystem.dp(owner,8));
        ScrollView scroll=new ScrollView(owner);scroll.addView(rows);
        AlertDialog dialog=new AlertDialog.Builder(owner).setTitle("Specialist transfers").setView(scroll).setPositiveButton("Close",null).create();
        JSONArray all=records();
        if(all.length()==0)rows.addView(DesignSystem.text(owner,"No signed transfer receipts.",14,DesignSystem.MUTED,false));
        for(int i=0;i<all.length();i++){
            JSONObject row=all.optJSONObject(i);if(row==null)continue;
            String id=row.optString("request_id"),status=row.optString("status","outcome_unknown");
            TextView label=DesignSystem.text(owner,row.optString("host","Download")+" · "+status.replace('_',' '),15,DesignSystem.TEXT,true);
            label.setPadding(0,DesignSystem.dp(owner,12),0,DesignSystem.dp(owner,6));rows.addView(label);
            LinearLayout actions=DesignSystem.horizontal(owner);
            actions.addView(button("Check status",()->refresh(id,false,dialog)),new LinearLayout.LayoutParams(0,-2,1));
            if(!BrowserDownloadContract.terminal(status))actions.addView(button("Cancel",()->
                new AlertDialog.Builder(owner).setTitle("Request cancellation?").setMessage("Only the owning transfer engine can confirm cancellation.")
                    .setPositiveButton("Request",(d,w)->refresh(id,true,dialog)).setNegativeButton("Keep transfer",null).show()),new LinearLayout.LayoutParams(0,-2,1));
            rows.addView(actions);
        }
        dialog.show();
    }
    private void refresh(String id,boolean cancel,AlertDialog dialog){
        IO.execute(()->{
            JSONObject row=find(id);if(row==null)return;
            String feedback;
            try{
                JSONObject response=call(cancel?"cancel":"status",args(row));
                String state=response.optString("status","outcome_unknown");
                // Do not turn a refused cancellation into a completed cancellation.
                row.put("status",state);store(row);
                JSONObject receipt=response.optJSONObject("result");
                StringBuilder info=new StringBuilder(state.replace('_',' '));
                if(receipt!=null){
                    JSONObject progress=receipt.optJSONObject("progress");
                    if(progress==null)progress=receipt.optJSONObject("result");
                    if(progress!=null){
                        long received=progress.optLong("bytes_received",-1),total=progress.optLong("bytes_total",-1);
                        if(received>=0&&total>0&&received<=total)info.append("\n").append(received).append(" / ").append(total).append(" bytes");
                    }
                }
                feedback=info.toString();
            }catch(Exception e){feedback="Outcome unavailable; no replay was attempted.";}
            final String result=feedback;
            owner.runOnUiThread(()->{if(!alive()||!dialog.isShowing())return;
                new AlertDialog.Builder(owner).setTitle("Signed transfer receipt").setMessage(result)
                    .setPositiveButton("Close",(d,w)->{dialog.dismiss();show();}).show();
            });
        });
    }
}
