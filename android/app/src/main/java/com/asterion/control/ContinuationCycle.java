package com.asterion.control;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Deterministic, phone-owned checkpoint cycle executor. ChatGPT remains the
 * external reasoning engine; Control never synthesizes model replies.
 *
 * A new turn is allowed ONLY after the previous checkpoint has a real
 * operator-issued response acknowledgment. A UI Send click is not an ack.
 * Durable stable IDs and ledger history prevent replay on Android restarts.
 */
final class ContinuationCycle {
  private static volatile ContinuationCycle singleton;
  private final AtomicFile disk;
  private final ContinuationLedger ledger;
  private JSONObject state;
  static synchronized ContinuationCycle get(Context context) {
    if(singleton==null)singleton=new ContinuationCycle(context.getApplicationContext());
    return singleton;
  }
  private ContinuationCycle(Context context) {
    disk=new AtomicFile(new File(context.getNoBackupFilesDir(),"continuation-cycle.json"));
    ledger=ContinuationLedger.get(context);
    try(FileInputStream in=disk.openRead()) {
      state=new JSONObject(new String(in.readAllBytes(),StandardCharsets.UTF_8));
    }catch(Exception ignored){state=new JSONObject();}
  }
  private void save()throws Exception {
    FileOutputStream out=disk.startWrite();
    try {
      out.write(state.toString().getBytes(StandardCharsets.UTF_8));
      out.flush();
      disk.finishWrite(out);
    }catch(Exception e){disk.failWrite(out);throw e;}
  }
  synchronized JSONObject status()throws Exception {
    JSONObject result=new JSONObject(state.toString());
    result.remove("instruction");
    return result.put("continuation_enabled",ledger.status().optBoolean("enabled",false));
  }
  synchronized JSONObject start(JSONObject input)throws Exception {
    if(!ledger.status().optBoolean("enabled",false))
      throw new IllegalStateException("Owner must enable checkpoint continuation before cycles");
    if(state.optBoolean("active",false))
      throw new IllegalStateException("A Control cycle is already active");
    String id=input.optString("cycle_id","").trim();
    String project=input.optString("project","").trim();
    String spec=input.optString("spec_reference","").trim();
    String tier=input.optString("priority_tier","").trim();
    String instruction=input.optString("message","").trim();
    String conversation=input.optString("conversation","same");
    String voiceLocale=input.optString("voice_locale","en-US");
    int maximum=input.optInt("max_cycles",0);
    // Owner-defined cycle is continuous. Zero means no artificial turn cap.
    // Each turn still requires a verified assistant reply before the next submission.
    // An explicit positive cap is an optional user choice, never an app default.
    if(!id.matches("[A-Za-z][A-Za-z0-9_.-]{2,65}")||
       !project.matches("[A-Za-z0-9_.-]{3,70}")||
       spec.length()<3||spec.length()>250||
       instruction.length()<1||instruction.length()>3000||
       !(tier.equals("5*")||tier.equals("6*")||tier.equals("7*"))||
       !("same".equals(conversation)||"new".equals(conversation))||
       !voiceLocale.matches("[a-z]{2}(-[A-Z]{2})?")||
       maximum<0||maximum>1000000)
      throw new IllegalArgumentException("Invalid canonical Control cycle parameters");
    if(id.equals(state.optString("cycle_id","")))
      throw new IllegalStateException("Reusing a prior cycle ID could replay checkpoint history");
    JSONObject current=ledger.status();
    String previous=current.optString("state","idle");
    if(!("idle".equals(previous)||"acknowledged".equals(previous)||
         "cancelled".equals(previous)||"failed".equals(previous)))
      throw new IllegalStateException("A prior ChatGPT checkpoint is still pending");
    // 'new' is permitted only when an external operator verifies navigation;
    // never silently assume a New chat click changes the current conversation.
    state=new JSONObject().put("active",true).put("state","ready")
      .put("cycle_id",id).put("project",project)
      .put("priority_tier",tier).put("spec_reference",spec)
      .put("instruction",instruction).put("conversation",conversation)
      .put("voice_locale",voiceLocale).put("max_cycles",maximum).put("index",1).put("ack_count",0)
      .put("last_error","").put("started_at_ms",System.currentTimeMillis());
    save();
    return status();
  }
  synchronized JSONObject pause()throws Exception {
    if(state.optBoolean("active",false)&&!"paused".equals(state.optString("state"))) {
      state.put("paused_previous_state",state.optString("state","ready"));
      state.put("state","paused");
      save();
    }
    return status();
  }
  synchronized JSONObject resume()throws Exception {
    if(!state.optBoolean("active",false))throw new IllegalStateException("No active cycle to resume");
    if(!"paused".equals(state.optString("state")) &&
       !"needs_review".equals(state.optString("state")))
      return status();
    String current=ledger.status().optString("state");
    String previous=state.optString("paused_previous_state","ready");
    if("dispatching".equals(current)||"requires_manual_review".equals(current))
      throw new IllegalStateException("Previous ChatGPT send is uncertain; review required");
    if("submitted_unverified".equals(current)){
      if(!"waiting_ack".equals(previous)&&!"queued".equals(previous))
        throw new IllegalStateException("A potentially sent checkpoint cannot be requeued");
      previous="waiting_ack";
    }
    if(!("ready".equals(previous)||"queued".equals(previous)||
         "waiting_ack".equals(previous)||"awaiting_new_chat".equals(previous)))
      throw new IllegalStateException("Cycle recovery requires an operator review");
    state.put("state",previous).put("last_error","");
    state.remove("paused_previous_state");
    save();return status();
  }
  synchronized JSONObject stop()throws Exception {
    JSONObject current=ledger.status();
    String checkpoint=state.optString("checkpoint","");
    if(checkpoint.equals(current.optString("last_checkpoint",""))&&
       "queued".equals(current.optString("state",""))){
      // A turn that was never sent can be cancelled safely.
      ledger.cancel();
    }
    state.put("active",false).put("state","stopped")
      .put("stopped_at_ms",System.currentTimeMillis());
    save();
    // Never cancel a turn already submitted to ChatGPT.
    return status();
  }
  synchronized JSONObject tick()throws Exception {
    if(!state.optBoolean("active",false)||"paused".equals(state.optString("state"))||
       "needs_review".equals(state.optString("state")))return status();
    if(!ledger.status().optBoolean("enabled",false))return status();
    String phase=state.optString("state","ready");
    int index=state.optInt("index",1);
    int maximum=state.optInt("max_cycles",0);
    if(maximum>0&&index>maximum) {
      state.put("active",false).put("state","finished");
      save();return status();
    }
    if("awaiting_voice_answer".equals(phase)) {
      VoiceDialogueService speaker=VoiceDialogueService.active;
      if(speaker==null) {
        state.put("state","needs_review")
          .put("last_error","Voice service stopped before the spoken answer arrived");
        save();return status();
      }
      JSONObject speech=speaker.report();
      String expectedVoice=state.optString("voice_id","");
      if(!expectedVoice.equals(speech.optString("question_id",""))) {
        state.put("state","needs_review")
          .put("last_error","Speech response did not match the current checkpoint");
        save();return status();
      }
      String speechPhase=speech.optString("phase","");
      if("answered".equals(speechPhase)) {
        String answer=speech.optString("transcript","").trim();
        if(answer.isEmpty()||answer.length()>1500) {
          state.put("state","needs_review")
            .put("last_error","Voice transcription is empty or too long");
          save();return status();
        }
        state.put("voice_answer",answer).put("state","voice_answer_recorded");
        save();
        return tick();
      }
      if("failed".equals(speechPhase)||"stopped".equals(speechPhase)||
         "unavailable".equals(speechPhase)) {
        state.put("state","needs_review")
          .put("last_error","Voice exchange failed; inspect speaker/microphone status");
        save();return status();
      }
      return status();
    }
    if("voice_answer_recorded".equals(phase)) {
      String checkpointId=state.optString("checkpoint","");
      JSONObject recorded=ledger.status();
      if(!checkpointId.equals(recorded.optString("last_checkpoint",""))) {
        state.put("state","needs_review")
          .put("last_error","Spoken answer checkpoint was replaced");
        save();return status();
      }
      String current=recorded.optString("state","");
      if("submitted_unverified".equals(current)) {
        ledger.acknowledge(checkpointId,
          "voice-answer-received-"+checkpointId+"-"+System.currentTimeMillis());
      }else if(!"acknowledged".equals(current)) {
        state.put("state","needs_review")
          .put("last_error","Spoken answer could not be attached to a confirmed ChatGPT submission");
        save();return status();
      }
      VoiceDialogueService speaker=VoiceDialogueService.active;
      if(speaker!=null) {
        try{speaker.acknowledge(state.optString("voice_id",""));}catch(Exception ignored){}
      }
      state.put("state","waiting_ack");
      save();
      return status();
    }
    if("voice_requesting".equals(phase)) {
      // A previous process may have already spoken the question.
      state.put("state","needs_review").put("last_error",
        "Speech request interrupted; no duplicate question will be issued");
      save();return status();
    }
    if("waiting_ack".equals(phase)||"queued".equals(phase)) {
      JSONObject checkpoint=ledger.status();
      String expected=state.optString("checkpoint","");
      String current=checkpoint.optString("state","");
      if(!expected.equals(checkpoint.optString("last_checkpoint",""))) {
        state.put("state","needs_review")
          .put("last_error","External checkpoint replaced the cycle checkpoint");
        save();return status();
      }
      if("acknowledged".equals(current)) {
        if(state.optBoolean("response_completed_work",false)) {
          state.put("ack_count",state.optInt("ack_count",0)+1)
            .put("state","finished").put("active",false)
            .put("last_acknowledged",expected).put("last_error","");
          save();return status();
        }
        state.put("ack_count",state.optInt("ack_count",0)+1)
          .put("index",index+1).put("state","ready")
          .put("last_acknowledged",expected)
          .put("response_completed_work",false)
          .put("marker_first_seen_ms",0L);
        save();
        return tick();
      }
      if("requires_manual_review".equals(current)||"cancelled".equals(current)||
         "failed".equals(current)) {
        state.put("state","needs_review")
          .put("last_error","Prior ChatGPT submission needs an operator review");
        save();return status();
      }
      if("queued".equals(current)&&"queued".equals(phase)) {
        // The actual phone keyboard is the only submission mechanism.
        // Recover foreground if Android SystemUI or another app interrupted it.
        ControlAccessibilityService access=ControlAccessibilityService.active;
        if(access!=null){
          String foreground=access.currentPackage();
          if("com.openai.chatgpt".equals(foreground)){
            try{ledger.dispatch();}catch(Exception e){
              state.put("last_error","Keyboard handoff deferred: "+e.getClass().getSimpleName());
              save();
            }
          }else{
            long now=System.currentTimeMillis();
            if(now-state.optLong("last_foreground_request_ms",0L)>14000L){
              JSONObject launch=access.requestChatForeground();
              state.put("last_foreground_request_ms",now)
                .put("last_foreground_request",launch.optString("reason","requested"));
              save();
            }
          }
        }
      }
      if("submitted_unverified".equals(current)&&"queued".equals(phase)) {
        state.put("state","waiting_ack");save();
      }
      if("submitted_unverified".equals(current)) {
        // A native Accessibility click does not mean the model replied.
        // Await a unique final response marker, then a stable quiet interval.
        ControlAccessibilityService view=ControlAccessibilityService.active;
        long now=System.currentTimeMillis();
        long sent=checkpoint.optLong("last_submit_ms",0);
        if(view!=null&&now-sent>=8000L) {
          JSONObject evidence=view.observeCycleResponse(expected);
          boolean visible=evidence.optBoolean("visible",false);
          boolean producing=evidence.optBoolean("generating",true);
          long began=state.optLong("marker_first_seen_ms",0L);
          if(visible&&!producing) {
            String spokenQuestion=evidence.optString("voice_question","").trim();
            if(began==0) {
              state.put("marker_first_seen_ms",now)
                .put("response_completed_work",evidence.optBoolean("finished",false))
                .put("observed_voice_question",spokenQuestion);
              save();
            }else if(now-began>=12000L) {
              if(!spokenQuestion.isEmpty() &&
                 spokenQuestion.equals(state.optString("observed_voice_question",""))) {
                VoiceDialogueService voice=VoiceDialogueService.active;
                if(voice==null){
                  state.put("state","needs_review").put("last_error",
                    "A spoken reply was requested but microphone service is not owner-enabled");
                  save();return status();
                }
                String speechId="voice-"+expected;
                state.put("voice_question",spokenQuestion)
                  .put("voice_id",speechId).put("state","voice_requesting")
                  .put("marker_first_seen_ms",0L);
                save();
                try{
                  voice.ask(spokenQuestion,state.optString("voice_locale","en-US"),speechId);
                  state.put("state","awaiting_voice_answer");
                }catch(Exception e){
                  state.put("state","needs_review").put("last_error",
                    "Spoken question unavailable: "+e.getClass().getSimpleName());
                }
                save();return status();
              }
              // A bounded on-screen assistant answer is not an Accessibility
              // click or proof of a new reply from any other checkpoint.
              String receipt="accessibility-reply-observed-"+expected+"-"+now;
              ledger.acknowledge(expected,receipt);
              state.put("response_completed_work",
                evidence.optBoolean("finished",false));
              state.put("marker_first_seen_ms",0L);
              save();
            }
          }else if(began>0) {
            state.put("marker_first_seen_ms",0L)
              .put("response_completed_work",false);
            save();
          }
        }
      }
      return status();
    }
    if("awaiting_new_chat".equals(phase)) {
      // Request navigation once only. The external operator must verify the
      // new conversation, because an Accessibility click is not proof.
      if(!state.optBoolean("new_chat_requested",false)){
        ControlAccessibilityService view=ControlAccessibilityService.active;
        if(view!=null&&"com.openai.chatgpt".equals(view.currentPackage())){
          JSONObject nav=view.requestNewChat();
          if(nav.optBoolean("requested",false)){
            state.put("new_chat_requested",true);
            save();
          }
        }
      }
      return status();
    }
    if(!"ready".equals(phase))return status();
    if("new".equals(state.optString("conversation")) &&
       state.optInt("new_chat_verified_index",0)!=index) {
      state.put("state","awaiting_new_chat").put("new_chat_requested",false)
        .put("last_error","Wait for external operator to verify New chat navigation");
      save();return status();
    }
    String checkpointId=state.getString("cycle_id")+"-"+index;
    String spokenInput=state.optString("voice_answer","").trim();
    String previousQuestion=state.optString("voice_question","").trim();
    String voiceContext=spokenInput.isEmpty()?"":(
      "\nThe owner answered your previous spoken question via Asterion Control."+
      "\nYour question: "+previousQuestion+
      "\nOwner's speech-to-text answer: "+spokenInput);
    String instructions=state.getString("instruction")+voiceContext+
      "\nCycle: "+index+". Continue from the same canonical specification and "+
      "the latest verified GitHub progress. Complete meaningful work before "+
      "replying. On the LAST visible line of your answer, join the exact "+
      "uppercase prefix ASTERION-CYCLE-ACK: immediately with the checkpoint "+
      "ID supplied above. If the defined work is fully complete and further "+
      "cycles are unnecessary, instead join ASTERION-CYCLE-DONE: with the same "+
      "checkpoint ID. Never print both. Do not print either marker earlier. "+
      "If you need the owner's input before continuing, instead join "+
      "ASTERION-VOICE-ASK: with the checkpoint ID, a vertical bar and your "+
      "single concise question (no more than 700 characters). Only do so "+
      "when the speaker/microphone session was enabled by the owner. "+
      "Asterion Control speaks your question first, then listens once for "+
      "the owner's spoken answer and carries the transcription to the next cycle. "+
      "The Control app verifies the actual visible response and stable "+
      "speech input before proceeding; do not duplicate or reset work.";
    JSONObject body=new JSONObject()
      .put("project",state.getString("project"))
      .put("checkpoint_id",checkpointId)
      .put("priority_tier",state.getString("priority_tier"))
      .put("spec_reference",state.getString("spec_reference"))
      .put("message",instructions);
    // Store the deterministic ID BEFORE queue: if killed, the next tick can
    // reconcile the ledger history rather than creating a second message.
    state.put("state","queueing").put("checkpoint",checkpointId);
    save();
    try {
      ledger.queue(body);
      state.put("state","queued");
      // Only clear an acknowledged voice answer after its next prompt was
      // durably queued. A failed queue operation preserves the user's answer.
      state.remove("voice_answer");state.remove("voice_question");
      state.remove("observed_voice_question");
      save();
    }catch(Exception e){
      state.put("state","needs_review").put("last_error",
        "Could not queue a unique cycle checkpoint: "+e.getClass().getSimpleName());
      save();
    }
    return status();
  }
  synchronized boolean allowAutomaticDispatch(String checkpoint){
    if(!state.optBoolean("active",false))return true;
    if(!checkpoint.equals(state.optString("checkpoint","")))return true;
    String phase=state.optString("state","");
    return "queued".equals(phase)||"waiting_ack".equals(phase);
  }
  synchronized JSONObject confirmNewChat(String verification)throws Exception {
    if(!state.optBoolean("active",false)||
       !"awaiting_new_chat".equals(state.optString("state")))
      throw new IllegalStateException("No pending New chat verification");
    if(verification==null||verification.length()<8||verification.length()>512)
      throw new IllegalArgumentException("Observed new-chat verification required");
    if(!state.optBoolean("new_chat_requested",false))
      throw new IllegalStateException("New chat control has not been requested yet");
    state.put("new_chat_verified_index",state.optInt("index",1))
      .put("new_chat_receipt",verification).put("state","ready")
      .put("last_error","");
    save();return status();
  }
  synchronized JSONObject recover()throws Exception {
    // A process restart must start a fresh observation interval, not take
    // an older timestamp as proof of a completed assistant response.
    if(state.optLong("marker_first_seen_ms",0L)>0) {
      state.put("marker_first_seen_ms",0L);
      save();
    }
    if("voice_requesting".equals(state.optString("state"))) {
      state.put("state","needs_review").put("last_error",
        "Voice request interrupted on app restart; do not repeat it");
      save();
    }
    if("queueing".equals(state.optString("state"))) {
      String checkpoint=state.optString("checkpoint");
      JSONObject other=ledger.status();
      if(checkpoint.equals(other.optString("last_checkpoint")) &&
         ("queued".equals(other.optString("state"))||
          "submitted_unverified".equals(other.optString("state")))) {
        state.put("state","queued");
      }else{
        state.put("state","needs_review")
          .put("last_error","Cycle stopped during checkpoint creation; no automatic replay");
      }
      save();
    }
    return status();
  }
}
