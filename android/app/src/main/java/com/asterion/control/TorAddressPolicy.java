package com.asterion.control;

import java.net.URI;
import java.util.Locale;
import java.security.MessageDigest;
import java.util.Arrays;

/** Parse onion destinations locally; never send onion text to a public search provider. */
final class TorAddressPolicy {
    private static final String ALPHABET="abcdefghijklmnopqrstuvwxyz234567";
    private TorAddressPolicy(){}
    static boolean onionHost(String host){
        if(host==null)return false;
        String h=host.toLowerCase(Locale.ROOT);
        while(h.endsWith("."))h=h.substring(0,h.length()-1);
        return h.equals("onion")||h.endsWith(".onion");
    }
    static boolean looksOnion(String raw){
        return raw!=null&&raw.toLowerCase(Locale.ROOT).contains(".onion");
    }
    static boolean validV3(String host){
        if(!onionHost(host))return false;
        String h=host.toLowerCase(Locale.ROOT);
        String[] parts=h.split("\\.");
        if(parts.length<2||!parts[parts.length-1].equals("onion"))return false;
        String label=parts[parts.length-2];
        if(label.length()!=56)return false;
        try{
            byte[] decoded=new byte[35];int buffer=0,bits=0,at=0;
            for(int i=0;i<label.length();i++){
                int v=ALPHABET.indexOf(label.charAt(i));if(v<0)return false;
                buffer=(buffer<<5)|v;bits+=5;
                if(bits>=8){decoded[at++]=(byte)(buffer>>(bits-8));bits-=8;}
            }
            if(at!=35||decoded[34]!=3)return false;
            MessageDigest digest=MessageDigest.getInstance("SHA3-256");
            digest.update(".onion checksum".getBytes(java.nio.charset.StandardCharsets.US_ASCII));
            digest.update(decoded,0,32);digest.update((byte)3);
            byte[] hash=digest.digest();
            return decoded[32]==hash[0]&&decoded[33]==hash[1];
        }catch(Exception e){return false;}
    }
    static String resolve(String raw){
        if(raw==null)return null;
        String value=raw.trim();
        if(value.isEmpty()||value.length()>4096||value.indexOf('\\')>=0||value.chars().anyMatch(c->c<=32||c==127))return null;
        if(!value.matches("(?i)^https?://.*")){
            if(value.contains("://")||value.matches("(?i)^[a-z][a-z0-9+.-]*:.*")&&!value.matches("(?i)^[a-z0-9.-]+:[0-9]+(?:[/?#].*)?$"))return null;
            value=(looksOnion(value)?"http://":"https://")+value;
        }
        try{
            URI u=URI.create(value);String host=u.getHost();
            if(host==null||u.getRawUserInfo()!=null||u.getPort()==0||u.getPort()>65535)return null;
            String h=host.toLowerCase(Locale.ROOT);
            if(onionHost(h))return validV3(h)?value:null;
            // Do not turn the Tor browser into an internal-network proxy or
            // allow unencrypted exit traffic. Onion HTTP stays inside Tor.
            if(!"https".equalsIgnoreCase(u.getScheme())||!h.contains(".")||
                !h.matches("[a-z0-9.-]+")||h.matches("[0-9.]+")||
                h.endsWith(".local")||h.endsWith(".internal")||h.endsWith(".localhost"))return null;
            return value;
        }catch(Exception e){return null;}
    }
}
