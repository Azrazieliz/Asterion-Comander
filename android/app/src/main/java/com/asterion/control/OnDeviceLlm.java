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

/**
 * In-process, on-device GGUF inference. No Windows AI server and no cloud API.
 * Model weights must be bundled in this signed APK, independently SHA-verified
 * and copied into private model storage before loading from mmap.
 * A missing library/weight is a hard error, never a success placeholder.
 */
final class OnDeviceLlm {
    static final String MODEL_ASSET="models/Qwen3-0.6B-Q4_K_M.gguf";
    static final String MODEL_FILE="Qwen3-0.6B-Q4_K_M.gguf";
    static final long MODEL_BYTES=484220288L;
    static final String MODEL_SHA256=
        "373db06783953f0981572d008f183eb2167b93304f5adbf7c4ce6ed6a91ee437";
    static final String MODEL_SOURCE="tauqir02/Qwen3-0.6B-GGUF";
    private static final Object LOCK=new Object();
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
    private static native byte[] nativeGenerate(String prompt,int maxTokens);
    private static native void nativeUnload();

    static JSONObject status(Context context) throws Exception {
        File file=new File(new File(context.getFilesDir(),"models"),MODEL_FILE);
        return new JSONObject()
            .put("ok",true)
            .put("platform","android_phone")
            .put("inference_backend","llama_cpp_jni")
            .put("native_library_loaded",LIBRARY_LOADED)
            .put("model_bundled_in_apk",hasPackagedModel(context))
            .put("model_private_file_bytes",file.isFile()?file.length():0L)
            .put("model_sha_verified",modelReady && LIBRARY_LOADED)
            .put("model_loaded",LIBRARY_LOADED && modelReady && nativeReady())
            .put("external_server_required",false)
            .put("paid_cloud_api_required",false)
            .put("model_source",MODEL_SOURCE)
            .put("last_failure_code",lastFailure);
    }
    private static boolean hasPackagedModel(Context c) {
        try (android.content.res.AssetFileDescriptor afd =
             c.getAssets().openFd(MODEL_ASSET)) {
            return afd.getLength()==MODEL_BYTES;
        }catch(Exception ignored){
            return false;
        }
    }
    static boolean ensureLoaded(Context context) {
        synchronized(LOCK) {
            if(!LIBRARY_LOADED){lastFailure="native_library_missing";return false;}
            try{
                if(modelReady&&nativeReady())return true;
                File folder=new File(context.getFilesDir(),"models");
                if(!folder.isDirectory()&&!folder.mkdirs()){
                    lastFailure="private_model_storage_unavailable";return false;
                }
                File file=new File(folder,MODEL_FILE);
                if(!verified(file)){
                    File temp=new File(folder,MODEL_FILE+".partial");
                    if(temp.exists()&&!temp.delete()){
                        lastFailure="partial_model_cleanup_failed";return false;
                    }
                    MessageDigest digest=MessageDigest.getInstance("SHA-256");
                    long read=0;
                    byte[] buffer=new byte[256*1024];
                    try (InputStream from=context.getAssets().open(MODEL_ASSET,
                         AssetManager.ACCESS_STREAMING);
                         FileOutputStream out=new FileOutputStream(temp)) {
                        for(int n;(n=from.read(buffer))!=-1;){
                            read+=n;
                            if(read>MODEL_BYTES)throw new IllegalStateException("invalid_length");
                            out.write(buffer,0,n);
                            digest.update(buffer,0,n);
                        }
                        out.getFD().sync();
                    }
                    if(read!=MODEL_BYTES||!MODEL_SHA256.equals(hex(digest.digest())))
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
    private static boolean verified(File file) throws Exception {
        if(!file.isFile()||file.length()!=MODEL_BYTES)return false;
        MessageDigest md=MessageDigest.getInstance("SHA-256");
        byte[] buf=new byte[262144];
        try(FileInputStream in=new FileInputStream(file)){
            for(int n;(n=in.read(buf))!=-1;)md.update(buf,0,n);
        }
        return MODEL_SHA256.equals(hex(md.digest()));
    }
    private static String hex(byte[] bytes) {
        StringBuilder result=new StringBuilder(bytes.length*2);
        for(byte value:bytes)result.append(
            String.format(Locale.ROOT,"%02x",value&255));
        return result.toString();
    }
    static String generate(Context context,String userPrompt) throws Exception {
        if(userPrompt==null||userPrompt.trim().isEmpty()||userPrompt.length()>1800)
            throw new IllegalArgumentException("prompt_length_invalid");
        if(!ensureLoaded(context))
            throw new IllegalStateException(lastFailure);
        // Qwen3 ChatML. A bounded context and no tool/network permissions.
        String prompt="<|im_start|>system\n"+
            "You are Asterion Control's locally hosted phone assistant. "+
            "Give concise, accurate answers. Never claim an app was modified, "+
            "a command ran, or a VPN connected unless you receive evidence. "+
            "You cannot autonomously operate other applications. /no_think"+
            "<|im_end|>\n<|im_start|>user\n"+
            userPrompt.trim()+"<|im_end|>\n<|im_start|>assistant\n";
        byte[] output=nativeGenerate(prompt,192);
        if(output==null||output.length==0)
            throw new IllegalStateException("no_generated_tokens");
        return new String(output,StandardCharsets.UTF_8).trim();
    }
}
