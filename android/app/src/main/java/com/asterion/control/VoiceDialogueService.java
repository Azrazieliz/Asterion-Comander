package com.asterion.control;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import org.json.JSONObject;
import java.util.ArrayList;
import java.util.Locale;
import java.util.UUID;

/**
 * Owner-started Android foreground speaker -> on-device microphone Q&A.
 * No remote speech API, no recording storage and no continuous hot microphone.
 */
public final class VoiceDialogueService extends Service {
  public static volatile VoiceDialogueService active;
  private final Handler ui=new Handler(Looper.getMainLooper());
  private TextToSpeech speaker;
  private SpeechRecognizer listener;
  private volatile String phase="stopped", question="", transcript="", error="";
  private volatile long updatedAt=0L;
  private volatile String questionId="";
  private volatile boolean speakerReady=false;
  private String listeningLocale="en-US";
  private static final int NOTIFICATION_ID=2107;
  private static final long SPEAKER_TIMEOUT_MS=90000L;
  private static final long ANSWER_TIMEOUT_MS=45000L;
  private volatile boolean consumed=true;
  private volatile boolean microphoneActive=false;
  private volatile boolean speakerPlaybackStarted=false;
  private volatile boolean speakerPlaybackCompleted=false;
  private volatile boolean pendingLocalTest=false;
  private void localVoiceTest(){
    if(active!=this)return;
    try{
      String prompt="Asterion Control speaker test. Please answer aloud: test one two three.";
      String id="selftest-"+System.currentTimeMillis();
      // Even without an installed offline speech pack, TEST must exercise the
      // speaker and then report the *specific* missing microphone prerequisite.
      if(Build.VERSION.SDK_INT>=31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)){
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
  private void state(String value,String message){
    phase=value;error=message;updatedAt=System.currentTimeMillis();
  }
  @Override public void onCreate(){
    super.onCreate();
    speaker=new TextToSpeech(this,status->{
      speakerReady=status==TextToSpeech.SUCCESS;
      state(speakerReady?"ready":"unavailable",
        speakerReady?"":"Android text-to-speech engine unavailable");
      if(speakerReady&&pendingLocalTest&&active==this){
        pendingLocalTest=false;
        ui.post(this::localVoiceTest);
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
    return new Notification.Builder(this,"asterion_voice")
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setContentTitle("Asterion voice questions enabled")
      .setContentText("Only listens after a spoken question. Stop at any time.")
      .addAction(android.R.drawable.ic_menu_close_clear_cancel,"Stop microphone session",action)
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
    if(intent!=null&&"TEST".equals(intent.getAction())){
      pendingLocalTest=true;
      if(speakerReady){pendingLocalTest=false;ui.post(this::localVoiceTest);}
      else state("initializing","Awaiting Android text-to-speech startup");
    }else if(!speakerReady)state("initializing","");
    return START_NOT_STICKY;
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
    if(Build.VERSION.SDK_INT<31||!SpeechRecognizer.isOnDeviceRecognitionAvailable(this))
      throw new IllegalStateException("Android on-device speech recognition is unavailable");
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED)
      throw new IllegalStateException("Android microphone consent is missing");
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
  private void speakNow(String text,String locale,String id){
    if(active!=this)return;
    Locale language=Locale.forLanguageTag(locale);
    speaker.setAudioAttributes(new android.media.AudioAttributes.Builder()
      .setUsage(android.media.AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
      .setContentType(android.media.AudioAttributes.CONTENT_TYPE_SPEECH).build());
    int languageResult=speaker.setLanguage(language);
    if(languageResult==TextToSpeech.LANG_MISSING_DATA || languageResult==TextToSpeech.LANG_NOT_SUPPORTED){
      clearDeadline();state("failed","Requested speech voice data is unavailable");return;
    }
    speaker.setOnUtteranceProgressListener(new UtteranceProgressListener(){
      @Override public void onStart(String utteranceId){
        if(id.equals(utteranceId))speakerPlaybackStarted=true;
      }
      @Override public void onDone(String utteranceId){
        if(id.equals(utteranceId)){
          speakerPlaybackCompleted=true;
          ui.post(()->startListening(locale,id));
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
    if(Build.VERSION.SDK_INT<31||!SpeechRecognizer.isOnDeviceRecognitionAvailable(this)){
      clearDeadline();
      microphoneActive=false;
      state("failed","Speaker playback completed; Android offline speech recognition is not installed or enabled");
      return;
    }
    try {
      if(listener!=null){listener.destroy();listener=null;}
      listener=SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
      scheduleDeadline(id,ANSWER_TIMEOUT_MS);
      listener.setRecognitionListener(new RecognitionListener(){
        @Override public void onReadyForSpeech(Bundle extras){
          microphoneActive=true;state("listening","");
        }
        @Override public void onBeginningOfSpeech(){}
        @Override public void onRmsChanged(float rmsdB){}
        @Override public void onBufferReceived(byte[] data){}
        @Override public void onEndOfSpeech(){state("processing","");}
        @Override public void onError(int code){
          if(!id.equals(questionId))return;
          microphoneActive=false;clearDeadline();
          state("failed",speechError(code));
          ui.post(()->{if(listener!=null){listener.destroy();listener=null;}});
        }
        @Override public void onResults(Bundle results){
          if(!id.equals(questionId))return;
          microphoneActive=false;clearDeadline();
          ArrayList<String> phrases=results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
          transcript=phrases==null||phrases.isEmpty()?"":phrases.get(0);
          state(transcript.isEmpty()?"failed":"answered",
                transcript.isEmpty()?"No recognized speech":"");
          ui.post(()->{if(listener!=null){listener.destroy();listener=null;}});
        }
        @Override public void onPartialResults(Bundle results){}
        @Override public void onEvent(int type,Bundle params){}
      });
      Intent request=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
      request.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
          RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
      request.putExtra(RecognizerIntent.EXTRA_LANGUAGE,locale);
      request.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS,1);
      state("listening","");
      listener.startListening(request);
    } catch(Exception e){
      clearDeadline();microphoneActive=false;
      if(listener!=null){listener.destroy();listener=null;}
      state("failed",e.getClass().getSimpleName());
    }
  }
  private static String speechError(int code){
    switch(code){
      case SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS:
        return "Microphone access denied by Android";
      case SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED:
        return "Offline recognition does not support the requested language";
      case SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE:
        return "Offline speech language pack is not installed";
      case SpeechRecognizer.ERROR_RECOGNIZER_BUSY:
        return "Android speech recognizer is busy";
      case SpeechRecognizer.ERROR_NO_MATCH:
        return "No matching speech recognized";
      case SpeechRecognizer.ERROR_SPEECH_TIMEOUT:
        return "No speech heard before the recognition timeout";
      case SpeechRecognizer.ERROR_AUDIO:
        return "Android microphone audio capture failed";
      default:
        return "Android speech recognition error "+code;
    }
  }
  JSONObject report()throws Exception {
    return new JSONObject().put("enabled",active==this)
      .put("phase",phase).put("question_id",questionId)
      .put("question",question).put("transcript",transcript)
      .put("microphone_active",microphoneActive)
      .put("speaker_started",speakerPlaybackStarted)
      .put("speaker_finished",speakerPlaybackCompleted)
      .put("answer_pending_ack","answered".equals(phase)&&!consumed)
      .put("error",error).put("updated_at_ms",updatedAt)
      .put("on_device_recognition",Build.VERSION.SDK_INT>=31
         && SpeechRecognizer.isOnDeviceRecognitionAvailable(this));
  }
  @Override public void onDestroy(){
    active=null;
    ui.post(()->{
      clearDeadline();microphoneActive=false;
      if(listener!=null){listener.destroy();listener=null;}
      if(speaker!=null){speaker.stop();speaker.shutdown();}
    });
    super.onDestroy();
  }
  @Override public IBinder onBind(Intent intent){return null;}
}
