package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Pattern;

/**
 * Native model jobs, not an AI "available" badge. Actual OnDeviceLlm.generate()
 * is executed in the original Android process on a bounded background worker.
 * The authenticated existing phone WSS transports submission and results.
 *
 * Request receipts are durably reserved before execution. Sensitive prompts
 * and generated text are never stored in preferences, logs, GitHub or Windows.
 * A process death therefore reports OUTCOME_UNKNOWN (no fake finished answer).
 */
final class OnDeviceAiJobs {
    private OnDeviceAiJobs(){}
    private static final Object LOCK=new Object();
    private static final String JOURNAL="asterion_native_ai_receipts_v1";
    private static final Pattern ID=Pattern.compile("[A-Za-z0-9_.:-]{8,100}");
    private static final ExecutorService EXECUTOR=Executors.newSingleThreadExecutor(r->{
        Thread t=new Thread(r,"asterion-ondevice-llm");
        t.setDaemon(false);
        return t;
    });
    private static final HashMap<String,Job> jobs=new HashMap<>();
    private static final int MAX_LIVE=48;

    private static final class Job {
        final String id,sha;
        final long requestedAt;
        volatile String state="queued";
        volatile boolean cancelRequested=false;
        volatile String result="",error="";
        volatile long finishedAt=0;
        Job(String id,String sha){
            this.id=id;this.sha=sha;this.requestedAt=System.currentTimeMillis();
        }
    }
    private static SharedPreferences store(Context c){
        return c.getSharedPreferences(JOURNAL,Context.MODE_PRIVATE);
    }
    private static String sha(String value) throws Exception {
        byte[] bytes=MessageDigest.getInstance("SHA-256").digest(
            value.getBytes(StandardCharsets.UTF_8));
        StringBuilder out=new StringBuilder(64);
        for(byte b:bytes)out.append(String.format(Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    private static void validate(String id){
        if(id==null||!ID.matcher(id).matches())
            throw new IllegalArgumentException("Invalid durable native inference request ID");
    }
    private static JSONObject response(Job job)throws Exception{
        JSONObject obj=new JSONObject().put("request_id",job.id)
            .put("state",job.state).put("engine","on_device_llama_cpp")
            .put("requested_at_ms",job.requestedAt)
            .put("finished_at_ms",job.finishedAt)
            .put("retry_safe",false);
        if("completed".equals(job.state))
            obj.put("text",job.result).put("characters",job.result.length());
        if("failed".equals(job.state))obj.put("error_type",job.error);
        return obj;
    }
    private static void persist(Context ctx,Job job)throws Exception{
        JSONObject receipt=new JSONObject().put("request_id",job.id)
            .put("prompt_sha256",job.sha).put("state",job.state)
            .put("requested_at_ms",job.requestedAt)
            .put("finished_at_ms",job.finishedAt);
        if(!store(ctx).edit().putString(job.id,receipt.toString()).commit())
            throw new IllegalStateException("Durable native inference receipt write failed");
    }
    private static JSONObject persisted(Context c,String id)throws Exception{
        String json=store(c).getString(id,null);
        if(json==null)return null;
        JSONObject receipt=new JSONObject(json);
        String prior=receipt.optString("state","outcome_unknown");
        String effective="running".equals(prior)||"queued".equals(prior)||
            "cancel_requested".equals(prior) ? "outcome_unknown" : prior;
        return new JSONObject().put("request_id",id)
            .put("state",effective).put("engine","on_device_llama_cpp")
            .put("durable",true).put("result_in_memory",false)
            .put("reason","completed".equals(effective)?"result_not_retained_after_process_restart":
                "previous_process_outcome_unavailable")
            .put("retry_safe",false);
    }
    private static void prune(){
        if(jobs.size()<MAX_LIVE)return;
        ArrayList<Job> finished=new ArrayList<>();
        for(Job value:jobs.values())
            if("completed".equals(value.state)||"failed".equals(value.state)||
               "cancelled".equals(value.state))finished.add(value);
        finished.sort((a,b)->Long.compare(a.finishedAt,b.finishedAt));
        for(Job old:finished){
            if(jobs.size()<MAX_LIVE/2)break;
            jobs.remove(old.id);
        }
    }

    static JSONObject submit(Context ctx,JSONObject request)throws Exception{
        String id=request.getString("request_id");
        String prompt=request.getString("prompt");
        validate(id);
        if(prompt.isBlank()||prompt.length()>1800)
            throw new IllegalArgumentException("Native model prompt must be 1..1800 characters");
        String digest=sha(prompt);
        synchronized(LOCK){
            Job current=jobs.get(id);
            if(current!=null){
                if(!digest.equals(current.sha))
                    throw new IllegalArgumentException("Request ID reused with different prompt");
                return response(current).put("reused",true);
            }
            String old=store(ctx).getString(id,null);
            if(old!=null){
                JSONObject meta=new JSONObject(old);
                if(!digest.equals(meta.optString("prompt_sha256")))
                    throw new IllegalArgumentException("Durable request ID collision");
                return persisted(ctx,id).put("reused",true);
            }
            prune();
            if(jobs.size()>=MAX_LIVE)
                throw new IllegalStateException("Too many active native inference jobs");
            Job job=new Job(id,digest);
            persist(ctx,job);
            jobs.put(id,job);
            Context app=ctx.getApplicationContext();
            EXECUTOR.submit(()->execute(app,job,prompt));
            return response(job).put("reused",false);
        }
    }
    private static void execute(Context ctx,Job job,String prompt){
        synchronized(LOCK){
            if(job.cancelRequested){
                job.state="cancelled";job.finishedAt=System.currentTimeMillis();
                try{persist(ctx,job);}catch(Exception ignored){}
                return;
            }
            job.state="running";
            try{persist(ctx,job);}
            catch(Exception failure){
                job.state="failed";
                job.error="receipt_write_failed";
                job.finishedAt=System.currentTimeMillis();
                return;
            }
        }
        String output=null;
        String error="";
        try{output=OnDeviceLlm.generate(ctx,prompt);}
        catch(Exception|LinkageError failure){error=failure.getClass().getSimpleName();}
        synchronized(LOCK){
            job.finishedAt=System.currentTimeMillis();
            if(job.cancelRequested)job.state="cancelled";
            else if(error.isEmpty()&&output!=null&&!output.isBlank()){
                job.result=output;job.state="completed";
            }else{
                job.error=error.isEmpty()?"empty_native_output":error;
                job.state="failed";
            }
            try{persist(ctx,job);}
            catch(Exception failure){
                job.state="failed";job.error="receipt_write_failed";
                job.result="";
            }
        }
    }
    static JSONObject status(Context c,String id)throws Exception{
        validate(id);
        synchronized(LOCK){
            Job live=jobs.get(id);
            if(live!=null)return response(live);
            JSONObject last=persisted(c,id);
            if(last==null)throw new IllegalArgumentException("Native request ID not found");
            return last;
        }
    }
    static JSONObject cancel(Context c,String id)throws Exception{
        validate(id);
        synchronized(LOCK){
            Job job=jobs.get(id);
            if(job==null){
                JSONObject state=persisted(c,id);
                if(state==null)throw new IllegalArgumentException("Unknown native job ID");
                return state.put("cancel_effective",false);
            }
            if("completed".equals(job.state)||"failed".equals(job.state)||
                "cancelled".equals(job.state))
                return response(job).put("cancel_effective",false);
            job.cancelRequested=true;
            if("running".equals(job.state))OnDeviceLlm.cancel();
            job.state="cancel_requested";
            persist(c,job);
            return response(job).put("cancel_effective",true);
        }
    }
}
