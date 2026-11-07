package com.asterion.control;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.KeyguardManager;
import android.app.Service;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.Context;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.media.AudioManager;
import android.media.AudioFocusRequest;
import android.media.AudioAttributes;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.Voice;
import android.speech.tts.UtteranceProgressListener;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Owner-started Android foreground speaker -> on-device microphone Q&A.
 * Owner-only authenticated remote requests; no recording storage or continuous hot microphone.
 */
public final class VoiceDialogueService extends Service {
  public static volatile VoiceDialogueService active;
  private final Handler ui=new Handler(Looper.getMainLooper());
  private TextToSpeech speaker;
  private AudioManager speechAudioManager;
  private AudioFocusRequest speechAudioRequest;
  private volatile boolean exclusiveSpeechAudio=false;
  private SpeechRecognizer listener;
  private volatile String phase="stopped", question="", transcript="", error="";
  private volatile long updatedAt=0L;
  private volatile String questionId="";
  private volatile boolean speakerReady=false;
  private String listeningLocale="en-US";
  private volatile float naturalRate=0.96f,naturalPitch=1.00f;
  private volatile String chosenVoice="system_default";
  private volatile int chosenVoiceQuality=-1;
  private static final int NOTIFICATION_ID=2107;
  private static final long SPEAKER_TIMEOUT_MS=90000L;
  private static final long ANSWER_TIMEOUT_MS=45000L;
  private volatile boolean consumed=true;
  private volatile boolean microphoneActive=false;
  private volatile boolean speakerPlaybackStarted=false;
  private volatile boolean speakerPlaybackCompleted=false;
  private volatile boolean pendingLocalTest=false;
  private volatile String recognizerBackend="none";
  private final ExecutorService voiceControlWorker=Executors.newSingleThreadExecutor();
  private volatile boolean speakOnly=false;
  private volatile boolean ownerCommandMode=false;
  private volatile String lastVoiceDispatch="not_started";
  private static final long VOICE_WAKE_MAX_MS=150000L;
  private PowerManager.WakeLock speechWakeLock;
  private volatile boolean pendingOwnerTalk=false;
  private void keepCpuForExchange() {
    PowerManager pm=(PowerManager)getSystemService(POWER_SERVICE);
    if(pm==null)throw new IllegalStateException("Power manager unavailable");
    if(speechWakeLock==null)
      speechWakeLock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"AsterionControl:VoiceExchange");
    if(!speechWakeLock.isHeld())speechWakeLock.acquire(VOICE_WAKE_MAX_MS);
  }
  private void releaseCpuForExchange(){
    if(speechWakeLock!=null&&speechWakeLock.isHeld())speechWakeLock.release();
  }
  private void localVoiceTest(){
    if(active!=this)return;
    try{
      String prompt="Asterion Control speaker test. Please answer aloud: test one two three.";
      String id="selftest-"+System.currentTimeMillis();
      // Even without an installed offline speech pack, TEST must exercise the
      // speaker and then report the *specific* missing microphone prerequisite.
      if((Build.VERSION.SDK_INT>=31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this))
          || SpeechRecognizer.isRecognitionAvailable(this)){
        ask(prompt,"en-US",id);
      }else{
        question=prompt;questionId=id;transcript="";consumed=true;
        speakerPlaybackStarted=false;speakerPlaybackCompleted=false;
        state("speaking","");
        scheduleDeadline(id,SPEAKER_TIMEOUT_MS);
        speakNow(prompt,"en-US",id);
      }
    }catch(Exception e){state("failed","Speaker test failed: "+e.getClass().getSimpleName()+
      (e.getMessage()==null?"":": "+e.getMessage()));}
  }
  private Runnable deadline;
  private void clearDeadline(){
    if(deadline!=null){ui.removeCallbacks(deadline);deadline=null;}
  }
  private void scheduleDeadline(String id,long delay){
    clearDeadline();
    deadline=()->{
      if(active!=this||!id.equals(questionId))return;
      if("answered".equals(phase)||"acknowledged".equals(phase))return;
      if(listener!=null){listener.cancel();listener.destroy();listener=null;}
      microphoneActive=false;
      state("failed","Speech answer timed out; microphone closed");
    };
    ui.postDelayed(deadline,delay);
  }
  private void acquireAudioFocus() {
    speechAudioManager=getSystemService(AudioManager.class);
    if(speechAudioManager==null)throw new IllegalStateException("Android audio manager unavailable");
    AudioAttributes use=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT)
      .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build();
    speechAudioRequest=new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
      .setAudioAttributes(use)
      .setOnAudioFocusChangeListener(change->{
        if(change==AudioManager.AUDIOFOCUS_LOSS || change==AudioManager.AUDIOFOCUS_LOSS_TRANSIENT)
          ui.post(()->{if("speaking".equals(phase)||"listening".equals(phase)){
            if(speaker!=null)speaker.stop();
            if(listener!=null)listener.cancel();
            microphoneActive=false;
            state("failed","Android audio focus lost");
          }});
      },ui).build();
    exclusiveSpeechAudio=speechAudioManager.requestAudioFocus(speechAudioRequest)
      ==AudioManager.AUDIOFOCUS_REQUEST_GRANTED;
    if(!exclusiveSpeechAudio)throw new IllegalStateException("Music or another app denied speech audio focus");
  }
  private void releaseAudioFocus(){
    if(!exclusiveSpeechAudio)return;
    exclusiveSpeechAudio=false;
    if(speechAudioManager!=null&&speechAudioRequest!=null)
      speechAudioManager.abandonAudioFocusRequest(speechAudioRequest);
    speechAudioRequest=null;
  }
  private void state(String value,String message){
    phase=value;error=message;updatedAt=System.currentTimeMillis();
    if("answered".equals(value)||"failed".equals(value)||"acknowledged".equals(value)
        ||"ready".equals(value)||"delivered".equals(value)) {
      releaseAudioFocus();
      releaseCpuForExchange();
    }
  }
  @Override public void onCreate(){
    SharedPreferences saved=getSharedPreferences(VOICE_PREFS,MODE_PRIVATE);
    naturalRate=Math.max(0.85f,Math.min(1.15f,saved.getFloat("rate",0.96f)));
    naturalPitch=Math.max(0.90f,Math.min(1.10f,saved.getFloat("pitch",1.00f)));
    super.onCreate();
    speaker=new TextToSpeech(this,status->{
      speakerReady=status==TextToSpeech.SUCCESS;
      state(speakerReady?"ready":"unavailable",
        speakerReady?"":"Android text-to-speech engine unavailable");
      if(speakerReady&&pendingLocalTest&&active==this){
        pendingLocalTest=false;
        ui.post(this::localVoiceTest);
      }
      if(speakerReady&&pendingOwnerTalk&&active==this){
        pendingOwnerTalk=false;
        ui.post(()->{
          try{beginOwnerVoiceControl("en-US");}
          catch(Exception e){state("failed","Could not start voice control: "+e.getMessage());}
        });
      }
    });
  }
  private Notification notification(){
    NotificationManager manager=getSystemService(NotificationManager.class);
    manager.createNotificationChannel(new NotificationChannel("asterion_voice",
      "Asterion voice questions",NotificationManager.IMPORTANCE_LOW));
    Intent stop=new Intent(this,VoiceDialogueService.class).setAction("STOP");
    PendingIntent action=PendingIntent.getService(this,2107,stop,
      PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
    Intent talk=new Intent(this,VoiceDialogueService.class).setAction("TALK");
    PendingIntent talkAction=PendingIntent.getService(this,2108,talk,
      PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
    return new Notification.Builder(this,"asterion_voice")
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentTitle("Asterion voice control")
      .setContentText("Ready for voice questions while other apps are open")
      .setVisibility(Notification.VISIBILITY_PUBLIC)
      .addAction(android.R.drawable.ic_btn_speak_now,"Talk to Asterion",talkAction)
      .addAction(android.R.drawable.ic_menu_close_clear_cancel,"Stop",action)
      .setOngoing(true).build();
  }
  @Override public int onStartCommand(Intent intent,int flags,int startId){
    if(intent!=null&&"STOP".equals(intent.getAction())){
      stopSelf();return START_NOT_STICKY;
    }
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
      stopSelf();return START_NOT_STICKY;
    }
    startForeground(NOTIFICATION_ID,notification(),
      ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
    active=this;
    if(intent!=null&&"TALK".equals(intent.getAction())){
      pendingOwnerTalk=true;
      if(speakerReady){
        pendingOwnerTalk=false;
        ui.post(()->{
          try{beginOwnerVoiceControl("en-US");}
          catch(Exception e){state("failed","Voice start failed: "+e.getMessage());}
        });
      }else state("initializing","Waiting for speaker");
    }else if(intent!=null&&"TEST".equals(intent.getAction())){
      pendingLocalTest=true;
      if(speakerReady){pendingLocalTest=false;ui.post(this::localVoiceTest);}
      else state("initializing","Awaiting Android text-to-speech startup");
    }else if(!speakerReady)state("initializing","");
    return START_NOT_STICKY;
  }
  // Owner-only native API, with Android microphone consent and foreground rules.
  static JSONObject enableFromOwnerApi(Context owner)throws Exception{
    if(owner.checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)
      throw new IllegalStateException("Android microphone permission is required");
    VoiceDialogueService running=active;
    if(running!=null)return running.report();
    if(MainActivity.foregroundActivity()==null)
      throw new IllegalStateException("Open Asterion Control on phone before enabling voice in the foreground");
    owner.startForegroundService(new Intent(owner,VoiceDialogueService.class));
    return new JSONObject().put("ok",true).put("start_requested",true).put("phase","initializing");
  }
  static JSONObject stopFromOwnerApi(Context owner)throws Exception{
    boolean wasRunning=active!=null;
    owner.stopService(new Intent(owner,VoiceDialogueService.class));
    return new JSONObject().put("ok",true).put("stop_requested",true).put("was_running",wasRunning);
  }
  synchronized JSONObject ask(String text,String locale)throws Exception {
    return ask(text,locale,"");
  }
  synchronized JSONObject ask(String text,String locale,String requestId)throws Exception {
    if(active!=this)throw new IllegalStateException("Enable voice questions from the phone first");
    if(!speakerReady)throw new IllegalStateException("Android speaker not ready");
    if(text==null||text.isBlank()||text.length()>700)
      throw new IllegalArgumentException("Question must contain 1-700 characters");
    if(!locale.matches("[a-z]{2}(-[A-Z]{2})?"))
      throw new IllegalArgumentException("Invalid speech locale");
    if(requestId!=null&&!requestId.isEmpty()&&
       !requestId.matches("[A-Za-z0-9_.-]{3,100}"))
      throw new IllegalArgumentException("Invalid voice question identifier");
    if(requestId!=null&&!requestId.isEmpty()&&requestId.equals(questionId)){
      if(!text.equals(question))throw new IllegalStateException("Question ID was already used");
      return report();  // Safe retry: never speak a question twice.
    }
    if("speaking".equals(phase)||"listening".equals(phase)||"processing".equals(phase))
      throw new IllegalStateException("Another voice exchange is active");
    if("answered".equals(phase)&&!consumed)
      throw new IllegalStateException("Previous voice answer has not been acknowledged");
    if(!(Build.VERSION.SDK_INT>=31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this))
        && !SpeechRecognizer.isRecognitionAvailable(this))
      throw new IllegalStateException("No Android speech recognition engine is available");
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)
      throw new IllegalStateException("Android microphone consent is missing");
    acquireAudioFocus(); // Android pauses competing music where the player supports focus.
    try{keepCpuForExchange();}catch(Exception e){releaseAudioFocus();throw e;}
    speakOnly=false;
    question=text;transcript="";consumed=false;
    speakerPlaybackStarted=false;speakerPlaybackCompleted=false;
    questionId=requestId==null||requestId.isEmpty()?UUID.randomUUID().toString():requestId;
    listeningLocale=locale;
    state("speaking","");
    final String id=questionId;
    ui.post(()->{
      scheduleDeadline(id,SPEAKER_TIMEOUT_MS);
      speakNow(text,locale,id);
    });
    return new JSONObject().put("ok",true).put("question_id",id).put("phase","speaking");
  }
  synchronized JSONObject acknowledge(String id)throws Exception {
    if(id==null||!id.equals(questionId)||!"answered".equals(phase))
      throw new IllegalStateException("No completed voice answer with this question ID");
    consumed=true;
    transcript="";question="";
    state("acknowledged","");
    return new JSONObject().put("ok",true).put("question_id",id)
      .put("phase","acknowledged");
  }
  private static final String VOICE_PREFS="voice_style";
  /** Default to an installed, high-quality OFFLINE voice for the requested accent.
   * Never substitute another country/accent silently or require network audio. */
  private void applyNaturalVoice(Locale language){
    if(speaker==null)return;
    try{
      Set<Voice> installed=speaker.getVoices();
      Voice best=null;
      if(installed!=null)for(Voice candidate:installed){
        if(candidate==null||candidate.isNetworkConnectionRequired() ||
            candidate.getLocale()==null ||
            !candidate.getLocale().toLanguageTag().equalsIgnoreCase(language.toLanguageTag()))continue;
        if(candidate.getFeatures()!=null &&
            candidate.getFeatures().contains(TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED))continue;
        if(best==null||candidate.getQuality()>best.getQuality())best=candidate;
      }
      if(best!=null&&best.getQuality()>=Voice.QUALITY_HIGH)speaker.setVoice(best);
    }catch(Exception ignored){/* Retain Android's selected locale voice. */}
    Voice applied=speaker.getVoice();
    chosenVoice=applied==null?"system_default":applied.getName();
    chosenVoiceQuality=applied==null?-1:applied.getQuality();
    speaker.setSpeechRate(naturalRate);
    speaker.setPitch(naturalPitch);
  }
  synchronized JSONObject voiceSettings()throws Exception{
    return new JSONObject().put("ok",true).put("rate",naturalRate)
      .put("pitch",naturalPitch).put("voice",chosenVoice)
      .put("voice_quality",chosenVoiceQuality)
      .put("locale",listeningLocale)
      .put("offline_voice_preferred",true);
  }
  synchronized JSONObject configureVoiceSettings(JSONObject input)throws Exception{
    if(input==null)throw new IllegalArgumentException("Missing voice preferences");
    double r=input.optDouble("rate",0.96),p=input.optDouble("pitch",1.0);
    if(!Double.isFinite(r)||r<0.85||r>1.15||!Double.isFinite(p)||p<0.90||p>1.10)
      throw new IllegalArgumentException("Rate must be 0.85–1.15 and pitch 0.90–1.10");
    if("speaking".equals(phase)||"listening".equals(phase)||"processing".equals(phase))
      throw new IllegalStateException("Finish current spoken exchange before changing voice");
    naturalRate=(float)r;naturalPitch=(float)p;
    getSharedPreferences(VOICE_PREFS,MODE_PRIVATE).edit()
      .putFloat("rate",naturalRate).putFloat("pitch",naturalPitch).apply();
    if(speaker!=null){speaker.setSpeechRate(naturalRate);speaker.setPitch(naturalPitch);}
    return voiceSettings();
  }
  private void speakNow(String text,String locale,String id){
    if(active!=this)return;
    Locale language=Locale.forLanguageTag(locale);
    speaker.setAudioAttributes(new android.media.AudioAttributes.Builder()
      .setUsage(android.media.AudioAttributes.USAGE_ASSISTANT)
      .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build());
    int languageResult=speaker.setLanguage(language);
    if(languageResult==TextToSpeech.LANG_MISSING_DATA || languageResult==TextToSpeech.LANG_NOT_SUPPORTED){
      clearDeadline();state("failed","Requested speech voice data is unavailable");return;
    }
    applyNaturalVoice(language);
    speaker.setOnUtteranceProgressListener(new UtteranceProgressListener(){
      @Override public void onStart(String utteranceId){
        if(id.equals(utteranceId))speakerPlaybackStarted=true;
      }
      @Override public void onDone(String utteranceId){
        if(id.equals(utteranceId)){
          speakerPlaybackCompleted=true;
          ui.post(()->{
            releaseAudioFocus();
            if(speakOnly){clearDeadline();speakOnly=false;state("ready","");}
            else startListening(locale,id);
          });
        }
      }
      @Override public void onError(String utteranceId){
        if(id.equals(utteranceId)){
          ui.post(()->clearDeadline());
          state("failed","Android speech playback failed");
        }
      }
    });
    int response=speaker.speak(text,TextToSpeech.QUEUE_FLUSH,null,id);
    if(response!=TextToSpeech.SUCCESS){clearDeadline();state("failed","Could not start speaker");}
  }
  private void startListening(String locale,String id){
    if(active!=this||!id.equals(questionId))return;
    boolean offline=Build.VERSION.SDK_INT>=31
      && SpeechRecognizer.isOnDeviceRecognitionAvailable(this);
    boolean standard=SpeechRecognizer.isRecognitionAvailable(this);
    if(!offline&&!standard){
      clearDeadline();microphoneActive=false;
      state("failed","Speaker completed; no Android speech recognition service available");
      return;
    }
    try{beginRecognition(locale,id,offline);}
    catch(Exception e){
      if(offline&&standard){
        try{beginRecognition(locale,id,false);return;}
        catch(Exception fallback){e=fallback;}
      }
      clearDeadline();microphoneActive=false;
      state("failed","Android speech recognition could not start: "+
        e.getClass().getSimpleName());
    }
  }
  /** The Android system recognizer is a one-time fallback when the offline
   * language model is missing (error 13). It may use Android's network speech
   * service; the app never uploads audio to Asterion servers or embeds AI.
   */
  private void beginRecognition(String locale,String id,boolean offline)throws Exception {
    if(active!=this||!id.equals(questionId))return;
    if(listener!=null){listener.cancel();listener.destroy();listener=null;}
    recognizerBackend=offline?"on_device":"android_system";
    listener=offline?SpeechRecognizer.createOnDeviceSpeechRecognizer(this)
      :SpeechRecognizer.createSpeechRecognizer(this);
    scheduleDeadline(id,ANSWER_TIMEOUT_MS);
    final String backend=recognizerBackend;
    listener.setRecognitionListener(new RecognitionListener(){
      @Override public void onReadyForSpeech(Bundle extras){
        if(id.equals(questionId)&&backend.equals(recognizerBackend)){
          microphoneActive=true;state("listening","");
        }
      }
      @Override public void onBeginningOfSpeech(){}
      @Override public void onRmsChanged(float rmsdB){}
      @Override public void onBufferReceived(byte[] data){}
      @Override public void onEndOfSpeech(){
        if(id.equals(questionId)&&backend.equals(recognizerBackend))
          state("processing","");
      }
      @Override public void onError(int code){
        if(!id.equals(questionId)||!backend.equals(recognizerBackend))return;
        microphoneActive=false;
        if(offline && (code==SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE
            || code==SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED
            || code==SpeechRecognizer.ERROR_CLIENT)
            && SpeechRecognizer.isRecognitionAvailable(VoiceDialogueService.this)){
          state("fallback","Offline recognizer unavailable (error "+code+"); trying Android system speech");
          ui.post(()->{
            if(active!=VoiceDialogueService.this||!id.equals(questionId))return;
            try{beginRecognition(locale,id,false);}
            catch(Exception failure){
              clearDeadline();
              state("failed","Android system speech fallback unavailable: "+
                failure.getClass().getSimpleName());
            }
          });
          return;
        }
        clearDeadline();state("failed",speechError(code));
        ui.post(()->{if(listener!=null){listener.destroy();listener=null;}});
      }
      @Override public void onResults(Bundle results){
        if(!id.equals(questionId)||!backend.equals(recognizerBackend))return;
        microphoneActive=false;clearDeadline();
        ArrayList<String> phrases=results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
        transcript=phrases==null||phrases.isEmpty()?"":phrases.get(0);
        boolean command=ownerCommandMode;
        ownerCommandMode=false;
        state(transcript.isEmpty()?"failed":command?"processing":"answered",
          transcript.isEmpty()?"No recognized speech":"");
        ui.post(()->{if(listener!=null){listener.destroy();listener=null;}});
        if(command&&!transcript.isEmpty()){
          final String spoken=transcript;
          voiceControlWorker.execute(()->dispatchOwnerVoiceRequest(spoken));
        }
      }
      @Override public void onPartialResults(Bundle results){}
      @Override public void onEvent(int type,Bundle params){}
    });
    Intent request=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
    request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
    request.putExtra(RecognizerIntent.EXTRA_LANGUAGE,locale);
    request.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1);
    if(offline)request.putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE,true);
    state("listening","");
    listener.startListening(request);
  }
  /** One explicit owner-initiated voice turn. The recognizer transcribes what the
   * owner says, then Control sends it into the existing ChatGPT writing bar.
   * This never creates a queue or fabricates an AI response.
   */
  synchronized JSONObject beginOwnerVoiceControl(String locale)throws Exception{
    if(active!=this)throw new IllegalStateException("Enable voice session first");
    if(ownerCommandMode)throw new IllegalStateException("Voice command already running");
    ownerCommandMode=true;
    try{
      JSONObject started=ask("What would you like me to do?",locale,
        "owner-command-"+System.currentTimeMillis());
      lastVoiceDispatch="listening_for_owner";
      return started.put("voice_control",true);
    }catch(Exception e){ownerCommandMode=false;throw e;}
  }
  /** Speak an assistant reply without reopening the microphone. Follow-up
   * questions continue through the existing question/listen endpoint.
   */
  synchronized JSONObject sayOnly(String text,String locale)throws Exception{
    if(active!=this||!speakerReady)throw new IllegalStateException("Speaker not ready");
    if(text==null||text.isBlank()||text.length()>700||
       locale==null||!locale.matches("[a-z]{2}(-[A-Z]{2})?"))
      throw new IllegalArgumentException("Invalid spoken reply");
    if("listening".equals(phase)||"processing".equals(phase)||"speaking".equals(phase))
      throw new IllegalStateException("Voice conversation is busy");
    acquireAudioFocus();
    try{keepCpuForExchange();}catch(Exception e){releaseAudioFocus();throw e;}
    speakOnly=true;ownerCommandMode=false;consumed=true;
    speakerPlaybackStarted=false;speakerPlaybackCompleted=false;
    String id="spoken-reply-"+System.currentTimeMillis();
    questionId=id;question=text;transcript="";
    state("speaking","");
    ui.post(()->{scheduleDeadline(id,SPEAKER_TIMEOUT_MS);speakNow(text,locale,id);});
    return new JSONObject().put("ok",true).put("phase","speaking").put("speech_id",id);
  }
  private void dispatchOwnerVoiceRequest(String spoken){
    ControlAccessibilityService access=ControlAccessibilityService.active;
    if(access==null){
      lastVoiceDispatch="accessibility_unavailable";
      state("failed","ChatGPT input access unavailable for voice request");
      return;
    }
    // Restore actual ChatGPT application; do not send into another app.
    for(int attempt=0;attempt<12;attempt++){
      if(active!=this)return;
      if(!"com.openai.chatgpt".equals(access.currentPackage()))
        access.requestChatForeground();
      else{
        JSONObject focus=access.prepareChatKeyboard();
        if(focus.optBoolean("ready",false)){
          // Spoken text is a user command to ChatGPT, not a queued checkpoint.
          JSONObject send=access.sendChatMessage(
            "ASTERION CONTROL — OWNER VOICE REQUEST\n"+
            "Spoken instruction: "+spoken+"\n"+
            "Execute the authorized request using Asterion Control. "+
            "Use the speaker endpoint for a spoken reply, and ask a "+
            "microphone question only if a response is required.");
          if(send.optBoolean("sent",false)){
            lastVoiceDispatch="submitted_unverified";
            consumed=true;state("delivered","");
          }else{
            lastVoiceDispatch="not_sent";
            state("failed",send.optString("reason","Voice request could not be sent"));
          }
          return;
        }
      }
      try{Thread.sleep(650);}catch(InterruptedException e){
        Thread.currentThread().interrupt();return;
      }
    }
    lastVoiceDispatch="chatgpt_input_unavailable";
    state("failed","ChatGPT writing bar could not be focused");
  }
  private static String speechError(int code){
    switch(code){
      case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
        return "Microphone access denied by Android";
      case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
        return "Offline recognition does not support the requested language";
      case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
        return "Android speech language is unavailable; install or enable its language model";
      case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
        return "Android speech recognizer is busy";
      case SpeechRecognizer.ERROR_NO_MATCH:
        return "No matching speech recognized";
      case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
        return "No speech heard before the recognition timeout";
      case SpeechRecognizer.ERROR_AUDIO:
        return "Android microphone audio capture failed";
      case SpeechRecognizer.ERROR_CLIENT:
        return "Android recognition service rejected the session (client error 5)";
      default:
        return "Android speech recognition error "+code;
    }
  }
  JSONObject report()throws Exception {
    PowerManager power=(PowerManager)getSystemService(POWER_SERVICE);
    KeyguardManager lock=(KeyguardManager)getSystemService(KEYGUARD_SERVICE);
    return new JSONObject().put("screen_interactive",power!=null&&power.isInteractive())
      .put("device_locked",lock!=null&&lock.isDeviceLocked())
      .put("bounded_cpu_wake_held",speechWakeLock!=null&&speechWakeLock.isHeld())
      .put("screen_off_mode","active_foreground_microphone_session")
      .put("enabled",active==this)
      .put("phase",phase).put("question_id",questionId)
      .put("question",question).put("transcript",transcript)
      .put("microphone_active",microphoneActive)
      .put("voice_control_active",ownerCommandMode)
      .put("last_voice_dispatch",lastVoiceDispatch)
      .put("speaker_started",speakerPlaybackStarted)
      .put("speaker_finished",speakerPlaybackCompleted)
      .put("answer_pending_ack","answered".equals(phase)&&!consumed)
      .put("error",error).put("updated_at_ms",updatedAt)
      .put("on_device_recognition",Build.VERSION.SDK_INT>=31
         && SpeechRecognizer.isOnDeviceRecognitionAvailable(this))
       .put("android_system_recognition",SpeechRecognizer.isRecognitionAvailable(this))
       .put("recognizer_backend",recognizerBackend)
      .put("voice",chosenVoice).put("voice_quality",chosenVoiceQuality)
      .put("speech_rate",naturalRate).put("speech_pitch",naturalPitch)
      .put("exclusive_audio_focus",exclusiveSpeechAudio);
  }
  @Override public void onDestroy(){
    active=null;
    ui.post(()->{
      clearDeadline();microphoneActive=false;
      if(listener!=null){listener.destroy();listener=null;}
      if(speaker!=null){speaker.stop();speaker.shutdown();}
      releaseAudioFocus();
      releaseCpuForExchange();
    });
    voiceControlWorker.shutdownNow();
    super.onDestroy();
  }
  @Override public IBinder onBind(Intent intent){return null;}
}
