package com.asterion.control;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Pull exact passages from the existing pinned requirements index's signed Android projection. */
final class AssistantRequirements {
    private static final Pattern WORD=Pattern.compile("[\\p{L}\\p{N}][\\p{L}\\p{N}_-]{2,}");
    private static final int MAX_ASSET=512*1024;
    private static final int MAX_CONTEXT_CHARS=3600;
    private static volatile JSONObject cached;

    private AssistantRequirements(){}

    private static JSONObject index(Context context)throws Exception{
        JSONObject previous=cached;
        if(previous!=null)return previous;
        try(InputStream input=context.getAssets().open("models/control-requirements.json")){
            byte[] bytes=input.readNBytes(MAX_ASSET+1);
            if(bytes.length>MAX_ASSET)throw new IllegalStateException("requirements_asset_oversized");
            JSONObject parsed=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
            if(!"asterion.control.android-requirements/1".equals(parsed.getString("schema")))
                throw new IllegalStateException("unknown_requirements_asset_schema");
            JSONArray records=parsed.getJSONArray("records");
            if(records.length()==0)throw new IllegalStateException("empty_requirements_asset");
            for(int i=0;i<records.length();i++){
                JSONObject record=records.getJSONObject(i);
                byte[] digest=MessageDigest.getInstance("SHA-256")
                    .digest(record.getString("text").getBytes(StandardCharsets.UTF_8));
                StringBuilder hex=new StringBuilder();
                for(byte value:digest)hex.append(String.format(Locale.ROOT,"%02x",value&255));
                if(!record.getString("span_sha256").contentEquals(hex))
                    throw new IllegalStateException("requirements_passage_mismatch");
            }
            cached=parsed;
            return parsed;
        }
    }

    private static Set<String> terms(String value){
        Set<String> out=new HashSet<>();
        Matcher matcher=WORD.matcher(value.toLowerCase(Locale.ROOT));
        while(matcher.find()&&out.size()<128)out.add(matcher.group());
        return out;
    }

    static String context(Context context,String query,String project){
        try{
            JSONObject index=index(context);
            Set<String> words=terms(query+" "+project);
            JSONArray records=index.getJSONArray("records");
            ArrayList<Scored> ranked=new ArrayList<>();
            for(int i=0;i<records.length();i++){
                JSONObject row=records.getJSONObject(i);
                Set<String> headings=terms(row.getString("topic")+" "+row.getString("id"));
                Set<String> body=terms(row.getString("text"));
                int score=0;
                for(String word:words){
                    if(headings.contains(word))score+=5;
                    else if(body.contains(word))score++;
                }
                if(score>0)ranked.add(new Scored(row,score));
            }
            ranked.sort((a,b)->Integer.compare(b.score,a.score));
            StringBuilder value=new StringBuilder("Exact passages from the signed Control requirements index. Open decisions are unresolved. Do not infer specialist installation or execution from a requirement.\n");
            value.append("Index ").append(index.getString("index_sha256")).append('\n');
            value.append("Open IDs ").append(index.getJSONArray("unresolved_ids")).append('\n');
            value.append("Potential conflicts ").append(index.getJSONObject("potential_conflicts")).append('\n');
            int included=0;
            for(Scored entry:ranked){
                JSONObject row=entry.row;
                String passage="["+row.getString("id")+" "+row.getString("status")+" "+
                    row.getString("path")+":"+row.getInt("start_line")+"-"+row.getInt("end_line")+"]\n"+
                    row.getString("text")+"\n";
                if(value.length()+passage.length()>MAX_CONTEXT_CHARS)continue;
                value.append(passage);
                if(++included==4)break;
            }
            return value.toString();
        }catch(Exception unavailable){
            return "Canonical Control requirement passages unavailable for this turn.";
        }
    }

    private static final class Scored{
        final JSONObject row;
        final int score;
        Scored(JSONObject row,int score){this.row=row;this.score=score;}
    }
}
