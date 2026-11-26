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
    final String asset,file,sha256,source,systemPrefix,userPrefix,assistantPrefix,systemText;
    final long bytes;
    final int inputChars,outputTokens,contextTokens;
    private OnDeviceModelProfile(JSONObject j) throws Exception {
        file=j.getString("file");
        if(!NAME.matcher(file).matches())throw new IllegalArgumentException("invalid_model_filename");
        asset="models/"+file;
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
        JSONObject format=j.getJSONObject("chat_format");
        systemPrefix=field(format,"system_prefix");
        userPrefix=field(format,"user_prefix");
        assistantPrefix=field(format,"assistant_prefix");
        systemText=j.getString("system_text");
        if(systemText.length()>4096 || systemText.isBlank())
            throw new IllegalArgumentException("invalid_system_text");
    }
    private static String field(JSONObject object,String key)throws Exception{
        String value=object.getString(key);
        if(value.isEmpty()||value.length()>512)throw new IllegalArgumentException("invalid_chat_format");
        return value;
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
    String prompt(String user) {
        return systemPrefix+systemText+userPrefix+user.trim()+assistantPrefix;
    }
}
