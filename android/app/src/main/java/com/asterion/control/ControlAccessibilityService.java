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
  @Override public void onAccessibilityEvent(AccessibilityEvent e) { }
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
          if (target != null && target.isEditable()) {
            Bundle b = new Bundle(); b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, a.optString("text"));
            result[0] = target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,b);
          }
          done.countDown(); return;
        }
        case "tap": case "swipe": {
          float x = (float)a.optDouble("x",0), y = (float)a.optDouble("y",0);
          Path p = new Path(); p.moveTo(x,y);
          long duration = 55;
          if(cmd.equals("swipe")) { p.lineTo((float)a.optDouble("x2",x),(float)a.optDouble("y2",y)); duration = Math.max(100,Math.min(5000,a.optLong("duration_ms",400))); }
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
