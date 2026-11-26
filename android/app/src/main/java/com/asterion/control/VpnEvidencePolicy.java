package com.asterion.control;

/** Conservative acceptance rules for actual measured VPN observations. */
final class VpnEvidencePolicy {
    private VpnEvidencePolicy(){}
    static boolean knownTransport(String transport){
        return "wifi".equals(transport)||"cellular".equals(transport)||"ethernet".equals(transport);
    }
    static boolean comparable(String before,String after,long age,long maxAge){
        return knownTransport(before)&&before.equals(after)&&age>=0&&age<maxAge;
    }
    static boolean exitReplaced(boolean baseline,boolean route,boolean peer,String before,String after){
        return baseline&&route&&peer&&before!=null&&!before.isEmpty()&&after!=null&&!after.isEmpty()&&!before.equals(after);
    }
    static String ipv6Assessment(boolean comparable,boolean route,boolean peer,String before,String after){
        if(!comparable||!route||!peer)return "inconclusive";
        if(before==null||before.isEmpty()||after==null||after.isEmpty())return "inconclusive_ipv6_unavailable";
        return before.equals(after)?"unchanged_ipv6_possible_leak":"ipv6_address_changed";
    }
    static double ratio(double baseline,double measured){
        return Double.isFinite(baseline)&&Double.isFinite(measured)&&baseline>0&&measured>=0?measured/baseline:0;
    }
}
