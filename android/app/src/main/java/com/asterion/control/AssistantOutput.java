package com.asterion.control;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

/** Presentation boundary for model output. Never treats model text as an executable command. */
final class AssistantOutput {
    private static final String[] MARKERS={"<think>","</think>","<analysis>","</analysis>",
            "<|im_start|>","<|im_end|>","<|endoftext|>","<|eot_id|>",
            "<|start_header_id|>","<|end_header_id|>",
            "<|channel|>analysis<|message|>","<|channel|>final<|message|>",
            "<|end|>","<|return|>","<|im_sep|>"};
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
        StringBuilder result=new StringBuilder();
        int depth=initiallyThinking?1:0;
        for(int i=0;i<raw.length();){
            String match=null;
            if(raw.charAt(i)=='<'){
                int available=raw.length()-i;
                boolean partial=false;
                for(String marker:MARKERS){
                    int length=Math.min(available,marker.length());
                    if(!raw.regionMatches(true,i,marker,0,length))continue;
                    if(length==marker.length()){match=marker;break;}
                    partial=true;
                }
                if(match==null&&partial)break;
            }
            if(match!=null){
                if(match.equals("<think>")||match.equals("<analysis>")||
                    match.equals("<|channel|>analysis<|message|>"))depth++;
                else if(match.equals("</think>")||match.equals("</analysis>"))depth=Math.max(0,depth-1);
                else if(match.equals("<|channel|>final<|message|>"))depth=0;
                else if(match.equals("<|im_start|>")||match.equals("<|start_header_id|>")||
                        match.equals("<|im_end|>")||match.equals("<|endoftext|>")||
                        match.equals("<|eot_id|>")||match.equals("<|return|>"))break;
                i+=match.length();continue;
            }
            if(depth==0)result.append(raw.charAt(i));
            i++;
        }
        return result.toString().trim();
    }
}
