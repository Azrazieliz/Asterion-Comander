package com.asterion.control;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import org.json.JSONObject;

/** Phone-initiated private HTTPS relay; no public inbound phone port. */
final class TransportConnectivity {
  private TransportConnectivity(){}
  static JSONObject report(Context ctx)throws Exception {
    ConnectivityManager cm=(ConnectivityManager)ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
    JSONObject out=new JSONObject().put("network","offline")
      .put("connected",false).put("validated",false).put("metered",true)
      .put("https_outbound_only",true).put("requires_home_wifi",false)
      .put("requires_pc_for_phone_commands",false);
    if(cm==null)return out;
    Network current=cm.getActiveNetwork();
    NetworkCapabilities caps=current==null?null:cm.getNetworkCapabilities(current);
    if(caps==null)return out;
    String mode=caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)?"vpn":
      caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)?"cellular":
      caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)?"wifi":
      caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)?"ethernet":"other";
    return out.put("network",mode)
      .put("connected",caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
      .put("validated",caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED))
      .put("metered",cm.isActiveNetworkMetered())
      .put("data_saver_restricted",
        cm.getRestrictBackgroundStatus()==ConnectivityManager.RESTRICT_BACKGROUND_STATUS_ENABLED);
  }
  static boolean usable(Context ctx){
    try{return report(ctx).optBoolean("validated",false);}
    catch(Exception ignored){return false;}
  }
}
