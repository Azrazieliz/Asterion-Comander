package com.asterion.control;

import android.app.ActivityManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.ServiceInfo;
import android.os.BatteryManager;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.StatFs;
import android.util.DisplayMetrics;
import android.view.WindowManager;
import org.json.JSONObject;
import org.json.JSONArray;
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** User-started LAN agent: bounded HTTP, bearer authentication, explicit foreground status. */
public final class AgentService extends Service {
  public static final int PORT = 8973;
  public static volatile boolean running = false;
  private volatile boolean alive = false;
  private ServerSocket server;
  private Thread acceptThread;
  private final ExecutorService clients=Executors.newFixedThreadPool(6);
  private TransferStore transfers;
  private ContinuationLedger continuation;
  private ContinuationCycle cycles;
  private final java.util.concurrent.ScheduledExecutorService observer =
      java.util.concurrent.Executors.newSingleThreadScheduledExecutor();
  private final java.util.concurrent.ScheduledExecutorService cycleSupervisor =
      java.util.concurrent.Executors.newSingleThreadScheduledExecutor();
  // Independent worker: GitHub HTTP never stalls local performance observation.
  // Does nothing until the owner explicitly enables the encrypted private bridge.
  private final java.util.concurrent.ScheduledExecutorService phoneBridgePoller =
      java.util.concurrent.Executors.newSingleThreadScheduledExecutor();
   private android.net.ConnectivityManager networkManager;
  private android.net.ConnectivityManager.NetworkCallback networkCallback;
  private final java.util.concurrent.atomic.AtomicLong lastNetworkWake =
      new java.util.concurrent.atomic.AtomicLong(0);
  private void wakePrivateBridge(){
    long now=android.os.SystemClock.elapsedRealtime();
    long previous=lastNetworkWake.get();
    if(now-previous<5000L||!lastNetworkWake.compareAndSet(previous,now))return;
    PhoneDirectMcp.networkChanged();
  }
  @Override public void onCreate(){
    super.onCreate();
    transfers=new TransferStore(this);
    continuation=ContinuationLedger.get(this);
    try{continuation.recover();}catch(Exception ignored){}
    cycles=ContinuationCycle.get(this);
    try{cycles.recover();}catch(Exception ignored){}
    // Control owns the durable transport cycle; ChatGPT supplies the actual
    // reasoning and explicit ACK/DONE marker. Never infer success from a tap.
    cycleSupervisor.scheduleWithFixedDelay(()->{
      try{if(cycles!=null)cycles.tick();}
      catch(Exception e){android.util.Log.w("AsterionCycle","Cycle tick deferred",e);}
    },5,4,java.util.concurrent.TimeUnit.SECONDS);
    observer.scheduleWithFixedDelay(()->{
      try{PerformanceManager.tick(this);AppObservation.sample(this);}catch(Exception ignored){}
    },3,3,java.util.concurrent.TimeUnit.SECONDS);
    // Optional direct phone-to-GitHub transport. No Windows worker, MCP or
    // tunnel required. All commands run inside AndroidMcp with local consent.
    // This scheduler is separate from performance sampling and survives UI close.
    phoneBridgePoller.scheduleWithFixedDelay(()->{
      try { PhoneGitBridge.poll(this); }
      catch(Exception e){android.util.Log.w("AsterionAgent","Phone bridge poll failed",e);}
    },1,3,java.util.concurrent.TimeUnit.SECONDS);
    // The standard phone-initiated TLS transport remains separately available.
    try{
      networkManager=(android.net.ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
      networkCallback=new android.net.ConnectivityManager.NetworkCallback(){
        @Override public void onAvailable(android.net.Network network){wakePrivateBridge();}
        @Override public void onCapabilitiesChanged(android.net.Network network,
            android.net.NetworkCapabilities caps){
          if(caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED))
            wakePrivateBridge();
        }
      };
      networkManager.registerDefaultNetworkCallback(networkCallback);
    }catch(Exception e){
      android.util.Log.w("AsterionAgent","Network callback unavailable; scheduled polling remains",e);
    }
  }
  public static final String PREF_REMOTE_ENABLED="remote_enabled";
  public static String token(Context c){
    SharedPreferences p=c.getSharedPreferences("agent",MODE_PRIVATE);
    String saved=p.getString("token",null);
    if(saved!=null && saved.length()>32)return saved;
    byte[] random=new byte[32];new SecureRandom().nextBytes(random);
    saved=Base64.getUrlEncoder().withoutPadding().encodeToString(random);
    p.edit().putString("token",saved).apply();return saved;
  }
  /** Revoke leaked/old access keys without displaying the replacement in UI. */
  public static String rotateToken(Context c){
    byte[] random=new byte[32];new SecureRandom().nextBytes(random);
    String value=Base64.getUrlEncoder().withoutPadding().encodeToString(random);
    c.getSharedPreferences("agent",MODE_PRIVATE).edit().putString("token",value).apply();
    return value;
  }
  private Notification notification(){
    getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("asterion_agent","Asterion remote control",NotificationManager.IMPORTANCE_LOW));
    Intent open=new Intent(this,MainActivity.class);
    open.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP);
    PendingIntent resume=PendingIntent.getActivity(this,2101,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    return new Notification.Builder(this,"asterion_agent").setSmallIcon(android.R.drawable.ic_menu_manage)
      .setContentTitle("Asterion Control active")
      .setContentText("Phone control stays active when this app is in the background. Tap to manage.")
      .setContentIntent(resume).setCategory(Notification.CATEGORY_SERVICE)
      .setOngoing(true).build();
  }
  @Override public synchronized int onStartCommand(Intent i,int f,int id){
    SharedPreferences remotePrefs=getSharedPreferences("agent",MODE_PRIVATE);
    if(i!=null&&"STOP".equals(i.getAction())){
      remotePrefs.edit().putBoolean(PREF_REMOTE_ENABLED,false).apply();
      stopSelf();return START_NOT_STICKY;
    }
    // START_STICKY is only honored for a service deliberately enabled by the owner.
    if(i==null&&!remotePrefs.getBoolean(PREF_REMOTE_ENABLED,false)){
      stopSelf();return START_NOT_STICKY;
    }
    remotePrefs.edit().putBoolean(PREF_REMOTE_ENABLED,true).apply();
    startForeground(2101,notification(),ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
    if(!alive||acceptThread==null||!acceptThread.isAlive()){
      alive=true;acceptThread=new Thread(this::serve,"asterion-agent");
      acceptThread.start();
    }
    running=true;PhoneDirectMcp.start(this);return START_STICKY;
  }
  /** Recover from a transient socket failure; do not silently disable the owner's session. */
  private boolean privatePeer(java.net.InetAddress peer){
    if(peer==null)return false;
    if(peer.isLoopbackAddress()||peer.isSiteLocalAddress())return true;
    byte[] bytes=peer.getAddress();
    if(bytes.length==4){
      int first=bytes[0]&255, second=bytes[1]&255;
      return first==100 && second>=64 && second<=127; // Private CGNAT/VPN
    }
    if(bytes.length==16)return (bytes[0]&254)==252; // IPv6 ULA fc00::/7
    return false;
  }
  private void serve(){
    while(alive){
      try(ServerSocket s=new ServerSocket(PORT)){
        server=s;s.setReuseAddress(true);
        while(alive){
          Socket client=s.accept();
          if(!privatePeer(client.getInetAddress())){
            try{client.close();}catch(Exception ignored){}
            continue; // Never expose native MCP/control over public IP directly.
          }
          client.setSoTimeout(8500);
          clients.execute(()->handle(client));
        }
      }catch(Exception e){
        if(alive){
          android.util.Log.w("AsterionAgent","Listener will retry after network failure",e);
          try{Thread.sleep(1800);}catch(InterruptedException interrupted){Thread.currentThread().interrupt();break;}
        }
      }
    }
    alive=false;running=false;
  }
  private String line(InputStream in)throws Exception{
    ByteArrayOutputStream b=new ByteArrayOutputStream();int c;
    while((c=in.read())!=-1){if(c==10)break;if(c!=13)b.write(c);if(b.size()>8192)throw new IllegalArgumentException("Header too long");}
    return b.toString("UTF-8");
  }
  private void write(OutputStream o,int status,String kind,byte[] body)throws Exception{
    String label=status==200?"OK":status==202?"Accepted":status==405?"Method Not Allowed":status==401?"Unauthorized":status==403?"Forbidden":status==404?"Not Found":status==503?"Unavailable":"Bad Request";
    String head="HTTP/1.1 "+status+" "+label+"\r\nContent-Type: "+kind+"\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
    o.write(head.getBytes(StandardCharsets.UTF_8));o.write(body);o.flush();
  }
  private void json(OutputStream o,int status,JSONObject body)throws Exception {write(o,status,"application/json; charset=utf-8",body.toString().getBytes(StandardCharsets.UTF_8));}
  private JSONObject error(String detail)throws Exception{return new JSONObject().put("error",detail);}
  private void handle(Socket socket){try(Socket s=socket){
    InputStream in=new BufferedInputStream(s.getInputStream());OutputStream out=new BufferedOutputStream(s.getOutputStream());
    String first=line(in);String[] request=first.split(" ");if(request.length<2){json(out,400,error("Malformed request"));return;}
    String method=request[0],path=request[1].split("\\?")[0];
    String auth="";int len=0;long offset=-1;
    for(int i=0;i<64;i++){String h=line(in);if(h.isEmpty())break;int at=h.indexOf(':');if(at<0)continue;
      String key=h.substring(0,at).trim().toLowerCase(),val=h.substring(at+1).trim();
      if(key.equals("authorization"))auth=val;
      if(key.equals("content-length"))len=Integer.parseInt(val);
      if(key.equals("x-transfer-offset"))offset=Long.parseLong(val);
    }
    if(!auth.equals("Bearer "+token(this))){json(out,401,error("Unauthorized"));return;}
    if(method.equals("PUT")&&path.startsWith("/transfer/chunk/")){
      String id=path.substring("/transfer/chunk/".length());
      try{
        if(len<=0||len>TransferStore.CHUNK_MAX||offset<0)
          throw new IllegalArgumentException("Invalid binary chunk headers");
        json(out,200,transfers.append(id,offset,in,len));
      }catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(len<0||len>65536){json(out,400,error("Body too large"));return;}
    byte[] data=in.readNBytes(len);
    if(data.length!=len){json(out,400,error("Truncated JSON request"));return;}
    JSONObject body=len>0?new JSONObject(new String(data,StandardCharsets.UTF_8)):new JSONObject();
    // Android-native MCP is stateless, bearer-authenticated and LAN-only here.
    // Public HTTPS ingress must be deployed separately; do not publish this port.
    if(path.equals("/mcp")){
      if(!method.equals("POST")){
        write(out,405,"application/json; charset=utf-8",new byte[0]);return;
      }
      JSONObject reply=AndroidMcp.handle(this,body);
      if(reply==null){write(out,202,"application/json; charset=utf-8",new byte[0]);return;}
      json(out,200,reply);return;
    }
    // Phone-resident checkpoint state. Owner must first opt in using Control's
    // native UI; HTTP bearer possession alone cannot enable self-continuation.
    // User-enabled Asterion app recording; only native MediaProjection frames.
    // Foreground voice exchange is independently owner-enabled on Android.
    if(method.equals("GET")&&path.equals("/voice/settings")){
      try{VoiceDialogueService v=VoiceDialogueService.active;
        json(out,v==null?503:200,v==null?error("Enable voice session first"):v.voiceSettings());}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/voice/settings")){
      try{VoiceDialogueService v=VoiceDialogueService.active;
        json(out,v==null?503:200,v==null?error("Enable voice session first"):v.configureVoiceSettings(body));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/voice/status")){
      try {
        VoiceDialogueService voice=VoiceDialogueService.active;
        json(out,200,voice==null?new JSONObject().put("enabled",false)
          .put("phase","stopped"):voice.report());
      } catch(Exception e){json(out,400,error("Voice status unavailable"));}
      return;
    }
    if(method.equals("POST")&&path.equals("/voice/enable")){
      try{json(out,200,VoiceDialogueService.enableFromOwnerApi(this));}
      catch(Exception e){json(out,409,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/voice/stop")){
      try{json(out,200,VoiceDialogueService.stopFromOwnerApi(this));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/voice/command")){
      try {
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null){json(out,503,error("Enable voice session first"));return;}
        json(out,200,voice.beginOwnerVoiceControl(body.optString("locale","en-US")));
      }catch(Exception e){json(out,409,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/voice/say")){
      try {
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null){json(out,503,error("Enable voice session first"));return;}
        json(out,200,voice.sayOnly(body.getString("text"),body.optString("locale","en-US")));
      }catch(Exception e){json(out,409,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/voice/question")){
      try {
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null){json(out,503,error("Enable voice dialogue from the phone"));return;}
        json(out,200,voice.ask(body.getString("text"),body.optString("locale","en-US"),
            body.optString("question_id","")));
      } catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/voice/ack")){
      try {
        VoiceDialogueService voice=VoiceDialogueService.active;
        if(voice==null){json(out,503,error("Voice not enabled"));return;}
        json(out,200,voice.acknowledge(body.getString("question_id")));
      }catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/observation/timeline")){
      try{json(out,200,AppObservation.timeline(this,100));}
      catch(Exception e){json(out,400,error("Observation timeline unavailable"));}return;
    }
    if(method.equals("GET")&&path.startsWith("/observation/frame/")){
      String id=path.substring("/observation/frame/".length());
      byte[] jpeg=AppObservation.recordedFrame(this,id);
      if(jpeg==null){json(out,404,error("Recorded frame not available"));return;}
      write(out,200,"image/jpeg",jpeg);return;
    }
    if(method.equals("GET")&&path.equals("/observation/status")){
      try{json(out,200,AppObservation.status(this));}
      catch(Exception e){json(out,400,error("Observation status unavailable"));}return;
    }
    if(method.equals("GET")&&path.equals("/observation/events")){
      try{json(out,200,AppObservation.recentEvents(this,80));}
      catch(Exception e){json(out,400,error("Observation events unavailable"));}return;
    }
    if(method.equals("GET")&&path.equals("/observation/frame")){
      byte[] jpeg=AppObservation.latestRecordedFrame(this);
      if(jpeg==null){json(out,503,error("No recorded frame available"));return;}
      write(out,200,"image/jpeg",jpeg);return;
    }
    if(method.equals("GET")&&path.equals("/github-bridge/status")){
      try{json(out,200,PhoneDirectMcp.status());}
      catch(Exception e){json(out,400,error("Private bridge status unavailable"));}
      return;
    }
    if(method.equals("GET")&&path.equals("/app-bridge/apps")){
      try{json(out,200,AppBridge.list(this));}
      catch(Exception e){json(out,400,error("App bridge discovery unavailable"));}return;
    }
    if(method.equals("POST")&&path.equals("/app-bridge/invoke")){
      try{json(out,200,AppBridge.invoke(this,body));}
      catch(SecurityException e){json(out,403,error(e.getMessage()));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/apps")){
      try{json(out,200,AppCatalog.list(this));}
      catch(Exception e){json(out,400,error("Application catalogue unavailable"));}return;
    }
    if(method.equals("POST")&&path.equals("/apps/launch")){
      try{json(out,200,AppCatalog.requestLaunch(this,body.getString("package")));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/network/status")){
      try{json(out,200,TransportConnectivity.report(this));}
      catch(Exception e){json(out,400,error("Network status unavailable"));}return;
    }
    if(method.equals("GET")&&path.equals("/cycles/status")){
      try{json(out,200,new JSONObject().put("controller","asterion-control")
        .put("android_autonomous_cycle",true)
        .put("cycle",cycles.status())
        .put("checkpoint",continuation.status().optString("state","idle")));}
      catch(Exception e){json(out,400,error("Cycle status unavailable"));}
      return;
    }
    if(method.equals("POST")&&path.equals("/cycles/start")){
      try{
        continuation.configure(true);
        json(out,200,cycles.start(body));
      }catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/cycles/pause")){
      try{json(out,200,cycles.pause());}
      catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/cycles/resume")){
      try{json(out,200,cycles.resume());}
      catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/cycles/stop")){
      try{json(out,200,cycles.stop());}
      catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/cycles/tick")){
      try{json(out,200,cycles.tick());}
      catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/continuation/ack")){
      try{json(out,200,continuation.acknowledge(
        body.getString("checkpoint_id"),body.getString("response_receipt")));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/continuation/cancel")){
      try{json(out,200,continuation.cancel());}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/chat/direct")){
      try{
        String message=body.optString("message","");
        if(message.isBlank()||message.length()>3000)
          throw new IllegalArgumentException("Direct ChatGPT message must be 1-3000 characters");
        ControlAccessibilityService control=ControlAccessibilityService.active;
        if(control==null){json(out,503,error("Accessibility permission unavailable"));return;}
        if(!"com.openai.chatgpt".equals(control.currentPackage())){
          JSONObject requested=control.requestChatForeground();
          json(out,200,new JSONObject().put("sent",false)
            .put("stage","foreground_requested").put("details",requested));
        }else{
          JSONObject keyboard=control.prepareChatKeyboard();
          if(!keyboard.optBoolean("ready",false)){
            json(out,200,new JSONObject().put("sent",false)
              .put("stage","writing_bar_focus_requested").put("details",keyboard));
          }else{
            JSONObject outcome=control.sendChatMessage(message);
            json(out,200,outcome.put("stage",
              outcome.optBoolean("sent",false)?"submitted_unverified":"input_not_submitted"));
          }
        }
      }catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.equals("/chat/new")){
      ControlAccessibilityService control=ControlAccessibilityService.active;
      if(control==null){json(out,503,error("Android Accessibility unavailable"));return;}
      try{json(out,200,control.requestNewChat());}
      catch(Exception e){json(out,400,error("ChatGPT navigation unavailable"));}return;
    }
    if(method.equals("GET")&&path.equals("/continuation/status")){
      try { JSONObject state=continuation.status();state.remove("pending");json(out,200,state); }
      catch(Exception e){json(out,400,error("Continuation status unavailable"));}return;
    }
    if(method.equals("POST")&&path.equals("/continuation/queue")){
      try { json(out,200,continuation.queue(body)); }
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/continuation/dispatch")){
      try { json(out,200,continuation.dispatch()); }
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/transfer/start")){
      try{json(out,200,transfers.start(body));}catch(Exception e){json(out,400,error(e.getMessage()));}
      return;
    }
    if(method.equals("POST")&&path.startsWith("/transfer/finish/")){
      try{json(out,200,transfers.finish(path.substring("/transfer/finish/".length())));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.startsWith("/transfer/cancel/")){
      try{json(out,200,transfers.cancel(path.substring("/transfer/cancel/".length())));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/performance/status")){
      try{json(out,200,PerformanceManager.status(this));}
      catch(Exception e){json(out,400,error("Performance status unavailable"));}return;
    }
    if(method.equals("POST")&&path.equals("/performance/mode")){
      try{json(out,200,PerformanceManager.setMode(this,body.getString("mode")));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("POST")&&path.equals("/performance/optimize")){
      try{json(out,200,PerformanceManager.prioritizeForegroundNow(this));}
      catch(Exception e){json(out,400,error(e.getMessage()));}return;
    }
    if(method.equals("GET")&&path.equals("/diagnostics/logcat")){
      try{json(out,200,ownLogcat());}
      catch(Exception e){json(out,503,error("Own-process logcat unavailable"));}return;
    }
    if(method.equals("GET")&&path.equals("/health")){json(out,200,health());return;}
    if(method.equals("GET")&&path.equals("/ui")){
      ControlAccessibilityService a=ControlAccessibilityService.active;
      json(out,a==null?503:200,a==null?error("Accessibility not enabled"):a.dump());return;
    }
    if(method.equals("POST")&&path.equals("/input")){
      ControlAccessibilityService a=ControlAccessibilityService.active;
      if(a==null){json(out,503,error("Enable Asterion accessibility service"));return;}
      boolean ok=a.action(body);json(out,ok?200:400,new JSONObject().put("ok",ok));return;
    }
    if(method.equals("GET")&&path.equals("/screen")){
      byte[] b=CaptureService.latest;
      if(b==null){json(out,503,error("Start screen sharing on the phone"));return;}
      write(out,200,"image/jpeg",b);return;
    }
    if(method.equals("GET")&&path.equals("/stream")){
      out.write("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=asterionframe\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n".getBytes(StandardCharsets.UTF_8));out.flush();
      long lastSentAt=0L;
      while(alive&&!s.isClosed()){
        byte[] b=CaptureService.latest;
        long frameAt=CaptureService.latestAtMs;
        if(b!=null&&frameAt>lastSentAt){String h="--asterionframe\r\nContent-Type: image/jpeg\r\nContent-Length: "+b.length+"\r\n\r\n";
          out.write(h.getBytes(StandardCharsets.UTF_8));out.write(b);out.write("\r\n".getBytes(StandardCharsets.UTF_8));out.flush();lastSentAt=frameAt;}
        Thread.sleep(12);
      }return;
    }
    json(out,404,error("Unknown endpoint"));
  }catch(Exception e){android.util.Log.w("AsterionAgent","Client closed: "+e.getClass().getSimpleName());}}
  /** Owner-bearer-authenticated diagnostic, restricted to THIS app process.
   * Android does not grant ordinary apps other apps' or system-wide logcat.
   * Bounded output and redaction avoid leaking credentials into receipts.
   */
  JSONObject ownLogcat() throws Exception {
    int pid=android.os.Process.myPid();
    java.lang.Process process=new ProcessBuilder("logcat","-d","--pid="+pid,
      "-t","80","-v","brief").redirectErrorStream(true).start();
    boolean finished=process.waitFor(2,java.util.concurrent.TimeUnit.SECONDS);
    if(!finished){
      process.destroyForcibly();
      throw new IllegalStateException("Own-process logcat timed out");
    }
    byte[] raw=process.getInputStream().readNBytes(12288);
    String lines=new String(raw,StandardCharsets.UTF_8);
    if(process.exitValue()!=0)
      return new JSONObject().put("ok",false).put("scope","own_app_pid_only")
        .put("pid",pid).put("reason","Android logcat command unavailable");
    lines=lines.replaceAll("(?i)Bearer\\s+[A-Za-z0-9._=\\-]+","Bearer [REDACTED]")
      .replaceAll("(?i)(token|api_key|secret|password)\\s*[=:]\\s*[^\\s]+","$1=[REDACTED]")
      .replaceAll("(?i)github_pat_[A-Za-z0-9_]+","[REDACTED]");
    return new JSONObject().put("ok",true).put("scope","own_app_pid_only")
      .put("pid",pid).put("truncated",raw.length>=12288).put("log",lines);
  }
  JSONObject health()throws Exception {
    DisplayMetrics m=new DisplayMetrics();((WindowManager)getSystemService(WINDOW_SERVICE)).getDefaultDisplay().getRealMetrics(m);
    ActivityManager.MemoryInfo mem=new ActivityManager.MemoryInfo();((ActivityManager)getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(mem);
    Intent battery=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
    JSONObject b=new JSONObject();if(battery!=null){int level=battery.getIntExtra(BatteryManager.EXTRA_LEVEL,-1),scale=battery.getIntExtra(BatteryManager.EXTRA_SCALE,-1);
      b.put("percent",level>=0&&scale>0?level*100.0/scale:JSONObject.NULL);
      int temp=battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1);
      b.put("temperature_c",temp>=0?temp/10.0:JSONObject.NULL);
      b.put("charging",battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0)!=0);}
    PowerManager pm=(PowerManager)getSystemService(POWER_SERVICE);
    JSONObject thermals=new JSONObject().put("status",pm.getCurrentThermalStatus());
    if(Build.VERSION.SDK_INT>=30){float headroom=pm.getThermalHeadroom(10);thermals.put("headroom",Float.isNaN(headroom)?JSONObject.NULL:headroom);}
    StatFs disk=new StatFs(getFilesDir().getPath());
    return new JSONObject().put("ok",true).put("device",Build.MODEL).put("android",Build.VERSION.RELEASE)
      .put("accessible",ControlAccessibilityService.active!=null).put("capture",CaptureService.active)
      .put("screen_width",m.widthPixels).put("screen_height",m.heightPixels)
      .put("frame_width",CaptureService.width).put("frame_height",CaptureService.height)
      .put("battery",b).put("memory_available",mem.availMem).put("memory_total",mem.totalMem)
      .put("storage_available",disk.getAvailableBytes()).put("storage_total",disk.getTotalBytes())
      .put("thermals",thermals).put("performance",PerformanceManager.status(this))
      .put("remote_transport",TransportConnectivity.report(this));
  }
  @Override public void onDestroy(){alive=false;running=false;try{if(server!=null)server.close();}catch(Exception ignored){}
    if(networkManager!=null&&networkCallback!=null){
      try{networkManager.unregisterNetworkCallback(networkCallback);}catch(Exception ignored){}
    }
    PhoneDirectMcp.stop();clients.shutdownNow();observer.shutdownNow();
    cycleSupervisor.shutdownNow();phoneBridgePoller.shutdownNow();super.onDestroy();}
  @Override public IBinder onBind(Intent i){return null;}
}
