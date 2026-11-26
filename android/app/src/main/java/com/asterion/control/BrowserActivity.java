package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.database.Cursor;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;

/** Asterion Browser: actual on-device multi-tab WebView browser, not a crawler mock.
 *
 * Runs in a dedicated Android process with its own WebView data-directory
 * suffix, isolated from Control's authenticated Windows dashboard WebView.
 * No JavaScript bridge, shell integration, silent downloads or credential export.
 * Signed cross-app browser automation, richer profiles and PC crawler are separate
 * future capabilities; this Activity does not claim those are already delivered.
 */
public final class BrowserActivity extends Activity {
    // Only the real foreground WebView URL can authorize vault Autofill.
    // The OS AssistStructure's webDomain alone is not trusted.
    private static volatile BrowserActivity activeBrowser;
    static String verifiedActiveHttpsOrigin(){
        BrowserActivity browser=activeBrowser;
        if(browser==null||browser.isFinishing())return null;
        final String[] value={null};
        Runnable read=()->{
            try{
                if(activeBrowser!=browser)return;
                BrowserTab tab=browser.current();
                if(tab==null)return;
                value[0]=ControlPasswordVault.exactOrigin(tab.web.getUrl());
            }catch(Exception invalid){value[0]=null;}
        };
        if(Looper.myLooper()==Looper.getMainLooper())read.run();
        else{
            java.util.concurrent.CountDownLatch done=new java.util.concurrent.CountDownLatch(1);
            new Handler(Looper.getMainLooper()).post(()->{
                try{read.run();}finally{done.countDown();}
            });
            try{if(!done.await(1500,java.util.concurrent.TimeUnit.MILLISECONDS))return null;}
            catch(InterruptedException interrupted){Thread.currentThread().interrupt();return null;}
        }
        return value[0];
    }
    private static final int MAX_TABS = 8;
    private static final String START = "about:blank";
    private final List<BrowserTab> tabs = new ArrayList<>();
    private LinearLayout root, tabStrip;
    private FrameLayout viewport;
    private EditText address;
    private TextView status, counter, back, forward;
    private ProgressBar progress;
    private int active = -1;
    private BrowserProtection protection;
    private SharedPreferences browserPrefs;

    private int dp(int value) { return DesignSystem.dp(this, value); }
    private TextView label(String text, int size, int color, boolean bold) {
        return DesignSystem.text(this, text, size, color, bold);
    }
    private void notice(String msg) { Toast.makeText(this, msg, Toast.LENGTH_SHORT).show(); }
    private void add(LinearLayout parent, View child) {
        parent.addView(child, new LinearLayout.LayoutParams(-1, -2));
    }
    private TextView control(String text, Runnable action) {
        TextView item = label(text, 12, DesignSystem.TEXT, true);
        item.setGravity(Gravity.CENTER);
        item.setPadding(dp(10), dp(12), dp(10), dp(12));
        DesignSystem.clickable(item, this, DesignSystem.SURFACE2, DesignSystem.EDGE, 13);
        item.setOnClickListener(v -> action.run());
        return item;
    }
    private void tool(LinearLayout parent, String name, Runnable action) {
        TextView item = control(name, action);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, dp(44), 1);
        lp.setMargins(dp(3), 0, dp(3), 0);
        parent.addView(item, lp);
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);DesignSystem.configure(this);
        protection=new BrowserProtection(this);
        browserPrefs=getSharedPreferences("asterion_browser_session_v1",Context.MODE_PRIVATE);
        protection.refresh(false,(updated,reason)->{
            if(!isFinishing()&&status!=null)refreshToolbar();
        });
        // Must be set before any WebView exists in this dedicated :asterion_browser process.
        if (Build.VERSION.SDK_INT >= 28) WebView.setDataDirectorySuffix("asterion_browser");
        getWindow().setStatusBarColor(DesignSystem.BG);
        getWindow().setNavigationBarColor(DesignSystem.BG);
        root = DesignSystem.vertical(this);
        root.setBackgroundColor(DesignSystem.BG);
        setContentView(root);

        LinearLayout heading = DesignSystem.horizontal(this);
        heading.setPadding(dp(15), dp(13), dp(15), dp(11));
        heading.setBackground(DesignSystem.gradient(this, 0xFF30264E, 0xFF183348, 0));
        DesignSystem.AsterionMark mark = new DesignSystem.AsterionMark(this);
        heading.addView(mark, new LinearLayout.LayoutParams(dp(38), dp(38)));
        LinearLayout titles = DesignSystem.vertical(this);
        titles.setPadding(dp(11), 0, 0, 0);
        add(titles, label("ASTERION", 15, DesignSystem.TEXT, true));
        add(titles, label("BROWSER", 10, DesignSystem.TEAL, true));
        heading.addView(titles, new LinearLayout.LayoutParams(0, -2, 1));
        counter = control("Tabs", this::newTab);
        heading.addView(counter);
        add(root, heading);

        LinearLayout search = DesignSystem.horizontal(this);
        search.setPadding(dp(11), dp(12), dp(11), dp(10));
        address = new EditText(this);
        address.setSingleLine(true);
        address.setTextColor(DesignSystem.TEXT);
        address.setHintTextColor(DesignSystem.MUTED);
        address.setHint("Search or enter an address");
        address.setTextSize(13);
        address.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        address.setImeOptions(EditorInfo.IME_ACTION_GO);
        address.setPadding(dp(13), dp(9), dp(13), dp(9));
        address.setSelectAllOnFocus(true);
        address.setBackground(DesignSystem.shape(this, DesignSystem.SURFACE2, DesignSystem.EDGE, 15));
        address.setOnEditorActionListener((view, action, event) -> {
            if (action == EditorInfo.IME_ACTION_GO ||
                    (event != null && event.getKeyCode() == KeyEvent.KEYCODE_ENTER)) {
                navigate(address.getText().toString());
                return true;
            }
            return false;
        });
        search.addView(address, new LinearLayout.LayoutParams(0, dp(45), 1));
        TextView go = control("Go", () -> navigate(address.getText().toString()));
        LinearLayout.LayoutParams goLp = new LinearLayout.LayoutParams(dp(54), dp(45));
        goLp.leftMargin = dp(8);
        search.addView(go, goLp);
        add(root, search);

        HorizontalScrollView scroll = new HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        tabStrip = DesignSystem.horizontal(this);
        tabStrip.setPadding(dp(10), dp(5), dp(10), dp(7));
        scroll.addView(tabStrip);
        add(root, scroll);

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        add(root, progress);
        viewport = new FrameLayout(this);
        root.addView(viewport, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout nav = DesignSystem.horizontal(this);
        nav.setPadding(dp(5), dp(8), dp(5), dp(9));
        back = control("Back", () -> { BrowserTab tab = current(); if(tab!=null&&tab.web.canGoBack()) tab.web.goBack(); });
        forward = control("Next", () -> { BrowserTab tab = current(); if(tab!=null&&tab.web.canGoForward()) tab.web.goForward(); });
        nav.addView(back, new LinearLayout.LayoutParams(0, dp(45), 1));
        nav.addView(forward, new LinearLayout.LayoutParams(0, dp(45), 1));
        tool(nav, "Reload", () -> { BrowserTab tab = current(); if(tab!=null) tab.web.reload(); });
        tool(nav, "+ Tab", this::newTab);
        tool(nav, "More", this::showBrowserMenu);
        add(root, nav);

        status = label("Ready", 11, DesignSystem.MUTED, false);
        status.setPadding(dp(17), dp(1), dp(13), dp(9));
        add(root, status);

        if(saved != null) {
            ArrayList<String> urls = saved.getStringArrayList("urls");
            if(urls != null) {
                for(String url : urls) {
                    if(tabs.size() >= MAX_TABS) break;
                    addTab(safeAddress(url));
                }
                if(!tabs.isEmpty()) showTab(Math.min(tabs.size()-1,
                    Math.max(0, saved.getInt("current",0))));
            }
        }
        if(tabs.isEmpty() && saved==null) restorePersistedTabs();
        if(tabs.isEmpty()) newTab();
    }

    private String safeAddress(String raw) {
        String value = raw == null ? "" : raw.trim();
        if(value.isEmpty()) return START;
        // Reject WebView-local and privilege-bearing schemes, including javascript:, file:, data:.
        if(value.matches("(?i)^[a-z][a-z0-9+.-]*:.*") &&
                !value.startsWith("https://") && !value.startsWith("http://")) return START;
        if(!value.startsWith("https://") && !value.startsWith("http://")) {
            if(value.contains(" ") || !value.contains(".")) {
                return searchPrefix() +
                    URLEncoder.encode(value, StandardCharsets.UTF_8);
            }
            value = "https://" + value;
        }
        try {
            URI parsed = URI.create(value);
            String host = parsed.getHost();
            if(host == null || host.isBlank() || parsed.getUserInfo()!=null) return START;
            return value;
        } catch(Exception bad) { return START; }
    }

    private BrowserTab current() {
        return active >= 0 && active < tabs.size() ? tabs.get(active) : null;
    }
    private void newTab() {
        if(tabs.size() >= MAX_TABS) { notice("Close a tab before opening another"); return; }
        addTab(START);
        showTab(tabs.size()-1);
    }
    private void addTab(String url) {
        WebView view = new WebView(this);
        view.setBackgroundColor(Color.WHITE);
        WebSettings s = view.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if(Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        BrowserTab tab = new BrowserTab(view);
        tab.pageUrl=url;
        view.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView web, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                if(scheme == null || (!scheme.equalsIgnoreCase("http") &&
                        !scheme.equalsIgnoreCase("https")))return true;
                // Prevent automatic advertising/popunder navigation, never all
                // cross-origin redirects (legitimate OAuth would be broken).
                if(request.isForMainFrame()&&!request.hasGesture() &&
                   protection.blocks(request.getUrl().toString(),tab.pageUrl)) {
                    tab.blocked.incrementAndGet();
                    return true;
                }
                return false;
            }
            @Override public WebResourceResponse shouldInterceptRequest(
                    WebView web,WebResourceRequest request) {
                WebResourceResponse denied=protection.intercept(request,tab.pageUrl);
                if(denied!=null)tab.blocked.incrementAndGet();
                return denied;
            }
            @Override public void onPageStarted(WebView web,String url,
                    android.graphics.Bitmap icon) {
                tab.pageUrl=url;
                tab.blocked.set(0);
                if(current()==tab)refreshToolbar();
            }
            @Override public void onReceivedSslError(WebView web, SslErrorHandler handler, SslError error) {
                handler.cancel();
                if(current()==tab) notice("Certificate verification failed; page blocked");
            }
            @Override public void onPageFinished(WebView web, String url) {
                tab.pageUrl=url;
                protection.applyCosmetic(web,url);
                CookieManager.getInstance().flush();
                rememberPage(url,tab.title);
                if(current()==tab) refreshToolbar();
                refreshTabs();
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView web,boolean isDialog,
                    boolean isUserGesture,android.os.Message resultMsg) {
                // No surprise advertising windows or background tabs.
                tab.popups.incrementAndGet();
                if(current()==tab)notice("Unrequested popup blocked");
                return false;
            }
            @Override public void onProgressChanged(WebView web, int amount) {
                if(current()==tab) {
                    progress.setProgress(amount);
                    progress.setVisibility(amount>=100 ? View.GONE : View.VISIBLE);
                }
            }
            @Override public void onReceivedTitle(WebView web, String title) {
                tab.title=title==null||title.isBlank()?"New tab":title;
                refreshTabs();
            }
        });
        view.setDownloadListener((address,agent,disposition,type,size) ->
            confirmDownload(address,agent,type,size));
        tabs.add(tab);
        view.loadUrl(url);
    }
    private void showTab(int index) {
        if(index<0||index>=tabs.size()) return;
        BrowserTab before=current();
        if(before!=null) {
            if(before.web.getParent()==viewport)viewport.removeView(before.web);
            before.web.onPause();
        }
        viewport.removeAllViews();
        active=index;
        BrowserTab selected=current();
        if(START.equals(selected.pageUrl)||START.equals(selected.web.getUrl())){
            viewport.addView(createNativeHome(),new FrameLayout.LayoutParams(-1,-1));
        }else{
            if(selected.web.getParent()!=null)
                ((android.view.ViewGroup)selected.web.getParent()).removeView(selected.web);
            viewport.addView(selected.web,new FrameLayout.LayoutParams(-1,-1));
            selected.web.onResume();
        }
        refreshToolbar();
        refreshTabs();
    }
    private void closeTab(int index) {
        if(index<0||index>=tabs.size()) return;
        BrowserTab old=tabs.get(index);
        viewport.removeView(old.web);
        tabs.remove(index);
        old.web.stopLoading();
        old.web.destroy();
        if(tabs.isEmpty()) { active=-1; newTab(); return; }
        if(index<active) active--;
        else if(index==active) active=Math.min(index,tabs.size()-1);
        int selected=active;
        active=-1;
        showTab(selected);
    }
    private void refreshTabs() {
        if(tabStrip==null) return;
        tabStrip.removeAllViews();
        for(int i=0;i<tabs.size();i++) {
            final int selected=i;
            BrowserTab t=tabs.get(i);
            LinearLayout chip=DesignSystem.horizontal(this);
            chip.setPadding(dp(8),dp(4),dp(6),dp(4));
            chip.setBackground(DesignSystem.shape(this,
                i==active?0xFF322B52:DesignSystem.SURFACE,
                i==active?DesignSystem.PURPLE:DesignSystem.EDGE,13));
            String title=t.title.length()>19?t.title.substring(0,18)+"…":t.title;
            TextView name=label(title,11,i==active?DesignSystem.TEXT:DesignSystem.MUTED,true);
            name.setPadding(dp(4),dp(6),dp(7),dp(6));
            name.setOnClickListener(v->showTab(selected));
            chip.addView(name);
            TextView close=label("×",19,DesignSystem.MUTED,false);
            close.setPadding(dp(4),dp(1),dp(4),dp(1));
            close.setContentDescription("Close tab "+(i+1));
            close.setOnClickListener(v->closeTab(selected));
            chip.addView(close);
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-2,-2);
            lp.rightMargin=dp(7);
            tabStrip.addView(chip,lp);
        }
        if(counter!=null) counter.setText(tabs.size()+" tabs");
    }
    private void refreshToolbar() {
        BrowserTab tab=current();
        if(tab==null) return;
        String url=tab.web.getUrl();
        if(url!=null && !address.hasFocus()) address.setText(START.equals(url)?"":url);
        back.setEnabled(tab.web.canGoBack());
        forward.setEnabled(tab.web.canGoForward());
        back.setAlpha(tab.web.canGoBack()?1f:0.4f);
        forward.setAlpha(tab.web.canGoForward()?1f:0.4f);
        if(url!=null) {
            if(START.equals(url)){
                status.setText("Asterion home • "+providerName()+" search • "+
                    (protection.isEnabled()?"Shields enabled":"Shields disabled"));
            }else try {
                status.setText(Uri.parse(url).getHost()+
                    " • "+tab.blocked.get()+" requests blocked"+
                    (protection.isEnabled()?"":" • Shield off"));
            }catch(Exception ignored){status.setText("Browser");}
        }
    }
    private void navigate(String value) {
        BrowserTab tab=current();
        if(tab==null) return;
        String url=safeAddress(value);
        tab.pageUrl=url;
        if(START.equals(url)){
            showTab(active);
        }else{
            if(tab.web.getParent()!=viewport){
                viewport.removeAllViews();
                if(tab.web.getParent()!=null)
                    ((android.view.ViewGroup)tab.web.getParent()).removeView(tab.web);
                viewport.addView(tab.web,new FrameLayout.LayoutParams(-1,-1));
                tab.web.onResume();
            }
            tab.web.loadUrl(url);
        }
        address.clearFocus();
    }
    private void confirmDownload(String url, String agent, String mime, long length) {
        Uri uri;
        try {
            uri=Uri.parse(url);
            if(!"https".equalsIgnoreCase(uri.getScheme()) &&
                    !"http".equalsIgnoreCase(uri.getScheme()))
                throw new IllegalArgumentException("Unsupported download URI");
        } catch(Exception bad) { notice("Download URL is not supported"); return; }
        String host=uri.getHost()==null?"website":uri.getHost();
        String size=length>0?(" • "+(length/1024)+" KB"):"";
        new AlertDialog.Builder(this)
            .setTitle("Save download?")
            .setMessage(host+" • "+(mime==null?"unknown type":mime)+size+
                "\n\nAndroid Download Manager will save this file.")
            .setPositiveButton("Save", (dialog,which)->{
                try {
                    DownloadManager.Request req=new DownloadManager.Request(uri);
                    req.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    if(mime!=null&&!mime.isBlank()) req.setMimeType(mime);
                    if(agent!=null&&!agent.isBlank())req.addRequestHeader("User-Agent",agent);
                    String cookie=CookieManager.getInstance().getCookie(url);
                    if(cookie!=null&&!cookie.isBlank())req.addRequestHeader("Cookie",cookie);
                    DownloadManager manager=(DownloadManager)getSystemService(DOWNLOAD_SERVICE);
                    if(manager==null)throw new IllegalStateException("Android download service unavailable");
                    long downloadId=manager.enqueue(req);
                    rememberDownload(downloadId,host);
                    notice("Download queued in Android Downloads");
                }catch(Exception e){notice("Download failed: "+e.getClass().getSimpleName());}
            }).setNeutralButton("Downloader", (dialog,which)->
                sendToSpecialistDownloader(url))
              .setNegativeButton("Cancel", null).show();
    }
    private void sendToSpecialistDownloader(String url){
        // This explicitly delegates B06: no Downloader extraction, segmented
        // transfer or retry engine runs inside the Control Browser process.
        notice("Checking signed Downloader capability");
        new Thread(()->{
            try{
                JSONObject request=new JSONObject()
                    .put("intent","download")
                    .put("request_id","browser-"+UUID.randomUUID().toString())
                    .put("payload",new JSONObject().put("url",url));
                JSONObject receipt=AppIntentFastPath.route(
                    getApplicationContext(),request);
                runOnUiThread(()->{
                    if(receipt.optBoolean("routed",false)){
                        String state=receipt.optString("status","outcome_unknown");
                        notice("Downloader operation: "+state);
                    }else{
                        notice("No approved signed Downloader action: "+
                            receipt.optString("status","unavailable"));
                    }
                });
            }catch(Exception error){
                runOnUiThread(()->notice("Downloader handoff unavailable: "+
                    error.getClass().getSimpleName()));
            }
        },"asterion-browser-signed-downloader-handoff").start();
    }
    private void rememberDownload(long id,String host){
        try{
            JSONArray previous=new JSONArray(browserPrefs.getString("downloads","[]"));
            JSONArray next=new JSONArray();
            next.put(new JSONObject().put("id",id).put("host",host)
                .put("queued_ms",System.currentTimeMillis()));
            for(int i=0;i<previous.length()&&next.length()<40;i++){
                JSONObject item=previous.optJSONObject(i);
                if(item!=null&&item.optLong("id",-1)!=id)next.put(item);
            }
            browserPrefs.edit().putString("downloads",next.toString()).apply();
        }catch(Exception ignored){}
    }
    private void showDownloadProgress(){
        DownloadManager manager=(DownloadManager)getSystemService(DOWNLOAD_SERVICE);
        if(manager==null){notice("Android Download Manager unavailable");return;}
        LinearLayout pane=DesignSystem.vertical(this);
        pane.setPadding(dp(18),dp(16),dp(18),dp(14));
        TextView info=label("Checking Android Downloads...",12,DesignSystem.TEXT,false);
        add(pane,info);
        AlertDialog dialog=new AlertDialog.Builder(this)
            .setTitle("Browser downloads")
            .setView(pane)
            .setNeutralButton("System Downloads",(d,w)->{
                try{startActivity(new Intent(DownloadManager.ACTION_VIEW_DOWNLOADS));}
                catch(Exception error){notice("Android Downloads unavailable");}
            })
            .setPositiveButton("Close",null).create();
        Handler updater=new Handler(Looper.getMainLooper());
        final Runnable[] runner=new Runnable[1];
        runner[0]=()->{
            if(!dialog.isShowing())return;
            try{
                JSONArray saved=new JSONArray(browserPrefs.getString("downloads","[]"));
                List<Long> ids=new ArrayList<>();
                List<String> hosts=new ArrayList<>();
                for(int i=0;i<saved.length()&&i<40;i++){
                    JSONObject entry=saved.optJSONObject(i);
                    if(entry!=null&&entry.optLong("id",0)>0){
                        ids.add(entry.optLong("id"));
                        hosts.add(entry.optString("host","Download"));
                    }
                }
                if(ids.isEmpty()){info.setText("No browser downloads queued.");}
                else{
                    long[] filters=new long[ids.size()];
                    for(int i=0;i<ids.size();i++)filters[i]=ids.get(i);
                    StringBuilder rows=new StringBuilder();
                    int displayed=0;
                    try(Cursor cursor=manager.query(
                            new DownloadManager.Query().setFilterById(filters))){
                        if(cursor!=null)while(cursor.moveToNext()){
                            long id=cursor.getLong(cursor.getColumnIndexOrThrow(
                                DownloadManager.COLUMN_ID));
                            int ix=ids.indexOf(id);
                            if(ix<0)continue;
                            int status=cursor.getInt(cursor.getColumnIndexOrThrow(
                                DownloadManager.COLUMN_STATUS));
                            long received=cursor.getLong(cursor.getColumnIndexOrThrow(
                                DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR));
                            long total=cursor.getLong(cursor.getColumnIndexOrThrow(
                                DownloadManager.COLUMN_TOTAL_SIZE_BYTES));
                            String state=status==DownloadManager.STATUS_SUCCESSFUL?"Completed":
                                status==DownloadManager.STATUS_FAILED?"Failed":
                                status==DownloadManager.STATUS_RUNNING?"Downloading":
                                status==DownloadManager.STATUS_PAUSED?"Paused":"Pending";
                            if(rows.length()>0)rows.append("\n\n");
                            rows.append(hosts.get(ix)).append(" • ").append(state);
                            if(total>0){
                                rows.append("\n").append(received/1024).append(" / ")
                                    .append(total/1024).append(" KB");
                                if(status==DownloadManager.STATUS_RUNNING)
                                    rows.append(" • ").append(received*100/total).append("%");
                            }
                            displayed++;
                        }
                    }
                    if(displayed==0)rows.append("No matching Android download receipts.");
                    info.setText(rows.toString());
                }
            }catch(Exception failure){info.setText("Android download status unavailable: "+
                failure.getClass().getSimpleName());}
            updater.postDelayed(runner[0],1100);
        };
        dialog.setOnDismissListener(d->updater.removeCallbacks(runner[0]));
        dialog.show();
        updater.post(runner[0]);
    }

    private void extractVisiblePage() {
        BrowserTab tab=current();
        if(tab==null)return;
        String js="(function(){return JSON.stringify({url:location.href,title:document.title,"+
            "text:document.body?document.body.innerText.slice(0,32000):''," +
            "captured_utc:new Date().toISOString(),method:'visible_dom_text'});})()";
        tab.web.evaluateJavascript(js, encoded -> {
            try {
                String json=new JSONArray("["+encoded+"]").getString(0);
                JSONObject record=new JSONObject(json);
                String text=record.optString("text","");
                if(text.isBlank()){notice("This page has no extractable visible text");return;}
                byte[] digest=MessageDigest.getInstance("SHA-256").digest(
                    text.getBytes(StandardCharsets.UTF_8));
                StringBuilder hash=new StringBuilder();
                for(byte b:digest)hash.append(String.format("%02x",b & 255));
                record.put("content_sha256",hash.toString());
                String preview=text.substring(0,Math.min(3500,text.length()));
                new AlertDialog.Builder(this).setTitle(record.optString("title","Page text"))
                    .setMessage(preview+"\n\n"+text.length()+" characters • DOM extraction\n"+
                        "SHA-256: "+hash)
                    .setPositiveButton("Copy text",(d,w)->copy("Page text",text))
                    .setNeutralButton("Copy evidence",(d,w)->copy("Page evidence",record.toString()))
                    .setNegativeButton("Close",null).show();
            }catch(Exception err){notice("Page extraction unavailable: "+err.getClass().getSimpleName());}
        });
    }
    /** Persist tab paths without query strings that can contain login tokens. */
    private String providerName(){
        String name=browserPrefs.getString("search_provider","Google");
        switch(name){
            case "Brave":case "Bing":case "DuckDuckGo":case "Google":return name;
            default:return "Google";
        }
    }
    private String searchPrefix(){
        switch(providerName()){
            case "Brave":return "https://search.brave.com/search?q=";
            case "Bing":return "https://www.bing.com/search?q=";
            case "DuckDuckGo":return "https://duckduckgo.com/?q=";
            default:return "https://www.google.com/search?q=";
        }
    }
    private void chooseSearchProvider(){
        final String[] names={"Google","Brave","Bing","DuckDuckGo"};
        new AlertDialog.Builder(this).setTitle("Search engine")
            .setSingleChoiceItems(names,java.util.Arrays.asList(names)
                .indexOf(providerName()),(dialog,which)->{
                if(which<0||which>=names.length)return;
                browserPrefs.edit().putString("search_provider",names[which]).apply();
                dialog.dismiss();
                refreshToolbar();
                if(current()!=null&&START.equals(current().pageUrl))showTab(active);
            }).setNegativeButton("Cancel",null).show();
    }
    private void showBrowserMenu(){
        String[] actions={
            "Home","Search engine • "+providerName(),
            "Shields and trackers","Encrypted vault",
            "Bookmarks and history","Extract page evidence",
            "Android downloads","Desktop site"};
        new AlertDialog.Builder(this).setTitle("Asterion Browser")
            .setItems(actions,(d,choice)->{
                switch(choice){
                    case 0:navigate("");break;
                    case 1:chooseSearchProvider();break;
                    case 2:showProtectionDetails();break;
                    case 3:showVault();break;
                    case 4:showSavedPages();break;
                    case 5:extractVisiblePage();break;
                    case 6:showDownloadProgress();break;
                    case 7:{
                        BrowserTab t=current();
                        if(t==null)break;
                        WebSettings settings=t.web.getSettings();
                        boolean desktop=!settings.getUseWideViewPort();
                        settings.setUseWideViewPort(desktop);
                        settings.setLoadWithOverviewMode(desktop);
                        notice(desktop?"Desktop viewport enabled":"Mobile viewport enabled");
                        if(!START.equals(t.pageUrl))t.web.reload();
                        break;
                    }
                }
            }).setNegativeButton("Close",null).show();
    }
    private View createNativeHome(){
        ScrollView scroll=new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(DesignSystem.BG);
        LinearLayout body=DesignSystem.vertical(this);
        body.setPadding(dp(24),dp(35),dp(24),dp(22));
        scroll.addView(body);
        LinearLayout hero=DesignSystem.vertical(this);
        hero.setPadding(dp(25),dp(30),dp(25),dp(28));
        hero.setBackground(DesignSystem.gradient(this,0xFF33245A,0xFF15374F,26));
        DesignSystem.AsterionMark mark=new DesignSystem.AsterionMark(this);
        hero.addView(mark,new LinearLayout.LayoutParams(dp(54),dp(54)));
        TextView kicker=label("ASTERION  /  THE OPEN WEB",11,0xFFA4EDE7,true);
        kicker.setLetterSpacing(.10f);
        kicker.setPadding(0,dp(17),0,dp(9));
        add(hero,kicker);
        TextView title=label("Explore without limits.",26,DesignSystem.TEXT,true);
        add(hero,title);
        TextView subtitle=label(
            "One place for research, browsing, bookmarks and downloads. Private shields stay in your control.",
            13,0xFFD0D8EA,false);
        subtitle.setPadding(0,dp(12),0,dp(19));
        add(hero,subtitle);
        TextView search=control("Search the web",()->{
            address.requestFocus();
            android.view.inputmethod.InputMethodManager keyboard=
                (android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            if(keyboard!=null)keyboard.showSoftInput(address,
                android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);
        });
        search.setBackground(DesignSystem.gradient(this,0xFF7862E8,0xFF288DC5,16));
        add(hero,search);
        TextView provider=label("Search provider: "+providerName()+"  •  Change",12,
            DesignSystem.TEXT,true);
        provider.setPadding(0,dp(17),0,0);
        provider.setOnClickListener(v->chooseSearchProvider());
        add(hero,provider);
        add(body,hero);
        TextView library=label("YOUR WORKSPACE",11,DesignSystem.TEAL,true);
        library.setLetterSpacing(.10f);
        library.setPadding(0,dp(29),0,dp(13));
        add(body,library);
        LinearLayout cards=DesignSystem.vertical(this);
        cards.setPadding(dp(16),dp(8),dp(16),dp(12));
        cards.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE,
            DesignSystem.EDGE,20));
        add(cards,control("Bookmarks & history",this::showSavedPages));
        add(cards,control("Private browsing shields",this::showProtectionDetails));
        add(cards,control("Downloads",this::showDownloadProgress));
        add(cards,control("Password vault",this::showVault));
        add(body,cards);
        TextView foot=label("No provider account or custom home server required.",11,
            DesignSystem.MUTED,false);
        foot.setPadding(0,dp(22),0,0);
        add(body,foot);
        return scroll;
    }

    private static String safeSessionUrl(String value){
        try{
            Uri url=Uri.parse(value);
            String scheme=url.getScheme();
            if(!"https".equalsIgnoreCase(scheme)&&
               !"http".equalsIgnoreCase(scheme))return START;
            Uri.Builder builder=url.buildUpon().clearQuery().fragment(null);
            String result=builder.build().toString();
            return result.length()>1200?START:result;
        }catch(Exception failure){return START;}
    }
    private void persistTabs(){
        JSONArray saved=new JSONArray();
        for(BrowserTab tab:tabs)
            saved.put(safeSessionUrl(tab.web.getUrl()==null?START:tab.web.getUrl()));
        browserPrefs.edit().putString("tabs",saved.toString())
            .putInt("active",active).apply();
    }
    private void restorePersistedTabs(){
        try{
            JSONArray stored=new JSONArray(browserPrefs.getString("tabs","[]"));
            for(int i=0;i<stored.length()&&tabs.size()<MAX_TABS;i++){
                String url=safeAddress(stored.optString(i,START));
                addTab(url);
            }
            if(!tabs.isEmpty())
                showTab(Math.max(0,Math.min(tabs.size()-1,
                    browserPrefs.getInt("active",0))));
        }catch(Exception ignored){}
    }
    private void rememberPage(String url,String title){
        String safe=safeSessionUrl(url);
        if(safe.equals(START)||safe.isEmpty())return;
        try{
            JSONArray old=new JSONArray(browserPrefs.getString("history","[]"));
            JSONArray now=new JSONArray();
            JSONObject fresh=new JSONObject().put("url",safe)
                .put("title",title).put("at",System.currentTimeMillis());
            now.put(fresh);
            for(int i=0;i<old.length()&&now.length()<180;i++){
                JSONObject entry=old.optJSONObject(i);
                if(entry!=null&&!safe.equals(entry.optString("url")))now.put(entry);
            }
            browserPrefs.edit().putString("history",now.toString()).apply();
        }catch(Exception ignored){}
    }
    private void bookmarkCurrent(){
        BrowserTab tab=current();
        if(tab==null)return;
        String url=safeSessionUrl(tab.web.getUrl());
        if(url.equals(START))return;
        try{
            JSONArray previous=new JSONArray(browserPrefs.getString("bookmarks","[]"));
            JSONArray next=new JSONArray();
            next.put(new JSONObject().put("url",url).put("title",tab.title));
            for(int i=0;i<previous.length()&&next.length()<100;i++){
                JSONObject e=previous.optJSONObject(i);
                if(e!=null&&!url.equals(e.optString("url")))next.put(e);
            }
            browserPrefs.edit().putString("bookmarks",next.toString()).apply();
            notice("Bookmark saved");
        }catch(Exception error){notice("Unable to save bookmark");}
    }
    private void showSavedPages(){
        String[] choices={"Open bookmarks","Open history","Bookmark this page",
            "Android downloads","Clear browsing history"};
        new AlertDialog.Builder(this).setTitle("Browser library")
            .setItems(choices,(d,which)->{
                if(which==0)showEntryList("bookmarks","Saved bookmarks");
                else if(which==1)showEntryList("history","Recent history");
                else if(which==2)bookmarkCurrent();
                else if(which==3){
                    showDownloadProgress();
                }else if(which==4){
                    new AlertDialog.Builder(this).setTitle("Clear browser history?")
                        .setMessage("This clears only Asterion Browser's navigation history. Saved bookmarks and signed Control sessions are preserved.")
                        .setPositiveButton("Clear",(ok,n)->browserPrefs.edit()
                            .remove("history").apply())
                        .setNegativeButton("Cancel",null).show();
                }
            }).show();
    }
    private void showEntryList(String key,String heading){
        try{
            JSONArray entries=new JSONArray(browserPrefs.getString(key,"[]"));
            int n=Math.min(50,entries.length());
            if(n==0){notice("No saved pages");return;}
            String[] titles=new String[n];
            String[] urls=new String[n];
            for(int i=0;i<n;i++){
                JSONObject entry=entries.optJSONObject(i);
                urls[i]=entry==null?START:entry.optString("url",START);
                titles[i]=entry==null?"Page":entry.optString("title","Page");
                if(titles[i].isEmpty())titles[i]=urls[i];
                if(titles[i].length()>65)titles[i]=titles[i].substring(0,65)+"…";
            }
            new AlertDialog.Builder(this).setTitle(heading)
                .setItems(titles,(dialog,which)->{
                    BrowserTab tab=current();
                    if(tab!=null)tab.web.loadUrl(safeAddress(urls[which]));
                }).setNegativeButton("Close",null).show();
        }catch(Exception ignored){notice("Saved pages unavailable");}
    }
    private void showProtectionDetails(){
        BrowserTab tab=current();
        String url=tab==null?START:tab.web.getUrl();
        if(url==null)url=START;
        final String currentUrl=url;
        int blocked=tab==null?0:tab.blocked.get();
        int popups=tab==null?0:tab.popups.get();
        boolean siteAllowed=protection.isAllowedSite(currentUrl);
        String details="Status: "+(protection.isEnabled()?"Enabled":"Disabled")+
            "\nReal supported filter domains: "+protection.domainRules()+
            "\nOfficial subscriptions loaded: "+protection.subscriptionsLoaded()+
            "\nRequests blocked on this tab: "+blocked+
            "\nPopups blocked: "+popups+
            "\nThis site excepted: "+siteAllowed+
            "\nLast updated: "+(protection.lastUpdated()>0?
                  new java.util.Date(protection.lastUpdated()).toString():"Not downloaded")+
            "\n\nEasyList and EasyPrivacy resource rules apply only where Android WebView exposes an interceptable request. In-stream and opaque service-worker advertising may remain.";
        final String[] options={"Update real filters",
            protection.isEnabled()?"Turn shield off":"Turn shield on",
            siteAllowed?"Protect this site":"Allow this site"};
        new AlertDialog.Builder(this).setTitle("Browser shields")
            .setMessage(details).setPositiveButton("Settings",(dialog,which)->
                new AlertDialog.Builder(this).setTitle("Shields")
                    .setItems(options,(d,index)->{
                        if(index==0){
                            protection.refresh(true,(ok,msg)->{
                                notice(msg);
                                if(ok&&current()!=null)current().web.reload();
                                refreshToolbar();
                            });
                            notice("Refreshing original filter lists");
                        }else if(index==1){
                            protection.setEnabled(!protection.isEnabled());
                            // Remove previously injected CSS on disable and
                            // apply the freshly selected shield on enable.
                            BrowserTab selected=current();
                            if(selected!=null)selected.web.reload();
                            refreshToolbar();
                        }else{
                            try{
                                protection.allowSite(currentUrl,!siteAllowed);
                                BrowserTab selected=current();
                                if(selected!=null)selected.web.reload();
                            }catch(Exception error){notice("Site exception unavailable");}
                        }
                    }).show())
            .setNegativeButton("Close",null).show();
    }

    /** Password vault is a purely local native screen, never AI or JavaScript. */
    private void showVault(){
        BrowserTab tab=current();
        if(tab==null){notice("Open an HTTPS website first");return;}
        String url=tab.web.getUrl();
        final String origin;
        try{origin=ControlPasswordVault.exactOrigin(url);}
        catch(Exception error){
            new AlertDialog.Builder(this).setTitle("Encrypted password vault")
                .setMessage("Passwords can only be saved and filled for a verified HTTPS origin. Open a secure login page.")
                .setPositiveButton("Close",null).show();
            return;
        }
        try{
            List<ControlPasswordVault.Entry> accounts=
                ControlPasswordVault.accounts(this,origin);
            String[] actions=new String[accounts.size()+2];
            for(int i=0;i<accounts.size();i++)
                actions[i]="Saved account • "+accounts.get(i).username;
            actions[accounts.size()]="Add HTTPS login";
            actions[accounts.size()+1]="Enable Android Autofill";
            new AlertDialog.Builder(this).setTitle("Encrypted Vault • "+origin)
                .setMessage("One Android Keystore-encrypted vault. Existing authorized website cookies are kept. Passwords are never sent to AI, Windows or logs.")
                .setItems(actions,(d,choice)->{
                    if(choice<accounts.size()){
                        ControlPasswordVault.Entry item=accounts.get(choice);
                        new AlertDialog.Builder(this).setTitle("Remove saved account?")
                            .setMessage("Delete the saved login for "+item.username+
                                " on "+origin+"? This does not sign out an existing website session.")
                            .setPositiveButton("Remove",(confirm,which)->{
                                try{
                                    if(ControlPasswordVault.delete(this,origin,item.username))
                                        notice("Account removed from encrypted vault");
                                }catch(Exception failure){notice("Unable to delete this login");}
                            })
                            .setNegativeButton("Cancel",null).show();
                    }else if(choice==accounts.size())addVaultAccount(origin);
                    else enableSystemAutofill();
                }).setNegativeButton("Close",null).show();
        }catch(Exception failure){
            notice("Encrypted vault unavailable: "+failure.getClass().getSimpleName());
        }
    }
    private void addVaultAccount(String origin){
        LinearLayout form=DesignSystem.vertical(this);
        form.setPadding(dp(24),dp(8),dp(24),dp(8));
        EditText username=new EditText(this);
        username.setSingleLine(true);
        username.setHint("Username or email");
        username.setInputType(InputType.TYPE_CLASS_TEXT |
            InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        add(form,username);
        EditText password=new EditText(this);
        password.setSingleLine(true);
        password.setHint("Password");
        password.setInputType(InputType.TYPE_CLASS_TEXT |
            InputType.TYPE_TEXT_VARIATION_PASSWORD);
        add(form,password);
        new AlertDialog.Builder(this).setTitle("Save login • "+origin)
            .setView(form)
            .setPositiveButton("Save",(d,which)->{
                try{
                    ControlPasswordVault.save(this,origin,
                        username.getText().toString(),password.getText().toString());
                    notice("Encrypted login saved for this site");
                }catch(Exception failure){
                    notice("Unable to save login: "+failure.getClass().getSimpleName());
                }finally{
                    password.setText("");
                    username.setText("");
                }
            }).setNegativeButton("Cancel",(d,which)->{
                password.setText("");
            }).show();
    }
    private void enableSystemAutofill(){
        try{
            Intent request=new Intent(Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE);
            request.setData(Uri.parse("package:"+getPackageName()));
            startActivity(request);
        }catch(Exception error){
            notice("Android Autofill settings are unavailable on this device");
        }
    }

    private void copy(String label,String value) {
        ClipboardManager cb=(ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE);
        if(cb!=null){cb.setPrimaryClip(ClipData.newPlainText(label,value));notice("Copied "+label);}
    }
    @Override public void onBackPressed() {
        BrowserTab tab=current();
        if(tab!=null&&tab.web.canGoBack())tab.web.goBack();
        else super.onBackPressed();
    }
    @Override protected void onStart(){
        super.onStart();
        activeBrowser=this;
    }
    @Override protected void onStop() {
        if(activeBrowser==this)activeBrowser=null;
        persistTabs();
        CookieManager.getInstance().flush();
        super.onStop();
    }
    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        ArrayList<String> urls=new ArrayList<>();
        for(BrowserTab tab:tabs) urls.add(tab.web.getUrl()==null?START:tab.web.getUrl());
        out.putStringArrayList("urls",urls);
        out.putInt("current",active);
    }
    @Override protected void onDestroy() {
        for(BrowserTab tab:tabs) {
            if(tab.web.getParent()!=null)
                ((android.view.ViewGroup)tab.web.getParent()).removeView(tab.web);
            tab.web.stopLoading();
            tab.web.destroy();
        }
        tabs.clear();
        super.onDestroy();
    }
    private static final class BrowserTab {
        final WebView web;
        volatile String pageUrl="";
        final AtomicInteger blocked=new AtomicInteger(0);
        final AtomicInteger popups=new AtomicInteger(0);
        String title="New tab";
        BrowserTab(WebView view){web=view;}
    }
}
