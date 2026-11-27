package com.asterion.control;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Bounded, exact local memory retrieval. Excerpts always identify the original record and span. */
final class AssistantMemorySearch {
    private static final Pattern WORD=Pattern.compile("[\\p{L}\\p{N}]{2,}");
    private static final Set<String> COMMON=Set.of("the","and","for","with","that","this","from","have",
        "are","was","what","how","can","you","your","please","does","about","dans","avec","pour",
        "les","des","une","est","que","qui","sur","mon","mes","vos","nous","vous");
    private static final int LIMIT=4500, PASSAGE=1600, OVERLAP=200;
    static final class Hit {
        final String id,project,source,excerpt;
        final int start,end,length,score;
        final long created;
        Hit(String id,String project,String source,String content,int start,int end,int score,long created){
            this.id=id;this.project=project;this.source=source;this.excerpt=content.substring(start,end);
            this.start=start;this.end=end;this.length=content.length();this.score=score;this.created=created;
        }
        String render(){
            return "Memory ID: "+id+" | Project: "+project+" | Source: "+source+
                " | "+(start==0&&end==length?"Complete record":"Exact excerpt UTF-16 ["+start+","+end+") of "+length)+
                "\n"+excerpt+"\n---\n";
        }
    }
    private final Set<String> query=new HashSet<>();
    private final ArrayList<Hit> best=new ArrayList<>();
    private static final Comparator<Hit> ORDER=Comparator.comparingInt((Hit h)->h.score).reversed()
        .thenComparing(Comparator.comparingLong((Hit h)->h.created).reversed())
        .thenComparing(h->h.id).thenComparingInt(h->h.start);
    AssistantMemorySearch(String text){
        Matcher matcher=WORD.matcher(text.toLowerCase(Locale.ROOT));
        while(matcher.find()&&query.size()<128)
            if(!COMMON.contains(matcher.group()))query.add(matcher.group());
    }
    boolean empty(){return query.isEmpty();}
    private int score(String value){
        HashSet<String> matched=new HashSet<>();
        Matcher matcher=WORD.matcher(value.toLowerCase(Locale.ROOT));
        while(matcher.find())if(query.contains(matcher.group()))matched.add(matcher.group());
        return matched.size();
    }
    private static int safeEnd(String value,int end){
        if(end>0&&end<value.length()&&Character.isHighSurrogate(value.charAt(end-1))
            &&Character.isLowSurrogate(value.charAt(end)))return end-1;
        return end;
    }
    void add(String id,String project,String source,String content,long created,boolean exactProject){
        if(empty()||content.isEmpty())return;
        int meta=score(source);
        Hit winner=null;
        for(int start=0;start<content.length();){
            int end=safeEnd(content,Math.min(content.length(),start+PASSAGE));
            int matches=score(content.substring(start,end));
            if(matches>0||meta>0){
                int rank=4*matches+2*meta+(exactProject?1:0);
                Hit candidate=new Hit(id,project,source,content,start,end,rank,created);
                if(winner==null||ORDER.compare(candidate,winner)<0)winner=candidate;
            }
            if(end==content.length())break;
            start=safeEnd(content,end-OVERLAP);
        }
        if(winner!=null){
            best.add(winner);best.sort(ORDER);
            if(best.size()>20)best.remove(best.size()-1);
        }
    }
    String render(){
        StringBuilder out=new StringBuilder();int count=0;
        for(Hit hit:best){
            if(count>=5)break;
            String value=hit.render();
            if(out.length()+value.length()>LIMIT)continue;
            out.append(value);count++;
        }
        return out.toString();
    }
}
