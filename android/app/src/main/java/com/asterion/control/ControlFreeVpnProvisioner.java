package com.asterion.control;

import android.app.Activity;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import com.wireguard.crypto.KeyPair;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetAddress;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/**
 * Free, no-manual-profile VPN provisioning using Cloudflare WARP's documented
 * open-source community client contract (wgcf v2, MIT).
 * HTTPS registration runs ON THE PHONE; the private Curve25519 key never
 * traverses the Control WSS, Windows, GitHub, model or logs.
 *
 * This provider API is UNOFFICIAL and may change or reject third parties.
 * Register only following an explicit owner tap agreeing to provider terms;
 * Android VpnService consent remains non-bypassable. Use the existing official
 * WireGuard GoBackend; no additional VPN/tunnel engine or paid service.
 *
 * The provider selects its own exit location; changing country or rotating
 * the public IP is not guaranteed and must not be falsely advertised.
 */
final class ControlFreeVpnProvisioner {
    private static final String SERVICE="https://api.cloudflareclient.com/v0a5641/reg";
    private static final String CLIENT="a-6.38.9-5641";
    private static final String USER_AGENT="1.1.1.1/6.38.9-5641 (Android 16.0.0)";
    private static final AtomicBoolean BUSY=new AtomicBoolean(false);
    private static final ExecutorService IO=Executors.newSingleThreadExecutor(r->{
        Thread t=new Thread(r,"asterion-free-wireguard-enroll");
        t.setDaemon(true);
        return t;
    });
    private static final Handler UI=new Handler(Looper.getMainLooper());
    private ControlFreeVpnProvisioner(){}
    static boolean busy(){return BUSY.get();}

    /**
     * Invoked only by the foreground owner after provider terms acceptance.
     * Caller must use its own Android consent stage before tunnel activation.
     */
    static void enroll(Activity owner,Consumer<String> feedback,Runnable connectedReady){
        if(owner!=MainActivity.foregroundActivity()||owner.isFinishing())
            throw new SecurityException("Foreground owner confirmation required");
        if(!BUSY.compareAndSet(false,true)){
            feedback.accept("VPN enrollment is already active");
            return;
        }
        final android.content.Context context=owner.getApplicationContext();
        final String attempt;
        try{attempt=ControlPrivateVpn.reserveProviderEnrollment(owner);}
        catch(Exception e){
            BUSY.set(false);
            feedback.accept("Cannot start VPN enrollment: "+e.getClass().getSimpleName());
            return;
        }
        feedback.accept("Registering the phone with the free VPN provider…");
        IO.execute(()->{
            String failure=null;
            try{
                String profile=registerOnPhone();
                // Persist the owner-authorized result even if the UI is paused.
                // A manual import or newer configuration supersedes this attempt.
                ControlPrivateVpn.completeProviderEnrollment(context,attempt,profile);
            }catch(Exception e){
                failure=classify(e);
                ControlPrivateVpn.failProviderEnrollment(context,attempt);
            }finally{BUSY.set(false);}
            final String failed=failure;
            UI.post(()->{
                if(owner.isFinishing()||owner.isDestroyed()||owner!=MainActivity.foregroundActivity())return;
                if(failed!=null){
                    feedback.accept("Free VPN enrollment unsuccessful or unconfirmed: "+failed);
                    return;
                }
                feedback.accept("Free VPN profile securely provisioned on this phone.");
                connectedReady.run();
            });
        });
    }
    private static String classify(Exception e){
        String message=e.getMessage()==null?"":e.getMessage();
        if(message.startsWith("provider_http_"))return message;
        if(message.startsWith("provider_invalid_"))return message;
        return e.getClass().getSimpleName();
    }
    private static String requiredKey(String s)throws Exception{
        if(s==null||!s.matches("[A-Za-z0-9+/]{43}="))
            throw new IllegalStateException("provider_invalid_public_key");
        return s;
    }
    private static String ipAddress(String ip)throws Exception{
        if(ip==null||ip.length()>90||ip.contains("%")||
           !ip.matches("[a-fA-F0-9:.]+"))
            throw new IllegalStateException("provider_invalid_tunnel_address");
        InetAddress resolved=android.net.InetAddresses.parseNumericAddress(ip);
        if(resolved.isAnyLocalAddress()||resolved.isLoopbackAddress()||
            resolved.isMulticastAddress())
            throw new IllegalStateException("provider_invalid_address_range");
        return ip;
    }
    private static String endpoint(JSONObject obj)throws Exception{
        String supplied=obj.optString("host","");
        if(!supplied.isEmpty()){
            if(supplied.length()>230||!supplied.matches("[a-zA-Z0-9.:-]+|\\[[a-fA-F0-9:]+\\]:[0-9]+"))
                throw new IllegalStateException("provider_invalid_endpoint");
            // A provider-published host can include its own port.
            if(!supplied.contains(":"))supplied=supplied+":2408";
            java.net.URI parsed=java.net.URI.create("https://"+supplied);
            if(parsed.getHost()==null||parsed.getPort()<1||parsed.getPort()>65535||parsed.getRawUserInfo()!=null||!parsed.getRawPath().isEmpty())throw new IllegalStateException("provider_invalid_endpoint");
            return supplied;
        }
        String ip=ipAddress(obj.optString("v4",""));
        int port=2408;
        JSONArray ports=obj.optJSONArray("ports");
        if(ports!=null&&ports.length()>0)port=ports.getInt(0);
        if(port<1||port>65535)
            throw new IllegalStateException("provider_invalid_port");
        return ip+":"+port;
    }
    private static String registerOnPhone()throws Exception{
        KeyPair keys=new KeyPair();
        JSONObject request=new JSONObject()
            .put("fcm_token","")
            .put("install_id","")
            .put("key",keys.getPublicKey().toBase64())
            .put("locale","en_US")
            .put("serial_number","")
            .put("os_version","16.0.0")
            .put("model",Build.MODEL.length()>60?
                Build.MODEL.substring(0,60):Build.MODEL)
            .put("key_type","curve25519")
            .put("tunnel_type","wireguard")
            .put("tos",Instant.now().toString());
        HttpURLConnection conn=(HttpURLConnection)new URL(SERVICE).openConnection();
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(20000);
        conn.setInstanceFollowRedirects(false);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type","application/json; charset=UTF-8");
        conn.setRequestProperty("Accept","application/json");
        conn.setRequestProperty("User-Agent",USER_AGENT);
        conn.setRequestProperty("CF-Client-Version",CLIENT);
        try{
            byte[] bytes=request.toString().getBytes(StandardCharsets.UTF_8);
            conn.setFixedLengthStreamingMode(bytes.length);
            try(OutputStream stream=conn.getOutputStream()){stream.write(bytes);}
            int code=conn.getResponseCode();
            if(code!=200&&code!=201)throw new IllegalStateException(
                "provider_http_"+code);
            ByteArrayOutputStream bytesRead=new ByteArrayOutputStream();
            try(InputStream input=conn.getInputStream()){
                byte[] chunk=new byte[8192];
                for(int read;(read=input.read(chunk))!=-1;){
                    if(bytesRead.size()+read>200000)
                        throw new IllegalStateException("provider_invalid_response_size");
                    bytesRead.write(chunk,0,read);
                }
            }
            JSONObject reply=new JSONObject(bytesRead.toString("UTF-8"));
            JSONObject remote=reply.getJSONObject("config");
            JSONObject iface=remote.getJSONObject("interface").getJSONObject("addresses");
            JSONArray peers=remote.getJSONArray("peers");
            if(peers.length()<1)throw new IllegalStateException("provider_invalid_peer_list");
            JSONObject first=peers.getJSONObject(0);
            String ipv4=ipAddress(iface.getString("v4"));
            String ipv6=iface.optString("v6","");
            if(ipv6.isEmpty())throw new IllegalStateException("provider_invalid_missing_ipv6_route");
            String addresses=ipv4+"/32";
            String routes="0.0.0.0/0";
            String dns="1.1.1.1,1.0.0.1";
            if(!ipv6.isEmpty()){
                addresses+=", "+ipAddress(ipv6)+"/128";
                routes+=", ::/0";
                dns+=", 2606:4700:4700::1111, 2606:4700:4700::1001";
            }
            StringBuilder conf=new StringBuilder();
            conf.append("[Interface]\nPrivateKey = ")
                .append(keys.getPrivateKey().toBase64())
                .append("\nAddress = ").append(addresses)
                .append("\nDNS = ").append(dns)
                .append("\nMTU = 1280\n\n[Peer]\nPublicKey = ")
                .append(requiredKey(first.getString("public_key")))
                .append("\nAllowedIPs = ").append(routes)
                .append("\nEndpoint = ")
                .append(endpoint(first.getJSONObject("endpoint")))
                .append("\nPersistentKeepalive = 25\n");
            // Reuse existing WireGuard parser and Keystore at caller: no
            // local config export and no hidden provider secrets in logs.
            return conf.toString();
        }finally{conn.disconnect();}
    }
}
