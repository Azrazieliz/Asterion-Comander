package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Owner's local assistant response preferences, deliberately separate from
 * OS/device permissions, signed tool policies and credential authorization.
 * Never posts settings to a remote provider or stores them in bridge receipts.
 */
final class ControlAssistantPreferences {
    private static final String STORE="asterion_assistant_owner_preferences_v1";
    private static final String EFFORT="reasoning_effort";
    private static final String GUIDANCE="owner_response_guidance";
    private static final String SAVE_HISTORY="encrypted_local_chat_history_enabled";
    private ControlAssistantPreferences(){}

    private static SharedPreferences prefs(Context ctx){
        return ctx.getSharedPreferences(STORE,Context.MODE_PRIVATE);
    }
    static String effort(Context ctx){
        String value=prefs(ctx).getString(EFFORT,"balanced");
        if("fast".equals(value)||"balanced".equals(value)||"deep".equals(value))
            return value;
        return "balanced";
    }
    static String guidance(Context ctx){
        String value=prefs(ctx).getString(GUIDANCE,"");
        return value==null?"":value;
    }
    static boolean saveHistory(Context ctx){
        return prefs(ctx).getBoolean(SAVE_HISTORY,true);
    }
    static void save(Context ctx,String effort,String guidance){
        save(ctx,effort,guidance,saveHistory(ctx));
    }
    static void save(Context ctx,String effort,String guidance,boolean keepHistory){
        if(!"fast".equals(effort)&&!"balanced".equals(effort)&&!"deep".equals(effort))
            throw new IllegalArgumentException("invalid_reasoning_effort");
        if(guidance==null||guidance.length()>2000)
            throw new IllegalArgumentException("owner_guidance_too_large");
        if(!prefs(ctx).edit().putString(EFFORT,effort)
                .putString(GUIDANCE,guidance)
                .putBoolean(SAVE_HISTORY,keepHistory).commit())
            throw new IllegalStateException("local_ai_preferences_not_saved");
    }
    static int outputTokens(Context ctx,OnDeviceModelProfile profile){
        switch(effort(ctx)){
            case "fast":return Math.min(384,profile.outputTokens);
            case "balanced":return Math.min(768,profile.outputTokens);
            default:return profile.outputTokens;
        }
    }
    static String promptGuidance(Context ctx){
        String user=guidance(ctx);
        return "Owner-selected reasoning effort: "+effort(ctx)+
            ". Ordinary adult, fictional, artistic, controversial, technical, "+
            "academic and political discussions must not receive automatic "+
            "blanket topic refusals. Respect user-directed style and creatively "+
            "answer legitimate requests. Device access, credentials, external "+
            "side effects and real-world harmful actions remain subject to "+
            "separate authorization and security controls. "+
            (user.isBlank()?"":"\nOwner-defined response guidance:\n"+user);
    }
}
