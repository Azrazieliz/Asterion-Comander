package com.asterion.control;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

public final class ControlAccessibilityService extends AccessibilityService {
  public static volatile ControlAccessibilityService active;
  private final Handler main = new Handler(Looper.getMainLooper());
  @Override protected void onServiceConnected() { super.onServiceConnected(); active = this; }
  private final java.util.concurrent.ExecutorService handoff =
      java.util.concurrent.Executors.newSingleThreadExecutor();
  private final java.util.concurrent.atomic.AtomicBoolean resumeScheduled =
      new java.util.concurrent.atomic.AtomicBoolean(false);
  private long lastResumeProbe = 0L;
  @Override public void onAccessibilityEvent(AccessibilityEvent e) {
    AppObservation.event(getApplicationContext(),e);
    // A queued, owner-enabled checkpoint can resume when ChatGPT becomes visible.
    // Never inject text into a different application or into an occupied composer.
    if (e == null || !"com.openai.chatgpt".contentEquals(e.getPackageName() == null
        ? "" : e.getPackageName())) return;
    long now = android.os.SystemClock.elapsedRealtime();
    if (now - lastResumeProbe < 4000L || !resumeScheduled.compareAndSet(false, true)) return;
    lastResumeProbe = now;
    handoff.execute(() -> {
      try {
        ContinuationLedger ledger = ContinuationLedger.get(getApplicationContext());
        if ("queued".equals(ledger.recover().optString("state"))
            && ledger.status().optBoolean("enabled")
            && ContinuationCycle.get(getApplicationContext()).allowAutomaticDispatch(
                ledger.status().optString("last_checkpoint",""))) {
          // Delay: allow ChatGPT's chat composer and navigation to settle.
          Thread.sleep(1600);
          ledger.dispatch();
        }
      } catch (Exception ignored) {
        // Status remains queued or failed for explicit inspection. No retry loop.
      } finally { resumeScheduled.set(false); }
    });
  }
  private AccessibilityNodeInfo findEditable(AccessibilityNodeInfo node, int depth) {
    if (node == null || depth > 24) return null;
    if (node.isEditable() && node.isVisibleToUser() && node.isEnabled()) return node;
    for (int i = 0; i < node.getChildCount(); i++) {
      AccessibilityNodeInfo found = findEditable(node.getChild(i), depth + 1);
      if (found != null) return found;
    }
    return null;
  }
  private AccessibilityNodeInfo findSend(AccessibilityNodeInfo node, int depth) {
    if (node == null || depth > 24) return null;
    CharSequence description = node.getContentDescription(), text = node.getText();
    String name = description != null ? description.toString().trim().toLowerCase(java.util.Locale.ROOT)
        : text == null ? "" : text.toString().trim().toLowerCase(java.util.Locale.ROOT);
    boolean send = name.equals("send") || name.equals("send message")
        || name.equals("send prompt") || name.equals("send a message")
        || name.equals("envoyer") || name.equals("envoyer le message");
    if (send && node.isClickable() && node.isEnabled() && node.isVisibleToUser()) return node;
    for (int i = 0; i < node.getChildCount(); i++) {
      AccessibilityNodeInfo result = findSend(node.getChild(i), depth + 1);
      if (result != null) return result;
    }
    return null;
  }
  /**
   * UI-only ChatGPT handoff. This is not a model call; it consumes normal app usage.
   * A successful Accessibility click is NOT proof that ChatGPT accepted the message.
   */
  private AccessibilityNodeInfo findComposer(AccessibilityNodeInfo root) {
    AccessibilityNodeInfo field=findEditable(root,0);
    if(field==null)return null;
    // Avoid typing into a ChatGPT search field or unrelated top-bar input.
    Rect bounds=new Rect(), screen=new Rect();
    field.getBoundsInScreen(bounds);
    root.getBoundsInScreen(screen);
    if(bounds.isEmpty() || screen.isEmpty() || bounds.centerY()<screen.top+screen.height()/2)
      return null;
    return field;
  }
  /** Safe navigation only. A clicked "New chat" control is NOT proof that
   * the new conversation loaded; the external operator must inspect UI first.
   */
  JSONObject requestNewChat(){
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] result={chatOutcome(false,false,"ChatGPT not ready")};
    main.post(()->{
      try{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null||root.getPackageName()==null||
            !"com.openai.chatgpt".contentEquals(root.getPackageName())){
          result[0]=chatOutcome(false,false,"ChatGPT must be visible on the phone");
          return;
        }
        AccessibilityNodeInfo editor=findComposer(root);
        if(editor!=null&&editor.getText()!=null&&editor.getText().length()>0){
          result[0]=chatOutcome(false,false,"Existing draft preserved; cannot navigate away");
          return;
        }
        AccessibilityNodeInfo button=findNewChat(root,0);
        if(button==null){
          result[0]=chatOutcome(false,false,
             "Accessible New chat control not visible; inspect ChatGPT UI");
          return;
        }
        boolean clicked=button.performAction(AccessibilityNodeInfo.ACTION_CLICK);
        JSONObject response=new JSONObject();
        response.put("requested",clicked).put("verified_new_chat",false)
          .put("reason",clicked?"New chat navigation clicked; inspect UI before sending":
            "Android did not accept New chat click");
        result[0]=response;
      }catch(Exception e){
        result[0]=chatOutcome(false,true,
          "Uncertain ChatGPT navigation: "+e.getClass().getSimpleName());
      }finally{done.countDown();}
    });
    try{
      if(!done.await(6,TimeUnit.SECONDS))
        return chatOutcome(false,true,"New chat navigation timed out");
    }catch(InterruptedException e){
      Thread.currentThread().interrupt();
      return chatOutcome(false,true,"New chat navigation interrupted");
    }
    return result[0];
  }
  private AccessibilityNodeInfo findNewChat(AccessibilityNodeInfo node,int depth){
    if(node==null||depth>24)return null;
    CharSequence desc=node.getContentDescription(),txt=node.getText();
    String value=(desc==null?txt:desc)==null?""
      :(desc==null?txt:desc).toString().trim().toLowerCase(java.util.Locale.ROOT);
    boolean match=value.equals("new chat")||value.equals("new conversation")
      ||value.equals("start new chat")||value.equals("start a new chat")
      ||value.equals("nouvelle conversation")||value.equals("nouvelle discussion");
    if(match&&node.isVisibleToUser()){
      AccessibilityNodeInfo parent=node;
      for(int i=0;i<4&&parent!=null;i++){
        if(parent.isEnabled()&&parent.isClickable()&&parent.isVisibleToUser())
          return parent;
        parent=parent.getParent();
      }
    }
    for(int i=0;i<node.getChildCount();i++){
      AccessibilityNodeInfo found=findNewChat(node.getChild(i),depth+1);
      if(found!=null)return found;
    }
    return null;
  }
  private JSONObject chatOutcome(boolean sent,boolean uncertain,String reason){
    JSONObject result=new JSONObject();
    try {
      result.put("sent",sent).put("uncertain",uncertain).put("reason",reason);
    }catch(Exception ignored){}
    return result;
  }
  JSONObject sendChatMessage(String message) {
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] output={chatOutcome(false,true,"UI dispatch did not finish")};
    main.post(()->{
      try {
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null || root.getPackageName()==null ||
           !"com.openai.chatgpt".contentEquals(root.getPackageName())){
          output[0]=chatOutcome(false,false,"ChatGPT Android app is not foreground");
          done.countDown();return;
        }
        AccessibilityNodeInfo editor=findComposer(root);
        if(editor==null){
          output[0]=chatOutcome(false,false,"No lower-screen ChatGPT composer found");
          done.countDown();return;
        }
        String existing=editor.getText()==null?"":editor.getText().toString();
        if(!existing.isEmpty() && !existing.equals(message)){
          output[0]=chatOutcome(false,false,"ChatGPT composer has user text; refusing to overwrite");
          done.countDown();return;
        }
        if(!existing.equals(message)){
          Bundle input=new Bundle();
          input.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,message);
          if(!editor.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,input)){
            output[0]=chatOutcome(false,false,"ChatGPT composer rejected text");
            done.countDown();return;
          }
        }
        // Compose send controls may only appear after the next recomposition.
        // Verify the exact queued text before clicking anything.
        main.postDelayed(()->{
          try{
            AccessibilityNodeInfo after=getRootInActiveWindow();
            if(after==null||after.getPackageName()==null||
              !"com.openai.chatgpt".contentEquals(after.getPackageName())){
              output[0]=chatOutcome(false,false,"ChatGPT is no longer foreground");
              return;
            }
            AccessibilityNodeInfo verify=findComposer(after);
            String actual=verify==null||verify.getText()==null
              ?"":verify.getText().toString();
            if(!message.equals(actual)){
              output[0]=chatOutcome(false,true,
                "ChatGPT composer changed during submission; inspect before retry");
              return;
            }
            AccessibilityNodeInfo send=findSend(after,0);
            if(send==null){
              output[0]=chatOutcome(false,false,
                "No accessible Send control; queued text remains prepared");
              return;
            }
            if(!send.performAction(AccessibilityNodeInfo.ACTION_CLICK)){
              output[0]=chatOutcome(false,true,
                "Send click not accepted; queued text may remain");
              return;
            }
            output[0]=chatOutcome(true,false,
              "Send control clicked; model response remains unverified");
          }catch(Exception e){
            output[0]=chatOutcome(false,true,
              "Uncertain ChatGPT composer outcome: "+e.getClass().getSimpleName());
          }finally{done.countDown();}
        },400L);
      }catch(Exception e){
        output[0]=chatOutcome(false,false,
          "ChatGPT UI preparation failed: "+e.getClass().getSimpleName());
        done.countDown();
      }
    });
    boolean finished=false;
    try{finished=done.await(11,TimeUnit.SECONDS);}
    catch(InterruptedException e){Thread.currentThread().interrupt();}
    if(!finished)return chatOutcome(false,true,
      "ChatGPT UI dispatch timed out; inspect before requeue");
    return output[0];
  }
  @Override public void onInterrupt() { }
  @Override public void onDestroy() { if(active == this) active = null; handoff.shutdownNow(); super.onDestroy(); }
  public boolean action(JSONObject a) {
    final String cmd = a.optString("action", "");
    final CountDownLatch done = new CountDownLatch(1);
    final boolean[] result = { false };
    main.post(() -> { try {
      switch(cmd) {
        case "back": result[0] = performGlobalAction(GLOBAL_ACTION_BACK); done.countDown(); return;
        case "home": result[0] = performGlobalAction(GLOBAL_ACTION_HOME); done.countDown(); return;
        case "recents": result[0] = performGlobalAction(GLOBAL_ACTION_RECENTS); done.countDown(); return;
        case "notifications": result[0] = performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS); done.countDown(); return;
        case "type": {
          AccessibilityNodeInfo root = getRootInActiveWindow();
          AccessibilityNodeInfo target = root == null ? null : root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
          if (target != null && target.isEditable()) {
            Bundle b = new Bundle(); b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, a.optString("text"));
            result[0] = target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,b);
          }
          done.countDown(); return;
        }
        case "tap": case "swipe": case "long_press": {
          float x = (float)a.optDouble("x",0), y = (float)a.optDouble("y",0);
          Path p = new Path(); p.moveTo(x,y);
          long duration = 55;
          if(cmd.equals("swipe")) { p.lineTo((float)a.optDouble("x2",x),(float)a.optDouble("y2",y)); duration = Math.max(100,Math.min(5000,a.optLong("duration_ms",400))); }
          if(cmd.equals("long_press")) duration = Math.max(550,Math.min(2500,a.optLong("duration_ms",900)));
          GestureDescription gd = new GestureDescription.Builder().addStroke(new GestureDescription.StrokeDescription(p,0,duration)).build();
          dispatchGesture(gd,new GestureResultCallback() {
            @Override public void onCompleted(GestureDescription g){result[0]=true;done.countDown();}
            @Override public void onCancelled(GestureDescription g){done.countDown();}
          },main);
          return;
        }
        case "click_text": {
          AccessibilityNodeInfo root=getRootInActiveWindow(); String text=a.optString("text");
          if(root != null && !text.isEmpty()) {
            for(AccessibilityNodeInfo n : root.findAccessibilityNodeInfosByText(text)) {
              AccessibilityNodeInfo clickable=n;
              while(clickable!=null && !clickable.isClickable()) clickable=clickable.getParent();
              if(clickable!=null && clickable.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {result[0]=true;break;}
            }
          }
          done.countDown();return;
        }
        default: done.countDown();
      }
    } catch(Exception e) { done.countDown(); } });
    try { done.await(7,TimeUnit.SECONDS); } catch(InterruptedException e) {Thread.currentThread().interrupt();}
    return result[0];
  }
  /** Current visible package, sampled on Accessibility's main thread.
   * Used only to prevent screen evidence from crossing application boundaries.
   */
  String currentPackage(){
    final String[] name={""};
    final CountDownLatch completed=new CountDownLatch(1);
    main.post(()->{
      try{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root!=null&&root.getPackageName()!=null)name[0]=root.getPackageName().toString();
      }catch(Exception ignored){}finally{completed.countDown();}
    });
    try{completed.await(2,TimeUnit.SECONDS);}
    catch(InterruptedException e){Thread.currentThread().interrupt();}
    return name[0];
  }
  public JSONObject dump() {
    final CountDownLatch done = new CountDownLatch(1);
    final JSONObject result = new JSONObject();
    main.post(() -> { try {
      AccessibilityNodeInfo root=getRootInActiveWindow();
      result.put("available",root!=null);if(root!=null)result.put("root",node(root,0,new int[]{0}));
    }catch(Exception ignore){} finally {done.countDown();} });
    try{done.await(4,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
    return result;
  }
  private JSONObject node(AccessibilityNodeInfo n,int depth,int[] count) throws Exception {
    JSONObject o=new JSONObject(); count[0]++;
    o.put("class",String.valueOf(n.getClassName()));o.put("text",String.valueOf(n.getText()==null?"":n.getText()));
    o.put("description",String.valueOf(n.getContentDescription()==null?"":n.getContentDescription()));
    o.put("id",n.getViewIdResourceName());o.put("clickable",n.isClickable());
    Rect b=new Rect();n.getBoundsInScreen(b);o.put("bounds",new JSONArray().put(b.left).put(b.top).put(b.right).put(b.bottom));
    if(depth<12&&count[0]<250){JSONArray children=new JSONArray();for(int i=0;i<n.getChildCount()&&count[0]<250;i++){AccessibilityNodeInfo child=n.getChild(i);if(child!=null)children.put(node(child,depth+1,count));}o.put("children",children);}
    return o;
  }
}
