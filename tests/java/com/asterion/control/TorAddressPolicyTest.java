package com.asterion.control;
public final class TorAddressPolicyTest {
    private static int n;
    private static void check(boolean value){n++;if(!value)throw new AssertionError("case "+n);}
    public static void main(String[] args)throws Exception{
        byte[] raw=new byte[35];raw[34]=3;
        java.security.MessageDigest d=java.security.MessageDigest.getInstance("SHA3-256");
        d.update(".onion checksum".getBytes(java.nio.charset.StandardCharsets.US_ASCII));d.update(raw,0,32);d.update((byte)3);
        byte[] hash=d.digest();raw[32]=hash[0];raw[33]=hash[1];
        StringBuilder label=new StringBuilder();int buf=0,bits=0;
        for(byte b:raw){buf=(buf<<8)|(b&255);bits+=8;while(bits>=5){bits-=5;label.append("abcdefghijklmnopqrstuvwxyz234567".charAt((buf>>bits)&31));}}
        String onion=label+".onion";
        check(TorAddressPolicy.validV3(onion));check(TorAddressPolicy.validV3("www."+onion));
        check(TorAddressPolicy.resolve(onion).equals("http://"+onion));
        check(TorAddressPolicy.resolve("https://example.com/")!=null);
        for(String bad:new String[]{"abc.onion","http://example.com/","https://127.0.0.1/","https://localhost/","https://test.local/","https://u:p@example.com/","javascript:alert(1)","https://example.com:0","https://example.com:65536","https://example.com\\x"})check(TorAddressPolicy.resolve(bad)==null);
        check(!BrowserNavigationPolicy.isWeb("http://"+onion));
        check(BrowserNavigationPolicy.resolve("find "+onion,"https://search.example/?q=").equals(BrowserNavigationPolicy.HOME));
        check(!BrowserNavigationPolicy.isWeb("https://"+onion+"."));
        check(!TorAddressPolicy.validV3("b"+onion.substring(1)));
        check(VpnRouteScope.privateSubnet(new byte[]{10,0,0,0},8));
        check(!VpnRouteScope.privateSubnet(new byte[]{10,0,0,0},7));
        check(!VpnRouteScope.privateSubnet(new byte[]{0,0,0,0},1));
        check(!VpnRouteScope.privateSubnet(new byte[]{(byte)192,(byte)168,0,0},15));
        check(VpnRouteScope.privateSubnet(new byte[]{(byte)172,16,0,0},12));
        check(!VpnRouteScope.privateSubnet(new byte[]{(byte)172,15,0,0},16));
        System.out.println("Tor and VPN route policy: "+n+" assertions passed");
    }
}
