package com.asterion.control;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.charset.CodingErrorAction;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Locale;
import java.util.List;

/** Exact text sources, not OCR, Office extraction or a vector-model substitute. */
final class ProjectSourceText {
    static final int MAX_BYTES=2*1024*1024;
    private static final int CHUNK=8000,OVERLAP=256;
    final String name,text,digest;
    final int bytes;
    ProjectSourceText(String name,byte[] raw)throws Exception{
        if(raw==null||raw.length<1||raw.length>MAX_BYTES)throw new IllegalArgumentException("source_size");
        if(name==null||name.isBlank()||name.length()>160||name.codePoints().anyMatch(Character::isISOControl))
            throw new IllegalArgumentException("source_name");
        this.name=name;bytes=raw.length;
        text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();
        if(text.isBlank()||text.codePoints().anyMatch(x->Character.isISOControl(x)&&x!=9&&x!=10&&x!=13))
            throw new IllegalArgumentException("source_not_text");
        StringBuilder hash=new StringBuilder();
        for(byte b:MessageDigest.getInstance("SHA-256").digest(raw))hash.append(String.format(Locale.ROOT,"%02x",b&255));
        digest=hash.toString();
    }
    static final class Passage {
        final int start,end;final String text;
        Passage(int start,int end,String text){this.start=start;this.end=end;this.text=text;}
    }
    private int boundary(int i){
        return i>0&&i<text.length()&&Character.isHighSurrogate(text.charAt(i-1))&&Character.isLowSurrogate(text.charAt(i))?i-1:i;
    }
    List<Passage> passages(){
        List<Passage> out=new ArrayList<>();
        for(int start=0;start<text.length();){
            int end=boundary(Math.min(text.length(),start+CHUNK));
            out.add(new Passage(start,end,text.substring(start,end)));
            if(end==text.length())break;
            start=boundary(end-OVERLAP);
        }
        return out;
    }
}
