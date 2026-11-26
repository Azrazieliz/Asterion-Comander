package com.asterion.control;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** Executes the production JNI on a host CPU. Explicitly NOT Android acceptance. */
public final class OnDeviceLlm {
    private static native boolean nativeLoad(String path);
    private static native boolean nativeReady();
    private static native byte[] nativeGenerate(byte[] system,String[] roles,byte[][] content,int limit,int context,NativeStream stream);
    private static native void nativeCancel();
    private static native void nativeResetCancel();
    static final class NativeStream {
        final AssistantOutput output=new AssistantOutput();
        final CountDownLatch started=new CountDownLatch(1);
        int pieces=0,omitted=0,tokens=0;
        public void onStart(boolean thinking,int used,int dropped){output.initialThinking(thinking);tokens=used;omitted=dropped;started.countDown();}
        public void onToken(byte[] bytes){pieces++;String visible=output.append(bytes);if(visible.contains("<think>"))throw new AssertionError("delimiter leaked");}
    }
    private static byte[] bytes(String text){return text.getBytes(StandardCharsets.UTF_8);}
    public static void main(String[] args)throws Exception{
        System.load(args[0]);if(!nativeLoad(args[1])||!nativeReady())throw new AssertionError("model did not load");
        NativeStream first=new NativeStream();
        byte[] answer=nativeGenerate(bytes("You are Asterion Control running inside its native application. Answer concisely."),new String[]{"user"},new byte[][]{bytes("What is two plus two? Answer in one short sentence.")},384,1024,first);
        if(answer==null||answer.length==0||first.pieces<1)throw new AssertionError("no real streamed generation");
        String visible=first.output.finish(answer);
        System.out.println("HOST_JNI_GENERATION pieces="+first.pieces+" prompt_tokens="+first.tokens+" public="+visible.replace('\n',' '));
        NativeStream packed=new NativeStream();
        answer=nativeGenerate(bytes("You are Asterion Control. Answer briefly."),new String[]{"user","assistant","user"},new byte[][]{bytes("Earlier context. ".repeat(600)),bytes("Earlier result."),bytes("Reply briefly: 3 + 4 = ?")},256,512,packed);
        if(answer==null||packed.omitted!=2)throw new AssertionError("native context packing did not omit complete oldest exchange");
        System.out.println("HOST_JNI_CONTEXT omitted_messages="+packed.omitted+" prompt_tokens="+packed.tokens);
        NativeStream cancel=new NativeStream();final byte[][] result={null};
        Thread thread=new Thread(()->{result[0]=nativeGenerate(bytes("Explain carefully."),new String[]{"user"},new byte[][]{bytes("Give a detailed explanation of sorting algorithms.")},2048,4096,cancel);});
        thread.start();if(!cancel.started.await(30,TimeUnit.SECONDS))throw new AssertionError("native generation did not start");
        long statusStarted=System.nanoTime();
        if(!nativeReady()||(System.nanoTime()-statusStarted)>100_000_000L)throw new AssertionError("model status blocked behind generation");
        nativeCancel();thread.join(30000);if(thread.isAlive()||result[0]!=null)throw new AssertionError("native cancellation failed");
        nativeResetCancel();
        System.out.println("HOST_JNI_CANCEL returned_without_completed_answer=true");
        System.out.println("HOST_JNI_ACCEPTANCE three runtime checks passed; phone/model quality unverified");
    }
}
