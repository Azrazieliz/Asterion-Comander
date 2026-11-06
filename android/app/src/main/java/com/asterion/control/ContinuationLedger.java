package com.asterion.control;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Phone-owned, opt-in continuation checkpoint ledger.
 * No model/API calls, chat credentials, or self-learning code lives in Control.
 * Never report a sent UI action as an accepted/answered ChatGPT turn.
 */
final class ContinuationLedger {
  private static final String FILE = "continuation-state.json";
  private static final int MAX_PROMPT = 3800;
  // Every new automated turn requires an actual observed response receipt.
  private static final long COOLDOWN_MS = 3500L;
  private static volatile ContinuationLedger singleton;
  static synchronized ContinuationLedger get(Context context) {
    if (singleton == null) singleton = new ContinuationLedger(context.getApplicationContext());
    return singleton;
  }
  private final AtomicFile store;
  private JSONObject state;
  private ContinuationLedger(Context context) {
    store = new AtomicFile(new File(context.getNoBackupFilesDir(), FILE));
    state = read();
  }
  private JSONObject fresh() {
    JSONObject j = new JSONObject();
    try {
      j.put("enabled", false).put("state", "idle").put("sequence", 0)
       .put("last_submit_ms", 0).put("last_error", "");
    } catch (Exception ignored) {}
    return j;
  }
  private JSONObject read() {
    try (FileInputStream in = store.openRead()) {
      return new JSONObject(new String(in.readAllBytes(), StandardCharsets.UTF_8));
    } catch (Exception ignored) { return fresh(); }
  }
  private void persist() throws Exception {
    FileOutputStream out = store.startWrite();
    try {
      out.write(state.toString().getBytes(StandardCharsets.UTF_8));
      out.flush();
      store.finishWrite(out);
    } catch (Exception e) { store.failWrite(out); throw e; }
  }
  synchronized JSONObject status() throws Exception {
    // Do not leak a queued prompt to an unauthenticated UI screen.
    return new JSONObject(state.toString());
  }
  synchronized JSONObject configure(boolean enabled) throws Exception {
    String current=state.optString("state","idle");
    if(!enabled && !"paused".equals(current)){
      state.put("paused_previous_state",current).put("state","paused");
    }else if(enabled && "paused".equals(current)){
      state.put("state",state.optString("paused_previous_state","idle"));
      state.remove("paused_previous_state");
    }
    state.put("enabled",enabled);
    persist();
    return status();
  }
  synchronized JSONObject queue(JSONObject body) throws Exception {
    if (!state.optBoolean("enabled")) throw new IllegalStateException("Owner has not enabled ChatGPT continuation on this Android phone");
    String project = body.optString("project", "").trim();
    String checkpoint = body.optString("checkpoint_id", "").trim();
    String tier = body.optString("priority_tier", "").trim();
    String text = body.optString("message", "").trim();
    String spec = body.optString("spec_reference", "").trim();
    if (!project.matches("[A-Za-z0-9_.-]{3,70}") || !checkpoint.matches("[A-Za-z0-9_.-]{3,100}"))
      throw new IllegalArgumentException("Invalid project or checkpoint identifier");
    if (!(tier.equals("5*") || tier.equals("6*") || tier.equals("7*")))
      throw new IllegalArgumentException("Priority tier must be 5*, 6* or 7*");
    if (spec.length() < 3 || spec.length() > 250 || text.isEmpty() || text.length() > MAX_PROMPT)
      throw new IllegalArgumentException("Invalid spec reference or continuation message");
    JSONArray history=state.optJSONArray("history");
    if(history!=null)for(int i=0;i<history.length();i++)
      if(checkpoint.equals(history.optString(i)))
        return new JSONObject().put("ok",true).put("duplicate",true)
          .put("state",state.optString("state"));
    String before=state.optString("state","idle");
    if(!("idle".equals(before)||"acknowledged".equals(before)||
         "cancelled".equals(before)||"failed".equals(before)))
      throw new IllegalStateException("Prior checkpoint has not been acknowledged or cancelled");
    // Deterministic cross-chat recovery envelope, not a second AI agent.
    // All identifiers come from the actual authoring operator and are stored
    // with the message, so context does not depend on this conversation memory.
    String envelope="ASTERION CONTROL — CONTINUATION CHECKPOINT\n"
        +"Project: "+project+"\nCheckpoint ID: "+checkpoint
        +"\nSpecification level: "+tier+"\nCanonical reference: "+spec
        +"\nResume instructions: Inspect the canonical files and latest source/progress in GitHub."
        +" Distinguish committed, built, installed and device-verified.\n"
        +"Next work: "+text;
    JSONObject item = new JSONObject().put("project", project).put("checkpoint_id", checkpoint)
      .put("priority_tier", tier).put("spec_reference", spec).put("message", envelope)
      .put("queued_at_ms", System.currentTimeMillis());
    if(history==null)history=new JSONArray();
    JSONArray kept=new JSONArray();
    for(int i=Math.max(0,history.length()-62);i<history.length();i++)
      kept.put(history.optString(i));
    kept.put(checkpoint);
    state.put("history",kept);
    state.put("pending", item).put("state", "queued").put("last_checkpoint", checkpoint)
      .put("sequence", state.optInt("sequence", 0) + 1).put("last_error", "")
      .put("attempt_count",0).put("last_attempt_ms",0);
    persist();
    return new JSONObject().put("ok", true).put("state", "queued").put("checkpoint_id", checkpoint);
  }
  synchronized JSONObject dispatch() throws Exception {
    if (!state.optBoolean("enabled")) throw new IllegalStateException("Continuation disabled on phone");
    if (!"queued".equals(state.optString("state")) || !state.has("pending"))
      throw new IllegalStateException("No queued checkpoint");
    if (System.currentTimeMillis() - state.optLong("last_submit_ms", 0) < COOLDOWN_MS)
      throw new IllegalStateException("Continuation cooldown is active");
    if(System.currentTimeMillis() - state.optLong("last_attempt_ms",0) < 3500L)
      throw new IllegalStateException("Retry cooldown active");
    int attempts=state.optInt("attempt_count",0);
    if(attempts>=4){
      state.put("state","requires_manual_review")
        .put("last_error","Four ChatGPT UI submission attempts did not succeed");
      persist();
      throw new IllegalStateException("Too many attempts; owner inspection required");
    }
    ControlAccessibilityService service = ControlAccessibilityService.active;
    if (service == null) throw new IllegalStateException("Android accessibility unavailable");
    String message = state.getJSONObject("pending").getString("message");
    // Save dispatching BEFORE touching another app: a crash cannot cause replay.
    state.put("state", "dispatching")
         .put("attempt_count", attempts+1)
         .put("last_attempt_ms",System.currentTimeMillis());
    persist();
    JSONObject outcome = service.sendChatMessage(message);
    if (outcome.optBoolean("sent")) {
      state.put("state", "submitted_unverified")
        .put("last_submit_ms", System.currentTimeMillis()).put("last_error", "");
      state.remove("pending");
    } else if(outcome.optBoolean("uncertain")) {
      state.put("state","requires_manual_review")
        .put("last_error",outcome.optString("reason","Uncertain ChatGPT send"));
    } else {
      String reason=outcome.optString("reason","UI send was not confirmed");
      // Transient composer/UI delays can be retried by a new ChatGPT window
      // event. A conflicting user draft is never overwritten or retried.
      boolean conflict=reason.contains("user text")||reason.contains("refusing to overwrite");
      state.put("state", conflict?"requires_manual_review":"queued")
        .put("last_error",reason);
    }
    persist();
    return new JSONObject().put("ok", outcome.optBoolean("sent"))
      .put("state", state.optString("state")).put("reason", outcome.optString("reason"));
  }
  /**
   * Only the external operator observing a real ChatGPT reply can acknowledge
   * the transport. The phone cannot infer model processing from UI clicks.
   */
  synchronized JSONObject acknowledge(String checkpoint,String receipt) throws Exception {
    String current=state.optString("state");
    if(!("submitted_unverified".equals(current)||
         ("paused".equals(current)&&"submitted_unverified".equals(state.optString("paused_previous_state")))) ||
       !checkpoint.equals(state.optString("last_checkpoint")))
      throw new IllegalStateException("No matching unacknowledged checkpoint");
    if(receipt==null||receipt.length()<8||receipt.length()>512)
      throw new IllegalArgumentException("Response evidence marker required (8-512 characters)");
    state.put("state",state.optBoolean("enabled")?"acknowledged":"paused")
         .put("paused_previous_state",state.optBoolean("enabled")?"":"acknowledged")
         .put("response_observed_ms",System.currentTimeMillis())
         .put("response_receipt",receipt);
    persist();
    return new JSONObject().put("ok",true).put("state","acknowledged")
      .put("checkpoint_id",checkpoint);
  }
  synchronized JSONObject cancel() throws Exception {
    String current=state.optString("state");
    if("dispatching".equals(current) || "submitted_unverified".equals(current))
      throw new IllegalStateException("A send may already have happened; inspect before cancelling");
    if("queued".equals(current)||"failed".equals(current)||"requires_manual_review".equals(current)||
       ("paused".equals(current)&&"queued".equals(state.optString("paused_previous_state")))){
      state.remove("pending");
      state.put("state",state.optBoolean("enabled")?"cancelled":"paused");
      if(!state.optBoolean("enabled"))state.put("paused_previous_state","cancelled");
      persist();
    }
    return new JSONObject().put("ok",true).put("state",state.optString("state"));
  }
  synchronized JSONObject recover() throws Exception {
    // A previous dispatch might have sent the message before a crash; NEVER replay it.
    if ("dispatching".equals(state.optString("state"))) {
      state.put("state", "requires_manual_review");
      persist();
    }
    return status();
  }
}
