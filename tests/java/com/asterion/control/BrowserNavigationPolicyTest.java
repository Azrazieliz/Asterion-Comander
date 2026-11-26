package com.asterion.control;
public final class BrowserNavigationPolicyTest {
    private static int assertions;
    private static final String P="https://duckduckgo.com/?q=";
    private static void equal(Object expected,Object actual){
        assertions++;
        if(!expected.equals(actual))throw new AssertionError("Expected "+expected+"; got "+actual);
    }
    public static void main(String[] args){
        String home=BrowserNavigationPolicy.HOME;
        equal(home,BrowserNavigationPolicy.resolve("",P));
        equal(home,BrowserNavigationPolicy.resolve(home,P));
        equal("https://example.com",BrowserNavigationPolicy.resolve("example.com",P));
        equal("https://example.com:8443/path",BrowserNavigationPolicy.resolve("example.com:8443/path",P));
        equal("HTTP://example.com/",BrowserNavigationPolicy.resolve("HTTP://example.com/",P));
        equal(P+"hello+world",BrowserNavigationPolicy.resolve("hello world",P));
        equal(P+"caf%C3%A9",BrowserNavigationPolicy.resolve("café",P));
        for(String bad:new String[]{"javascript:alert(1)","file:///etc/passwd","data:text/html,test","intent://x","https://user:pass@example.com/","https://example.com:65536","https://example.com:0","https://example.com\\evil","https://example.com\nother","https://","https://example.com:bad"}){
            equal(home,BrowserNavigationPolicy.resolve(bad,P));
        }
        equal("https://example.com/a%20b",BrowserNavigationPolicy.sessionUrl("https://example.com/a%20b?token=secret#oauth"));
        equal(home,BrowserNavigationPolicy.sessionUrl("https://user@example.com/"));
        equal(home,BrowserNavigationPolicy.sessionUrl("file:///private"));
        equal(home,BrowserNavigationPolicy.sessionUrl(null));
        equal(home,BrowserNavigationPolicy.sessionUrl("https://example.com/"+"x".repeat(1201)));
        for(int mask=0;mask<8;mask++){
            equal(mask==7,BrowserNavigationPolicy.allowPopup((mask&1)!=0,(mask&2)!=0,(mask&4)!=0));
        }
        equal(true,BrowserNavigationPolicy.sameDocument("https://example.com/","https://example.com/"));
        equal(false,BrowserNavigationPolicy.sameDocument("https://example.com/","https://example.com/login"));
        equal(false,BrowserNavigationPolicy.sameDocument("https://example.com/",home));
        equal(false,BrowserNavigationPolicy.sameDocument(home,home));
        equal(false,BrowserNavigationPolicy.sameDocument(null,null));
        equal(true,BrowserNavigationPolicy.sameHttpsOrigin("https://example.com","https://EXAMPLE.com:443/path"));
        equal(true,BrowserNavigationPolicy.sameHttpsOrigin("https://example.com:8443","https://example.com:8443/a"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("https://example.com:8443","https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("https://example.com.evil.test","https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("https://sub.example.com","https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("http://example.com","https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("https://user@example.com","https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin(null,"https://example.com"));
        equal(false,BrowserNavigationPolicy.sameHttpsOrigin("https://example.com",home));
        System.out.println("BrowserNavigationPolicy: "+assertions+" assertions passed");
    }
}
