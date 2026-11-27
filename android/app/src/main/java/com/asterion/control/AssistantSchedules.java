package com.asterion.control;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.UUID;

/** Extends the existing owner-enabled AgentService tick and native inference queue.
 * No external calls, no new model engine, no automatic dispatch of model-proposed actions.
 */
final class AssistantSchedules {
    private static final Object LOCK=new Object();
    private static JSONArray rows;
    private static final int MAX=32;
    private static final String CHANNEL="asterion_local_schedules";
    private static JSONArray state(Context c)throws Exception{
        if(rows==null){
            JSONArray loaded=ControlAssistantMemory.loadSchedules(c);
            if(loaded.length()>MAX)throw new IllegalStateException("schedule_count_budget");
            rows=loaded;
        }
        return rows;
    }
    private static JSONArray copy(Context c)throws Exception{return new JSONArray(state(c).toString());}
    private static void commit(Context c,JSONArray updated)throws Exception{
        ControlAssistantMemory.saveSchedules(c,updated);rows=updated;
    }
    private static JSONObject find(JSONArray a,String id)throws Exception{
        for(int i=0;i<a.length();i++)if(a.getJSONObject(i).getString("id").equals(id))return a.getJSONObject(i);
        throw new IllegalArgumentException("Schedule unavailable");
    }
    static JSONArray list(Context c)throws Exception{synchronized(LOCK){return copy(c);}}
    static boolean active(JSONObject r){return "submitted".equals(r.optString("last_state"))||"reserved".equals(r.optString("last_state"));}
    static String create(Context c,AssistantSchedulePlan p,String id)throws Exception{
        synchronized(LOCK){
            if(id==null)id=UUID.randomUUID().toString();
            if(!id.matches("[a-f0-9-]{36}"))throw new IllegalArgumentException("Invalid schedule identity");
            JSONArray a=copy(c);
            for(int i=0;i<a.length();i++){
                JSONObject prior=a.getJSONObject(i);
                if(prior.getString("id").equals(id)){
                    if(!prior.getString("kind").equals(p.kind)||!prior.getString("prompt").equals(p.prompt)||
                        !prior.getString("title").equals(p.title)||prior.getInt("interval_minutes")!=p.intervalMinutes||
                        prior.getInt("delay_minutes")!=p.delayMinutes)throw new IllegalArgumentException("Schedule identity conflict");
                    return id;
                }
            }
            if(a.length()>=MAX)throw new IllegalStateException("32 local schedules maximum; review old tasks");
            if(p.kind.equals("inference")&&p.prompt.length()>OnDeviceModelProfile.read(c).inputChars)
                throw new IllegalArgumentException("Prompt exceeds installed model input budget");
            a.put(new JSONObject().put("id",id).put("kind",p.kind).put("title",p.title).put("prompt",p.prompt)
                .put("delay_minutes",p.delayMinutes).put("interval_minutes",p.intervalMinutes)
                .put("enabled",true).put("next_ms",AssistantSchedulePlan.first(System.currentTimeMillis(),p.delayMinutes))
                .put("last_state","not_run").put("last_result","").put("last_finished_ms",0));
            commit(c,a);return id;
        }
    }
    static void pause(Context c,String id,boolean resume)throws Exception{
        synchronized(LOCK){
            JSONArray a=copy(c);JSONObject r=find(a,id);
            if(resume){
                long due=r.getLong("next_ms");
                if(due==0)throw new IllegalStateException("One-time task has already been claimed; create a new task");
                if(due<=System.currentTimeMillis())
                    r.put("next_ms",AssistantSchedulePlan.first(System.currentTimeMillis(),r.getInt("interval_minutes")==0?1:r.getInt("interval_minutes")));
            }
            r.put("enabled",resume);commit(c,a);
        }
    }
    static void delete(Context c,String id)throws Exception{
        synchronized(LOCK){
            JSONArray a=copy(c);JSONObject r=find(a,id);
            if(active(r))throw new IllegalStateException("Wait for the running occurrence or cancel it first");
            for(int i=0;i<a.length();i++)if(a.getJSONObject(i).getString("id").equals(id)){a.remove(i);break;}
            commit(c,a);
        }
    }
    static void cancel(Context c,String id)throws Exception{
        synchronized(LOCK){
            JSONObject r=find(state(c),id);
            if(active(r)&&r.getString("kind").equals("inference"))
                OnDeviceAiJobs.cancel(c,r.getString("occurrence_id"));
        }
    }
    private static String notifyResult(Context c,String scheduleId){
        try{
            NotificationManager nm=c.getSystemService(NotificationManager.class);
            if(nm==null||!nm.areNotificationsEnabled())return "notification_unavailable";
            nm.createNotificationChannel(new NotificationChannel(CHANNEL,"Asterion scheduled tasks",NotificationManager.IMPORTANCE_DEFAULT));
            NotificationChannel channel=nm.getNotificationChannel(CHANNEL);
            if(channel==null||channel.getImportance()==NotificationManager.IMPORTANCE_NONE)return "notification_unavailable";
            Intent open=new Intent(c,MainActivity.class).putExtra("open_schedules",true);
            open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP);
            PendingIntent action=PendingIntent.getActivity(c,scheduleId.hashCode(),open,PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
            nm.notify("schedule-"+scheduleId,2301,new Notification.Builder(c,CHANNEL)
                .setSmallIcon(android.R.drawable.ic_menu_recent_history)
                .setContentTitle("Asterion scheduled task")
                .setContentText("Open Control to review the result.")
                .setVisibility(Notification.VISIBILITY_SECRET)
                .setContentIntent(action).setAutoCancel(true).build());
            return "notification_posted";
        }catch(Exception unavailable){return "notification_unavailable";}
    }
    private static void finish(Context c,JSONArray a,JSONObject r,String status,String output)throws Exception{
        r.put("last_state",status).put("last_result",output).put("last_finished_ms",System.currentTimeMillis())
            .put("notification","not_attempted");
        commit(c,a);
        // Persist result before notification; no notification replay after process death.
        if(status.equals("completed")){
            String notice=notifyResult(c,r.getString("id"));
            JSONArray next=copy(c);find(next,r.getString("id")).put("notification",notice);commit(c,next);
        }
    }
    static void tick(Context c)throws Exception{
        if(!AgentService.running)return;
        synchronized(LOCK){
            JSONArray a=copy(c);
            boolean inferenceActive=false;
            for(int i=0;i<a.length();i++){
                JSONObject r=a.getJSONObject(i);
                if(!active(r))continue;
                if(r.getString("kind").equals("reminder")){
                    finish(c,a,r,"outcome_unknown","Prior reminder dispatch was interrupted; not replayed.");return;
                }
                JSONObject observation;
                try{observation=OnDeviceAiJobs.status(c,r.getString("occurrence_id"));}
                catch(Exception unknown){
                    finish(c,a,r,"outcome_unknown","No recoverable inference receipt. No automatic replay.");return;
                }
                String phase=observation.optString("state","outcome_unknown");
                if("queued".equals(phase)||"running".equals(phase)||"cancel_requested".equals(phase)){inferenceActive=true;continue;}
                String answer=observation.optString("text","");
                if(phase.equals("completed")&&!answer.isBlank()){
                    if(answer.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>12000)finish(c,a,r,"failed","Generated result exceeded the retained output budget.");
                    else finish(c,a,r,"completed",answer);
                }else if(phase.equals("cancelled")||phase.equals("failed"))
                    finish(c,a,r,phase,"Local inference "+phase+". No external action was executed.");
                else finish(c,a,r,"outcome_unknown","Result unavailable after interruption. No automatic replay.");
                return;
            }
            long now=System.currentTimeMillis();
            JSONObject chosen=null;
            for(int i=0;i<a.length();i++){
                JSONObject r=a.getJSONObject(i);long due=r.getLong("next_ms");
                if(!r.optBoolean("enabled")||due<=0||due>now)continue;
                if(r.getString("kind").equals("inference")&&(inferenceActive||OnDeviceLlm.inferenceBusy()))continue;
                if(chosen==null||due<chosen.getLong("next_ms"))chosen=r;
            }
            if(chosen==null)return;
            JSONObject r=chosen;long due=r.getLong("next_ms");
            long next=AssistantSchedulePlan.next(due,now,r.getInt("interval_minutes"));
            String occurrence="schedule-"+r.getString("id")+"-"+due;
            r.put("occurrence_id",occurrence).put("last_due_ms",due).put("last_state","reserved")
                .put("last_result","").put("last_finished_ms",0).put("notification","not_attempted")
                .put("next_ms",next).put("enabled",next>0);
            commit(c,a);
            if(r.getString("kind").equals("reminder")){
                finish(c,a,r,"completed",r.getString("prompt"));return;
            }
            try{
                OnDeviceAiJobs.submit(c,new JSONObject().put("request_id",occurrence).put("prompt",r.getString("prompt")));
            }catch(Exception failure){
                finish(c,a,r,"outcome_unknown","Submission could not be confirmed. No automatic replay.");return;
            }
            JSONArray updated=copy(c);find(updated,r.getString("id")).put("last_state","submitted");commit(c,updated);
        }
    }
}
