package com.asterion.control;

/** Verify complete containment of a split subnet in an approved private range. */
final class VpnRouteScope {
    private VpnRouteScope(){}
    static boolean privateSubnet(byte[] address,int prefix){
        if(address==null)return false;
        if(address.length==4){
            if(prefix<0||prefix>32)return false;
            int a=address[0]&255,b=address[1]&255;
            return (a==10&&prefix>=8)||(a==172&&b>=16&&b<=31&&prefix>=12)||
                (a==192&&b==168&&prefix>=16)||(a==100&&b>=64&&b<=127&&prefix>=10);
        }
        return address.length==16&&prefix>=7&&prefix<=128&&(address[0]&254)==252;
    }
}
