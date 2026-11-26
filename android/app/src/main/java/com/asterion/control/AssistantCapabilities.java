package com.asterion.control;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

/** Live discovery through the original signer-pinned specialist bridge, no parallel registry. */
final class AssistantCapabilities {
    private AssistantCapabilities(){}
    static String context(Context context)throws Exception{
        JSONArray apps=AppBridge.list(context).getJSONArray("apps");
        JSONArray packs=new JSONArray();
        for(int i=0;i<apps.length()&&packs.length()<6;i++){
            JSONObject app=apps.getJSONObject(i);
            JSONObject entry=new JSONObject().put("package",app.getString("package"))
                .put("name",app.optString("name")).put("installed",true)
                .put("owner_approved",app.optBoolean("approved"));
            if(app.optBoolean("approved")){
                JSONObject capability=AppBridge.capabilities(context,app.getString("package"));
                entry.put("verified_capability_pack",capability);
            }
            packs.put(entry);
        }
        return "Live Android capability discovery (not source-code availability): "+packs+
            "\nFor an operation offered in a verified capability pack, you may propose ONE JSON object in " +
            "a fenced asterion_action block with exactly package, action, payload. It is a proposal, not execution. "+
            "The native owner authorization screen and signed provider validate it before execution. "+
            "Do not invent a capability if the list is empty. Browser, memory and model settings are available in the app navigation.";
    }
    static JSONObject proposal(String response)throws Exception{
        String marker="```asterion_action";
        int start=response.indexOf(marker);
        if(start<0)return null;
        int end=response.indexOf("```",start+marker.length());
        if(end<0||response.indexOf(marker,start+marker.length())>=0)return null;
        String raw=response.substring(start+marker.length(),end).trim();
        if(raw.length()>5000)return null;
        JSONObject object=new JSONObject(raw);
        if(object.length()!=3||!object.has("package")||!object.has("action")||
            !(object.opt("payload") instanceof JSONObject))return null;
        return object;
    }
    static void validate(Context context,JSONObject proposal)throws Exception{
        JSONObject pack=AppBridge.capabilities(context,proposal.getString("package"));
        if(!pack.optBoolean("ok")||!pack.optBoolean("owner_approved"))throw new SecurityException("capability_not_verified");
        JSONArray actions=pack.getJSONArray("actions");
        for(int i=0;i<actions.length();i++)if(actions.getJSONObject(i).getString("name").equals(proposal.getString("action")))return;
        throw new SecurityException("action_not_advertised");
    }
}
