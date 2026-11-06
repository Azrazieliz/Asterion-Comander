package com.asterion.control;

import android.os.Build;
import android.util.Base64;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Arrays;

/**
 * Stateless MCP JSON-RPC endpoint implemented on the owner's Android phone.
 *
 * No embedded model or planner: only authorized deterministic native tools.
 * Transport authentication is enforced by AgentService before handle().
 * Public remote exposure is NOT allowed without an authenticated TLS ingress.
 */
final class AndroidMcp {
  private static final String VERSION="2025-11-25";
  private AndroidMcp(){}

  private static JSONObject prop(String kind)throws Exception{
    return new JSONObject().put("type",kind);
  }
  private static JSONObject tool(String name,String description,JSONObject props,String... required)throws Exception{
    return new JSONObject().put("name",name).put("description",description)
      .put("inputSchema",new JSONObject().put("type","object")
        .put("properties",props==null?new JSONObject():props)
        .put("required",new JSONArray(Arrays.asList(required))));
  }
  private static JSONObject args(String... kv)throws Exception{
    JSONObject j=new JSONObject();
    for(int i=0;i<kv.length;i+=2)j.put(kv[i],prop(kv[i+1]));
    return j;
  }
  static JSONObject tools()throws Exception{
    JSONArray tools=new JSONArray();
    tools.put(tool("control_phone_status","Android native Control service, version and permissions",null));
    tools.put(tool("control_phone_bridge_status","Inspect optional phone-owned private GitHub fallback",null));
    tools.put(tool("control_phone_health","Android native battery, memory, thermal and screen state",null));
    tools.put(tool("control_phone_ui","Accessible active Android UI hierarchy",null));
    tools.put(tool("control_phone_screen","Current consented live native screen frame",null));
    tools.put(tool("control_phone_input","Authorized Android gesture or UI action",args(
      "action","string","x","number","y","number","x2","number","y2","number",
      "duration_ms","integer","text","string"),"action"));
    tools.put(tool("control_phone_apps","Discover launchable installed Android apps",null));
    tools.put(tool("control_phone_app_launch","Request app launch when Control is foreground",
      args("package","string"),"package"));
    tools.put(tool("control_phone_chat_new","Request New chat navigation; requires external visual confirmation",null));
    tools.put(tool("control_phone_continuation_status","Inspect owner-enabled checkpoint lifecycle",null));
    tools.put(tool("control_phone_continuation_queue","Queue canonical-project-referenced ChatGPT continuation",
      args("project","string","checkpoint_id","string","priority_tier","string",
        "spec_reference","string","message","string"),
      "project","checkpoint_id","priority_tier","spec_reference","message"));
    tools.put(tool("control_phone_continuation_dispatch","Attempt safe queued ChatGPT app submission",null));
    tools.put(tool("control_phone_continuation_ack","Acknowledge a real observed ChatGPT response",
      args("checkpoint_id","string","response_receipt","string"),"checkpoint_id","response_receipt"));
    tools.put(tool("control_phone_continuation_cancel","Cancel a queued/unverified-failure checkpoint",null));
    tools.put(tool("control_phone_observation_status","Inspect owner-selected app observation",null));
    tools.put(tool("control_phone_observation_events","Fetch bounded local observation events",null));
    tools.put(tool("control_phone_observation_frame","Fetch latest recorded selected-app frame",null));
    tools.put(tool("control_phone_observation_timeline","List retained sampled frames with timestamps",null));
    tools.put(tool("control_phone_observation_get_frame","Retrieve a selected retained gameplay evidence image",
      args("frame_id","string"),"frame_id"));
    tools.put(tool("control_phone_voice_status","Read owner-enabled on-device voice question state",null));
    tools.put(tool("control_phone_voice_question","Speak once; listen with owner-enabled microphone",
      args("text","string","locale","string","question_id","string"),"text"));
    tools.put(tool("control_phone_voice_ack","Acknowledge completed speech answer and erase transcript",
      args("question_id","string"),"question_id"));
    tools.put(tool("control_phone_cycle_status","Read durable ChatGPT checkpoint cycle state",null));
    tools.put(tool("control_phone_cycle_start","Start ACK-gated canonical checkpoint cycles",
      args("cycle_id","string","project","string","priority_tier","string",
        "spec_reference","string","message","string","conversation","string",
        "voice_locale","string","max_cycles","integer"),
      "cycle_id","project","priority_tier","spec_reference","message"));
    tools.put(tool("control_phone_cycle_pause","Pause checkpoint cycles",null));
    tools.put(tool("control_phone_cycle_resume","Resume verified checkpoint cycles",null));
    tools.put(tool("control_phone_cycle_stop","Stop future checkpoint cycles",null));
    tools.put(tool("control_phone_cycle_confirm_new_chat","Operator confirms a new ChatGPT conversation was actually observed",
      args("verification","string"),"verification"));
    tools.put(tool("control_phone_network_status","Inspect mobile-data, VPN and authenticated relay readiness",null));
    return new JSONObject().put("tools",tools);
  }
  private static JSONObject textContent(Object value)throws Exception{
    return new JSONObject().put("content",new JSONArray().put(
      new JSONObject().put("type","text").put("text",String.valueOf(value))));
  }
  private static JSONObject imageContent(byte[] jpeg)throws Exception{
    if(jpeg==null||jpeg.length==0)throw new IllegalStateException("Authorized screen frame not ready");
    return new JSONObject().put("content",new JSONArray().put(
      new JSONObject().put("type","image").put("mimeType","image/jpeg")
      .put("data",Base64.encodeToString(jpeg,Base64.NO_WRAP))));
  }
  private static JSONObject invoke(AgentService owner,String name,JSONObject args)throws Exception{
    ContinuationLedger ledger=ContinuationLedger.get(owner);
    switch(name){
      case "control_phone_status":
        return textContent(new JSONObject().put("ok",true).put("android",Build.VERSION.RELEASE)
          .put("device",Build.MODEL).put("capture",CaptureService.active)
          .put("accessibility",ControlAccessibilityService.active!=null)
          .put("version","0.9.0"));
      case "control_phone_bridge_status":return textContent(PhoneGitBridge.status(owner));
      case "control_phone_health":return textContent(owner.health());
      case "control_phone_ui":{
        ControlAccessibilityService service=ControlAccessibilityService.active;
        if(service==null)throw new IllegalStateException("Owner has not enabled Android Accessibility");
        return textContent(service.dump());
      }
      case "control_phone_screen":return imageContent(CaptureService.latest);
      case "control_phone_input":{
        ControlAccessibilityService access=ControlAccessibilityService.active;
        if(access==null)throw new IllegalStateException("Owner has not enabled Android Accessibility");
        return textContent(new JSONObject().put("ok",access.action(args)));
      }
      case "control_phone_apps":return textContent(AppCatalog.list(owner));
      case "control_phone_app_launch":return textContent(AppCatalog.requestLaunch(owner,args.getString("package")));
      case "control_phone_chat_new":{
        ControlAccessibilityService service=ControlAccessibilityService.active;
        if(service==null)throw new IllegalStateException("Accessibility not enabled");
        return textContent(service.requestNewChat());
      }
      case "control_phone_continuation_status":{
        JSONObject state=ledger.status();state.remove("pending");return textContent(state);
      }
      case "control_phone_continuation_queue":return textContent(ledger.queue(args));
      case "control_phone_continuation_dispatch":return textContent(ledger.dispatch());
      case "control_phone_continuation_ack":return textContent(ledger.acknowledge(
        args.getString("checkpoint_id"),args.getString("response_receipt")));
      case "control_phone_continuation_cancel":return textContent(ledger.cancel());
      case "control_phone_observation_status":return textContent(AppObservation.status(owner));
      case "control_phone_observation_events":return textContent(AppObservation.recentEvents(owner,80));
      case "control_phone_observation_frame":return imageContent(AppObservation.latestRecordedFrame(owner));
      case "control_phone_observation_timeline":return textContent(AppObservation.timeline(owner,100));
      case "control_phone_observation_get_frame":
        return imageContent(AppObservation.recordedFrame(owner,args.getString("frame_id")));
      case "control_phone_network_status":return textContent(TransportConnectivity.report(owner));
      case "control_phone_cycle_status":return textContent(ContinuationCycle.get(owner).status());
      case "control_phone_cycle_start":return textContent(ContinuationCycle.get(owner).start(args));
      case "control_phone_cycle_pause":return textContent(ContinuationCycle.get(owner).pause());
      case "control_phone_cycle_resume":return textContent(ContinuationCycle.get(owner).resume());
      case "control_phone_cycle_stop":return textContent(ContinuationCycle.get(owner).stop());
      case "control_phone_cycle_confirm_new_chat":return textContent(
        ContinuationCycle.get(owner).confirmNewChat(args.getString("verification")));
      case "control_phone_voice_status":{
        VoiceDialogueService voice=VoiceDialogueService.active;
        return textContent(voice==null?new JSONObject().put("enabled",false)
            .put("phase","stopped"):voice.report());
      }
      case "control_phone_voice_question":{
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null)throw new IllegalStateException("Owner has not enabled the microphone voice session");
        return textContent(voice.ask(args.getString("text"),args.optString("locale","en-US"),
          args.optString("question_id","")));
      }
      case "control_phone_voice_ack":{
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null)throw new IllegalStateException("Voice session not enabled");
        return textContent(voice.acknowledge(args.getString("question_id")));
      }
      default:throw new IllegalArgumentException("Unknown MCP tool: "+name);
    }
  }
  static JSONObject handle(AgentService owner,JSONObject message){
    Object id=message.opt("id");
    if(id==null||id==JSONObject.NULL)return null; // JSON-RPC notification
    JSONObject result=new JSONObject();
    try{
      result.put("jsonrpc","2.0").put("id",id);
      String method=message.optString("method","");
      switch(method){
        case "initialize":
          result.put("result",new JSONObject().put("protocolVersion",VERSION)
            .put("capabilities",new JSONObject().put("tools",new JSONObject()))
            .put("serverInfo",new JSONObject().put("name","asterion-control-android")
              .put("version","0.9.0")));
          break;
        case "ping":result.put("result",new JSONObject());break;
        case "tools/list":result.put("result",tools());break;
        case "tools/call":{
          JSONObject parameters=message.optJSONObject("params");
          if(parameters==null)throw new IllegalArgumentException("Missing tools/call params");
          String name=parameters.getString("name");
          JSONObject arguments=parameters.optJSONObject("arguments");
          result.put("result",invoke(owner,name,arguments==null?new JSONObject():arguments));
          break;
        }
        default:result.put("error",new JSONObject().put("code",-32601)
          .put("message","Unknown MCP method"));break;
      }
    }catch(Exception e){
      try{result.put("error",new JSONObject().put("code",-32000)
        .put("message",e.getClass().getSimpleName()+": "+String.valueOf(e.getMessage())));}
      catch(Exception ignored){}
    }
    return result;
  }
}
