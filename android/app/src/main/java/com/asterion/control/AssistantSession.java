package com.asterion.control;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** One process-owned session. Rotation detaches views, never starts a second generation. */
final class AssistantSession {
    static final AssistantSession INSTANCE=new AssistantSession();
    final ExecutorService work=Executors.newSingleThreadExecutor();
    private final Handler main=new Handler(Looper.getMainLooper());
    final CopyOnWriteArrayList<Runnable> listeners=new CopyOnWriteArrayList<>();
    AssistantConversation conversation=new AssistantConversation();
    String status="",persistenceIssue="";
    private volatile boolean stopRequested;
    private long lastNotification;
    void changed(){for(Runnable listener:listeners)listener.run();}
    void save(Context c){
        try{ControlAssistantMemory.saveConversation(c,conversation);persistenceIssue="";}
        catch(Exception failure){persistenceIssue="History could not be saved. Keep this conversation open.";}
    }
    void send(Context context,String prompt){
        if(conversation.running())return;
        Context app=context.getApplicationContext();
        final AssistantConversation target=conversation;
        long generation=target.begin(prompt);stopRequested=false;
        status="Preparing local model";save(app);changed();
        work.execute(()->{
            String[] finalText={""};
            try{
                if(stopRequested)throw new InterruptedException();
                String answer=OnDeviceLlm.generate(app,target.project,target.modelMessages(),new OnDeviceLlm.Stream(){
                    public void context(int tokens,int omitted){main.post(()->{
                        target.messages.get(target.messages.size()-1).omittedContextMessages=omitted;
                        status=omitted==0?"Generating on this phone":"Generating · "+omitted+" earlier messages outside active context";changed();});}
                    public void text(String text){
                        finalText[0]=text;
                        long now=android.os.SystemClock.elapsedRealtime();
                        if(now-lastNotification<70)return;lastNotification=now;
                        main.post(()->{if(target.update(generation,text,"running"))changed();});
                    }
                });
                main.post(()->{
                    target.update(generation,answer,stopRequested?"cancelled":"completed");
                    status=stopRequested?"Stopped":"";save(app);changed();
                });
            }catch(Exception|LinkageError failure){
                main.post(()->{
                    target.update(generation,finalText[0],stopRequested?"cancelled":"failed");
                    status=stopRequested?"Stopped":"The local model could not finish. Your message is retained; you can retry.";
                    save(app);changed();
                });
            }
        });
    }
    void cancel(){if(conversation.running()){stopRequested=true;OnDeviceLlm.cancel();status="Stopping";changed();}}
}
