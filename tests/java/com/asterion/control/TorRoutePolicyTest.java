package com.asterion.control;
public final class TorRoutePolicyTest {
    private static int n;
    private static void check(boolean value){n++;if(!value)throw new AssertionError("case "+n);}
    public static void main(String[] args){
        String onion="http://"+"a".repeat(56)+".onion/";
        check(TorRoutePolicy.onion(onion));check(TorRoutePolicy.target(onion));
        check(!TorRoutePolicy.mayLoad(false,onion));check(TorRoutePolicy.mayLoad(true,onion));
        check(TorRoutePolicy.target("https://example.com/"));check(!TorRoutePolicy.mayLoad(false,"https://example.com/"));
        for(String url:new String[]{"http://localhost/","http://127.0.0.1/","http://[::1]/","http://host.local/","http://abc.onion/","http://host.internal/","http://host.localhost/","http://example.com./","file:///secret","http://user:pass@example.com/"})check(!TorRoutePolicy.target(url));
        System.out.println("TorRoutePolicy: "+n+" assertions passed");
    }
}
