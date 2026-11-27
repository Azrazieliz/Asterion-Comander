package com.asterion.control;

/** A positive official Tor check must carry a numeric, nonempty IP address.
 * Does not certify DNS leaks, fingerprinting, or anonymity beyond that request.
 */
final class TorProofPolicy {
    static boolean isTor(boolean claim,String ip){
        if(!claim||ip==null||ip.isBlank()||ip.length()>45||ip.indexOf('%')>=0)return false;
        if(ip.indexOf(':')>=0){
            if(!ip.matches("[0-9a-fA-F:.]+"))return false;
            try{return java.net.InetAddress.getByName(ip) instanceof java.net.Inet6Address;}
            catch(Exception invalid){return false;}
        }
        String[] parts=ip.split("\\.",-1);
        if(parts.length!=4)return false;
        for(String part:parts){
            if(!part.matches("[0-9]{1,3}")||Integer.parseInt(part)>255)return false;
        }
        return true;
    }
}
