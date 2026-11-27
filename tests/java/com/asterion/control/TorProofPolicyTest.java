package com.asterion.control;
public final class TorProofPolicyTest {
    private static void check(boolean value){if(!value)throw new AssertionError();}
    public static void main(String[] args){
        check(TorProofPolicy.isTor(true,"192.0.2.1"));
        check(TorProofPolicy.isTor(true,"2001:db8::1"));
        check(!TorProofPolicy.isTor(false,"192.0.2.1"));
        check(!TorProofPolicy.isTor(true,"example.com"));
        check(!TorProofPolicy.isTor(true,"999.1.1.1"));
        check(!TorProofPolicy.isTor(true,""));
        check(!TorProofPolicy.isTor(true,"2001:db8::bad%wlan0"));
        System.out.println("Tor proof policy passed");
    }
}
