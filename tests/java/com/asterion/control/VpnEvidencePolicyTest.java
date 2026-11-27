package com.asterion.control;
public final class VpnEvidencePolicyTest {
    private static int n;
    static void expect(Object expected,Object actual){n++;if(!expected.equals(actual))throw new AssertionError("case "+n);}
    public static void main(String[] args){
        expect(true,VpnEvidencePolicy.mayCommitEnrollment("attempt","attempt",false,false,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment("old","new",false,false,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment(null,"attempt",false,false,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment("","",false,false,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment("attempt","attempt",true,false,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment("attempt","attempt",false,true,false));
        expect(false,VpnEvidencePolicy.mayCommitEnrollment("attempt","attempt",false,false,true));
        for(int i=0;i<32;i++)expect(i==31,VpnEvidencePolicy.fullRoute(
            (i&1)!=0,(i&2)!=0,(i&4)!=0,(i&8)!=0,(i&16)!=0?2:0));
        expect(true,VpnEvidencePolicy.comparable("wifi","wifi",100,1000));
        expect(false,VpnEvidencePolicy.comparable("wifi","cellular",100,1000));
        expect(false,VpnEvidencePolicy.comparable("unknown","unknown",100,1000));
        expect(false,VpnEvidencePolicy.comparable("wifi","wifi",1000,1000));
        expect(false,VpnEvidencePolicy.comparable("wifi","wifi",-1,1000));
        for(int i=0;i<8;i++)expect(i==7,VpnEvidencePolicy.exitReplaced((i&1)!=0,(i&2)!=0,(i&4)!=0,"1.2.3.4","5.6.7.8"));
        expect(false,VpnEvidencePolicy.exitReplaced(true,true,true,"1.2.3.4","1.2.3.4"));
        expect(false,VpnEvidencePolicy.exitReplaced(true,true,true,"","5.6.7.8"));
        expect("unchanged_ipv6_possible_leak",VpnEvidencePolicy.ipv6Assessment(true,true,true,"2001:db8::1","2001:db8::1"));
        expect("ipv6_address_changed",VpnEvidencePolicy.ipv6Assessment(true,true,true,"2001:db8::1","2001:db8::2"));
        expect("inconclusive_ipv6_unavailable",VpnEvidencePolicy.ipv6Assessment(true,true,true,"2001:db8::1",""));
        expect("inconclusive",VpnEvidencePolicy.ipv6Assessment(true,false,true,"2001:db8::1","2001:db8::2"));
        expect(0.75,VpnEvidencePolicy.ratio(100,75));
        expect(0.0,VpnEvidencePolicy.ratio(0,75));
        expect(0.0,VpnEvidencePolicy.ratio(Double.NaN,75));
        if(!VpnEvidencePolicy.completeWindow(8000000,30_000_000_000L,30_000_000_000L,512L<<20,1,true))throw new AssertionError("complete sustained window");
        if(VpnEvidencePolicy.completeWindow(512L<<20,10_000_000_000L,30_000_000_000L,512L<<20,10,true))throw new AssertionError("cap is not duration");
        if(VpnEvidencePolicy.completeWindow(8000000,30_000_000_000L,30_000_000_000L,512L<<20,1,false))throw new AssertionError("unstable route");
        if(VpnEvidencePolicy.completeWindow(8000000,40_000_000_000L,30_000_000_000L,512L<<20,1,true))throw new AssertionError("overshot window");
        System.out.println("VpnEvidencePolicy: "+n+" assertions passed");
    }
}
