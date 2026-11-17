package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.net.http.SslError;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.text.InputType;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
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

/** Asterion Browser: actual on-device multi-tab WebView browser, not a crawler mock.
 *
 * Runs in a dedicated Android process with its own WebView data-directory
 * suffix, isolated from Control's authenticated Windows dashboard WebView.
 * No JavaScript bridge, shell integration, silent downloads or credential export.
 * Signed cross-app browser automation, richer profiles and PC crawler are separate
 * future capabilities; this Activity does not claim those are already delivered.
 */
public final class BrowserActivity extends Activity {
    private static final int MAX_TABS = 8;
    private static final String START = "https://duckduckgo.com/";
    private final List<BrowserTab> tabs = new ArrayList<>();
    private LinearLayout root, tabStrip;
    private FrameLayout viewport;
    private EditText address;
    private TextView status, counter, back, forward;
    private ProgressBar progress;
    private int active = -1;

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
        super.onCreate(saved);
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
        counter = control("0 tabs", this::newTab);
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
        tool(nav, "Extract", this::extractVisiblePage);
        tool(nav, "+ Tab", this::newTab);
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
        if(tabs.isEmpty()) newTab();
    }

    private static String safeAddress(String raw) {
        String value = raw == null ? "" : raw.trim();
        if(value.isEmpty()) return START;
        // Reject WebView-local and privilege-bearing schemes, including javascript:, file:, data:.
        if(value.matches("(?i)^[a-z][a-z0-9+.-]*:.*") &&
                !value.startsWith("https://") && !value.startsWith("http://")) return START;
        if(!value.startsWith("https://") && !value.startsWith("http://")) {
            if(value.contains(" ") || !value.contains(".")) {
                return "https://duckduckgo.com/?q=" +
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
        view.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView web, WebResourceRequest request) {
                String scheme = request.getUrl().getScheme();
                return scheme == null || (!scheme.equalsIgnoreCase("http") &&
                        !scheme.equalsIgnoreCase("https"));
            }
            @Override public void onReceivedSslError(WebView web, SslErrorHandler handler, SslError error) {
                handler.cancel();
                if(current()==tab) notice("Certificate verification failed; page blocked");
            }
            @Override public void onPageFinished(WebView web, String url) {
                if(current()==tab) refreshToolbar();
                refreshTabs();
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
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
            viewport.removeView(before.web);
            before.web.onPause();
        }
        active=index;
        BrowserTab selected=current();
        if(selected.web.getParent()!=null)
            ((android.view.ViewGroup)selected.web.getParent()).removeView(selected.web);
        viewport.addView(selected.web, new FrameLayout.LayoutParams(-1,-1));
        selected.web.onResume();
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
        if(url!=null && !address.hasFocus()) address.setText(url);
        back.setEnabled(tab.web.canGoBack());
        forward.setEnabled(tab.web.canGoForward());
        back.setAlpha(tab.web.canGoBack()?1f:0.4f);
        forward.setAlpha(tab.web.canGoForward()?1f:0.4f);
        if(url!=null) {
            try { status.setText("Browsing • " + Uri.parse(url).getHost()); }
            catch(Exception ignored) { status.setText("Browsing"); }
        }
    }
    private void navigate(String value) {
        BrowserTab tab=current();
        if(tab==null) return;
        String url=safeAddress(value);
        tab.web.loadUrl(url);
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
                    manager.enqueue(req);
                    notice("Download queued in Android Downloads");
                }catch(Exception e){notice("Download failed: "+e.getClass().getSimpleName());}
            }).setNegativeButton("Cancel", null).show();
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
                    .setNeutralButton("Copy evidence",(d,w)->copy("Page evidence",record.toString(2)))
                    .setNegativeButton("Close",null).show();
            }catch(Exception err){notice("Page extraction unavailable: "+err.getClass().getSimpleName());}
        });
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
        String title="New tab";
        BrowserTab(WebView view){web=view;}
    }
}
