package com.asterion.control;

/** Executable JVM-only CSS safety and site-scoping acceptance. */
public final class BrowserCosmeticFiltersTest {
  private static int checks=0;
  private static void check(boolean condition,String message){
    checks++;
    if(!condition)throw new AssertionError(message);
  }
  private static void has(String css,String expected,String message){
    check(css.contains(expected),message+" missing "+expected);
  }
  private static void lacks(String css,String unexpected,String message){
    check(!css.contains(unexpected),message+" unexpectedly contains "+unexpected);
  }
  public static void main(String[] args){
    BrowserCosmeticFilters.Builder b=new BrowserCosmeticFilters.Builder();
    b.accept("##.generic-ad");
    b.accept("##[id^=\"sponsored_\"]");
    b.accept("example.com##.targeted-ad");
    b.accept("foo.example.com##.nested-ad");
    b.accept("example.com,news.test##.multi-site-banner");
    b.accept("example.com,~safe.example.com##.exclude-safe");
    b.accept("safe.example.com#@#.generic-ad");
    b.accept("news.test#@#.multi-site-banner");
    b.accept("##body");
    b.accept("##*");
    b.accept("##:root");
    b.accept("##div;body{display:none}");
    b.accept("##div{color:red}");
    b.accept("##div:has-text(sponsored)");
    b.accept("##div:-abp-properties(p)");
    b.accept("ads.example.com##.ads-dot");
    b.accept("http://evil##.unsafe-url-domain");
    b.accept("example.com##.targeted-ad");
    BrowserCosmeticFilters.Book book=b.build();
    String example=book.cssForHost("example.com");
    String nested=book.cssForHost("foo.example.com");
    String safe=book.cssForHost("safe.example.com");
    String news=book.cssForHost("news.test");
    String other=book.cssForHost("unrelated.test");
    has(example,".generic-ad{display:none!important;","generic");
    has(example,".targeted-ad{display:none!important;","site");
    has(example,".multi-site-banner{display:none!important;","multiple");
    has(example,".exclude-safe{display:none!important;","exclude elsewhere");
    has(nested,".nested-ad{display:none!important;","nested domain");
    has(nested,".targeted-ad{display:none!important;","parent domain scope");
    lacks(safe,".generic-ad{display:none!important;","exception hides no generic");
    lacks(safe,".exclude-safe{display:none!important;","domain exclusion");
    has(safe,".targeted-ad{display:none!important;","scoped parent survives");
    lacks(news,".multi-site-banner{display:none!important;","domain exception");
    has(other,".generic-ad{display:none!important;","global site default");
    lacks(other,".targeted-ad{display:none!important;","unrelated domain");
    lacks(other,".multi-site-banner{display:none!important;","unrelated multi");
    lacks(other,"body{display:none", "never hide entire body");
    lacks(other,":root{display:none", "never hide root");
    lacks(other,"div;body", "no CSS rule injection");
    lacks(other,"{color:red}", "no arbitrary CSS declaration");
    lacks(other,"has-text", "no unimplemented selector");
    lacks(other,":-abp-", "no extended ABP selector");
    lacks(example,".unsafe-url-domain", "reject invalid scoped domain");
    check(book.cssForHost("localhost").isEmpty(),"invalid host");
    check(book.cssForHost("evil.example.com.attacker.test").contains(".generic-ad"),"global on lookalike");
    lacks(book.cssForHost("evil.example.com.attacker.test"),".targeted-ad", "strict host suffix");
    check(book.count()>=7,"parsed supported hide rules");
    check(book.cssForHost("example.com").length()<170000,"bounded CSS output");
    System.out.println("BROWSER_COSMETIC_PASS "+checks+" assertions");
  }
}
