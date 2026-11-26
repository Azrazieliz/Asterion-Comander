package com.asterion.control;
public final class BrowserDownloadContractTest {
    private static int checks;
    private static void expect(boolean actual,boolean expected){
        checks++;if(actual!=expected)throw new AssertionError("case "+checks);
    }
    public static void main(String[] args){
        String id="browser-12345678-1234-1234-1234-123456789abc";
        for(String pkg:new String[]{BrowserDownloadContract.DOWNLOADER,BrowserDownloadContract.DOWNLOADER_ACCEPTANCE,BrowserDownloadContract.NEXUS}){
            expect(BrowserDownloadContract.canDispatch(pkg,"download","https://example.com/file",id),true);
            expect(BrowserDownloadContract.canDispatch(pkg,"download","http://example.com/file",id),true);
            expect(BrowserDownloadContract.canDispatch(pkg,"diagnostics","https://example.com/file",id),false);
            expect(BrowserDownloadContract.canDispatch(pkg,"download","file:///tmp/secret",id),false);
            expect(BrowserDownloadContract.canDispatch(pkg,"download","https://user:pass@example.com/",id),false);
            expect(BrowserDownloadContract.canDispatch(pkg,"download","https://example.com/"+"x".repeat(3501),id),false);
            expect(BrowserDownloadContract.canDispatch(pkg,"download","https://example.com/file","other-request"),false);
        }
        expect(BrowserDownloadContract.canDispatch("com.other.app","download","https://example.com/file",id),false);
        expect(BrowserDownloadContract.ownerPackage("com.asterion.nexus.fake"),false);
        expect(BrowserDownloadContract.ownerPackage(null),false);
        for(String s:new String[]{"completed","failed","rejected","cancelled","canceled"})expect(BrowserDownloadContract.terminal(s),true);
        for(String s:new String[]{"accepted","running","cancel_requested","outcome_unknown","unavailable",null})expect(BrowserDownloadContract.terminal(s),false);
        System.out.println("BrowserDownloadContract: "+checks+" assertions passed");
    }
}
