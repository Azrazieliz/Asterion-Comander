package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
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

    private static String fetchPublicIpv4() throws Exception {
        HttpURLConnection conn=null;
        try {
            conn=(HttpURLConnection)new URL(
                "https://api.ipify.org?format=json").openConnection();
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

    private static double sampleSpeedMbps(int trial) throws Exception {
        HttpURLConnection conn=null;
        try {
            conn=(HttpURLConnection)new URL(
                "https://speed.cloudflare.com/__down?bytes="+SPEED_BYTES+
                "&asterion_trial="+trial).openConnection();
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

    private static double medianSpeed() throws Exception {
        double[] values=new double[3];
        for(int i=0;i<3;i++)values[i]=sampleSpeedMbps(i);
        Arrays.sort(values);
        return values[1];
    }

    /** Must run off UI thread and only after an explicit owner button press. */
    static JSONObject measure(Context context, boolean baseline) throws Exception {
        JSONObject vpn=ControlPrivateVpn.status(context);
        boolean active=vpn.optBoolean("active",false);
        if(baseline&&active)throw new IllegalStateException(
            "Disconnect VPN before measuring normal connection");
        if(!baseline&&!active)throw new IllegalStateException(
            "No active WireGuard tunnel to verify");
        String ip=fetchPublicIpv4();
        double median=medianSpeed();
        long now=System.currentTimeMillis();
        SharedPreferences prefs=context.getSharedPreferences(PREFS,Context.MODE_PRIVATE);
        JSONObject result=new JSONObject()
            .put("ok",true)
            .put("test_scope","user_requested_ip_and_short_https_throughput")
            .put("public_ipv4",ip)
            .put("median_sample_mbps",Math.round(median*100.0)/100.0)
            .put("vpn_backend_active",active)
            .put("sustained_25_percent_loss_verified",false)
            .put("provider_country_verified",false)
            .put("peer_trust_verified",false)
            .put("measurement_timestamp_ms",now);
        if(baseline){
            if(!prefs.edit().putString("untunnelled_ipv4",ip)
                    .putLong("baseline_timestamp_ms",now)
                    .putString("baseline_mbps",Double.toString(median)).commit())
                throw new IllegalStateException("baseline_persistence_failed");
            return result.put("phase","untunnelled_baseline")
                .put("ip_replacement_verified",false);
        }
        String oldIp=prefs.getString("untunnelled_ipv4","");
        long age=now-prefs.getLong("baseline_timestamp_ms",0);
        boolean valid=!oldIp.isEmpty() && age>=0 && age<BASELINE_MAX_AGE_MS;
        boolean different=valid&&!oldIp.equals(ip);
        result.put("phase","tunnel_check")
            .put("baseline_available",valid)
            .put("ip_replacement_verified",different)
            .put("ip_unchanged_against_baseline",valid&&!different);
        if(valid){
            result.put("previous_public_ipv4",oldIp);
            double before=Double.parseDouble(prefs.getString("baseline_mbps","0"));
            double ratio=before>0?median/before:0.0;
            result.put("short_sample_speed_ratio",Math.round(ratio*100.0)/100.0)
                .put("short_sample_within_25_percent_loss",before>0&&ratio>=0.75);
        }
        return result;
    }
}
