package com.asterion.control;
public final class VoiceReplyPolicyTest {
  public static void main(String[] args){
    assert VoiceReplyPolicy.englishLocale("en");
    assert VoiceReplyPolicy.englishLocale("en-US");
    assert VoiceReplyPolicy.englishLocale("en-GB");
    assert !VoiceReplyPolicy.englishLocale("fr-FR");
    assert !VoiceReplyPolicy.englishLocale(null);
    assert !VoiceReplyPolicy.englishLocale("en-US-extra");
    assert VoiceReplyPolicy.currentExchange(true,"q","q",4,4);
    assert !VoiceReplyPolicy.currentExchange(false,"q","q",4,4);
    assert !VoiceReplyPolicy.currentExchange(true,"q","q",4,5);
    assert !VoiceReplyPolicy.currentExchange(true,"q","other",4,4);
    assert VoiceReplyPolicy.speech("hello",false).equals("hello");
    assert VoiceReplyPolicy.speech("",true).contains("Review the proposed action");
    String longText="a".repeat(900);
    for(boolean review:new boolean[]{false,true}){
      String s=VoiceReplyPolicy.speech(longText,review);
      assert s.length()<=700;
      assert s.contains("full response");
      assert s.contains("Review the proposed action")==review;
    }
    assert VoiceReplyPolicy.speech(null,false).contains("available");
    System.out.println("VoiceReplyPolicy: 19 assertions passed");
  }
}
