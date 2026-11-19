package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Handler;
import android.os.Looper;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Browser network shield owned by Browser, not by Downloader. Downloads genuine
 * EasyList and EasyPrivacy over HTTPS. Only the conservatively understood
 * third-party hostname rules are enforced; the unsupported ABP rule types,
 * cosmetic rules, in-stream ads and opaque service-worker traffic are NOT
 * represented as blocked. Report real intercepted requests only.
 */
final class BrowserProtection {
    interface Listener { void updated(boolean success, String message); }
    private static final String PREF="asterion_browser_filters_v1";
    private static final String[] SOURCES={
        "https://easylist.to/easylist/easylist.txt",
        "https://easylist.to/easylist/easyprivacy.txt"};
    private static final String[] CACHE={"easylist.txt","easyprivacy.txt"};
    private static final int MAX_SOURCE=10*1024*1024;
    private static final int MIN_RULES=1200;
    private static final long REFRESH_MS=24L*60*60*1000;
    private static final Set<String> SEED=new HashSet<>(Arrays.asList(
        "doubleclick.net","googlesyndication.com","googleadservices.com",
        "adnxs.com","criteo.com","taboola.com","outbrain.com",
        "scorecardresearch.com","pubmatic.com","rubiconproject.com",
        "casalemedia.com","adsrvr.org","smartadserver.com",
        "quantserve.com","adsafeprotected.com"));
    private static final ExecutorService WORK=Executors.newSingleThreadExecutor(r->{
        Thread t=new Thread(r,"asterion-filter-subscriptions");
        t.setDaemon(true);
        return t;
    });
    private final SharedPreferences pref;
    private final File folder;
    private final AtomicReference<Rules> active=new AtomicReference<>(new Rules(
        SEED,Collections.emptySet(),false));
    private volatile boolean enabled;
    private volatile boolean updating;

    private static final class Rules {
        final Set<String> deny;
        final Set<String> allow;
        final boolean loaded;
        Rules(Set<String> blocked,Set<String> exception,boolean cached){
            deny=Collections.unmodifiableSet(new HashSet<>(blocked));
            allow=Collections.unmodifiableSet(new HashSet<>(exception));
            loaded=cached;
        }
    }
    private static final class Builder {
        final Set<String> deny=new HashSet<>(SEED);
        final Set<String> allow=new HashSet<>();
        int parsed=0;
        void accept(String line) {
            String rule=line.trim();
            if(rule.startsWith("!")||rule.startsWith("[")||rule.startsWith("#"))return;
            boolean exception=rule.startsWith("@@");
            if(exception)rule=rule.substring(2);
            if(!rule.startsWith("||"))return;
            int from=2,at=from;
            while(at<rule.length()){
                char ch=rule.charAt(at);
                if(Character.isLetterOrDigit(ch)||ch=='.'||ch=='-')at++;
                else break;
            }
            if(at-from<4||at-from>180)return;
            String host=rule.substring(from,at).toLowerCase(Locale.ROOT);
            if(!host.contains(".")||host.contains("..")||
                host.startsWith(".")||host.endsWith(".")||
                !host.matches("[a-z0-9.-]+"))return;
            String remainder=rule.substring(at);
            // Scope constraints cannot be safely reduced to whole-host matches.
            if(remainder.contains("domain=")||remainder.contains("denyallow=")||
               remainder.contains("~third-party")||remainder.contains("redirect=")||
               remainder.contains("rewrite="))return;
            if(!(remainder.isEmpty()||remainder.equals("^")||
                 remainder.startsWith("^$")||remainder.startsWith("$")))return;
            if(exception){
                // Only unscoped whole-host exceptions prevent false positives.
                if(remainder.isEmpty()||remainder.equals("^"))allow.add(host);
            }else deny.add(host);
            parsed++;
        }
        Rules build(){return new Rules(deny,allow,true);}
    }
    BrowserProtection(Context ctx){
        Context app=ctx.getApplicationContext();
        pref=app.getSharedPreferences(PREF,Context.MODE_PRIVATE);
        folder=new File(app.getFilesDir(),"browser-subscriptions");
        enabled=pref.getBoolean("enabled",true);
        loadCached();
    }
    boolean isEnabled(){return enabled;}
    void setEnabled(boolean newValue){
        enabled=newValue;
        pref.edit().putBoolean("enabled",newValue).apply();
    }
    boolean isUpdating(){return updating;}
    boolean subscriptionsLoaded(){return active.get().loaded;}
    int domainRules(){return active.get().deny.size();}
    long lastUpdated(){return pref.getLong("updated_ms",0);}
    String sourceDigest(){return pref.getString("lists_sha256","");}
    String updateError(){return pref.getString("update_error","");}
    private static String host(String raw){
        if(raw==null)return "";
        try{
            Uri uri=Uri.parse(raw);
            String scheme=uri.getScheme();
            if(!"http".equalsIgnoreCase(scheme)&&
               !"https".equalsIgnoreCase(scheme))return "";
            String value=uri.getHost();
            return value==null?"":value.toLowerCase(Locale.ROOT);
        }catch(Exception error){return "";}
    }
    private static boolean matches(String subject,String rule){
        return subject.equals(rule)||subject.endsWith("."+rule);
    }
    private static String rootDomain(String host){
        String[] parts=host.split("\\.");
        if(parts.length<2)return host;
        int n=2;
        if(parts.length>=3&&parts[parts.length-1].length()==2 &&
           Arrays.asList("co","com","org","net","ac","gov","edu")
                 .contains(parts[parts.length-2]))n=3;
        StringBuilder out=new StringBuilder();
        for(int i=parts.length-n;i<parts.length;i++){
            if(out.length()>0)out.append('.');
            out.append(parts[i]);
        }
        return out.toString();
    }
    boolean isAllowedSite(String page){
        String h=host(page);
        return !h.isEmpty()&&pref.getBoolean("allow:"+h,false);
    }
    void allowSite(String page,boolean value){
        String h=host(page);
        if(h.isEmpty()||h.length()>180)throw new IllegalArgumentException("No valid site");
        pref.edit().putBoolean("allow:"+h,value).apply();
    }
    boolean blocks(String resource,String page){
        if(!enabled||isAllowedSite(page))return false;
        String target=host(resource),origin=host(page);
        if(target.isEmpty()||origin.isEmpty())return false;
        if(rootDomain(target).equals(rootDomain(origin)))return false;
        Rules rules=active.get();
        for(String exception:rules.allow)if(matches(target,exception))return false;
        for(String blocked:rules.deny)if(matches(target,blocked))return true;
        return false;
    }
    WebResourceResponse intercept(WebResourceRequest req,String page){
        if(req==null||req.isForMainFrame()||!blocks(req.getUrl().toString(),page))return null;
        return new WebResourceResponse("text/plain","UTF-8",403,
            "Blocked by Asterion Browser",
            Collections.singletonMap("Cache-Control","no-store"),
            new ByteArrayInputStream(new byte[0]));
    }
    private File cached(int n){return new File(folder,CACHE[n]);}
    private void loadCached(){
        try{
            if(!folder.isDirectory())return;
            Builder builder=new Builder();
            for(int n=0;n<CACHE.length;n++){
                File file=cached(n);
                if(!file.isFile()||file.length()>MAX_SOURCE)return;
                try(BufferedReader reader=new BufferedReader(new InputStreamReader(
                        new FileInputStream(file),StandardCharsets.UTF_8))){
                    for(String line;(line=reader.readLine())!=null;)builder.accept(line);
                }
            }
            if(builder.parsed>=MIN_RULES)active.set(builder.build());
        }catch(Exception ignored){
            // Corrupt caches are never interpreted as a successful refresh.
        }
    }
    void refresh(boolean force,Listener callback){
        if(!force&&System.currentTimeMillis()-lastUpdated()<REFRESH_MS){
            if(callback!=null)new Handler(Looper.getMainLooper()).post(
                ()->callback.updated(false,"Lists already current"));
            return;
        }
        synchronized(this){
            if(updating){
                if(callback!=null)new Handler(Looper.getMainLooper()).post(
                    ()->callback.updated(false,"Update already running"));
                return;
            }
            updating=true;
        }
        WORK.execute(()->{
            String reason="Filter update unavailable";
            boolean success=false;
            try{
                if(!folder.isDirectory()&&!folder.mkdirs())
                    throw new IOException("Cannot prepare private filter storage");
                Builder builder=new Builder();
                MessageDigest hash=MessageDigest.getInstance("SHA-256");
                File[] staging=new File[SOURCES.length];
                for(int n=0;n<SOURCES.length;n++){
                    staging[n]=new File(folder,CACHE[n]+".partial");
                    HttpURLConnection http=(HttpURLConnection)new URL(SOURCES[n]).openConnection();
                    http.setInstanceFollowRedirects(false);
                    http.setConnectTimeout(12000);
                    http.setReadTimeout(20000);
                    try{
                        if(http.getResponseCode()!=200)
                            throw new IOException("Official list HTTP "+http.getResponseCode());
                        int length=0;
                        try(InputStream input=http.getInputStream();
                            FileOutputStream output=new FileOutputStream(staging[n])){
                            byte[] buffer=new byte[32768];
                            for(int read;(read=input.read(buffer))!=-1;){
                                length+=read;
                                if(length>MAX_SOURCE)throw new IOException("Filter too large");
                                output.write(buffer,0,read);
                            }
                            output.getFD().sync();
                        }
                        if(length<30000)throw new IOException("Filter payload unexpectedly short");
                    }finally{http.disconnect();}
                }
                for(File file:staging){
                    try(BufferedReader reader=new BufferedReader(new InputStreamReader(
                            new FileInputStream(file),StandardCharsets.UTF_8))){
                        for(String line;(line=reader.readLine())!=null;){
                            builder.accept(line);
                            hash.update(line.getBytes(StandardCharsets.UTF_8));
                            hash.update((byte)'\n');
                        }
                    }
                }
                if(builder.parsed<MIN_RULES)
                    throw new IOException("Downloaded lists contain too few usable rules");
                for(int n=0;n<staging.length;n++){
                    if(!staging[n].renameTo(cached(n)))
                        throw new IOException("Filter cache could not commit");
                }
                StringBuilder digest=new StringBuilder(64);
                for(byte value:hash.digest())
                    digest.append(String.format(Locale.ROOT,"%02x",value&255));
                if(!pref.edit().putLong("updated_ms",System.currentTimeMillis())
                    .putString("lists_sha256",digest.toString())
                    .putString("update_error","").commit())
                    throw new IOException("Filter metadata not persisted");
                active.set(builder.build());
                success=true;
                reason="EasyList + EasyPrivacy updated";
            }catch(Exception failure){
                reason=failure.getClass().getSimpleName();
                pref.edit().putString("update_error",reason).apply();
            }finally{
                synchronized(this){updating=false;}
            }
            final boolean completed=success;
            final String message=reason;
            if(callback!=null)new Handler(Looper.getMainLooper()).post(
                ()->callback.updated(completed,message));
        });
    }
}
