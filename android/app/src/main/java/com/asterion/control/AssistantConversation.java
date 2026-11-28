package com.asterion.control;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Conversation state independent of Activity lifetime and native inference. */
final class AssistantConversation {
    static final class Message {
        final String id,role;
        String text,state;
        int omittedContextMessages=0,omittedReferenceBlocks=0;
        AssistantActionRecord actionRecord;
        boolean visual;
        String visualEvidence="";
        Message(String id,String role,String text,String state){
            if(!role.equals("user")&&!role.equals("assistant"))throw new IllegalArgumentException("invalid_role");
            this.id=id;this.role=role;this.text=text;this.state=state;
        }
    }
    final String id;
    String title="New conversation",project="General";
    AssistantResearchSelection researchSelection;
    final List<Message> messages=new ArrayList<>();
    long revision=0;
    AssistantConversation(){this(UUID.randomUUID().toString());}
    AssistantConversation(String id){this.id=id;}
    long begin(String text){
        if(text==null||text.isBlank())throw new IllegalArgumentException("empty_message");
        if(running())throw new IllegalStateException("conversation_busy");
        if(messages.isEmpty())title=text.strip().replace('\n',' ').substring(0,Math.min(64,text.strip().replace('\n',' ').length()));
        messages.add(new Message(UUID.randomUUID().toString(),"user",text,"completed"));
        messages.add(new Message(UUID.randomUUID().toString(),"assistant","","running"));
        return ++revision;
    }
    AssistantConversation fork(){
        AssistantConversation copy=new AssistantConversation();
        copy.title=title+" · revision";copy.project=project;copy.researchSelection=researchSelection;
        for(Message m:messages){Message cloned=new Message(m.id,m.role,m.text,m.state);
            cloned.omittedContextMessages=m.omittedContextMessages;cloned.omittedReferenceBlocks=m.omittedReferenceBlocks;cloned.actionRecord=m.actionRecord;cloned.visual=m.visual;cloned.visualEvidence=m.visualEvidence;copy.messages.add(cloned);}
        return copy;
    }
    boolean running(){return !messages.isEmpty()&&messages.get(messages.size()-1).state.equals("running");}
    boolean update(long generation,String text,String state){
        if(generation!=revision||!running())return false;
        Message last=messages.get(messages.size()-1);
        last.text=text;last.state=state;return true;
    }
    void recover(){
        for(Message m:messages)if(m.state.equals("running"))m.state="interrupted";
        revision++;
    }
    void editFrom(int index,String text){
        if(running()||index<0||index>=messages.size()||!messages.get(index).role.equals("user"))
            throw new IllegalStateException("invalid_edit");
        messages.subList(index,messages.size()).clear();
        revision++;
    }
    String retry(){
        if(running()||messages.size()<2)throw new IllegalStateException("invalid_retry");
        int at=messages.size()-2;
        if(!messages.get(at).role.equals("user"))throw new IllegalStateException("invalid_retry");
        String prompt=messages.get(at).text;
        messages.subList(at,messages.size()).clear();revision++;
        return prompt;
    }
    List<Message> modelMessages(){
        ArrayList<Message> out=new ArrayList<>();
        for(int i=0;i<messages.size();i++){
            Message m=messages.get(i);
            if(m.role.equals("user")){
                if(i==messages.size()-2&&running()){out.add(m);break;}
                if(i+1<messages.size()&&messages.get(i+1).role.equals("assistant")&&
                    (messages.get(i+1).state.equals("completed")||messages.get(i+1).state.equals("truncated"))){
                    out.add(m);
                    Message answer=messages.get(++i);
                    if(answer.visual){
                        // This is a historical model observation, never pixels,
                        // executable structured data or authorization.
                        String evidence=answer.visualEvidence.replace("<","\\u003c").replace(">","\\u003e");
                        String observed=answer.text.replace("<","\\u003c").replace(">","\\u003e");
                        out.add(new Message(answer.id,answer.role,"Historical local visual model observation (unverified interpretation):\n"+
                            evidence+"\n"+observed,answer.state));
                    }else out.add(answer);
                }
            }
        }
        return out;
    }
}
