package com.asterion.control;

import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONObject;
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
  private static final long COOLDOWN_MS = 60_000L;
  private final AtomicFile store;
  private JSONObject state;
  ContinuationLedger(Context context) {
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
    state.put("enabled", enabled);
    if (!enabled) {
      state.put("state", "paused");
    } else if ("paused".equals(state.optString("state"))) {
      state.put("state", state.has("pending") ? "queued" : "idle");
    }
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
    if (checkpoint.equals(state.optString("last_checkpoint")))
      return new JSONObject().put("ok", true).put("duplicate", true).put("state", state.optString("state"));
    if (state.has("pending") && !"idle".equals(state.optString("state")) &&
        !"submitted_unverified".equals(state.optString("state")) &&
        !"failed".equals(state.optString("state")))
      throw new IllegalStateException("A previous checkpoint is still pending");
    JSONObject item = new JSONObject().put("project", project).put("checkpoint_id", checkpoint)
      .put("priority_tier", tier).put("spec_reference", spec).put("message", text)
      .put("queued_at_ms", System.currentTimeMillis());
    state.put("pending", item).put("state", "queued").put("last_checkpoint", checkpoint)
      .put("sequence", state.optInt("sequence", 0) + 1).put("last_error", "");
    persist();
    return new JSONObject().put("ok", true).put("state", "queued").put("checkpoint_id", checkpoint);
  }
  synchronized JSONObject dispatch() throws Exception {
    if (!state.optBoolean("enabled")) throw new IllegalStateException("Continuation disabled on phone");
    if (!"queued".equals(state.optString("state")) || !state.has("pending"))
      throw new IllegalStateException("No queued checkpoint");
    if (System.currentTimeMillis() - state.optLong("last_submit_ms", 0) < COOLDOWN_MS)
      throw new IllegalStateException("Continuation cooldown is active");
    ControlAccessibilityService service = ControlAccessibilityService.active;
    if (service == null) throw new IllegalStateException("Android accessibility unavailable");
    String message = state.getJSONObject("pending").getString("message");
    // Save dispatching BEFORE touching another app: a crash cannot cause replay.
    state.put("state", "dispatching"); persist();
    JSONObject outcome = service.sendChatMessage(message);
    if (outcome.optBoolean("sent")) {
      state.put("state", "submitted_unverified")
        .put("last_submit_ms", System.currentTimeMillis()).put("last_error", "");
      state.remove("pending");
    } else {
      state.put("state", "failed")
        .put("last_error", outcome.optString("reason", "UI send was not confirmed"));
    }
    persist();
    return new JSONObject().put("ok", outcome.optBoolean("sent"))
      .put("state", state.optString("state")).put("reason", outcome.optString("reason"));
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
