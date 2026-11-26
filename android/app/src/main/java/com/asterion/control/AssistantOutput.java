package com.asterion.control;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** Presentation boundary for model output. Never treats model text as an executable command. */
final class AssistantOutput {
    private final ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    private boolean initiallyThinking;
    synchronized void initialThinking(boolean value){initiallyThinking=value;}
    synchronized String append(byte[] piece){
        if(bytes.size()+piece.length>262144)throw new IllegalStateException("response_budget_exceeded");
        bytes.write(piece,0,piece.length);
        // A token can end halfway through an emoji or another UTF-8 code point.
        ByteBuffer input=ByteBuffer.wrap(bytes.toByteArray());
        CharBuffer output=CharBuffer.allocate(bytes.size()+1);
        StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPLACE)
            .onUnmappableCharacter(CodingErrorAction.REPLACE).decode(input,output,false);
        output.flip();
        return visible(output.toString(),false,initiallyThinking);
    }
    synchronized String finish(byte[] full){return visible(new String(full,StandardCharsets.UTF_8),true,initiallyThinking);}
    static String visible(String raw,boolean complete){return visible(raw,complete,false);}
    static String visible(String raw,boolean complete,boolean initiallyThinking){
        if(raw==null)return "";
        String lower=raw.toLowerCase(Locale.ROOT);
        String[] markers={"<think>","</think>","<analysis>","</analysis>",
            "<|im_start|>","<|im_end|>","<|endoftext|>","<|eot_id|>",
            "<|start_header_id|>","<|end_header_id|>",
            "<|channel|>analysis<|message|>","<|channel|>final<|message|>",
            "<|end|>","<|return|>","<|im_sep|>"};
        StringBuilder result=new StringBuilder();
        int depth=initiallyThinking?1:0;
        for(int i=0;i<raw.length();){
            String match=null;
            for(String marker:markers)if(lower.startsWith(marker,i)){match=marker;break;}
            if(match!=null){
                if(match.equals("<think>")||match.equals("<analysis>")||
                    match.equals("<|channel|>analysis<|message|>"))depth++;
                else if(match.equals("</think>")||match.equals("</analysis>"))depth=Math.max(0,depth-1);
                else if(match.equals("<|channel|>final<|message|>"))depth=0;
                else if(match.equals("<|im_start|>")||match.equals("<|start_header_id|>"))break;
                i+=match.length();continue;
            }
            // Withhold incomplete delimiters at EVERY token boundary, including final
            // truncated generations. A visible prefix must never flash internal text.
            String tail=lower.substring(i);
            boolean prefix=false;
            if(tail.charAt(0)=='<')for(String marker:markers)
                if(marker.startsWith(tail)){prefix=true;break;}
            if(prefix)break;
            if(depth==0)result.append(raw.charAt(i));
            i++;
        }
        return result.toString().trim();
    }
}
