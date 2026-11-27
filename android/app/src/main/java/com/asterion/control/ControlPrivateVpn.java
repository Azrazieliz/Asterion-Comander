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
import com.wireguard.android.backend.Statistics;
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
  private static final java.util.concurrent.atomic.AtomicBoolean TRANSITION=new java.util.concurrent.atomic.AtomicBoolean(false);
  private static volatile String connectionState="off";
  private static volatile String lastErrorCode="";
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
    boolean v4Default=false,v6Default=false;
    for(Peer peer:config.getPeers()){
      if(!peer.getEndpoint().isPresent())throw new IllegalArgumentException("Peer endpoint required");
      for(InetNetwork allowed:peer.getAllowedIps()){
        routes++;
        java.net.InetAddress network=allowed.getAddress();
        int mask=allowed.getMask();
        if(mask==0){
          if(network instanceof java.net.Inet6Address)v6Default=true;else v4Default=true;
        }
        // Split mode is for specific private-device routes, never an indirect
        // default route (two /1s, or a broad public subnet).
        if(!allowFullTunnel&&!VpnRouteScope.privateSubnet(network.getAddress(),mask))
          throw new IllegalArgumentException("Public or broad routes require full-tunnel consent");
      }
    }
    if(routes==0)throw new IllegalArgumentException("No permitted tunnel routes");
    if(allowFullTunnel){
      if(!v4Default||!v6Default)throw new IllegalArgumentException("Full tunnel requires IPv4 and IPv6 default routes");
      if(config.getInterface().getDnsServers().isEmpty())throw new IllegalArgumentException("Full tunnel DNS required");
      if(!config.getInterface().getExcludedApplications().isEmpty()||!config.getInterface().getIncludedApplications().isEmpty())
        throw new IllegalArgumentException("Full phone tunnel cannot exclude applications");
    }
    return config;
  }
  private static boolean tunnelUp() throws Exception{
    return backend!=null&&backend.getState(TUNNEL)==Tunnel.State.UP;
  }
  private static boolean configured(Context context){
    return !pref(context).getString("encrypted_configuration","").isEmpty();
  }
  static synchronized String reserveProviderEnrollment(Activity owner)throws Exception{
    requireLocal(owner);
    if(configured(owner)||TRANSITION.get()||tunnelUp())
      throw new IllegalStateException("Existing VPN configuration or operation");
    String attempt=java.util.UUID.randomUUID().toString();
    if(!pref(owner).edit().putString("provider_attempt",attempt)
        .putString("provider_enrollment_state","registering").commit())
      throw new IllegalStateException("Could not persist enrollment reservation");
    return attempt;
  }
  static synchronized void completeProviderEnrollment(Context context,String attempt,String text)throws Exception{
    if(!VpnEvidencePolicy.mayCommitEnrollment(attempt,pref(context).getString("provider_attempt",""),
          configured(context),TRANSITION.get(),tunnelUp()))
      throw new IllegalStateException("Enrollment superseded by newer VPN state");
    // Authorization was recorded in the foreground before registration began.
    // Saving the profile is not activating a VPN or approving Android consent.
    storeConfiguration(context,text,true,"configured");
    ControlEventJournal.write(context,"vpn_config_imported","owner_ui",
        "completed","provider_profile_full_tunnel",0);
  }
  static synchronized void failProviderEnrollment(Context context,String attempt){
    if(attempt.equals(pref(context).getString("provider_attempt",""))){
      pref(context).edit().remove("provider_attempt")
          .putString("provider_enrollment_state","failed_or_unknown").commit();
    }
  }
  private static void storeConfiguration(Context context,String text,boolean full,String enrollment)throws Exception{
    parseAndValidate(text,full);
    // Keep the existing Keystore and single encrypted configuration.
    String encrypted=encrypt(text);
    if(!pref(context).edit().putString("encrypted_configuration",encrypted)
        .putBoolean("allow_full_tunnel",full).remove("provider_attempt")
        .putString("provider_enrollment_state",enrollment).commit())
      throw new IllegalStateException("Could not save encrypted config");
  }
  static synchronized void importLocally(Activity owner,String text,boolean allowFullTunnel)
      throws Exception{
    requireLocal(owner);
    if(TRANSITION.get()||tunnelUp())
      throw new IllegalStateException("Disconnect the existing tunnel before replacing its configuration");
    storeConfiguration(owner,text,allowFullTunnel,"manual_profile");
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
    if(!TRANSITION.compareAndSet(false,true)){report.accept("VPN operation already in progress");return;}
    try{
      android.net.ConnectivityManager cm=owner.getSystemService(android.net.ConnectivityManager.class);
      android.net.Network n=cm==null?null:cm.getActiveNetwork();
      android.net.NetworkCapabilities caps=n==null?null:cm.getNetworkCapabilities(n);
      if(caps!=null&&caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN)&&
          (backend==null||backend.getState(TUNNEL)!=Tunnel.State.UP)){
        TRANSITION.set(false);report.accept("Disconnect the existing Android VPN before connecting Asterion");return;
      }
    }catch(Exception e){TRANSITION.set(false);report.accept("Could not verify existing VPN state");return;}
    connectionState="starting";
    WORKER.submit(()->{
      long started=android.os.SystemClock.elapsedRealtime();
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
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "connected","backend_up",android.os.SystemClock.elapsedRealtime()-started);
        MAIN.post(()->report.accept("VPN tunnel is up. Peer reachability is not yet verified."));
      }catch(Exception|LinkageError e){
        connectionState="error";lastErrorCode=e.getClass().getSimpleName();
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "failed",lastErrorCode,android.os.SystemClock.elapsedRealtime()-started);
        MAIN.post(()->report.accept("VPN failed: "+lastErrorCode));
      }finally{TRANSITION.set(false);}
    });
  }
  static void disconnect(Activity owner,Consumer<String> report){
    requireLocal(owner);
    Context context=owner.getApplicationContext();
    if(!TRANSITION.compareAndSet(false,true)){report.accept("VPN operation already in progress");return;}
    WORKER.submit(()->{
      try{
        GoBackend instance=backend;
        if(instance!=null){
          Tunnel.State after=instance.setState(TUNNEL,Tunnel.State.DOWN,null);
          if(after!=Tunnel.State.DOWN||instance.getState(TUNNEL)!=Tunnel.State.DOWN)
            throw new IllegalStateException("Tunnel did not reach DOWN");
        }
        connectionState="off";
        ControlEventJournal.write(context,"vpn_tunnel","wireguard",
          "disconnected","owner_requested",0);
        MAIN.post(()->report.accept("Asterion VPN disconnected"));
      }catch(Exception e){
        lastErrorCode=e.getClass().getSimpleName();
        MAIN.post(()->report.accept("VPN disconnect was not verified: "+lastErrorCode));
      }finally{TRANSITION.set(false);}
    });
  }
  private static String providerEnrollmentState(Context context){
    String state=pref(context).getString("provider_enrollment_state","not_started");
    if("registering".equals(state)&&!ControlFreeVpnProvisioner.busy())
      return "outcome_unknown";
    return state;
  }
  static JSONObject status(Context c)throws Exception{
    boolean up=false;
    boolean peerVerified=false;
    long lastHandshake=0L,receiveBytes=0L,transmitBytes=0L;
    String evidenceError="";
    try{
      GoBackend instance=backend;
      up=instance!=null&&instance.getState(TUNNEL)==Tunnel.State.UP;
      if(up){
        // Real WireGuard peer state, not an app toggle or fabricated VPN badge.
        Statistics stats=instance.getStatistics(TUNNEL);
        receiveBytes=stats.totalRx();transmitBytes=stats.totalTx();
        for(com.wireguard.crypto.Key peer:stats.peers()){
          Statistics.PeerStats detail=stats.peer(peer);
          if(detail!=null&&detail.latestHandshakeEpochMillis()>lastHandshake)
            lastHandshake=detail.latestHandshakeEpochMillis();
        }
        long age=System.currentTimeMillis()-lastHandshake;
        peerVerified=lastHandshake>0&&age>=0L&&age<=180000L&&receiveBytes>0L;
      }
    }catch(Exception problem){
      evidenceError=problem.getClass().getSimpleName();
    }
    boolean systemVpnRoute=false;
    try{
      android.net.ConnectivityManager cm=(android.net.ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
      android.net.Network network=cm==null?null:cm.getActiveNetwork();
      android.net.NetworkCapabilities caps=network==null?null:cm.getNetworkCapabilities(network);
      systemVpnRoute=caps!=null&&caps.hasTransport(android.net.NetworkCapabilities.TRANSPORT_VPN)&&caps.hasCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED);
    }catch(Exception ignored){}
    return new JSONObject().put("ok",true)
      .put("android_validated_vpn_route",systemVpnRoute)
      .put("provider_enrollment_state",providerEnrollmentState(c))
      .put("verified_active_tunnel",up&&peerVerified&&systemVpnRoute)
      .put("transition_in_progress",TRANSITION.get())
      .put("backend","wireguard_go")
      .put("active",up)
      .put("state",up?"tunnel_up":connectionState)
      .put("configuration_present",!pref(c).getString("encrypted_configuration","").isEmpty())
      .put("configuration_encrypted_at_rest",true)
      .put("full_tunnel_owner_approved",pref(c).getBoolean("allow_full_tunnel",false))
      .put("peer_reachability_verified",peerVerified)
      .put("last_real_peer_handshake_ms",lastHandshake)
      .put("real_bytes_received",receiveBytes)
      .put("real_bytes_sent",transmitBytes)
      .put("peer_statistics_error_code",evidenceError)
      .put("android_system_consent_required",true)
      .put("error_code",lastErrorCode);
  }
}
