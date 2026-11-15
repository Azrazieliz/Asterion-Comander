package com.asterion.control;

/**
 * JVM-only no-network regression for the real Android HTTPS exit observer.
 * Run with javac alongside PublicExitIp.java; does not build an APK or
 * launch a VPN, touch Android permissions or contact api.ipify.org.
 */
public final class PublicExitIpCheck {
  private static int tests=0;
  private static void assertIp(String value,boolean expected){
    tests++;
    boolean actual=PublicExitIp.isPublicIpLiteral(value);
    if(actual!=expected)throw new AssertionError(
        "PublicExitIp.isPublicIpLiteral("+value+") expected "+expected+
        " observed "+actual);
  }
  public static void main(String[] args){
    assertIp("8.8.8.8",true);
    assertIp("1.1.1.1",true);
    assertIp("185.199.108.153",true);
    assertIp("2606:4700:4700::1111",true);
    assertIp("2001:4860:4860::8888",true);
    assertIp("127.0.0.1",false);
    assertIp("10.0.0.2",false);
    assertIp("172.16.1.1",false);
    assertIp("192.168.1.10",false);
    assertIp("100.64.0.1",false);
    assertIp("0.0.0.0",false);
    assertIp("198.51.100.10",false);
    assertIp("203.0.113.5",false);
    assertIp("169.254.10.20",false);
    assertIp("255.255.255.255",false);
    assertIp("::1",false);
    assertIp("fe80::1",false);
    assertIp("fd00::1",false);
    assertIp("2001:db8::1",false);
    assertIp("localhost",false);
    assertIp("google.com",false);
    assertIp("999.999.999.999",false);
    assertIp("123.34.56.78\nX-Header:true",false);
    assertIp(null,false);
    tests++;
    if(!PublicExitIp.changed("8.8.8.8","1.1.1.1"))
      throw new AssertionError("Changing public IPs must be observed");
    tests++;
    if(PublicExitIp.changed("8.8.8.8","8.8.8.8"))
      throw new AssertionError("Identical public IPs cannot count as a change");
    tests++;
    if(PublicExitIp.changed("192.168.1.1","1.1.1.1"))
      throw new AssertionError("Private baseline cannot prove changed public IP");
    System.out.println("PUBLIC_EXIT_IP_JAVA_CHECKS "+tests+" PASS");
  }
}
