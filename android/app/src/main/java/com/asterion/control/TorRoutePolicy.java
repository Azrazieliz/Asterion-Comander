package com.asterion.control;
import java.net.URI;
import java.util.Locale;
final class TorRoutePolicy {
    private TorRoutePolicy(){}
    static boolean onion(String url){
        try{String host=URI.create(url).getHost();return host!=null&&host.toLowerCase(Locale.ROOT).endsWith(".onion");}
        catch(Exception e){return false;}
    }
    static boolean target(String url){
        if(!BrowserNavigationPolicy.isWeb(url))return false;
        String host=URI.create(url).getHost().toLowerCase(Locale.ROOT);
        // No local, numeric, intranet or browser-to-loopback requests in this mode.
        if(host.endsWith(".")||host.contains(":")||!host.contains(".")||host.matches("[0-9.]+")||
           host.endsWith(".local")||host.endsWith(".localhost")||host.endsWith(".internal"))return false;
        if(onion(url))return host.matches("(?:[a-z0-9-]+\\.)*[a-z2-7]{56}\\.onion");
        return true;
    }
    static boolean mayLoad(boolean ready,String url){return ready&&target(url);}
}
