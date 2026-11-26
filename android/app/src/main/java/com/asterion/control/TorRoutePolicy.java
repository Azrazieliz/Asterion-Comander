package com.asterion.control;
import java.net.URI;
import java.util.Locale;
final class TorRoutePolicy {
    static final String BROWSER="org.torproject.torbrowser", VPN="org.torproject.vpn";
    // Tor Project release signing script, Bug 41814 (c9e0f19d62a9da0e8ce633c7c32064b3b5ff9c15).
    static final String BROWSER_SIGNER="20061f045e737c67375c17794cfedb436a03cec6bacb7cb9f96642205ca2cec8";
    static final String VPN_SIGNER="c2f6ffa30e56a7c53a226248ef908612ee539df2f52bede5a55037425b83331d";
    private TorRoutePolicy(){}
    static boolean onionHost(String value){
        try{
            URI uri=URI.create(value);String host=uri.getHost();
            if(host==null)return false;
            host=host.toLowerCase(Locale.ROOT);
            while(host.endsWith("."))host=host.substring(0,host.length()-1);
            return host.equals("onion")||host.endsWith(".onion");
        }catch(Exception e){return false;}
    }
    static String onionAddress(String input){
        if(input==null||input.length()>4096)return null;
        String raw=input.trim();
        if(raw.chars().anyMatch(c->c<32||c==127)||raw.indexOf('\\')>=0)return null;
        if(!raw.contains("://"))raw="http://"+raw;
        try{
            URI u=URI.create(raw);
            if(!("http".equalsIgnoreCase(u.getScheme())||"https".equalsIgnoreCase(u.getScheme()))||u.getRawUserInfo()!=null)return null;
            String h=u.getHost();
            if(h==null||!h.toLowerCase(Locale.ROOT).matches("(?:[a-z0-9-]+\\.)*[a-z2-7]{56}\\.onion")||u.getPort()==0||u.getPort()>65535)return null;
            return raw;
        }catch(Exception e){return null;}
    }
    static boolean signer(String pkg,String fingerprint){
        return BROWSER.equals(pkg)&&BROWSER_SIGNER.equals(fingerprint)||VPN.equals(pkg)&&VPN_SIGNER.equals(fingerprint);
    }
}
