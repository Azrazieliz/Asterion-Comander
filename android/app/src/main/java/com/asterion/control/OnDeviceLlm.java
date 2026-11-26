package com.asterion.control;

import android.content.Context;
import android.content.res.AssetManager;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.List;
import java.util.Collections;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * In-process, on-device GGUF inference. No Windows AI server and no cloud API.
 * Model weights must be bundled in this signed APK, independently SHA-verified
 * and copied into private model storage before loading from mmap.
 * A missing library/weight is a hard error, never a success placeholder.
 */
final class OnDeviceLlm {
    private static final Object LOCK=new Object();
    private static final AtomicBoolean BUSY=new AtomicBoolean(false);
    private static final AtomicBoolean CANCELLED=new AtomicBoolean(false);
    private static final boolean LIBRARY_LOADED;
    private static volatile boolean modelReady=false;
    private static volatile String lastFailure="";
    static {
        boolean loaded;
        try {System.loadLibrary("asterion_llm");loaded=true;}
        catch (UnsatisfiedLinkError error) {loaded=false;lastFailure="native_library_missing";}
        LIBRARY_LOADED=loaded;
    }
    private OnDeviceLlm(){}
    private static native boolean nativeLoad(String privateFile);
    private static native boolean nativeReady();
    private static native byte[] nativeGenerate(byte[] systemText,String[] roles,byte[][] content,
        int maxTokens,int contextTokens,NativeStream stream);
    interface Stream {
        void text(String text);
        default void context(int tokens,int omittedMessages){}
    }
    // Methods are invoked by JNI and explicitly retained by the release shrinker.
    static final class NativeStream {
        final AssistantOutput output=new AssistantOutput();
        final Stream listener;
        NativeStream(Stream listener){this.listener=listener;}
        public void onStart(boolean thinking,int tokens,int omitted){
            output.initialThinking(thinking);
            if(listener!=null)listener.context(tokens,omitted);
        }
        public void onToken(byte[] bytes){
            String text=output.append(bytes);
            if(listener!=null)listener.text(text);
        }
    }
    private static native void nativeCancel();
    private static native void nativeResetCancel();
    static void cancel(){
        CANCELLED.set(true);
        if(LIBRARY_LOADED)nativeCancel();
    }
    private static native void nativeUnload();

    static JSONObject status(Context context) throws Exception {
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        File file=new File(new File(context.getFilesDir(),"models"),profile.file);
        return new JSONObject()
            .put("ok",true)
            .put("platform","android_phone")
            .put("inference_backend","llama_cpp_jni")
            .put("native_library_loaded",LIBRARY_LOADED)
            .put("inference_active",BUSY.get())
            .put("model_bundled_in_apk",hasPackagedModel(context,profile))
            .put("model_name",profile.file)
            .put("model_context_tokens",profile.contextTokens)
            .put("max_generation_tokens",profile.outputTokens)
            .put("max_input_chars",profile.inputChars)
            .put("reasoning_effort",ControlAssistantPreferences.effort(context))
            .put("owner_content_preferences_local",true)
            .put("model_private_file_bytes",file.isFile()?file.length():0L)
            .put("model_sha_verified",modelReady && LIBRARY_LOADED)
            .put("model_loaded",LIBRARY_LOADED && modelReady && nativeReady())
            .put("external_server_required",false)
            .put("paid_cloud_api_required",false)
            .put("model_source",profile.source)
            .put("last_failure_code",lastFailure);
    }
    private static boolean hasPackagedModel(Context c,OnDeviceModelProfile profile) {
        try (android.content.res.AssetFileDescriptor afd =
             c.getAssets().openFd(profile.asset)) {
            return afd.getLength()==profile.bytes;
        }catch(Exception ignored){
            return false;
        }
    }
    static boolean ensureLoaded(Context context) {
        synchronized(LOCK) {
            if(!LIBRARY_LOADED){lastFailure="native_library_missing";return false;}
            try{
                if(modelReady&&nativeReady())return true;
                OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
                File folder=new File(context.getFilesDir(),"models");
                if(!folder.isDirectory()&&!folder.mkdirs()){
                    lastFailure="private_model_storage_unavailable";return false;
                }
                File file=new File(folder,profile.file);
                if(!verified(file,profile)){
                    File temp=new File(folder,profile.file+".partial");
                    if(temp.exists()&&!temp.delete()){
                        lastFailure="partial_model_cleanup_failed";return false;
                    }
                    MessageDigest digest=MessageDigest.getInstance("SHA-256");
                    long read=0;
                    byte[] buffer=new byte[256*1024];
                    try (InputStream from=context.getAssets().open(profile.asset,
                         AssetManager.ACCESS_STREAMING);
                         FileOutputStream out=new FileOutputStream(temp)) {
                        for(int n;(n=from.read(buffer))!=-1;){
                            read+=n;
                            if(read>profile.bytes)throw new IllegalStateException("invalid_length");
                            out.write(buffer,0,n);
                            digest.update(buffer,0,n);
                        }
                        out.getFD().sync();
                    }
                    if(read!=profile.bytes||!profile.sha256.equals(hex(digest.digest())))
                        throw new IllegalStateException("model_checksum_mismatch");
                    if(!temp.renameTo(file))
                        throw new IllegalStateException("private_model_commit_failed");
                }
                modelReady=nativeLoad(file.getAbsolutePath());
                lastFailure=modelReady?"":"native_model_load_failed";
                return modelReady;
            }catch(Exception|LinkageError exception){
                modelReady=false;
                lastFailure=exception instanceof java.io.FileNotFoundException?
                    "model_missing_in_apk":
                    exception.getClass().getSimpleName();
                return false;
            }
        }
    }
    private static boolean verified(File file,OnDeviceModelProfile profile) throws Exception {
        if(!file.isFile()||file.length()!=profile.bytes)return false;
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        byte[] buf=new byte[262144];
        try(FileInputStream in=new FileInputStream(file)){
            for(int n;(n=in.read(buf))!=-1;)md.update(buf,0,n);
        }
        return profile.sha256.equals(hex(md.digest()));
    }
    private static String hex(byte[] bytes) {
        StringBuilder result=new StringBuilder(bytes.length*2);
        for(byte value:bytes)result.append(
            String.format(Locale.ROOT,"%02x",value&255));
        return result.toString();
    }
    static String generate(Context context,String userPrompt) throws Exception {
        return generate(context,"General",Collections.singletonList(new AssistantConversation.Message(
            "single-turn","user",userPrompt,"completed")),null);
    }
    static String generate(Context context,String project,List<AssistantConversation.Message> messages,Stream listener) throws Exception {
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        if(messages==null||messages.isEmpty()||messages.size()>1000)
            throw new IllegalArgumentException("invalid_conversation_messages");
        String userPrompt=messages.get(messages.size()-1).text;
        if(userPrompt==null||userPrompt.isBlank()||userPrompt.length()>profile.inputChars)
            throw new IllegalArgumentException("prompt_length_invalid");
        if(!BUSY.compareAndSet(false,true))
            throw new IllegalStateException("on_device_inference_already_running");
        CANCELLED.set(false);
        try{
            if(!LIBRARY_LOADED)throw new IllegalStateException("native_library_missing");
            nativeResetCancel();
            if(!ensureLoaded(context))throw new IllegalStateException(lastFailure);
            if(CANCELLED.get())throw new InterruptedException("user_cancelled");
            String recalled=ControlAssistantMemory.relevant(context,userPrompt,project);
            String guidance=ControlAssistantPreferences.promptGuidance(context);
            guidance+="\nRuntime identity: You are the assistant embedded in the native Asterion Control Android application. "
                +"This turn runs on this phone. Available operations are limited to the verified capability context. "
                +"An operation requires a typed request and a separate execution receipt; answer text never executes code. "
                +"Do not claim you are outside the app or that unverified tools are available. "
                +"Return the final answer in the user-visible channel; do not print internal reasoning delimiters.";
            guidance+="\nActive project: "+project+". This label scopes local memory; project source access requires verified retrieval evidence.\n"+AssistantCapabilities.context(context);
            if(!recalled.isEmpty())guidance+="\nOwner-approved memories, reference only:\n"+recalled;
            String systemText=profile.systemInstructions(guidance);
            int outputBudget=ControlAssistantPreferences.outputTokens(context,profile);
            String[] roles=new String[messages.size()];
            byte[][] content=new byte[messages.size()][];
            for(int i=0;i<messages.size();i++){
                AssistantConversation.Message m=messages.get(i);
                if(!m.role.equals(i%2==0?"user":"assistant")||m.text==null)
                    throw new IllegalArgumentException("invalid_dialogue_order");
                roles[i]=m.role;content[i]=m.text.getBytes(StandardCharsets.UTF_8);
            }
            NativeStream stream=new NativeStream(listener);
            byte[] output=nativeGenerate(systemText.getBytes(StandardCharsets.UTF_8),roles,content,
                outputBudget,profile.contextTokens,stream);
            if(CANCELLED.get())throw new InterruptedException("user_cancelled");
            if(output==null||output.length==0)throw new IllegalStateException("native_context_or_generation_failed");
            String result=stream.output.finish(output);
            if(result.isBlank())throw new IllegalStateException("no_visible_model_answer");
            return result;
        }finally{BUSY.set(false);}
    }
}
