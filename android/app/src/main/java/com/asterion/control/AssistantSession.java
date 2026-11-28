package com.asterion.control;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.util.UUID;
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
    private InferenceGate.Request activeRequest;
    private boolean actionBusy;
    private InferenceGate.Request modelImportRequest;
    AssistantArtifact pendingArtifact;
    boolean importingModel(){return modelImportRequest!=null;}
    boolean busy(){return actionBusy||conversation.running()||importingModel();}
    private long lastNotification;
    void changed(){for(Runnable listener:listeners)listener.run();}
    void save(Context c){
        try{ControlAssistantMemory.saveConversation(c,conversation);persistenceIssue="";}
        catch(Exception failure){persistenceIssue="History could not be saved. Keep this conversation open.";}
    }
    void send(Context context,String prompt){
        if(busy())return;
        Context app=context.getApplicationContext();
        final AssistantConversation target=conversation;
        long generation=target.begin(prompt);
        InferenceGate.Request request=new InferenceGate.Request();
        activeRequest=request;
        String project=target.project;
        java.util.List<AssistantConversation.Message> messages=target.modelMessages();
        status="Preparing local model";save(app);changed();
        work.execute(()->{
            String[] finalText={""};
            try{
                String answer=OnDeviceLlm.generate(app,project,messages,new OnDeviceLlm.Stream(){
                    public void context(int tokens,int omitted,int dropped){main.post(()->{
                        if(activeRequest!=request || !target.running() || target.revision!=generation)return;
                        target.messages.get(target.messages.size()-1).omittedContextMessages=omitted;
                        target.messages.get(target.messages.size()-1).omittedReferenceBlocks=dropped;
                        status="Generating on this phone"+(omitted==0?"":" · "+omitted+" earlier messages outside active context")+(dropped==0?"":" · "+dropped+" reference blocks omitted");changed();});}
                    public void text(String text){
                        finalText[0]=text;
                        long now=android.os.SystemClock.elapsedRealtime();
                        if(now-lastNotification<70)return;lastNotification=now;
                        main.post(()->{if(target.update(generation,text,"running"))changed();});
                    }
                },request);
                main.post(()->{
                    if(activeRequest!=request)return;
                    activeRequest=null;
                    target.update(generation,answer,request.isCancelled()?"cancelled":"completed");
                    status=request.isCancelled()?"Stopped":"";save(app);changed();
                });
            }catch(Exception|LinkageError failure){
                main.post(()->{
                    if(activeRequest!=request)return;
                    activeRequest=null;
                    target.update(generation,finalText[0],request.isCancelled()?"cancelled":"failed");
                    status=request.isCancelled()?"Stopped":"The local model could not finish. Your message is retained; you can retry.";
                    save(app);changed();
                });
            }
        });
    }
    private boolean canOperate(AssistantConversation owner,AssistantConversation.Message message){
        return !busy()&&conversation==owner&&owner.messages.contains(message)&&message.role.equals("assistant")&&message.state.equals("completed");
    }
    void authorize(Context context,AssistantConversation owner,AssistantConversation.Message message,JSONObject proposal){
        if(!canOperate(owner,message)||message.actionRecord!=null)return;
        Context app=context.getApplicationContext();
        AssistantActionRecord initial=new AssistantActionRecord("assistant-"+UUID.randomUUID(),
            proposal.optString("package"),proposal.optString("action"),"submission_pending","outcome_unknown");
        message.actionRecord=initial;
        save(app);
        if(ControlAssistantPreferences.saveHistory(app)&&!persistenceIssue.isEmpty()){
            message.actionRecord=null;status="Action was not submitted: history could not be saved.";changed();return;
        }
        actionBusy=true;owner.revision++;status="Checking signed capability";changed();
        work.execute(()->{
            AssistantActionRecord observed=initial;
            boolean invoking=false;
            try{
                AssistantCapabilities.validate(app,proposal);
                JSONObject request=new JSONObject(proposal.toString()).put("request_id",initial.requestId);
                invoking=true;
                JSONObject receipt=AppBridge.invoke(app,request);
                observed=observed.submitted(receipt.optString("status","outcome_unknown"));
                observed=observed.withData(AssistantPartnerEvidence.capture(observed,receipt));
                JSONObject state=AppBridge.operation(app,initial.appPackage,initial.requestId,false);
                observed=observed.observed(state.optString("status","outcome_unknown"));
                observed=observed.withData(AssistantPartnerEvidence.capture(observed,state));
            }catch(Exception failure){
                if(!invoking)observed=observed.submitted("not_dispatched");
            }
            finishAction(app,owner,message,observed);
        });
    }
    void recheck(Context context,AssistantConversation owner,AssistantConversation.Message message){
        if(!canOperate(owner,message)||message.actionRecord==null)return;
        Context app=context.getApplicationContext();AssistantActionRecord initial=message.actionRecord;
        actionBusy=true;status="Checking existing operation without replay";changed();
        work.execute(()->{
            AssistantActionRecord observed=initial;
            try{
                JSONObject state=AppBridge.operation(app,initial.appPackage,initial.requestId,false);
                observed=initial.observed(state.optString("status","outcome_unknown"));
                observed=observed.withData(AssistantPartnerEvidence.capture(observed,state));
            }catch(Exception failure){observed=initial.observed("outcome_unknown");}
            finishAction(app,owner,message,observed);
        });
    }
    private void finishAction(Context app,AssistantConversation owner,AssistantConversation.Message message,AssistantActionRecord observed){
        main.post(()->{
            actionBusy=false;
            if(conversation!=owner||!owner.messages.contains(message)){status="Operation outcome retained by the existing bridge.";changed();return;}
            message.actionRecord=observed;owner.revision++;
            status="Provider observation: "+observed.observation+". Output verification remains separate.";
            save(app);changed();
        });
    }
    void importPdf(Context context,android.net.Uri uri,String project,int first,int last){
        if(busy()||!project.equals(conversation.project))return;
        Context app=context.getApplicationContext();
        actionBusy=true;status="Extracting selected PDF pages locally";changed();
        work.execute(()->{
            String outcome;
            try{
                ProjectSourceText source=AssistantPdfImport.extract(app,uri,first,last);
                ControlAssistantMemory.importProjectSource(app,project,source);
                outcome="Encrypted PDF text available: "+source.name+
                    ". Only extracted text is searchable; images and diagrams have not been analyzed.";
            }catch(Exception failure){
                String reason=failure.getMessage();
                if("no_extractable_text".equals(reason))outcome="No extractable text on the selected pages. Image-only pages require a vision or OCR engine.";
                else if("pdf_text_budget".equals(reason))outcome="Selected text exceeds the import budget. Choose a smaller page range.";
                else outcome="PDF not imported. Check document size, encryption, page range and local storage.";
            }
            String report=outcome;
            main.post(()->{actionBusy=false;status=report;changed();});
        });
    }
    void importModel(Context context,java.util.List<android.net.Uri> documents,boolean adapter){
        if(busy())return;
        Context app=context.getApplicationContext();
        InferenceGate.Request request=new InferenceGate.Request();
        modelImportRequest=request;status="Importing signed model file";changed();
        work.execute(()->{
            String result;
            try{
                OnDeviceModelProfile profile=OnDeviceModelProfile.read(app);
                long total=adapter?profile.adapterBytes:profile.bytes;
                OnDeviceLlm.importOwnerModelArtifact(app,documents,adapter,request,received->main.post(()->{
                    if(modelImportRequest!=request||request.isCancelled())return;
                    status="Verifying "+(adapter?"adapter":"model")+" · "+(received*100/total)+"%";
                    changed();
                }));
                result=(adapter?"Adapter":"Model")+" imported and SHA-256 verified. Other required files must also be present before inference.";
            }catch(InterruptedException stopped){result="Model import cancelled; previous files retained.";}
            catch(Exception|LinkageError failure){
                result="Model import did not complete. Check the signed profile, exact file identity and available storage.";
            }
            final String report=result;
            main.post(()->{
                if(modelImportRequest!=request)return;
                modelImportRequest=null;status=report;changed();
            });
        });
    }
    void cancel(){
        if(modelImportRequest!=null){
            OnDeviceLlm.cancel(modelImportRequest);status="Cancelling model import";changed();return;
        }
        if(activeRequest!=null&&conversation.running()){
            OnDeviceLlm.cancel(activeRequest);
            status="Stopping";changed();
        }
    }
}
