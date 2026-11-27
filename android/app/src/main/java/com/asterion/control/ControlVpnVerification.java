package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.LinkProperties;
import android.net.RouteInfo;
import java.net.Inet6Address;
import java.net.InetAddress;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Locale;

/**
 * A deliberate, user-triggered public-IP / indicative throughput check.
 * This NEVER asserts successful VPN routing merely because VpnService is UP.
 * Uses public HTTPS endpoints; the external providers see this device's egress
 * address, so this operation is never performed silently in the background.
 * No bearer tokens, WireGuard keys, payloads or private app files are sent.
 */
final class ControlVpnVerification {
    private static final String PREFS="control_vpn_quality_v1";
    private static final long BASELINE_MAX_AGE_MS=24L*60*60*1000;
    private static final int SPEED_BYTES=1_048_576;
    private ControlVpnVerification(){}

    private static String fetchPublicIp(Network network,boolean ipv6) throws Exception {
        HttpURLConnection conn=null;
        try {
            conn=(HttpURLConnection)network.openConnection(new URL(
                ipv6?"https://api6.ipify.org?format=json":"https://api.ipify.org?format=json"));
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(7000);
            conn.setInstanceFollowRedirects(false);
            conn.setUseCaches(false);
            conn.setRequestProperty("Accept","application/json");
            if(conn.getResponseCode()!=200)
                throw new IllegalStateException("public_ip_http_"+conn.getResponseCode());
            try(InputStream stream=conn.getInputStream()){
                byte[] chunk=new byte[1024];
                ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                int n;
                while((n=stream.read(chunk))!=-1){
                    if(bytes.size()+n>2048)
                        throw new IllegalStateException("ip_result_too_large");
                    bytes.write(chunk,0,n);
                }
                String ip=new JSONObject(
                    new String(bytes.toByteArray(),StandardCharsets.UTF_8))
                    .getString("ip");
                if(ipv6){
                    if(!ip.matches("[0-9a-fA-F:]+")||!ip.contains(":"))throw new IllegalStateException("invalid_ipv6_response");
                    InetAddress addr=InetAddress.getByName(ip);
                    if(!(addr instanceof Inet6Address))throw new IllegalStateException("invalid_ipv6_family");
                    return addr.getHostAddress();
                }
                if(!ip.matches("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}"))
                    throw new IllegalStateException("invalid_ipv4_response");
                for(String piece:ip.split("\\.")){
                    int octet=Integer.parseInt(piece);
                    if(octet>255)throw new IllegalStateException("invalid_ipv4_octet");
                }
                return ip;
            }
        }finally{if(conn!=null)conn.disconnect();}
    }

    private static double sampleSpeedMbps(Network network,int trial) throws Exception {
        HttpURLConnection conn=null;
        try {
            conn=(HttpURLConnection)network.openConnection(new URL(
                "https://speed.cloudflare.com/__down?bytes="+SPEED_BYTES+
                "&asterion_trial="+trial));
            conn.setConnectTimeout(6000);
            conn.setReadTimeout(15000);
            conn.setInstanceFollowRedirects(false);
            conn.setUseCaches(false);
            conn.setRequestProperty("Cache-Control","no-store");
            if(conn.getResponseCode()!=200)
                throw new IllegalStateException("speed_http_"+conn.getResponseCode());
            long start=SystemClock.elapsedRealtimeNanos();
            int bytes=0;
            try(InputStream stream=conn.getInputStream()){
                byte[] buffer=new byte[32768];
                int n;
                while((n=stream.read(buffer))!=-1){
                    bytes+=n;
                    if(bytes>SPEED_BYTES*2)
                        throw new IllegalStateException("speed_payload_too_large");
                }
            }
            long elapsed=SystemClock.elapsedRealtimeNanos()-start;
            if(bytes<SPEED_BYTES*0.95 || elapsed<=0)
                throw new IllegalStateException("speed_sample_incomplete");
            return (bytes*8.0)/(elapsed/1e9)/1_000_000.0;
        }finally{if(conn!=null)conn.disconnect();}
    }

    private static double medianSpeed(Network network) throws Exception {
        double[] values=new double[3];
        for(int i=0;i<3;i++)values[i]=sampleSpeedMbps(network,i);
        Arrays.sort(values);
        return values[1];
    }

    private static final class RouteSnapshot{
        final Network network;final boolean vpn,validated,default4,default6,privateDns;final String transport;final int dns;
        RouteSnapshot(Context context)throws Exception{
            ConnectivityManager cm=(ConnectivityManager)context.getSystemService(Context.CONNECTIVITY_SERVICE);
            if(cm==null||(network=cm.getActiveNetwork())==null)throw new IllegalStateException("No active Android network");
            NetworkCapabilities caps=cm.getNetworkCapabilities(network);
            LinkProperties link=cm.getLinkProperties(network);
            if(caps==null||link==null)throw new IllegalStateException("Network route evidence unavailable");
            vpn=caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
            validated=caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED);
            boolean wifi=caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI),cell=caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR),ethernet=caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET);
            int physical=(wifi?1:0)+(cell?1:0)+(ethernet?1:0);
            transport=physical!=1?"unknown":wifi?"wifi":cell?"cellular":"ethernet";
            boolean v4=false,v6=false;
            for(RouteInfo route:link.getRoutes())if(route.isDefaultRoute()){
                if(route.getDestination().getAddress() instanceof Inet6Address)v6=true;else v4=true;
            }
            default4=v4;default6=v6;dns=link.getDnsServers().size();privateDns=link.isPrivateDnsActive();
        }
        boolean stable(RouteSnapshot other){return network.equals(other.network)&&vpn==other.vpn&&validated==other.validated&&
            transport.equals(other.transport)&&default4==other.default4&&default6==other.default6&&dns==other.dns&&privateDns==other.privateDns;}
    }

    /** Must run off UI thread and only after an explicit owner button press. */
    static JSONObject measure(Context context, boolean baseline) throws Exception {
        RouteSnapshot beforeRoute=new RouteSnapshot(context);
        JSONObject vpn=ControlPrivateVpn.status(context);
        boolean active=vpn.optBoolean("active",false);
        if(baseline&&(active||beforeRoute.vpn))throw new IllegalStateException("Disconnect active VPN before baseline");
        if(!baseline&&(!active||!beforeRoute.vpn))throw new IllegalStateException("No active Asterion WireGuard network route");
        String ip=fetchPublicIp(beforeRoute.network,false);
        String ipv6="",ipv6State="observed";
        try{ipv6=fetchPublicIp(beforeRoute.network,true);}catch(Exception unavailable){ipv6State="unavailable";}
        boolean dnsResolved=false;
        try{dnsResolved=beforeRoute.network.getAllByName("api.ipify.org").length>0;}catch(Exception ignored){}
        double median=medianSpeed(beforeRoute.network);
        RouteSnapshot afterRoute=new RouteSnapshot(context);
        JSONObject afterVpn=ControlPrivateVpn.status(context);
        if(!beforeRoute.stable(afterRoute)||afterVpn.optBoolean("active",false)!=active)
            throw new IllegalStateException("Network changed during measurement; repeat the test");
        long now=System.currentTimeMillis();
        boolean peer=afterVpn.optBoolean("peer_reachability_verified",false);
        SharedPreferences prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
        JSONObject result=new JSONObject()
            .put("ok",true)
            .put("test_scope","owner_requested_bound_network_ipv4_ipv6_route_and_short_https_throughput")
            .put("public_ipv4",ip).put("public_ipv6",ipv6).put("ipv6_probe",ipv6State)
            .put("physical_transport",beforeRoute.transport)
            .put("android_vpn_route_observed",beforeRoute.vpn)
            .put("android_network_validated",beforeRoute.validated)
            .put("default_ipv4_route_observed",beforeRoute.default4)
            .put("default_ipv6_route_observed",beforeRoute.default6)
            .put("configured_dns_server_count",beforeRoute.dns)
            .put("android_private_dns_active",beforeRoute.privateDns)
            .put("dns_resolution_through_selected_network",dnsResolved)
            .put("external_dns_leak_test_verified",false)
            .put("ipv6_leak_free_verified",false)
            .put("median_sample_mbps",Math.round(median*100.0)/100.0)
            .put("vpn_backend_active",active)
            .put("peer_reachability_verified",peer)
            .put("sustained_25_percent_loss_verified",false)
            .put("provider_country_verified",false)
            .put("peer_trust_verified",false)
            .put("measurement_timestamp_ms",now);
        if(baseline){
            if(!prefs.edit().putString("untunnelled_ipv4",ip).putString("untunnelled_ipv6",ipv6)
                    .putString("baseline_transport",beforeRoute.transport)
                    .putLong("baseline_timestamp_ms",now)
                    .putString("baseline_mbps",Double.toString(median)).commit())
                throw new IllegalStateException("baseline_persistence_failed");
            return result.put("phase","untunnelled_baseline")
                .put("ip_replacement_verified",false);
        }
        String oldIp=prefs.getString("untunnelled_ipv4","");
        String oldIpv6=prefs.getString("untunnelled_ipv6","");
        long age=now-prefs.getLong("baseline_timestamp_ms",0);
        boolean valid=!oldIp.isEmpty()&&VpnEvidencePolicy.comparable(
            prefs.getString("baseline_transport","unknown"),beforeRoute.transport,age,BASELINE_MAX_AGE_MS);
        boolean route=beforeRoute.vpn&&beforeRoute.validated;
        boolean different=VpnEvidencePolicy.exitReplaced(valid,route,peer,oldIp,ip);
        result.put("phase","tunnel_check").put("baseline_available",valid)
            .put("ip_replacement_verified",different)
            .put("ip_unchanged_against_baseline",valid&&oldIp.equals(ip))
            .put("ipv6_assessment",VpnEvidencePolicy.ipv6Assessment(valid,route,peer,oldIpv6,ipv6));
        if(valid){
            result.put("previous_public_ipv4",oldIp);
            if(!oldIpv6.isEmpty())result.put("previous_public_ipv6",oldIpv6);
            double previous=Double.parseDouble(prefs.getString("baseline_mbps","0"));
            double ratio=VpnEvidencePolicy.ratio(previous,median);
            result.put("short_sample_speed_ratio",Math.round(ratio*100.0)/100.0)
                .put("short_sample_within_25_percent_loss",route&&peer&&previous>0&&ratio>=0.75);
        }
        return result;
    }

    // Owner-selected longer throughput measurement. A bounded data cap is
    // deliberately not evidence of a complete duration on a very fast network.
    private static final long SUSTAINED_NS=30_000_000_000L;
    private static final long SUSTAINED_CAP=512L*1024*1024;
    private static final int SUSTAINED_CHUNK=8*1024*1024;
    private static final long SUSTAINED_BASELINE_AGE=15L*60*1000;
    private static final java.util.concurrent.atomic.AtomicBoolean MEASURING=
        new java.util.concurrent.atomic.AtomicBoolean(false);

    static JSONObject measureSustained(Context context,boolean baseline)throws Exception{
        if(!MEASURING.compareAndSet(false,true))throw new IllegalStateException("vpn_measurement_already_active");
        try{
            RouteSnapshot initial=new RouteSnapshot(context);
            JSONObject vpn=ControlPrivateVpn.status(context);
            boolean active=vpn.optBoolean("active",false);
            if(!initial.validated||!VpnEvidencePolicy.knownTransport(initial.transport))
                throw new IllegalStateException("validated_known_network_required");
            if(baseline?(active||initial.vpn):(!active||!initial.vpn))
                throw new IllegalStateException("incorrect_vpn_measurement_phase");
            SharedPreferences prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
            if(baseline&&!prefs.edit().remove("long_timestamp_ms").commit())
                throw new IllegalStateException("old_baseline_invalidation_failed");
            String ip=fetchPublicIp(initial.network,false);
            byte[] buffer=new byte[32768];
            long began=SystemClock.elapsedRealtimeNanos(),bytes=0;
            int attempts=0,finished=0;
            while(SystemClock.elapsedRealtimeNanos()-began<SUSTAINED_NS&&bytes<SUSTAINED_CAP){
                if(!initial.stable(new RouteSnapshot(context)))throw new IllegalStateException("network_changed");
                int wanted=(int)Math.min(SUSTAINED_CHUNK,SUSTAINED_CAP-bytes);
                HttpURLConnection conn=(HttpURLConnection)initial.network.openConnection(new URL(
                    "https://speed.cloudflare.com/__down?bytes="+wanted+"&asterion_trial="+
                    Long.toUnsignedString(began)+"-"+attempts++));
                int received=0;
                try{
                    conn.setConnectTimeout(5000);conn.setReadTimeout(5000);
                    conn.setInstanceFollowRedirects(false);conn.setUseCaches(false);
                    conn.setRequestProperty("Cache-Control","no-store");
                    conn.setRequestProperty("Accept-Encoding","identity");
                    if(conn.getResponseCode()!=200)throw new IllegalStateException("throughput_http_"+conn.getResponseCode());
                    try(InputStream input=conn.getInputStream()){
                        while(received<wanted&&SystemClock.elapsedRealtimeNanos()-began<SUSTAINED_NS){
                            int n=input.read(buffer,0,Math.min(buffer.length,wanted-received));
                            if(n<0)break;
                            if(n==0)throw new IllegalStateException("empty_throughput_read");
                            received+=n;bytes+=n;
                        }
                    }
                    if(received==wanted)finished++;
                    else if(SystemClock.elapsedRealtimeNanos()-began<SUSTAINED_NS)
                        throw new IllegalStateException("throughput_payload_incomplete");
                }finally{conn.disconnect();}
            }
            long elapsed=SystemClock.elapsedRealtimeNanos()-began;
            JSONObject after=ControlPrivateVpn.status(context);
            String endIp=fetchPublicIp(initial.network,false);
            boolean stable=initial.stable(new RouteSnapshot(context))&&ip.equals(endIp)&&
                active==after.optBoolean("active",false);
            boolean peer=after.optBoolean("peer_reachability_verified",false);
            boolean complete=VpnEvidencePolicy.completeWindow(bytes,elapsed,SUSTAINED_NS,SUSTAINED_CAP,finished,stable);
            double mbps=elapsed>0?bytes*8.0/(elapsed/1e9)/1e6:0;
            long now=System.currentTimeMillis();
            JSONObject result=new JSONObject().put("ok",true)
                .put("test_scope","owner_requested_30_second_bound_https_throughput")
                .put("phase",baseline?"untunnelled_sustained_baseline":"tunnel_sustained_check")
                .put("sample_bytes",bytes).put("sample_seconds",elapsed/1e9)
                .put("complete_window",complete).put("completed_payloads",finished)
                .put("public_ipv4",ip).put("route_and_ipv4_stable",stable)
                .put("physical_transport",initial.transport)
                .put("peer_reachability_verified",peer).put("sample_mbps",mbps)
                .put("external_dns_leak_test_verified",false)
                .put("ipv6_leak_free_verified",false)
                .put("provider_country_verified",false)
                .put("sustained_25_percent_loss_verified",false);
            if(baseline){
                if(complete&&!prefs.edit().putString("long_transport",initial.transport)
                    .putString("long_ipv4",ip).putString("long_mbps",Double.toString(mbps))
                    .putLong("long_timestamp_ms",now).commit())throw new IllegalStateException("baseline_persistence_failed");
                return result.put("baseline_saved",complete);
            }
            String previous=prefs.getString("long_ipv4","");
            double old=Double.parseDouble(prefs.getString("long_mbps","0"));
            boolean comparable=VpnEvidencePolicy.comparable(prefs.getString("long_transport","unknown"),
                initial.transport,now-prefs.getLong("long_timestamp_ms",0),SUSTAINED_BASELINE_AGE)&&
                !previous.isEmpty()&&Double.isFinite(old)&&old>0;
            boolean replaced=VpnEvidencePolicy.exitReplaced(comparable,initial.vpn&&initial.validated,peer,previous,ip);
            double ratio=VpnEvidencePolicy.ratio(old,mbps);
            return result.put("baseline_available",comparable).put("ip_replacement_verified",replaced)
                .put("speed_ratio",comparable?ratio:JSONObject.NULL)
                .put("matched_30_second_sample_threshold_met",complete&&comparable&&replaced&&ratio>=0.75);
        }finally{MEASURING.set(false);}
    }
}
