package com.asterion.control;

import android.content.Context;
import org.json.JSONObject;
import org.json.JSONArray;
import java.util.Locale;
import java.util.regex.Pattern;

/** Read-only local evidence from existing Control implementations. No secrets,
 * private transcript, remote operations, external probes or model-selected
 * permission changes. A snapshot is not a functional acceptance certificate.
 */
final class AssistantLocalContext {
    private AssistantLocalContext(){}
    interface Read {JSONObject get()throws Exception;}
    static boolean wants(String query,String regex){
        return Pattern.compile("(?iu)(?:^|[^\\p{L}\\p{N}])(?:"+regex+")(?:$|[^\\p{L}\\p{N}])").matcher(query).find();
    }
    private static void add(JSONObject out,String name,Read read,String... allowed)throws Exception{
        try{
            JSONObject raw=read.get(),safe=new JSONObject();
            for(String key:allowed){
                Object value=raw.opt(key);
                if(value instanceof Boolean||value instanceof Number)safe.put(key,value);
                else if(value instanceof String&&((String)value).length()<=120)safe.put(key,value);
            }
            out.put(name,safe);
        }catch(Exception unavailable){out.put(name,new JSONObject().put("observation","unavailable"));}
    }
    static String observe(Context c,String query)throws Exception{
        JSONObject out=new JSONObject();
        boolean general=wants(query,"device status|phone status|system status|diagnostics|état du téléphone|diagnostic");
        if(general||wants(query,"network|internet|wifi|wi-fi|wss|relay|connection|réseau|connexion|connectivité")){
            add(out,"network",()->TransportConnectivity.report(c),"network","connected","validated","metered","data_saver_restricted","requires_pc_for_phone_commands");
            add(out,"native_wss",()->PhoneDirectMcp.status(),"connected","phase","last_success_ms","requires_github","phone_outbound_tls");
        }
        if(general||wants(query,"vpn|wireguard|tunnel")){
            add(out,"vpn",()->ControlPrivateVpn.status(c),"backend","active","state","configuration_present","peer_reachability_verified");
        }
        if(general||wants(query,"voice|microphone|speaker|wake word|voix|haut-parleur")){
            add(out,"voice",()->{
                VoiceDialogueService voice=VoiceDialogueService.active;
                return voice==null?new JSONObject().put("enabled",false).put("phase","stopped"):voice.report();
            },"enabled","phase","microphone_active","owner_voice_route","always_listening_enabled","ambient_recognizer_active","speaker_started","speaker_finished","on_device_recognition");
        }
        if(general||wants(query,"security|privacy|permissions|sécurité|confidentialité")){
            add(out,"security",()->ControlSecurityPolicy.status(c),"level","owner_local_only","android_permission_bypass","external_access_granted");
        }
        if(general||wants(query,"memory|ram|thermal|processor|resources|mémoire|température|ressources")){
            add(out,"resources",()->new OnDeviceModelResources(c).status(c),"device_model","soc_manufacturer","soc_model","available_processors","thermal_status","android_low_memory","available_bytes","total_bytes");
        }
        if(wants(query,"model status|model loaded|model version|modèle installé|modèle chargé|état du modèle")){
            add(out,"native_model",()->OnDeviceLlm.status(c),"native_library_loaded","model_name","model_loaded","model_sha_verified","weight_precision","configured_backend","configured_kv_bits","model_context_tokens","external_server_required");
        }
        if(wants(query,"cycle|cycles|development cycle")){
            add(out,"development_cycle",()->ContinuationCycle.get(c).status(),"active","state","index","ack_count","rollover_count","continuation_enabled");
        }
        if(wants(query,"schedule|schedules|scheduled|reminder|reminders|rappel|rappels|planification")){
            add(out,"schedules",()->{
                JSONArray list=AssistantSchedules.list(c);
                int enabled=0,active=0;
                for(int i=0;i<list.length();i++){
                    JSONObject r=list.getJSONObject(i);
                    if(r.optBoolean("enabled"))enabled++;
                    if(AssistantSchedules.active(r))active++;
                }
                return new JSONObject().put("count",list.length()).put("enabled",enabled).put("active",active).put("service_running",AgentService.running);
            },"count","enabled","active","service_running");
        }
        if(out.length()==0)return "";
        return "Current native Control read-only observations, captured at "+System.currentTimeMillis()+
            " epoch milliseconds. These are actual local state observations; they do not prove external network tests, successful installation or functional acceptance. Unavailable fields are unknown. "+out;
    }
}
