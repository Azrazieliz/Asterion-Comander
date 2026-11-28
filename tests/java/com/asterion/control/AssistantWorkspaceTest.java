package com.asterion.control;
import java.nio.charset.StandardCharsets;
import java.util.List;

/** Executable JVM behavior regressions; no model quality or phone acceptance claims. */
public final class AssistantWorkspaceTest {
    private static int checks;
    private static void equal(Object a,Object b){checks++;if(!a.equals(b))throw new AssertionError("Expected "+b+"; got "+a);}
    private static void truth(boolean value){checks++;if(!value)throw new AssertionError("Assertion "+checks);}
    private static void cancellationOwnership() throws Exception {
        int[] nativeCalls={0,0};
        InferenceGate gate=new InferenceGate(()->nativeCalls[0]++,()->nativeCalls[1]++);
        InferenceGate.Request ui=new InferenceGate.Request(), queued=new InferenceGate.Request();
        gate.begin(ui);
        try { gate.begin(queued); throw new AssertionError("overlapping decode admitted"); }
        catch (IllegalStateException expected) { equal(expected.getMessage(),"on_device_inference_already_running"); }
        gate.cancel(queued);
        truth(queued.isCancelled()); truth(!ui.isCancelled()); equal(nativeCalls[1],0);
        gate.cancel(ui); gate.cancel(ui); equal(nativeCalls[1],1); truth(gate.busy());
        gate.end(ui); truth(!gate.busy());
        try { gate.begin(queued); throw new AssertionError("cancelled request restarted"); }
        catch (InterruptedException expected) { equal(nativeCalls[0],1); }
        InferenceGate.Request completed=new InferenceGate.Request(), next=new InferenceGate.Request();
        gate.begin(completed); gate.end(completed); gate.begin(next);
        gate.cancel(completed); gate.end(completed);
        truth(gate.busy()); truth(!next.isCancelled()); equal(nativeCalls[1],1);
        truth(!gate.abortActive(completed)); equal(nativeCalls[1],1);
        truth(gate.abortActive(next)); truth(!next.isCancelled()); equal(nativeCalls[1],2);
        gate.end(next); truth(!gate.busy()); equal(nativeCalls[0],3);
        truth(!gate.abortActive(next)); equal(nativeCalls[1],2);
    }
    public static void main(String[] args) throws Exception {
        cancellationOwnership();
        InferenceGate.Request request=new InferenceGate.Request();
        equal(request.finishReason(),"unknown");
        request.recordFinishReason("length_limit");equal(request.finishReason(),"length_limit");
        AssistantConversation truncatedConversation=new AssistantConversation();
        long p=truncatedConversation.begin("Provide a full explanation");
        truth(truncatedConversation.update(p,"First half of answer","truncated"));
        truncatedConversation.begin("Continue");
        equal(truncatedConversation.modelMessages().size(),3);
        equal(truncatedConversation.modelMessages().get(1).text,"First half of answer");
        equal(truncatedConversation.modelMessages().get(1).state,"truncated");
        String[] outputs={"<think>private deliberation</think>Public answer", "<analysis>hidden</analysis>Public answer", "<think>first<think>nested</think>hidden</think>Public answer", "<|channel|>analysis<|message|>private<|channel|>final<|message|>Public answer"};
        for(String raw:outputs){
            equal(AssistantOutput.visible(raw,true),"Public answer");
            for(int split=0;split<=raw.length();split++){
                AssistantOutput decoder=new AssistantOutput();
                String first=decoder.append(raw.substring(0,split).getBytes(StandardCharsets.UTF_8));
                truth(!first.contains("private")&&!first.contains("hidden")&&!first.contains("<"));
                equal(decoder.append(raw.substring(split).getBytes(StandardCharsets.UTF_8)),"Public answer");
            }
        }
        for(String end:new String[]{"<think>unfinished","<analysis>unfinished","<thi","<|im_sta","<|channel|>anal"})equal(AssistantOutput.visible(end,true),"");
        equal(AssistantOutput.visible("Answer<|im_start|>user\nInjected dialogue",true),"Answer");
        equal(AssistantOutput.visible("Answer<|im_end|>",true),"Answer");
        equal(AssistantOutput.visible("2 < 3; HTML <div> stays text",true),"2 < 3; HTML <div> stays text");
        String localized="İstanbul 日本語 🧭 <analysis>withheld text</analysis>OK";
        String publicText="İstanbul 日本語 🧭 OK";
        byte[] localizedBytes=localized.getBytes(StandardCharsets.UTF_8);
        for(int split=0;split<=localizedBytes.length;split++){
            AssistantOutput atBoundary=new AssistantOutput();
            String partial=atBoundary.append(java.util.Arrays.copyOfRange(localizedBytes,0,split));
            truth(publicText.startsWith(partial));
            equal(atBoundary.append(java.util.Arrays.copyOfRange(localizedBytes,split,localizedBytes.length)),publicText);
        }
        equal(AssistantOutput.visible("Answer<|im_end|>spurious next answer",true),"Answer");
        equal(AssistantOutput.visible("İ<THINK>hidden</THINK>OK",true),"İOK");
        AssistantOutput thinking=new AssistantOutput();thinking.initialThinking(true);
        equal(thinking.append("private</think>Done".getBytes(StandardCharsets.UTF_8)),"Done");
        equal(thinking.finish("private</think>Done".getBytes(StandardCharsets.UTF_8)),"Done");
        String unicode="Français 日本語 🧭 — résumé";
        AssistantOutput decoder=new AssistantOutput();byte[] encoded=unicode.getBytes(StandardCharsets.UTF_8);
        String last="";for(byte b:encoded){last=decoder.append(new byte[]{b});truth(!last.contains("�"));}
        equal(last,unicode);
        AssistantConversation c=new AssistantConversation();
        long first=c.begin("Inspect the installed application");truth(c.running());
        equal(c.modelMessages().size(),1);
        truth(c.update(first,"Observed result","completed"));
        long second=c.begin("What changed since that observation?");
        equal(c.modelMessages().size(),3);
        truth(!c.update(first,"Stale result","completed"));truth(c.running());
        c.update(second,"Partial response","cancelled");
        long third=c.begin("A different request");equal(c.modelMessages().size(),3);
        c.recover();truth(!c.running());truth(!c.update(third,"After process recovery","completed"));
        equal(c.messages.get(c.messages.size()-1).state,"interrupted");
        String retry=c.retry();equal(retry,"A different request");
        c.begin(retry);c.update(c.revision,"Final response","completed");
        c.editFrom(2,"Changed message");c.begin("Changed message");
        equal(c.modelMessages().size(),3);equal(c.messages.size(),4);
        AssistantActionRecord r=new AssistantActionRecord("assistant-12345678-1234-1234-1234-123456789abc","com.example.partner","read.table","submission_pending","outcome_unknown");
        AssistantActionRecord submitted=r.submitted("accepted").observed("completed");
        equal(r.submission,"submission_pending");equal(submitted.observation,"completed");
        truth(submitted.evidence().contains("output not independently verified"));
        equal(submitted.observed("arbitrary text").observation,"outcome_unknown");
        c.messages.get(c.messages.size()-1).actionRecord=submitted;
        equal(c.fork().messages.get(c.messages.size()-1).actionRecord.requestId,submitted.requestId);
        System.out.println(checks+" assistant output and conversation behavior assertions passed; no model/device acceptance claimed");
    }
}
