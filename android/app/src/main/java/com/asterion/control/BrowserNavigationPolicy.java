package com.asterion.control;

import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/** Original Browser navigation and privacy rules, independent of the Android view lifecycle. */
final class BrowserNavigationPolicy {
    static final String HOME="about:blank";
    private BrowserNavigationPolicy(){}
    static String resolve(String raw,String prefix){
        String value=raw==null?"":raw.trim();
        if(value.isEmpty()||HOME.equals(value))return HOME;
        if(value.length()>16384||value.chars().anyMatch(c->c<32||c==127)||value.indexOf('\\')>=0)return HOME;
        String lower=value.toLowerCase(Locale.ROOT);
        if(lower.startsWith("http://")||lower.startsWith("https://"))
            return isWeb(value)?value:HOME;
        // A bare hostname with an explicit port is an address, not a scheme.
        boolean hostPort=value.matches("(?i)^[a-z0-9.-]+\\.[a-z0-9.-]+:[0-9]+(?:[/?#].*)?$");
        if(!hostPort&&value.matches("(?i)^[a-z][a-z0-9+.-]*:.*"))return HOME;
        if(value.contains(" ")||!value.contains("."))return prefix+URLEncoder.encode(value,StandardCharsets.UTF_8);
        String address="https://"+value;
        return isWeb(address)?address:HOME;
    }
    static boolean isWeb(String value){
        if(value==null||value.indexOf('\\')>=0)return false;
        try{
            URI u=URI.create(value);String scheme=u.getScheme();
            return ("https".equalsIgnoreCase(scheme)||"http".equalsIgnoreCase(scheme))&&
                u.getHost()!=null&&!u.getHost().isBlank()&&u.getRawUserInfo()==null&&
                (u.getPort()==-1||(u.getPort()>0&&u.getPort()<=65535));
        }catch(Exception invalid){return false;}
    }
    /** Persist only safe paths, never query/fragment/userinfo carrying credentials or OAuth state. */
    static String sessionUrl(String value){
        if(!isWeb(value))return HOME;
        URI u=URI.create(value);
        String path=u.getRawPath();
        String clean=u.getScheme()+"://"+u.getRawAuthority()+(path==null?"":path);
        return clean.length()<=1200?clean:HOME;
    }
    static boolean allowPopup(boolean gesture,boolean foreground,boolean hasRoom){
        return gesture&&foreground&&hasRoom;
    }
    static boolean sameHttpsOrigin(String requested,String visible){
        if(!isWeb(requested)||!isWeb(visible))return false;
        URI a=URI.create(requested),b=URI.create(visible);
        return "https".equalsIgnoreCase(a.getScheme())&&"https".equalsIgnoreCase(b.getScheme())&&
            a.getHost().equalsIgnoreCase(b.getHost())&&
            (a.getPort()==-1?443:a.getPort())==(b.getPort()==-1?443:b.getPort());
    }
    static boolean sameDocument(String committed,String current){
        return isWeb(committed)&&isWeb(current)&&committed.equals(current);
    }
}
