package com.asterion.control;

import android.app.Activity;
import android.app.KeyguardManager;
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
 * No JavaScript bridge, shell integration, silent downloads or remote credential export.
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
                if(tab==null||tab.privateProfile!=null||tab.web.getParent()!=browser.viewport||!BrowserNavigationPolicy.sameDocument(tab.committedUrl,tab.web.getUrl())||tab.web.getCertificate()==null)return;
                value[0]=ControlPasswordVault.exactOrigin(tab.committedUrl);
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
    private LinearLayout root, navigation;
    private static boolean webDirectoryConfigured;
    private FrameLayout viewport;
    private EditText address;
    private TextView status, counter, site;
    private static final int SITE_PERMISSION_CODE=4107;
    private static final int VAULT_AUTH_CODE=4108;
    private static final int VAULT_EXPORT_FILE=4110,VAULT_IMPORT_FILE=4111,VAULT_ARCHIVE_AUTH=4112;
    private Uri pendingArchive;
    private boolean archiveExport,archiveBusy;
    private final java.util.concurrent.ExecutorService vaultArchiveIo=java.util.concurrent.Executors.newSingleThreadExecutor();
    private Integer pendingVaultPolicy;
    private String pendingVaultOrigin;
    private SiteRequest pendingSiteRequest, androidPermissionInFlight;
    private AlertDialog siteRequestDialog;
    private View back, forward;
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
    private View iconButton(String kind,String description,Runnable action){
        FrameLayout target=new FrameLayout(this);
        target.setMinimumWidth(dp(48));target.setMinimumHeight(dp(48));
        DesignSystem.clickable(target,this,DesignSystem.SURFACE,0,12);
        target.setContentDescription(description);target.setFocusable(true);
        View icon=new BrowserIcon(kind);
        target.addView(icon,new FrameLayout.LayoutParams(dp(23),dp(23),Gravity.CENTER));
        target.setOnClickListener(v->action.run());return target;
    }
    private View navButton(String kind,String description,Runnable action){
        View target=iconButton(kind,description,action);
        navigation.addView(target,new LinearLayout.LayoutParams(0,dp(48),1));return target;
    }
    private final class BrowserIcon extends View {
        private final String kind;
        private final android.graphics.Paint p=new android.graphics.Paint(3);
        BrowserIcon(String kind){super(BrowserActivity.this);this.kind=kind;}
        private void line(android.graphics.Canvas c,float x,float y,float a,float b){c.drawLine(x,y,a,b,p);}
        @Override protected void onDraw(android.graphics.Canvas c){
            super.onDraw(c);c.save();c.scale(getWidth()/24f,getHeight()/24f);
            p.setColor(DesignSystem.TEXT);p.setStyle(android.graphics.Paint.Style.STROKE);
            p.setStrokeWidth(1.8f);p.setStrokeCap(android.graphics.Paint.Cap.ROUND);p.setStrokeJoin(android.graphics.Paint.Join.ROUND);
            switch(kind){
                case "back":line(c,19,12,5,12);line(c,5,12,11,6);line(c,5,12,11,18);break;
                case "forward":case "go":line(c,5,12,19,12);line(c,19,12,13,6);line(c,19,12,13,18);break;
                case "home":line(c,3,11,12,3);line(c,12,3,21,11);line(c,5,10,5,21);line(c,19,10,19,21);line(c,5,21,19,21);c.drawRect(10,14,14,21,p);break;
                case "reload":c.drawArc(4,4,20,20,-45,300,false,p);line(c,20,3,20,9);line(c,14,9,20,9);break;
                case "download":line(c,12,3,12,16);line(c,7,11,12,16);line(c,12,16,17,11);line(c,4,20,20,20);break;
                case "menu":line(c,4,6,20,6);line(c,4,12,20,12);line(c,4,18,20,18);break;
                default:c.drawCircle(12,12,9,p);line(c,12,10,12,17);c.drawCircle(12,6.5f,.5f,p);
            }c.restore();
        }
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);DesignSystem.configure(this);
        protection=new BrowserProtection(this);
        browserPrefs=getSharedPreferences("asterion_browser_session_v1",Context.MODE_PRIVATE);
        protection.refresh(false,(updated,reason)->{
            if(!isFinishing()&&status!=null)refreshToolbar();
        });
        // The WebView suffix is process-global; recreating this Activity must not reset it.
        if(!webDirectoryConfigured){WebView.setDataDirectorySuffix("asterion_browser");webDirectoryConfigured=true;BrowserPrivateProfiles.cleanPreviousProcess();}
        boolean dark=(getResources().getConfiguration().uiMode &
            android.content.res.Configuration.UI_MODE_NIGHT_MASK)==android.content.res.Configuration.UI_MODE_NIGHT_YES;
        getWindow().setStatusBarColor(Color.TRANSPARENT);getWindow().setNavigationBarColor(Color.TRANSPARENT);
        getWindow().setSoftInputMode(android.view.WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        root=DesignSystem.vertical(this);root.setBackgroundColor(DesignSystem.BG);root.setFocusableInTouchMode(true);
        if(Build.VERSION.SDK_INT>=30){
            getWindow().setDecorFitsSystemWindows(false);
            android.view.WindowInsetsController controller=getWindow().getInsetsController();
            if(controller!=null){
                int flags=android.view.WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS |
                    android.view.WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                controller.setSystemBarsAppearance(dark?0:flags,flags);
            }
            root.setOnApplyWindowInsetsListener((v,insets)->{
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|
                    android.view.WindowInsets.Type.displayCutout());
                android.graphics.Insets ime=insets.getInsets(android.view.WindowInsets.Type.ime());
                root.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,ime.bottom));
                if(navigation!=null)navigation.setVisibility(insets.isVisible(android.view.WindowInsets.Type.ime())?View.GONE:View.VISIBLE);
                return insets;
            });
        }else{
            getWindow().setStatusBarColor(DesignSystem.BG);getWindow().setNavigationBarColor(DesignSystem.BG);
            root.setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        }
        setContentView(root);
        LinearLayout search=DesignSystem.horizontal(this);search.setPadding(dp(8),dp(4),dp(8),dp(4));
        search.setBackgroundColor(DesignSystem.SURFACE);
        site=control("Site",this::showSiteInfo);site.setMinWidth(dp(48));site.setPadding(dp(5),0,dp(5),0);
        search.addView(site,new LinearLayout.LayoutParams(dp(54),dp(48)));
        address=new EditText(this);address.setSingleLine(true);address.setTextSize(15);
        address.setSaveEnabled(false);address.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        address.setTextColor(DesignSystem.TEXT);address.setHintTextColor(DesignSystem.MUTED);
        address.setHint("Search with "+providerName()+" or enter URL");address.setContentDescription("Address and search");
        address.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_URI);
        address.setImeOptions(EditorInfo.IME_ACTION_GO);address.setPadding(dp(12),0,dp(12),0);address.setSelectAllOnFocus(true);
        address.setBackground(DesignSystem.shape(this,DesignSystem.SURFACE2,DesignSystem.EDGE,16));
        address.setOnEditorActionListener((view,action,event)->{
            if(action==EditorInfo.IME_ACTION_GO||(event!=null&&event.getKeyCode()==KeyEvent.KEYCODE_ENTER&&event.getAction()==KeyEvent.ACTION_DOWN)){
                navigate(address.getText().toString());return true;
            }return false;
        });
        LinearLayout.LayoutParams addressLp=new LinearLayout.LayoutParams(0,dp(48),1);
        addressLp.leftMargin=dp(4);search.addView(address,addressLp);
        search.addView(iconButton("go","Open address or search",()->navigate(address.getText().toString())),new LinearLayout.LayoutParams(dp(48),dp(48)));
        add(root,search);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);progress.setVisibility(View.GONE);
        root.addView(progress,new LinearLayout.LayoutParams(-1,dp(2)));
        viewport=new FrameLayout(this);root.addView(viewport,new LinearLayout.LayoutParams(-1,0,1));
        navigation=DesignSystem.horizontal(this);navigation.setBackgroundColor(DesignSystem.SURFACE);
        back=navButton("back","Back",()->{BrowserTab t=current();if(t!=null&&t.web.canGoBack())t.web.goBack();});
        forward=navButton("forward","Forward",()->{BrowserTab t=current();if(t!=null&&t.web.canGoForward())t.web.goForward();});
        navButton("home","Home",()->navigate(""));
        navButton("reload","Reload",()->{BrowserTab t=current();if(t!=null&&!START.equals(t.pageUrl))t.web.reload();});
        navButton("download","Downloads",this::showDownloadProgress);
        counter=control("1",this::showTabSwitcher);counter.setTextSize(16);counter.setPadding(0,0,0,0);
        navigation.addView(counter,new LinearLayout.LayoutParams(0,dp(48),1));
        navButton("menu","Browser menu",this::showBrowserMenu);
        status=label("",11,DesignSystem.MUTED,false);
        add(root,navigation);root.requestFocus();root.requestApplyInsets();

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
        return BrowserNavigationPolicy.resolve(raw,searchPrefix());
    }

    private BrowserTab current() {
        return active >= 0 && active < tabs.size() ? tabs.get(active) : null;
    }
    private void newTab() {
        if(tabs.size() >= MAX_TABS) { notice("Close a tab before opening another"); return; }
        addTab(START);
        showTab(tabs.size()-1);
    }
    private void newPrivateTab(){
        if(tabs.size()>=MAX_TABS){notice("Close a tab first");return;}
        if(!BrowserPrivateProfiles.supported()){notice("This WebView cannot isolate and clear private profiles");return;}
        try{addTab(START,true,BrowserPrivateProfiles.newName());showTab(tabs.size()-1);}
        catch(RuntimeException failure){notice("Private profile could not be opened");}
    }
    private void addTab(String url){addTab(url,true,null);}
    private void addTab(String url,boolean load,String privateProfile) {
        WebView view = new WebView(this);
        if(privateProfile!=null){
            try{BrowserPrivateProfiles.attach(view,privateProfile);}
            catch(RuntimeException failure){view.destroy();throw failure;}
            view.setSaveEnabled(false);view.setSaveFromParentEnabled(false);
            view.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        }
        view.setBackgroundColor(Color.WHITE);
        WebSettings s = view.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setGeolocationEnabled(privateProfile==null);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setSupportMultipleWindows(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        if(Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        BrowserTab tab = new BrowserTab(view,privateProfile);
        tab.pageUrl=url;
        view.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView web, WebResourceRequest request) {
                if(TorRoutePolicy.onionHost(request.getUrl().toString())){
                    String onion=TorRoutePolicy.onionAddress(request.getUrl().toString());
                    if(onion!=null&&request.isForMainFrame()&&request.hasGesture()&&current()==tab)openEmbeddedTor(onion);
                    return true;
                }
                if(!BrowserNavigationPolicy.isWeb(request.getUrl().toString()))return true;
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
                if(TorRoutePolicy.onionHost(request.getUrl().toString()))return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));
                WebResourceResponse denied=protection.intercept(request,tab.pageUrl);
                if(denied!=null)tab.blocked.incrementAndGet();
                return denied;
            }
            @Override public void onPageStarted(WebView web,String url,
                    android.graphics.Bitmap icon) {
                if(!tabs.contains(tab))return;
                if(pendingSiteRequest!=null&&pendingSiteRequest.tab==tab)finishSiteRequest(false);
                tab.siteGrants.clear();
                tab.committedUrl=null;
                tab.pageUrl=url;
                tab.blocked.set(0);
                if(current()==tab){
                    if(!START.equals(url)&&tab.web.getParent()!=viewport)showTab(active);
                    else if(START.equals(url)&&tab.web.getParent()==viewport)showTab(active);
                    refreshToolbar();
                }
            }
            @Override public void onReceivedSslError(WebView web, SslErrorHandler handler, SslError error) {
                tab.committedUrl=null;
                handler.cancel();
                if(current()==tab) notice("Certificate verification failed; page blocked");
            }
            @Override public void doUpdateVisitedHistory(WebView web,String url,boolean reload){
                if(!reload&&BrowserNavigationPolicy.sameHttpsOrigin(tab.committedUrl,url)&&url.equals(web.getUrl())){
                    tab.committedUrl=url;tab.pageUrl=url;
                    if(current()==tab)refreshToolbar();persistTabs();
                }
            }
            @Override public void onPageCommitVisible(WebView web,String url){
                if(tabs.contains(tab)&&BrowserNavigationPolicy.isWeb(url)&&url.equals(web.getUrl()))tab.committedUrl=url;
            }
            @Override public void onReceivedError(WebView web,WebResourceRequest request,android.webkit.WebResourceError error){
                if(request.isForMainFrame()){
                    tab.committedUrl=null;
                    if(current()==tab)notice("Page could not load: "+error.getDescription());
                }
            }
            @Override public void onPageFinished(WebView web, String url) {
                if(!tabs.contains(tab)||!url.equals(web.getUrl()))return;
                tab.pageUrl=url;
                protection.applyCosmetic(web,url);
                if(tab.privateProfile==null){CookieManager.getInstance().flush();rememberPage(url,tab.title);}
                if(current()==tab) refreshToolbar();
                refreshTabs();persistTabs();
            }
        });
        view.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView web,boolean isDialog,
                    boolean isUserGesture,android.os.Message resultMsg) {
                if(!BrowserNavigationPolicy.allowPopup(isUserGesture,current()==tab&&tab.web.getParent()==viewport,tabs.size()<MAX_TABS)){
                    tab.popups.incrementAndGet();
                    if(current()==tab)notice("Popup blocked");
                    return false;
                }
                if(!(resultMsg.obj instanceof WebView.WebViewTransport))return false;
                try{addTab(START,false,tab.privateProfile);}catch(RuntimeException failure){notice("New window unavailable");return false;}
                BrowserTab child=tabs.get(tabs.size()-1);
                child.popup=true;
                ((WebView.WebViewTransport)resultMsg.obj).setWebView(child.web);
                resultMsg.sendToTarget();
                showTab(tabs.size()-1);
                return true;
            }
            @Override public void onPermissionRequest(android.webkit.PermissionRequest request){
                runOnUiThread(()->requestMediaPermission(tab,request));
            }
            @Override public void onPermissionRequestCanceled(android.webkit.PermissionRequest request){
                runOnUiThread(()->{if(pendingSiteRequest!=null&&pendingSiteRequest.media==request)finishSiteRequest(false);});
            }
            @Override public void onGeolocationPermissionsShowPrompt(String origin,android.webkit.GeolocationPermissions.Callback callback){
                runOnUiThread(()->requestLocationPermission(tab,origin,callback));
            }
            @Override public void onGeolocationPermissionsHidePrompt(){
                runOnUiThread(()->{if(pendingSiteRequest!=null&&pendingSiteRequest.tab==tab&&pendingSiteRequest.location!=null)finishSiteRequest(false);});
            }
            @Override public void onCloseWindow(WebView web){if(tab.popup&&tabs.contains(tab))closeTab(tabs.indexOf(tab));}
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
        view.setDownloadListener((address,agent,disposition,type,size) -> {
            if(current()==tab&&tab.web.getParent()==viewport)confirmDownload(address,agent,disposition,type,size,tab.privateProfile!=null);
        });
        tabs.add(tab);
        if(load)view.loadUrl(url);
    }
    private void showTab(int index) {
        if(index<0||index>=tabs.size()) return;
        BrowserTab before=current();
        if(before!=null&&before!=tabs.get(index)&&pendingSiteRequest!=null)finishSiteRequest(false);
        if(before!=null) {
            if(before.web.getParent()==viewport)viewport.removeView(before.web);
            before.web.onPause();
        }
        viewport.removeAllViews();
        active=index;
        BrowserTab selected=current();
        if(START.equals(selected.pageUrl)){
            viewport.addView(createNativeHome(),new FrameLayout.LayoutParams(-1,-1));
        }else{
            if(selected.web.getParent()!=null)
                ((android.view.ViewGroup)selected.web.getParent()).removeView(selected.web);
            viewport.addView(selected.web,new FrameLayout.LayoutParams(-1,-1));
            selected.web.onResume();
        }
        refreshToolbar();
        refreshTabs();
        persistTabs();
    }
    private void closeTab(int index) {
        if(index<0||index>=tabs.size()) return;
        BrowserTab old=tabs.get(index);
        if(pendingSiteRequest!=null&&pendingSiteRequest.tab==old)finishSiteRequest(false);
        viewport.removeView(old.web);
        tabs.remove(index);
        old.web.stopLoading();
        old.web.destroy();releasePrivate(old);
        if(tabs.isEmpty()) { active=-1; newTab(); return; }
        if(index<active) active--;
        else if(index==active) active=Math.min(index,tabs.size()-1);
        int selected=active;
        active=-1;
        showTab(selected);
    }
    private void refreshTabs(){
        if(counter!=null){counter.setText(Integer.toString(tabs.size()));counter.setContentDescription(tabs.size()==1?"1 tab":tabs.size()+" tabs");}
    }
    private void showTabSwitcher(){
        LinearLayout list=DesignSystem.vertical(this);list.setPadding(dp(12),dp(8),dp(12),dp(8));
        ScrollView scroll=new ScrollView(this);scroll.addView(list);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(tabs.size()==1?"1 tab":tabs.size()+" tabs")
            .setView(scroll).setPositiveButton("New tab",(d,w)->newTab())
            .setNeutralButton("Private tab",(d,w)->newPrivateTab()).setNegativeButton("Close",null).create();
        for(int i=0;i<tabs.size();i++){
            final int index=i;BrowserTab tab=tabs.get(i);LinearLayout row=DesignSystem.horizontal(this);
            TextView title=label((i==active?"●  ":"")+(tab.privateProfile!=null?"Private · ":"")+tab.title,15,DesignSystem.TEXT,true);
            title.setMaxLines(2);title.setEllipsize(android.text.TextUtils.TruncateAt.END);
            title.setMinHeight(dp(56));title.setGravity(Gravity.CENTER_VERTICAL);title.setPadding(dp(10),0,dp(8),0);
            title.setOnClickListener(v->{dialog.dismiss();showTab(index);});row.addView(title,new LinearLayout.LayoutParams(0,-2,1));
            TextView close=control("×",()->{dialog.dismiss();closeTab(index);showTabSwitcher();});
            close.setContentDescription("Close tab "+(i+1));row.addView(close,new LinearLayout.LayoutParams(dp(48),dp(48)));add(list,row);
        }dialog.show();
    }
    private void showSiteInfo(){
        BrowserTab t=current();String url=t==null?START:t.pageUrl;String scheme=Uri.parse(url).getScheme();
        String origin=START.equals(url)?"Home":("https".equalsIgnoreCase(scheme)?"HTTPS address":"HTTP address (not encrypted)");
        new AlertDialog.Builder(this).setTitle("Site information")
            .setMessage(origin+"\n"+(START.equals(url)?"":url+"\n")+status.getText())
            .setPositiveButton("Shields",(d,w)->showProtectionDetails())
            .setNeutralButton("Permissions",(d,w)->showSitePermissions()).setNegativeButton("Close",null).show();
    }
    private void refreshToolbar() {
        BrowserTab tab=current();
        if(tab==null) return;
        String url=tab.pageUrl;
        address.setHint("Search with "+providerName()+" or enter URL");
        address.setImeOptions(EditorInfo.IME_ACTION_GO|(tab.privateProfile!=null?EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING:0));
        if(url!=null && !address.hasFocus()) address.setText(START.equals(url)?"":url);
        site.setText(tab.privateProfile!=null?"Private":(START.equals(url)?"Site":("https".equalsIgnoreCase(Uri.parse(url).getScheme())?"HTTPS":"HTTP")));
        site.setContentDescription("Site information and protection");
        back.setEnabled(tab.web.canGoBack());
        forward.setEnabled(tab.web.canGoForward());
        back.setAlpha(tab.web.canGoBack()?1f:0.4f);
        forward.setAlpha(tab.web.canGoForward()?1f:0.4f);
        if(url!=null) {
            if(tab.privateProfile!=null){status.setText("Isolated private profile · "+tab.blocked.get()+" requests blocked");}
            else if(START.equals(url)){
                status.setText("Asterion home • "+providerName()+" search • "+
                    (protection.isEnabled()?"Shields enabled":"Shields disabled"));
            }else try {
                status.setText(Uri.parse(url).getHost()+
                    " • "+tab.blocked.get()+" requests blocked"+
                    (protection.isEnabled()?"":" • Shield off"));
            }catch(Exception ignored){status.setText("Browser");}
        }
    }
    private void openEmbeddedTor(String url){
        Intent intent=new Intent(this,TorActivity.class);
        if(url!=null)intent.putExtra("tor_url",url);
        startActivity(intent);
    }
    private void showTorOptions(){
        new AlertDialog.Builder(this).setTitle("Tor network")
            .setItems(new String[]{"Embedded Tor (restricted browsing)","Official Tor Browser / Tor VPN"},(d,choice)->{
                if(choice==0)openEmbeddedTor(null);else ControlTorRoute.panel(this);
            }).setNegativeButton("Cancel",null).show();
    }
    private void navigate(String value) {
        BrowserTab tab=current();
        if(tab==null) return;
        String onion=TorRoutePolicy.onionAddress(value);
        if(onion!=null){openEmbeddedTor(onion);return;}
        if(TorAddressPolicy.looksOnion(value)){notice("Invalid onion address; not sent to search");return;}
        String url=safeAddress(value);
        if(START.equals(url)&&value!=null&&!value.trim().isEmpty()&&!START.equals(value.trim())){notice("Unsupported or invalid address");return;}
        if(pendingSiteRequest!=null)finishSiteRequest(false);
        tab.committedUrl=null;
        tab.pageUrl=url;
        if(START.equals(url)){
            tab.web.stopLoading();tab.web.loadUrl(START);tab.title="New tab";showTab(active);
        }else{
            if(tab.web.getParent()!=viewport){
                viewport.removeAllViews();
                if(tab.web.getParent()!=null)((android.view.ViewGroup)tab.web.getParent()).removeView(tab.web);
                viewport.addView(tab.web,new FrameLayout.LayoutParams(-1,-1));tab.web.onResume();
            }tab.web.loadUrl(url);
        }
        address.clearFocus();root.requestFocus();
        android.view.inputmethod.InputMethodManager keyboard=(android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
        if(keyboard!=null)keyboard.hideSoftInputFromWindow(address.getWindowToken(),0);
        refreshToolbar();persistTabs();
    }
    private static final class SiteRequest {
        final BrowserTab tab;
        final String origin;
        final android.webkit.PermissionRequest media;
        final android.webkit.GeolocationPermissions.Callback location;
        final String[] androidPermissions,webResources;
        final String description;
        SiteRequest(BrowserTab t,String o,android.webkit.PermissionRequest m,
                android.webkit.GeolocationPermissions.Callback l,String[] p,String[] w,String d){
            tab=t;origin=o;media=m;location=l;androidPermissions=p;webResources=w;description=d;
        }
    }
    private boolean visibleSite(SiteRequest request){
        return ControlSecurityPolicy.canRequestBrowserPermission(request.origin,verifiedActiveHttpsOrigin(),
            current()==request.tab&&activeBrowser==this&&!isFinishing()&&!isDestroyed()&&request.tab.web.getParent()==viewport);
    }
    private void requestMediaPermission(BrowserTab tab,android.webkit.PermissionRequest request){
        if(request==null)return;
        java.util.LinkedHashSet<String> permissions=new java.util.LinkedHashSet<>();
        java.util.LinkedHashSet<String> names=new java.util.LinkedHashSet<>();
        String[] resources=request.getResources();
        if(resources==null||resources.length==0){request.deny();return;}
        for(String resource:resources){
            if(android.webkit.PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(resource)){
                permissions.add(android.Manifest.permission.RECORD_AUDIO);names.add("microphone");
            }else if(android.webkit.PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(resource)){
                permissions.add(android.Manifest.permission.CAMERA);names.add("camera");
            }else{request.deny();return;}
        }
        if(request.getOrigin()==null){request.deny();return;}
        beginSiteRequest(new SiteRequest(tab,request.getOrigin().toString(),request,null,
            permissions.toArray(new String[0]),resources.clone(),String.join(" and ",names)));
    }
    private void requestLocationPermission(BrowserTab tab,String origin,android.webkit.GeolocationPermissions.Callback callback){
        if(callback==null)return;
        beginSiteRequest(new SiteRequest(tab,origin,null,callback,new String[]{
            android.Manifest.permission.ACCESS_COARSE_LOCATION,android.Manifest.permission.ACCESS_FINE_LOCATION},new String[0],"location"));
    }
    private boolean androidAllows(SiteRequest request){
        if(request.location!=null)return ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.ACCESS_COARSE_LOCATION)||
            ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.ACCESS_FINE_LOCATION);
        for(String permission:request.androidPermissions)
            if(!ControlSecurityPolicy.browserPermissionGranted(this,permission))return false;
        return true;
    }
    private void answerSiteRequest(SiteRequest request,boolean allowed){
        try{
            if(request.media!=null){
                if(allowed)request.media.grant(request.webResources);else request.media.deny();
            }else if(request.location!=null)request.location.invoke(request.origin,allowed,false);
            if(allowed)request.tab.siteGrants.add(request.description);
        }catch(Exception invalid){notice("Site permission request expired");}
    }
    private void beginSiteRequest(SiteRequest request){
        // Never allow a hidden tab, cross-origin frame, insecure page or a
        // second request to take over an already visible consent dialog.
        if(pendingSiteRequest!=null||androidPermissionInFlight!=null||!hasWindowFocus()||!visibleSite(request)){answerSiteRequest(request,false);return;}
        String display;
        try{display=ControlPasswordVault.exactOrigin(request.origin);}catch(Exception invalid){answerSiteRequest(request,false);return;}
        pendingSiteRequest=request;
        siteRequestDialog=new AlertDialog.Builder(this).setTitle("Site permission")
            .setMessage(display+" requests access to your "+request.description+".\n\nAllow for this page only?")
            .setPositiveButton("Allow once",(d,w)->{
                if(pendingSiteRequest!=request||!visibleSite(request)){finishSiteRequest(false);return;}
                if(androidAllows(request)){finishSiteRequest(true);return;}
                androidPermissionInFlight=request;
                try{requestPermissions(request.androidPermissions,SITE_PERMISSION_CODE);}
                catch(Exception denied){androidPermissionInFlight=null;finishSiteRequest(false);}
            }).setNegativeButton("Deny",(d,w)->finishSiteRequest(false))
            .setOnCancelListener(d->finishSiteRequest(false)).create();
        siteRequestDialog.show();
    }
    private void finishSiteRequest(boolean grant){
        SiteRequest request=pendingSiteRequest;pendingSiteRequest=null;
        AlertDialog dialog=siteRequestDialog;siteRequestDialog=null;
        if(dialog!=null&&dialog.isShowing())dialog.dismiss();
        if(request!=null)answerSiteRequest(request,grant&&visibleSite(request)&&androidAllows(request));
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code==SITE_PERMISSION_CODE){
            SiteRequest completed=androidPermissionInFlight;androidPermissionInFlight=null;
            if(completed!=null&&pendingSiteRequest==completed)finishSiteRequest(true);
        }
    }
    private void showSitePermissions(){
        BrowserTab tab=current();String origin=verifiedActiveHttpsOrigin();
        String grants=tab==null||tab.siteGrants.isEmpty()?"None granted on this page":String.join(", ",tab.siteGrants);
        String message=(origin==null?"No verified HTTPS site":origin)+"\n\nPage access: "+grants+
            "\nAndroid microphone: "+(ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.RECORD_AUDIO)?"allowed":"not granted")+
            "\nAndroid camera: "+(ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.CAMERA)?"allowed":"not granted")+
            "\nAndroid location: "+((ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.ACCESS_COARSE_LOCATION)||ControlSecurityPolicy.browserPermissionGranted(this,android.Manifest.permission.ACCESS_FINE_LOCATION))?"allowed":"not granted")+
            "\n\nWebsite access is requested for each page. Closing a site destroys its WebView and ends its access.";
        AlertDialog.Builder builder=new AlertDialog.Builder(this).setTitle("Site permissions").setMessage(message)
            .setNeutralButton("Android settings",(d,w)->startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+getPackageName()))))
            .setNegativeButton("Close",null);
        if(tab!=null&&!START.equals(tab.pageUrl))builder.setPositiveButton("Close site",(d,w)->{if(tabs.contains(tab))closeTab(tabs.indexOf(tab));});
        builder.show();
    }

    private void confirmDownload(String url, String agent, String disposition, String mime, long length,boolean privateDownload) {
        Uri uri;
        try {
            uri=Uri.parse(url);
            if(!BrowserNavigationPolicy.isWeb(url))
                throw new IllegalArgumentException("Unsupported download URI");
        } catch(Exception bad) { notice("Download URL is not supported"); return; }
        String host=uri.getHost()==null?"website":uri.getHost();
        String size=length>0?(" • "+(length/1024)+" KB"):"";
        AlertDialog.Builder downloadDialog=new AlertDialog.Builder(this)
            .setTitle("Save download?")
            .setMessage(host+" • "+(mime==null?"unknown type":mime)+size+
                "\n\nAndroid Download Manager will save this file."+(privateDownload?" This file and its download record remain outside the private profile; no private cookies are transferred.":""))
            .setPositiveButton("Save", (dialog,which)->{
                try {
                    DownloadManager.Request req=new DownloadManager.Request(uri);
                    String filename=android.webkit.URLUtil.guessFileName(url,disposition,mime).replaceAll("[^\\p{L}\\p{N}._ -]","_");
                    if(filename.isBlank()||filename.equals(".")||filename.equals(".."))filename="download";
                    if(filename.length()>120)filename=filename.substring(filename.length()-120);
                    req.setTitle(filename);
                    req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS,filename);
                    req.setNotificationVisibility(
                        DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    if(mime!=null&&!mime.isBlank()) req.setMimeType(mime);
                    if(agent!=null&&!agent.isBlank())req.addRequestHeader("User-Agent",agent);
                    String cookie=privateDownload?null:CookieManager.getInstance().getCookie(url);
                    if(cookie!=null&&!cookie.isBlank())req.addRequestHeader("Cookie",cookie);
                    DownloadManager manager=(DownloadManager)getSystemService(DOWNLOAD_SERVICE);
                    if(manager==null)throw new IllegalStateException("Android download service unavailable");
                    long downloadId=manager.enqueue(req);
                    if(!privateDownload)rememberDownload(downloadId,host);
                    notice("Download queued in Android Downloads");
                }catch(Exception e){notice("Download failed: "+e.getClass().getSimpleName());}
            }).setNegativeButton("Cancel", null);
        if(!privateDownload)downloadDialog.setNeutralButton("Downloader",(dialog,which)->sendToSpecialistDownloader(url));
        downloadDialog.show();
    }
    private void sendToSpecialistDownloader(String url){
        // B06 delegates to the original signed Downloader/Nexus engine.
        new BrowserDownloadPanel(this).choose(url);
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
            .setNegativeButton("Specialist transfers",(d,w)->new BrowserDownloadPanel(this).show())
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
                            if(status==DownloadManager.STATUS_FAILED||status==DownloadManager.STATUS_PAUSED){
                                int reason=cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON));
                                rows.append(" (Android reason ").append(reason).append(")");
                            }
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

    private void extractVisiblePage(){captureVisiblePage(false);}
    private void pinResearchPage(){captureVisiblePage(true);}
    private void captureVisiblePage(boolean pin) {
        BrowserTab tab=current();
        if(tab==null)return;
        String expected=tab.committedUrl;
        if(!BrowserNavigationPolicy.sameDocument(expected,tab.web.getUrl())){notice("Wait for a committed website page.");return;}
        if(pin&&tab.privateProfile!=null){notice("Private browsing pages cannot be pinned persistently.");return;}
        String js="(function(){return JSON.stringify({url:location.href,title:document.title,"+
            "text:document.body?document.body.innerText.slice(0,32000):''," +
            "captured_utc:new Date().toISOString(),method:'visible_dom_text'});})()";
        tab.web.evaluateJavascript(js, encoded -> {
            try {
                String json=new JSONArray("["+encoded+"]").getString(0);
                JSONObject record=new JSONObject(json);
                if(isFinishing()||isDestroyed()||current()!=tab||!BrowserNavigationPolicy.sameDocument(expected,tab.committedUrl)||!expected.equals(tab.web.getUrl())||!expected.equals(record.optString("url"))){notice("Page changed during capture; retry.");return;}
                String text=record.optString("text","");
                if(text.isBlank()){notice("This page has no extractable visible text");return;}
                if(pin){
                    String safe=BrowserNavigationPolicy.sessionUrl(expected);
                    if(BrowserNavigationPolicy.HOME.equals(safe))throw new IllegalArgumentException("Invalid capture URL");
                    String title=record.optString("title","Page").replaceAll("[\\p{Cntrl}]"," ").strip();
                    if(title.isEmpty())title="Page";
                    title=title.substring(0,Math.min(title.length(),120));
                    String capture=BrowserResearchText.capture(safe,title,text,System.currentTimeMillis());
                    final String label=title;
                    new AlertDialog.Builder(this).setTitle("Pin page to research board")
                        .setMessage(safe+"\n\n"+text.substring(0,Math.min(500,text.length()))+
                            "\n\nAn encrypted local copy will be retained. Website text may contain private information. Query and fragment are excluded from the recorded URL.")
                        .setPositiveButton("Pin source",(d,w)->{
                            if(!isFinishing()&&!isDestroyed()&&current()==tab&&expected.equals(tab.committedUrl)&&expected.equals(tab.web.getUrl()))
                                startActivity(new Intent(this,BrowserResearchActivity.class).putExtra("capture",capture).putExtra("source_name",label));
                            else notice("Page changed; capture not pinned.");
                        }).setNegativeButton("Cancel",null).show();
                    return;
                }
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
            "Android downloads","Desktop site","Asterion assistant","New private tab","Tor network","Pin page to research board","Research board"};
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
                        boolean desktop=!t.desktop;
                        t.desktop=desktop;
                        settings.setUserAgentString(desktop?"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36":t.mobileUserAgent);
                        settings.setUseWideViewPort(desktop);
                        settings.setLoadWithOverviewMode(desktop);
                        notice(desktop?"Desktop viewport enabled":"Mobile viewport enabled");
                        if(!START.equals(t.pageUrl))t.web.reload();
                        break;
                    }
                    case 8:startActivity(new Intent(this,AssistantActivity.class));break;
                    case 9:newPrivateTab();break;
                    case 10:showTorOptions();break;
                    case 11:pinResearchPage();break;
                    case 12:startActivity(new Intent(this,BrowserResearchActivity.class));break;
                }
            }).setNegativeButton("Close",null).show();
    }
    private View createNativeHome(){
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(DesignSystem.BG);
        LinearLayout body=DesignSystem.vertical(this);body.setPadding(dp(20),dp(24),dp(20),dp(24));scroll.addView(body);
        LinearLayout heading=DesignSystem.horizontal(this);
        DesignSystem.AsterionMark mark=new DesignSystem.AsterionMark(this);
        heading.addView(mark,new LinearLayout.LayoutParams(dp(38),dp(38)));
        boolean privateHome=current()!=null&&current().privateProfile!=null;
        TextView title=label(privateHome?"Private browsing":"Asterion Browser",22,DesignSystem.TEXT,true);title.setPadding(dp(12),0,0,0);
        heading.addView(title,new LinearLayout.LayoutParams(0,-2,1));add(body,heading);
        TextView search=control("Search with "+providerName(),()->{
            address.requestFocus();
            android.view.inputmethod.InputMethodManager keyboard=(android.view.inputmethod.InputMethodManager)getSystemService(INPUT_METHOD_SERVICE);
            if(keyboard!=null)keyboard.showSoftInput(address,android.view.inputmethod.InputMethodManager.SHOW_IMPLICIT);
        });
        LinearLayout.LayoutParams searchLp=new LinearLayout.LayoutParams(-1,dp(52));searchLp.topMargin=dp(20);body.addView(search,searchLp);
        if(privateHome){
            TextView detail=label("Separate website storage. This tab is not restored or saved in browsing history. Site-data cleanup is requested on close. After an unexpected stop, cleanup is retried at the next Browser process start. Downloads and network providers are outside this isolation.",14,DesignSystem.MUTED,false);
            detail.setPadding(0,dp(22),0,dp(22));add(body,detail);
        }else{
            homeSection(body,"Bookmarks","bookmarks",8);homeSection(body,"Recent activity","history",5);
        }
        TextView settings=control("Search engine · "+providerName(),this::chooseSearchProvider);
        add(body,settings);return scroll;
    }
    private void homeSection(LinearLayout body,String heading,String key,int limit){
        LinearLayout bar=DesignSystem.horizontal(this);bar.setPadding(0,dp(20),0,dp(4));
        TextView label=label(heading,17,DesignSystem.TEXT,true);bar.addView(label,new LinearLayout.LayoutParams(0,-2,1));
        if(key.equals("bookmarks"))bar.addView(control("Add",this::addHomeBookmark));
        bar.addView(control("View all",()->showEntryList(key,heading)));add(body,bar);
        try{
            JSONArray entries=new JSONArray(browserPrefs.getString(key,"[]"));
            if(entries.length()==0){
                TextView empty=label(key.equals("bookmarks")?"No bookmarks saved":"No recent pages",13,DesignSystem.MUTED,false);
                empty.setPadding(0,dp(8),0,dp(12));add(body,empty);return;
            }
            for(int i=0;i<Math.min(limit,entries.length());i++){
                JSONObject entry=entries.optJSONObject(i);if(entry==null)continue;
                String url=entry.optString("url",START);String name=entry.optString("title","");
                if(name.isBlank())name=url;
                TextView shortcut=control(name,()->navigate(url));shortcut.setGravity(Gravity.START|Gravity.CENTER_VERTICAL);
                shortcut.setSingleLine(true);shortcut.setEllipsize(android.text.TextUtils.TruncateAt.END);
                shortcut.setMinHeight(dp(48));shortcut.setContentDescription(name+", "+Uri.parse(url).getHost());
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(5);body.addView(shortcut,lp);
                if(key.equals("bookmarks"))shortcut.setOnLongClickListener(v->{
                    new AlertDialog.Builder(this).setTitle("Remove bookmark?").setPositiveButton("Remove",(d,w)->{
                        try{JSONArray old=new JSONArray(browserPrefs.getString("bookmarks","[]"));JSONArray next=new JSONArray();
                            for(int j=0;j<old.length();j++){JSONObject e=old.optJSONObject(j);if(e!=null&&!url.equals(e.optString("url")))next.put(e);}
                            browserPrefs.edit().putString("bookmarks",next.toString()).apply();showTab(active);
                        }catch(Exception ignored){notice("Unable to remove bookmark");}
                    }).setNegativeButton("Cancel",null).show();return true;
                });
            }
        }catch(Exception ignored){notice("Saved pages unavailable");}
    }

    private static String safeSessionUrl(String value){
        return BrowserNavigationPolicy.sessionUrl(value);
    }
    private void persistTabs(){
        JSONArray saved=new JSONArray();
        for(BrowserTab tab:tabs)if(tab.privateProfile==null)saved.put(safeSessionUrl(tab.pageUrl));
        browserPrefs.edit().putString("tabs",saved.toString())
            .putInt("active",normalActiveIndex()).apply();
    }
    private int normalActiveIndex(){int index=0,selected=0;for(int i=0;i<tabs.size();i++)if(tabs.get(i).privateProfile==null){if(i<=active)selected=index;index++;}return selected;}
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
    private void addHomeBookmark(){
        LinearLayout fields=DesignSystem.vertical(this);fields.setPadding(dp(20),dp(8),dp(20),0);
        EditText name=new EditText(this);name.setSingleLine(true);name.setHint("Name (optional)");add(fields,name);
        EditText link=new EditText(this);link.setSingleLine(true);link.setHint("https://example.com");link.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);add(fields,link);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Add shortcut").setView(fields).setPositiveButton("Save",null).setNegativeButton("Cancel",null).create();
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(w->{
            String raw=link.getText().toString().trim();if(!raw.contains("://"))raw="https://"+raw;
            String url=safeSessionUrl(raw);if(url.equals(START)){link.setError("Enter a valid website address");return;}
            String title=name.getText().toString().trim();if(title.isEmpty())title=Uri.parse(url).getHost();
            if(saveBookmark(url,title)){dialog.dismiss();showTab(active);}
        }));dialog.show();
    }
    private void bookmarkCurrent(){
        BrowserTab tab=current();
        if(tab==null)return;
        if(tab.privateProfile!=null){notice("Private pages are not saved to the library");return;}
        saveBookmark(tab.web.getUrl(),tab.title);
    }
    private boolean saveBookmark(String raw,String title){
        String url=safeSessionUrl(raw);
        if(url.equals(START))return false;
        try{
            JSONArray previous=new JSONArray(browserPrefs.getString("bookmarks","[]"));
            JSONArray next=new JSONArray();
            next.put(new JSONObject().put("url",url).put("title",title));
            for(int i=0;i<previous.length()&&next.length()<100;i++){
                JSONObject e=previous.optJSONObject(i);
                if(e!=null&&!url.equals(e.optString("url")))next.put(e);
            }
            browserPrefs.edit().putString("bookmarks",next.toString()).apply();
            notice("Bookmark saved");return true;
        }catch(Exception error){notice("Unable to save bookmark");return false;}
    }
    private void showSavedPages(){
        if(current()!=null&&current().privateProfile!=null){notice("Switch to a regular tab to use the browsing library");return;}
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
                    if(tab!=null)navigate(urls[which]);
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
        final boolean privateSite=tab!=null&&tab.privateProfile!=null;
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
                            if(privateSite){notice("Private tabs do not save site exceptions");return;}
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
    private void requestVaultAuth(int policy,String origin){
        if(pendingVaultPolicy!=null){notice("Device confirmation is already open");return;}
        KeyguardManager manager=getSystemService(KeyguardManager.class);
        if(manager==null||!manager.isDeviceSecure()){
            notice("Set an Android device screen lock to use vault authentication");return;
        }
        Intent confirm=manager.createConfirmDeviceCredentialIntent(
            "Asterion Vault","Confirm your Android device credential to unlock or change vault protection.");
        if(confirm==null){notice("Android device confirmation unavailable");return;}
        pendingVaultPolicy=policy;pendingVaultOrigin=origin;
        try{startActivityForResult(confirm,VAULT_AUTH_CODE);}
        catch(Exception failure){pendingVaultPolicy=null;pendingVaultOrigin=null;notice("Could not open Android confirmation");}
    }
    @Override protected void onActivityResult(int requestCode,int resultCode,Intent data){
        super.onActivityResult(requestCode,resultCode,data);
        if(requestCode==VAULT_EXPORT_FILE||requestCode==VAULT_IMPORT_FILE){
            pendingArchive=null;
            if(resultCode!=RESULT_OK||data==null||data.getData()==null)return;
            Uri selected=data.getData();
            if(!"content".equals(selected.getScheme())){notice("Document provider required");return;}
            KeyguardManager manager=getSystemService(KeyguardManager.class);
            if(manager==null||!manager.isDeviceSecure()){notice("Set an Android device lock first");return;}
            Intent confirm=manager.createConfirmDeviceCredentialIntent("Asterion Vault","Confirm access to the encrypted portable archive.");
            if(confirm==null){notice("Android device confirmation unavailable");return;}
            pendingArchive=selected;archiveExport=requestCode==VAULT_EXPORT_FILE;
            try{startActivityForResult(confirm,VAULT_ARCHIVE_AUTH);}
            catch(Exception unavailable){pendingArchive=null;notice("Could not open credential confirmation");}
            return;
        }
        if(requestCode==VAULT_ARCHIVE_AUTH){
            Uri selected=pendingArchive;pendingArchive=null;
            if(selected==null||resultCode!=RESULT_OK||isFinishing())return;
            try{
                ControlPasswordVault.confirmDeviceAuth(this,-1);
                archivePassphrase(selected,archiveExport);
            }catch(Exception failure){notice("Archive authorization unavailable");}
            return;
        }
        if(requestCode!=VAULT_AUTH_CODE)return;
        Integer policy=pendingVaultPolicy;String origin=pendingVaultOrigin;
        pendingVaultPolicy=null;pendingVaultOrigin=null;
        if(policy==null||resultCode!=RESULT_OK){notice("Vault confirmation cancelled");return;}
        try{
            ControlPasswordVault.confirmDeviceAuth(this,policy);
            if(origin!=null&&origin.equals(verifiedActiveHttpsOrigin()))showVault();
            else notice("Vault policy confirmed. Open a verified HTTPS login to use it.");
        }catch(Exception failure){notice("Vault confirmation could not be applied");}
    }
    private void showVaultProtection(String origin){
        int[] values={0,1,5,15};
        int selected=0;
        for(int i=0;i<values.length;i++)if(values[i]==ControlPasswordVault.authTimeout(this))selected=i;
        new AlertDialog.Builder(this).setTitle("Vault device authentication")
            .setSingleChoiceItems(new String[]{"Off","After 1 minute","After 5 minutes","After 15 minutes"},selected,
                (dialog,which)->{dialog.dismiss();requestVaultAuth(values[which],origin);})
            .setNegativeButton("Cancel",null).show();
    }
    private void showVault(){
        BrowserTab tab=current();
        if(tab==null){notice("Open an HTTPS website first");return;}
        String url=tab.web.getUrl();
        final String origin;
        try{origin=verifiedActiveHttpsOrigin();if(origin==null)throw new SecurityException("No verified visible HTTPS document");}
        catch(Exception error){
            new AlertDialog.Builder(this).setTitle("Encrypted password vault")
                .setMessage("Passwords can only be saved and filled for a verified HTTPS origin. Open a secure login page.")
                .setPositiveButton("Close",null).show();
            return;
        }
        if(!ControlPasswordVault.canAccess(this)){
            new AlertDialog.Builder(this).setTitle("Vault locked")
                .setMessage("Confirm your Android device credential. Website sessions remain intact.")
                .setPositiveButton("Unlock",(d,w)->requestVaultAuth(-1,origin))
                .setNeutralButton("Protection",(d,w)->showVaultProtection(origin))
                .setNegativeButton("Cancel",null).show();return;
        }
        try{
            List<ControlPasswordVault.Entry> accounts=
                ControlPasswordVault.accounts(this,origin);
            String[] actions=new String[accounts.size()+6];
            for(int i=0;i<accounts.size();i++)
                actions[i]="Saved account • "+accounts.get(i).username;
            actions[accounts.size()]="Add HTTPS login";
            actions[accounts.size()+1]="Enable Android Autofill";
            actions[accounts.size()+2]="Device authentication and timeout";
            actions[accounts.size()+3]="Lock vault now";
            actions[accounts.size()+4]="Android passkeys and credential providers";
            actions[accounts.size()+5]="Encrypted vault import / export";
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
                    else if(choice==accounts.size()+1)enableSystemAutofill();
                    else if(choice==accounts.size()+2)showVaultProtection(origin);
                    else if(choice==accounts.size()+4)openCredentialProviderSettings();
                    else if(choice==accounts.size()+5)showVaultArchive();
                    else if(ControlPasswordVault.authTimeout(this)>0){
                        ControlPasswordVault.lock();notice("Vault locked");
                    }else notice("Enable device authentication first");
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
        password.setSaveEnabled(false);
        password.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        username.setSaveEnabled(false);
        username.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        add(form,password);
        android.widget.Button generate=new android.widget.Button(this);
        generate.setText("Generate strong password");
        generate.setOnClickListener(v->password.setText(ControlPasswordVault.generatePassword()));
        add(form,generate);
        new AlertDialog.Builder(this).setTitle("Save login • "+origin)
            .setView(form)
            .setPositiveButton("Save",(d,which)->{
                try{
                    if(!origin.equals(verifiedActiveHttpsOrigin()))throw new SecurityException("Site changed");
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
    private void showVaultArchive(){
        if(archiveBusy||pendingArchive!=null){notice("Archive operation already active");return;}
        new AlertDialog.Builder(this).setTitle("Encrypted portable vault")
            .setItems(new String[]{"Export encrypted archive","Import without overwriting existing logins"},(d,index)->{
                try{
                    Intent picker;
                    if(index==0){
                        picker=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/octet-stream");
                        picker.putExtra(Intent.EXTRA_TITLE,"asterion-vault.astvault");
                    }else picker=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*");
                    picker.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(picker,index==0?VAULT_EXPORT_FILE:VAULT_IMPORT_FILE);
                }catch(Exception failure){notice("Document provider unavailable");}
            }).setNegativeButton("Cancel",null).show();
    }
    private EditText archiveSecret(String hint){
        EditText field=new EditText(this);field.setHint(hint);field.setSingleLine(true);
        field.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
        field.setSaveEnabled(false);field.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        return field;
    }
    private void archivePassphrase(Uri uri,boolean export){
        LinearLayout form=DesignSystem.vertical(this);form.setPadding(dp(24),dp(8),dp(24),dp(8));
        add(form,label(export?"Use a unique passphrase of at least 12 characters. The selected provider receives only encrypted bytes; a cancelled export may leave an empty file.":"Only authenticated Asterion archive files are accepted. Existing logins will not be overwritten.",13,DesignSystem.MUTED,false));
        EditText secret=archiveSecret("Archive passphrase");add(form,secret);
        EditText repeat=archiveSecret("Confirm passphrase");if(export)add(form,repeat);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(export?"Encrypt vault archive":"Decrypt and merge vault")
            .setView(form).setNegativeButton("Cancel",null).setPositiveButton(export?"Export":"Import",null).create();
        long approvedAt=android.os.SystemClock.elapsedRealtime();
        dialog.setOnDismissListener(d->{secret.setText("");repeat.setText("");});
        dialog.show();
        dialog.getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_SECURE);
        dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            if(android.os.SystemClock.elapsedRealtime()-approvedAt>120000||
                !ControlPasswordVault.canAccess(this)){dialog.dismiss();notice("Archive authorization expired; select the file again");return;}
            char[] pass=new char[secret.length()];
            secret.getText().getChars(0,secret.length(),pass,0);
            char[] second=new char[repeat.length()];repeat.getText().getChars(0,repeat.length(),second,0);
            boolean valid=pass.length>=12&&pass.length<=256&&(!export||java.util.Arrays.equals(pass,second));
            java.util.Arrays.fill(second,'\0');
            if(!valid){java.util.Arrays.fill(pass,'\0');secret.setError("Use 12–256 characters"+(export?" and matching confirmation":""));return;}
            if(archiveBusy){java.util.Arrays.fill(pass,'\0');return;}
            archiveBusy=true;dialog.dismiss();
            vaultArchiveIo.execute(()->{
                String outcome;
                try{
                    if(export){
                        byte[] sealed=ControlPasswordVault.exportEncrypted(this,pass);
                        try(java.io.OutputStream out=getContentResolver().openOutputStream(uri,"wt")){
                            if(out==null)throw new java.io.IOException("no_output_stream");
                            out.write(sealed);out.flush();
                        }
                        try(java.io.InputStream in=getContentResolver().openInputStream(uri)){
                            if(in==null||!MessageDigest.isEqual(sealed,in.readNBytes(sealed.length+1)))
                                throw new java.io.IOException("archive_readback_mismatch");
                        }
                        outcome="Encrypted archive saved and byte-verified. Keep its passphrase separately.";
                    }else{
                        byte[] sealed;
                        try(java.io.InputStream in=getContentResolver().openInputStream(uri)){
                            if(in==null)throw new java.io.IOException("no_input_stream");
                            sealed=in.readNBytes(VaultArchive.MAX_BYTES+1);
                        }
                        int[] counts=ControlPasswordVault.importEncrypted(this,sealed,pass);
                        outcome="Imported "+counts[0]+" new logins; "+counts[1]+" existing logins preserved.";
                    }
                }catch(Exception failure){
                    outcome=export?"Archive export not verified; selected file may be incomplete.":"Archive could not be authenticated or merge could not be confirmed.";
                }finally{java.util.Arrays.fill(pass,'\0');}
                String report=outcome;runOnUiThread(()->{
                    archiveBusy=false;if(!isFinishing()&&!isDestroyed())
                        new AlertDialog.Builder(this).setTitle("Encrypted vault archive").setMessage(report).setPositiveButton("Close",null).show();
                });
            });
        });
    }

    private void openCredentialProviderSettings(){
        new AlertDialog.Builder(this).setTitle("Android passkeys")
            .setMessage("Manage passkeys through the Android credential provider. In-app third-party website passkeys require provider approval and have not been verified for Asterion Control. No passkeys are copied into the Control vault.")
            .setPositiveButton("Open Android settings",(d,w)->{
                try{
                    startActivity(new Intent("android.settings.CREDENTIAL_PROVIDER"));
                }catch(Exception unsupported){notice("Credential provider settings unavailable on this device.");}
            }).setNegativeButton("Cancel",null).show();
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
        finishSiteRequest(false);
        if(activeBrowser==this)activeBrowser=null;
        persistTabs();
        CookieManager.getInstance().flush();
        super.onStop();
    }
    @Override protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        ArrayList<String> urls=new ArrayList<>();
        for(BrowserTab tab:tabs)if(tab.privateProfile==null)urls.add(safeSessionUrl(tab.pageUrl));
        out.putStringArrayList("urls",urls);
        out.putInt("current",normalActiveIndex());
    }
    @Override protected void onDestroy() {
        finishSiteRequest(false);
        for(BrowserTab tab:tabs) {
            if(tab.web.getParent()!=null)
                ((android.view.ViewGroup)tab.web.getParent()).removeView(tab.web);
            tab.web.stopLoading();
            tab.web.destroy();releasePrivate(tab);
        }
        tabs.clear();pendingArchive=null;
        vaultArchiveIo.shutdown();
        super.onDestroy();
    }
    private void releasePrivate(BrowserTab tab){
        if(tab.privateProfile==null)return;
        try{BrowserPrivateProfiles.released(tab.privateProfile,()->{});}
        catch(RuntimeException failure){if(!isFinishing())notice("Private cleanup pending next Browser process start");}
    }
    private static final class BrowserTab {
        final WebView web;
        volatile String pageUrl="";
        final AtomicInteger blocked=new AtomicInteger(0);
        final AtomicInteger popups=new AtomicInteger(0);
        String title="New tab";
        final String mobileUserAgent,privateProfile;
        boolean desktop,popup;
        final java.util.Set<String> siteGrants=new java.util.LinkedHashSet<>();
        String committedUrl;
        BrowserTab(WebView view,String profile){web=view;privateProfile=profile;mobileUserAgent=view.getSettings().getUserAgentString();}
    }
}
