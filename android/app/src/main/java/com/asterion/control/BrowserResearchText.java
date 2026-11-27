package com.asterion.control;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Browser-owned captured text; shared project store owns persistence. */
final class BrowserResearchText {
    static final String PROJECT="Browser Research";
    static final int LIMIT=32000;
    static String sha(String text)throws Exception{
        StringBuilder out=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)))
            out.append(String.format(Locale.ROOT,"%02x",b&255));
        return out.toString();
    }
    static String capture(String safeUrl,String title,String text,long time)throws Exception{
        if(safeUrl==null||safeUrl.length()>1200||safeUrl.isBlank()||title==null||
            title.length()>160||text==null||text.isBlank()||text.length()>LIMIT||time<=0)
            throw new IllegalArgumentException("Invalid browser capture");
        return "Browser source capture\nURL (query/fragment removed): "+safeUrl+"\nTitle: "+title+
            "\nCaptured UTC: "+java.time.Instant.ofEpochMilli(time)+"\nVisible text SHA-256: "+sha(text)+
            "\nExtraction: rendered DOM; maximum "+LIMIT+" UTF-16 characters. Content is observed, not verified truth.\n\n"+text;
    }
    static String excerpt(String text,String term){
        if(term==null||term.isBlank()||term.length()>120||term.codePoints().anyMatch(Character::isISOControl))
            throw new IllegalArgumentException("Invalid comparison term");
        // Compare captured content, not URL/title/timestamp/hash metadata.
        int boundary=text.startsWith("Browser source capture\n")?text.indexOf("\n\n"): -1;
        int contentStart=boundary<0?0:boundary+2;
        Matcher match=Pattern.compile(Pattern.quote(term.strip()),Pattern.CASE_INSENSITIVE|Pattern.UNICODE_CASE).matcher(text);
        match.region(contentStart,text.length());
        if(!match.find())return "No literal match in captured text.";
        int start=Math.max(contentStart,match.start()-120),end=Math.min(text.length(),match.end()+120);
        if(start>0&&Character.isLowSurrogate(text.charAt(start)))start--;
        if(end<text.length()&&Character.isHighSurrogate(text.charAt(end-1)))end++;
        return "Exact record UTF-16 ["+start+","+end+"):\n"+text.substring(start,end);
    }
}
