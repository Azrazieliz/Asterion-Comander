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
    assert VoiceReplyPolicy.canonicalLocale("fr-fr").equals("fr-FR");
    assert VoiceReplyPolicy.canonicalLocale("ja-JP").equals("ja-JP");
    assert VoiceReplyPolicy.canonicalLocale("zh-Hant-TW").equals("zh-Hant-TW");
    assert VoiceReplyPolicy.invitation("fr-FR").contains("souhaitez");
    assert VoiceReplyPolicy.invitation("ja-JP").contains("何");
    assert VoiceReplyPolicy.testPrompt("ja-JP").contains("一、二、三");
    assert VoiceReplyPolicy.speech("Bonjour",true,"fr-FR").contains("Vérifiez");
    assert VoiceReplyPolicy.speech("日本語",true,"ja-JP").contains("確認");
    assert VoiceReplyPolicy.speech("abc".repeat(300),true,"fr-FR").length()<=700;
    assert VoiceReplyPolicy.speech("😀".repeat(450),true,"ja-JP").length()<=700;
    assert VoiceReplyPolicy.invitation("nl-NL").isEmpty();
    for(String invalid:new String[]{"","und","en-US-extra","fr_FR","en\\nUS","<en>"})
      try{VoiceReplyPolicy.canonicalLocale(invalid);throw new AssertionError("Invalid locale admitted");}
      catch(IllegalArgumentException expected){}
    System.out.println("VoiceReplyPolicy multilingual behavior passed");
  }
}
