package com.asterion.control;

/** JVM-only regression test: javac/java, no Android SDK or APK build. */
public final class VoiceWakeWordsTest {
  private static int assertions=0;
  private static void check(boolean ok,String label){
    assertions++;
    if(!ok)throw new AssertionError(label);
  }
  private static void expect(String spoken,boolean awaiting,long wake,long now,
       String command,boolean rearm,boolean heard,String label){
    VoiceWakeWords.Decision d=VoiceWakeWords.decide(spoken,awaiting,wake,now);
    check(command.equals(d.command),label+" command");
    check(rearm==d.awaitingCommand,label+" rearm");
    check(heard==d.heardWake,label+" wake");
  }
  public static void main(String[] args){
    long t=100000L;
    expect("Asterion",false,0,t,"",true,true,"bare wake");
    expect("hey ASTERION!",false,0,t,"",true,true,"punctuated wake");
    expect("Okay Asterion, open diagnostics",false,0,t,
       "open diagnostics",false,true,"one-shot command");
    expect("asterion",true,t-2000,t,"",true,true,"repeated wake never sent");
    expect("Asterion, open browser",true,t-2000,t,
       "open browser",false,true,"repeated wake with command");
    expect("show my incident list",true,t-5000,t,
       "show my incident list",false,false,"timely followup");
    expect("search for private stuff",true,t-12001,t,
       "",false,false,"expired followup ignored");
    expect("open browser",false,0,t,"",false,false,"no wake no command");
    expect("asterionics search",false,0,t,"",false,false,"word boundary");
    expect(null,false,0,t,"",false,false,"null");
    expect("   ",true,t-1500,t,"",false,false,"blank");
    expect("Hey asterionics",false,0,t,"",false,false,"false prefix");
    expect("Salut Astérion, ouvre les notes",false,0,t,"ouvre les notes",false,true,"French command");
    expect("アステリオン、こんにちは",false,0,t,"こんにちは",false,true,"Japanese command");
    expect("아스테리온",false,0,t,"",true,true,"Korean wake");
    expect("Astérionique",false,0,t,"",false,false,"French false prefix");
    check(VoiceWakeWords.matchesWake("ASTERION?"),"wake preview");
    check(!VoiceWakeWords.matchesWake("asterionics"),"preview false prefix");
    System.out.println("VOICE_WAKE_WORDS_PASS "+assertions+" assertions");
  }
}
