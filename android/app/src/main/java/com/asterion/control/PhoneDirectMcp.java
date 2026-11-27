package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.Network;
import android.util.Base64;
import android.util.Log;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.SocketTimeoutException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.SSLSocketFactory;

/** Phone-outbound TLS MCP connection. No GitHub polling, public Android port or new model.
 * Owner must already have paired the phone with the native Windows Control service.
 * TLS server hostname verification and WebSocket handshake verification are mandatory.
 * No uncertain command is ever replayed after a disconnect.
 */
final class PhoneDirectMcp {
  private static final String HOST="wise-eagle-c8b55706.tunnl.gg";
  private static final String PATH="/phone/live";
  private static final String GUID="258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
  private static final SecureRandom RANDOM=new SecureRandom();
  private static final AtomicBoolean STARTED=new AtomicBoolean(false);
  private static volatile boolean stop=false,connected=false;
  private static volatile SSLSocket active;
  private static volatile String phase="stopped",lastError="",lastStage="idle",lastErrorDetail="";
  private static volatile Network socketNetwork;
  private static volatile Context appContext;
  private static volatile long lastSuccess=0;
  private static volatile long lastWireResponseMs=0;
  private static volatile long lastPongMs=0;
  private static volatile long outstandingPingAtMs=0;
  private static final long HEALTHY_WSS_WINDOW_MS=65000L;
  private static final long HEARTBEAT_GRACE_MS=35000L;
  private static Thread worker;
  private static AgentService requestedOwner;
  private PhoneDirectMcp(){}

  static synchronized void start(AgentService owner){
    requestedOwner=owner;
    if(!STARTED.compareAndSet(false,true))return;
    stop=false;appContext=owner.getApplicationContext();
    worker=new Thread(()->loop(owner),"asterion-direct-mcp");
    worker.setDaemon(true);
    worker.start();
  }
  static void networkChanged(){
    // Ignore repeated capability callbacks for the currently bound network.
    Context context=appContext;
    if(context!=null){
      ConnectivityManager manager=(ConnectivityManager)context.getSystemService(
        Context.CONNECTIVITY_SERVICE);
      Network current=manager==null?null:manager.getActiveNetwork();
      if(current!=null&&current.equals(socketNetwork))return;
    }
    closeActiveSocket();
  }
  private static void closeActiveSocket(){
    SSLSocket sock=active;
    if(sock!=null)try{sock.close();}catch(Exception ignored){}
  }
  static synchronized void stop(){
    requestedOwner=null;
    stop=true;
    // Explicit service shutdown must close even an unchanged bound network.
    closeActiveSocket();
    Thread thread=worker;
    if(thread!=null)thread.interrupt();
  }
  static JSONObject status()throws Exception{
    long age=System.currentTimeMillis()-lastWireResponseMs;
    boolean fresh=connected&&lastWireResponseMs>0&&
      age>=0&&age<=HEALTHY_WSS_WINDOW_MS;
    return new JSONObject().put("transport","direct_wss")
      .put("connected",fresh).put("socket_open",connected).put("phase",phase)
      .put("wire_last_authenticated_frame_ms",lastWireResponseMs)
      .put("last_heartbeat_pong_ms",lastPongMs)
      .put("last_unanswered_ping_ms",outstandingPingAtMs)
      .put("heartbeat_recent",fresh)
      .put("last_success_ms",lastSuccess).put("last_error",lastError)
      .put("last_stage",lastStage).put("last_error_detail",lastErrorDetail)
      .put("requires_github",false).put("phone_outbound_tls",true);
  }
  private static void loop(AgentService owner){
    try{
      while(!stop){
        // Same Android-owned bearer credential registered with the Windows
        // Control gateway through /api/v1/phone/register. Do not require the
        // unrelated PC pairing preference for phone-first cellular access.
        String key=AgentService.token(owner);
        if(key==null||key.length()<32){
          phase="unpaired";sleep(7000);continue;
        }
        try{
          phase="connecting";
          session(owner,key);
          lastError="";lastErrorDetail="";
        }catch(Exception e){
          if(!stop){
            String name=e.getClass().getSimpleName();
            lastError=name;
            String message=e.getMessage()==null?"":e.getMessage();
            lastErrorDetail=message.replaceAll("[\\r\\n\\t]"," ").substring(0,Math.min(160,message.length()));
            phase="reconnecting";
            ControlEventJournal.write(owner,"transport_error",lastStage,
              "disconnected",name,0);
            Log.w("AsterionDirectMcp","Direct cellular relay disconnected: "+name);
          }
        }finally{connected=false;active=null;}
        sleep(2800);
      }
    }finally{
      synchronized(PhoneDirectMcp.class){
        connected=false;phase="stopped";worker=null;STARTED.set(false);
        // Android may recreate the service before its previous thread exits.
        // Start exactly one successor, not a second concurrent session.
        AgentService next=requestedOwner;
        if(next!=null)start(next);
      }
    }
  }
  private static void sleep(long ms){
    try{Thread.sleep(ms);}catch(InterruptedException ignored){Thread.currentThread().interrupt();}
  }
  private static String readLine(InputStream in)throws Exception{
    ByteArrayOutputStream bytes=new ByteArrayOutputStream();
    while(true){
      int c=in.read();
      if(c<0)throw new java.io.EOFException("TLS handshake ended");
      if(c==10)break;
      if(c!=13)bytes.write(c);
      if(bytes.size()>8192)throw new IllegalArgumentException("Oversized WebSocket header");
    }
    return bytes.toString("UTF-8");
  }
  private static String shaAccept(String nonce)throws Exception{
    byte[] digest=MessageDigest.getInstance("SHA-1").digest(
      (nonce+GUID).getBytes(StandardCharsets.US_ASCII));
    return Base64.encodeToString(digest,Base64.NO_WRAP);
  }
  private static void handshake(SSLSocket sock,String bearer)throws Exception{
    byte[] nonce=new byte[16];RANDOM.nextBytes(nonce);
    String wsKey=Base64.encodeToString(nonce,Base64.NO_WRAP);
    OutputStream out=sock.getOutputStream();
    String request="GET "+PATH+" HTTP/1.1\r\n"
      +"Host: "+HOST+"\r\n"
      +"Upgrade: websocket\r\n"
      +"Connection: Upgrade\r\n"
      +"Sec-WebSocket-Key: "+wsKey+"\r\n"
      +"Sec-WebSocket-Version: 13\r\n"
      +"Authorization: Bearer "+bearer+"\r\n\r\n";
    out.write(request.getBytes(StandardCharsets.US_ASCII));out.flush();
    InputStream in=sock.getInputStream();
    String line=readLine(in);
    if(!line.startsWith("HTTP/1.1 101 ")&&!line.startsWith("HTTP/1.0 101 ")){
      // Only expose numeric response status. Do not reveal headers, bearer,
      // endpoint credentials or an HTML error body in exported diagnostics.
      String[] parts=line.split(" ");
      String status=parts.length>=2&&parts[1].matches("[0-9]{3}")?parts[1]:"unknown";
      throw new java.io.IOException("WSS upgrade HTTP "+status);
    }
    boolean upgraded=false,connection=false,accepted=false;
    for(int i=0;i<64;i++){
      line=readLine(in);
      if(line.isEmpty())break;
      int at=line.indexOf(':');
      if(at<0)continue;
      String key=line.substring(0,at).trim().toLowerCase(java.util.Locale.ROOT);
      String value=line.substring(at+1).trim();
      if("upgrade".equals(key)&&value.equalsIgnoreCase("websocket"))upgraded=true;
      if("connection".equals(key)&&value.toLowerCase(java.util.Locale.ROOT).contains("upgrade"))connection=true;
      if("sec-websocket-accept".equals(key)&&shaAccept(wsKey).equals(value))accepted=true;
    }
    if(!upgraded||!connection||!accepted)
      throw new java.io.IOException("Invalid authenticated WSS upgrade response");
  }
  private static void writeMasked(OutputStream out,int opcode,byte[] payload)throws Exception{
    if(payload.length>8_000_000)throw new IllegalArgumentException("WebSocket response too large");
    out.write(0x80|opcode);
    if(payload.length<126){
      out.write(0x80|payload.length);
    }else if(payload.length<=65535){
      out.write(0x80|126);
      out.write((payload.length>>8)&255);out.write(payload.length&255);
    }else{
      out.write(0x80|127);
      long length=payload.length;
      for(int b=7;b>=0;b--)out.write((int)(length>>>(b*8))&255);
    }
    byte[] mask=new byte[4];RANDOM.nextBytes(mask);out.write(mask);
    for(int i=0;i<payload.length;i++)out.write(payload[i]^mask[i%4]);
    out.flush();
  }
  private static long unsigned(InputStream in)throws Exception{
    int c=in.read();if(c<0)throw new java.io.EOFException("WSS disconnected");
    return c;
  }
  private static final class Frame {
    final int opcode;final byte[] payload;
    Frame(int op,byte[] b){opcode=op;payload=b;}
  }
  private static Frame readFrame(InputStream in)throws Exception{
    int a=(int)unsigned(in);
    // Only an idle timeout BEFORE a frame is safe for a heartbeat.
    // Once a frame starts, a timeout is an incomplete protocol message.
    try{
    int b=(int)unsigned(in);
    if((a&0x80)==0)throw new IllegalArgumentException("Fragmented WSS frames not supported");
    if((b&0x80)!=0)throw new IllegalArgumentException("Server masked a WebSocket frame");
    int opcode=a&0x0f;
    long len=b&0x7f;
    if(len==126){len=(unsigned(in)<<8)|unsigned(in);}
    if(len==127){
      len=0;
      for(int i=0;i<8;i++)len=(len<<8)|unsigned(in);
    }
    if(len<0||len>8_000_000)throw new IllegalArgumentException("WebSocket message exceeds limit");
    byte[] data=in.readNBytes((int)len);
    if(data.length!=(int)len)throw new java.io.EOFException("Truncated WebSocket payload");
    return new Frame(opcode,data);
    }catch(SocketTimeoutException partial){
      throw new IOException("Incomplete authenticated WebSocket frame",partial);
    }
  }
  private static SSLSocket openBoundTlsSocket(Context owner)throws Exception{
    ConnectivityManager manager=(ConnectivityManager)owner.getSystemService(
      Context.CONNECTIVITY_SERVICE);
    Network network=manager==null?null:manager.getActiveNetwork();
    lastStage="dns";
    InetAddress[] addresses=network!=null?network.getAllByName(HOST)
      :InetAddress.getAllByName(HOST);
    IOException failure=null;
    for(InetAddress address:addresses){
      Socket plain=null;
      try{
        lastStage="tcp";
        plain=network!=null?network.getSocketFactory().createSocket():new Socket();
        plain.setTcpNoDelay(true);plain.setKeepAlive(true);
        plain.connect(new InetSocketAddress(address,443),10000);
        lastStage="tls";
        SSLSocket tls=(SSLSocket)((SSLSocketFactory)SSLSocketFactory.getDefault())
          .createSocket(plain,HOST,443,true);
        socketNetwork=network;
        return tls;
      }catch(IOException e){
        failure=e;
        if(plain!=null)try{plain.close();}catch(Exception ignored){}
      }
    }
    if(failure!=null)throw failure;
    throw new IOException("No route to the authenticated Control endpoint");
  }
  private static void session(AgentService owner,String pairedToken)throws Exception{
    SSLSocket socket=openBoundTlsSocket(owner);
    active=socket;
    try(SSLSocket sock=socket){
      if(stop)throw new IOException("Control service stopped before TLS handshake");
      SSLParameters options=sock.getSSLParameters();
      options.setEndpointIdentificationAlgorithm("HTTPS");
      sock.setSSLParameters(options);
      sock.setSoTimeout(20000);
      lastStage="tls_handshake";sock.startHandshake();
      lastStage="wss_upgrade";handshake(sock,pairedToken);
      connected=true;phase="connected";lastStage="connected";lastError="";lastErrorDetail="";lastSuccess=System.currentTimeMillis();
      lastWireResponseMs=lastSuccess;
      lastPongMs=0;
      outstandingPingAtMs=0;
      ControlEventJournal.write(owner,"transport_connected","wss_upgrade","connected","authenticated",0);
      InputStream in=sock.getInputStream();OutputStream out=sock.getOutputStream();
      while(!stop){
        Frame frame;
        try{frame=readFrame(in);}
        catch(SocketTimeoutException timeout){
          if(stop||!pairedToken.equals(AgentService.token(owner)))break;
          long now=System.currentTimeMillis();
          if(outstandingPingAtMs>0 &&
             now-outstandingPingAtMs>HEARTBEAT_GRACE_MS)
            throw new IOException("Authenticated WSS heartbeat was not acknowledged");
          if(outstandingPingAtMs==0){
            outstandingPingAtMs=now;
            writeMasked(out,9,new byte[0]);
          }
          continue;
        }
        if(stop||!pairedToken.equals(AgentService.token(owner)))break;
        if(frame.opcode==8)break;
        if(frame.opcode==9){
          lastWireResponseMs=System.currentTimeMillis();
          writeMasked(out,10,frame.payload);continue;
        }
        if(frame.opcode==10){
          lastPongMs=System.currentTimeMillis();
          lastWireResponseMs=lastPongMs;
          outstandingPingAtMs=0;
          continue;
        }
        if(frame.opcode!=1)throw new IllegalArgumentException("Unknown WebSocket frame type");
        lastWireResponseMs=System.currentTimeMillis();
        outstandingPingAtMs=0;
        JSONObject event=new JSONObject(new String(frame.payload,StandardCharsets.UTF_8));
        String id=event.optString("id","");
        JSONObject rpc=event.optJSONObject("rpc");
        if(!id.matches("[a-f0-9]{32}")||rpc==null)continue;
        JSONObject answer=AndroidMcp.handle(owner,rpc);
        if(answer==null)answer=new JSONObject().put("jsonrpc","2.0")
          .put("id",rpc.opt("id")).put("result",new JSONObject());
        JSONObject response=new JSONObject().put("id",id).put("rpc",answer);
        writeMasked(out,1,response.toString().getBytes(StandardCharsets.UTF_8));
        lastSuccess=System.currentTimeMillis();
      }
    }
  }
}
