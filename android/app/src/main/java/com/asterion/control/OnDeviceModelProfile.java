package com.asterion.control;

import android.content.Context;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.regex.Pattern;

/** Immutable signed-APK model metadata. Never infer safety or performance from a model name. */
final class OnDeviceModelProfile {
    private static final Pattern NAME=Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]{0,119}\\.gguf");
    private static final Pattern SHA=Pattern.compile("[0-9a-f]{64}");
    final String asset,file,sha256,source,systemText;
    final long bytes;
    final int inputChars,outputTokens,contextTokens;
    final String precision,backendDevice,adapterFile,adapterSha256;
    final int offloadLayers,kvBits;
    final long adapterBytes,residentBytes,workspaceBytes,kvBytesPerToken;
    final boolean allowSmallerContext,externalModelPack;
    private OnDeviceModelProfile(JSONObject j) throws Exception {
        file=j.getString("file");
        if(!NAME.matcher(file).matches())throw new IllegalArgumentException("invalid_model_filename");
        asset="models/"+file;
        String distribution=j.optString("distribution","bundled");
        if(!"bundled".equals(distribution)&&!"owner_import".equals(distribution))
            throw new IllegalArgumentException("invalid_model_distribution");
        externalModelPack="owner_import".equals(distribution);
        bytes=j.getLong("bytes");
        if(bytes<1024*1024L||bytes>15_000_000_000L)throw new IllegalArgumentException("invalid_model_size");
        sha256=j.getString("sha256").toLowerCase(Locale.ROOT);
        if(!SHA.matcher(sha256).matches())throw new IllegalArgumentException("invalid_model_digest");
        source=j.getString("source");
        if(source.isBlank()||source.length()>200)throw new IllegalArgumentException("invalid_model_provenance");
        inputChars=j.getInt("max_input_chars");
        outputTokens=j.getInt("max_new_tokens");
        contextTokens=j.getInt("context_tokens");
        if(inputChars<1801||inputChars>98304||outputTokens<193||outputTokens>2048
                ||contextTokens<512||contextTokens>16384
                ||contextTokens<outputTokens+256)
            throw new IllegalArgumentException("invalid_context_budget");
        precision=j.optString("weight_precision","unspecified");
        if(!precision.matches("[A-Za-z0-9._-]{1,32}"))
            throw new IllegalArgumentException("invalid_weight_precision");
        backendDevice=j.optString("backend_device","");
        offloadLayers=j.optInt("offload_layers",0);
        if(!backendDevice.matches("[A-Za-z0-9._-]{0,64}") || offloadLayers<0 ||
                offloadLayers>256 || (offloadLayers==0)!=backendDevice.isEmpty())
            throw new IllegalArgumentException("invalid_backend_profile");
        kvBits=j.optInt("kv_precision_bits",16);
        if(kvBits!=8&&kvBits!=16)throw new IllegalArgumentException("invalid_kv_precision");
        JSONObject memory=j.optJSONObject("memory_budget");
        residentBytes=boundBytes(memory,"resident_weight_bytes",bytes);
        workspaceBytes=boundBytes(memory,"workspace_bytes",512L<<20);
        kvBytesPerToken=boundBytes(memory,"kv_bytes_per_token",256L<<10);
        allowSmallerContext=j.optBoolean("allow_smaller_context",false);
        JSONObject adapter=j.optJSONObject("adapter");
        adapterFile=adapter==null?"":adapter.getString("file");
        adapterSha256=adapter==null?"":adapter.getString("sha256");
        adapterBytes=adapter==null?0:boundBytes(adapter,"bytes",0);
        if(j.has("adapter")&&(adapter==null||!NAME.matcher(adapterFile).matches()||
                adapterFile.equals(file)||!SHA.matcher(adapterSha256).matches()||
                adapterBytes==0||!sha256.equals(adapter.getString("base_sha256"))))
            throw new IllegalArgumentException("invalid_adapter_identity");
        // Role formatting comes from the verified GGUF tokenizer metadata
        // through llama_chat_apply_template, never from a model-name switch.
        systemText=j.getString("system_text");
        if(systemText.length()>4096 || systemText.isBlank())
            throw new IllegalArgumentException("invalid_system_text");
    }
    private static long boundBytes(JSONObject value,String key,long fallback) {
        long bytes=value==null?fallback:value.optLong(key,fallback);
        if(bytes<0||bytes>(64L<<30))throw new IllegalArgumentException("invalid_memory_estimate");
        return bytes;
    }
    static OnDeviceModelProfile read(Context context)throws Exception{
        try(InputStream in=context.getAssets().open("models/control-model.json")){
            byte[] raw=new byte[16385];
            int n=0,r;
            while(n<raw.length && (r=in.read(raw,n,raw.length-n))!=-1)n+=r;
            if(n>=raw.length||n==0)throw new IllegalArgumentException("invalid_model_manifest_size");
            return new OnDeviceModelProfile(new JSONObject(
                new String(raw,0,n,StandardCharsets.UTF_8)));
        }
    }
    /** Format is supplied by the signed manifest, not guessed from vendor or weight filename. */
    String systemInstructions(String ownerInstructions) {
        return systemText+"\n"+ownerInstructions;
    }
}
