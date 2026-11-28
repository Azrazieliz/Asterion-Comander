package com.asterion.control;

import android.content.Context;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

final class OnDeviceVisionProfile {
    static final class Artifact {
        final String file,sha;
        final long bytes;
        Artifact(JSONObject raw)throws Exception{
            file=raw.getString("file");sha=raw.getString("sha256");bytes=raw.getLong("bytes");
            if(!file.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,119}\\.gguf")||!sha.matches("[0-9a-f]{64}")||
                bytes<1048576||bytes>2000000000L)throw new IllegalArgumentException("invalid_vision_artifact");
        }
    }
    final Artifact base,projector;
    final String source;
    final boolean external;
    final int contextTokens,outputTokens,maxSide;
    final long workspace;
    private OnDeviceVisionProfile(JSONObject j)throws Exception{
        if(j.getInt("schema_version")!=1)throw new IllegalArgumentException("invalid_vision_schema");
        String distribution=j.getString("distribution");
        if(!"owner_import".equals(distribution)&&!"bundled".equals(distribution))
            throw new IllegalArgumentException("invalid_vision_distribution");
        external="owner_import".equals(distribution);
        base=new Artifact(j.getJSONObject("base"));projector=new Artifact(j.getJSONObject("projector"));
        if(base.file.equals(projector.file)||!base.sha.equals(j.getJSONObject("projector").getString("base_sha256")))
            throw new IllegalArgumentException("vision_projector_identity_mismatch");
        source=j.getString("source");
        contextTokens=j.getInt("context_tokens");outputTokens=j.getInt("max_new_tokens");
        maxSide=j.getInt("max_image_side");workspace=j.getLong("workspace_bytes");
        if(source.isBlank()||source.length()>200||contextTokens<512||contextTokens>4096||
            outputTokens<1||outputTokens>1024||outputTokens+128>contextTokens||maxSide<128||maxSide>1024||
            workspace<(256L<<20)||workspace>(4L<<30))throw new IllegalArgumentException("invalid_vision_budget");
    }
    static OnDeviceVisionProfile read(Context c)throws Exception{
        try(InputStream in=c.getAssets().open("models/control-vision.json")){
            byte[] raw=in.readNBytes(16385);
            if(raw.length==0||raw.length>16384)throw new IllegalArgumentException("invalid_vision_manifest");
            OnDeviceVisionProfile visual=new OnDeviceVisionProfile(new JSONObject(new String(raw,StandardCharsets.UTF_8)));
            OnDeviceModelProfile text=OnDeviceModelProfile.read(c);
            if(visual.base.file.equals(text.file)||visual.projector.file.equals(text.file)||
               visual.base.file.equals(text.adapterFile)||visual.projector.file.equals(text.adapterFile))
                throw new IllegalArgumentException("visual_text_artifact_collision");
            return visual;
        }
    }
}
