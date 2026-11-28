package com.asterion.control;

import java.util.Locale;

/** Locale-bound spoken preview; full response remains in the canonical conversation. */
final class VoiceReplyPolicy {
  private VoiceReplyPolicy(){}
  static boolean englishLocale(String locale){
    return locale!=null&&locale.matches("en(-[A-Z]{2})?");
  }
  static String canonicalLocale(String tag){
    if(tag==null||!tag.matches("[A-Za-z]{2,3}(-[A-Za-z]{4})?(-([A-Za-z]{2}|[0-9]{3}))?"))
      throw new IllegalArgumentException("Invalid speech language tag");
    Locale value=Locale.forLanguageTag(tag);
    if(value.getLanguage().isEmpty()||"und".equals(value.getLanguage()))
      throw new IllegalArgumentException("Invalid speech language tag");
    return value.toLanguageTag();
  }
  static String language(String locale){return Locale.forLanguageTag(canonicalLocale(locale)).getLanguage();}
  static boolean currentExchange(boolean active,String expectedId,String currentId,
                                 long expectedGeneration,long currentGeneration){
    return active&&expectedId!=null&&expectedId.equals(currentId)&&expectedGeneration==currentGeneration;
  }
  static String invitation(String locale){
    switch(language(locale)){
      case "fr":return "Que souhaitez-vous que je fasse ?";
      case "ja":return "何をしましょうか？";
      case "de":return "Was soll ich für Sie tun?";
      case "es":return "¿Qué quiere que haga?";
      case "it":return "Che cosa vuole che faccia?";
      case "pt":return "O que gostaria que eu fizesse?";
      case "ko":return "무엇을 도와드릴까요?";
      case "zh":return "您希望我做什么？";
      case "en":return "What would you like me to do?";
      default:return ""; // No misleading English prompt in a different voice.
    }
  }
  static String testPrompt(String locale){
    switch(language(locale)){
      case "fr":return "Test vocal Asterion. Répondez à voix haute : un, deux, trois.";
      case "ja":return "Asterion の音声テストです。声に出して、一、二、三と答えてください。";
      case "de":return "Asterion Sprachtest. Antworten Sie laut: eins, zwei, drei.";
      case "es":return "Prueba de voz de Asterion. Responda en voz alta: uno, dos, tres.";
      case "it":return "Test vocale Asterion. Risponda ad alta voce: uno, due, tre.";
      case "pt":return "Teste de voz Asterion. Responda em voz alta: um, dois, três.";
      case "ko":return "Asterion 음성 테스트입니다. 소리 내어 하나, 둘, 셋이라고 답해 주세요.";
      case "zh":return "Asterion 语音测试。请大声回答：一、二、三。";
      case "en":return "Asterion Control speaker test. Please answer aloud: test one two three.";
      default:return "";
    }
  }
  private static String notice(String locale,boolean review){
    switch(language(locale)){
      case "fr":return review?" Vérifiez l’action proposée dans Asterion Control.":" La réponse complète est disponible dans Asterion Control.";
      case "ja":return review?" Asterion Control で提案された操作を確認してください。":" 回答の全文は Asterion Control で確認できます。";
      case "de":return review?" Prüfen Sie die vorgeschlagene Aktion in Asterion Control.":" Die vollständige Antwort steht in Asterion Control.";
      case "es":return review?" Revise la acción propuesta en Asterion Control.":" La respuesta completa está en Asterion Control.";
      case "it":return review?" Controlli l'azione proposta in Asterion Control.":" La risposta completa è disponibile in Asterion Control.";
      case "pt":return review?" Reveja a ação proposta no Asterion Control.":" A resposta completa está disponível no Asterion Control.";
      case "ko":return review?" Asterion Control에서 제안된 작업을 확인하세요.":" 전체 답변은 Asterion Control에서 확인할 수 있습니다.";
      case "zh":return review?" 请在 Asterion Control 中审核建议的操作。":" 完整回答可在 Asterion Control 中查看。";
      case "en":return review?" Review the proposed action in Asterion Control.":" The full response is available in Asterion Control.";
      default:return "";
    }
  }
  static String speech(String answer,boolean review){return speech(answer,review,"en-US");}
  static String speech(String answer,boolean review,String locale){
    String text=answer==null?"":answer.trim();
    String suffix=review?notice(locale,true):"";
    String continuation=notice(locale,false);
    if(text.isEmpty())return (review?suffix:continuation).trim();
    if(text.length()+suffix.length()>700){
      int max=700-suffix.length()-continuation.length();
      if(max>0&&Character.isHighSurrogate(text.charAt(max-1)))max--;
      text=text.substring(0,max).trim()+continuation;
    }
    return text+suffix;
  }
}
