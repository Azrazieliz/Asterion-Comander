package com.asterion.control;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.VpnService;
import android.os.Handler;
import android.os.Looper;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import org.json.JSONObject;
import com.wireguard.android.backend.GoBackend;
import com.wireguard.android.backend.Tunnel;
import com.wireguard.config.Config;
import com.wireguard.config.InetNetwork;
import com.wireguard.config.Peer;
import java.io.ByteArrayInputStream;
import java.net.InetAddress;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Optional owner-controlled WireGuard private tunnel. No always-on activation,
 * external relay, shared key, traffic interception or silent VPN replacement.
 *
 * Uses the official WireGuard userspace backend. Android's VpnService consent
 * is mandatory; the existing native secure Control connection remains primary.
 * Config contains secrets and is encrypted in Android Keystore at rest.
 */
final class ControlPrivateVpn {
  private static final String PREF="owner_private_vpn_v1";
  private static final String KEY_ALIAS="asterion_control_wg_config_v1";
  private static final ExecutorService WORKER=Executors.newSingleThreadExecutor();
  private static final Handler MAIN=new Handler(Looper.getMainLooper());
  private static volatile GoBackend backend;
  private static volatile String connectionState="off";
  private static volatile String lastErrorCode="";
  private static volatile String observedPublicIp="";
  private static volatile String egressVerification="not_checked";
  private static volatile boolean publicIpChanged=false;
  private static volatile long egressCheckedAtMs=0;
  private static final Tunnel TUNNEL=new Tunnel(){
    @Override public String getName(){return "AsterionPrivate";}
    @Override public void onStateChange(State state){
      connectionState=state==State.UP?"tunnel_up":"off";
    }
  };
  private ControlPrivateVpn(){}
  private static SharedPreferences pref(Context c){
    return c.getSharedPreferences(PREF,Context.MODE_PRIVATE);
  }
  private static void requireLocal(Activity a){
    if(a!=MainActivity.foregroundActivity()||a.isFinishing())
      throw new SecurityException("Foreground owner approval required");
  }
  private static SecretKey key() throws Exception {
    KeyStore store=KeyStore.getInstance("AndroidKeyStore");
    store.load(null);
    if(store.containsAlias(KEY_ALIAS))
      return (SecretKey)store.getKey(KEY_ALIAS,null);
    KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,
      "AndroidKeyStore");
    generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
      KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
      .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
      .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
      .setRandomizedEncryptionRequired(true).build());
    return generator.generateKey();
  }
  private static String encrypt(String clear)throws Exception{
    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.ENCRYPT_MODE,key());
    String iv=Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP);
    String ciphertext=Base64.encodeToString(cipher.doFinal(
      clear.getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP);
    return iv+":"+ciphertext;
  }
  private static String decrypt(Context c)throws Exception{
    String encoded=pref(c).getString("encrypted_configuration","");
    String[] fields=encoded.split(":",-1);
    if(fields.length!=2||fields[0].isEmpty()||fields[1].isEmpty())
      throw new IllegalStateException("No usable encrypted WireGuard config");
    byte[] nonce=Base64.decode(fields[0],Base64.DEFAULT);
    if(nonce.length!=12)throw new IllegalStateException("Invalid encrypted VPN nonce");
    Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
    cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,nonce));
    byte[] bytes=cipher.doFinal(Base64.decode(fields[1],Base64.DEFAULT));
    return new String(bytes,StandardCharsets.UTF_8);
  }
  private static Config parseAndValidate(String text,boolean allowFullTunnel)throws Exception{
    if(text==null||text.length()<80||text.length()>16000)
      throw new IllegalArgumentException("Configuration length invalid");
    Config config=Config.parse(new ByteArrayInputStream(
      text.getBytes(StandardCharsets.UTF_8)));
    if(config.getPeers().isEmpty()||config.getPeers().size()>8)
      throw new IllegalArgumentException("Expected one to eight WireGuard peers");
    int routes=0;
    for(Peer peer:config.getPeers()){
      for(InetNetwork allowed:peer.getAllowedIps()){
        routes++;
        if(!allowFullTunnel&&allowed.getMask()==0)
          throw new IllegalArgumentException(
            "Default/full-tunnel route requires separate owner consent");
      }
    }
    if(routes==0)throw new IllegalArgumentException("No permitted tunnel routes");
    return config;
  }
  static synchronized void importLocally(Activity owner,String text,boolean allowFullTunnel)
      throws Exception{
    requireLocal(owner);
    parseAndValidate(text,allowFullTunnel);
    // Store ONLY encrypted configuration. No private keys in logs, source,
    // remote commands, public storage, exception output or UI status.
    String encrypted=encrypt(text);
    observedPublicIp="";
    publicIpChanged=false;
    egressVerification="not_checked";
    egressCheckedAtMs=0;
    if(!pref(owner).edit().putString("encrypted_configuration",encrypted)
       .putBoolean("allow_full_tunnel",allowFullTunnel).commit())
      throw new IllegalStateException("Could not save encrypted config");
    ControlEventJournal.write(owner,"vpn_config_imported","owner_ui",
      "completed",allowFullTunnel?"full_tunnel":"private_routes_only",0);
  }
  static Intent consentIntent(Activity owner){
    requireLocal(owner);
    return VpnService.prepare(owner); // Returns non-null for real Android OS dialog.
  }
  static void connect(Activity owner,Consumer<String> report){
    requireLocal(owner);
    final Context context=owner.getApplicationContext();
    if(VpnService.prepare(owner)!=null){
      report.accept("Android VPN approval required");return;
    }
    connectionState="starting";
    egressVerification="checking";
    publicIpChanged=false;
    observedPublicIp="";
    WORKER.submit(()->{
      long started=android.os.SystemClock.elapsedRealtime();
      // This HTTPS observer is third-party and necessarily sees the public
      // source IP. It runs ONLY for an owner-initiated VPN connection.
      String before="";
      try {before=PublicExitIp.probe();}
      catch(Exception ignored){} // Probe unavailable is not a tunnel failure.
      try{
        Config config=parseAndValidate(decrypt(context),
          pref(context).getBoolean("allow_full_tunnel",false));
        GoBackend instance=backend;
        if(instance==null){
          instance=new GoBackend(context);
          backend=instance;
        }
        Tunnel.State after=instance.setState(TUNNEL,Tunnel.State.UP,config);
        if(after!=Tunnel.State.UP)
          throw new IllegalStateException("VPN engine did not reach UP");
        connectionState="tunnel_up";lastErrorCode="";
        String after="";
        try {after=PublicExitIp.probe();}
        catch(Exception ignored){}
        if(!after.isEmpty()){
          observedPublicIp=after;
          publicIpChanged=PublicExitIp.changed(before,after);
          egressVerification=before.isEmpty()?"baseline_unavailable":
            publicIpChanged?"public_ip_changed":"public_ip_unchanged";
        }else{
          observedPublicIp="";
          publicIpChanged=false;
          egressVerification="exit_probe_failed";
        }
        egressCheckedAtMs=System.currentTimeMillis();
        final String result=egressVerification;
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "connected",result,android.os.SystemClock.elapsedRealtime()-started);
        MAIN.post(()->report.accept(publicIpChanged
          ?"VPN exit IP changed. Full-device leak and speed tests remain unverified."
          :"WireGuard backend is up, but IP hiding is NOT verified ("+result+")."));
      }catch(Exception|LinkageError e){
        connectionState="error";lastErrorCode=e.getClass().getSimpleName();
        publicIpChanged=false;
        egressVerification="backend_error";
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "failed",lastErrorCode,android.os.SystemClock.elapsedRealtime()-started);
        MAIN.post(()->report.accept("VPN failed: "+lastErrorCode));
      }
    });
  }
  static void disconnect(Activity owner,Consumer<String> report){
    requireLocal(owner);
    Context context=owner.getApplicationContext();
    WORKER.submit(()->{
      try{
        GoBackend instance=backend;
        if(instance!=null)instance.setState(TUNNEL,Tunnel.State.DOWN,null);
        connectionState="off";
        egressVerification="not_checked";
        publicIpChanged=false;
        observedPublicIp="";
        egressCheckedAtMs=0;
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "disconnected","owner_requested",0);
        MAIN.post(()->report.accept("Asterion VPN disconnected"));
      }catch(Exception e){
        lastErrorCode=e.getClass().getSimpleName();
        MAIN.post(()->report.accept("VPN disconnect was not verified: "+lastErrorCode));
      }
    });
  }
  static JSONObject status(Context c)throws Exception{
    boolean up=false;
    try{
      GoBackend instance=backend;
      up=instance!=null&&instance.getState(TUNNEL)==Tunnel.State.UP;
    }catch(Exception ignored){}
    return new JSONObject().put("ok",true)
      .put("backend","wireguard_go")
      .put("active",up)
      .put("state",up?"tunnel_up":connectionState)
      .put("configuration_present",!pref(c).getString("encrypted_configuration","").isEmpty())
      .put("configuration_encrypted_at_rest",true)
      .put("full_tunnel_owner_approved",pref(c).getBoolean("allow_full_tunnel",false))
      .put("peer_reachability_verified",false)
      .put("public_exit_ip",observedPublicIp)
      .put("public_ip_changed_from_direct_baseline",publicIpChanged)
      .put("public_ip_check_state",egressVerification)
      .put("public_ip_checked_at_ms",egressCheckedAtMs)
      .put("full_device_ipv4_ipv6_dns_leak_test_passed",false)
      .put("full_phone_privacy_verified",false)
      .put("external_check_provider","https://api.ipify.org")
      .put("android_system_consent_required",true)
      .put("error_code",lastErrorCode);
  }
}
