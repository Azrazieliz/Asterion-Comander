package com.asterion.control;

/** Bounded spoken preview; full response remains in the canonical conversation. */
final class VoiceReplyPolicy {
  private VoiceReplyPolicy(){}
  static String speech(String answer,boolean review){
    String text=answer==null?"":answer.trim();
    String suffix=review?" Review the proposed action in Asterion Control.":"";
    if(text.isEmpty())return review?suffix.trim():"The response is available in Asterion Control.";
    String continuation=" The full response is available in Asterion Control.";
    if(text.length()+suffix.length()>700){
      int max=700-suffix.length()-continuation.length();
      if(max>0&&Character.isHighSurrogate(text.charAt(max-1)))max--;
      text=text.substring(0,max).trim()+continuation;
    }
    return text+suffix;
  }
}
