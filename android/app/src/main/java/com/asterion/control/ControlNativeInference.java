package com.asterion.control;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.SystemClock;
import org.json.JSONObject;
import java.io.File;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.lang.reflect.InvocationHandler;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/**
 * Actual on-device GGUF inference adapter via the opt-in MIT AiKit JNI
 * llama.cpp runtime. THIS IS NOT a fake response or a remote API.
 *
 * Java reflection allows the existing Asterion Android Java-only default
 * configuration and minSdk29 compatibility to remain unchanged. To package
 * the actual MIT native libraries, an explicitly selected Android build must
 * set -PasterionNativeAi=true; that build needs compileSdk37 / minSdk30.
 * The default build never silently grows a native library or changes minSdk.
 *
 * Everything is OWNER-initiated in foreground. No auto-generated content
 * restrictions are added by Asterion; underlying model weights may retain
 * their own learned behavior. App file, signing identity, Control pairing and
 * native LAN/WSS remain unchanged.
 *
 * The true AiKit 1.0 API was checked against its upstream source:
 *   AiKitEngine.Companion.create(context), loadModel(path,listener),
 *   isModelLoaded(), unloadModel()
 *   AiKitEngineExtensionsKt.chat(engine)
 *   AiKitChat.sendMessage(prompt,maxTokens,systemPrompt,listener)
 *
 * This backend has not been APK-compiled or device-benchmarked under the
 * owner's separate no-build hold; its runtime failures are reported honestly.
 */
final class ControlNativeInference {
  private static final ExecutorService WORK=Executors.newSingleThreadExecutor();
  private static final Handler MAIN=new Handler(Looper.getMainLooper());
  private static final AtomicBoolean STARTING=new AtomicBoolean(false);
  private static final AtomicBoolean GENERATING=new AtomicBoolean(false);
  private static volatile Object engine=null, chat=null;
  private static volatile String state="not_loaded", lastError="";
  private static volatile long loadedAtMs=0, lastGenerationMs=0;
  private static volatile long lastTokens=0;
  private static volatile String modelSha256="";
  private static final int MAX_REPLY_CHARS=12000;
  private static final String SYSTEM=(
    "You are Asterion Intelligence, the owner's on-device general assistant. "+
    "Respond usefully and directly, in the language of the request. This "+
    "is REAL offline text generation: never pretend to have executed tools, "+
    "searched the web, accessed private files or modified another device "+
    "unless an authenticated external Control receipt is provided. "+
    "You may handle creative writing and adult fictional themes where "+
    "otherwise lawful; no artificial topic filtering is applied by Control."
  );
  private ControlNativeInference(){}

  private static void requireOwner(Activity owner){
    if(owner==null||owner!=MainActivity.foregroundActivity()||
       owner.isFinishing())
      throw new SecurityException("Foreground owner approval required");
  }

  private static void show(Consumer<String> feedback,String message){
    MAIN.post(()->feedback.accept(message));
  }

  private static void safeStateError(Throwable error){
    state="error";
    lastError=error==null?"Unknown":error.getClass().getSimpleName();
  }

  private static Object methodTarget(Object obj,String method)throws Exception{
    Method target=obj.getClass().getMethod(method);
    return target.invoke(obj);
  }

  private static boolean available(){
    try{
      Class.forName("com.hazratbilal.aikit.core.AiKitEngine");
      Class.forName("com.hazratbilal.aikit.chat.AiKitChat");
      return true;
    }catch(ClassNotFoundException|LinkageError missing){
      return false;
    }
  }

  private static void resourcePreflight(Context c)throws Exception{
    ActivityManager manager=(ActivityManager)c.getSystemService(
        Context.ACTIVITY_SERVICE);
    if(manager==null)throw new IllegalStateException("Android memory unavailable");
    ActivityManager.MemoryInfo info=new ActivityManager.MemoryInfo();
    manager.getMemoryInfo(info);
    // Q4_K_M Qwen3.5-2B GGUF is 1,396,198,496 bytes; JNI buffers,
    // KV cache and other apps need independent headroom. The real peak is
    // NOT proven, so do not start under moderate/critical memory pressure.
    if(info.lowMemory||info.availMem<2_300_000_000L)
      throw new IllegalStateException("Insufficient free Android model RAM");
    PowerManager power=(PowerManager)c.getSystemService(Context.POWER_SERVICE);
    if(power!=null&&android.os.Build.VERSION.SDK_INT>=29 &&
       power.getCurrentThermalStatus()>=PowerManager.THERMAL_STATUS_SEVERE)
      throw new IllegalStateException("Thermal pressure forbids model load");
  }

  private static Object createActualEngine(Context context)throws Exception{
    Class<?> type=Class.forName("com.hazratbilal.aikit.core.AiKitEngine");
    Field companionField=type.getField("Companion");
    Object companion=companionField.get(null);
    Method create=companion.getClass().getMethod("create",Context.class);
    return create.invoke(companion,context.getApplicationContext());
  }

  private static Object createActualChat(Object loaded)throws Exception{
    Class<?> extension=Class.forName(
        "com.hazratbilal.aikit.chat.AiKitEngineExtensionsKt");
    Class<?> type=Class.forName(
        "com.hazratbilal.aikit.core.AiKitEngine");
    return extension.getMethod("chat",type).invoke(null,loaded);
  }

  private static boolean reallyLoaded(){
    Object active=engine;
    if(active==null)return false;
    try{
      Object result=methodTarget(active,"isModelLoaded");
      return Boolean.TRUE.equals(result);
    }catch(Exception|LinkageError failure){return false;}
  }

  static void load(Activity owner,Consumer<String> feedback){
    requireOwner(owner);
    if(!STARTING.compareAndSet(false,true)){
      feedback.accept("Native model loading already underway");return;
    }
    Context context=owner.getApplicationContext();
    state="verifying_weights";
    WORK.execute(()->{
      try{
        if(!available())
          throw new IllegalStateException(
              "Native AiKit library not included in this Android build");
        resourcePreflight(context);
        File source=ControlModelVault.requireVerifiedWeights(context);
        modelSha256=ControlModelVault.modelSha();
        if(reallyLoaded()){
          state="loaded";show(feedback,"Local model already loaded.");return;
        }
        final Object newEngine=createActualEngine(context);
        final Class<?> listener=Class.forName(
          "com.hazratbilal.aikit.core.AiKitEngine$ModelStateListener");
        final long started=SystemClock.elapsedRealtime();
        Object callback=Proxy.newProxyInstance(listener.getClassLoader(),
          new Class<?>[]{listener},(proxy,method,args)->{
            String type=method.getName();
            if(type.equals("onModelLoading")){
              state="loading_native_weights";
            }else if(type.equals("onModelLoaded")){
              if(!Boolean.TRUE.equals(methodTarget(newEngine,"isModelLoaded"))){
                state="error";lastError="NativeModelNotLoaded";
                show(feedback,"Native engine did not report ready");return null;
              }
              engine=newEngine;
              chat=createActualChat(newEngine);
              loadedAtMs=System.currentTimeMillis();
              state="loaded";lastError="";STARTING.set(false);
              show(feedback,"Offline model loaded by native llama.cpp engine.");
            }else if(type.equals("onModelError")){
              Throwable cause=(args!=null&&args.length>0&&
                args[0] instanceof Throwable)?(Throwable)args[0]:null;
              safeStateError(cause);STARTING.set(false);
              show(feedback,"Native model load failed: "+lastError);
            }else if(type.equals("onModelUnloaded")){
              state="not_loaded";chat=null;engine=null;
            }else if(type.equals("toString")){
              return "AsterionNativeAiModelListener";
            }else if(type.equals("hashCode")){
              return System.identityHashCode(proxy);
            }else if(type.equals("equals")){
              return proxy==args[0];
            }
            return null;
          });
        // Library performs the actual native file load in its own coroutine.
        newEngine.getClass().getMethod("loadModel",String.class,listener)
          .invoke(newEngine,source.getAbsolutePath(),callback);
        // STARTING stays true until the REAL onModelLoaded/onModelError
        // callback, preventing overlapping native memory allocations.
      }catch(Throwable error){
        safeStateError(error);
        show(feedback,"Offline AI unavailable: "+lastError);
        STARTING.set(false);
      }
    });
  }

  static void generate(Activity owner,String request,Consumer<String> feedback){
    requireOwner(owner);
    if(request==null||request.trim().isEmpty()||request.length()>5000){
      feedback.accept("Enter a request of up to 5,000 characters");return;
    }
    if(!reallyLoaded()||chat==null){
      feedback.accept("Load and verify an actual offline model first");return;
    }
    if(!GENERATING.compareAndSet(false,true)){
      feedback.accept("The offline model is already generating");return;
    }
    state="generating";
    lastTokens=0;
    final Object activeChat=chat;
    WORK.execute(()->{
      try {
        Class<?> listener=Class.forName(
           "com.hazratbilal.aikit.chat.AiKitChat$ChatListener");
        StringBuilder tokens=new StringBuilder();
        final long started=SystemClock.elapsedRealtime();
        Object callback=Proxy.newProxyInstance(listener.getClassLoader(),
          new Class<?>[]{listener},(proxy,method,args)->{
            String type=method.getName();
            if(type.equals("onGenerationStarted")){
              state="generating";
            }else if(type.equals("onToken")){
              if(args!=null&&args.length==1&&args[0] instanceof String){
                String part=(String)args[0];
                if(tokens.length()<MAX_REPLY_CHARS)
                  tokens.append(part,0,Math.min(part.length(),
                      MAX_REPLY_CHARS-tokens.length()));
                lastTokens++;
              }
            }else if(type.equals("onGenerationComplete")){
              final String answer=(args!=null&&args.length>0&&
                  args[0] instanceof String)?(String)args[0]:tokens.toString();
              lastGenerationMs=SystemClock.elapsedRealtime()-started;
              state="loaded";GENERATING.set(false);
              show(feedback,answer.length()>MAX_REPLY_CHARS?
                answer.substring(0,MAX_REPLY_CHARS):answer);
            }else if(type.equals("onGenerationError")){
              Throwable issue=args!=null&&args.length>0&&
                 args[0] instanceof Throwable?(Throwable)args[0]:null;
              safeStateError(issue);
              GENERATING.set(false);
              show(feedback,"Local generation failed: "+lastError);
            }else if(type.equals("onCancelled")){
              state=reallyLoaded()?"loaded":"not_loaded";
              GENERATING.set(false);
              show(feedback,"Offline generation cancelled.");
            }else if(type.equals("toString")){
              return "AsterionNativeAiChatListener";
            }else if(type.equals("hashCode")){
              return System.identityHashCode(proxy);
            }else if(type.equals("equals")){
              return proxy==args[0];
            }
            return null;
          });
        activeChat.getClass().getMethod(
           "sendMessage",String.class,int.class,String.class,listener)
           .invoke(activeChat,request.trim(),512,SYSTEM,callback);
      }catch(Throwable error){
        safeStateError(error);
        GENERATING.set(false);
        show(feedback,"Local generation unavailable: "+lastError);
      }
    });
  }

  static void cancel(Activity owner){
    requireOwner(owner);
    WORK.execute(()->{
      try{
        Object current=chat;
        if(current!=null)
          current.getClass().getMethod("cancelGeneration").invoke(current);
      }catch(Exception ignored){}
    });
  }

  static void unload(Activity owner,Consumer<String> feedback){
    requireOwner(owner);
    if(STARTING.get()||GENERATING.get()){
      feedback.accept("Model is busy; cancel generation or finish loading first");
      return;
    }
    WORK.execute(()->{
      try {
        Object current=engine;
        if(current!=null)current.getClass().getMethod("unloadModel").invoke(current);
        state="not_loaded";engine=null;chat=null;
        modelSha256="";loadedAtMs=0;
        show(feedback,"Native model unloaded; memory released.");
      }catch(Throwable failure){
        safeStateError(failure);
        show(feedback,"Native model unload failed: "+lastError);
      }
    });
  }

  static JSONObject status()throws Exception{
    return new JSONObject()
      .put("native_runtime_packaged",available())
      .put("native_runtime_kind","aikit_llamacpp_jni")
      .put("actual_model_loaded",reallyLoaded())
      .put("state",state)
      .put("load_in_progress",STARTING.get())
      .put("generation_in_progress",GENERATING.get())
      .put("model_sha256",modelSha256)
      .put("last_generation_ms",lastGenerationMs)
      .put("received_token_callback_count",lastTokens)
      .put("loaded_at_ms",loadedAtMs)
      .put("training_performed",false)
      .put("actual_device_benchmark_passed",false)
      .put("last_error_code",lastError);
  }
}
