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
    private static volatile JSONObject lastCompletedGeneration;
    static {
        boolean loaded;
        try {System.loadLibrary("asterion_llm");loaded=true;}
        catch (UnsatisfiedLinkError error) {loaded=false;lastFailure="native_library_missing";}
        LIBRARY_LOADED=loaded;
    }
    private OnDeviceLlm(){}
    private static native boolean nativeLoad(String privateFile);
    private static native boolean nativeLoadProfile(String file,String adapter,String backend,int layers);
    private static native void nativeConfigureContext(int threads,int kvBits);
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
        int promptTokens,omittedMessages,pieces;
        long firstPieceNanos,lastPieceNanos;
        NativeStream(Stream listener){this.listener=listener;}
        public void onStart(boolean thinking,int tokens,int omitted){
            promptTokens=tokens;
            omittedMessages=omitted;
            output.initialThinking(thinking);
            if(listener!=null)listener.context(tokens,omitted);
        }
        public void onToken(byte[] bytes){
            lastPieceNanos=System.nanoTime();
            if(pieces++==0)firstPieceNanos=lastPieceNanos;
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
            .put("weight_precision",profile.precision)
            .put("configured_backend",profile.backendDevice.isEmpty()?"CPU":profile.backendDevice)
            .put("configured_offload_layers",profile.offloadLayers)
            .put("configured_kv_bits",profile.kvBits)
            .put("configured_adapter_sha256",profile.adapterSha256)
            .put("device_resources",new OnDeviceModelResources(context).status(context))
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
            .put("last_failure_code",lastFailure)
            .put("last_completed_generation",lastCompletedGeneration==null?JSONObject.NULL:lastCompletedGeneration);
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
                File file=stageArtifact(context,folder,profile.file,profile.bytes,profile.sha256);
                if(CANCELLED.get())throw new InterruptedException("user_cancelled");
                if(profile.adapterFile.isEmpty()&&profile.backendDevice.isEmpty()){
                    modelReady=nativeLoad(file.getAbsolutePath());
                }else{
                    String adapter="";
                    if(!profile.adapterFile.isEmpty())
                        adapter=stageArtifact(context,folder,profile.adapterFile,profile.adapterBytes,
                            profile.adapterSha256).getAbsolutePath();
                    if(CANCELLED.get())throw new InterruptedException("user_cancelled");
                    modelReady=nativeLoadProfile(file.getAbsolutePath(),adapter,profile.backendDevice,profile.offloadLayers);
                }
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
    private static File stageArtifact(Context context,File folder,String name,long length,String sha)throws Exception {
        File file=new File(folder,name);
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        byte[] buffer=new byte[256*1024];
        if(file.isFile()&&file.length()==length){
            try(InputStream in=new FileInputStream(file)){
                for(int size;(size=in.read(buffer))!=-1;){
                    if(CANCELLED.get())throw new InterruptedException("user_cancelled");
                    digest.update(buffer,0,size);
                }
            }
            if(sha.equals(hex(digest.digest())))return file;
        }
        File temporary=File.createTempFile("model-", ".partial",folder);
        try{
            long received=0;
            digest.reset();
            try(InputStream input=context.getAssets().open("models/"+name,AssetManager.ACCESS_STREAMING);
                FileOutputStream output=new FileOutputStream(temporary)){
                for(int size;(size=input.read(buffer))!=-1;){
                    if(CANCELLED.get())throw new InterruptedException("user_cancelled");
                    received+=size;
                    if(received>length)throw new IllegalStateException("invalid_length");
                    output.write(buffer,0,size);
                    digest.update(buffer,0,size);
                }
                output.getFD().sync();
            }
            if(received!=length||!sha.equals(hex(digest.digest())))
                throw new IllegalStateException("model_checksum_mismatch");
            android.system.Os.rename(temporary.getAbsolutePath(),file.getAbsolutePath());
            return file;
        }finally{
            temporary.delete();
        }
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
            long requestStarted=System.nanoTime();
            boolean warm=modelReady;
            int outputBudget=ControlAssistantPreferences.outputTokens(context,profile);
            new OnDeviceModelResources(context).contextTokens(profile,outputBudget,modelReady);
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
            guidance+="\n"+AssistantRequirements.context(context,userPrompt,project);
            if(!recalled.isEmpty())guidance+="\nOwner-approved memories, reference only:\n"+recalled;
            String systemText=profile.systemInstructions(guidance);
            OnDeviceModelResources resources=new OnDeviceModelResources(context);
            int contextBudget=resources.contextTokens(profile,outputBudget,true);
            nativeConfigureContext(resources.threads(),profile.kvBits);
            String[] roles=new String[messages.size()];
            byte[][] content=new byte[messages.size()][];
            for(int i=0;i<messages.size();i++){
                AssistantConversation.Message m=messages.get(i);
                if(!m.role.equals(i%2==0?"user":"assistant")||m.text==null)
                    throw new IllegalArgumentException("invalid_dialogue_order");
                roles[i]=m.role;content[i]=m.text.getBytes(StandardCharsets.UTF_8);
            }
            NativeStream stream=new NativeStream(listener);
            long inferenceStarted=System.nanoTime();
            byte[] output=nativeGenerate(systemText.getBytes(StandardCharsets.UTF_8),roles,content,
                outputBudget,contextBudget,stream);
            if(CANCELLED.get())throw new InterruptedException("user_cancelled");
            if(output==null||output.length==0)throw new IllegalStateException("native_context_or_generation_failed");
            String result=stream.output.finish(output);
            if(result.isBlank())throw new IllegalStateException("no_visible_model_answer");
            OnDeviceModelResources after=new OnDeviceModelResources(context);
            lastCompletedGeneration=new JSONObject()
                .put("base_sha256",profile.sha256)
                .put("adapter_sha256",profile.adapterSha256)
                .put("weight_precision",profile.precision)
                .put("kv_bits",profile.kvBits)
                .put("configured_backend",profile.backendDevice.isEmpty()?"CPU":profile.backendDevice)
                .put("model_already_loaded",warm)
                .put("context_tokens",contextBudget)
                .put("prompt_tokens",stream.promptTokens)
                .put("omitted_messages",stream.omittedMessages)
                .put("generated_token_pieces",stream.pieces)
                .put("request_to_first_piece_ms",(stream.firstPieceNanos-requestStarted)/1_000_000)
                .put("inference_to_first_piece_ms",(stream.firstPieceNanos-inferenceStarted)/1_000_000)
                .put("decode_between_pieces_ms",(stream.lastPieceNanos-stream.firstPieceNanos)/1_000_000)
                .put("process_pss_kib_after",android.os.Debug.getPss())
                .put("available_bytes_before_context",resources.memory.availMem)
                .put("available_bytes_after",after.memory.availMem)
                .put("thermal_before",resources.thermalStatus)
                .put("thermal_after",after.thermalStatus);
            return result;
        }finally{BUSY.set(false);}
    }
}
