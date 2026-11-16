package com.asterion.control;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.ActivityManager;


import android.content.Context;
import android.content.ClipData;
import android.content.ClipDescription;
import android.content.ClipboardManager;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.media.projection.MediaProjectionManager;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.os.StatFs;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.ArrayAdapter;
import android.widget.ListView;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.NetworkInterface;
import java.net.URL;
import java.net.InetAddress;
import java.net.DatagramSocket;
import java.net.DatagramPacket;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Comparator;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorCompletionService;
import java.util.concurrent.CompletionService;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/** Asterion Control · native, phone-first command surface. Technical APIs remain hidden. */
public final class MainActivity extends Activity {
  private static volatile java.lang.ref.WeakReference<MainActivity> visibleActivity =
      new java.lang.ref.WeakReference<>(null);
  static Activity foregroundActivity() {
    MainActivity current=visibleActivity.get();
    return current==null||current.isFinishing()||current.isDestroyed()?null:current;
  }
  private static final int CAPTURE_REQUEST=112,NOTIFICATION_REQUEST=113,MICROPHONE_REQUEST=115,VPN_REQUEST=119,HUB_MICROPHONE_REQUEST=120,HUB_NOTIFICATION_REQUEST=121;
  private final Handler handler=new Handler(Looper.getMainLooper());
  private final ExecutorService io=Executors.newSingleThreadExecutor();
  private SharedPreferences prefs;
  private LinearLayout root,navbar,content,homeBody,healthBody,devicesBody;
  private FrameLayout stage;
  private final View[] pages=new View[5];
  private final LinearLayout[] tabButtons=new LinearLayout[5];
  private final DesignSystem.Icon[] tabIcons=new DesignSystem.Icon[5];
  private final TextView[] tabLabels=new TextView[5];
  private TextView headerStatus,pcConnection,homeAgent,homeBattery,homeMemory,homeThermal,homeConnectionIssue,connectionIssue;
  private TextView healthBattery,healthTemp,healthMemory,healthStorage,healthThermal,healthWifi,healthActionStatus,pcPerformanceActionStatus;
  private TextView remoteConnection,remotePlaceholder,agentConnection,captureConnection,accessConnection,phoneAddress,hostHealth,pairingFeedback,transferFeedback,updateFeedback,phoneBridgeFeedback;
  private String activeTransferId=null;
  private LinearLayout phoneAccessAction,phoneCaptureAction,phoneStopAction,transferCancelAction,voiceStartAction,voiceTalkAction,voiceStopAction;
  private DesignSystem.Meter batteryMeter,memoryMeter,storageMeter;
  private EditText serverUrl,serverToken,localAddress;
  private WebView web;
  private LinearLayout emptyRemote;
  private boolean advancedSetupVisible=false;
  private LinearLayout advancedSetup;
  private TextView privacyStatus;
  private TextView securitySummary;
  private int currentTab=0;
  private String pendingRemoteSection="desktop";
  private boolean webStarted=false,hostRefreshing=false;
  private boolean fullRepairInProgress=false;
  private String fullRepairTicket="";
  private String workerPhoneState="Windows-to-phone connection not checked yet";
  private long lastHostRefresh=0;
  private boolean destroyed=false;
  private boolean runVoiceTestAfterPermission=false;
  private TextView voiceTestStatus;
  private final Runnable ticker=new Runnable(){@Override public void run(){if(destroyed)return;updateHealth();handler.postDelayed(this,3500);}};

  private int dp(float x){return DesignSystem.dp(this,x);}
  private LinearLayout v(){return DesignSystem.vertical(this);}
  private LinearLayout h(){return DesignSystem.horizontal(this);}
  private TextView t(String value,float size,int color,boolean bold){return DesignSystem.text(this,value,size,color,bold);}
  private void gap(LinearLayout parent,int size){View g=new View(this);parent.addView(g,new LinearLayout.LayoutParams(1,dp(size)));}
  private void wide(LinearLayout p,View v){p.addView(v,new LinearLayout.LayoutParams(-1,-2));}
  private void margin(LinearLayout p,View v,int top){LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(-1,-2);a.topMargin=dp(top);p.addView(v,a);}
  private void pad(LinearLayout l,int x,int y){l.setPadding(dp(x),dp(y),dp(x),dp(y));}
  private void toast(String msg){Toast.makeText(this,msg,Toast.LENGTH_SHORT).show();}
  private DesignSystem.Icon icon(String name,int color,int size){DesignSystem.Icon icon=new DesignSystem.Icon(this,name,color);icon.setLayoutParams(new LinearLayout.LayoutParams(dp(size),dp(size)));return icon;}
  private TextView eyebrow(String value){return DesignSystem.eyebrow(this,value);}
  private LinearLayout card(){return DesignSystem.card(this);}
  private LinearLayout clickableCard(Runnable run){LinearLayout c=card();DesignSystem.clickable(c,this,DesignSystem.SURFACE,DesignSystem.EDGE,22);c.setOnClickListener(w->run.run());return c;}
  private void mark(LinearLayout target,int size){DesignSystem.AsterionMark icon=new DesignSystem.AsterionMark(this);target.addView(icon,new LinearLayout.LayoutParams(dp(size),dp(size)));}
  private View line(){View divider=new View(this);divider.setBackgroundColor(DesignSystem.EDGE);return divider;}
  private void sectionTitle(LinearLayout parent,String title,String subtitle){TextView a=t(title,27,DesignSystem.TEXT,true);margin(parent,a,3);if(subtitle!=null&&!subtitle.isEmpty()){TextView b=t(subtitle,12.5f,DesignSystem.MUTED,false);margin(parent,b,7);}}
  private TextView action(LinearLayout row,String name,String iconName,boolean primary,Runnable run){
    LinearLayout wrap=h();wrap.setGravity(Gravity.CENTER);wrap.setPadding(dp(13),dp(12),dp(13),dp(12));
    if(primary)wrap.setBackground(DesignSystem.gradient(this,0xFF755CF6,0xFF2B88CD,15));
    else DesignSystem.clickable(wrap,this,DesignSystem.SURFACE2,DesignSystem.EDGE,15);
    if(iconName!=null){wrap.addView(icon(iconName,primary?Color.WHITE:DesignSystem.PURPLE,17));View space=new View(this);wrap.addView(space,new LinearLayout.LayoutParams(dp(8),1));}
    TextView label=t(name,12.5f,DesignSystem.TEXT,true);wrap.addView(label);wrap.setOnClickListener(w->run.run());
    row.addView(wrap,new LinearLayout.LayoutParams(0,dp(45),1));return label;
  }
  private void button(LinearLayout parent,String label,String iconName,boolean primary,Runnable run){LinearLayout outer=h();action(outer,label,iconName,primary,run);wide(parent,outer);}
  private void twoActions(LinearLayout parent,String label1,String icon1,Runnable click1,String label2,String icon2,Runnable click2){
    LinearLayout r=h();action(r,label1,icon1,true,click1);View sp=new View(this);r.addView(sp,new LinearLayout.LayoutParams(dp(9),1));action(r,label2,icon2,false,click2);wide(parent,r);
  }
  private LinearLayout squareIcon(String name,int tint){LinearLayout box=h();box.setGravity(Gravity.CENTER);box.setBackground(DesignSystem.shape(this,0xFF282743,0,16));box.addView(icon(name,tint,25));box.setLayoutParams(new LinearLayout.LayoutParams(dp(52),dp(52)));return box;}
  private void rowTitle(LinearLayout parent,String head,String sub,View trailing){
    LinearLayout r=h();LinearLayout labels=v();labels.addView(t(head,17,DesignSystem.TEXT,true));TextView s=t(sub,12,DesignSystem.MUTED,false);s.setMaxLines(2);margin(labels,s,5);r.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
    if(trailing!=null){r.addView(trailing);}wide(parent,r);
  }
  private void metricRow(LinearLayout parent,String title,String desc,TextView current,int color){
    LinearLayout r=h();DesignSystem.Icon ic=icon("activity",color,19);r.addView(ic);LinearLayout values=v();values.setPadding(dp(12),0,0,0);values.addView(t(title,13,DesignSystem.MUTED,false));margin(values,current,4);r.addView(values,new LinearLayout.LayoutParams(0,-2,1));if(desc!=null){TextView tag=t(desc,11,DesignSystem.MUTED,false);r.addView(tag);}wide(parent,r);
  }
  @Override public void onCreate(Bundle b){super.onCreate(b);
    getWindow().setStatusBarColor(DesignSystem.BG);getWindow().setNavigationBarColor(DesignSystem.BG);
    prefs=getSharedPreferences("control",MODE_PRIVATE);
    // Existing pre-v0.6 keys may have been exposed on the former connections page.
    // Migrate once, revoke that key and re-register privately on next pairing.
    if(!prefs.getBoolean("agent_key_rotated_v06",false)){
      AgentService.rotateToken(this);
      prefs.edit().putBoolean("agent_key_rotated_v06",true).apply();
    }
    root=v();root.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,new int[]{0xFF10162A,0xFF090D1C,0xFF070A14}));setContentView(root);
    buildHeader();stage=new FrameLayout(this);root.addView(stage,new LinearLayout.LayoutParams(-1,0,1));
    pages[0]=scrollHome();pages[1]=remotePage();pages[2]=scrollHealth();pages[3]=scrollDevices();pages[4]=scrollTools();
    for(View page:pages){page.setVisibility(View.GONE);stage.addView(page,new FrameLayout.LayoutParams(-1,-1));}
    buildNav();show(0);updateHealth();handler.postDelayed(ticker,3500);
    // Owner-authorized continuation is persistent and controlled by the internal
    // ledger. No diagnostic/transport toggles belong on the everyday UI.
    if(!prefs.getBoolean("continuation_initial_default_v0913",false)){
      try{ContinuationLedger.get(this).configure(true);}catch(Exception ignored){}
      prefs.edit().putBoolean("continuation_initial_default_v0913",true).apply();
    }
    // Only check periodically; Android continues to approve every APK install.
    long checked=prefs.getLong("last_auto_update_check_ms",0L);
    if(System.currentTimeMillis()-checked>86400000L){
      prefs.edit().putLong("last_auto_update_check_ms",System.currentTimeMillis()).apply();
      handler.postDelayed(()->{if(!destroyed)UpdateManager.check(this,this::showUpdateFeedback);},3000);
    }
    if(!prefs.getString("url","").isEmpty()&&!prefs.getString("token","").isEmpty()){
      handler.postDelayed(()->{if(AgentService.running)registerPhone();},1500);
    }
  }
  private void buildHeader(){
    LinearLayout header=h();header.setPadding(dp(20),dp(16),dp(20),dp(14));mark(header,43);
    LinearLayout brand=v();brand.setPadding(dp(12),0,0,0);
    TextView name=t("ASTERION",17,DesignSystem.TEXT,true);name.setLetterSpacing(.13f);brand.addView(name);
    TextView sub=t("C O N T R O L",10.2f,DesignSystem.TEAL,true);margin(brand,sub,4);
    header.addView(brand,new LinearLayout.LayoutParams(0,-2,1));
    headerStatus=DesignSystem.pill(this,"ON DEVICE",DesignSystem.TEAL);header.addView(headerStatus);wide(root,header);
  }
  private void buildNav(){
    View separator=line();root.addView(separator,new LinearLayout.LayoutParams(-1,dp(1)));
    navbar=h();navbar.setBackgroundColor(0xFF101526);navbar.setPadding(dp(9),dp(7),dp(9),dp(9));
    String[] names={"Home","Screen","Health","Connect","Tools"};String[] images={"home","monitor","pulse","devices","settings"};
    for(int i=0;i<pages.length;i++){final int index=i;LinearLayout slot=v();slot.setGravity(Gravity.CENTER);slot.setPadding(dp(1),dp(7),dp(1),dp(6));
      DesignSystem.Icon ic=icon(images[i],DesignSystem.MUTED,22);slot.addView(ic);
      TextView label=t(names[i],10.6f,DesignSystem.MUTED,false);label.setGravity(Gravity.CENTER);margin(slot,label,5);
      slot.setOnClickListener(w->show(index));slot.setContentDescription("Open "+names[i]);
      navbar.addView(slot,new LinearLayout.LayoutParams(0,dp(57),1));tabButtons[i]=slot;tabIcons[i]=ic;tabLabels[i]=label;
    }
    wide(root,navbar);
  }
  private ScrollView scroll(LinearLayout body){ScrollView view=new ScrollView(this);view.setFillViewport(false);view.setVerticalScrollBarEnabled(false);body.setPadding(dp(19),dp(14),dp(19),dp(28));view.addView(body);return view;}
  private View scrollHome(){homeBody=v();
    wide(homeBody,eyebrow("YOUR DEVICES · LIVE STATUS"));
    sectionTitle(homeBody,"Your devices.","Phone and Windows control, with live status.");gap(homeBody,19);
    LinearLayout hero=card();hero.setBackground(DesignSystem.gradient(this,0xFF342754,0xFF172A42,25));
    LinearLayout r=h();r.addView(squareIcon("monitor",0xFFD4C9FF));LinearLayout copy=v();copy.setPadding(dp(13),0,0,0);
    copy.addView(eyebrow("WINDOWS COMPUTER"));margin(copy,t("LAPTOP-1LI4VRCJ",17,DesignSystem.TEXT,true),5);r.addView(copy,new LinearLayout.LayoutParams(0,-2,1));wide(hero,r);
    pcConnection=t("Checking your computer…",12.5f,DesignSystem.MUTED,false);margin(hero,pcConnection,17);
    gap(hero,17);button(hero,"Open remote desktop","monitor",true,()->show(1));wide(homeBody,hero);gap(homeBody,12);
    LinearLayout phone=clickableCard(()->show(3));LinearLayout phoneR=h();phoneR.addView(squareIcon("phone",DesignSystem.TEAL));
    LinearLayout phoneCopy=v();phoneCopy.setPadding(dp(12),0,0,0);phoneCopy.addView(eyebrow("ANDROID · THIS PHONE"));
    margin(phoneCopy,t(Build.MODEL,15,DesignSystem.TEXT,true),6);
    homeAgent=t("Remote access is off",12,DesignSystem.MUTED,false);margin(phoneCopy,homeAgent,6);
    phoneR.addView(phoneCopy,new LinearLayout.LayoutParams(0,-2,1));phoneR.addView(icon("arrow",DesignSystem.MUTED,19));wide(phone,phoneR);wide(homeBody,phone);
    gap(homeBody,10);button(homeBody,"Auto-repair connection","refresh",true,()->fullRepair(false));
    homeConnectionIssue=t("Checking native connection…",12,DesignSystem.MUTED,false);
    homeConnectionIssue.setMaxLines(6);margin(homeBody,homeConnectionIssue,8);
    gap(homeBody,26);LinearLayout healthTitle=h();healthTitle.addView(eyebrow("PHONE HEALTH"),new LinearLayout.LayoutParams(0,-2,1));
    TextView details=t("VIEW ALL  ›",11,DesignSystem.PURPLE,true);details.setOnClickListener(w->show(2));healthTitle.addView(details);wide(homeBody,healthTitle);gap(homeBody,11);
    LinearLayout metrics=h();metrics.setGravity(Gravity.TOP);
    homeBattery=smallMetric(metrics,"BATTERY","—",DesignSystem.TEAL);
    homeThermal=smallMetric(metrics,"THERMAL","—",DesignSystem.PURPLE);
    homeMemory=smallMetric(metrics,"FREE RAM","—",DesignSystem.WARNING);wide(homeBody,metrics);
    gap(homeBody,13);
    LinearLayout quick=card();
    rowTitle(quick,"What do you want to do?","Capabilities and real incidents, without another setup screen",icon("settings",DesignSystem.TEAL,22));
    gap(quick,13);
    twoActions(quick,"Add app","devices",this::showAppBridgeApprovals,
      "Tools","settings",()->show(4));
    gap(quick,9);
    twoActions(quick,"Diagnose","activity",this::showCrossAppDiagnostics,
      "Permissions","shield",this::showPermissionsHub);
    wide(homeBody,quick);
    gap(homeBody,20);
    LinearLayout privacy=card();rowTitle(privacy,"Private by design","No account, no subscription. Access is yours to authorize.",icon("shield",DesignSystem.TEAL,24));wide(homeBody,privacy);
    return scroll(homeBody);
  }
  private TextView smallMetric(LinearLayout p,String name,String initial,int color){
    LinearLayout card=v();card.setPadding(dp(11),dp(14),dp(8),dp(14));card.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE,DesignSystem.EDGE,17));
    TextView caption=t(name,9.2f,DesignSystem.MUTED,true);caption.setLetterSpacing(.06f);card.addView(caption);
    TextView value=t(initial,17,color,true);margin(card,value,13);
    LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(91),1);
    if(p.getChildCount()>0)lp.leftMargin=dp(8);p.addView(card,lp);return value;
  }
  private View remotePage(){LinearLayout layout=v();layout.setPadding(dp(17),dp(11),dp(17),dp(14));
    LinearLayout title=h();LinearLayout labels=v();labels.addView(eyebrow("REMOTE VIEW"));margin(labels,t("Remote control",21,DesignSystem.TEXT,true),7);title.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
    LinearLayout refresh=h();refresh.setGravity(Gravity.CENTER);refresh.setPadding(dp(11),dp(11),dp(11),dp(11));DesignSystem.clickable(refresh,this,DesignSystem.SURFACE2,DesignSystem.EDGE,13);refresh.addView(icon("refresh",DesignSystem.PURPLE,20));refresh.setContentDescription("Refresh live remote view");refresh.setOnClickListener(w->{if(web!=null&&webStarted&&web.getVisibility()==View.VISIBLE){web.evaluateJavascript("(function(){if(typeof state!==\'undefined\'&&state.page===\'android\'&&typeof discover===\'function\'){discover();}else if(typeof startLive===\'function\'){startLive();}else{location.reload();}})()",null);}else connectRemote(true);});title.addView(refresh);wide(layout,title);
    remoteConnection=t("Checking Windows connection…",12,DesignSystem.MUTED,false);margin(layout,remoteConnection,10);gap(layout,10);
    LinearLayout remoteTabs=h();
    action(remoteTabs,"PC","monitor",false,()->showRemoteSection("desktop"));
    action(remoteTabs,"Phone","phone",false,()->showRemoteSection("android"));
    action(remoteTabs,"Incidents","activity",false,()->showRemoteSection("diagnostics"));
    wide(layout,remoteTabs);gap(layout,10);
    FrameLayout frame=new FrameLayout(this);frame.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE,DesignSystem.EDGE,21));
    web=new WebView(this);web.setBackgroundColor(DesignSystem.SURFACE);WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(false);settings.setAllowFileAccess(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setCacheMode(WebSettings.LOAD_NO_CACHE);settings.setBuiltInZoomControls(false);settings.setDisplayZoomControls(false);
    web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !sameOrigin(request.getUrl().toString(),prefs.getString("url",""));}
      @Override public void onPageFinished(WebView view,String url){if(!sameOrigin(url,prefs.getString("url","")))return;
        String token=prefs.getString("token","");
        String css="header,footer,.headline,.authbar,.notice,.tabs{display:none!important}.app{padding:7px 9px!important}main{margin:0!important}.tabs{margin:0 0 12px!important}.tabs button{padding:9px 14px!important}.tabs button[data-page=files],.tabs button[data-page=processes],.tabs button[data-page=system]{display:none!important}.sectiontitle{flex-wrap:wrap!important}body{background:#13192b!important}.phone-viewer{min-height:270px!important}";
        String script="(function(){if(!document.getElementById('asterion-embedded')){const st=document.createElement('style');st.id='asterion-embedded';st.textContent="+JSONObject.quote(css)+";document.head.appendChild(st);}const t=document.querySelector('#token');const b=document.querySelector('#connect');if(t&&b){t.value="+JSONObject.quote(token)+";b.click();}})()";
        view.evaluateJavascript(script,null);
         view.evaluateJavascript("(function(){if(typeof showPage==='function')showPage("+
           JSONObject.quote(pendingRemoteSection)+");})()",null);
      }
    });frame.addView(web,new FrameLayout.LayoutParams(-1,-1));
    emptyRemote=v();emptyRemote.setGravity(Gravity.CENTER);pad(emptyRemote,24,16);
    DesignSystem.Icon big=icon("monitor",DesignSystem.PURPLE,42);emptyRemote.addView(big);
    TextView heading=t("Connect to your PC",21,DesignSystem.TEXT,true);heading.setGravity(Gravity.CENTER);margin(emptyRemote,heading,18);
    remotePlaceholder=t("Pair your Windows agent to stream the desktop and control it remotely.",13,DesignSystem.MUTED,false);remotePlaceholder.setGravity(Gravity.CENTER);margin(emptyRemote,remotePlaceholder,12);
    gap(emptyRemote,22);button(emptyRemote,"Set up Windows link","devices",true,()->show(3));frame.addView(emptyRemote,new FrameLayout.LayoutParams(-1,-1));
    layout.addView(frame,new LinearLayout.LayoutParams(-1,0,1));return layout;
  }
  private View scrollHealth(){healthBody=v();wide(healthBody,eyebrow("LIVE DEVICE DIAGNOSTICS"));sectionTitle(healthBody,"Health & performance.","What your phone actually reports, in real time.");gap(healthBody,21);
    LinearLayout therm=card();therm.setBackground(DesignSystem.gradient(this,0xFF272844,0xFF17363A,23));
    rowTitle(therm,"Thermal pressure","Android operating-system status",icon("pulse",DesignSystem.TEAL,25));
    healthThermal=t("Reading…",27,DesignSystem.TEAL,true);margin(therm,healthThermal,19);
    TextView note=t("Thermal pressure is reported by Android; it is not a CPU-temperature estimate.",11,DesignSystem.MUTED,false);margin(therm,note,8);wide(healthBody,therm);gap(healthBody,11);
    LinearLayout gauges=h();gauges.setGravity(Gravity.TOP);healthBattery=smallMetric(gauges,"BATTERY","—",DesignSystem.TEAL);healthTemp=smallMetric(gauges,"BATTERY °C","—",DesignSystem.PURPLE);healthMemory=smallMetric(gauges,"FREE RAM","—",DesignSystem.WARNING);wide(healthBody,gauges);
    gap(healthBody,14);LinearLayout meters=card();rowTitle(meters,"Resource overview","Current load and available capacity",icon("activity",DesignSystem.PURPLE,23));
    gap(meters,17);wide(meters,t("BATTERY LEVEL",10,DesignSystem.MUTED,true));gap(meters,8);batteryMeter=new DesignSystem.Meter(this,DesignSystem.TEAL);wide(meters,batteryMeter);
    gap(meters,16);wide(meters,t("MEMORY IN USE",10,DesignSystem.MUTED,true));gap(meters,8);memoryMeter=new DesignSystem.Meter(this,DesignSystem.PURPLE);wide(meters,memoryMeter);
    gap(meters,16);wide(meters,t("INTERNAL STORAGE IN USE",10,DesignSystem.MUTED,true));gap(meters,8);storageMeter=new DesignSystem.Meter(this,DesignSystem.WARNING);wide(meters,storageMeter);
    wide(healthBody,meters);gap(healthBody,12);
    LinearLayout safety=card();rowTitle(safety,"Automatic protection",
      "Thermal and memory safeguards manage Control overhead",icon("activity",DesignSystem.TEAL,23));
    gap(safety,9);healthActionStatus=t("Reading performance configuration…",12,DesignSystem.MUTED,false);
    wide(safety,healthActionStatus);wide(healthBody,safety);
    gap(healthBody,12);LinearLayout store=card();healthStorage=t("—",18,DesignSystem.TEXT,true);metricRow(store,"Internal storage",null,healthStorage,DesignSystem.PURPLE);margin(healthBody,store,0);
    gap(healthBody,12);LinearLayout network=card();healthWifi=t("Checking…",17,DesignSystem.TEXT,true);metricRow(network,"Network",null,healthWifi,DesignSystem.TEAL);wide(healthBody,network);
    gap(healthBody,24);wide(healthBody,eyebrow("REMOTE SERVICES"));gap(healthBody,10);
    LinearLayout services=card();agentConnection=serviceLine(services,"Phone agent","power");services.addView(line(),new LinearLayout.LayoutParams(-1,dp(1)));
    captureConnection=serviceLine(services,"Screen sharing","share");services.addView(line(),new LinearLayout.LayoutParams(-1,dp(1)));
    accessConnection=serviceLine(services,"Input access","shield");wide(healthBody,services);
    gap(healthBody,24);wide(healthBody,eyebrow("WINDOWS HEALTH"));gap(healthBody,10);
    LinearLayout windows=card();hostHealth=t("Connect your Windows agent to see its CPU, memory, storage and temperature sensors.",12,DesignSystem.MUTED,false);wide(windows,hostHealth);
    wide(healthBody,windows);
    gap(healthBody,24);wide(healthBody,eyebrow("CONTROL DIAGNOSTICS & SECURITY"));gap(healthBody,10);
    LinearLayout diagnostics=card();rowTitle(diagnostics,"Incident diagnostics",
      "Durable Control events and actual Android process exit history",icon("activity",DesignSystem.PURPLE,23));
    gap(diagnostics,10);button(diagnostics,"Inspect recent Control incidents","activity",false,
      ()->showLocalDiagnostics());
    gap(diagnostics,10);button(diagnostics,"Review recorded Asterion app incidents","activity",false,
      ()->showCrossAppDiagnostics());wide(healthBody,diagnostics);
    gap(healthBody,12);LinearLayout security=card();rowTitle(security,"Security level",
      "Enforced locally on both network and direct Control commands",icon("shield",DesignSystem.TEAL,23));
    securitySummary=t("Current: "+ControlSecurityPolicy.level(this),13,DesignSystem.TEXT,true);
    margin(security,securitySummary,12);gap(security,12);
    button(security,"Choose security level","shield",true,()->showSecurityChoices());
    gap(security,9);button(security,"Permissions and developer access","activity",false,
      ()->showPermissionDetails());wide(healthBody,security);
    gap(healthBody,12);LinearLayout connectivity=card();rowTitle(connectivity,"Private connectivity",
      "Existing encrypted link is preserved; optional Asterion VPN is not active",
      icon("shield",DesignSystem.TEAL,23));
    gap(connectivity,11);button(connectivity,"Inspect VPN and network permissions","devices",false,
      ()->showVpnDetails());wide(healthBody,connectivity);
    return scroll(healthBody);
  }

  private void setSecurityModeLocally(String mode,boolean[] flags){
    try{
      if(!ControlSecurityPolicy.configureLocally(this,mode,flags,3600000L))
        throw new IllegalStateException("Security settings not persisted");
      if(securitySummary!=null)securitySummary.setText("Current: "+ControlSecurityPolicy.level(this));
      toast("Security level updated: "+ControlSecurityPolicy.level(this));
    }catch(Exception e){toast("Security change rejected: "+e.getClass().getSimpleName());}
  }
  private void showSecurityChoices(){
    final String[] choices={"Normal — existing encrypted paired control",
      "Developer — 60 minutes, owner-approved diagnostics",
      "Lockdown — block remote operations, allow only status",
      "Custom — choose permitted remote capabilities"};
    new AlertDialog.Builder(this).setTitle("Asterion security level")
      .setSingleChoiceItems(choices,-1,(dialog,which)->{
        dialog.dismiss();
        if(which==0)setSecurityModeLocally(ControlSecurityPolicy.NORMAL,null);
        else if(which==1)
          new AlertDialog.Builder(this).setTitle("Temporary Developer access")
            .setMessage("Developer mode expires after 60 minutes. Android system permissions remain required and are never granted automatically.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Enable", (d,w)->setSecurityModeLocally(
              ControlSecurityPolicy.DEVELOPER,null)).show();
        else if(which==2)
          new AlertDialog.Builder(this).setTitle("Enable Lockdown?")
            .setMessage("Remote input, app launches, file writes and automated commands will be denied. You can restore Normal here on this phone.")
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Enable Lockdown",(d,w)->setSecurityModeLocally(
              ControlSecurityPolicy.LOCKDOWN,null)).show();
        else{
          final String[] names={"Remote touch and text","Launch applications",
            "Authorized app engine actions","Remote file transfers",
            "ChatGPT continuation and cycles","Developer diagnostics"};
          final boolean[] selected={true,true,true,true,true,false};
          new AlertDialog.Builder(this).setTitle("Custom remote permissions")
            .setMultiChoiceItems(names,selected,(d,index,checked)->selected[index]=checked)
            .setNegativeButton("Cancel",null)
            .setPositiveButton("Apply custom policy",(d,w)->setSecurityModeLocally(
              ControlSecurityPolicy.CUSTOM,selected)).show();
        }
      }).setNegativeButton("Cancel",null).show();
  }
  private String localExitMeaning(int code){
    switch(code){
      case 1:return "App closed itself";
      case 2:return "Android process signal";
      case 3:return "Android low-memory termination";
      case 4:return "Java crash";
      case 5:return "Native-code crash";
      case 6:return "App not responding (ANR)";
      case 7:return "App initialization failed";
      case 8:return "App permissions changed";
      case 9:return "Excessive system resource usage";
      case 10:return "Owner requested exit";
      case 11:return "App stopped by the owner";
      case 12:return "Dependency exited";
      default:return "Other or unidentified Android exit";
    }
  }
  private void showLocalDiagnostics(){
    try{
      JSONObject head=ControlEventJournal.recent(this,0,1);
      long latest=head.optLong("latest_sequence",0);
      JSONObject log=ControlEventJournal.recent(
        this,Math.max(0,latest-18),20);
      JSONObject exits=ControlCrashDiagnostics.recentExitHistory(this);
      org.json.JSONArray entries=log.optJSONArray("events");
      org.json.JSONArray history=exits.optJSONArray("exits");
      int crashCount=0,exitCount=history==null?0:history.length();
      StringBuilder report=new StringBuilder();
      report.append("Control recorded ").append(latest)
        .append(" local events. These are only from Control, not other apps.\n");
      report.append("\nRecent connection and service activity:\n");
      if(entries==null||entries.length()==0)
        report.append("No local events in this stored sample.\n");
      else for(int i=Math.max(0,entries.length()-10);i<entries.length();i++){
        JSONObject event=entries.optJSONObject(i);
        if(event==null)continue;
        String kind=event.optString("kind","event");
        String state=event.optString("state","");
        String label=kind.replace('_',' ');
        if(kind.contains("transport")||kind.contains("wss"))
          label="Control connection";
        else if(kind.contains("service"))
          label="Control background service";
        report.append("• ").append(label);
        if(!state.isEmpty())report.append(" — ").append(state.replace('_',' '));
        report.append("\n");
      }
      report.append("\nAndroid process exits (historical): ")
        .append(exitCount).append("\n");
      if(history!=null)
        for(int i=0;i<Math.min(8,history.length());i++){
          JSONObject exit=history.optJSONObject(i);
          if(exit==null)continue;
          int reason=exit.optInt("reason_code",-1);
          if(reason==4||reason==5||reason==6)crashCount++;
          report.append("• ").append(localExitMeaning(reason));
          long at=exit.optLong("timestamp_ms",0);
          if(at>0)report.append(" · ").append(
            android.text.format.DateFormat.format(
              "dd MMM yyyy HH:mm",new java.util.Date(at)));
          report.append("\n");
        }
      report.append("\n").append(crashCount)
        .append(" crashes/freezes classified among the displayed exit entries. ")
        .append("Other exits may be normal and do not automatically indicate failures.")
        .append("\n\nTo investigate another Asterion app, open Incident investigation. ")
        .append("Its own engine must report events to Control.");
      new AlertDialog.Builder(this)
        .setTitle("Control connection & exit history")
        .setMessage(report.toString())
        .setNeutralButton("All app incidents",(d,w)->
          showRemoteSection("diagnostics"))
        .setPositiveButton("Close",null).show();
    }catch(Exception e){
      new AlertDialog.Builder(this).setTitle("History unavailable")
        .setMessage("Control could not read its own stored history. No conclusion "+
          "about other apps or current crashes is possible.")
        .setPositiveButton("Close",null).show();
    }
  }
  /** A single readable incident UI, not competing raw JSON dialogs. */
  /** Phone-head diagnostics: query the installed Android partner catalog
   * directly. Windows event analysis is optional, never a prerequisite.
   */
  private void showCrossAppDiagnostics(){
    io.execute(()->{
      try{
        java.util.Map<String,String> installed=AppCatalog.launchable(this);
        JSONObject discovery=AppBridge.list(this);
        org.json.JSONArray providers=discovery.getJSONArray("apps");
        java.util.Map<String,Boolean> available=new java.util.HashMap<>();
        for(int i=0;i<providers.length();i++){
          JSONObject item=providers.getJSONObject(i);
          available.put(item.getString("package"),item.optBoolean("approved"));
        }
        java.util.List<String> packages=new ArrayList<>();
        java.util.List<String> titles=new ArrayList<>();
        for(java.util.Map.Entry<String,String> app:installed.entrySet()){
          String pkg=app.getKey(),label=app.getValue();
          if(!(label.toLowerCase(Locale.ROOT).startsWith("asterion")||
               pkg.startsWith("com.asterion.")||
               pkg.startsWith("com.azrael.pixivdumpsync")||
               pkg.equals("com.ailm.android")))continue;
          if(pkg.equals(getPackageName()))continue;
          packages.add(pkg);
          String bridge=available.containsKey(pkg)?
            (available.get(pkg)?"Approved · read live evidence":
             "Bridge available · tap to authorize"):
            "No native bridge in installed build";
          titles.add(label+"\n"+bridge);
        }
        runOnUiThread(()->{
          if(destroyed)return;
          new AlertDialog.Builder(this)
            .setTitle("Phone diagnostics · "+available.size()+" bridges found")
            .setItems(titles.toArray(new String[0]),(d,index)->{
              String pkg=packages.get(index);
              showAppIntegrationActions(pkg,installed.get(pkg),
                available.containsKey(pkg),
                Boolean.TRUE.equals(available.get(pkg)));
            })
            .setPositiveButton("Windows event archive",(d,w)->
              showRemoteSection("diagnostics"))
            .setNegativeButton("Close",null).show();
        });
      }catch(Exception e){
        runOnUiThread(()->{
          if(destroyed)return;
          new AlertDialog.Builder(this)
            .setTitle("Phone diagnostic discovery unavailable")
            .setMessage("Asterion Control could not read the native app "+
              "catalog: "+e.getClass().getSimpleName()+
              ". It does not mean the partner applications are healthy "+
              "or missing.")
            .setPositiveButton("Close",null).show();
        });
      }
    });
  }
  /** One owner-facing authorization hub; Android remains the only authority
   * that may actually grant each permission. Required and optional are distinct.
   */
  private void showPermissionDetails(){showPermissionsHub();}
  private void openOwnAppSettings(){
    try{startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
      Uri.parse("package:"+getPackageName())));}
    catch(Exception e){toast("Android app settings unavailable");}
  }
  private void showPermissionsHub(){
    try{
      JSONObject state=ControlPermissionMatrix.status(this);
      boolean accessibility=state.optBoolean("accessibility_enabled");
      boolean capture=state.optBoolean("media_projection_active");
      boolean notifications=state.optBoolean("notifications_granted");
      boolean usage=state.optBoolean("usage_stats_granted");
      boolean mic=checkSelfPermission(Manifest.permission.RECORD_AUDIO)==
        PackageManager.PERMISSION_GRANTED;
      boolean installs=Build.VERSION.SDK_INT>=26&&
        getPackageManager().canRequestPackageInstalls();
      boolean battery=false;
      try{
        PowerManager power=(PowerManager)getSystemService(POWER_SERVICE);
        battery=power!=null&&power.isIgnoringBatteryOptimizations(getPackageName());
      }catch(Exception ignored){}
      String[] rows={
        "Remote touch · Required for phone input · "+(accessibility?"Enabled":"Not granted"),
        "Screen sharing · Consent per session · "+(capture?"Active":"Not active"),
        "Notifications · Recommended for background service · "+(notifications?"Allowed":"Not granted"),
        "Microphone · Optional voice · "+(mic?"Allowed":"Not granted"),
        "Usage access · Optional app observation · "+(usage?"Allowed":"Not granted"),
        "Battery restrictions · Recommended for unattended jobs · "+
          (battery?"Optimization exemption":"Check Samsung settings"),
        "Install APK updates · Optional · "+(installs?"Allowed":"Not granted"),
        "WireGuard VPN · Optional, never automatic · "+
          (state.optBoolean("asterion_vpn_active")?"Active":"Inactive"),
        "All Android app permissions · View Control settings",
        "Developer options · Optional diagnostics only · "+
          (state.optBoolean("developer_options_enabled")?"Enabled":"Disabled")
      };
      // Do not setMessage with setItems: Android otherwise hides the list.
      new AlertDialog.Builder(this).setTitle("Permissions · tap a setting")
        .setItems(rows,(dlg,item)->openPermissionStep(item))
        .setPositiveButton("Refresh", (d,w)->showPermissionsHub())
        .setNegativeButton("Close",null).show();
    }catch(Exception e){
      toast("Permission status unavailable: "+e.getClass().getSimpleName());
    }
  }
  private void openPermissionStep(int selected){
    try{
      switch(selected){
        case 0:
          startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
          break;
        case 1:
          beginCapture();break;
        case 2:
          if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(
             Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
              HUB_NOTIFICATION_REQUEST);
          else openOwnAppSettings();
          break;
        case 3:
          if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=
             PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},
              HUB_MICROPHONE_REQUEST);
          else openOwnAppSettings();
          break;
        case 4:
          startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS));
          break;
        case 5:
          showBatterySetup();break;
        case 6:
          if(Build.VERSION.SDK_INT>=26)
            startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
              Uri.parse("package:"+getPackageName())));
          else openOwnAppSettings();
          break;
        case 7:
          showVpnDetails();break;
        case 8:
          openOwnAppSettings();break;
        case 9:
          startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
          break;
        default:break;
      }
    }catch(Exception e){
      // Never misreport a Settings action as a granted permission.
      new AlertDialog.Builder(this)
        .setTitle("Android setting unavailable")
        .setMessage("The requested Android settings panel could not open on "+
          "this device. You can open Asterion Control's own app settings "+
          "and navigate to the permission manually.")
        .setPositiveButton("App settings",(d,w)->openOwnAppSettings())
        .setNegativeButton("Close",null).show();
    }
  }
  private void showVpnDetails(){
    try{
      JSONObject android=ControlPermissionMatrix.status(this);
      JSONObject tunnel=ControlPrivateVpn.status(this);
      boolean active=tunnel.optBoolean("active",false);
      boolean configured=tunnel.optBoolean("configuration_present",false);
      String message="Asterion WireGuard: "+tunnel.optString("state","off")+
        "\nConfiguration safely stored: "+configured+
        "\nAndroid VPN route active: "+android.optBoolean("other_vpn_or_active_vpn")+
        "\nFull-tunnel owner approved: "+tunnel.optBoolean("full_tunnel_owner_approved")+
        "\n\nThe current Control secure connection does not require a VPN. " +
        "A VPN can run only with a valid owner-managed peer and Android system consent. " +
        "Tunnel UP does not prove remote peer reachability or improved speed.";
      AlertDialog.Builder dialog=new AlertDialog.Builder(this)
        .setTitle("Private VPN — WireGuard").setMessage(message)
        .setNegativeButton("Close",null);
      if(active){
        dialog.setPositiveButton("Disconnect",(d,w)->
          ControlPrivateVpn.disconnect(this,this::toast));
      }else{
        if(configured)
          dialog.setPositiveButton("Connect",(d,w)->requestVpnConsentAndConnect());
        else
          dialog.setPositiveButton("Get free VPN profile",(d,w)->showFreeVpnConfigSetup());
        dialog.setNeutralButton(configured?"Replace configuration":"Import configuration",
          (d,w)->showVpnImportType());
      }
      dialog.show();
    }catch(Exception e){toast("VPN status unavailable: "+e.getClass().getSimpleName());}
  }
  private void showFreeVpnConfigSetup(){
    new AlertDialog.Builder(this)
      .setTitle("Set up a free WireGuard tunnel")
      .setMessage("Asterion Control already includes the WireGuard engine, "+
        "but no VPN server or account is bundled. A third-party peer must "+
        "supply a valid configuration.\n\n"+
        "Proton VPN's Free plan currently allows manual WireGuard "+
        "configurations. Create a free Proton account, open Downloads > "+
        "WireGuard configuration, and download the generated .conf file. "+
        "Import its contents into Asterion Control. This does not share "+
        "your configuration with Control's Windows service.\n\n"+
        "After importing, Android must separately approve the VPN. "+
        "A working internet route and exit IP must be tested before "+
        "calling the VPN connected. No speed, port forwarding, "+
        "or rotation guarantees are implied.")
      .setPositiveButton("Open Proton account",(d,w)->{
        try{
          startActivity(new Intent(Intent.ACTION_VIEW,
            Uri.parse("https://account.protonvpn.com")));
        }catch(Exception e){toast("Could not open Proton setup website");}
      })
      .setNeutralButton("Import WireGuard profile",(d,w)->showVpnImportType())
      .setNegativeButton("Close",null).show();
  }
  private void showVpnImportType(){
    final String[] options={"Private-device split routes (recommended)",
      "Full-device tunnel (requires extra consent)"};
    new AlertDialog.Builder(this).setTitle("WireGuard traffic scope")
      .setItems(options,(d,which)->showVpnImportEditor(which==1))
      .setNegativeButton("Cancel",null).show();
  }
  private void showVpnImportEditor(boolean fullTunnel){
    final EditText editor=new EditText(this);
    editor.setHint("[Interface]\nPrivateKey = ...\nAddress = ...\n\n[Peer]\nPublicKey = ...\nAllowedIPs = ...\nEndpoint = ...");
    editor.setSingleLine(false);editor.setMinLines(6);editor.setMaxLines(11);
    editor.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE);
    editor.setTransformationMethod(android.text.method.PasswordTransformationMethod.getInstance());
    editor.setTextSize(12f);editor.setPadding(dp(14),dp(12),dp(14),dp(12));
    String message=fullTunnel?
      "Full-device routing may replace another VPN and change how all apps access the internet. The owner must approve Android's VPN prompt.":
      "Only the private routes declared by the configuration will enter this encrypted tunnel. Existing Control access remains available without it.";
    new AlertDialog.Builder(this).setTitle("Import encrypted WireGuard profile")
      .setMessage(message).setView(editor)
      .setNegativeButton("Cancel",(d,w)->editor.setText(""))
      .setPositiveButton("Import",(d,w)->{
        try{
          ControlPrivateVpn.importLocally(this,editor.getText().toString(),fullTunnel);
          toast("Encrypted VPN profile imported. Connect when ready.");
        }catch(Exception e){
          toast("VPN config rejected: "+e.getClass().getSimpleName());
        }finally{editor.setText("");}
      }).show();
  }
  private void requestVpnConsentAndConnect(){
    try{
      Intent permission=ControlPrivateVpn.consentIntent(this);
      if(permission!=null){
        new AlertDialog.Builder(this).setTitle("Android VPN approval")
          .setMessage("Android will request permission to activate Asterion Private. If another VPN is running, it may be displaced. No VPN is activated without your approval.")
          .setNegativeButton("Cancel",null)
          .setPositiveButton("Continue",(d,w)->startActivityForResult(permission,VPN_REQUEST))
          .show();
      }else{
        ControlPrivateVpn.connect(this,this::toast);
      }
    }catch(Exception e){toast("Unable to start VPN: "+e.getClass().getSimpleName());}
  }

  private TextView serviceLine(LinearLayout card,String title,String iconName){LinearLayout row=h();row.setPadding(0,dp(11),0,dp(11));row.addView(icon(iconName,DesignSystem.PURPLE,20));TextView titleText=t(title,13,DesignSystem.TEXT,true);titleText.setPadding(dp(14),0,0,0);row.addView(titleText,new LinearLayout.LayoutParams(0,-2,1));TextView value=t("Checking",12,DesignSystem.MUTED,false);row.addView(value);wide(card,row);return value;}
  /** Explicit owner action: re-arm existing agent and re-register with the same Windows worker.
      Android must still grant Accessibility and MediaProjection when unavailable. */
  private void forceActivateConnection(){
    if(homeConnectionIssue!=null)homeConnectionIssue.setText("Activating the existing native control link…");
    if(connectionIssue!=null)connectionIssue.setText("Activating the existing native control link…");
    startAgent(); // onStartCommand also wakes the already installed direct transport.
    String url=prefs.getString("url",""),token=prefs.getString("token","");
    if(url.isEmpty()||token.isEmpty()){
      ConnectionDiagnostics.failure(this,"not_paired","No saved Windows pairing; connect your computer once");
      updateConnectionIssue();
      return;
    }
    handler.postDelayed(()->{
      if(destroyed)return;
      if(!AgentService.running||!AgentService.listenerReady){
        ConnectionDiagnostics.failure(this,"agent_listener_unavailable",
          "Android phone control listener is not active; service may be restricted or recovering");
        updateConnectionIssue();
      }else{
        registerPhone();
      }
      checkHost();
    },1300);
    if(!CaptureService.active) {
      beginCapture(); // Android itself asks for fresh user consent; no silent recording.
    } else if(ControlAccessibilityService.active==null) {
      toast("Android input access needs your approval");
      try{startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));}
      catch(Exception e){ConnectionDiagnostics.failure(this,"accessibility_settings",
        "Android Accessibility settings could not be opened");}
    }
    updateConnectionIssue();
  }
  private void updateConnectionIssue(){
    String issue;
    boolean wanted=getSharedPreferences("agent",MODE_PRIVATE)
      .getBoolean(AgentService.PREF_REMOTE_ENABLED,false);
    if(prefs.getString("url","").isEmpty()||prefs.getString("token","").isEmpty())
      issue="Not paired with a Windows worker";
    else if(!wanted)issue="Phone remote access is disabled";
    else if(!AgentService.running)issue="Android phone agent stopped";
    else if(!AgentService.listenerReady)issue="Phone control listener not accepting connections";
    else if(ControlAccessibilityService.active==null)issue="Android Accessibility input is not authorized";
    else if(!CaptureService.active)issue="Native screen sharing stopped; Android approval required";
    else if(CaptureService.latestAtMs==0L||System.currentTimeMillis()-CaptureService.latestAtMs>5000L)
      issue="Screen sharing started but frames are stale";
    else issue="Phone listener, input and screen capture are active";
    String detail=issue+"\nWindows link: "+workerPhoneState+
      "\n"+ConnectionDiagnostics.lastFailure(this);
    if(connectionIssue!=null)connectionIssue.setText(detail);
    if(homeConnectionIssue!=null)homeConnectionIssue.setText(detail);
  }
  private void fullRepair(boolean force){
    if(fullRepairInProgress){setPairingFeedback("Recovery already in progress. The existing job is being checked.");return;}
    if(force){
      new AlertDialog.Builder(this).setTitle("Force reinitialize Asterion Control?")
        .setMessage("Recover the Windows worker, direct native WebSocket, phone listener and screen-capture path. Other active Windows jobs will be preserved or the restart will be blocked. Existing pairing, credentials, app data and files are kept. Android may request screen-sharing consent again.")
        .setPositiveButton("Reinitialize",(d,w)->beginFullRepair(true))
        .setNegativeButton("Cancel",null).show();
    }else beginFullRepair(false);
  }
  private void beginFullRepair(boolean force){
    if(prefs.getString("url","").isEmpty()||prefs.getString("token","").isEmpty()){
      setPairingFeedback("No saved Windows pairing. Discover your existing computer; nothing was reset.");
      discoverComputer();return;
    }
    fullRepairInProgress=true;
    fullRepairTicket="";
    setPairingFeedback(force?"Force reinitialize: recovering Windows, native WebSocket and Android…":
      "Auto-repair: checking Windows, native WebSocket, Android and video…");
    if(force){
      // Android only: restart listener without revoking saved authorization.
      stopService(new Intent(this,AgentService.class));
      handler.postDelayed(()->{if(!destroyed){startAgent();submitFullRepair(force,0);}},1200);
    }else{startAgent();submitFullRepair(force,0);}
  }
  private void submitFullRepair(boolean force,int retry){
    if(destroyed||!fullRepairInProgress)return;
    io.execute(()->{
      try{
        JSONObject job=pcTransferRequest("/api/v1/recovery/start","POST",
          new JSONObject().put("mode",force?"force":"auto"));
        String ticket=job.getString("id");
        runOnUiThread(()->{
          if(destroyed||!fullRepairInProgress)return;
          fullRepairTicket=ticket;
          setPairingFeedback("Windows repair started · verifying worker, phone, direct WebSocket and video…");
          if(AgentService.running)registerPhone();
          pollFullRepair(ticket,0,force);
        });
      }catch(Exception e){
        runOnUiThread(()->{
          if(destroyed||!fullRepairInProgress)return;
          if(retry<15){
            setPairingFeedback("Waiting for the independent Windows worker watchdog · "+
              (retry+1)+"/16 checks. Pairing preserved.");
            handler.postDelayed(()->submitFullRepair(force,retry+1),4000);
          }else{
            fullRepairInProgress=false;
            setPairingFeedback("Full recovery incomplete: Windows worker or recovery endpoint "+
              "could not be contacted. The independent Windows watchdog must be installed. "+
              "Existing pairing was not changed.");
          }
        });
      }
    });
  }
  private void pollFullRepair(String ticket,int attempt,boolean force){
    if(destroyed||!fullRepairInProgress||!ticket.equals(fullRepairTicket))return;
    io.execute(()->{
      String phase="running",detail="Waiting for native recovery verification";
      try{
        JSONObject result=pcTransferRequest("/api/v1/recovery/status","GET",null);
        if(!ticket.equals(result.optString("id")))
          throw new IllegalStateException("Different repair receipt: no replay");
        phase=result.optString("phase","running");
        JSONObject steps=result.optJSONObject("steps");
        detail="Windows: "+(steps==null?"unchecked":steps.optString("windows_worker","checking"))+
          "\nPhone: "+(steps==null?"unchecked":steps.optString("phone_listener","checking"))+
          "\nDirect WebSocket: "+(steps==null?"unchecked":steps.optString("native_websocket","checking"))+
          "\nInput: "+(steps==null?"unchecked":steps.optString("accessibility","checking"))+
          "\nVideo: "+(steps==null?"unchecked":steps.optString("live_video","checking"));
        if(result.has("error")&&!result.optString("error").isEmpty())
          detail+="\n"+result.optString("error","");
      }catch(Exception e){detail="Windows recovery receipt unavailable: "+e.getClass().getSimpleName();}
      final String state=phase,summary=detail;
      runOnUiThread(()->{
        if(destroyed||!fullRepairInProgress||!ticket.equals(fullRepairTicket))return;
        if("verified".equals(state)){
          fullRepairInProgress=false;
          setPairingFeedback("FULL PATH VERIFIED\n"+summary);
          ConnectionDiagnostics.success(this);checkHost();updateConnectionIssue();
        }else if("permission_required".equals(state)){
          fullRepairInProgress=false;
          setPairingFeedback("Direct Windows/phone link recovered. Android consent required.\n"+summary);
          if(!CaptureService.active)beginCapture();
        }else if("partial".equals(state)||"failed".equals(state)||"stale".equals(state)||attempt>=45){
          fullRepairInProgress=false;
          setPairingFeedback("Full repair NOT verified. Pairing preserved.\n"+summary);
          updateConnectionIssue();
        }else{
          setPairingFeedback("Recovering entire native connection ("+(attempt+1)+"/46)\n"+summary);
          handler.postDelayed(()->pollFullRepair(ticket,attempt+1,force),2000);
        }
      });
    });
  }
  private void repairDeviceLink(){
    if(!prefs.getString("token","").isEmpty()&&!prefs.getString("url","").isEmpty()){
      startAgent();
      handler.postDelayed(()->{if(AgentService.running)registerPhone();
        else setPairingFeedback("Phone service did not start; enable phone access.");},1500);
    }else discoverComputer();
  }
  private View scrollDevices(){
    devicesBody=v();wide(devicesBody,eyebrow("SECURE DEVICE ACCESS"));
    sectionTitle(devicesBody,"Your connections.","Control your own devices without cables or repeated setup.");gap(devicesBody,18);

    // Clear device status first. No access tokens, IPs, terminals or logs in this primary view.
    LinearLayout summary=card();summary.setBackground(DesignSystem.gradient(this,0xFF28334B,0xFF182A38,23));
    rowTitle(summary,"Windows computer","Your remote desktop and device resources",icon("monitor",DesignSystem.PURPLE,25));
    gap(summary,12);remoteConnection=t("Checking saved connection…",12,DesignSystem.MUTED,false);wide(summary,remoteConnection);
    gap(summary,16);
    if(prefs.getString("url","").isEmpty())
      button(summary,"Find Windows computer","devices",true,this::discoverComputer);
    else button(summary,"Auto-repair connection","refresh",true,()->fullRepair(false));
    gap(summary,9);button(summary,"Force reinitialize all components","power",false,()->fullRepair(true));
    gap(summary,9);button(summary,"Cycle status","check",false,this::showCycleStatus);
    gap(summary,10);pairingFeedback=t("Your phone is the controller. Connect once; the Windows worker follows.",12,DesignSystem.MUTED,false);
    pairingFeedback.setMaxLines(13);wide(summary,pairingFeedback);
    gap(summary,10);connectionIssue=t("Checking last disconnection…",12,DesignSystem.MUTED,false);
    connectionIssue.setMaxLines(9);wide(summary,connectionIssue);
    wide(devicesBody,summary);

    gap(devicesBody,12);LinearLayout phone=card();
    rowTitle(phone,"This Android phone","Optional incoming screen and touch access",icon("phone",DesignSystem.TEAL,23));
    gap(phone,12);phoneAddress=t("Checking phone access…",12,DesignSystem.MUTED,false);wide(phone,phoneAddress);
    gap(phone,13);phoneAccessAction=v();
    button(phoneAccessAction,"Grant phone access","shield",true,this::enablePhoneControl);
    wide(phone,phoneAccessAction);
    phoneCaptureAction=v();
    button(phoneCaptureAction,"Start screen sharing","share",false,this::beginCapture);
    wide(phone,phoneCaptureAction);
    phoneStopAction=v();
    button(phoneStopAction,"Stop phone access","power",false,
      ()->{stopService(new Intent(this,CaptureService.class));stopAgent();});
    wide(phone,phoneStopAction);
    wide(devicesBody,phone);

    gap(devicesBody,12);LinearLayout toolsShortcut=clickableCard(()->show(4));
    rowTitle(toolsShortcut,"Tools and capabilities",
      "AI, voice, app integrations, incidents, files and updates",icon("settings",DesignSystem.TEAL,22));
    wide(devicesBody,toolsShortcut);
    gap(devicesBody,9);
    button(devicesBody,"All Android authorizations","shield",false,
      this::showPermissionsHub);
    gap(devicesBody,12);LinearLayout security=card();
    rowTitle(security,"Access & privacy","Only connected devices you authorize can control this phone",icon("shield",DesignSystem.TEAL,24));
    gap(security,12);privacyStatus=t("Access is off until you enable it. Android may request accessibility and screen-sharing permission.",12,DesignSystem.MUTED,false);
    wide(security,privacyStatus);wide(devicesBody,security);

    gap(devicesBody,24);LinearLayout advanced=clickableCard(()->toggleAdvancedSetup());
    rowTitle(advanced,"Pair or change computer","One-time setup · saved for later sessions",icon("settings",DesignSystem.PURPLE,21));
    wide(devicesBody,advanced);gap(devicesBody,10);
    advancedSetup=card();advancedSetup.setVisibility(View.GONE);
    wide(advancedSetup,eyebrow("COMPUTER ADDRESS"));gap(advancedSetup,8);
    serverUrl=input(prefs.getString("url",""),false,"Windows computer · private network address");wide(advancedSetup,serverUrl);
    gap(advancedSetup,13);wide(advancedSetup,eyebrow("ONE-TIME PAIRING CODE"));gap(advancedSetup,8);
    serverToken=input("",false,"8-digit code shown by Windows");wide(advancedSetup,serverToken);
    gap(advancedSetup,13);button(advancedSetup,"Pair this computer","check",true,()->{
      completePairing(serverUrl.getText().toString().trim(),serverToken.getText().toString().trim());
      toggleAdvancedSetup();
    });
    gap(advancedSetup,13);TextView notice=t("Advanced pairing details stay hidden in everyday use. For connections outside your local network, use your private encrypted VPN; never expose the current HTTP service to the public internet.",11,DesignSystem.MUTED,false);wide(advancedSetup,notice);
    wide(devicesBody,advancedSetup);
    // Retained internally for registration; never displayed as a plain-text access credential.
    localAddress=input(prefs.getString("phoneip",ipAddress()),false,"");
    return scroll(devicesBody);
  }
  /** One navigation surface for Control capabilities.
   * Existing features are moved here, not cloned or removed.
   */
  private View scrollTools(){
    LinearLayout toolsBody=v();
    wide(toolsBody,eyebrow("CONTROL CAPABILITIES"));
    sectionTitle(toolsBody,"Tools & services.",
      "Actual feature status, useful commands and explicit limitations.");
    gap(toolsBody,15);
    LinearLayout intelligence=card();
    rowTitle(intelligence,"On-device AI",
      "Qwen3 GGUF runs inside this Samsung, with no Windows inference server",
      icon("activity",DesignSystem.PURPLE,23));
    gap(intelligence,12);
    button(intelligence,"Ask the phone AI","activity",true,
      this::showPhoneAiChat);
    gap(intelligence,9);
    twoActions(intelligence,"Model status","check",this::showPhoneAiStatus,
      "Android cycles","activity",this::showCycleStatus);
    gap(intelligence,9);
    twoActions(intelligence,"PC model lab","activity",()->showWindowsRegistry("models"),
      "PC skills","settings",()->showWindowsRegistry("skills"));
    wide(toolsBody,intelligence);
    gap(toolsBody,12);LinearLayout incidents=card();
    rowTitle(incidents,"Incident investigation",
      "Cross-app opt-in evidence and Android's own crash history",
      icon("activity",DesignSystem.TEAL,23));
    gap(incidents,10);
    button(incidents,"Asterion application incidents","activity",true,
      this::showCrossAppDiagnostics);
    gap(incidents,8);
    button(incidents,"Android Control crash history","activity",false,
      this::showLocalDiagnostics);
    gap(incidents,8);
    button(incidents,"Open evidence dashboard","monitor",false,
      ()->showRemoteSection("diagnostics"));
    wide(toolsBody,incidents);
    gap(toolsBody,12);LinearLayout privacyTools=card();
    rowTitle(privacyTools,"Network & privacy",
      "Owner-managed WireGuard and local security permissions",
      icon("shield",DesignSystem.TEAL,23));
    gap(privacyTools,10);
    twoActions(privacyTools,"VPN status","shield",this::showVpnDetails,
      "Security","settings",this::showSecurityChoices);
    gap(privacyTools,9);
    button(privacyTools,"All Android authorizations","shield",true,
      this::showPermissionsHub);
    wide(toolsBody,privacyTools);

    // Internal relays, checkpoints and observation have authenticated APIs,
    // not duplicate diagnostic switches on this user-facing screen.
    gap(toolsBody,12);LinearLayout voice=card();
    rowTitle(voice,"Voice control",
      "Say Asterion followed by your request · works in background while Android permits microphone access",
      icon("activity",DesignSystem.TEAL,22));
    voiceStartAction=v();
    button(voiceStartAction,"Enable hands-free voice","check",true,this::startVoiceQuestions);
    wide(voice,voiceStartAction);
    voiceTalkAction=v();
    button(voiceTalkAction,"Talk to Asterion","activity",true,()->{
      try{
        VoiceDialogueService v=VoiceDialogueService.active;
        if(v==null){startVoiceQuestions();return;}
        v.beginOwnerVoiceControl("en-US");
        toast("Asterion is speaking; answer after the question");
      }catch(Exception e){toast("Voice: "+e.getMessage());}
    });
    wide(voice,voiceTalkAction);
    voiceStopAction=v();
    button(voiceStopAction,"Stop voice session","power",false,
      ()->{
        try{VoiceDialogueService.stopFromOwnerApi(this);}
        catch(Exception e){toast("Voice could not stop: "+e.getMessage());}
        updateHealth();
      });
    wide(voice,voiceStopAction);wide(toolsBody,voice);

    gap(toolsBody,12);LinearLayout integrations=card();
    rowTitle(integrations,"Asterion app integrations",
      "Native commands · per-app consent · no unrestricted access",icon("shield",DesignSystem.TEAL,22));
    gap(integrations,10);
    button(integrations,"Browse installed apps & add","devices",true,this::showAppBridgeApprovals);
    gap(integrations,9);
    button(integrations,"My added apps","settings",false,this::showMyAddedApps);
    gap(integrations,9);
    button(integrations,"Check app diagnostic coverage","activity",false,
      this::showIntegrationCoverage);
    wide(toolsBody,integrations);

    gap(toolsBody,12);LinearLayout transfer=card();
    rowTitle(transfer,"Direct Wi-Fi file transfer","PC → Phone · Files are saved to Downloads/Asterion Control",icon("download",DesignSystem.TEAL,24));
    gap(transfer,12);button(transfer,"Send a PC file to this phone","share",true,this::promptWifiTransfer);
    transferCancelAction=v();button(transferCancelAction,"Cancel transfer","power",false,this::cancelWifiTransfer);
    wide(transfer,transferCancelAction);transferCancelAction.setVisibility(View.GONE);
    gap(transfer,9);transferFeedback=t("No transfer active. Uses the existing private Wi-Fi connection, never GitHub or ADB.",12,DesignSystem.MUTED,false);
    transferFeedback.setMaxLines(6);wide(transfer,transferFeedback);wide(toolsBody,transfer);

    gap(toolsBody,12);LinearLayout updater=card();
    rowTitle(updater,"Asterion Control updates","Official signed releases · install without losing data",icon("refresh",DesignSystem.TEAL,22));
    gap(updater,12);button(updater,"Check for updates","refresh",true,
      ()->UpdateManager.check(this,this::showUpdateFeedback));
    gap(updater,9);updateFeedback=t("Checks the official release, verifies SHA-256 and requests Android approval before installing.",12,DesignSystem.MUTED,false);
    updateFeedback.setMaxLines(5);wide(updater,updateFeedback);
    wide(toolsBody,updater);


    return scroll(toolsBody);
  }

  /** Phone is the AI head. No PC or cloud model endpoint is consulted. */
  private void showPhoneAiStatus(){
    io.execute(()->{
      String report;
      try{
        JSONObject data=OnDeviceLlm.status(getApplicationContext());
        report="Host: this Android phone\n"+
          "Runtime included: "+data.optBoolean("native_library_loaded",false)+
          "\nGGUF weights bundled in signed APK: "+
            data.optBoolean("model_bundled_in_apk",false)+
          "\nPrivate verified model loaded: "+
            data.optBoolean("model_loaded",false)+
          "\nModel source: "+data.optString("model_source","unavailable")+
          "\nWindows inference required: No"+
          "\nInternet inference required: No"+
          "\nLast local failure: "+data.optString("last_failure_code","none")+
          "\n\nA model file and a compiled native library must both be "+
          "present before inference can work. Model readiness is NOT "+
          "evidence that an app operation has been carried out.";
      }catch(Exception e){report="Phone AI status unavailable: "+
        e.getClass().getSimpleName();}
      final String text=report;
      runOnUiThread(()->{
        if(destroyed)return;
        new AlertDialog.Builder(this).setTitle("Phone AI status")
          .setMessage(text).setPositiveButton("Close",null).show();
      });
    });
  }
  private void showPhoneAiChat(){
    EditText field=input("",false,"Ask the on-device model");
    field.setSingleLine(false);
    field.setMinLines(3);
    field.setMaxLines(7);
    field.setInputType(InputType.TYPE_CLASS_TEXT|
      InputType.TYPE_TEXT_FLAG_MULTI_LINE);
    new AlertDialog.Builder(this)
      .setTitle("Ask Asterion · on this phone")
      .setMessage("Inference runs locally using the model bundled in this "+
        "signed APK. The response does not execute app commands.")
      .setView(field)
      .setPositiveButton("Generate locally",(dialog,which)->{
        String prompt=field.getText().toString().trim();
        if(prompt.isEmpty()){toast("Enter a question");return;}
        AlertDialog working=new AlertDialog.Builder(this)
          .setTitle("Running on-device inference")
          .setMessage("Loading the verified local model and decoding "+
            "on this phone. Windows and cloud inference are not used.")
          .setCancelable(false).create();
        working.show();
        io.execute(()->{
          String answer;
          try{answer=OnDeviceLlm.generate(getApplicationContext(),prompt);}
          catch(Exception|LinkageError error){
            answer="Local model execution failed: "+
              error.getClass().getSimpleName()+
              ". No text result or completed operation is claimed.";
          }
          final String text=answer;
          runOnUiThread(()->{
            if(working.isShowing())working.dismiss();
            if(destroyed)return;
            new AlertDialog.Builder(this).setTitle("On-device AI result")
              .setMessage(text).setPositiveButton("Close",null).show();
          });
        });
      }).setNegativeButton("Cancel",null).show();
  }

  private void showWindowsIntelligence(){
    String host=prefs.getString("url","").replaceAll("/+$","");
    String token=prefs.getString("token","");
    if(host.isEmpty()||token.isEmpty()){
      toast("Windows Control is not paired");return;
    }
    io.execute(()->{
      HttpURLConnection connection=null;
      String message;
      try{
        connection=(HttpURLConnection)new URL(host+
          "/api/v1/intelligence/capabilities").openConnection();
        connection.setConnectTimeout(4000);
        connection.setReadTimeout(8000);
        connection.setRequestProperty("Authorization","Bearer "+token);
        int status=connection.getResponseCode();
        if(status!=200)throw new IllegalStateException("HTTP "+status);
        byte[] raw=connection.getInputStream().readNBytes(16385);
        if(raw.length>16384)throw new IllegalStateException("Response too large");
        JSONObject data=new JSONObject(new String(raw,StandardCharsets.UTF_8));
        if(!data.optBoolean("ok",false))throw new IllegalStateException("Invalid status");
        message="Local model configured: "+
          (data.optBoolean("local_model_configured")?"Yes":"No")+
          "\\nLocal inference reachability verified: "+
          (data.optBoolean("local_model_reachable_verified")?"Yes":"No")+
          "\\nRegistered cycles (recent): "+data.optInt("registered_cycles_visible",0)+
          "\\nVerified work executor bound: "+
          (data.optBoolean("work_executor_bound")?"Yes":"No")+
          "\\nAutomatic development running: "+
          (data.optBoolean("automatic_project_work_running")?"Yes":"No")+
          "\\n\\n"+data.optString("reason",
            "A verified model and executor are required.");
      }catch(Exception e){
        message="Intelligence capability unavailable: "+
          e.getClass().getSimpleName()+
          ". No autonomous work or inference is claimed.";
      }finally{if(connection!=null)connection.disconnect();}
      final String output=message;
      runOnUiThread(()->{
        if(destroyed)return;
        new AlertDialog.Builder(this).setTitle("AI & development readiness")
          .setMessage(output).setPositiveButton("Close",null).show();
      });
    });
  }
  private JSONObject readOwnerStatus(String path)throws Exception{
    String host=prefs.getString("url","").replaceAll("/+$","");
    String token=prefs.getString("token","");
    if(host.isEmpty()||token.isEmpty())throw new IllegalStateException("Not paired");
    // Only predetermined app-owned authenticated paths may reach this method.
    if(!("/api/v1/diagnostics/coverage".equals(path)||
          "/api/v1/v2/models".equals(path)||
          "/api/v1/v2/skills".equals(path)))
      throw new IllegalArgumentException("Unsupported owner status route");
    HttpURLConnection conn=null;
    try{
      conn=(HttpURLConnection)new URL(host+path).openConnection();
      conn.setRequestMethod("GET");
      conn.setConnectTimeout(4000);conn.setReadTimeout(8000);
      conn.setRequestProperty("Authorization","Bearer "+token);
      if(conn.getResponseCode()!=200)throw new IllegalStateException(
        "Windows HTTP "+conn.getResponseCode());
      byte[] raw=conn.getInputStream().readNBytes(32769);
      if(raw.length>32768)throw new IllegalStateException("Response too large");
      JSONObject obj=new JSONObject(new String(raw,StandardCharsets.UTF_8));
      if(!obj.optBoolean("ok",false))throw new IllegalStateException(
        "Unverified owner status");
      return obj;
    }finally{if(conn!=null)conn.disconnect();}
  }
  private void showWindowsRegistry(String kind){
    if(!"models".equals(kind)&&!"skills".equals(kind))return;
    io.execute(()->{
      String message;
      try{
        JSONObject response=readOwnerStatus("/api/v1/v2/"+kind);
        org.json.JSONArray rows=response.optJSONArray("items");
        int count=rows==null?0:rows.length();
        StringBuilder summary=new StringBuilder()
          .append(count).append(" saved ").append(kind).append("\\n");
        if(count==0)summary.append(
          "\\nNo locally registered entries. This does not install or train a model.");
        else for(int i=0;i<Math.min(12,count);i++){
          JSONObject item=rows.optJSONObject(i);
          if(item!=null)summary.append("\\n• ")
            .append(item.optString("id",item.optString("repo","unknown")))
            .append(" · ").append(item.optString("state","recorded"));
        }
        if("models".equals(kind))summary.append(
          "\\n\\nModel inventory is not evidence of working inference or training.");
        else summary.append(
          "\\n\\nOnly owner-approved deterministic skills can be executed.");
        message=summary.toString();
      }catch(Exception e){
        message="Registry unavailable: "+e.getClass().getSimpleName()+
          ". No missing data or model status is inferred.";
      }
      final String result=message;
      runOnUiThread(()->{
        if(destroyed)return;
        new AlertDialog.Builder(this).setTitle(
          "models".equals(kind)?"Model Laboratory":"Skill Studio")
          .setMessage(result).setPositiveButton("Close",null).show();
      });
    });
  }
  private void showIntegrationCoverage(){
    io.execute(()->{
      String message;
      try{
        JSONObject response=readOwnerStatus("/api/v1/diagnostics/coverage");
        StringBuilder summary=new StringBuilder();
        summary.append("Event sources observed: ")
          .append(response.optInt("recent_event_source_count",0));
        if(!response.optBoolean("phone_app_catalog_available"))
          summary.append("\\nPhone app inventory unavailable");
        if(!response.optBoolean("partner_bridge_catalog_available"))
          summary.append("\\nNative bridge inventory unavailable");
        else summary.append("\\nNative opt-in bridge providers: ")
          .append(response.optInt("native_partner_count",0));
        org.json.JSONArray apps=response.optJSONArray("apps");
        if(apps!=null)for(int i=0;i<Math.min(20,apps.length());i++){
          JSONObject item=apps.optJSONObject(i);
          if(item==null)continue;
          summary.append("\\n\\n").append(item.optString("name","App"))
            .append("\\nBridge: ")
            .append(item.optBoolean("partner_bridge_discovered")?
              (item.optBoolean("partner_bridge_approved")?
                "approved":"requires local approval"):"not discovered")
            .append(" · Recent diagnostic events: ")
            .append(item.optBoolean("recent_instrumented_event_observed")?
              "observed":"not observed");
        }
        summary.append("\\n\\nNo observed event is not proof of a healthy or "+
          "uninstrumented app. Other apps' private logs are inaccessible.");
        message=summary.toString();
      }catch(Exception e){
        message="Integration coverage unavailable: "+
          e.getClass().getSimpleName()+
          ". Existing app access and pairing are unchanged.";
      }
      final String result=message;
      runOnUiThread(()->{
        if(destroyed)return;
        new AlertDialog.Builder(this).setTitle("Asterion app coverage")
          .setMessage(result).setPositiveButton("Close",null).show();
      });
    });
  }
  private void showRemoteSection(String section){
    if(!"desktop".equals(section)&&!"android".equals(section)
       &&!"diagnostics".equals(section))return;
    pendingRemoteSection=section;
    if(currentTab!=1)show(1);
    if(web!=null&&webStarted&&web.getVisibility()==View.VISIBLE)
      web.evaluateJavascript(
        "(function(){if(typeof showPage==='function')showPage("+
        JSONObject.quote(section)+");})()",null);
  }
  private void transferStatus(String message){
    if(transferFeedback!=null)transferFeedback.setText(message);
    if(transferCancelAction!=null)transferCancelAction.setVisibility(activeTransferId==null?View.GONE:View.VISIBLE);
  }
  private void enablePrivatePhoneRelay(){
    // Credentials are entered directly into the native app, never in a chat or
    // GitHub command file. Existing encrypted credentials can be reused.
    try{
      JSONObject state=PhoneGitBridge.status(this);
      if(state.optBoolean("enabled")){
        showPrivatePhoneRelayStatus();return;
      }
      if(state.optBoolean("token_present")){
        new AlertDialog.Builder(this)
          .setTitle("Enable direct phone relay")
          .setMessage("Reuse the existing encrypted repository credential for the optional private queue? This does not install a gateway or create a callable ChatGPT tool.")
          .setPositiveButton("Enable",(dialog,which)->configurePrivatePhoneRelay("",true))
          .setNegativeButton("Cancel",null).show();
        return;
      }
    }catch(Exception e){toast("Phone bridge status unavailable");return;}
    EditText credential=input("",true,"Fine-grained GitHub token");
    LinearLayout layout=v();layout.setPadding(dp(18),dp(10),dp(18),0);
    wide(layout,t("Create a GitHub token restricted to the private "
      +"Azrazieliz/Asterion-Control-Bridge repository, with Contents: Read and write. "
      +"Paste it here only. It is encrypted in Android Keystore storage.",
      12,DesignSystem.MUTED,false));
    gap(layout,12);wide(layout,credential);
    new AlertDialog.Builder(this).setTitle("Enable direct phone relay")
      .setView(layout)
      .setPositiveButton("Enable",(dialog,which)->{
        String token=credential.getText().toString().trim();
        credential.setText("");
        if(token.isEmpty()){toast("A repository-scoped token is required");return;}
        configurePrivatePhoneRelay(token,true);
      }).setNegativeButton("Cancel",null).show();
  }
  private void configurePrivatePhoneRelay(String token,boolean enabled){
    if(phoneBridgeFeedback!=null)phoneBridgeFeedback.setText("Configuring private phone relay...");
    io.execute(()->{
      try{
        JSONObject state=PhoneGitBridge.configure(this,token,enabled);
        runOnUiThread(()->{
          if(destroyed)return;
          if(phoneBridgeFeedback!=null)phoneBridgeFeedback.setText(
            state.optBoolean("enabled")?"Enabled · checking private command queue":"Relay disabled");
          if(enabled)startAgent();
          showPrivatePhoneRelayStatus();
        });
      }catch(Exception e){
        runOnUiThread(()->{
          if(phoneBridgeFeedback!=null)phoneBridgeFeedback.setText(
            "Unable to configure relay: "+e.getClass().getSimpleName());
        });
      }
    });
  }
  private void showPrivatePhoneRelayStatus(){
    try{
      JSONObject state=PhoneGitBridge.status(this);
      boolean enabled=state.optBoolean("enabled");
      long polled=state.optLong("last_poll_ms",0);
      long success=state.optLong("last_success_ms",0);
      String text=(enabled?"Enabled":"Disabled")
        +" · credential: "+(state.optBoolean("token_present")?"saved":"missing")
        +" · phone service: "+(AgentService.running?"running":"stopped")
        +"\nLast poll: "+(polled>0?new java.util.Date(polled).toString():"never")
        +"\nLast success: "+(success>0?new java.util.Date(success).toString():"never")
        +"\nCompleted commands: "+state.optLong("completed",0)
        +"\nLast error: "+state.optString("last_error","none");
      if(phoneBridgeFeedback!=null)phoneBridgeFeedback.setText(
        enabled?(polled>0L&&System.currentTimeMillis()-polled<30000L&&
           success>0L&&System.currentTimeMillis()-success<30000L?
           "Recently active · live connection not guaranteed":
           success>0L?"Enabled · historical success only":"Enabled · not yet verified"):
        "Disabled");
      new AlertDialog.Builder(this).setTitle("Private phone relay status")
        .setMessage(text).setPositiveButton("Close",null).show();
    }catch(Exception e){toast("Relay status unavailable");}
  }
  private void disablePrivatePhoneRelay(){
    new AlertDialog.Builder(this).setTitle("Disable phone relay")
      .setMessage("Stop polling the private command queue? The encrypted token will remain saved for later reactivation.")
      .setPositiveButton("Disable",(dialog,which)->configurePrivatePhoneRelay("",false))
      .setNegativeButton("Cancel",null).show();
  }

  private void promptWifiTransfer(){
    if(prefs.getString("url","").isEmpty()||prefs.getString("token","").isEmpty()){
      toast("Pair your Windows computer first");return;
    }
    EditText field=input("",false,"PC path, for example Downloads\\report.zip");
    new AlertDialog.Builder(this)
      .setTitle("Send PC file over Wi-Fi")
      .setMessage("Enter the path of an existing Windows file inside the authorized Asterion Control PC root. The phone receives it in Downloads/Asterion Control.")
      .setView(field)
      .setPositiveButton("Transfer",(d,w)->{
        String pcPath=field.getText().toString().trim();
        if(pcPath.isEmpty()){toast("Choose a Windows file path");return;}
        submitWifiTransfer(pcPath);
      })
      .setNegativeButton("Cancel",null).show();
  }
  private JSONObject pcTransferRequest(String path,String method,JSONObject body)throws Exception{
    String url=prefs.getString("url","").replaceAll("/+$","");
    String token=prefs.getString("token","");
    if(url.isEmpty()||token.isEmpty())throw new IllegalStateException("Windows not paired");
    HttpURLConnection conn=(HttpURLConnection)new URL(url+path).openConnection();
    try{
      conn.setConnectTimeout(4000);conn.setReadTimeout(9000);
      conn.setRequestMethod(method);
      conn.setRequestProperty("Authorization","Bearer "+token);
      if(body!=null){
        conn.setDoOutput(true);conn.setRequestProperty("Content-Type","application/json");
        try(OutputStream out=conn.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
      }
      int code=conn.getResponseCode();
      java.io.InputStream input=code<400?conn.getInputStream():conn.getErrorStream();
      String json=input==null?"{}":new String(input.readNBytes(4000),StandardCharsets.UTF_8);
      JSONObject parsed=new JSONObject(json);
      if(code>=400)throw new IllegalStateException("HTTP "+code+": "+parsed.optString("detail","transfer refused"));
      return parsed;
    }finally{conn.disconnect();}
  }
  private void submitWifiTransfer(String pcPath){
    if(activeTransferId!=null){toast("Cancel or finish the current transfer first");return;}
    transferStatus("Preparing authenticated Wi-Fi transfer…");
    io.execute(()->{
      try{
        JSONObject out=pcTransferRequest("/api/v1/phone/transfers","POST",new JSONObject().put("pc_path",pcPath));
        String id=out.getString("id");
        runOnUiThread(()->{
          activeTransferId=id;
          transferStatus("Transfer request accepted · awaiting first progress · "+pcPath);
          pollWifiTransfer(id,0);
        });
      }catch(Exception e){runOnUiThread(()->transferStatus("Transfer not started: "+e.getMessage()));}
    });
  }
  private void pollWifiTransfer(String id,int attempts){
    if(destroyed||!id.equals(activeTransferId))return;
    if(attempts>1800){transferStatus("Transfer status timed out. Check Downloads and Windows.");activeTransferId=null;return;}
    io.execute(()->{
      try{
        JSONObject job=pcTransferRequest("/api/v1/phone/transfers/"+id,"GET",null);
        runOnUiThread(()->{
          if(destroyed||!id.equals(activeTransferId))return;
          String state=job.optString("state","unknown");
          long sent=job.optLong("bytes_sent",0),total=job.optLong("size",0);
          if(state.equals("completed")){
            JSONObject receipt=job.optJSONObject("result");
            activeTransferId=null;
            transferStatus(receipt!=null&&receipt.optString("location").length()>0&&
                 receipt.optString("sha256").matches("[a-fA-F0-9]{64}")?
                 "Windows reports transfer finished at "+receipt.optString("location")+
                   "\nReported SHA-256: "+receipt.optString("sha256"):
                 "Windows reported transfer completion without an independently checkable phone receipt");
          }else if(state.equals("failed")||state.equals("cancelled")){
            activeTransferId=null;
            transferStatus("Transfer "+state+": "+job.optString("error",""));
          }else{
            double percent=total>0?100.0*sent/total:0;
            transferStatus(state+" · "+sent+" / "+total+" bytes · "+
              String.format(Locale.US,"%.1f",percent)+"%");
            handler.postDelayed(()->pollWifiTransfer(id,attempts+1),750);
          }
        });
      }catch(Exception e){runOnUiThread(()->{
        if(!destroyed&&id.equals(activeTransferId)){
          transferStatus("Transfer status unavailable: "+e.getMessage());
          handler.postDelayed(()->pollWifiTransfer(id,attempts+1),1500);
        }
      });}
    });
  }
  private void cancelWifiTransfer(){
    String id=activeTransferId;
    if(id==null){toast("No active transfer");return;}
    io.execute(()->{
      try{pcTransferRequest("/api/v1/phone/transfers/"+id+"/cancel","POST",new JSONObject());
        runOnUiThread(()->transferStatus("Cancellation requested"));
      }catch(Exception e){runOnUiThread(()->transferStatus("Cancellation failed: "+e.getMessage()));}
    });
  }

  private void showUpdateFeedback(String message){
    if(updateFeedback!=null)updateFeedback.setText(message);
    else toast(message);
  }

  /** Native private-network peer discovery; no ADB or remote-desktop dependency. */
  private void discoverComputer(){
    if(remoteConnection!=null)remoteConnection.setText("Searching for your Windows computer…");
    io.execute(()->{
      try(DatagramSocket socket=new DatagramSocket()){
        socket.setBroadcast(true);socket.setSoTimeout(2200);
        byte[] bytes="ASTERION_CONTROL_DISCOVER_V1".getBytes(StandardCharsets.UTF_8);
        socket.send(new DatagramPacket(bytes,bytes.length,InetAddress.getByName("255.255.255.255"),8912));
        byte[] replyBytes=new byte[512];DatagramPacket reply=new DatagramPacket(replyBytes,replyBytes.length);
        socket.receive(reply);
        JSONObject info=new JSONObject(new String(reply.getData(),0,reply.getLength(),StandardCharsets.UTF_8));
        if(!"asterion-control".equals(info.optString("service"))||info.optInt("version")!=1)throw new IllegalArgumentException("Unexpected service");
        InetAddress peer=reply.getAddress();
        if(!(peer.isSiteLocalAddress()||peer.isLoopbackAddress()||peer.getHostAddress().startsWith("100.")))throw new IllegalArgumentException("Not private LAN");
        String address="http://"+peer.getHostAddress()+":"+info.optInt("port",8911);
        runOnUiThread(()->showPairingPrompt(address,info.optString("name","Windows computer")));
      }catch(Exception e){
        if(discoverByPrivateTcp())return;
        runOnUiThread(()->{
        if(remoteConnection!=null)remoteConnection.setText("Computer discovery not available on this network");
        new AlertDialog.Builder(this).setTitle("Computer not found")
          .setMessage("Start the Windows agent on the same private network or VPN. Advanced pairing remains available if discovery is blocked.")
          .setPositiveButton("Advanced pairing",(d,w)->{
            advancedSetupVisible=true;if(advancedSetup!=null)advancedSetup.setVisibility(View.VISIBLE);
          }).setNegativeButton("Cancel",null).show();
      });}
    });
  }
  /** TCP fallback for Windows installations whose private firewall blocks UDP discovery.
      Tries the phone's current /24 subnet, limited by timeouts and a bounded pool. */
  private boolean discoverByPrivateTcp(){
    String local=ipAddress();
    String[] octets=local.split("\\.");
    if(octets.length!=4)return false;
    final String prefix=octets[0]+"."+octets[1]+"."+octets[2]+".";
    java.util.concurrent.ExecutorService scan=Executors.newFixedThreadPool(24);
    CompletionService<JSONObject> completions=new ExecutorCompletionService<>(scan);
    int count=0;
    for(int host=1;host<=254;host++){
      final String ip=prefix+host;
      if(ip.equals(local))continue;
      completions.submit(()->{
        HttpURLConnection connection=null;
        try{
          connection=(HttpURLConnection)new URL("http://"+ip+":8911/api/v1/discovery").openConnection();
          connection.setConnectTimeout(350);
          connection.setReadTimeout(350);
          if(connection.getResponseCode()!=200)return null;
          JSONObject response=new JSONObject(new String(connection.getInputStream().readNBytes(1024),StandardCharsets.UTF_8));
          if(!"asterion-control".equals(response.optString("service"))||response.optInt("version")!=1)return null;
          return new JSONObject().put("address","http://"+ip+":8911").put("name",response.optString("name","Windows computer"));
        }catch(Exception error){return null;}
        finally{if(connection!=null)connection.disconnect();}
      });
      count++;
    }
    boolean found=false;
    try{
      long deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(6);
      for(int i=0;i<count;i++){
        long remaining=deadline-System.nanoTime();
        if(remaining<=0)break;
        Future<JSONObject> result=completions.poll(remaining,TimeUnit.NANOSECONDS);
        if(result==null)break;
        JSONObject response=result.get();
        if(response!=null){
          String address=response.getString("address"),name=response.getString("name");
          runOnUiThread(()->showPairingPrompt(address,name));
          found=true;break;
        }
      }
    }catch(Exception ignored){}
    finally{scan.shutdownNow();}
    return found;
  }
  private void showPairingPrompt(String address,String name){
    EditText code=input("",false,"8-digit code on your Windows computer");
    code.setInputType(InputType.TYPE_CLASS_NUMBER);
    code.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(8)});
    new AlertDialog.Builder(this).setTitle("Connect to "+name)
      .setMessage("Enter the one-time code shown by the Asterion Control Windows agent. Future connections use saved device authorization.")
      .setView(code).setNegativeButton("Cancel",null)
      .setPositiveButton("Connect",(d,w)->completePairing(address,code.getText().toString().trim())).show();
  }
  private void completePairing(String address,String code){
    if(!code.matches("[0-9]{8}")){toast("Enter the eight-digit code");return;}
    io.execute(()->{
      HttpURLConnection conn=null;
      try{
        conn=(HttpURLConnection)new URL(address+"/api/v1/pair").openConnection();
        conn.setRequestMethod("POST");conn.setDoOutput(true);conn.setConnectTimeout(4500);conn.setReadTimeout(6000);
        conn.setRequestProperty("Content-Type","application/json");
        byte[] body=new JSONObject().put("name",Build.MODEL).put("code",code).toString().getBytes(StandardCharsets.UTF_8);
        try(OutputStream out=conn.getOutputStream()){out.write(body);}
        int codeResponse=conn.getResponseCode();
        if(codeResponse!=200){
          String reason=codeResponse==401?"Incorrect or expired code":codeResponse==403?"The Windows agent rejected this network":codeResponse==429?"Too many attempts; request a new code":codeResponse==404?"The Windows agent needs updating":("Windows returned HTTP "+codeResponse);
          throw new IllegalStateException(reason);
        }
        JSONObject response=new JSONObject(new String(conn.getInputStream().readNBytes(16384),StandardCharsets.UTF_8));
        String token=response.getString("token");
        if(token.length()<32)throw new IllegalArgumentException("Invalid token");
        runOnUiThread(()->{
          prefs.edit().putString("url",address).putString("token",token).apply();
          if(serverUrl!=null)serverUrl.setText(address);
          if(serverToken!=null)serverToken.setText("");
          setPairingFeedback("Windows paired. Starting phone control and registering this device…");
          checkHost();toast("Windows paired; checking device registration");show(3);
          startAgent();
          handler.postDelayed(()->{if(AgentService.running)registerPhone();else if(remoteConnection!=null)remoteConnection.setText("Windows paired; turn on phone access to register this device");},1400);
        });
      }catch(Exception e){
        String message=e instanceof java.net.SocketTimeoutException?"Windows connection timed out":e instanceof java.net.ConnectException?"Cannot reach Windows on this network":e.getMessage()==null?e.getClass().getSimpleName():e.getMessage();
        runOnUiThread(()->{
          setPairingFeedback("Pairing failed: "+message);
          toast("Pairing failed: "+message);
        });
      }
      finally{if(conn!=null)conn.disconnect();}
    });
  }
  private void setPairingFeedback(String message){
    if(pairingFeedback!=null)pairingFeedback.setText(message);
    if(remoteConnection!=null)remoteConnection.setText(message);
  }
  private void toggleAdvancedSetup(){
    advancedSetupVisible=!advancedSetupVisible;
    if(advancedSetup!=null) advancedSetup.setVisibility(advancedSetupVisible?View.VISIBLE:View.GONE);
  }
  private void enablePhoneControl(){
    startAgent();
    if(ControlAccessibilityService.active==null){
      toast("Enable Asterion Control under Installed accessibility apps");
      try{startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));}
      catch(Exception e){toast("Accessibility settings unavailable");}
    }else{
      toast("Phone remote control enabled");
    }
    handler.postDelayed(this::updateHealth,550);
    if(!prefs.getString("url","").isEmpty() && !prefs.getString("token","").isEmpty())
      handler.postDelayed(()->{if(AgentService.running)registerPhone();},1100);
  }
  private void labeledInput(LinearLayout parent,String label,String hint,boolean secret,int mode){wide(parent,eyebrow(label));gap(parent,7);}
  private EditText input(String value,boolean secret,String hint){EditText field=new EditText(this);field.setSingleLine(true);field.setText(value);field.setHint(hint);field.setTextColor(DesignSystem.TEXT);field.setHintTextColor(DesignSystem.MUTED);field.setTextSize(13);field.setPadding(dp(15),dp(14),dp(13),dp(14));
    field.setBackground(DesignSystem.shape(this,0xFF0D1527,DesignSystem.EDGE,13));
    if(secret)field.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);return field;}
  private void show(int page){currentTab=page;for(int i=0;i<pages.length;i++){
      pages[i].setVisibility(i==page?View.VISIBLE:View.GONE);boolean selected=i==page;
      tabLabels[i].setTextColor(selected?DesignSystem.TEXT:DesignSystem.MUTED);tabIcons[i].tint(selected?DesignSystem.PURPLE:DesignSystem.MUTED);
      if(selected)tabButtons[i].setBackground(DesignSystem.shape(this,0xFF292743,0,15));else tabButtons[i].setBackgroundColor(Color.TRANSPARENT);
    }
    if(page==1){connectRemote(false);if(!hostRefreshing)checkHost();}if(page==0||page==2||page==3||page==4)updateHealth();
  }
  private void save(){prefs.edit().putString("url",serverUrl.getText().toString().trim())
    .putString("phoneip",localAddress.getText().toString().trim()).apply();updateHealth();}
  private void connectRemote(boolean force){String url=prefs.getString("url","");String token=prefs.getString("token","");
    if(!url.matches("(?i)^https?://[^\\s/]+(?:/.*)?$")||token.isEmpty()){
      if(remoteConnection!=null)remoteConnection.setText("Not paired · Open Devices to configure");
      if(emptyRemote!=null)emptyRemote.setVisibility(View.VISIBLE);if(web!=null)web.setVisibility(View.GONE);return;}
    if(remoteConnection!=null)remoteConnection.setText("Connecting to "+url.replaceFirst("^https?://",""));
    emptyRemote.setVisibility(View.GONE);web.setVisibility(View.VISIBLE);
    if(force||!webStarted){webStarted=true;web.loadUrl(url.replaceAll("/+$","")+"/?embedded=1");}
  }
  private void updateHealth(){try{
    Intent b=registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));int level=b==null?-1:b.getIntExtra(BatteryManager.EXTRA_LEVEL,-1);
    int scale=b==null?-1:b.getIntExtra(BatteryManager.EXTRA_SCALE,-1);double percent=level>=0&&scale>0?100.0*level/scale:-1;
    int rawTemp=b==null?-1:b.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,-1);
    boolean plugged=b!=null&&b.getIntExtra(BatteryManager.EXTRA_PLUGGED,0)!=0;
    ActivityManager.MemoryInfo m=new ActivityManager.MemoryInfo();((ActivityManager)getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(m);
    StatFs fs=new StatFs(Environment.getDataDirectory().getAbsolutePath());
    PowerManager power=(PowerManager)getSystemService(POWER_SERVICE);int thermal=power.getCurrentThermalStatus();String thermalText=thermalName(thermal);
    int tint=thermal>=PowerManager.THERMAL_STATUS_SEVERE?DesignSystem.BAD:thermal>=PowerManager.THERMAL_STATUS_MODERATE?DesignSystem.WARNING:DesignSystem.TEAL;
    if(homeBattery!=null)homeBattery.setText(percent<0?"—":Math.round(percent)+"%");
    if(homeThermal!=null){homeThermal.setText(thermalText);homeThermal.setTextColor(tint);homeThermal.setTextSize(thermalText.length()>9?12:17);}
    if(homeMemory!=null)homeMemory.setText(String.format(Locale.US,"%.1f GB",m.availMem/1e9));
    if(homeAgent!=null)homeAgent.setText(AgentService.running?
       (AgentService.listenerReady?"Phone listener active · Windows link checked separately":"Phone agent starting · listener unverified"):
       "Phone agent stopped");
    if(healthBattery!=null)healthBattery.setText(percent<0?"—":Math.round(percent)+"%");
    if(healthTemp!=null)healthTemp.setText(rawTemp<0?"—":String.format(Locale.US,"%.1f°",rawTemp/10.0));
    if(healthMemory!=null)healthMemory.setText(String.format(Locale.US,"%.1f GB",m.availMem/1e9));
    if(healthThermal!=null){healthThermal.setText(thermalText);healthThermal.setTextColor(tint);}
    if(healthActionStatus!=null){
      JSONObject p=PerformanceManager.status(this);
      int every=p.optInt("capture_interval_ms",90);
      String details="Automatic · "+p.optString("reason","normal")+
        "\nConfigured capture target: "+every+" ms/frame (actual FPS not measured)";
      healthActionStatus.setText(details);
    }
    if(healthStorage!=null)healthStorage.setText(String.format(Locale.US,"%.1f GB free of %.0f GB",fs.getAvailableBytes()/1e9,fs.getTotalBytes()/1e9));
    if(healthWifi!=null)healthWifi.setText(networkName());
    if(batteryMeter!=null)batteryMeter.setProgress(percent<0?0:(float)(percent/100));
    if(memoryMeter!=null)memoryMeter.setProgress((float)(1.0-(double)m.availMem/(double)m.totalMem));
    if(storageMeter!=null)storageMeter.setProgress((float)(1.0-(double)fs.getAvailableBytes()/(double)fs.getTotalBytes()));
    if(phoneAccessAction!=null)phoneAccessAction.setVisibility(
      ControlAccessibilityService.active==null?View.VISIBLE:View.GONE);
    if(phoneCaptureAction!=null)phoneCaptureAction.setVisibility(
      CaptureService.active?View.GONE:View.VISIBLE);
    if(phoneStopAction!=null)phoneStopAction.setVisibility(
      (AgentService.running||CaptureService.active)?View.VISIBLE:View.GONE);
    if(voiceStartAction!=null)voiceStartAction.setVisibility(
      VoiceDialogueService.active==null?View.VISIBLE:View.GONE);
    if(voiceStopAction!=null)voiceStopAction.setVisibility(
      VoiceDialogueService.active==null?View.GONE:View.VISIBLE);
    if(voiceTalkAction!=null)voiceTalkAction.setVisibility(
      VoiceDialogueService.active==null?View.GONE:View.VISIBLE);
    if(agentConnection!=null){agentConnection.setText(AgentService.running?(AgentService.listenerReady?"Listener active":"Starting / unavailable"):"Stopped");agentConnection.setTextColor(AgentService.running?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(captureConnection!=null){boolean fresh=CaptureService.active&&CaptureService.latestAtMs>0L&&
         System.currentTimeMillis()-CaptureService.latestAtMs<5000L;
       captureConnection.setText(!CaptureService.active?"Off":fresh?"Fresh frames on phone":"Capture active · frames stale");
       captureConnection.setTextColor(fresh?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(accessConnection!=null){accessConnection.setText(ControlAccessibilityService.active!=null?"Authorized":"Not enabled");accessConnection.setTextColor(ControlAccessibilityService.active!=null?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(phoneAddress!=null){
      boolean requested=getSharedPreferences("agent",MODE_PRIVATE)
        .getBoolean(AgentService.PREF_REMOTE_ENABLED,false);
      phoneAddress.setText(AgentService.running?
        (AgentService.listenerReady?"Phone listener active · Windows reachability checked separately":
         "Phone service starting · listener unverified"):
        requested?"Phone access requested but agent stopped":"Remote phone access disabled");
    }
    if(privacyStatus!=null)privacyStatus.setText(
      AgentService.running?"Phone agent running · "+(ControlAccessibilityService.active!=null?
          "input authorized":"touch permission needed")+" · "+(CaptureService.active?
          "screen capture active (remote delivery unverified)":"screen capture off"):
       "Phone agent stopped · "+(CaptureService.active?"local capture still running":"capture off")+
       " · input permission "+(ControlAccessibilityService.active!=null?"granted":"not granted"));
    if(headerStatus!=null)headerStatus.setText(
       CaptureService.active&&CaptureService.latestAtMs>0L&&
       System.currentTimeMillis()-CaptureService.latestAtMs<5000L?
         "LOCAL CAPTURE LIVE":AgentService.running?"PHONE SERVICE ON":"ON DEVICE");
    updateConnectionIssue();
    if(!hostRefreshing&&(currentTab==0||currentTab==2||currentTab==3)&&System.currentTimeMillis()-lastHostRefresh>12000){lastHostRefresh=System.currentTimeMillis();checkHost();}
  }catch(Exception ignored){} }
  private void applyPerformanceAction(String mode){
    try{
      JSONObject result="boost".equals(mode)?
        PerformanceManager.prioritizeForegroundNow(this):
        PerformanceManager.setMode(this,mode);
      if(result.optBoolean("ok")){
        updateHealth();
        toast("Control workload: "+result.optString("reason","updated"));
      }else toast("Control performance action did not complete");
    }catch(Exception e){toast("Performance action rejected: "+e.getClass().getSimpleName());}
  }
  private void managePcPerformance(String mode){
    String url=prefs.getString("url","").replaceAll("/+$","");
    String token=prefs.getString("token","");
    if(url.isEmpty()||token.isEmpty()){
      toast("Pair the Windows Control agent first");return;
    }
    io.execute(()->{
      String result;
      java.net.HttpURLConnection connection=null;
      try{
        connection=(java.net.HttpURLConnection)new java.net.URL(
          url+"/api/v1/performance/jobs").openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(4000);connection.setReadTimeout(6000);
        connection.setDoOutput(true);
        connection.setRequestProperty("Authorization","Bearer "+token);
        connection.setRequestProperty("Content-Type","application/json");
        byte[] payload=new JSONObject().put("mode",mode).toString()
          .getBytes(java.nio.charset.StandardCharsets.UTF_8);
        try(java.io.OutputStream out=connection.getOutputStream()){out.write(payload);}
        if(connection.getResponseCode()!=200)throw new IllegalStateException(
          "Windows denied priority change (HTTP "+connection.getResponseCode()+")");
        JSONObject reply=new JSONObject(new String(connection.getInputStream().readNBytes(16384),
          java.nio.charset.StandardCharsets.UTF_8));
        if(!reply.optBoolean("ok"))throw new IllegalStateException("No confirmed priority action");
        result="PC jobs adjusted: "+reply.optJSONArray("applied").length()+
          " · unchanged: "+reply.optJSONArray("skipped").length()+
          "\nScope: Control-started Windows processes only";
      }catch(Exception e){result="PC job priority unavailable: "+e.getClass().getSimpleName();}
      finally{if(connection!=null)connection.disconnect();}
      final String receipt=result;
      runOnUiThread(()->{if(pcPerformanceActionStatus!=null)pcPerformanceActionStatus.setText(receipt);});
    });
  }
  private String thermalName(int level){switch(level){case PowerManager.THERMAL_STATUS_NONE:return "Nominal";case PowerManager.THERMAL_STATUS_LIGHT:return "Light";case PowerManager.THERMAL_STATUS_MODERATE:return "Moderate";case PowerManager.THERMAL_STATUS_SEVERE:return "Severe";case PowerManager.THERMAL_STATUS_CRITICAL:return "Critical";case PowerManager.THERMAL_STATUS_EMERGENCY:return "Emergency";case PowerManager.THERMAL_STATUS_SHUTDOWN:return "Shutdown";default:return "Unavailable";}}
  private String networkName(){try{ConnectivityManager cm=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);Network n=cm.getActiveNetwork();NetworkCapabilities cap=cm.getNetworkCapabilities(n);if(cap==null)return "Offline";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))return "Wi-Fi connected";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))return "Mobile data";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_VPN))return "VPN connected";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))return "Ethernet";return "Connected";}catch(Exception e){return "Unavailable";}}
  private void checkHost(){
    String url=prefs.getString("url","").replaceAll("/+$",""),token=prefs.getString("token","");
    if(url.isEmpty()||token.isEmpty()){
      workerPhoneState="Windows not paired";
      if(pcConnection!=null)pcConnection.setText("Not linked yet · Connect to start");
      if(hostHealth!=null)hostHealth.setText("Windows agent not paired.");
      updateConnectionIssue();return;
    }
    hostRefreshing=true;
    io.execute(()->{
      String status="Offline · Check connection",metric="Windows telemetry unavailable";
      String peer="Worker not reachable";
      try{
        HttpURLConnection c=(HttpURLConnection)new URL(url+"/api/v1/device-health").openConnection();
        try{
          c.setConnectTimeout(2400);c.setReadTimeout(2600);
          c.setRequestProperty("Authorization","Bearer "+token);
          int code=c.getResponseCode();
          if(code==200){
            byte[] bytes=c.getInputStream().readNBytes(500000);
            JSONObject data=new JSONObject(new String(bytes,StandardCharsets.UTF_8));
            status="Online · Secure key accepted";
            double cpu=data.optDouble("cpu_percent",-1);
            JSONObject mem=data.optJSONObject("memory");
            metric="CPU "+(cpu>=0?String.format(Locale.US,"%.1f%%",cpu):"—")
              +"  ·  RAM "+(mem!=null?mem.optInt("percent")+"%":"—")+"\n\n";
            JSONObject thermal=data.optJSONObject("thermals");
            metric+=thermal!=null&&thermal.optBoolean("available")
              ?"Thermal sensors available":"No OS thermal sensors reported";
          }else{
            status="Windows rejected request · HTTP "+code;
            peer=code==401||code==403?"Windows rejected the saved authorization (HTTP "+code+")"
              :"Windows worker health returned HTTP "+code;
            ConnectionDiagnostics.failure(this,"windows_http_"+code,peer);
          }
        }finally{c.disconnect();}
        if(status.startsWith("Online")){
          HttpURLConnection phoneConn=(HttpURLConnection)new URL(url+"/api/v1/phone").openConnection();
          try{
            phoneConn.setConnectTimeout(2800);phoneConn.setReadTimeout(4500);
            phoneConn.setRequestProperty("Authorization","Bearer "+token);
            int code=phoneConn.getResponseCode();
            if(code==200){
              JSONObject p=new JSONObject(new String(phoneConn.getInputStream().readNBytes(16384),StandardCharsets.UTF_8));
              if(p.optBoolean("reachable")){
                peer="Windows verified native phone agent reachable";
                ConnectionDiagnostics.success(this);
              }else{
                String why=p.optString("reason","");
                peer=why.isEmpty()?"Windows worker cannot reach Android agent":why;
                ConnectionDiagnostics.failure(this,"worker_phone_unreachable",peer);
              }
            }else{
              peer="Windows-to-phone status returned HTTP "+code;
              ConnectionDiagnostics.failure(this,"worker_probe_http_"+code,peer);
            }
          }finally{phoneConn.disconnect();}
        }
      }catch(Exception ex){
        peer="Windows link probe failed: "+ex.getClass().getSimpleName();
        ConnectionDiagnostics.failure(this,"worker_probe_failed",peer);
      }
      final String state=status,details=metric,phoneStatus=peer;
      runOnUiThread(()->{
        hostRefreshing=false;if(destroyed)return;
        workerPhoneState=phoneStatus;
        if(pcConnection!=null)pcConnection.setText(state);
        if(hostHealth!=null)hostHealth.setText(details);
        if(remoteConnection!=null)remoteConnection.setText(
          state.startsWith("Online")?"Windows worker online":state);
        updateConnectionIssue();
      });
    });
  }
  private void startAgent(){try{
    // Notification permission is not a prerequisite for a user-started foreground agent.
    // Android can run the service even if notification posting is denied.
    if(Build.VERSION.SDK_INT>=33&&
       checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED&&
       !prefs.getBoolean("asked_notification",false)){
      prefs.edit().putBoolean("asked_notification",true).apply();
      requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFICATION_REQUEST);
    }
    startForegroundService(new Intent(this,AgentService.class));handler.postDelayed(()->{updateHealth();toast(AgentService.running?"Phone agent enabled":"Agent could not start; check device permissions");},700);
    }catch(Exception e){toast("Unable to start agent: "+e.getClass().getSimpleName());}}
  private void stopAgent(){
    getSharedPreferences("agent",MODE_PRIVATE).edit().putBoolean(AgentService.PREF_REMOTE_ENABLED,false).apply();
    stopService(new Intent(this,AgentService.class));
    handler.postDelayed(this::updateHealth,450);
    toast("Phone agent disabled");
  }
  private void showAwayFromHomeStatus(){
    try{
      JSONObject network=TransportConnectivity.report(this);
      JSONObject direct=PhoneDirectMcp.status();
      boolean ready=direct.optBoolean("connected",false);
      String report="Network: "+network.optString("network","offline")+
        "\nInternet validated: "+network.optBoolean("validated")+
        "\nDirect authenticated connection: "+ready+
        "\nState: "+direct.optString("phase","stopped")+
        "\nLast direct success: "+direct.optLong("last_success_ms",0)+
        "\nLast error: "+direct.optString("last_error","none");
      new AlertDialog.Builder(this).setTitle("Direct mobile-data Control")
        .setMessage(report).setPositiveButton("Close",null).show();
    }catch(Exception e){toast("Direct connection status unavailable");}
  }
  private void showCycleStatus(){
    try{
      JSONObject ledger=ContinuationLedger.get(this).status();
      JSONObject cycle=ContinuationCycle.get(this).status();
      String information="Development cycle: "+cycle.optString("state","idle")
        +"\nActive: "+cycle.optBoolean("active",false)
        +"  |  Current turn number: "+cycle.optInt("index",0)
        +"  |  Verified replies: "+cycle.optInt("ack_count",0)
        +"\nTotal-turn limit: "+(cycle.optBoolean("active",false)?
          (cycle.optBoolean("overnight_unbounded",false)?"None (until stop or genuine completion)":"Owner-configured"):
          "No cycle running")
        +"\nSubstantial work target: ~30 minutes per turn (25-minute minimum quality warning)"
        +"\nAction performance targets (not verified measurements): <10 seconds end-to-end; trivial navigation ~1 second"
        +"\nCurrent chat: "+cycle.optInt("messages_in_chat",0)+"/"+cycle.optInt("chat_rollover_messages",20)+" messages"
        +"\nAutomatic rollover count: "+cycle.optInt("rollover_count",0)
        +"\nContinuation enabled: "+ledger.optBoolean("enabled",false)
        +"\nCheckpoint: "+ledger.optString("state","idle")
        +"\nLast error: "+cycle.optString("last_error","none")
        +"\nA cycle is a long-running sequence of substantive ChatGPT turns, not one tap or one turn."
        +"\nA real reply/receipt is required before any continuation; uncertain sends are never replayed.";
      new AlertDialog.Builder(this).setTitle("Continuous development cycle status")
        .setMessage(information).setPositiveButton("Close",null).show();
    }catch(Exception e){toast("Cycle status unavailable: "+e.getClass().getSimpleName());}
  }
  private void testVoiceDialogue(){
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
      runVoiceTestAfterPermission=true;
      requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},MICROPHONE_REQUEST);
      return;
    }
    try {
      Intent test=new Intent(this,VoiceDialogueService.class).setAction("TEST");
      startForegroundService(test);
      if(voiceTestStatus!=null)voiceTestStatus.setText("Starting audible test question…");
      monitorVoiceTest(System.currentTimeMillis()+65000L);
    }catch(Exception e){
      if(voiceTestStatus!=null)voiceTestStatus.setText("Test start failed: "+e.getClass().getSimpleName());
    }
  }
  private void monitorVoiceTest(long until){
    handler.postDelayed(()->{
      if(destroyed||voiceTestStatus==null)return;
      VoiceDialogueService service=VoiceDialogueService.active;
      try {
        if(service!=null){
          JSONObject report=service.report();
          String phase=report.optString("phase","initializing");
          String answer=report.optString("transcript","");
          String problem=report.optString("error","");
          String backend=report.optString("recognizer_backend","none");
          String speaker=report.optBoolean("speaker_finished")?
            "Speaker completed":report.optBoolean("speaker_started")?
            "Speaker started":"Speaker not confirmed";
          voiceTestStatus.setText("Voice test: "+phase+" | "+speaker+" | speech: "+backend+
            (answer.isEmpty()?"":" — heard: "+answer)+
            (problem.isEmpty()?"":" — "+problem));
          if("answered".equals(phase)||"failed".equals(phase)||
             "unavailable".equals(phase))return;
        }
      }catch(Exception ignored){}
      if(System.currentTimeMillis()<until)monitorVoiceTest(until);
      else voiceTestStatus.setText("Voice test timed out; no successful transcript");
    },350);
  }
  private void showVoiceAnswerStatus(){
    try{
      VoiceDialogueService session=VoiceDialogueService.active;
      if(session==null){toast("Speech session not enabled");return;}
      JSONObject report=session.report();
      String message="Phase: "+report.optString("phase")+
        "\nSpeaker started: "+report.optBoolean("speaker_started")+
        "\nSpeaker completed: "+report.optBoolean("speaker_finished")+
        "\nOffline recognition available: "+report.optBoolean("on_device_recognition")+
        "\nMicrophone listening: "+report.optBoolean("microphone_active")+
        "\nAnswer pending acknowledgment: "+report.optBoolean("answer_pending_ack")+
        "\nRecognized answer: "+report.optString("transcript","")+
        "\nError: "+report.optString("error","none");
      new AlertDialog.Builder(this).setTitle("Speaker and microphone status")
        .setMessage(message).setPositiveButton("Close",null).show();
    }catch(Exception e){toast("Voice status unavailable");}
  }
  private void startVoiceQuestions(){
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){
      requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},MICROPHONE_REQUEST);
      return;
    }
    try{startForegroundService(new Intent(this,VoiceDialogueService.class));
      toast("Voice questions enabled. Microphone listens only after a question");}
    catch(Exception e){toast("Android could not start the voice session");}
  }
  private void startAsterionObservation(){
    // The user selects an installed app by its actual label, not by typing
    // implementation package identifiers. Control remains a tool interface.
    List<Map.Entry<String,String>> all=new ArrayList<>();
    for(Map.Entry<String,String> item:AppCatalog.launchable(this).entrySet()){
      String pkg=item.getKey();
      if(pkg.equals("com.openai.chatgpt")||pkg.equals("com.asterion.control")
        ||pkg.startsWith("com.android.")||pkg.startsWith("com.google.android.")
        ||pkg.startsWith("com.samsung.android.")||pkg.startsWith("com.sec.android."))
        continue;
      all.add(item);
    }
    all.sort(Comparator.comparing(x->x.getValue().toLowerCase(Locale.ROOT)));
    if(all.isEmpty()){toast("No eligible installed applications found");return;}
    LinearLayout container=v();pad(container,12,10);
    EditText search=input("",false,"Search installed applications");
    wide(container,search);
    gap(container,9);
    ListView selection=new ListView(this);
    selection.setFastScrollEnabled(true);
    container.addView(selection,new LinearLayout.LayoutParams(-1,dp(370)));
    List<Map.Entry<String,String>> visible=new ArrayList<>(all);
    List<String> names=new ArrayList<>();
    for(Map.Entry<String,String> item:visible)names.add(item.getValue());
    ArrayAdapter<String> adapter=new ArrayAdapter<>(this,
      android.R.layout.simple_list_item_1,names);
    selection.setAdapter(adapter);
    search.addTextChangedListener(new android.text.TextWatcher(){
      @Override public void beforeTextChanged(CharSequence s,int start,int count,int after){}
      @Override public void onTextChanged(CharSequence s,int start,int before,int count){
        String term=s.toString().trim().toLowerCase(Locale.ROOT);
        visible.clear();
        adapter.clear();
        for(Map.Entry<String,String> item:all){
          if(term.isEmpty()||item.getValue().toLowerCase(Locale.ROOT).contains(term)){
            visible.add(item);
            adapter.add(item.getValue());
          }
        }
        adapter.notifyDataSetChanged();
      }
      @Override public void afterTextChanged(android.text.Editable editable){}
    });
    AlertDialog browse=new AlertDialog.Builder(this)
      .setTitle("Select application to observe").setView(container)
      .setNegativeButton("Cancel",null).create();
    selection.setOnItemClickListener((parent,view,position,id)->{
      if(position<0||position>=visible.size())return;
      Map.Entry<String,String> chosen=visible.get(position);
      browse.dismiss();
      new AlertDialog.Builder(this).setTitle("Observe "+chosen.getValue())
        .setMessage("Record this application only while it is foreground. Android will request screen capture approval if needed. Protected screens remain protected.")
        .setPositiveButton("Start",(d,w)->{
          try{
            AppObservation.configure(this,true,chosen.getKey());
            toast("Observation enabled for "+chosen.getValue());
            if(!CaptureService.active)beginCapture();
          }catch(Exception e){toast("Could not enable selected app observation");}
        }).setNegativeButton("Cancel",null).show();
    });
    browse.show();
  }
  private void stopAsterionObservation(){
    try{AppObservation.configure(this,false,"");toast("Observation stopped");}
    catch(Exception e){toast("Observation could not stop");}
  }
  /** An owner-facing installed-app chooser, not just the handful of apps
   * already providing a bridge. No unsupported app is presented as connected.
   */
  private java.util.Set<String> trackedApps(){
    java.util.Set<String> result=new java.util.LinkedHashSet<>();
    try{
      org.json.JSONArray saved=new org.json.JSONArray(
        prefs.getString("tracked_apps_v1","[]"));
      for(int i=0;i<Math.min(saved.length(),150);i++){
        String pkg=saved.optString(i,"");
        if(pkg.matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*){1,12}"))
          result.add(pkg);
      }
    }catch(Exception ignored){}
    return result;
  }
  private boolean markTrackedApp(String pkg,boolean added){
    if(!AppCatalog.launchable(this).containsKey(pkg))return false;
    java.util.Set<String> stored=trackedApps();
    if(added)stored.add(pkg);else stored.remove(pkg);
    org.json.JSONArray out=new org.json.JSONArray();
    for(String item:stored)out.put(item);
    return prefs.edit().putString("tracked_apps_v1",out.toString()).commit();
  }
  private void showAppBridgeApprovals(){
    io.execute(()->{
      try{
        java.util.Map<String,String> installed=AppCatalog.launchable(this);
        org.json.JSONArray providers=AppBridge.list(this).getJSONArray("apps");
        java.util.Map<String,Boolean> bridged=new java.util.HashMap<>();
        for(int i=0;i<providers.length();i++){
          JSONObject entry=providers.getJSONObject(i);
          bridged.put(entry.getString("package"),entry.optBoolean("approved"));
        }
        java.util.Set<String> favorites=trackedApps();
        java.util.List<java.util.Map.Entry<String,String>> all=
          new ArrayList<>(installed.entrySet());
        all.removeIf(entry->entry.getKey().equals(getPackageName()));
        all.sort((left,right)->{
          boolean a=favorites.contains(left.getKey()),b=favorites.contains(right.getKey());
          if(a!=b)return a?-1:1;
          return left.getValue().compareToIgnoreCase(right.getValue());
        });
        runOnUiThread(()->{
          if(destroyed)return;
          LinearLayout layout=v();pad(layout,14,10);
          TextView explanation=t("Tap any installed app to add it to Control or authorize "+
            "a supported native integration. An app without a bridge can be saved "+
            "as a shortcut, but cannot be remotely controlled or diagnosed automatically.",
            12,DesignSystem.MUTED,false);
          wide(layout,explanation);gap(layout,12);
          EditText search=input("",false,"Search installed apps");
          wide(layout,search);gap(layout,8);
          ListView list=new ListView(this);
          final ArrayAdapter<String> adapter=new ArrayAdapter<>(
            this,android.R.layout.simple_list_item_1,new ArrayList<>());
          list.setAdapter(adapter);
          layout.addView(list,new LinearLayout.LayoutParams(-1,dp(410)));
          final java.util.List<String> shown=new ArrayList<>();
          Runnable update=()->{
            String query=search.getText().toString().trim().toLowerCase(Locale.ROOT);
            shown.clear();adapter.clear();
            for(java.util.Map.Entry<String,String> entry:all){
              String pkg=entry.getKey(),name=entry.getValue();
              if(!query.isEmpty()&&!name.toLowerCase(Locale.ROOT).contains(query)
                 &&!pkg.toLowerCase(Locale.ROOT).contains(query))continue;
              shown.add(pkg);
              String state=bridged.containsKey(pkg)?
                (bridged.get(pkg)?" · Connected":" · Approve bridge"):
                (favorites.contains(pkg)?" · Saved (not integrated)":" · Add");
              adapter.add(name+state);
              if(shown.size()>=120)break;
            }
            adapter.notifyDataSetChanged();
          };
          search.addTextChangedListener(new android.text.TextWatcher(){
            @Override public void beforeTextChanged(CharSequence x,int start,int count,int after){}
            @Override public void onTextChanged(CharSequence x,int start,int before,int count){update.run();}
            @Override public void afterTextChanged(android.text.Editable x){}
          });
          update.run();
          AlertDialog dlg=new AlertDialog.Builder(this)
            .setTitle("Add an installed app")
            .setView(layout)
            .setNegativeButton("Close",null).create();
          list.setOnItemClickListener((parent,view,position,id)->{
            if(position<0||position>=shown.size())return;
            String pkg=shown.get(position),label=installed.get(pkg);
            boolean provider=bridged.containsKey(pkg);
            boolean approved=Boolean.TRUE.equals(bridged.get(pkg));
            dlg.dismiss();
            showAppIntegrationActions(pkg,label,provider,approved);
          });
          dlg.show();
        });
      }catch(Exception e){
        runOnUiThread(()->toast("Unable to load installed app list: "+
          e.getClass().getSimpleName()));
      }
    });
  }
  private void showAppIntegrationActions(String pkg,String label,
                                        boolean bridge,boolean approved){
    if(!AppCatalog.launchable(this).containsKey(pkg)){
      toast("App is no longer installed");return;
    }
    boolean tracked=trackedApps().contains(pkg);
    String state=bridge?(approved?"Native bridge authorized":
      "Native bridge available — owner approval needed"):
      "No Asterion native bridge provided by this installed version";
    boolean writer=pkg.startsWith("com.asterion.writing.");
    String[] actions=writer?new String[]{
      tracked?"Remove from my Control apps":"Add to my Control apps",
      bridge?(approved?"Revoke native bridge":"Authorize native bridge"):
        "How to enable this app's bridge",
      "Read live process and crash evidence",
      "Check installed Writer models",
      "Open app · generic Accessibility control",
      "Open its Android app settings",
      "Choose another app"
    }:new String[]{
      tracked?"Remove from my Control apps":"Add to my Control apps",
      bridge?(approved?"Revoke native bridge":"Authorize native bridge"):
        "How to enable this app's bridge",
      "Read live process and crash evidence",
      "Open app · generic Accessibility control",
      "Open its Android app settings",
      "Choose another app"
    };
    // AlertDialog message and setItems are mutually exclusive in the native
    // ListAlertController. A message hid ALL action rows on Android 17.
    new AlertDialog.Builder(this)
      .setTitle(label+" · "+(bridge?(approved?"Connected":"Approval needed"):
        "App shortcut"))
      .setItems(actions,(dlg,which)->{
        if(which==0){
          if(markTrackedApp(pkg,!tracked))
            toast(tracked?"Removed from Control shortcuts":
              "Added to Control shortcuts (not automatically integrated)");
          else toast("Could not save the app");
          showAppIntegrationActions(pkg,label,bridge,approved);
        }else if(which==1){
          if(!bridge){
            new AlertDialog.Builder(this)
              .setTitle("Asterion partner bridge not installed")
              .setMessage(label+" has no exported "+pkg+
                ".asterion.bridge provider. Update THIS app to a build "+
                "containing the owner-signed v1 bridge, then reopen it "+
                "from Control's app picker. The shortcut already works "+
                "for launching but cannot read its private state.")
              .setPositiveButton("Open app settings",(d,w)->{
                try{startActivity(new Intent(
                  Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                  Uri.parse("package:"+pkg)));}
                catch(Exception e){toast("Settings unavailable");}
              })
              .setNegativeButton("Back",(d,w)->
                showAppIntegrationActions(pkg,label,false,false)).show();
          }else{
            new AlertDialog.Builder(this)
              .setTitle(approved?"Revoke this app's bridge?":"Authorize this app?")
              .setMessage("Application: "+label+"\n"+
                (approved?"Revoking Control's local approval will disable "+
                  "future native calls.":"Control pins the exact installed "+
                  "application certificate. Only explicitly supported "+
                  "read-only actions can run on the new v1 bridge."))
              .setPositiveButton(approved?"Revoke":"Authorize",(d,w)->{
                try{
                  AppBridge.approveLocally(this,pkg,!approved);
                  toast(approved?"Bridge revoked":"Native bridge authorized");
                }catch(Exception e){
                  toast("Approval failed: "+e.getClass().getSimpleName());
                }
                showAppBridgeApprovals();
              }).setNegativeButton("Cancel",null).show();
          }
        }else if(which==2 || (writer&&which==3)){
          String action=writer&&which==3?"models.status":"diagnostics.summary";
          if(!bridge||!approved){
            new AlertDialog.Builder(this).setTitle("Native integration required")
              .setMessage("This installed app has not exposed and approved "+
                "the Asterion v1 bridge. Control cannot inspect its private "+
                "process or model information without the partner's cooperation.")
              .setPositiveButton("Configure app",(d,w)->
                showAppIntegrationActions(pkg,label,bridge,approved))
              .setNegativeButton("Close",null).show();
          }else showPartnerEvidence(pkg,label,action);
        }else if(which==(writer?4:3)){
          io.execute(()->{
            try{
              JSONObject outcome=AppCatalog.requestLaunch(this,pkg);
              runOnUiThread(()->{
                if(!outcome.optBoolean("intent_dispatched"))
                  toast(outcome.optString("reason","App launch unavailable"));
              });
            }catch(Exception e){
              runOnUiThread(()->toast("App launch rejected"));
            }
          });
        }else if(which==(writer?5:4)){
          try{
            startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
              Uri.parse("package:"+pkg)));
          }catch(Exception e){toast("Android app settings unavailable");}
        }else if(which==(writer?6:5))showAppBridgeApprovals();
      }).setNegativeButton("Close",null).show();
  }

  private void showPartnerEvidence(String pkg,String label,String action){
    if(!"diagnostics.summary".equals(action)&&!"models.status".equals(action))
      return;
    io.execute(()->{
      String display;
      try{
        JSONObject request=new JSONObject()
          .put("package",pkg)
          .put("action",action)
          .put("request_id",java.util.UUID.randomUUID().toString())
          .put("payload",new JSONObject());
        JSONObject response=AppBridge.invoke(this,request);
        JSONObject result=response.optJSONObject("result");
        JSONObject evidence=result==null?null:result.optJSONObject("evidence");
        if(!response.optBoolean("ok")||evidence==null)
          throw new IllegalStateException(response.optString("status","unavailable"));
        StringBuilder report=new StringBuilder();
        if("models.status".equals(action)){
          int count=evidence.optInt("installed_gguf_count",0);
          report.append("Completed GGUF model files: ").append(count)
            .append("\nTotal model bytes: ")
            .append(evidence.optLong("installed_bytes",0))
            .append("\n\n");
          org.json.JSONArray models=evidence.optJSONArray("models");
          if(models!=null)for(int i=0;i<Math.min(models.length(),12);i++){
            JSONObject model=models.optJSONObject(i);
            if(model!=null)report.append("• ")
              .append(model.optString("name","unknown"))
              .append(" · ").append(model.optLong("bytes",0))
              .append(" bytes\n");
          }
          report.append("\nThese are verified completed files in Writer's "+
            "private model directory. Control has not loaded or "+
            "benchmarked them, and cannot infer with them until "+
            "an explicit approved inference bridge exists.");
        }else{
          report.append("Live native bridge response: YES")
            .append("\nVersion: ").append(evidence.optString("version_name","unknown"))
            .append("\nApp process memory (PSS): ")
            .append(evidence.optInt("process_pss_kb",0)).append(" KiB")
            .append("\nApp process heap used: ")
            .append(evidence.optLong("process_heap_used_bytes",0)).append(" bytes");
          org.json.JSONArray exits=evidence.optJSONArray("android_historical_exits");
          report.append("\n\nAndroid process exits in history: ")
            .append(exits==null?0:exits.length());
          if(exits!=null)for(int i=0;i<Math.min(exits.length(),8);i++){
            JSONObject exit=exits.optJSONObject(i);
            if(exit==null)continue;
            report.append("\n• ")
              .append(localExitMeaning(exit.optInt("reason_code",-1)));
            long timestamp=exit.optLong("timestamp_ms",0);
            if(timestamp>0)report.append(" · ").append(
              android.text.format.DateFormat.format(
                "dd MMM HH:mm",new java.util.Date(timestamp)));
          }
          JSONObject video=evidence.optJSONObject("videoflow");
          if(video!=null){
            report.append("\n\nVideoFlow persisted queue snapshot");
            if(video.optBoolean("stored_queue_counts_verified")){
              JSONObject counts=video.optJSONObject("counts");
              report.append("\nQueued: ").append(counts==null?0:counts.optInt("queued",0))
                .append(" · Running in DB: ")
                .append(counts==null?0:counts.optInt("running",0))
                .append("\nDone: ").append(counts==null?0:counts.optInt("done",0))
                .append(" · Failed: ").append(counts==null?0:counts.optInt("error",0));
              org.json.JSONArray failed=video.optJSONArray("recent_failed_items");
              if(failed!=null&&failed.length()>0){
                report.append("\nRecent failures (sanitized):");
                for(int n=0;n<Math.min(failed.length(),8);n++){
                  JSONObject f=failed.optJSONObject(n);
                  if(f==null)continue;
                  report.append("\n• Item ").append(f.optLong("item_id"))
                    .append(": ").append(
                      f.optString("error_category","unclassified"));
                }
              }
              report.append("\nStored running/queued states may be stale. "+
                "The actual worker count is not verified by this snapshot.");
            }else report.append("\nVideoFlow database has no verified queue "+
              "snapshot. This does not mean there are no downloads.");
          }
          JSONObject work=evidence.optJSONObject("workmanager");
          if(work!=null){
            report.append("\n\nAndroid WorkManager history");
            if(work.optBoolean("stored_work_counts_verified")){
              JSONObject counts=work.optJSONObject("counts");
              if(counts!=null)for(String key:new String[]{
                "enqueued","running_in_stored_db","succeeded",
                "failed","blocked","cancelled"}){
                if(counts.has(key))
                  report.append("\n• ").append(key.replace('_',' '))
                    .append(": ").append(counts.optInt(key));
              }
              report.append("\nThese include all background WorkManager tasks, "+
                "not only AI or generation jobs. Live execution is unverified.");
            }else report.append("\nNo verified WorkManager history is available.");
          }
          if(video==null&&work==null)
            report.append("\n\nEngine request/queue telemetry is not yet "+
              "exposed by this partner version.");
          report.append("\nThis is real process evidence, not a diagnosis "+
            "of model quality or third-party sites.");
        }
        display=report.toString();
      }catch(Exception exc){
        display="Unable to inspect "+label+": "+
          exc.getClass().getSimpleName()+
          ". No result is fabricated. Verify the updated partner "+
          "app is installed and approved.";
      }
      final String report=display;
      runOnUiThread(()->{
        if(destroyed)return;
        new AlertDialog.Builder(this)
          .setTitle("models.status".equals(action)?
            label+" · Installed models":label+" · Live diagnostics")
          .setMessage(report)
          .setPositiveButton("Close",null).show();
      });
    });
  }

  private void showMyAddedApps(){
    java.util.Set<String> saved=trackedApps();
    java.util.Map<String,String> installed=AppCatalog.launchable(this);
    java.util.List<String> packages=new ArrayList<>();
    java.util.List<String> labels=new ArrayList<>();
    for(String pkg:saved){
      if(installed.containsKey(pkg)){
        packages.add(pkg);labels.add(installed.get(pkg));
      }
    }
    if(packages.isEmpty()){
      new AlertDialog.Builder(this).setTitle("My Control apps")
        .setMessage("No app shortcuts have been added yet. "+
          "Choose an installed app and tap Add to my Control apps.")
        .setPositiveButton("Browse apps",(d,w)->showAppBridgeApprovals())
        .setNegativeButton("Close",null).show();
      return;
    }
    new AlertDialog.Builder(this).setTitle("My Control apps")
      .setItems(labels.toArray(new String[0]),(d,index)->{
        String pkg=packages.get(index);
        io.execute(()->{
          boolean bridge=false,approved=false;
          try{
            org.json.JSONArray apps=AppBridge.list(this).getJSONArray("apps");
            for(int i=0;i<apps.length();i++){
              JSONObject entry=apps.getJSONObject(i);
              if(pkg.equals(entry.optString("package"))){
                bridge=true;approved=entry.optBoolean("approved");break;
              }
            }
          }catch(Exception ignored){}
          final boolean b=bridge,a=approved;
          runOnUiThread(()->showAppIntegrationActions(pkg,installed.get(pkg),b,a));
        });
      })
      .setPositiveButton("Browse installed apps",(d,w)->showAppBridgeApprovals())
      .setNegativeButton("Close",null).show();
  }

  private void enableCheckpointContinuation(){
    new AlertDialog.Builder(this).setTitle("Enable ChatGPT continuation")
      .setMessage("Asterion Control may send a saved continuation checkpoint in the ChatGPT Android app when you open ChatGPT. This uses your existing app access and is not an API subscription. It never erases an existing draft. You can pause it here at any time.")
      .setPositiveButton("Enable", (dialog,which)->{
        try { ContinuationLedger.get(this).configure(true);
          toast("Checkpoint continuation enabled"); }
        catch(Exception e){toast("Checkpoint setting could not be saved");}
      }).setNegativeButton("Cancel",null).show();
  }
  private void pauseCheckpointContinuation(){
    try { ContinuationLedger.get(this).configure(false);
      toast("Checkpoint continuation paused"); }
    catch(Exception e){toast("Checkpoint setting could not be saved");}
  }
  private void openChatGptCheckpoint(){
    try {
      JSONObject state=ContinuationLedger.get(this).status();
      if(!state.optBoolean("enabled") || !"queued".equals(state.optString("state"))){
        toast("Enable continuation and queue a checkpoint first");return;
      }
      ControlAccessibilityService access=ControlAccessibilityService.active;
      if(access==null){
        toast("Cannot restore existing ChatGPT task without Accessibility");return;
      }
      JSONObject restore=access.requestChatForeground();
      if(restore.optBoolean("already_foreground",false))
        toast("Existing ChatGPT task foreground; checkpoint still queued");
      else if(restore.optBoolean("requested",false))
        toast("Returning to existing ChatGPT conversation; delivery not verified");
      else toast("Existing ChatGPT task not verified; checkpoint remains queued. "+
        restore.optString("reason",""));
    }catch(Exception e){toast("Cannot open ChatGPT checkpoint");}
  }
  private void showBatterySetup(){
    new AlertDialog.Builder(this).setTitle("Keep Asterion Control active")
      .setMessage("For long unattended tests on Samsung: select Battery > Unrestricted for Asterion Control, and remove it from Sleeping/Deep sleeping apps. Android may still require screen-sharing permission again if capture is stopped.")
      .setPositiveButton("Open app settings",(dialog,which)->{
        try{Intent details=new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
          Uri.parse("package:"+getPackageName()));startActivity(details);}
        catch(Exception e){toast("Open Android Settings > Apps > Asterion Control > Battery");}
      }).setNegativeButton("Cancel",null).show();
  }
  @Override protected void onResume(){
    super.onResume();
    visibleActivity = new java.lang.ref.WeakReference<>(this);
    // Never enable the microphone just because Android permission was granted.
    // A one-time migration clears legacy automatic listening; only an explicit
    // owner opt-in may start persistent wake-phrase monitoring.
    VoiceDialogueService.migrateMusicSafePreferences(this);
    if(checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED){
      VoiceDialogueService.ensureOwnerRequestedAlwaysOn(this);
      handler.postDelayed(()->{
        if(VoiceDialogueService.active!=null){
          android.app.NotificationManager nm=getSystemService(android.app.NotificationManager.class);
          if(nm!=null)nm.cancel(RestoreReceiver.VOICE_RECOVERY_NOTIFICATION);
        }
      },1800L);
    }
    if(prefs!=null&&!destroyed&&getSharedPreferences("agent",MODE_PRIVATE)
       .getBoolean(AgentService.PREF_REMOTE_ENABLED,false)){
      if(!AgentService.running)startAgent();
      if(!prefs.getString("url","").isEmpty()&&!prefs.getString("token","").isEmpty()){
        handler.postDelayed(()->{if(!destroyed&&AgentService.running)registerPhone();},1400);
      }
    }
  }
  @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);
    if(request==HUB_MICROPHONE_REQUEST||request==HUB_NOTIFICATION_REQUEST){
      boolean granted=results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED;
      toast((request==HUB_MICROPHONE_REQUEST?"Microphone":"Notifications")+
        (granted?" permission granted":" permission not granted"));
      // A permission granted in this hub must NEVER start voice listening
      // or auto-enable a background service.
      return;
    }
    if(request==MICROPHONE_REQUEST){
      if(results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED){
        if(runVoiceTestAfterPermission){runVoiceTestAfterPermission=false;testVoiceDialogue();}
        else startVoiceQuestions();
      }else{
        runVoiceTestAfterPermission=false;
        if(voiceTestStatus!=null)
          voiceTestStatus.setText("Voice test blocked: Android microphone permission denied");
        new AlertDialog.Builder(this).setTitle("Microphone permission required")
          .setMessage("Android did not grant microphone access. The speaker can run separately, but no spoken answer can be captured until microphone access is granted.")
          .setPositiveButton("App permissions",(dialog,which)->{
            startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
              Uri.parse("package:"+getPackageName())));
          }).setNegativeButton("Close",null).show();
      }
      return;
    }
    if(request==NOTIFICATION_REQUEST&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED){
      startAgent();
      if(!prefs.getString("token","").isEmpty())handler.postDelayed(()->{if(AgentService.running)registerPhone();},1400);
    }}
  private void beginCapture(){try{MediaProjectionManager p=(MediaProjectionManager)getSystemService(Context.MEDIA_PROJECTION_SERVICE);startActivityForResult(p.createScreenCaptureIntent(),CAPTURE_REQUEST);}catch(Exception e){toast("Screen capture not available");}}
  @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);
    if(request==CAPTURE_REQUEST){
      if(code==RESULT_OK&&data!=null){
        try{Intent i=new Intent(this,CaptureService.class);i.putExtra("result",code);
          i.putExtra("data",data);startForegroundService(i);
          handler.postDelayed(this::updateHealth,450);
        }catch(Exception e){
          ConnectionDiagnostics.failure(this,"capture_launch_failed",
            "Android could not start screen sharing: "+e.getClass().getSimpleName());
          toast("Screen share could not start");
        }
      }else{
        ConnectionDiagnostics.failure(this,"capture_permission_denied",
          "Screen sharing authorization was not granted by Android");
      }
      handler.postDelayed(this::updateConnectionIssue,500);
    }
    if(request==VPN_REQUEST){
      if(code==RESULT_OK)ControlPrivateVpn.connect(this,this::toast);
      else toast("Android VPN authorization declined; existing connection unchanged");
    }
  }
  private void registerPhone(){
    if(!AgentService.running){
      ConnectionDiagnostics.failure(this,"agent_not_running","Android phone agent is not running");
      setPairingFeedback("Enable phone access to register this device");updateConnectionIssue();return;
    }
    io.execute(()->{
      String raw=prefs.getString("url","").replaceAll("/+$","");
      if(raw.isEmpty()){
        ConnectionDiagnostics.failure(this,"windows_not_paired","No saved Windows pairing");
        runOnUiThread(()->{toast("Windows is not paired");updateConnectionIssue();});return;
      }
      String ip=localIpForPeer(raw);
      if(ip.equals("Unavailable")){
        ConnectionDiagnostics.failure(this,"no_private_route","Phone has no private network route to Windows");
        runOnUiThread(()->{toast("Phone has no private network route to Windows");updateConnectionIssue();});return;
      }
      String bearer=prefs.getString("token","");
      for(int attempt=0;attempt<4;attempt++){
        HttpURLConnection conn=null;
        try{
          conn=(HttpURLConnection)new URL(raw+"/api/v1/phone/register").openConnection();
          conn.setConnectTimeout(3500);conn.setReadTimeout(4000);
          conn.setRequestMethod("POST");conn.setDoOutput(true);
          conn.setRequestProperty("Authorization","Bearer "+bearer);
          conn.setRequestProperty("Content-Type","application/json");
          JSONObject body=new JSONObject().put("base_url","http://"+ip+":"+AgentService.PORT)
                                      .put("token",AgentService.token(this))
                                      .put("device",Build.MODEL);
          try(OutputStream out=conn.getOutputStream()){out.write(body.toString().getBytes(StandardCharsets.UTF_8));}
          int status=conn.getResponseCode();
          if(status==200){
            ConnectionDiagnostics.success(this);
            runOnUiThread(()->{
              workerPhoneState="Phone registered; Windows reachability being verified";
              setPairingFeedback("Phone registration accepted by Windows · testing live reachability");
              updateConnectionIssue();
              toast("Phone registered with Windows");
              updateHealth();
            });return;
          }
          if(status!=502&&status!=503){
            final int failure=status;
            ConnectionDiagnostics.failure(this,"registration_http_"+failure,
              failure==401||failure==403?"Windows rejected saved phone registration authorization"
                :"Windows registration returned HTTP "+failure);
            runOnUiThread(()->{
              workerPhoneState="Registration rejected: HTTP "+failure;
              setPairingFeedback("Phone registration HTTP "+failure+" — use Auto-repair connection");
              updateConnectionIssue();
              toast("Phone registration returned HTTP "+failure);
            });return;
          }
        }catch(Exception e){
          if(attempt==3){
            final String failure=e.getClass().getSimpleName();
            ConnectionDiagnostics.failure(this,"registration_exception",
              "Phone registration failed: "+failure);
            runOnUiThread(()->{
              workerPhoneState="Registration failed: "+failure;
              setPairingFeedback("Phone registration failed: "+failure+" — use Force activate connection");
              updateConnectionIssue();
              toast("Phone registration failed: "+failure);
            });
          }
        }finally{if(conn!=null)conn.disconnect();}
        try{Thread.sleep(700);}catch(InterruptedException e){Thread.currentThread().interrupt();return;}
      }
      ConnectionDiagnostics.failure(this,"registration_retry_exhausted",
        "Windows could not confirm reaching the Android phone after registration attempts");
      runOnUiThread(()->{workerPhoneState="Windows cannot reach phone after retries";
        toast("Phone agent is not reachable from Windows");updateConnectionIssue();});
    });
  }
  /** Select the phone address Windows can actually reach, not an arbitrary VPN/cellular interface. */
  private String localIpForPeer(String host){
    try{
      URL u=new URL(host);
      int port=u.getPort()<0?u.getDefaultPort():u.getPort();
      try(Socket sock=new Socket()){
        sock.connect(new InetSocketAddress(u.getHost(),port),1800);
        java.net.InetAddress addr=sock.getLocalAddress();
        if(addr instanceof Inet4Address&&!addr.isLoopbackAddress()&&addr.isSiteLocalAddress())
          return addr.getHostAddress();
      }
    }catch(Exception ignored){}
    return ipAddress();
  }
  private static boolean sameOrigin(String a,String b){try{URL u=new URL(a),v=new URL(b);int p=u.getPort()<0?u.getDefaultPort():u.getPort();int q=v.getPort()<0?v.getDefaultPort():v.getPort();return u.getProtocol().equals(v.getProtocol())&&u.getHost().equalsIgnoreCase(v.getHost())&&p==q;}catch(Exception ex){return false;}}
  private static String ipAddress(){try{for(NetworkInterface n:Collections.list(NetworkInterface.getNetworkInterfaces())){if(!n.isUp()||n.isLoopback())continue;for(java.net.InetAddress a:Collections.list(n.getInetAddresses())){if(a instanceof Inet4Address&&!a.isLoopbackAddress()&&a.isSiteLocalAddress())return a.getHostAddress();}}}catch(Exception ignored){}return "Unavailable";}
  @Override public void onBackPressed(){if(currentTab==1&&web!=null&&web.canGoBack())web.goBack();else if(currentTab!=0)show(0);else super.onBackPressed();}
  @Override protected void onPause(){
    if(visibleActivity.get()==this)visibleActivity = new java.lang.ref.WeakReference<>(null);
    super.onPause();
  }
  @Override protected void onDestroy(){destroyed=true;handler.removeCallbacks(ticker);io.shutdownNow();if(web!=null){web.destroy();}super.onDestroy();}
}
