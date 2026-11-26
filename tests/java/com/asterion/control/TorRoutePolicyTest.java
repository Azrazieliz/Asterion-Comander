package com.asterion.control;
public final class TorRoutePolicyTest {
    static int checks;
    static void expect(boolean v){checks++;if(!v)throw new AssertionError("case "+checks);}
    public static void main(String[] args){
        String host="a".repeat(56)+".onion";
        expect(TorRoutePolicy.onionAddress(host).equals("http://"+host));
        expect(TorRoutePolicy.onionAddress("https://"+host+"/path")!=null);
        expect(TorRoutePolicy.onionAddress("https://"+host+"@example.com")==null);
        expect(TorRoutePolicy.onionAddress("http://short.onion")==null);
        expect(TorRoutePolicy.onionAddress("http://"+host+".example.com")==null);
        expect(TorRoutePolicy.onionAddress("ftp://"+host)==null);
        expect(TorRoutePolicy.onionAddress("http://"+host+":0")==null);
        expect(TorRoutePolicy.onionHost("http://"+host+"."));
        expect(!BrowserNavigationPolicy.isWeb("http://"+host));
        expect(!BrowserNavigationPolicy.isWeb("http://"+host+"."));
        expect(BrowserNavigationPolicy.sessionUrl("http://"+host).equals(BrowserNavigationPolicy.HOME));
        expect(BrowserNavigationPolicy.isWeb("https://example.com/"));
        expect(TorRoutePolicy.signer(TorRoutePolicy.BROWSER,TorRoutePolicy.BROWSER_SIGNER));
        expect(TorRoutePolicy.signer(TorRoutePolicy.VPN,TorRoutePolicy.VPN_SIGNER));
        expect(!TorRoutePolicy.signer(TorRoutePolicy.BROWSER,TorRoutePolicy.VPN_SIGNER));
        expect(!TorRoutePolicy.signer("org.other",TorRoutePolicy.BROWSER_SIGNER));
        System.out.println("TorRoutePolicy: "+checks+" assertions passed");
    }
}
