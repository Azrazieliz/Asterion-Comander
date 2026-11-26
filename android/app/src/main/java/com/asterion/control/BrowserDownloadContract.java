package com.asterion.control;

import java.util.regex.Pattern;

/** Only the existing owning transfer engines, including the approved Nexus migration. */
final class BrowserDownloadContract {
    static final String DOWNLOADER="com.azrael.pixivdumpsync";
    static final String DOWNLOADER_ACCEPTANCE="com.azrael.pixivdumpsync.acceptance";
    static final String NEXUS="com.asterion.nexus";
    private static final Pattern ID=Pattern.compile("browser-[a-f0-9-]{36}");
    private BrowserDownloadContract(){}
    static boolean ownerPackage(String pkg){return DOWNLOADER.equals(pkg)||DOWNLOADER_ACCEPTANCE.equals(pkg)||NEXUS.equals(pkg);}
    static boolean requestId(String id){return id!=null&&ID.matcher(id).matches();}
    static boolean canDispatch(String pkg,String intent,String url,String id){
        return ownerPackage(pkg)&&"download".equals(intent)&&requestId(id)&&
            BrowserNavigationPolicy.isWeb(url)&&url.length()<=3500;
    }
    static boolean terminal(String status){
        return "completed".equals(status)||"failed".equals(status)||"rejected".equals(status)||
            "cancelled".equals(status)||"canceled".equals(status);
    }
}
