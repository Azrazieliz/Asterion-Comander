package com.asterion.control;

import android.content.Context;
import android.os.Looper;

/** Voice transport to the EXISTING canonical assistant. No model or tool engine duplicated. */
final class VoiceNativeAssistant {
    interface Listener {
        void accepted();
        void completed(String text,boolean actionReviewRequired);
        void failed(String state);
    }
    private final AssistantSession session=AssistantSession.INSTANCE;
    private AssistantConversation target;
    private long revision;
    private Listener callback;
    private final Runnable observer=this::observe;
    boolean busy(){return callback!=null;}
    boolean submit(Context context,String text,Listener listener){
        if(Looper.myLooper()!=Looper.getMainLooper())throw new IllegalStateException("Main thread required");
        if(busy()||session.busy())return false;
        target=session.conversation;revision=target.revision+1;callback=listener;
        session.listeners.add(observer);
        try{
            session.send(context,text);
            if(target.revision!=revision){detach();return false;}
            listener.accepted();
            observe();
            return true;
        }catch(RuntimeException failure){detach();throw failure;}
    }
    private void observe(){
        if(callback==null||target==null)return;
        if(target.revision!=revision){Listener done=callback;detach();done.failed("superseded");return;}
        if(target.running())return;
        if(target.messages.isEmpty())return;
        AssistantConversation.Message last=target.messages.get(target.messages.size()-1);
        Listener done=callback;detach();
        if(!"assistant".equals(last.role)||!"completed".equals(last.state)||last.text.isBlank()){
            done.failed(last.state);return;
        }
        // Never speak or execute an assistant action block. The canonical
        // workspace already provides explicit owner review of tool proposals.
        int marker=last.text.indexOf("```asterion_action");
        String speech=marker<0?last.text:last.text.substring(0,marker).trim();
        done.completed(speech,marker>=0);
    }
    void interrupt(){
        if(callback!=null&&session.conversation==target&&target.revision==revision&&target.running())
            session.cancel();
        detach();
    }
    private void detach(){session.listeners.remove(observer);target=null;callback=null;}
}
