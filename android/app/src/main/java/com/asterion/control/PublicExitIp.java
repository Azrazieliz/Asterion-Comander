package com.asterion.control;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.net.Inet4Address;
import java.net.Inet6Address;
import java.net.InetAddress;
import java.net.HttpURLConnection;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.nio.charset.StandardCharsets;

/**
 * Bounded opt-in external IP observer used ONLY after an explicit owner VPN
 * connect request. Not a VPN, country changer, DNS leak checker or anonymity
 * guarantee. A fixed HTTPS endpoint observes the caller's actual public IP:
 * this necessarily discloses the connection address to that endpoint.
 *
 * No owner/Control secret, URL, account or file data is transmitted.
 * The observer does not run by itself, at boot, or during app startup.
 */
final class PublicExitIp {
  private static final String OBSERVER="https://api.ipify.org";
  private PublicExitIp(){}

  static String probe() throws IOException {
    URL url=new URL(OBSERVER);
    HttpURLConnection connection=(HttpURLConnection)url.openConnection();
    if(!(connection instanceof HttpsURLConnection))
      throw new IOException("Public IP observer must use HTTPS");
    connection.setInstanceFollowRedirects(false);
    connection.setRequestMethod("GET");
    connection.setUseCaches(false);
    connection.setConnectTimeout(4000);
    connection.setReadTimeout(4000);
    connection.setRequestProperty("Accept","text/plain");
    try {
      int code=connection.getResponseCode();
      if(code!=200)throw new IOException("Public IP observer returned "+code);
      ByteArrayOutputStream buffer=new ByteArrayOutputStream();
      try(InputStream input=connection.getInputStream()){
        byte[] bytes=new byte[64];
        while(true){
          int n=input.read(bytes);
          if(n<0)break;
          if(buffer.size()+n>64)
            throw new IOException("Public IP observer response too large");
          buffer.write(bytes,0,n);
        }
      }
      String value=new String(buffer.toByteArray(),StandardCharsets.US_ASCII).trim();
      if(!isPublicIpLiteral(value))
        throw new IOException("Public IP observer returned no valid public IP");
      return value;
    }finally {
      connection.disconnect();
    }
  }

  static boolean isPublicIpLiteral(String value) {
    if(value==null||value.length()<3||value.length()>45)return false;
    if(value.indexOf(':')<0){
      String[] parts=value.split("\\.",-1);
      if(parts.length!=4)return false;
      int[] octets=new int[4];
      for(int i=0;i<4;i++){
        String p=parts[i];
        if(p.length()<1||p.length()>3)return false;
        for(int c=0;c<p.length();c++)
          if(p.charAt(c)<'0'||p.charAt(c)>'9')return false;
        try {
          octets[i]=Integer.parseInt(p);
        }catch(NumberFormatException e){return false;}
        if(octets[i]>255)return false;
      }
      int a=octets[0], b=octets[1], c=octets[2];
      if(a==0||a==10||a==127||a>=224||
         (a==100&&b>=64&&b<=127)||
         (a==169&&b==254)||
         (a==172&&b>=16&&b<=31)||
         (a==192&&(b==168||b==0&&c==0||b==0&&c==2))||
         (a==198&&(b==18||b==19||b==51&&c==100))||
         (a==203&&b==0&&c==113))return false;
      return true;
    }
    // Only IPv6 numeric literals may reach InetAddress; never resolve
    // hostnames or honor scoped link-local '%iface' identifiers.
    if(value.indexOf('%')>=0||!value.matches("[0-9a-fA-F:.]+"))
      return false;
    try {
      InetAddress address=InetAddress.getByName(value);
      if(!(address instanceof Inet6Address)||address.isAnyLocalAddress()||
         address.isLoopbackAddress()||address.isLinkLocalAddress()||
         address.isSiteLocalAddress()||address.isMulticastAddress())
        return false;
      byte[] bytes=address.getAddress();
      // IPv6 unique local fc00::/7 and documentation 2001:db8::/32.
      if((bytes[0]&0xfe)==0xfc)return false;
      if(bytes[0]==0x20&&bytes[1]==0x01&&
         (bytes[2]&0xff)==0x0d&&(bytes[3]&0xff)==0xb8)return false;
      return true;
    }catch(Exception e){return false;}
  }

  static boolean changed(String original,String current){
    return isPublicIpLiteral(original)&&isPublicIpLiteral(current)&&
      !original.equalsIgnoreCase(current);
  }
}
