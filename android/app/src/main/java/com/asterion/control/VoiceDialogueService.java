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
  private void state(String value,String message){
    phase=value;error=message;updatedAt=System.currentTimeMillis();
  }
  @Override public void onCreate(){
    super.onCreate();
    speaker=new TextToSpeech(this,status->{
      speakerReady=status==TextToSpeech.SUCCESS;
      state(speakerReady?"ready":"unavailable",
        speakerReady?"":"Android text-to-speech engine unavailable");
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
    if(!speakerReady)state("initializing","");
    return START_NOT_STICKY;
  }
  JSONObject ask(String text,String locale)throws Exception {
    if(active!=this)throw new IllegalStateException("Enable voice questions from the phone first");
    if(!speakerReady)throw new IllegalStateException("Android speaker not ready");
    if(text==null||text.isBlank()||text.length()>700)
      throw new IllegalArgumentException("Question must contain 1-700 characters");
    if(!locale.matches("[a-z]{2}(-[A-Z]{2})?"))
      throw new IllegalArgumentException("Invalid speech locale");
    if("speaking".equals(phase)||"listening".equals(phase))
      throw new IllegalStateException("Another voice exchange is active");
    if(Build.VERSION.SDK_INT<31||!SpeechRecognizer.isOnDeviceRecognitionAvailable(this))
      throw new IllegalStateException("Android on-device speech recognition is unavailable");
    question=text;transcript="";questionId=UUID.randomUUID().toString();
    listeningLocale=locale;
    state("speaking","");
    ui.post(()->speakNow(text,locale,questionId));
    return new JSONObject().put("ok",true).put("question_id",questionId)
      .put("phase","speaking");
  }
  private void speakNow(String text,String locale,String id){
    if(active!=this)return;
    Locale language=Locale.forLanguageTag(locale);
    if(speaker.setLanguage(language)==TextToSpeech.LANG_MISSING_DATA){
      state("failed","Speech voice data not installed");return;
    }
    speaker.setOnUtteranceProgressListener(new UtteranceProgressListener(){
      @Override public void onStart(String utteranceId){}
      @Override public void onDone(String utteranceId){
        if(id.equals(utteranceId))ui.post(()->startListening(locale,id));
      }
      @Override public void onError(String utteranceId){
        if(id.equals(utteranceId))state("failed","Android speech playback failed");
      }
    });
    int response=speaker.speak(text,TextToSpeech.QUEUE_FLUSH,null,id);
    if(response!=TextToSpeech.SUCCESS)state("failed","Could not start speaker");
  }
  private void startListening(String locale,String id){
    if(active!=this||!id.equals(questionId))return;
    try {
      if(listener!=null){listener.destroy();listener=null;}
      listener=SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
      listener.setRecognitionListener(new RecognitionListener(){
        @Override public void onReadyForSpeech(Bundle extras){state("listening","");}
        @Override public void onBeginningOfSpeech(){}
        @Override public void onRmsChanged(float rmsdB){}
        @Override public void onBufferReceived(byte[] data){}
        @Override public void onEndOfSpeech(){state("processing","");}
        @Override public void onError(int code){state("failed","Recognition failed: "+code);}
        @Override public void onResults(Bundle results){
          ArrayList<String> phrases=results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
          transcript=phrases==null||phrases.isEmpty()?"":phrases.get(0);
          state(transcript.isEmpty()?"failed":"answered",
                transcript.isEmpty()?"No recognized speech":"");
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
    } catch(Exception e){state("failed",e.getClass().getSimpleName());}
  }
  JSONObject report()throws Exception {
    return new JSONObject().put("enabled",active==this)
      .put("phase",phase).put("question_id",questionId)
      .put("question",question).put("transcript",transcript)
      .put("error",error).put("updated_at_ms",updatedAt)
      .put("on_device_recognition",Build.VERSION.SDK_INT>=31
         && SpeechRecognizer.isOnDeviceRecognitionAvailable(this));
  }
  @Override public void onDestroy(){
    active=null;
    ui.post(()->{
      if(listener!=null){listener.destroy();listener=null;}
      if(speaker!=null){speaker.stop();speaker.shutdown();}
    });
    super.onDestroy();
  }
  @Override public IBinder onBind(Intent intent){return null;}
}
