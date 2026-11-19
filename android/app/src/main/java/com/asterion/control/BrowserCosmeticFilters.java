package com.asterion.control;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Conservative, deterministic element-hiding CSS subset of ABP/EasyList.
 * Not a second network blocker: BrowserProtection owns subscription refresh,
 * WebView interception, site allowlists and this visual rulebook.
 *
 * Supported: ## CSS hide rules, domain-scoped lists, ~domain exclusions and
 * #@# exceptions. Procedural scriptlets, extended selectors and unsafe CSS
 * declarations are deliberately skipped instead of being misrepresented.
 */
final class BrowserCosmeticFilters {
    private static final int MAX_SELECTOR_CHARS=320;
    private static final int MAX_RULES=90000;
    private static final int MAX_CSS_CHARS=170000;
    private static final int MAX_DOMAIN_CHARS=180;
    private static final String HIDE="{display:none!important;visibility:hidden!important}\n";
    private BrowserCosmeticFilters(){}

    private static boolean domainValid(String domain){
        if(domain==null||domain.length()<4||domain.length()>MAX_DOMAIN_CHARS||
           domain.startsWith(".")||domain.endsWith(".")||
           domain.contains("..")||!domain.contains("."))return false;
        for(int n=0;n<domain.length();n++){
            char ch=domain.charAt(n);
            if(!((ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||
                 ch=='.'||ch=='-'))return false;
        }
        return true;
    }
    private static boolean domainMatches(String host,String domain){
        return host.equals(domain)||host.endsWith("."+domain);
    }
    private static boolean safeSelector(String selector){
        if(selector.isEmpty()||selector.length()>MAX_SELECTOR_CHARS)return false;
        String lower=selector.toLowerCase(Locale.ROOT);
        if(Arrays.asList("*","body","html",":root").contains(lower)||
           lower.contains(":-abp-")||lower.contains(":has-text(")||
           lower.contains(":matches-css(")||lower.contains(":xpath(")||
           lower.contains(":remove(")||lower.contains("url(")||
           lower.contains("expression("))return false;
        boolean identifying=false;
        for(int n=0;n<selector.length();n++){
            char ch=selector.charAt(n);
            if(ch<32||ch>126||ch=='{'||ch=='}'||ch==';'||ch=='\\'||
               ch=='@'||ch=='\u0060')return false;
            if(ch=='.'||ch=='#'||ch=='[')identifying=true;
        }
        return identifying;
    }

    private static final class Rule {
        final String selector;
        final boolean exception;
        final String[] domains;
        final String[] excluded;
        Rule(String selector,boolean exception,List<String> domains,List<String> excluded){
            this.selector=selector;
            this.exception=exception;
            this.domains=domains.toArray(new String[0]);
            this.excluded=excluded.toArray(new String[0]);
        }
        boolean applies(String host){
            for(String item:excluded)if(domainMatches(host,item))return false;
            if(domains.length==0)return true;
            for(String item:domains)if(domainMatches(host,item))return true;
            return false;
        }
    }

    static final class Builder {
        private final List<Rule> rules=new ArrayList<>();
        private int parsed=0;
        int parsed(){return parsed;}
        void accept(String line){
            if(rules.size()>=MAX_RULES||line==null||line.length()>1500)return;
            int exceptionAt=line.indexOf("#@#");
            boolean exception=exceptionAt>=0;
            int at=exception?exceptionAt:line.indexOf("##");
            if(at<0)return;
            String selector=line.substring(at+(exception?3:2)).trim();
            if(!safeSelector(selector))return;
            String domainPart=line.substring(0,at).trim().toLowerCase(Locale.ROOT);
            List<String> includes=new ArrayList<>(),excludes=new ArrayList<>();
            if(!domainPart.isEmpty()){
                String[] tokens=domainPart.split(",",-1);
                if(tokens.length>16)return;
                for(String raw:tokens){
                    String token=raw.trim();
                    boolean excluded=token.startsWith("~");
                    if(excluded)token=token.substring(1);
                    if(!domainValid(token))return;
                    if(excluded)excludes.add(token);
                    else includes.add(token);
                }
            }
            rules.add(new Rule(selector,exception,includes,excludes));
            parsed++;
        }
        Book build(){
            return new Book(Collections.unmodifiableList(new ArrayList<>(rules)));
        }
    }

    static final class Book {
        private final List<Rule> rules;
        private Book(List<Rule> rules){this.rules=rules;}
        int count(){return rules.size();}
        String cssForHost(String rawHost){
            if(rawHost==null)return "";
            String host=rawHost.toLowerCase(Locale.ROOT);
            if(!domainValid(host))return "";
            Set<String> hides=new LinkedHashSet<>(),exceptions=new LinkedHashSet<>();
            for(Rule rule:rules){
                if(!rule.applies(host))continue;
                if(rule.exception)exceptions.add(rule.selector);
                else hides.add(rule.selector);
            }
            StringBuilder out=new StringBuilder();
            for(String selector:hides){
                if(exceptions.contains(selector))continue;
                if(out.length()+selector.length()+HIDE.length()>MAX_CSS_CHARS)break;
                out.append(selector).append(HIDE);
            }
            return out.toString();
        }
    }
}
