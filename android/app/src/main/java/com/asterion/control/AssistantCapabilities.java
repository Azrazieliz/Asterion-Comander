package com.asterion.control;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;

/** Live discovery through the original signer-pinned specialist bridge, no parallel registry. */
final class AssistantCapabilities {
    private AssistantCapabilities(){}
    static String context(Context context,String query,String project){
        try{
            JSONArray apps=AppBridge.list(context).getJSONArray("apps");
            String terms=(query+" "+project).toLowerCase(java.util.Locale.ROOT);
            java.util.ArrayList<JSONObject> ranked=new java.util.ArrayList<>();
            for(int i=0;i<apps.length();i++){
                JSONObject app=apps.getJSONObject(i);
                if(app.optBoolean("approved"))ranked.add(app);
            }
            ranked.sort((a,b)->Integer.compare(rank(b,terms),rank(a,terms)));
            JSONArray packs=new JSONArray();
            int attempted=0,omitted=0;
            for(JSONObject app:ranked){
                if(attempted>=4){omitted++;continue;}
                // Do not block ordinary conversation on unrelated Binder calls.
                if(rank(app,terms)==0&&!terms.matches("(?s).*\\b(apps|applications|capabilities|tools|integrations|outils)\\b.*")){omitted++;continue;}
                attempted++;
                String pkg=app.getString("package");
                JSONObject entry=new JSONObject().put("package",pkg).put("name",app.optString("name"));
                try{
                    JSONObject verified=AppBridge.capabilities(context,pkg);
                    if(verified.optBoolean("ok")&&verified.optBoolean("owner_approved")){
                        JSONArray offered=verified.getJSONArray("actions"),selected=new JSONArray();
                        for(int i=0;i<offered.length()&&i<12;i++)selected.put(offered.getJSONObject(i));
                        entry.put("actions",selected).put("omitted_actions",offered.length()-selected.length());
                    }else entry.put("unavailable",verified.optString("reason","not_verified"));
                }catch(Exception unavailable){entry.put("unavailable","provider_unavailable");}
                if(packs.toString().length()+entry.toString().length()>3200){omitted++;continue;}
                packs.put(entry);
            }
            return "Live Android signed capability discovery, not execution: "+packs+
                "\nApproved apps omitted from this turn: "+omitted+". Only advertised actions may be proposed. "+
                "A proposal is ONE JSON object fenced as asterion_action, with exactly package, action, payload. "+
                "Owner review and signed provider validation are required. No execution from answer text.";
        }catch(Exception unavailable){return "Live Android capability discovery unavailable for this turn. Do not invent actions.";}
    }
    private static int rank(JSONObject app,String terms){
        String name=app.optString("name").toLowerCase(java.util.Locale.ROOT);
        String pkg=app.optString("package").toLowerCase(java.util.Locale.ROOT);
        int score=terms.contains(pkg)?10:0;
        for(String word:name.split("[^\\p{L}\\p{N}]+")){
            if(word.length()>2&&!word.equals("asterion")&&terms.matches("(?s).*\\b"+java.util.regex.Pattern.quote(word)+"\\b.*"))score+=3;
        }
        return score;
    }
    static JSONObject proposal(String response)throws Exception{
        String raw=AssistantStructured.singleBlock(response,"asterion_action");
        if(raw==null||raw.length()>5000)return null;
        JSONObject object=new JSONObject(raw);
        if(object.length()!=3||!(object.opt("package") instanceof String)||!(object.opt("action") instanceof String)||
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
