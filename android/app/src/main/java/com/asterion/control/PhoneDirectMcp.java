package com.asterion.control;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;
import android.util.Log;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.SocketTimeoutException;
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
  private static volatile String phase="stopped",lastError="";
  private static volatile long lastSuccess=0;
  private static Thread worker;
  private PhoneDirectMcp(){}

  static synchronized void start(AgentService owner){
    if(!STARTED.compareAndSet(false,true))return;
    stop=false;
    worker=new Thread(()->loop(owner),"asterion-direct-mcp");
    worker.setDaemon(true);
    worker.start();
  }
  static void networkChanged(){
    SSLSocket sock=active;
    if(sock!=null)try{sock.close();}catch(Exception ignored){}
  }
  static synchronized void stop(){
    stop=true;networkChanged();
    Thread thread=worker;
    if(thread!=null)thread.interrupt();
  }
  static JSONObject status()throws Exception{
    return new JSONObject().put("transport","direct_wss")
      .put("connected",connected).put("phase",phase)
      .put("last_success_ms",lastSuccess).put("last_error",lastError)
      .put("requires_github",false).put("phone_outbound_tls",true);
  }
  private static void loop(AgentService owner){
    try{
      while(!stop){
        SharedPreferences p=owner.getSharedPreferences("control",Context.MODE_PRIVATE);
        String key=p.getString("token","");
        if(key==null||key.length()<32){
          phase="unpaired";sleep(7000);continue;
        }
        try{
          phase="connecting";
          session(owner,key);
          lastError=""; 
        }catch(Exception e){
          if(!stop){
            String name=e.getClass().getSimpleName();
            lastError=name;
            phase="reconnecting";
            Log.w("AsterionDirectMcp","Direct cellular relay disconnected: "+name);
          }
        }finally{connected=false;active=null;}
        sleep(2800);
      }
    }finally{
      connected=false;phase="stopped";STARTED.set(false);
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
    if(!line.startsWith("HTTP/1.1 101 ")&&!line.startsWith("HTTP/1.0 101 "))
      throw new java.io.IOException("WSS handshake rejected");
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
    int a=(int)unsigned(in),b=(int)unsigned(in);
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
  }
  private static void session(AgentService owner,String pairedToken)throws Exception{
    SSLSocket socket=(SSLSocket)SSLSocketFactory.getDefault().createSocket(HOST,443);
    active=socket;
    try(SSLSocket sock=socket){
      SSLParameters options=sock.getSSLParameters();
      options.setEndpointIdentificationAlgorithm("HTTPS");
      sock.setSSLParameters(options);
      sock.setSoTimeout(40000);
      sock.startHandshake();
      handshake(sock,pairedToken);
      connected=true;phase="connected";lastError="";lastSuccess=System.currentTimeMillis();
      InputStream in=sock.getInputStream();OutputStream out=sock.getOutputStream();
      while(!stop){
        Frame frame;
        try{frame=readFrame(in);}
        catch(SocketTimeoutException timeout){
          writeMasked(out,9,new byte[0]);continue;
        }
        if(frame.opcode==8)break;
        if(frame.opcode==9){writeMasked(out,10,frame.payload);continue;}
        if(frame.opcode==10)continue;
        if(frame.opcode!=1)throw new IllegalArgumentException("Unknown WebSocket frame type");
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
