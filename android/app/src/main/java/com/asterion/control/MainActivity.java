package com.asterion.control;

import android.Manifest;
import android.app.Activity;
import android.app.ActivityManager;


import android.content.Context;
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
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.Inet4Address;
import java.net.NetworkInterface;
import java.net.URL;
import java.util.Collections;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Asterion Control · native, phone-first command surface. Technical APIs remain hidden. */
public final class MainActivity extends Activity {
  private static final int CAPTURE_REQUEST=112,NOTIFICATION_REQUEST=113;
  private final Handler handler=new Handler(Looper.getMainLooper());
  private final ExecutorService io=Executors.newSingleThreadExecutor();
  private SharedPreferences prefs;
  private LinearLayout root,navbar,content,homeBody,healthBody,devicesBody;
  private FrameLayout stage;
  private final View[] pages=new View[4];
  private final LinearLayout[] tabButtons=new LinearLayout[4];
  private final DesignSystem.Icon[] tabIcons=new DesignSystem.Icon[4];
  private final TextView[] tabLabels=new TextView[4];
  private TextView headerStatus,pcConnection,homeAgent,homeBattery,homeMemory,homeThermal;
  private TextView healthBattery,healthTemp,healthMemory,healthStorage,healthThermal,healthWifi;
  private TextView remoteConnection,remotePlaceholder,agentConnection,captureConnection,accessConnection,phoneAddress,hostHealth;
  private DesignSystem.Meter batteryMeter,memoryMeter,storageMeter;
  private EditText serverUrl,serverToken,localAddress;
  private WebView web;
  private LinearLayout emptyRemote;
  private boolean advancedSetupVisible=false;
  private LinearLayout advancedSetup;
  private TextView privacyStatus;
  private int currentTab=0;
  private boolean webStarted=false,hostRefreshing=false;
  private long lastHostRefresh=0;
  private boolean destroyed=false;
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
    pages[0]=scrollHome();pages[1]=remotePage();pages[2]=scrollHealth();pages[3]=scrollDevices();
    for(View page:pages){page.setVisibility(View.GONE);stage.addView(page,new FrameLayout.LayoutParams(-1,-1));}
    buildNav();show(0);updateHealth();handler.postDelayed(ticker,3500);
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
    String[] names={"Home","Screen","Health","Connect"};String[] images={"home","monitor","pulse","devices"};
    for(int i=0;i<4;i++){final int index=i;LinearLayout slot=v();slot.setGravity(Gravity.CENTER);slot.setPadding(dp(1),dp(7),dp(1),dp(6));
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
    sectionTitle(homeBody,"Control without limits.","Your computer and phone in one clear workspace.");gap(homeBody,19);
    LinearLayout hero=card();hero.setBackground(DesignSystem.gradient(this,0xFF342754,0xFF172A42,25));
    LinearLayout r=h();r.addView(squareIcon("monitor",0xFFD4C9FF));LinearLayout copy=v();copy.setPadding(dp(13),0,0,0);
    copy.addView(eyebrow("WINDOWS COMPUTER"));margin(copy,t("LAPTOP-1LI4VRCJ",17,DesignSystem.TEXT,true),5);r.addView(copy,new LinearLayout.LayoutParams(0,-2,1));wide(hero,r);
    pcConnection=t("Checking your computer…",12.5f,DesignSystem.MUTED,false);margin(hero,pcConnection,17);
    gap(hero,17);button(hero,"Open remote desktop","monitor",true,()->show(1));gap(hero,9);
    button(hero,"Change connection","settings",false,()->show(3));wide(homeBody,hero);gap(homeBody,12);
    LinearLayout phone=clickableCard(()->show(3));LinearLayout phoneR=h();phoneR.addView(squareIcon("phone",DesignSystem.TEAL));
    LinearLayout phoneCopy=v();phoneCopy.setPadding(dp(12),0,0,0);phoneCopy.addView(eyebrow("ANDROID · THIS PHONE"));
    margin(phoneCopy,t(Build.MODEL,15,DesignSystem.TEXT,true),6);
    homeAgent=t("Remote access is off",12,DesignSystem.MUTED,false);margin(phoneCopy,homeAgent,6);
    phoneR.addView(phoneCopy,new LinearLayout.LayoutParams(0,-2,1));phoneR.addView(icon("arrow",DesignSystem.MUTED,19));wide(phone,phoneR);wide(homeBody,phone);
    gap(homeBody,25);wide(homeBody,eyebrow("ONE-TAP CONTROLS"));gap(homeBody,11);
    LinearLayout quick=v();twoActions(quick,"Share my screen","share",this::beginCapture,"Allow remote access","power",this::startAgent);wide(homeBody,quick);
    gap(homeBody,26);LinearLayout healthTitle=h();healthTitle.addView(eyebrow("PHONE HEALTH"),new LinearLayout.LayoutParams(0,-2,1));
    TextView details=t("VIEW ALL  ›",11,DesignSystem.PURPLE,true);details.setOnClickListener(w->show(2));healthTitle.addView(details);wide(homeBody,healthTitle);gap(homeBody,11);
    LinearLayout metrics=h();metrics.setGravity(Gravity.TOP);
    homeBattery=smallMetric(metrics,"BATTERY","—",DesignSystem.TEAL);
    homeThermal=smallMetric(metrics,"THERMAL","—",DesignSystem.PURPLE);
    homeMemory=smallMetric(metrics,"FREE RAM","—",DesignSystem.WARNING);wide(homeBody,metrics);
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
    LinearLayout title=h();LinearLayout labels=v();labels.addView(eyebrow("REMOTE VIEW"));margin(labels,t("Your Windows desktop",21,DesignSystem.TEXT,true),7);title.addView(labels,new LinearLayout.LayoutParams(0,-2,1));
    LinearLayout refresh=h();refresh.setGravity(Gravity.CENTER);refresh.setPadding(dp(11),dp(11),dp(11),dp(11));DesignSystem.clickable(refresh,this,DesignSystem.SURFACE2,DesignSystem.EDGE,13);refresh.addView(icon("refresh",DesignSystem.PURPLE,20));refresh.setContentDescription("Refresh remote connection");refresh.setOnClickListener(w->connectRemote(true));title.addView(refresh);wide(layout,title);
    remoteConnection=t("Configure your Windows connection in Devices.",12,DesignSystem.MUTED,false);margin(layout,remoteConnection,10);gap(layout,13);
    FrameLayout frame=new FrameLayout(this);frame.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE,DesignSystem.EDGE,21));
    web=new WebView(this);web.setBackgroundColor(DesignSystem.SURFACE);WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(false);settings.setAllowFileAccess(false);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);settings.setBuiltInZoomControls(false);settings.setDisplayZoomControls(false);
    web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !sameOrigin(request.getUrl().toString(),prefs.getString("url",""));}
      @Override public void onPageFinished(WebView view,String url){if(!sameOrigin(url,prefs.getString("url","")))return;
        String token=prefs.getString("token","");
        String css="header,footer,.authbar,.notice{display:none!important}.app{padding:8px!important}main{margin:0!important}.tabs{margin:0 0 12px!important}.tabs button{padding:10px 16px!important}.tabs button[data-page=files],.tabs button[data-page=processes],.tabs button[data-page=system]{display:none!important}.viewer{height:50vh!important;min-height:240px!important}.phone-viewer{min-height:370px!important}.sectiontitle{flex-wrap:wrap!important}body{background:#13192b!important}";
        String script="(function(){if(!document.getElementById('asterion-embedded')){const st=document.createElement('style');st.id='asterion-embedded';st.textContent="+JSONObject.quote(css)+";document.head.appendChild(st);}const t=document.querySelector('#token');const b=document.querySelector('#connect');if(t&&b){t.value="+JSONObject.quote(token)+";b.click();}})()";
        view.evaluateJavascript(script,null);
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
    wide(healthBody,meters);gap(healthBody,12);LinearLayout store=card();healthStorage=t("—",18,DesignSystem.TEXT,true);metricRow(store,"Internal storage",null,healthStorage,DesignSystem.PURPLE);margin(healthBody,store,0);
    gap(healthBody,12);LinearLayout network=card();healthWifi=t("Checking…",17,DesignSystem.TEXT,true);metricRow(network,"Network",null,healthWifi,DesignSystem.TEAL);wide(healthBody,network);
    gap(healthBody,24);wide(healthBody,eyebrow("REMOTE SERVICES"));gap(healthBody,10);
    LinearLayout services=card();agentConnection=serviceLine(services,"Phone agent","power");services.addView(line(),new LinearLayout.LayoutParams(-1,dp(1)));
    captureConnection=serviceLine(services,"Screen sharing","share");services.addView(line(),new LinearLayout.LayoutParams(-1,dp(1)));
    accessConnection=serviceLine(services,"Input access","shield");wide(healthBody,services);
    gap(healthBody,24);wide(healthBody,eyebrow("WINDOWS HEALTH"));gap(healthBody,10);
    LinearLayout windows=card();hostHealth=t("Connect your Windows agent to see its CPU, memory, storage and temperature sensors.",12,DesignSystem.MUTED,false);wide(windows,hostHealth);wide(healthBody,windows);
    return scroll(healthBody);
  }
  private TextView serviceLine(LinearLayout card,String title,String iconName){LinearLayout row=h();row.setPadding(0,dp(11),0,dp(11));row.addView(icon(iconName,DesignSystem.PURPLE,20));TextView titleText=t(title,13,DesignSystem.TEXT,true);titleText.setPadding(dp(14),0,0,0);row.addView(titleText,new LinearLayout.LayoutParams(0,-2,1));TextView value=t("Checking",12,DesignSystem.MUTED,false);row.addView(value);wide(card,row);return value;}
  private View scrollDevices(){
    devicesBody=v();wide(devicesBody,eyebrow("SECURE DEVICE ACCESS"));
    sectionTitle(devicesBody,"Your connections.","Control your own devices without cables or repeated setup.");gap(devicesBody,18);

    // Clear device status first. No access tokens, IPs, terminals or logs in this primary view.
    LinearLayout summary=card();summary.setBackground(DesignSystem.gradient(this,0xFF28334B,0xFF182A38,23));
    rowTitle(summary,"Windows computer","Your remote desktop and device resources",icon("monitor",DesignSystem.PURPLE,25));
    gap(summary,12);remoteConnection=t("Checking saved connection…",12,DesignSystem.MUTED,false);wide(summary,remoteConnection);
    gap(summary,16);twoActions(summary,"Open desktop","monitor",()->show(1),"Reconnect","refresh",()->{save();checkHost();});
    wide(devicesBody,summary);

    gap(devicesBody,12);LinearLayout phone=card();
    rowTitle(phone,"This Android phone","Optional incoming screen and touch access",icon("phone",DesignSystem.TEAL,23));
    gap(phone,12);phoneAddress=t("Checking phone access…",12,DesignSystem.MUTED,false);wide(phone,phoneAddress);
    gap(phone,16);button(phone,"Enable phone remote control","shield",true,this::enablePhoneControl);
    gap(phone,9);button(phone,"Share screen · Android permission","share",false,this::beginCapture);
    gap(phone,9);button(phone,"Disable phone access","power",false,()->{stopService(new Intent(this,CaptureService.class));stopAgent();});
    wide(devicesBody,phone);

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
    gap(advancedSetup,13);wide(advancedSetup,eyebrow("PRIVATE PAIRING KEY"));gap(advancedSetup,8);
    serverToken=input(prefs.getString("token",""),true,"Enter pairing key once");wide(advancedSetup,serverToken);
    gap(advancedSetup,13);button(advancedSetup,"Save and connect","check",true,()->{
      save();toggleAdvancedSetup();checkHost();show(1);
    });
    gap(advancedSetup,13);TextView notice=t("Advanced pairing details stay hidden in everyday use. For connections outside your local network, use your private encrypted VPN; never expose the current HTTP service to the public internet.",11,DesignSystem.MUTED,false);wide(advancedSetup,notice);
    wide(devicesBody,advancedSetup);
    // Retained internally for registration; never displayed as a plain-text access credential.
    localAddress=input(prefs.getString("phoneip",ipAddress()),false,"");
    return scroll(devicesBody);
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
    if(page==1)connectRemote(false);if(page==0||page==2||page==3)updateHealth();
  }
  private void save(){prefs.edit().putString("url",serverUrl.getText().toString().trim()).putString("token",serverToken.getText().toString().trim())
    .putString("phoneip",localAddress.getText().toString().trim()).apply();updateHealth();}
  private void connectRemote(boolean force){String url=prefs.getString("url","");String token=prefs.getString("token","");
    if(!url.matches("(?i)^https?://[^\\s/]+(?:/.*)?$")||token.isEmpty()){
      if(remoteConnection!=null)remoteConnection.setText("Not paired · Open Devices to configure");
      if(emptyRemote!=null)emptyRemote.setVisibility(View.VISIBLE);if(web!=null)web.setVisibility(View.GONE);return;}
    if(remoteConnection!=null)remoteConnection.setText("Connecting to "+url.replaceFirst("^https?://",""));
    emptyRemote.setVisibility(View.GONE);web.setVisibility(View.VISIBLE);
    if(force||!webStarted){webStarted=true;web.loadUrl(url);}
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
    if(homeAgent!=null)homeAgent.setText(AgentService.running?"Agent enabled · Remote access on":"Agent off · Device is local");
    if(healthBattery!=null)healthBattery.setText(percent<0?"—":Math.round(percent)+"%");
    if(healthTemp!=null)healthTemp.setText(rawTemp<0?"—":String.format(Locale.US,"%.1f°",rawTemp/10.0));
    if(healthMemory!=null)healthMemory.setText(String.format(Locale.US,"%.1f GB",m.availMem/1e9));
    if(healthThermal!=null){healthThermal.setText(thermalText);healthThermal.setTextColor(tint);}
    if(healthStorage!=null)healthStorage.setText(String.format(Locale.US,"%.1f GB free of %.0f GB",fs.getAvailableBytes()/1e9,fs.getTotalBytes()/1e9));
    if(healthWifi!=null)healthWifi.setText(networkName());
    if(batteryMeter!=null)batteryMeter.setProgress(percent<0?0:(float)(percent/100));
    if(memoryMeter!=null)memoryMeter.setProgress((float)(1.0-(double)m.availMem/(double)m.totalMem));
    if(storageMeter!=null)storageMeter.setProgress((float)(1.0-(double)fs.getAvailableBytes()/(double)fs.getTotalBytes()));
    if(agentConnection!=null){agentConnection.setText(AgentService.running?"Enabled":"Off");agentConnection.setTextColor(AgentService.running?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(captureConnection!=null){captureConnection.setText(CaptureService.active?"Streaming":"Off");captureConnection.setTextColor(CaptureService.active?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(accessConnection!=null){accessConnection.setText(ControlAccessibilityService.active!=null?"Authorized":"Not enabled");accessConnection.setTextColor(ControlAccessibilityService.active!=null?DesignSystem.TEAL:DesignSystem.MUTED);}
    if(phoneAddress!=null)phoneAddress.setText(AgentService.running?"Remote control enabled":"Remote control disabled");
    if(privacyStatus!=null)privacyStatus.setText(
      AgentService.running?"Phone agent active · "+(ControlAccessibilityService.active!=null?"input authorized":"touch permission needed")+" · "+(CaptureService.active?"screen shared":"screen private"):
      "Remote phone access is disabled. No screen or input is shared.");
    if(headerStatus!=null)headerStatus.setText(AgentService.running?"SHARING ON":"ON DEVICE");
    if(!hostRefreshing&&(currentTab==0||currentTab==2)&&System.currentTimeMillis()-lastHostRefresh>12000){lastHostRefresh=System.currentTimeMillis();checkHost();}
  }catch(Exception ignored){} }
  private String thermalName(int level){switch(level){case PowerManager.THERMAL_STATUS_NONE:return "Nominal";case PowerManager.THERMAL_STATUS_LIGHT:return "Light";case PowerManager.THERMAL_STATUS_MODERATE:return "Moderate";case PowerManager.THERMAL_STATUS_SEVERE:return "Severe";case PowerManager.THERMAL_STATUS_CRITICAL:return "Critical";case PowerManager.THERMAL_STATUS_EMERGENCY:return "Emergency";case PowerManager.THERMAL_STATUS_SHUTDOWN:return "Shutdown";default:return "Unavailable";}}
  private String networkName(){try{ConnectivityManager cm=(ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);Network n=cm.getActiveNetwork();NetworkCapabilities cap=cm.getNetworkCapabilities(n);if(cap==null)return "Offline";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))return "Wi-Fi connected";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR))return "Mobile data";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_VPN))return "VPN connected";if(cap.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))return "Ethernet";return "Connected";}catch(Exception e){return "Unavailable";}}
  private void checkHost(){String url=prefs.getString("url","").replaceAll("/+$","");String token=prefs.getString("token","");
    if(url.isEmpty()||token.isEmpty()){if(pcConnection!=null)pcConnection.setText("Not linked yet · Connect to start");if(hostHealth!=null)hostHealth.setText("Windows agent not paired.");return;}
    hostRefreshing=true;io.execute(()->{String status="Offline · Check connection",metric="Windows telemetry unavailable";
      try{URL u=new URL(url+"/api/v1/device-health");HttpURLConnection c=(HttpURLConnection)u.openConnection();c.setConnectTimeout(2400);c.setReadTimeout(2600);c.setRequestProperty("Authorization","Bearer "+token);int code=c.getResponseCode();
        if(code==200){byte[] bytes=c.getInputStream().readNBytes(500000);JSONObject data=new JSONObject(new String(bytes,java.nio.charset.StandardCharsets.UTF_8));
          status="Online · Secure key accepted";double cpu=data.optDouble("cpu_percent",-1);
          JSONObject mem=data.optJSONObject("memory");metric="CPU "+(cpu>=0?String.format(Locale.US,"%.1f%%",cpu):"—")+"  ·  RAM "+(mem!=null?mem.optInt("percent")+"%":"—")+"\n\n";
          JSONObject thermal=data.optJSONObject("thermals");metric+=thermal!=null&&thermal.optBoolean("available")?"Thermal sensors available":"No OS thermal sensors reported";
        }else status="Agent rejected request · HTTP "+code;c.disconnect();
      }catch(Exception ignored){}
      final String state=status,details=metric;
      runOnUiThread(()->{hostRefreshing=false;if(destroyed)return;if(pcConnection!=null)pcConnection.setText(state);if(hostHealth!=null)hostHealth.setText(details);
        if(remoteConnection!=null)remoteConnection.setText(state.startsWith("Online")?"Connected to Windows agent":state);
      });
    });
  }
  private void startAgent(){try{if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},NOTIFICATION_REQUEST);return;}
    startForegroundService(new Intent(this,AgentService.class));handler.postDelayed(()->{updateHealth();toast(AgentService.running?"Phone agent enabled":"Agent could not start; check device permissions");},700);
    }catch(Exception e){toast("Unable to start agent: "+e.getClass().getSimpleName());}}
  private void stopAgent(){stopService(new Intent(this,AgentService.class));handler.postDelayed(this::updateHealth,450);toast("Phone agent disabled");}
  @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){super.onRequestPermissionsResult(request,permissions,results);
    if(request==NOTIFICATION_REQUEST&&results.length>0&&results[0]==PackageManager.PERMISSION_GRANTED)startAgent();}
  private void beginCapture(){try{MediaProjectionManager p=(MediaProjectionManager)getSystemService(Context.MEDIA_PROJECTION_SERVICE);startActivityForResult(p.createScreenCaptureIntent(),CAPTURE_REQUEST);}catch(Exception e){toast("Screen capture not available");}}
  @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);
    if(request==CAPTURE_REQUEST&&code==RESULT_OK&&data!=null){try{Intent i=new Intent(this,CaptureService.class);i.putExtra("result",code);i.putExtra("data",data);startForegroundService(i);handler.postDelayed(this::updateHealth,450);}catch(Exception e){toast("Screen share could not start");}}
  }
  private void registerPhone(){save();if(!AgentService.running){toast("Enable phone agent first");return;}
    io.execute(()->{try{String raw=prefs.getString("url","").replaceAll("/+$","");if(raw.isEmpty())throw new IllegalArgumentException("Windows address required");
      URL url=new URL(raw+"/api/v1/phone/register");HttpURLConnection conn=(HttpURLConnection)url.openConnection();conn.setConnectTimeout(5500);conn.setReadTimeout(6500);conn.setRequestMethod("POST");conn.setDoOutput(true);
      conn.setRequestProperty("Authorization","Bearer "+prefs.getString("token",""));conn.setRequestProperty("Content-Type","application/json");
      String ip=prefs.getString("phoneip",ipAddress());JSONObject body=new JSONObject().put("base_url","http://"+ip+":"+AgentService.PORT).put("token",AgentService.token(this));
      try(OutputStream out=conn.getOutputStream()){out.write(body.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
      int code=conn.getResponseCode();conn.disconnect();runOnUiThread(()->toast(code==200?"Phone linked with Windows":"Registration failed · HTTP "+code));
    }catch(Exception e){runOnUiThread(()->toast("Registration failed · "+e.getClass().getSimpleName()));}});
  }
  private static boolean sameOrigin(String a,String b){try{URL u=new URL(a),v=new URL(b);int p=u.getPort()<0?u.getDefaultPort():u.getPort();int q=v.getPort()<0?v.getDefaultPort():v.getPort();return u.getProtocol().equals(v.getProtocol())&&u.getHost().equalsIgnoreCase(v.getHost())&&p==q;}catch(Exception ex){return false;}}
  private static String ipAddress(){try{for(NetworkInterface n:Collections.list(NetworkInterface.getNetworkInterfaces())){if(!n.isUp()||n.isLoopback())continue;for(java.net.InetAddress a:Collections.list(n.getInetAddresses())){if(a instanceof Inet4Address&&!a.isLoopbackAddress()&&a.isSiteLocalAddress())return a.getHostAddress();}}}catch(Exception ignored){}return "Unavailable";}
  @Override public void onBackPressed(){if(currentTab==1&&web!=null&&web.canGoBack())web.goBack();else if(currentTab!=0)show(0);else super.onBackPressed();}
  @Override protected void onDestroy(){destroyed=true;handler.removeCallbacks(ticker);io.shutdownNow();if(web!=null){web.destroy();}super.onDestroy();}
}
