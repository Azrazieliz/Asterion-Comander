package com.asterion.control;

import org.json.JSONObject;

/** Receipt projection is local, typed and intentionally narrower than Binder output.
 * The provider is authoritative for its own observation, not independent proof of
 * completion. Free-form provider text, paths, account identifiers and payloads
 * must not become model instructions or persistent history. */
final class AssistantPartnerEvidence {
    private AssistantPartnerEvidence(){}
    private static void scalars(JSONObject from,JSONObject to,String... keys)throws Exception{
        if(from==null)return;
        for(String key:keys){
            Object value=from.opt(key);
            if(value instanceof Boolean)to.put(key,value);
            else if(value instanceof Number){
                double number=((Number)value).doubleValue();
                if(Double.isFinite(number)&&number>=0)to.put(key,value);
            }
        }
    }
    private static void nested(JSONObject from,JSONObject to,String key,String... fields)throws Exception{
        JSONObject source=from.optJSONObject(key);
        if(source==null)return;
        JSONObject out=new JSONObject();scalars(source,out,fields);
        JSONObject counts=source.optJSONObject("counts");
        if(counts!=null){
            JSONObject safe=new JSONObject();
            scalars(counts,safe,"queued","running","completed","failed","cancelled","paused",
                "ENQUEUED","RUNNING","SUCCEEDED","FAILED","BLOCKED","CANCELLED",
                "enqueued","succeeded","blocked","pending","downloading");
            if(safe.length()>0)out.put("counts",safe);
        }
        if(out.length()>0)to.put(key,out);
    }
    static String capture(AssistantActionRecord record,JSONObject envelope)throws Exception{
        if(envelope==null||!record.requestId.equals(envelope.optString("request_id"))||
            !record.appPackage.equals(envelope.optString("package"))||
            !"completed".equals(envelope.optString("status")))return "";
        JSONObject receipt=envelope.optJSONObject("result");
        if(receipt==null||!receipt.optBoolean("ok",false)||!"completed".equals(receipt.optString("status")))return "";
        if(receipt.has("request_id")&&!record.requestId.equals(receipt.optString("request_id")))return "";
        if(receipt.has("action")&&!record.action.equals(receipt.optString("action")))return "";
        JSONObject result=new JSONObject();
        if("status".equals(record.action)||"diagnostics.summary".equals(record.action)||
           "models.status".equals(record.action)){
            JSONObject e=receipt.optJSONObject("evidence");
            if(e==null||!record.appPackage.equals(e.optString("package")))return "";
            scalars(e,result,"version_code","android_sdk","process_response_verified","process_heap_used_bytes",
                "process_pss_kb","engine_telemetry_available","engine_queue_state_verified",
                "models_available_verified","private_files_read","android_historical_exits_count");
            nested(e,result,"videoflow","database_present","stored_queue_counts_verified","live_workers_verified",
                "items_counted","last_persisted_update_ms");
            nested(e,result,"workmanager","database_present","stored_work_counts_verified",
                "work_execution_now_verified","total_records");
            nested(e,result,"model_storage","installed_gguf_count","installed_bytes","model_loaded_verified",
                "inference_available_to_control","model_download_active_verified");
        }else if("rounder.inventory.meta".equals(record.action)){
            JSONObject e=receipt.optJSONObject("result");
            if(e==null||!"completed".equals(e.optString("status")))return "";
            scalars(e,result,"entries","folders","files","total_file_bytes","indexed","index_building",
                "complete_for_index_generation");
        }else if("rounder.inventory.page".equals(record.action)){
            JSONObject e=receipt.optJSONObject("result");
            if(e==null||!"completed".equals(e.optString("status")))return "";
            scalars(e,result,"count","has_more");
        }
        if(result.length()==0)return "";
        String data=new JSONObject().put("observed_at_ms",System.currentTimeMillis())
            .put("scope","provider_reported_metadata_only").put("values",result).toString();
        return data.length()<=3000?data:"";
    }
}
