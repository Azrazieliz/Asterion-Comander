package com.asterion.control;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pure hotword parser shared by preview and final Android recognition.
 * The wake word alone is NEVER an instruction or web-search query.
 * This class has no Android dependencies so it can be compiled and tested
 * without building or signing an APK.
 */
final class VoiceWakeWords {
  private static final long FOLLOWUP_MS=12000L;
  private static final Pattern WAKE=Pattern.compile(
    "(?iu)^\\s*(?:(?:hey|okay|ok|salut|bonjour|hola|hallo|ciao|olá)\\s+)?(?:asterion|astérion|アステリオン|아스테리온)(?=$|[\\s,:;.!?、。！？：-])[\\s,:;.!?、。！？：-]*(.*)$");
  private VoiceWakeWords(){}

  static final class Decision {
    final String command;
    final boolean awaitingCommand;
    final boolean heardWake;
    Decision(String command,boolean awaitingCommand,boolean heardWake){
      this.command=command;
      this.awaitingCommand=awaitingCommand;
      this.heardWake=heardWake;
    }
  }
  static boolean matchesWake(String transcript){
    return transcript!=null && WAKE.matcher(transcript.trim()).matches();
  }
  static Decision decide(String transcript,boolean wasAwaiting,
                         long lastWakeMs,long nowMs){
    String speech=transcript==null?"":transcript.trim();
    Matcher match=WAKE.matcher(speech);
    if(match.matches()){
      String tail=match.group(1).trim();
      // Repeating a bare hotword re-arms the follow-up window; it must not
      // ever be forwarded as a browser search or owner command.
      return new Decision(tail,tail.isEmpty(),true);
    }
    if(wasAwaiting&&!speech.isEmpty()&&nowMs>=lastWakeMs
        &&nowMs-lastWakeMs<=FOLLOWUP_MS)
      return new Decision(speech,false,false);
    return new Decision("",false,false);
  }
}
