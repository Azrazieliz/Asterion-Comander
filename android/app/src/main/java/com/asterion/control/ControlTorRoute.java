package com.asterion.control;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.PackageInfo;
import android.content.pm.Signature;
import android.net.Uri;
import java.security.MessageDigest;
import java.util.Locale;

/** Delegates onion browsing to the actual Tor Project browser; no WebView fallback. */
final class ControlTorRoute {
    private ControlTorRoute(){}
    static boolean trusted(Context c,String pkg){
        try{
            PackageInfo p=c.getPackageManager().getPackageInfo(pkg,PackageManager.GET_SIGNING_CERTIFICATES);
            Signature[] signers=p.signingInfo.getApkContentsSigners();
            if(signers.length!=1)return false;
            byte[] digest=MessageDigest.getInstance("SHA-256").digest(signers[0].toByteArray());
            StringBuilder hex=new StringBuilder();for(byte b:digest)hex.append(String.format(Locale.ROOT,"%02x",b&255));
            return TorRoutePolicy.signer(pkg,hex.toString());
        }catch(Exception unavailable){return false;}
    }
    static void offer(Activity owner,String onion){
        if(onion!=null&&TorRoutePolicy.onionAddress(onion)==null)return;
        if(!trusted(owner,TorRoutePolicy.BROWSER)){
            new AlertDialog.Builder(owner).setTitle("Verified Tor Browser required")
                .setMessage("Install the stable Tor Project release from its official source. This link will not be sent to a normal browser or stored for later.")
                .setPositiveButton("Official download",(d,w)->official(owner,false)).setNegativeButton("Cancel",null).show();return;
        }
        new AlertDialog.Builder(owner).setTitle("Open in Tor Browser")
            .setMessage("Tor Browser runs separately. Connect and verify its Tor circuit there. Control will not share cookies, vault entries or browsing history.")
            .setPositiveButton("Open",(d,w)->{
                if(!trusted(owner,TorRoutePolicy.BROWSER))return;
                try{
                    Intent i=onion==null?owner.getPackageManager().getLaunchIntentForPackage(TorRoutePolicy.BROWSER):
                        new Intent(Intent.ACTION_VIEW,Uri.parse(onion)).setPackage(TorRoutePolicy.BROWSER);
                    if(i==null)throw new IllegalStateException();owner.startActivity(i);
                }catch(Exception failure){new AlertDialog.Builder(owner).setMessage("Verified Tor Browser could not be opened. No fallback attempted.").setPositiveButton("Close",null).show();}
            }).setNegativeButton("Cancel",null).show();
    }
    static void panel(Activity owner){
        boolean browser=trusted(owner,TorRoutePolicy.BROWSER),vpn=trusted(owner,TorRoutePolicy.VPN);
        String[] choices={"Open embedded Tor · restricted browser",browser?"Open verified Tor Browser":"Get official Tor Browser",vpn?"Open verified Tor VPN Beta":"Get official Tor VPN Beta"};
        new AlertDialog.Builder(owner).setTitle("Tor network")
            .setItems(choices,(d,w)->{
                if(w==0){
                    owner.startActivity(new Intent(owner,TorActivity.class));return;
                }
                if(w==1){offer(owner,null);return;}
                new AlertDialog.Builder(owner).setTitle("Tor VPN Beta")
                    .setMessage("Experimental only: the Tor Project warns that it may leak information. Do not use for sensitive activity. Android permits one active VPN; Control will not silently replace another tunnel.")
                    .setPositiveButton(vpn?"Open app":"Official download",(a,b)->{
                        if(!vpn){official(owner,true);return;}
                        if(!trusted(owner,TorRoutePolicy.VPN))return;
                        try{
                            android.net.ConnectivityManager cm=owner.getSystemService(android.net.ConnectivityManager.class);
                            android.net.Network n=cm==null?null:cm.getActiveNetwork();
                            android.net.NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);
                            if(caps!=null&&caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN)){
                                new AlertDialog.Builder(owner).setMessage("Disconnect the current Android VPN before switching.").setPositiveButton("Close",null).show();return;
                            }
                            Intent i=owner.getPackageManager().getLaunchIntentForPackage(TorRoutePolicy.VPN);if(i!=null)owner.startActivity(i);
                        }catch(Exception ignored){}
                    }).setNegativeButton("Cancel",null).show();
            }).setNegativeButton("Close",null).show();
    }
    private static void official(Activity owner,boolean vpn){
        try{owner.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(vpn?"https://download.torproject.org/tor-vpn-for-android/":"https://download.torproject.org/tor-browser-for-android/")));}catch(Exception ignored){}
    }
}
