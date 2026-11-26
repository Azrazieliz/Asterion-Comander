package com.asterion.control;
import java.net.InetAddress;
public final class VpnRouteScopeTest {
  private static void test(String ip,int mask,boolean want)throws Exception{
    if(VpnRouteScope.privateSubnet(InetAddress.getByName(ip).getAddress(),mask)!=want)
      throw new AssertionError(ip+"/"+mask);
  }
  public static void main(String[] args)throws Exception{
    test("10.0.0.0",8,true);test("10.0.0.0",7,false);
    test("172.16.0.0",12,true);test("172.16.0.0",11,false);
    test("192.168.0.0",16,true);test("192.168.0.0",15,false);
    test("100.64.0.0",10,true);test("100.64.0.0",9,false);
    test("0.0.0.0",1,false);test("128.0.0.0",1,false);
    test("fd00::",8,true);test("fc00::",7,true);test("fc00::",6,false);
    test("::",0,false);test("2001:4860::",32,false);
    System.out.println("14 VPN scope cases passed");
  }
}
