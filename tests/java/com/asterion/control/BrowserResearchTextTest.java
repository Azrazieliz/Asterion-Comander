package com.asterion.control;
public final class BrowserResearchTextTest {
    public static void main(String[] args)throws Exception{
        String source=BrowserResearchText.capture("https://example.test/a","Fixture","A rare Orchid appears.",1000);
        if(!source.contains(BrowserResearchText.sha("A rare Orchid appears.")))throw new AssertionError("digest");
        if(!BrowserResearchText.excerpt(source,"orchid").contains("Orchid"))throw new AssertionError("match");
        if(!BrowserResearchText.excerpt(source,"Fixture").startsWith("No literal match"))throw new AssertionError("metadata is not source content");
        if(!BrowserResearchText.excerpt(source,"notpresent").startsWith("No literal match"))throw new AssertionError("missing");
        if(!BrowserResearchText.excerpt("a.b literal","a.b").contains("a.b"))throw new AssertionError("literal regex");
        System.out.println("Browser source capture and comparison passed");
    }
}
