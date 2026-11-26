package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ComponentName;
import android.content.Intent;
import android.content.ServiceConnection;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.inputmethod.EditorInfo;
import android.webkit.*;
import android.widget.*;
import androidx.webkit.ProxyConfig;
import androidx.webkit.ProxyController;
import androidx.webkit.WebViewFeature;
import org.json.JSONObject;
import org.torproject.jni.TorService;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Proxy;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** A separate owner-opened Tor browser process. No changes to the OS VPN,
 * normal Browser profile, paired WSS, or ordinary download engine. */
public final class TorActivity extends Activity {
    private static boolean directoryConfigured;
    private static final String CHECK="https://check.torproject.org/";
    private static final String CHECK_API="https://check.torproject.org/api/ip";
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private WebView web;
    private EditText address;
    private TextView status,go;
    private TorService tor;
    private boolean bound,closed,probing;
    private volatile boolean ready;
    private long started,verifiedAt;
    private int proxyPort=-1;
    private String privateProfile;
    private String pending;
    private int epoch;
    private int dp(float v){return DesignSystem.dp(this,v);}
    private final ServiceConnection connection=new ServiceConnection(){
        @Override public void onServiceConnected(ComponentName name,IBinder binder){
            if(closed)return;
            if(!(binder instanceof TorService.LocalBinder)){fail("Tor service identity unavailable");return;}
            tor=((TorService.LocalBinder)binder).getService();poll();
        }
        @Override public void onServiceDisconnected(ComponentName name){fail("Tor service disconnected");}
        @Override public void onBindingDied(ComponentName name){fail("Tor service stopped");}
        @Override public void onNullBinding(ComponentName name){fail("Tor service binding unavailable");}
    };
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        if(!directoryConfigured){
            WebView.setDataDirectorySuffix("asterion_tor");
            directoryConfigured=true;
            BrowserPrivateProfiles.cleanPreviousProcess();
        }
        pending=TorAddressPolicy.resolve(getIntent().getStringExtra("tor_url"));
        LinearLayout root=DesignSystem.vertical(this);
        root.setBackgroundColor(DesignSystem.BG);
        if(android.os.Build.VERSION.SDK_INT>=30){
            getWindow().setDecorFitsSystemWindows(false);
            getWindow().setStatusBarColor(Color.TRANSPARENT);getWindow().setNavigationBarColor(Color.TRANSPARENT);
            root.setOnApplyWindowInsetsListener((v,insets)->{
                android.graphics.Insets a=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
                android.graphics.Insets k=insets.getInsets(WindowInsets.Type.ime());
                root.setPadding(a.left,a.top,a.right,Math.max(a.bottom,k.bottom));return insets;
            });
        }
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        LinearLayout bar=DesignSystem.horizontal(this);bar.setGravity(Gravity.CENTER_VERTICAL);bar.setPadding(dp(8),dp(4),dp(8),dp(4));
        address=new EditText(this);address.setSingleLine(true);address.setTextSize(15);
        address.setTextColor(DesignSystem.TEXT);address.setHintTextColor(DesignSystem.MUTED);
        address.setHint("HTTPS or v3 .onion address");address.setSaveEnabled(false);
        address.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        address.setImeOptions(EditorInfo.IME_ACTION_GO|EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING);
        address.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);
        address.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE2,DesignSystem.EDGE,12));address.setPadding(dp(10),0,dp(10),0);
        bar.addView(address,new LinearLayout.LayoutParams(0,dp(48),1));
        go=button("Go",()->navigate(address.getText().toString()));go.setEnabled(false);bar.addView(go,new LinearLayout.LayoutParams(dp(54),dp(48)));
        address.setOnEditorActionListener((v,a,e)->{if(a==EditorInfo.IME_ACTION_GO){navigate(address.getText().toString());return true;}return false;});
        root.addView(bar);
        status=DesignSystem.text(this,"Tor · Waiting for a verified circuit",13,DesignSystem.MUTED,false);
        status.setPadding(dp(12),dp(8),dp(12),dp(8));root.addView(status);
        FrameLayout viewport=new FrameLayout(this);root.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout nav=DesignSystem.horizontal(this);
        for(String label:new String[]{"Back","Verify","Close Tor"}){
            Runnable action=label.equals("Back")?()->{if(ready&&web!=null&&web.canGoBack())web.goBack();}:
                label.equals("Verify")?()->{if(ready){ready=false;go.setEnabled(false);web.stopLoading();web.getSettings().setBlockNetworkLoads(true);probe();}}:this::finish;
            nav.addView(button(label,action),new LinearLayout.LayoutParams(0,dp(48),1));
        }root.addView(nav);setContentView(root);root.requestApplyInsets();
        if(!WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)||!BrowserPrivateProfiles.supported()){
            fail("This WebView cannot isolate Tor proxy and storage");return;
        }
        try{
            web=new WebView(this);
            privateProfile=BrowserPrivateProfiles.newName();BrowserPrivateProfiles.attach(web,privateProfile);
            web.setSaveEnabled(false);web.setSaveFromParentEnabled(false);
            web.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
            WebSettings settings=web.getSettings();
            settings.setBlockNetworkLoads(true);
            // Restrict active content until a separate fingerprint/leak test qualifies it.
            settings.setJavaScriptEnabled(false);settings.setDomStorageEnabled(false);
            settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);
            settings.setJavaScriptCanOpenWindowsAutomatically(false);settings.setSupportMultipleWindows(false);
            settings.setGeolocationEnabled(false);settings.setMediaPlaybackRequiresUserGesture(true);
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
            // Avoid WebView's external reputation lookup for onion destinations.
            settings.setSafeBrowsingEnabled(false);
            web.setWebChromeClient(new WebChromeClient(){
                @Override public void onPermissionRequest(PermissionRequest request){request.deny();}
                @Override public void onGeolocationPermissionsShowPrompt(String origin,GeolocationPermissions.Callback callback){callback.invoke(origin,false,false);}
                @Override public boolean onCreateWindow(WebView v,boolean dialog,boolean gesture,android.os.Message msg){return false;}
            });
            web.setWebViewClient(new WebViewClient(){
                @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest request){
                    return !ready||TorAddressPolicy.resolve(request.getUrl().toString())==null||!request.isForMainFrame();
                }
                @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest request){
                    if(!ready||!"GET".equals(request.getMethod())||TorAddressPolicy.resolve(request.getUrl().toString())==null)
                        return new WebResourceResponse("text/plain","UTF-8",403,"Blocked",java.util.Collections.emptyMap(),new ByteArrayInputStream(new byte[0]));
                    return null;
                }
                @Override public void onReceivedSslError(WebView v,SslErrorHandler h,android.net.http.SslError e){h.cancel();status.setText("Tor · Website certificate rejected");}
                @Override public void onReceivedError(WebView v,WebResourceRequest request,WebResourceError error){
                    if(request.isForMainFrame())status.setText("Tor · Page could not load; no direct fallback");
                }
                @Override public void onPageFinished(WebView v,String url){
                    if(ready&&TorAddressPolicy.resolve(url)!=null){address.setText(url);status.setText("Tor exit verified · Restricted browser mode");}
                }
            });
            web.setDownloadListener((u,a,d,m,l)->Toast.makeText(this,"Downloads disabled in isolated Tor mode",Toast.LENGTH_SHORT).show());
            viewport.addView(web,new FrameLayout.LayoutParams(-1,-1));
            // Bind the packaged native daemon in this SAME isolated process.
            // No exported Tor control endpoint and no new Android VPN service.
            started=SystemClock.elapsedRealtime();
            bound=bindService(new Intent(this,TorService.class),connection,BIND_AUTO_CREATE);
            if(!bound)fail("Native Tor service unavailable");
        }catch(Exception|LinkageError failure){fail("Tor initialization failed: "+failure.getClass().getSimpleName());}
    }
    private TextView button(String title,Runnable action){
        TextView v=DesignSystem.text(this,title,14,DesignSystem.TEXT,true);v.setGravity(Gravity.CENTER);
        DesignSystem.clickable(v,this,DesignSystem.SURFACE2,DesignSystem.EDGE,12);
        v.setContentDescription(title);v.setFocusable(true);v.setOnClickListener(w->action.run());return v;
    }
    private void poll(){
        if(closed||tor==null)return;
        if(!ready&&verifiedAt==0&&SystemClock.elapsedRealtime()-started>120000){fail("Tor bootstrap timed out");return;}
        if(!ready&&!probing){
            if(SystemClock.elapsedRealtime()-started>120000){fail("Tor bootstrap timed out");return;}
            int socks=tor.getSocksPort(),http=tor.getHttpTunnelPort();
            if(socks>0&&http>0){proxyPort=socks;probe();}
        }else if(ready&&(tor.getSocksPort()!=proxyPort||SystemClock.elapsedRealtime()-verifiedAt>300000)){
            ready=false;go.setEnabled(false);web.stopLoading();web.getSettings().setBlockNetworkLoads(true);
            if(tor.getSocksPort()!=proxyPort){fail("Tor proxy changed; reopen mode");return;}
            probe();
        }
        ui.postDelayed(this::poll,1000);
    }
    private void probe(){
        if(closed||probing||tor==null)return;
        final int socks=tor.getSocksPort(),http=tor.getHttpTunnelPort(),generation=++epoch;
        if(socks<=0||http<=0){fail("Tor proxy unavailable");return;}
        probing=true;status.setText("Tor · Checking actual exit through native proxy");
        io.execute(()->{
            boolean verified=false;
            HttpURLConnection conn=null;
            try{
                // Explicit HTTP CONNECT proxy from the bound native Tor service.
                // HTTPS validates the check service certificate normally.
                conn=(HttpURLConnection)new URL(CHECK_API).openConnection(new Proxy(Proxy.Type.HTTP,new InetSocketAddress("127.0.0.1",http)));
                conn.setConnectTimeout(20000);conn.setReadTimeout(20000);
                conn.setInstanceFollowRedirects(false);conn.setUseCaches(false);
                if(conn.getResponseCode()==200){
                    try(InputStream in=conn.getInputStream()){
                        ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buf=new byte[512];int n;
                        while((n=in.read(buf))!=-1){if(out.size()+n>4096)throw new IllegalStateException("oversized proof");out.write(buf,0,n);}
                        JSONObject proof=new JSONObject(new String(out.toByteArray(),StandardCharsets.UTF_8));
                        verified=proof.optBoolean("IsTor",false)&&!proof.optString("IP","").isEmpty();
                    }
                }
            }catch(Exception ignored){}finally{if(conn!=null)conn.disconnect();}
            final boolean ok=verified;
            ui.post(()->{
                if(closed||generation!=epoch)return;
                probing=false;
                if(!ok||tor==null||tor.getSocksPort()!=socks){
                    if(SystemClock.elapsedRealtime()-started>120000||verifiedAt>0){fail("Tor exit could not be verified");return;}
                    status.setText("Tor · Building circuit; exit proof pending");return;
                }
                try{
                    // No DIRECT rule, no implicit loopback bypass, no other proxy.
                    ProxyConfig config=new ProxyConfig.Builder().addProxyRule("socks://127.0.0.1:"+socks).removeImplicitRules().build();
                    probing=true;
                    ProxyController.getInstance().setProxyOverride(config,getMainExecutor(),()->{
                        if(closed||generation!=epoch)return;
                        probing=false;proxyPort=socks;verifiedAt=SystemClock.elapsedRealtime();
                        ready=true;web.getSettings().setBlockNetworkLoads(false);go.setEnabled(true);
                        status.setText("Tor exit verified · Restricted browser mode");
                        if(pending!=null){String url=pending;pending=null;navigate(url);}
                        else if(web.getUrl()==null)navigate(CHECK);
                    });
                }catch(RuntimeException failure){fail("WebView Tor proxy could not be applied");}
            });
        });
    }
    private void navigate(String value){
        if(!ready||closed||web==null){status.setText("Tor is not verified; navigation blocked");return;}
        String url=TorAddressPolicy.resolve(value);
        if(url==null){status.setText("Enter a valid HTTPS or v3 onion address");return;}
        address.clearFocus();android.view.inputmethod.InputMethodManager keyboard=(android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
        if(keyboard!=null)keyboard.hideSoftInputFromWindow(address.getWindowToken(),0);
        web.loadUrl(url);
    }
    private void fail(String reason){
        ready=false;closed=true;epoch++;ui.removeCallbacksAndMessages(null);go.setEnabled(false);status.setText(reason+" · No direct fallback");
        if(web!=null){web.stopLoading();web.getSettings().setBlockNetworkLoads(true);}
        releaseService();
    }
    private void releaseService(){
        if(bound){bound=false;try{unbindService(connection);}catch(Exception ignored){}}
        tor=null;
    }
    @Override public void onDestroy(){
        closed=true;ready=false;epoch++;ui.removeCallbacksAndMessages(null);
        if(web!=null){
            web.stopLoading();web.getSettings().setBlockNetworkLoads(true);
            if(web.getParent()!=null)((android.view.ViewGroup)web.getParent()).removeView(web);
            web.destroy();web=null;
        }
        releaseService();io.shutdownNow();
        if(privateProfile!=null)try{BrowserPrivateProfiles.released(privateProfile,()->{});}catch(Exception ignored){}
        // Proxy override is process-only and intentionally never cleared into a direct route.
        super.onDestroy();
    }
}
