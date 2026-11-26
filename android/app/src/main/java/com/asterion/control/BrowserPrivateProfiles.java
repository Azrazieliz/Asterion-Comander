package com.asterion.control;

import android.webkit.WebView;
import androidx.webkit.Profile;
import androidx.webkit.ProfileStore;
import androidx.webkit.WebStorageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** Uses actual WebView profile isolation; no global CookieManager/cache deletion. */
final class BrowserPrivateProfiles {
    private static final String PREFIX="asterion-private-";
    private static final Map<String,Session> live=new HashMap<>();
    private static boolean initialized=false;
    private static final class Session{
        final Profile profile;int views;
        Session(Profile p){profile=p;views=1;}
    }
    private BrowserPrivateProfiles(){}
    static boolean supported(){
        try{return WebViewFeature.isFeatureSupported(WebViewFeature.MULTI_PROFILE)&&
            WebViewFeature.isFeatureSupported(WebViewFeature.DELETE_BROWSING_DATA);}
        catch(Exception unavailable){return false;}
    }
    static void cleanPreviousProcess(){
        if(initialized||!supported())return;
        initialized=true;
        try{
            ProfileStore store=ProfileStore.getInstance();
            for(String name:new ArrayList<>(store.getAllProfileNames())){
                if(name.startsWith(PREFIX)){
                    try{store.deleteProfile(name);}catch(RuntimeException ignored){}
                }
            }
        }catch(RuntimeException ignored){}
    }
    static String newName(){return PREFIX+UUID.randomUUID();}
    static void attach(WebView view,String name){
        if(!supported()||name==null||!name.startsWith(PREFIX))
            throw new IllegalStateException("Private WebView profiles unavailable");
        // Must occur before navigation, settings access, or getProfile.
        WebViewCompat.setProfile(view,name);
        Session session=live.get(name);
        if(session==null)live.put(name,new Session(WebViewCompat.getProfile(view)));
        else session.views++;
    }
    static void released(String name,Runnable done){
        if(name==null)return;
        Session session=live.get(name);
        if(session==null)return;
        if(--session.views>0)return;
        live.remove(name);
        // Full profile-local storage, cookies, service workers and network cache.
        // A crash before completion may leave storage until next process start;
        // the name is never reused. Never delete or clear the ordinary profile.
        WebStorageCompat.deleteBrowsingData(session.profile.getWebStorage(),done);
    }
}
