package com.asterion.control;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.accessibilityservice.InputMethod;
import android.os.Build;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.SurroundingText;
import android.view.KeyEvent;
import android.util.DisplayMetrics;
import android.view.accessibility.AccessibilityWindowInfo;
import java.util.List;
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
  @Override public InputMethod onCreateInputMethod(){return new InputMethod(this);}
  /** Android 13+ native input connection is available even when ChatGPT's
   * Compose view does not export a text-editable AccessibilityNodeInfo. */
  private InputMethod.AccessibilityInputConnection chatKeyboard(){
    if(Build.VERSION.SDK_INT<33)return null;
    AccessibilityNodeInfo root=getRootInActiveWindow();
    if(root==null||root.getPackageName()==null||
        !"com.openai.chatgpt".contentEquals(root.getPackageName()))return null;
    InputMethod ime=getInputMethod();
    if(ime==null||!ime.getCurrentInputStarted())return null;
    EditorInfo editor=ime.getCurrentInputEditorInfo();
    if(editor==null||!"com.openai.chatgpt".equals(editor.packageName))return null;
    if((editor.inputType & 0x0000000f)==0x00000001 &&
        (editor.inputType & 0x000000f0)==0x00000080)return null; // password
    return ime.getCurrentInputConnection();
  }
  private String inputText(InputMethod.AccessibilityInputConnection input){
    if(input==null)return null;
    SurroundingText text=input.getSurroundingText(4096,4096,0);
    return text==null||text.getText()==null?null:text.getText().toString();
  }
  /** Visible ChatGPT composer action: tap its blue send arrow, just above
   * the software keyboard. Uses REAL Accessibility gestures, not an invented
   * keyboard Send key. The owner's draft is never silently replaced. */
  private boolean tapVisibleBlueArrow(GestureResultCallback callback){
    AccessibilityNodeInfo root=getRootInActiveWindow();
    if(root==null||root.getPackageName()==null||
        !"com.openai.chatgpt".contentEquals(root.getPackageName()))return false;
    InputMethod ime=getInputMethod();
    if(ime==null||!ime.getCurrentInputStarted()||chatKeyboard()==null)return false;
    DisplayMetrics metrics=getResources().getDisplayMetrics();
    float density=metrics.density;
    Rect keyboard=new Rect();
    boolean found=false;
    List<AccessibilityWindowInfo> windows=getWindows();
    if(windows!=null)for(AccessibilityWindowInfo w:windows){
      if(w==null||w.getType()!=AccessibilityWindowInfo.TYPE_INPUT_METHOD)continue;
      w.getBoundsInScreen(keyboard);
      if(keyboard.top>metrics.heightPixels/3 &&
          keyboard.bottom>=metrics.heightPixels-120*density){found=true;break;}
    }
    if(!found)return false; // No visible keyboard: never tap guessed buttons.
    float x=metrics.widthPixels-39*density;
    float y=keyboard.top-35*density;
    if(y<metrics.heightPixels*0.38f || y>=keyboard.top ||
        x<metrics.widthPixels*0.78f || x>=metrics.widthPixels)return false;
    Path path=new Path();path.moveTo(x,y);
    GestureDescription gesture=new GestureDescription.Builder()
      .addStroke(new GestureDescription.StrokeDescription(path,0,65L)).build();
    return dispatchGesture(gesture,callback,main);
  }
  private void verifyChatSend(String message,JSONObject[] output,CountDownLatch done){
    main.postDelayed(()->{
      try{
        InputMethod.AccessibilityInputConnection input=chatKeyboard();
        String remaining=inputText(input);
        if(message.equals(remaining))
          output[0]=chatOutcome(false,false,
            "ChatGPT text still in composer; Send did not complete");
        else if(remaining==null)
          output[0]=chatOutcome(false,true,
            "ChatGPT keyboard changed; inspect UI before any retry");
        else output[0]=chatOutcome(true,false,
          "Blue Send action cleared draft; await visible ChatGPT reply");
      }catch(Exception e){output[0]=chatOutcome(false,true,
        "ChatGPT send result uncertain: "+e.getClass().getSimpleName());
      }finally{done.countDown();}
    },850L);
  }
  private void sendBlueArrowOrAccessibleButton(String message,
      JSONObject[] output,CountDownLatch done){
    // Owner-required path: actual native Android keyboard -> visible blue Send tap.
    // Do not substitute Accessibility ACTION_CLICK or an IME "send" key.
    boolean requested=tapVisibleBlueArrow(new GestureResultCallback(){
      @Override public void onCompleted(GestureDescription gesture){
        verifyChatSend(message,output,done);
      }
      @Override public void onCancelled(GestureDescription gesture){
        output[0]=chatOutcome(false,true,"Visible blue Send tap cancelled; inspect draft");
        done.countDown();
      }
    });
    if(!requested){output[0]=chatOutcome(false,false,
      "Visible ChatGPT keyboard and blue Send arrow not confirmed; draft preserved");
      done.countDown();}
  }
  private void keyboardChatSend(String message,JSONObject[] output,CountDownLatch done){
    try{
      InputMethod.AccessibilityInputConnection keyboard=chatKeyboard();
      if(keyboard==null){output[0]=chatOutcome(false,false,
        "ChatGPT keyboard not focused; tap message field first");done.countDown();return;}
      String before=inputText(keyboard);
      if(before==null){output[0]=chatOutcome(false,false,
        "ChatGPT keyboard text unavailable; refuse blind injection");done.countDown();return;}
      if(!before.isEmpty()&&!message.equals(before)){
        output[0]=chatOutcome(false,false,
          "Existing user draft preserved; refusing to overwrite");done.countDown();return;}
      if(before.isEmpty())keyboard.commitText(message,1,null);
      // commitText is void; verify the resulting editor contents before tapping.
      main.postDelayed(()->{
        try{
          InputMethod.AccessibilityInputConnection next=chatKeyboard();
          if(next==null||!message.equals(inputText(next))){
            output[0]=chatOutcome(false,true,
              "ChatGPT composer text not verified; no Send tap");done.countDown();return;}
          sendBlueArrowOrAccessibleButton(message,output,done);
        }catch(Exception e){output[0]=chatOutcome(false,true,
          "Keyboard action uncertain: "+e.getClass().getSimpleName());done.countDown();}
      },260L);
    }catch(Exception e){output[0]=chatOutcome(false,false,
      "ChatGPT keyboard unavailable: "+e.getClass().getSimpleName());done.countDown();}
  }
  @Override public void onAccessibilityEvent(AccessibilityEvent e) {
    AppObservation.event(getApplicationContext(),e);
    // Direct voice request: the actual ChatGPT writing bar must be visible.
    // Do not invent a follow-up or dispatch any old checkpoint automatically.
    if(e==null||!"com.openai.chatgpt".contentEquals(
        e.getPackageName()==null?"":e.getPackageName()))return;
    VoiceDialogueService voice=VoiceDialogueService.active;
    if(voice!=null)voice.onChatWindowVisible();
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
  /**
   * Safe, read-only proof that the New chat navigation actually finished.
   * A successful tap, empty old-chat composer or unchanged foreground package
   * is never sufficient to send the next autonomous-cycle checkpoint.
   */
  JSONObject verifyNewChatLanding(String previousCheckpoint) {
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] result={new JSONObject()};
    main.post(()->{
      try{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null||root.getPackageName()==null||
           !"com.openai.chatgpt".contentEquals(root.getPackageName())){
          result[0]=new JSONObject().put("verified",false)
            .put("reason","ChatGPT new chat not foreground");
          return;
        }
        AccessibilityNodeInfo composer=findComposer(root);
        if(composer!=null&&composer.getText()!=null&&composer.getText().length()>0){
          result[0]=new JSONObject().put("verified",false)
            .put("reason","Existing draft visible; new-chat rollover paused");
          return;
        }
        InputMethod.AccessibilityInputConnection input=chatKeyboard();
        String text=inputText(input);
        if(text!=null&&!text.isEmpty()){
          result[0]=new JSONObject().put("verified",false)
            .put("reason","Keyboard contains unsent text; preserve owner draft");
          return;
        }
        int[] evidence=new int[]{0,0}; // welcome heading, previous checkpoint marker
        inspectNewChatLanding(root,previousCheckpoint,evidence,0,new int[]{0});
        boolean clean=evidence[0]>0&&evidence[1]==0;
        result[0]=new JSONObject().put("verified",clean)
          .put("reason",clean?"New Chat welcome and empty composer verified":
            "New-chat landing not provable from visible native UI; no blind send");
      }catch(Exception e){
        try{result[0]=new JSONObject().put("verified",false)
          .put("reason","ChatGPT new-chat check failed: "+e.getClass().getSimpleName());}
        catch(Exception ignored){}
      }finally{done.countDown();}
    });
    try{if(!done.await(3,TimeUnit.SECONDS)){
      JSONObject timedOut=new JSONObject();
      try{timedOut.put("verified",false).put("reason","New-chat verification timed out");}
      catch(Exception ignored){}
      return timedOut;
    }}
    catch(InterruptedException e){Thread.currentThread().interrupt();return new JSONObject();}
    return result[0];
  }

  private void inspectNewChatLanding(AccessibilityNodeInfo node,String previousCheckpoint,
       int[] evidence,int depth,int[] count){
    if(node==null||depth>26||count[0]++>450||!node.isVisibleToUser())return;
    CharSequence text=node.getText(),desc=node.getContentDescription();
    if(!node.isEditable())for(CharSequence value:new CharSequence[]{text,desc}){
      if(value==null||value.length()>600)continue;
      String item=value.toString().trim();
      if(!previousCheckpoint.isEmpty() &&
         (item.contains("ASTERION-CYCLE-ACK:"+previousCheckpoint)||
          item.contains("ASTERION-CYCLE-DONE:"+previousCheckpoint)))evidence[1]++;
      String normalized=item.toLowerCase(java.util.Locale.ROOT)
        .replace('’','\'').replace('?', ' ').replaceAll("\\s+"," ").trim();
      boolean welcome=normalized.equals("what can i help with")||
        normalized.equals("what can i help you with")||
        normalized.equals("how can i help")||
        normalized.equals("how can i help you today")||
        normalized.equals("where should we begin")||
        normalized.equals("where should we start")||
        normalized.equals("what are you working on")||
        normalized.equals("what's on your mind today")||
        normalized.equals("ready when you are")||
        normalized.equals("comment puis-je vous aider")||
        normalized.equals("par quoi voulez-vous commencer");
      if(welcome){
        Rect b=new Rect(),screen=new Rect();
        node.getBoundsInScreen(b);
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root!=null)root.getBoundsInScreen(screen);
        if(!b.isEmpty()&&!screen.isEmpty()&&
           b.centerY()>screen.top+screen.height()*0.1f&&
           b.centerY()<screen.top+screen.height()*0.85f)evidence[0]++;
      }
    }
    for(int i=0;i<node.getChildCount()&&count[0]<=450;i++)
      inspectNewChatLanding(node.getChild(i),previousCheckpoint,evidence,depth+1,count);
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
  /**
   * Observe an explicit, unique terminal receipt in the assistant's visible
   * ChatGPT reply. A Send tap and a still-generating reply are NOT completion.
   *
   * The receipt token never occurs verbatim in the outgoing prompt (the model
   * constructs it from its checkpoint ID), so observing it is independent
   * evidence that an actual assistant reply reached the UI.
   */
  JSONObject observeCycleResponse(String checkpoint) {
    final JSONObject[] result={new JSONObject()};
    final CountDownLatch finished=new CountDownLatch(1);
    main.post(()->{
      try {
        JSONObject evidence=new JSONObject().put("visible",false)
          .put("generating",false).put("finished",false);
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null||root.getPackageName()==null||
           !"com.openai.chatgpt".contentEquals(root.getPackageName())) {
          result[0]=evidence;return;
        }
        String accepted="ASTERION-CYCLE-ACK:"+checkpoint;
        String complete="ASTERION-CYCLE-DONE:"+checkpoint;
        boolean[] flags=new boolean[3]; // ack, done, generating
        String[] spokenQuestion={""};
        observeMarkers(root,accepted,complete,flags,spokenQuestion,0,new int[]{0});
        evidence.put("visible",flags[0]||flags[1]||!spokenQuestion[0].isEmpty())
          .put("generating",flags[2]).put("finished",flags[1])
          .put("voice_question",spokenQuestion[0]);
        result[0]=evidence;
      }catch(Exception ignored){}finally{finished.countDown();}
    });
    try{if(!finished.await(3,TimeUnit.SECONDS))return new JSONObject();}
    catch(InterruptedException e){Thread.currentThread().interrupt();return new JSONObject();}
    return result[0];
  }
  private void observeMarkers(AccessibilityNodeInfo node,String accepted,String complete,
       boolean[] flags,String[] spokenQuestion,int depth,int[] seen) {
    if(node==null||depth>28||seen[0]++>=450||!node.isVisibleToUser())return;
    CharSequence value=node.getText(),description=node.getContentDescription();
    if(!node.isEditable()) {
      for(CharSequence item:new CharSequence[]{value,description}) {
        if(item==null)continue;
        String text=item.toString();
        if(text.length()>25000)continue;
        if(text.contains(accepted))flags[0]=true;
        if(text.contains(complete))flags[1]=true;
        // A question is only accepted from a visible non-editable reply
        // containing this exact cycle's checkpoint token.
        String prefix="ASTERION-VOICE-ASK:"+complete.substring(
            "ASTERION-CYCLE-DONE:".length())+"|";
        int begin=text.indexOf(prefix);
        if(begin>=0){
          String candidate=text.substring(begin+prefix.length());
          int end=candidate.indexOf('\n');
          if(end>=0)candidate=candidate.substring(0,end);
          candidate=candidate.trim();
          if(candidate.length()>=2&&candidate.length()<=700)
            spokenQuestion[0]=candidate;
        }
        String label=text.trim().toLowerCase(java.util.Locale.ROOT);
        if(label.equals("stop generating")||label.equals("stop responding")||
           label.equals("stop response")||label.equals("arrêter la génération")||
           label.equals("arrêter la réponse"))flags[2]=true;
      }
    }
    for(int i=0;i<node.getChildCount()&&seen[0]<450;i++)
      observeMarkers(node.getChild(i),accepted,complete,flags,spokenQuestion,depth+1,seen);
  }

  /** Focus the real visible ChatGPT composer before attempting native keyboard input.
   * Returns requested/ready separately; foreground and keyboard state must be
   * checked again before sending. Never overwrite another user's draft.
   */
  JSONObject prepareChatKeyboard(){
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] result={new JSONObject()};
    main.post(()->{
      try{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null||root.getPackageName()==null||
           !"com.openai.chatgpt".contentEquals(root.getPackageName())){
          result[0]=new JSONObject().put("ready",false).put("reason","ChatGPT is not foreground");
        }else if(chatKeyboard()!=null){
          result[0]=new JSONObject().put("ready",true).put("reason","Android keyboard focused");
        }else{
          AccessibilityNodeInfo field=findComposer(root);
          boolean pressed=field!=null&&field.performAction(AccessibilityNodeInfo.ACTION_CLICK);
          if(!pressed){
            DisplayMetrics metrics=new DisplayMetrics();
            android.view.WindowManager wm=(android.view.WindowManager)getSystemService(WINDOW_SERVICE);
            wm.getDefaultDisplay().getRealMetrics(metrics);
            // Tap the INPUT REGION, never the trailing Send / Stop control.
            float x=metrics.widthPixels*0.39f;
            float y=metrics.heightPixels*0.925f;
            Path point=new Path();point.moveTo(x,y);
            GestureDescription gesture=new GestureDescription.Builder()
              .addStroke(new GestureDescription.StrokeDescription(point,0,70)).build();
            pressed=dispatchGesture(gesture,new GestureResultCallback(){},main);
          }
          result[0]=new JSONObject().put("ready",false)
            .put("focus_requested",pressed)
            .put("reason",pressed?"Waiting for visible ChatGPT keyboard":"Composer focus unavailable");
        }
      }catch(Exception e){
        try{result[0]=new JSONObject().put("ready",false)
          .put("reason","Keyboard preparation failed: "+e.getClass().getSimpleName());}
        catch(Exception ignored){}
      }finally{done.countDown();}
    });
    try{done.await(3,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
    return result[0];
  }
  /** Request ChatGPT foreground through Android's own launcher intent, or dismiss
   * a blocking SystemUI shade. Never treat intent dispatch as confirmed focus. */
  JSONObject requestChatForeground(){
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] output={new JSONObject()};
    main.post(()->{
      try{
        AccessibilityNodeInfo root=getRootInActiveWindow();
        String pkg=root==null||root.getPackageName()==null?"":root.getPackageName().toString();
        if("com.openai.chatgpt".equals(pkg)){
          output[0]=new JSONObject().put("requested",false).put("already_foreground",true);
        }else if("com.android.systemui".equals(pkg)){
          output[0]=new JSONObject().put("requested",performGlobalAction(GLOBAL_ACTION_BACK))
            .put("reason","Dismissed SystemUI obstruction; recheck ChatGPT");
        }else{
          android.content.Intent intent=getPackageManager().getLaunchIntentForPackage("com.openai.chatgpt");
          if(intent==null){
            output[0]=new JSONObject().put("requested",false)
              .put("reason","ChatGPT launch activity unavailable");
          }else{
            intent.addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            output[0]=new JSONObject().put("requested",true)
              .put("verified_foreground",false);
          }
        }
      }catch(Exception e){
        try{output[0]=new JSONObject().put("requested",false)
          .put("reason",e.getClass().getSimpleName());}catch(Exception ignored){}
      }finally{done.countDown();}
    });
    try{done.await(3,TimeUnit.SECONDS);}catch(InterruptedException e){Thread.currentThread().interrupt();}
    return output[0];
  }
  JSONObject sendChatMessage(String message) {
    final CountDownLatch done=new CountDownLatch(1);
    final JSONObject[] output={chatOutcome(false,true,"Native keyboard dispatch did not finish")};
    main.post(()->{
      try {
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null||root.getPackageName()==null||
           !"com.openai.chatgpt".contentEquals(root.getPackageName())){
          output[0]=chatOutcome(false,false,"ChatGPT Android app is not foreground");
          done.countDown();return;
        }
        // No ACTION_SET_TEXT injection: send through Android's active keyboard.
        keyboardChatSend(message,output,done);
      }catch(Exception e){
        output[0]=chatOutcome(false,false,
          "ChatGPT keyboard dispatch failed: "+e.getClass().getSimpleName());
        done.countDown();
      }
    });
    boolean finished=false;
    try{finished=done.await(11,TimeUnit.SECONDS);}
    catch(InterruptedException e){Thread.currentThread().interrupt();}
    if(!finished)return chatOutcome(false,true,
      "Keyboard dispatch timed out; inspect before retry");
    return output[0];
  }
  @Override public void onInterrupt() { }
  @Override public void onDestroy() { if(active == this) active = null; super.onDestroy(); }
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
          InputMethod.AccessibilityInputConnection nativeKeyboard=chatKeyboard();
          if(nativeKeyboard!=null){
            String current=inputText(nativeKeyboard);
            String intended=a.optString("text");
            if(current!=null&&current.isEmpty()&&!intended.isEmpty()&&intended.length()<=3800){
              nativeKeyboard.commitText(intended,1,null);
              result[0]=intended.equals(inputText(nativeKeyboard));
            }
          }else if (target != null && target.isEditable() && !"com.openai.chatgpt".equals(
              root==null||root.getPackageName()==null?"":root.getPackageName().toString())) {
            Bundle b = new Bundle();
            b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,a.optString("text"));
            result[0]=target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,b);
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
      result.put("available",root!=null);
      result.put("foreground_package",root==null||root.getPackageName()==null?"":root.getPackageName().toString());
      InputMethod ime=Build.VERSION.SDK_INT>=33?getInputMethod():null;
      EditorInfo editor=ime==null?null:ime.getCurrentInputEditorInfo();
      result.put("keyboard",new JSONObject().put("active",ime!=null&&ime.getCurrentInputStarted())
        .put("editor_package",editor==null?"":editor.packageName)
        .put("ime_action",editor==null?-1:editor.imeOptions&EditorInfo.IME_MASK_ACTION)
        .put("draft_empty",editor!=null&&"com.openai.chatgpt".equals(editor.packageName)
          &&"".equals(inputText(chatKeyboard()))));
      if(root!=null)result.put("root",node(root,0,new int[]{0}));
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
