package com.asterion.control;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.webkit.SslErrorHandler;
import android.net.http.SslError;
import androidx.webkit.ProxyConfig;
import androidx.webkit.ProxyController;
import androidx.webkit.WebViewFeature;
import org.torproject.jni.TorService;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;

/** Process-local Tor lifecycle. Never clears the proxy while a browsing view is alive. */
final class TorBrowserRoute {
    private static final String CHECK="https://check.torproject.org/api/ip";
    private final Context context;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private final ExecutorService io=Executors.newSingleThreadExecutor();
    private final Consumer<String> changed;
    private TorService service;
    private WebView probe;
    private boolean bound,closed,checking;
    private volatile boolean ready;
    private long started;
    private String state="Connecting to Tor";
    TorBrowserRoute(Context c,Consumer<String> listener){context=c;changed=listener;}
    boolean ready(){return ready;}
    String state(){return state;}
    private void state(String value){state=value;changed.accept(value);}
    private final ServiceConnection connection=new ServiceConnection(){
        @Override public void onServiceConnected(ComponentName name,IBinder binder){
            if(closed)return;
            service=((TorService.LocalBinder)binder).getService();poll();
        }
        @Override public void onServiceDisconnected(ComponentName name){fail("Tor service disconnected");}
        @Override public void onBindingDied(ComponentName name){fail("Tor service stopped");}
        @Override public void onNullBinding(ComponentName name){fail("Tor service unavailable");}
    };
    void start(){
        if(closed)return;
        if(!WebViewFeature.isFeatureSupported(WebViewFeature.PROXY_OVERRIDE)){
            fail("WebView proxy override unsupported");return;
        }
        started=android.os.SystemClock.elapsedRealtime();
        try{
            bound=context.bindService(new Intent(context,TorService.class),connection,Context.BIND_AUTO_CREATE);
            if(!bound)fail("Tor service could not start");
            ui.postDelayed(()->{if(!ready&&!closed)fail("Tor connection verification timed out");},120000);
        }catch(RuntimeException|LinkageError failure){fail("Tor native runtime unavailable");}
    }
    private void poll(){
        if(closed||checking||service==null)return;
        final TorService current=service;
        io.execute(()->{
            int port=-1;
            try{if("1".equals(current.getInfo("status/circuit-established")))port=current.getSocksPort();}
            catch(RuntimeException ignored){}
            final int observed=port;
            ui.post(()->{
                if(closed||service!=current||checking)return;
                if(observed>0&&observed<=65535)configure(observed);
                else if(android.os.SystemClock.elapsedRealtime()-started<120000)ui.postDelayed(this::poll,1000);
                else fail("Tor circuit was not established");
            });
        });
    }
    private void configure(int port){
        checking=true;state("Checking Tor exit route");
        try{
            ProxyConfig config=new ProxyConfig.Builder()
                .addProxyRule("socks5://127.0.0.1:"+port)
                .removeImplicitRules().build();
            ProxyController.getInstance().setProxyOverride(config,context.getMainExecutor(),()->{
                if(!closed&&checking)verifyWebView();
            });
        }catch(RuntimeException e){fail("Tor proxy configuration failed");}
    }
    private void verifyWebView(){
        // Check the SAME WebView networking stack used for browsing, rather
        // than declaring success from a Tor daemon status or an HTTP ACK.
        probe=new WebView(context);
        probe.getSettings().setJavaScriptEnabled(true);
        probe.getSettings().setAllowFileAccess(false);
        probe.getSettings().setAllowContentAccess(false);
        probe.getSettings().setCacheMode(android.webkit.WebSettings.LOAD_NO_CACHE);
        probe.getSettings().setSafeBrowsingEnabled(false);
        probe.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView w,WebResourceRequest req){return !CHECK.equals(req.getUrl().toString());}
            @Override public void onReceivedError(WebView w,WebResourceRequest req,WebResourceError e){if(req.isForMainFrame())fail("Tor exit check failed");}
            @Override public void onReceivedSslError(WebView w,SslErrorHandler h,SslError e){h.cancel();fail("Tor exit TLS verification failed");}
            @Override public void onPageFinished(WebView w,String url){
                if(closed||w!=probe||!CHECK.equals(url)||w.getCertificate()==null)return;
                w.evaluateJavascript("document.body ? document.body.innerText : ''",json->{
                    if(closed||w!=probe)return;
                    try{
                        Object decoded=new JSONTokener(json).nextValue();
                        JSONObject proof=new JSONObject(String.valueOf(decoded));
                        if(!proof.optBoolean("IsTor",false))throw new SecurityException();
                        disposeProbe();ready=true;state("Tor exit verified");watch();
                    }catch(Exception invalid){fail("Tor exit not verified");}
                });
            }
        });
        probe.loadUrl(CHECK);
    }
    private void watch(){
        if(closed||!ready||service==null)return;
        final TorService current=service;
        io.execute(()->{
            boolean connected=false;
            try{connected="1".equals(current.getInfo("status/circuit-established"))&&current.getSocksPort()>0;}
            catch(RuntimeException ignored){}
            final boolean ok=connected;
            ui.post(()->{if(closed||!ready)return;if(!ok)fail("Tor circuit lost; browsing stopped");else ui.postDelayed(this::watch,5000);});
        });
    }
    private void disposeProbe(){if(probe!=null){WebView old=probe;probe=null;old.stopLoading();old.destroy();}}
    private void fail(String why){if(closed)return;ready=false;checking=false;disposeProbe();state(why);}
    void close(){
        closed=true;ready=false;ui.removeCallbacksAndMessages(null);disposeProbe();
        if(bound){try{context.unbindService(connection);}catch(Exception ignored){}bound=false;}
        io.shutdownNow();
        // Keep the process-specific override in place: never fallback to direct.
    }
}
