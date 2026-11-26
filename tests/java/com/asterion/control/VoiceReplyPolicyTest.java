package com.asterion.control;
public final class VoiceReplyPolicyTest {
  public static void main(String[] args){
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
    System.out.println("VoiceReplyPolicy: 9 assertions passed");
  }
}
