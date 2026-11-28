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

/**
 * In-process, on-device GGUF inference. No Windows AI server and no cloud API.
 * Model weights must be bundled in this signed APK, independently SHA-verified
 * and copied into private model storage before loading from mmap.
 * A missing library/weight is a hard error, never a success placeholder.
 */
final class OnDeviceLlm {
    private static final Object LOCK=new Object();
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
    private static final InferenceGate GATE=new InferenceGate(
        ()->{if(LIBRARY_LOADED)nativeResetCancel();}, ()->{if(LIBRARY_LOADED)nativeCancel();});
    private OnDeviceLlm(){}
    private static native boolean nativeLoad(String privateFile);
    private static native boolean nativeLoadProfile(String file,String adapter,String backend,int layers,boolean mappedNoRepack);
    private static native void nativeConfigureContext(int threads,int kvBits);
    private static native boolean nativeReady();
    private static native String nativeBackendReport();
    private static native String nativeVulkanProbe();
    private static volatile JSONObject cachedBackendReport,lastVulkanProbe;
    static JSONObject configureVulkan(Context context,int layers) throws Exception {
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        if(!LIBRARY_LOADED)throw new IllegalStateException("native_library_missing");
        if(!profile.backendDevice.isEmpty()||layers<0||layers>profile.maxVulkanLayers)
            throw new IllegalArgumentException("outside_signed_vulkan_budget");
        InferenceGate.Request request=new InferenceGate.Request();
        GATE.begin(request);
        try {
            JSONObject probe=new JSONObject().put("requested_layers",layers);
            if(layers>0){
                OnDeviceModelResources resources=new OnDeviceModelResources(context);
                // The probe is small and independent of the model's fit.
                // Full model/context admission remains unchanged at generation.
                if(resources.memory.lowMemory)throw new IllegalStateException("android_memory_pressure");
                if(resources.thermalStatus>=android.os.PowerManager.THERMAL_STATUS_SEVERE)
                    throw new IllegalStateException("android_thermal_pressure");
                String raw=nativeVulkanProbe();
                String[] fields=raw==null?new String[0]:raw.split("\\|",-1);
                boolean passed=fields.length==5&&"passed".equals(fields[0]);
                probe.put("passed",passed).put("observed_at_ms",System.currentTimeMillis());
                if(passed){
                    probe.put("device",fields[1]).put("description",fields[2])
                        .put("matrix_compute_and_readback_us",Long.parseLong(fields[3]))
                        .put("max_absolute_error",Double.parseDouble(fields[4]));
                }else probe.put("reason",fields.length>=2?fields[1]:"invalid_native_probe_result");
                lastVulkanProbe=new JSONObject(probe.toString());
                if(!passed)return probe.put("selection_saved",false);
            }
            synchronized(LOCK){
                ControlAssistantPreferences.saveVulkanLayers(context,profile,layers);
                if(modelReady){nativeUnload();modelReady=false;}
                cachedBackendReport=null;
            }
            return probe.put("selection_saved",true)
                .put("model_gpu_inference_verified",false);
        }finally{GATE.end(request);}
    }
    private static JSONObject runtimeBackends() throws Exception{
        if(!LIBRARY_LOADED)return new JSONObject().put("available",false).put("reason","native_library_missing");
        if(GATE.busy()){
            return cachedBackendReport==null?
                new JSONObject().put("available",false).put("reason","inference_busy"):
                new JSONObject(cachedBackendReport.toString()).put("cached_during_inference",true);
        }
        try{
            String raw=nativeBackendReport();
            if(raw==null)return new JSONObject().put("available",false).put("reason","native_runtime_busy");
            org.json.JSONArray devices=new org.json.JSONArray();
            JSONObject result=new JSONObject().put("available",true).put("devices",devices)
                .put("observed_at_ms",System.currentTimeMillis()).put("gpu_execution_verified",false);
            boolean vulkan=false;
            for(String line:raw.split("\\n")){
                String[] fields=line.split("\\|",-1);
                if(fields.length==3&&fields[0].equals("loaded")){
                    result.put("loaded_device",fields[1]).put("requested_offload_layers",Integer.parseInt(fields[2]));
                }else if(fields.length==7&&fields[0].equals("device")){
                    int type=Integer.parseInt(fields[4]);
                    devices.put(new JSONObject().put("backend",fields[1]).put("device",fields[2])
                        .put("description",fields[3]).put("device_type",type)
                        .put("reported_free_bytes",Long.parseLong(fields[5]))
                        .put("reported_total_bytes",Long.parseLong(fields[6])));
                    vulkan|=fields[1].equals("Vulkan")&&(type==1||type==2);
                }
            }
            result.put("vulkan_gpu_registered",vulkan);
            cachedBackendReport=new JSONObject(result.toString());
            return result;
        }catch(Exception|LinkageError failure){
            return new JSONObject().put("available",false).put("reason",failure.getClass().getSimpleName());
        }
    }
    private static native byte[] nativeGenerate(byte[] systemText,String[] roles,byte[][] content,
        int maxTokens,int contextTokens,NativeStream stream,byte[][] references);
    interface Stream {
        void text(String text);
        default void context(int tokens,int omittedMessages){}
        default void context(int tokens,int omittedMessages,int omittedReferences){context(tokens,omittedMessages);}
    }
    // Methods are invoked by JNI and explicitly retained by the release shrinker.
    static final class NativeStream {
        final AssistantOutput output=new AssistantOutput();
        final Stream listener;
        int promptTokens,omittedMessages,omittedReferences,pieces;
        long firstPieceNanos,lastPieceNanos,firstVisibleNanos;
        NativeStream(Stream listener){this.listener=listener;}
        public void onStart(boolean thinking,int tokens,int omitted,int dropped){
            promptTokens=tokens;
            omittedMessages=omitted;omittedReferences=dropped;
            output.initialThinking(thinking);
            if(listener!=null)listener.context(tokens,omitted,dropped);
        }
        public void onToken(byte[] bytes){
            lastPieceNanos=System.nanoTime();
            if(pieces++==0)firstPieceNanos=lastPieceNanos;
            String text=output.append(bytes);
            if(firstVisibleNanos==0 && !text.isBlank())firstVisibleNanos=lastPieceNanos;
            if(listener!=null)listener.text(text);
        }
    }
    private static native void nativeCancel();
    private static native void nativeResetCancel();
    static void cancel(InferenceGate.Request request){GATE.cancel(request);}
    static boolean inferenceBusy(){return GATE.busy();}
    private static native void nativeUnload();

    static JSONObject status(Context context) throws Exception {
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        File file=new File(new File(context.getFilesDir(),"models"),profile.file);
        return new JSONObject()
            .put("ok",true)
            .put("platform","android_phone")
            .put("inference_backend","llama_cpp_jni")
            .put("native_library_loaded",LIBRARY_LOADED)
            .put("inference_active",GATE.busy())
            .put("model_bundled_in_apk",hasPackagedModel(context,profile))
            .put("model_distribution",profile.externalModelPack?"owner_import":"bundled")
            .put("model_private_file_present",file.isFile()&&file.length()==profile.bytes)
            .put("adapter_private_file_present",profile.adapterFile.isEmpty()||
                new File(file.getParentFile(),profile.adapterFile).length()==profile.adapterBytes)
            .put("model_name",profile.file)
            .put("model_context_tokens",profile.contextTokens)
            .put("weight_precision",profile.precision)
            .put("configured_backend",!profile.backendDevice.isEmpty()?profile.backendDevice:
                ControlAssistantPreferences.vulkanLayers(context,profile)>0?"Vulkan":"CPU")
            .put("configured_offload_layers",ControlAssistantPreferences.vulkanLayers(context,profile))
            .put("signed_max_vulkan_layers",profile.maxVulkanLayers)
            .put("mapped_no_repack",profile.mappedNoRepack)
            .put("last_vulkan_probe",lastVulkanProbe==null?JSONObject.NULL:lastVulkanProbe)
            .put("native_backend_report",runtimeBackends())
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
    private static boolean ensureLoaded(Context context,InferenceGate.Request request) {
        synchronized(LOCK) {
            if(!LIBRARY_LOADED){lastFailure="native_library_missing";return false;}
            try{
                if(modelReady&&nativeReady())return true;
                OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
                File folder=new File(context.getFilesDir(),"models");
                if(!folder.isDirectory()&&!folder.mkdirs()){
                    lastFailure="private_model_storage_unavailable";return false;
                }
                File file=stageArtifact(context,folder,profile.file,profile.bytes,profile.sha256,request,!profile.externalModelPack);
                if(request.isCancelled())throw new InterruptedException("user_cancelled");
                int layers=ControlAssistantPreferences.vulkanLayers(context,profile);
                String backend=profile.backendDevice.isEmpty()&&layers>0?"Vulkan":profile.backendDevice;
                if(profile.adapterFile.isEmpty()&&backend.isEmpty()&&!profile.mappedNoRepack){
                    modelReady=nativeLoad(file.getAbsolutePath());
                }else{
                    String adapter="";
                    if(!profile.adapterFile.isEmpty())
                        adapter=stageArtifact(context,folder,profile.adapterFile,profile.adapterBytes,
                            profile.adapterSha256,request,!profile.externalModelPack).getAbsolutePath();
                    if(request.isCancelled())throw new InterruptedException("user_cancelled");
                    modelReady=nativeLoadProfile(file.getAbsolutePath(),adapter,backend,layers,profile.mappedNoRepack);
                }
                lastFailure=modelReady?"":"native_model_load_failed";
                return modelReady;
            }catch(Exception|LinkageError exception){
                modelReady=false;
                lastFailure=exception instanceof java.io.FileNotFoundException?
                    ("model_pack_not_imported".equals(exception.getMessage())?"model_pack_not_imported":"model_missing_in_apk"):
                    exception.getClass().getSimpleName();
                return false;
            }
        }
    }
    private static boolean verifiedExisting(File file,long length,String sha,InferenceGate.Request request)throws Exception{
        if(!file.isFile()||file.length()!=length)return false;
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        byte[] buffer=new byte[256*1024];
        try(InputStream in=new FileInputStream(file)){
            for(int size;(size=in.read(buffer))!=-1;){
                if(request.isCancelled())throw new InterruptedException("user_cancelled");
                digest.update(buffer,0,size);
            }
        }
        return sha.equals(hex(digest.digest()));
    }
    private static File stageArtifact(Context context,File folder,String name,long length,String sha,
                                      InferenceGate.Request request,boolean bundled)throws Exception {
        File file=new File(folder,name);
        if(verifiedExisting(file,length,sha,request))return file;
        if(!bundled)throw new java.io.FileNotFoundException("model_pack_not_imported");
        try(InputStream input=context.getAssets().open("models/"+name,AssetManager.ACCESS_STREAMING)){
            return copyArtifact(folder,file,input,length,sha,request,null);
        }
    }
    private static File copyArtifact(File folder,File file,InputStream input,long length,String sha,
                                     InferenceGate.Request request,java.util.function.LongConsumer progress)throws Exception{
        if(folder.getUsableSpace()<length+(64L<<20))
            throw new java.io.IOException("insufficient_private_model_storage");
        File temporary=File.createTempFile("model-", ".partial",folder);
        try{
            long received=0,lastReport=0;
            MessageDigest digest=MessageDigest.getInstance("SHA-256");
            byte[] buffer=new byte[256*1024];
            try(FileOutputStream output=new FileOutputStream(temporary)){
                for(int size;(size=input.read(buffer))!=-1;){
                    if(request.isCancelled())throw new InterruptedException("user_cancelled");
                    received+=size;
                    if(received>length)throw new IllegalStateException("invalid_length");
                    output.write(buffer,0,size);
                    digest.update(buffer,0,size);
                    if(progress!=null&&(received-lastReport>=8L*1024*1024||received==length)){
                        lastReport=received;progress.accept(received);
                    }
                }
                output.getFD().sync();
            }
            if(request.isCancelled())throw new InterruptedException("user_cancelled");
            if(received!=length||!sha.equals(hex(digest.digest())))
                throw new IllegalStateException("model_checksum_mismatch");
            try(InputStream header=new FileInputStream(temporary)){
                if(header.read()!='G'||header.read()!='G'||header.read()!='U'||header.read()!='F')
                    throw new IllegalStateException("invalid_gguf_header");
            }
            android.system.Os.rename(temporary.getAbsolutePath(),file.getAbsolutePath());
            return file;
        }finally{temporary.delete();}
    }
    /** Only the signed APK profile determines the imported filename, length,
     * digest and adapter/base binding. No unsigned profile or arbitrary model
     * path can be supplied. The UI passes one explicit SAF document selection. */
    static void importOwnerModelArtifact(Context context,java.util.List<android.net.Uri> documents,boolean adapter,
                                        InferenceGate.Request request,java.util.function.LongConsumer progress)throws Exception{
        if(documents==null||documents.isEmpty())throw new SecurityException("document_provider_required");
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        if(!profile.externalModelPack||(adapter&&profile.adapterFile.isEmpty()))
            throw new SecurityException("signed_profile_does_not_allow_import");
        GATE.begin(request);
        try{
            synchronized(LOCK){
                File folder=new File(context.getFilesDir(),"models");
                if(!folder.isDirectory()&&!folder.mkdirs())throw new java.io.IOException("private_model_storage_unavailable");
                String name=adapter?profile.adapterFile:profile.file;
                String sha=adapter?profile.adapterSha256:profile.sha256;
                long length=adapter?profile.adapterBytes:profile.bytes;
                File file=new File(folder,name);
                if(verifiedExisting(file,length,sha,request)){if(progress!=null)progress.accept(length);return;}
                try(InputStream input=ModelPackDocuments.open(context,documents,name)){
                    copyArtifact(folder,file,input,length,sha,request,progress);
                }
                if(modelReady&&LIBRARY_LOADED){modelReady=false;nativeUnload();}
                lastFailure="";
            }
        }finally{GATE.end(request);}
    }
    private static String hex(byte[] bytes) {
        StringBuilder result=new StringBuilder(bytes.length*2);
        for(byte value:bytes)result.append(
            String.format(Locale.ROOT,"%02x",value&255));
        return result.toString();
    }
    static String generate(Context context,String userPrompt,InferenceGate.Request request) throws Exception {
        return generate(context,"General",Collections.singletonList(new AssistantConversation.Message(
            "single-turn","user",userPrompt,"completed")),null,request);
    }
    static String generate(Context context,String project,List<AssistantConversation.Message> messages,Stream listener,InferenceGate.Request request) throws Exception {
        OnDeviceModelProfile profile=OnDeviceModelProfile.read(context);
        if(messages==null||messages.isEmpty()||messages.size()>1000)
            throw new IllegalArgumentException("invalid_conversation_messages");
        String userPrompt=messages.get(messages.size()-1).text;
        if(userPrompt==null||userPrompt.isBlank()||userPrompt.length()>profile.inputChars)
            throw new IllegalArgumentException("prompt_length_invalid");
        GATE.begin(request);
        try{
            if(!LIBRARY_LOADED)throw new IllegalStateException("native_library_missing");
            long requestStarted=System.nanoTime();
            boolean warm=modelReady;
            int outputBudget=ControlAssistantPreferences.outputTokens(context,profile);
            new OnDeviceModelResources(context).contextTokens(profile,outputBudget,modelReady);
            if(!ensureLoaded(context,request))throw new IllegalStateException(lastFailure);
            if(request.isCancelled())throw new InterruptedException("user_cancelled");
            String recalled;
            try{recalled=ControlAssistantMemory.relevant(context,userPrompt,project);}
            catch(Exception unavailable){recalled="Local persistent memory unavailable for this turn.";}
            String guidance=ControlAssistantPreferences.promptGuidance(context);
            guidance+="\nRuntime identity: You are the assistant embedded in the native Asterion Control Android application. "
                +"This turn runs on this phone. Available operations are limited to the verified capability context. "
                +"An operation requires a typed request and a separate execution receipt; answer text never executes code. "
                +"Do not claim you are outside the app or that unverified tools are available. "
                +"Return the final answer in the user-visible channel; do not print internal reasoning delimiters.";
            guidance+="\nActive project: "+project+". This label scopes local memory; project source access requires verified retrieval evidence. "+
                "Reference blocks may be omitted to fit the active context. Do not assume complete retrieval.\n"+AssistantStructured.GUIDANCE+"\n"+AssistantSchedulePlan.GUIDANCE+"\n"+AssistantCalculator.GUIDANCE+"\n"+AssistantResearchPlan.GUIDANCE;
            java.util.ArrayList<byte[]> references=new java.util.ArrayList<>();
            try{
                String local=AssistantLocalContext.observe(context,userPrompt);
                if(!local.isEmpty())references.add(local.getBytes(StandardCharsets.UTF_8));
            }catch(Exception unavailable){references.add("Native status observation unavailable.".getBytes(StandardCharsets.UTF_8));}
            // Explicit receipt identity takes precedence over recent unrelated
            // observations. Keep each evidence block separate for native context
            // budgeting so one large record cannot discard all the others.
            java.util.HashSet<String> seenReceipts=new java.util.HashSet<>();
            for(int i=messages.size()-1;i>=0;i--){
                AssistantActionRecord record=messages.get(i).actionRecord;
                if(record!=null&&userPrompt.contains(record.requestId)&&seenReceipts.add(record.requestId)){
                    references.add(0,("Requested native receipt, reference only:\n"+record.evidence()).getBytes(StandardCharsets.UTF_8));
                    if(seenReceipts.size()>=2)break;
                }
            }
            for(int i=messages.size()-1;i>=0&&seenReceipts.size()<4;i--){
                AssistantActionRecord record=messages.get(i).actionRecord;
                if(record!=null&&seenReceipts.add(record.requestId))
                    references.add(("Historical native partner observation, not independent proof:\n"+record.evidence()).getBytes(StandardCharsets.UTF_8));
            }
            String capabilities=AssistantCapabilities.context(context,userPrompt,project);
            String requirements=AssistantRequirements.context(context,userPrompt,project);
            if(!recalled.isEmpty())references.add(("Owner-approved memories, reference only:\n"+recalled).getBytes(StandardCharsets.UTF_8));
            if(!capabilities.isEmpty())references.add(capabilities.getBytes(StandardCharsets.UTF_8));
            if(!requirements.isEmpty())references.add(requirements.getBytes(StandardCharsets.UTF_8));
            if(listener!=null){
                try{
                    String documents=ControlAssistantMemory.projectSourceContext(context,project,userPrompt,request);
                    if(!documents.isEmpty())references.add(documents.getBytes(StandardCharsets.UTF_8));
                }catch(InterruptedException cancelled){throw cancelled;}
                catch(Exception unavailable){references.add("Local project documents unavailable this turn.".getBytes(StandardCharsets.UTF_8));}
            }
            // Only local interactive/voice sessions receive past conversation text.
            // Remote WSS and scheduled single-turn inference have no history listener.
            if(listener!=null&&ControlAssistantPreferences.reuseHistory(context)){
                try{
                    String history=ControlAssistantMemory.conversationContext(context,userPrompt,project,messages,request);
                    if(!history.isEmpty())references.add(history.getBytes(StandardCharsets.UTF_8));
                }catch(InterruptedException cancelled){throw cancelled;}
                catch(Exception unavailable){references.add("Encrypted historical context unavailable this turn.".getBytes(StandardCharsets.UTF_8));}
            }
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
                outputBudget,contextBudget,stream,references.toArray(new byte[0][]));
            if(request.isCancelled())throw new InterruptedException("user_cancelled");
            if(output==null||output.length==0)throw new IllegalStateException("native_context_or_generation_failed");
            String result=stream.output.finish(output);
            if(result.isBlank())throw new IllegalStateException("no_visible_model_answer");
            result=AssistantCalculator.attachResult(result);
            long answerReady=System.nanoTime();
            if(stream.firstVisibleNanos==0)stream.firstVisibleNanos=answerReady;
            OnDeviceModelResources after=new OnDeviceModelResources(context);
            lastCompletedGeneration=new JSONObject()
                .put("base_sha256",profile.sha256)
                .put("adapter_sha256",profile.adapterSha256)
                .put("weight_precision",profile.precision)
                .put("kv_bits",profile.kvBits)
                .put("configured_backend",!profile.backendDevice.isEmpty()?profile.backendDevice:
                    ControlAssistantPreferences.vulkanLayers(context,profile)>0?"Vulkan":"CPU")
                .put("configured_offload_layers",ControlAssistantPreferences.vulkanLayers(context,profile))
                .put("mapped_no_repack",profile.mappedNoRepack)
                .put("model_already_loaded",warm)
                .put("context_tokens",contextBudget)
                .put("prompt_tokens",stream.promptTokens)
                .put("omitted_messages",stream.omittedMessages)
                .put("omitted_reference_blocks",stream.omittedReferences)
                .put("generated_token_pieces",stream.pieces)
                .put("request_to_first_visible_ms",(stream.firstVisibleNanos-requestStarted)/1_000_000)
                .put("request_total_ms",(answerReady-requestStarted)/1_000_000)
                .put("request_to_first_piece_ms",(stream.firstPieceNanos-requestStarted)/1_000_000)
                .put("inference_to_first_piece_ms",(stream.firstPieceNanos-inferenceStarted)/1_000_000)
                .put("decode_between_pieces_ms",(stream.lastPieceNanos-stream.firstPieceNanos)/1_000_000)
                .put("process_pss_kib_after",android.os.Debug.getPss())
                .put("available_bytes_before_context",resources.memory.availMem)
                .put("available_bytes_after",after.memory.availMem)
                .put("thermal_before",resources.thermalStatus)
                .put("thermal_after",after.thermalStatus);
            return result;
        }finally{GATE.end(request);}
    }
}
