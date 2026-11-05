package com.asterion.control;

import android.Manifest;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.widget.Button;
import android.widget.EditText;
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

/** Android-first operator UI: no command-shell or logcat controls in normal navigation. */
public final class MainActivity extends Activity {
  private static final int CAPTURE_REQUEST=112;
  private EditText serverUrl,serverToken,localAddress;
  private TextView status,deviceStatus;
  private WebView web;
  private LinearLayout container,connectionPanel,remotePanel,healthPanel;
  private SharedPreferences prefs;
  private final Handler handler=new Handler(Looper.getMainLooper());
  private final int BACKGROUND=Color.rgb(10,16,30),PANEL=Color.rgb(24,36,56),ACCENT=Color.rgb(55,136,211),TEXT=Color.rgb(235,243,253);
  @Override protected void onCreate(Bundle b){super.onCreate(b);getWindow().setStatusBarColor(BACKGROUND);getWindow().setNavigationBarColor(BACKGROUND);
    prefs=getSharedPreferences("control",MODE_PRIVATE);
    container=new LinearLayout(this);container.setOrientation(LinearLayout.VERTICAL);container.setBackgroundColor(BACKGROUND);setContentView(container);
    TextView heading=text("ASTERION  /  CONTROL",22,true);heading.setPadding(20,16,16,5);container.addView(heading);
    status=text("Remote access and device supervision",12,false);status.setPadding(20,0,16,8);container.addView(status);
    LinearLayout nav=new LinearLayout(this);nav.setOrientation(LinearLayout.HORIZONTAL);nav.setPadding(8,6,8,6);container.addView(nav);
    navButton(nav,"Remote",()->show(0));navButton(nav,"Health",()->show(1));navButton(nav,"Connections",()->show(2));
    remotePanel=new LinearLayout(this);remotePanel.setOrientation(LinearLayout.VERTICAL);container.addView(remotePanel,new LinearLayout.LayoutParams(-1,0,1));
    web=new WebView(this);web.setBackgroundColor(BACKGROUND);WebSettings ws=web.getSettings();ws.setJavaScriptEnabled(true);ws.setDomStorageEnabled(false);ws.setAllowFileAccess(false);
    ws.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);web.setWebViewClient(new WebViewClient(){
      @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){return !sameOrigin(request.getUrl().toString(),prefs.getString("url",""));}
      @Override public void onPageFinished(WebView view,String url){String token=prefs.getString("token","");
        if(sameOrigin(url,prefs.getString("url",""))&&!token.isEmpty()){
          String js="(function(){const t=document.querySelector('#token');const b=document.querySelector('#connect');if(t&&b){t.value="+JSONObject.quote(token)+";b.click()}})()";
          view.evaluateJavascript(js,null);
        }
      }
    });remotePanel.addView(web,new LinearLayout.LayoutParams(-1,-1));
    healthPanel=new LinearLayout(this);healthPanel.setOrientation(LinearLayout.VERTICAL);healthPanel.setPadding(20,12,20,12);
    deviceStatus=text("Reading device status...",16,false);healthPanel.addView(deviceStatus);container.addView(healthPanel,new LinearLayout.LayoutParams(-1,0,1));
    connectionPanel=new LinearLayout(this);connectionPanel.setOrientation(LinearLayout.VERTICAL);connectionPanel.setPadding(20,10,20,8);
    ScrollView wrap=new ScrollView(this);wrap.addView(connectionPanel);container.addView(wrap,new LinearLayout.LayoutParams(-1,0,1));
    connectionPanel.addView(text("Windows agent address",15,true));serverUrl=input(prefs.getString("url","http://192.168.1.2:8911"),false);connectionPanel.addView(serverUrl);
    connectionPanel.addView(text("Windows API token",15,true));serverToken=input(prefs.getString("token",""),true);connectionPanel.addView(serverToken);
    connectionPanel.addView(text("Phone agent reachable IP (Wi-Fi or VPN)",15,true));localAddress=input(prefs.getString("phoneip",ipAddress()),false);connectionPanel.addView(localAddress);
    Button connect=button("Save and connect to PC");connectionPanel.addView(connect);connect.setOnClickListener(v->{save();show(0);connectRemote();});
    connectionPanel.addView(text("Phone agent: independent of USB/ADB",16,true));
    connectionPanel.addView(text("Your phone hosts a local authenticated control API at port 8973. Keep the agent notification visible while remote control is enabled.",12,false));
    Button agent=button("Start phone agent");connectionPanel.addView(agent);agent.setOnClickListener(v->{
      if(Build.VERSION.SDK_INT>=33&&checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED){requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},3);}
      startForegroundService(new Intent(this,AgentService.class));Toast.makeText(this,"Agent started",Toast.LENGTH_SHORT).show();updateHealth();
    });
    Button register=button("Register phone with Windows");connectionPanel.addView(register);register.setOnClickListener(v->registerPhone());
    Button accessibility=button("Enable phone input control");connectionPanel.addView(accessibility);accessibility.setOnClickListener(v->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
    Button capture=button("Start live phone screen sharing");connectionPanel.addView(capture);capture.setOnClickListener(v->{
      MediaProjectionManager m=(MediaProjectionManager)getSystemService(Context.MEDIA_PROJECTION_SERVICE);
      startActivityForResult(m.createScreenCaptureIntent(),CAPTURE_REQUEST);
    });
    Button stopCapture=button("Stop screen sharing");connectionPanel.addView(stopCapture);stopCapture.setOnClickListener(v->stopService(new Intent(this,CaptureService.class)));
    Button stopAgent=button("Stop phone remote agent");connectionPanel.addView(stopAgent);stopAgent.setOnClickListener(v->stopService(new Intent(this,AgentService.class)));
    TextView tokenText=text("Phone agent token: "+AgentService.token(this),11,false);tokenText.setTextIsSelectable(true);connectionPanel.addView(tokenText);
    connectionPanel.addView(text("For access outside the local network, connect both devices using an encrypted private VPN. Never expose the HTTP agent directly to the public internet. Android requires manual authorization for a new screen-capture session.",12,false));
    show(2);updateHealth();handler.postDelayed(new Runnable(){@Override public void run(){updateHealth();handler.postDelayed(this,3000);}},3000);
  }
  private TextView text(String value,int sp,boolean bold){TextView t=new TextView(this);t.setText(value);t.setTextSize(sp);t.setTextColor(TEXT);t.setPadding(6,8,6,8);if(bold)t.setTypeface(null,1);return t;}
  private EditText input(String value,boolean secret){EditText e=new EditText(this);e.setSingleLine(true);e.setText(value);e.setTextColor(TEXT);e.setHintTextColor(Color.GRAY);e.setTextSize(14);e.setPadding(14,12,14,12);e.setBackgroundColor(PANEL);
    if(secret)e.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
    e.setLayoutParams(new LinearLayout.LayoutParams(-1,-2));return e;}
  private Button button(String label){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextColor(TEXT);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(PANEL));return b;}
  private void navButton(LinearLayout nav,String label,Runnable onClick){Button b=button(label);nav.addView(b,new LinearLayout.LayoutParams(0,-2,1));b.setOnClickListener(v->onClick.run());}
  private void show(int tab){remotePanel.setVisibility(tab==0?View.VISIBLE:View.GONE);healthPanel.setVisibility(tab==1?View.VISIBLE:View.GONE);connectionPanel.getParent();
    ((View)connectionPanel.getParent()).setVisibility(tab==2?View.VISIBLE:View.GONE);if(tab==0&&web.getUrl()==null)connectRemote();}
  private void save(){prefs.edit().putString("url",serverUrl.getText().toString().trim()).putString("token",serverToken.getText().toString().trim())
    .putString("phoneip",localAddress.getText().toString().trim()).apply();}
  private void connectRemote(){String url=prefs.getString("url","");if(url.startsWith("http://")||url.startsWith("https://")){web.loadUrl(url);status.setText("PC: "+url);}else status.setText("Set a valid PC address in Connections");}
  private static boolean sameOrigin(String a,String b){try{URL u=new URL(a),v=new URL(b);return u.getProtocol().equals(v.getProtocol())&&u.getHost().equalsIgnoreCase(v.getHost())&&u.getPort()==v.getPort();}catch(Exception ex){return false;}}
  private static String ipAddress(){try{for(NetworkInterface n:Collections.list(NetworkInterface.getNetworkInterfaces())){
    if(!n.isUp()||n.isLoopback())continue;for(java.net.InetAddress addr:Collections.list(n.getInetAddresses())){
      if(addr instanceof Inet4Address&&!addr.isLoopbackAddress()&&addr.isSiteLocalAddress())return addr.getHostAddress();
    }
  }}catch(Exception ignored){}return "";}
  private void registerPhone(){save();if(!AgentService.running){Toast.makeText(this,"Start the agent first",Toast.LENGTH_LONG).show();return;}
    new Thread(()->{try{
      URL url=new URL(prefs.getString("url","").replaceAll("/+$","")+"/api/v1/phone/register");HttpURLConnection conn=(HttpURLConnection)url.openConnection();conn.setConnectTimeout(5000);conn.setReadTimeout(6000);conn.setRequestMethod("POST");conn.setDoOutput(true);
      conn.setRequestProperty("Authorization","Bearer "+prefs.getString("token",""));conn.setRequestProperty("Content-Type","application/json");
      JSONObject payload=new JSONObject().put("base_url","http://"+prefs.getString("phoneip",ipAddress())+":"+AgentService.PORT).put("token",AgentService.token(this));
      try(OutputStream out=conn.getOutputStream()){out.write(payload.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));}
      int code=conn.getResponseCode();runOnUiThread(()->Toast.makeText(this,code==200?"Phone registered with Windows":"Registration failed: HTTP "+code,Toast.LENGTH_LONG).show());conn.disconnect();
    }catch(Exception e){runOnUiThread(()->Toast.makeText(this,"Connection failed: "+e.getMessage(),Toast.LENGTH_LONG).show());}}).start();
  }
  private void updateHealth(){if(deviceStatus==null)return;try{
    Intent b=registerReceiver(null,new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));int level=b==null?-1:b.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL,-1);
    int temp=b==null?-1:b.getIntExtra(android.os.BatteryManager.EXTRA_TEMPERATURE,-1);
    android.app.ActivityManager.MemoryInfo m=new android.app.ActivityManager.MemoryInfo();((android.app.ActivityManager)getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(m);
    android.os.PowerManager p=(android.os.PowerManager)getSystemService(POWER_SERVICE);
    deviceStatus.setText("PHONE HEALTH\n\n"+Build.MODEL+" / Android "+Build.VERSION.RELEASE+"\n\nBattery: "+level+"%\nBattery temperature: "+(temp>=0?temp/10.0+"°C":"unavailable")+
      "\nRAM free: "+String.format(java.util.Locale.US,"%.1f GB",m.availMem/1e9)+"\nThermal status: "+p.getCurrentThermalStatus()+
      "\n\nPhone agent: "+(AgentService.running?"active":"inactive")+"\nInput access: "+(ControlAccessibilityService.active!=null?"authorized":"not enabled")+
      "\nLive capture: "+(CaptureService.active?"active":"inactive"));
  }catch(Exception e){deviceStatus.setText("Device health unavailable: "+e.getMessage());}}
  @Override protected void onActivityResult(int request,int code,Intent data){super.onActivityResult(request,code,data);
    if(request==CAPTURE_REQUEST&&code==RESULT_OK&&data!=null){Intent i=new Intent(this,CaptureService.class);i.putExtra("result",code);i.putExtra("data",data);startForegroundService(i);}
  }
  @Override public void onBackPressed(){if(remotePanel.getVisibility()==View.VISIBLE&&web.canGoBack())web.goBack();else show(2);}
  @Override protected void onDestroy(){if(web!=null){web.destroy();}super.onDestroy();}
}
