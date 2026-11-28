package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.res.Configuration;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.database.Cursor;
import android.speech.RecognizerIntent;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONArray;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.UUID;

/** Local assistant workspace. No changes to the paired agent, signer or specialist engines. */
public final class AssistantActivity extends Activity {
    private final AssistantSession session=AssistantSession.INSTANCE;
    private final Runnable observer=this::render;
    private LinearLayout root,body;
    private ScrollView transcript;
    private TextView title,status,send,model,project;
    private EditText composer;
    private int bg,text,muted,panel,accent,edge;
    private TextToSpeech speech;
    private boolean speechReady=false;
    private String draft="";
    private long drawnRevision=-1;
    private boolean drawnRunning=false;
    private int drawnCount=-1;
    private LinearLayout liveAnswer;
    private String liveText="";
    private boolean alive=true;
    private String pendingSourceProject;
    private int dp(int x){return DesignSystem.dp(this,x);}
    private TextView label(String value,int size,int color,boolean bold){return DesignSystem.text(this,value,size,color,bold);}
    private TextView control(String name,Runnable action){
        TextView v=label(name,14,text,true);v.setGravity(Gravity.CENTER);v.setMinWidth(dp(48));v.setMinHeight(dp(48));
        v.setPadding(dp(12),dp(8),dp(12),dp(8));v.setContentDescription(name);
        DesignSystem.clickable(v,this,panel,0,12);v.setOnClickListener(w->action.run());return v;
    }
    @Override public void onCreate(Bundle state){super.onCreate(state);
        boolean dark=(getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        bg=dark?0xFF0D1015:0xFFF7F8FA;panel=dark?0xFF191D25:Color.WHITE;
        text=dark?0xFFF1F2F5:0xFF181D26;muted=dark?0xFFA7AFBD:0xFF566174;
        accent=dark?0xFFC5B5FF:0xFF6546C7;edge=dark?0xFF343B48:0xFFDADEE6;
        getWindow().setStatusBarColor(bg);getWindow().setNavigationBarColor(bg);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        root=DesignSystem.vertical(this);root.setBackgroundColor(bg);
        root.setOnApplyWindowInsetsListener((v,insets)->{
            if(android.os.Build.VERSION.SDK_INT<30){root.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());return insets;}
            android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());
            android.graphics.Insets keyboard=insets.getInsets(WindowInsets.Type.ime());
            root.setPadding(bars.left,bars.top,bars.right,Math.max(bars.bottom,keyboard.bottom));return insets;
        });
        setContentView(root);root.requestApplyInsets();
        if(!dark)root.setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
        LinearLayout bar=DesignSystem.horizontal(this);bar.setPadding(dp(12),dp(8),dp(12),dp(8));
        bar.addView(control("History",this::history));
        title=label("",19,text,true);title.setSingleLine(true);title.setEllipsize(android.text.TextUtils.TruncateAt.END);
        title.setPadding(dp(12),0,dp(8),0);title.setMinHeight(dp(48));title.setGravity(Gravity.CENTER_VERTICAL);
        title.setOnClickListener(v->rename());title.setContentDescription("Rename conversation");bar.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        bar.addView(control("New",this::newConversation));root.addView(bar);
        LinearLayout meta=DesignSystem.horizontal(this);meta.setPadding(dp(16),0,dp(16),dp(8));
        project=control("General",this::changeProject);meta.addView(project);
        model=control("",this::modelSettings);meta.addView(model,new LinearLayout.LayoutParams(0,-2,1));root.addView(meta);
        body=DesignSystem.vertical(this);transcript=new ScrollView(this);transcript.setFillViewport(true);
        body.setPadding(dp(20),dp(8),dp(20),dp(20));transcript.addView(body);
        root.addView(transcript,new LinearLayout.LayoutParams(-1,0,1));
        status=label("",12,muted,false);status.setPadding(dp(20),dp(6),dp(20),dp(6));status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);root.addView(status);
        LinearLayout box=DesignSystem.vertical(this);box.setPadding(dp(14),dp(8),dp(14),dp(10));
        composer=new EditText(this);composer.setTextColor(text);composer.setTextSize(16);composer.setHintTextColor(muted);composer.setHint("Message Asterion");
        composer.setMaxLines(7);composer.setMinLines(1);composer.setPadding(dp(14),dp(12),dp(14),dp(12));
        composer.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE|android.text.InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);
        composer.setBackground(DesignSystem.shape(this,panel,edge,18));box.addView(composer,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout actions=DesignSystem.horizontal(this);actions.addView(control("Attach",this::attach));actions.addView(control("Voice",this::voice));
        View space=new View(this);actions.addView(space,new LinearLayout.LayoutParams(0,1,1));
        send=control("Send",()->{if(session.conversation.running()||session.importingModel())session.cancel();else submit();});send.setTextColor(accent);actions.addView(send);box.addView(actions);root.addView(box);
        if(state!=null){draft=state.getString("draft","");composer.setText(draft);}
        speech=new TextToSpeech(this,result->{speechReady=result==TextToSpeech.SUCCESS;});
        session.listeners.add(observer);render();
        String research=getIntent().getStringExtra("research_draft");getIntent().removeExtra("research_draft");
        if(state==null&&research!=null){offerResearchDraft(research);return;}
        String previous=getSharedPreferences("control",MODE_PRIVATE).getString("assistant_last_conversation","");
        if(session.conversation.messages.isEmpty()&&!previous.isEmpty()&&ControlAssistantPreferences.saveHistory(this)){
            final String emptyId=session.conversation.id;
            session.work.execute(()->{try{AssistantConversation saved=ControlAssistantMemory.loadConversation(this,previous);
                runOnUiThread(()->{if(alive&&session.conversation.id.equals(emptyId)&&session.conversation.messages.isEmpty()){session.conversation=saved;render();}});
            }catch(Exception ignored){}});
        }
    }
    private void offerResearchDraft(String value){
        if(value.length()>12000||!idle()||composer.length()>0){notice("Research handoff unavailable while a draft or response is active.");return;}
        new AlertDialog.Builder(this).setTitle("Review browser research in new conversation")
            .setMessage("Open a new Browser Research conversation and load the comparison draft? The existing conversation is retained if encrypted history is enabled. Nothing is sent automatically.")
            .setPositiveButton("Prepare draft",(d,w)->{
                if(!idle()||composer.length()>0)return;
                session.save(this);
                if(!session.persistenceIssue.isEmpty()){notice("Existing conversation could not be saved; handoff cancelled.");return;}
                session.conversation=new AssistantConversation();session.conversation.project=BrowserResearchText.PROJECT;
                session.status="";composer.setText(value);session.changed();
            }).setNegativeButton("Cancel",null).show();
    }
    @Override protected void onSaveInstanceState(Bundle state){state.putString("draft",composer.getText().toString());super.onSaveInstanceState(state);}
    @Override protected void onDestroy(){alive=false;session.listeners.remove(observer);if(speech!=null){speech.stop();speech.shutdown();}super.onDestroy();}
    private void submit(){
        if(!idle())return;
        String prompt=composer.getText().toString().trim();if(prompt.isEmpty())return;
        try{if(prompt.length()>OnDeviceModelProfile.read(this).inputChars){notice("This message exceeds the current model input budget. Attach a shorter excerpt.");return;}}
        catch(Exception e){notice("The installed model configuration could not be read.");return;}
        composer.setText("");session.send(this,prompt);
    }
    private void render(){
        if(!alive)return;
        AssistantConversation c=session.conversation;
        if(ControlAssistantPreferences.saveHistory(this)&&!c.messages.isEmpty())getSharedPreferences("control",MODE_PRIVATE).edit().putString("assistant_last_conversation",c.id).apply();
        title.setText(c.title);project.setText(c.project);
        model.setText("On device · "+ControlAssistantPreferences.effort(this));
        send.setText(c.running()||session.importingModel()?"Stop":"Send");
        send.setEnabled(!session.busy()||c.running()||session.importingModel());
        status.setText(!session.persistenceIssue.isEmpty()?session.persistenceIssue:session.status);
        boolean atBottom=transcript.getChildCount()==0||body.getHeight()-transcript.getScrollY()-transcript.getHeight()<dp(120);
        boolean rebuild=drawnRevision!=c.revision||drawnCount!=c.messages.size()||drawnRunning!=c.running();
        if(rebuild){
            body.removeAllViews();liveAnswer=null;liveText="";
            if(c.messages.isEmpty()){
                TextView empty=label("Asterion Control",26,text,true);empty.setPadding(0,dp(60),0,dp(8));body.addView(empty);
                TextView local=label(ControlAssistantPreferences.saveHistory(this)?"On-device model · Encrypted history":"On-device model · History off",14,muted,false);body.addView(local);
            }
            for(int i=0;i<c.messages.size();i++){
                AssistantConversation.Message m=c.messages.get(i);final int index=i;
                LinearLayout turn=DesignSystem.vertical(this);turn.setPadding(dp(14),dp(12),dp(14),dp(12));
                if(m.role.equals("user"))turn.setBackground(DesignSystem.shape(this,panel,0,16));
                TextView role=label(m.role.equals("user")?"You":"Asterion",12,muted,true);turn.addView(role);
                LinearLayout answer=DesignSystem.vertical(this);turn.addView(answer);
                if(m.state.equals("running")){liveAnswer=answer;liveText=m.text;}
                if(m.role.equals("assistant")&&m.state.equals("completed"))
                    AssistantMarkdown.render(this,answer,m.text,text,muted,panel,selection->submitSelection(c,m,selection),this::exportArtifact);
                else AssistantMarkdown.render(this,answer,m.text,text,muted,panel);
                if(!m.state.equals("running")){
                    LinearLayout tools=DesignSystem.horizontal(this);
                    tools.addView(control("Copy",()->((ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Asterion",m.text))));
                    if(m.role.equals("user"))tools.addView(control("Edit",()->edit(index)));
                    else{
                        tools.addView(control("Read",()->{if(speechReady)speech.speak(m.text,TextToSpeech.QUEUE_FLUSH,null,m.id);else notice("Speech is not ready on this device.");}));
                        if(i==c.messages.size()-1){
                            turn.addView(tools);tools=DesignSystem.horizontal(this);
                            tools.addView(control("Retry",this::retry));
                            tools.addView(control("Continue",()->{if(idle())session.send(this,"Continue the previous answer from where it ended, avoiding repetition.");}));
                        }
                        if(m.actionRecord!=null){
                            tools.addView(control("Check receipt",()->session.recheck(this,c,m)));
                             tools.addView(control("Interpret receipt",()->interpretReceipt(c,m)));
                        }else try{JSONObject proposal=m.state.equals("completed")?AssistantCapabilities.proposal(m.text):null;if(proposal!=null)tools.addView(control("Review action",()->reviewAction(c,m,proposal)));}catch(Exception ignored){}
                        if(m.state.equals("completed"))try{
                            String query=AssistantResearchPlan.parse(m.text);
                            if(query!=null)tools.addView(control("Review search",()->reviewResearch(c,m,query)));
                        }catch(IllegalArgumentException ignored){}
                        if(m.state.equals("completed"))try{
                            AssistantSchedulePlan schedule=AssistantSchedulePlan.parse(m.text);
                            if(schedule!=null)tools.addView(control("Review schedule",()->{
                                if(idle()&&session.conversation==c&&c.messages.contains(m))
                                    AssistantScheduleUi.review(this,schedule,m.id,id->notice("Local schedule saved. Manage it under Tools."));
                            }));
                        }catch(IllegalArgumentException ignored){}
                    }
                    turn.addView(tools);
                    if(m.actionRecord!=null)turn.addView(label(m.actionRecord.evidence(),12,muted,false));
                    if(m.omittedContextMessages>0)turn.addView(label(m.omittedContextMessages+" earlier messages remain in history outside this response's context",12,muted,false));
                    if(m.omittedReferenceBlocks>0)turn.addView(label(m.omittedReferenceBlocks+" retrieved reference blocks did not fit this response",12,muted,false));
                    if(!m.state.equals("completed"))turn.addView(label(m.state.equals("cancelled")?"Stopped":m.state.equals("interrupted")?"Interrupted · response incomplete":"Response incomplete",12,muted,false));
                }
                LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(14);body.addView(turn,p);
            }
            drawnRevision=c.revision;drawnCount=c.messages.size();drawnRunning=c.running();
        }else if(liveAnswer!=null&&c.running()){
            String current=c.messages.get(c.messages.size()-1).text;
            if(!current.equals(liveText)){liveAnswer.removeAllViews();AssistantMarkdown.render(this,liveAnswer,current,text,muted,panel);liveText=current;}
        }
        if(atBottom)transcript.post(()->transcript.fullScroll(View.FOCUS_DOWN));
    }
    private void submitSelection(AssistantConversation owner,AssistantConversation.Message message,String selection){
        if(session.conversation!=owner||!owner.messages.contains(message)||!message.state.equals("completed")||!idle())return;
        try{
            if(selection.length()>OnDeviceModelProfile.read(this).inputChars){notice("Selections exceed the current model input budget.");return;}
        }catch(Exception invalid){notice("The installed model configuration could not be read.");return;}
        session.send(this,selection);
    }
    private void notice(String value){status.setText(value);}
    private boolean idle(){if(session.busy()){notice("Finish or stop the active response or receipt check first.");return false;}return true;}
    private void newConversation(){if(!idle())return;session.save(this);session.conversation=new AssistantConversation();session.status="";render();}
    private void rename(){if(!idle())return;input("Conversation title",session.conversation.title,value->{session.conversation.title=value;session.save(this);render();});}
    private void changeProject(){if(!idle())return;input("Project context",session.conversation.project,value->{session.conversation.project=value;session.save(this);render();});}
    private interface Value{void accept(String value);}
    private void input(String title,String current,Value accept){
        EditText field=new EditText(this);field.setText(current);field.setSelectAllOnFocus(true);field.setMaxLines(6);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(title).setView(field).setNegativeButton("Cancel",null).setPositiveButton("Save",null).create();
        dialog.setOnShowListener(v->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(w->{String value=field.getText().toString().trim();if(value.isEmpty()||value.length()>12000){field.setError("Enter 1–12,000 characters");return;}accept.accept(value);dialog.dismiss();}));dialog.show();
    }
    private void edit(int index){if(!idle())return;input("Edit message",session.conversation.messages.get(index).text,value->{session.save(this);session.conversation=session.conversation.fork();session.conversation.editFrom(index,value);session.send(this,value);});}
    private void retry(){if(!idle())return;try{session.save(this);session.conversation=session.conversation.fork();session.send(this,session.conversation.retry());}catch(Exception failure){notice("This conversation has no response to regenerate.");}}
    private void history(){historyPage(0);}
    private void historyPage(int offset){
        if(!idle())return;notice("Opening encrypted history");
        AssistantConversation original=session.conversation;
        session.work.execute(()->{
            try{JSONArray list=ControlAssistantMemory.conversations(this,offset,51);runOnUiThread(()->{
                if(!alive||session.busy()||session.conversation!=original)return;
                int count=Math.min(50,list.length());
                java.util.ArrayList<String> titles=new java.util.ArrayList<>();
                if(offset>0)titles.add("Previous 50 conversations");
                int first=titles.size();
                for(int i=0;i<count;i++){JSONObject item=list.optJSONObject(i);titles.add(item.optString("title")+"\n"+item.optString("project"));}
                if(list.length()>count)titles.add("Next 50 conversations");
                new AlertDialog.Builder(this).setTitle("Conversations · "+(offset+1)+"–"+(offset+count))
                    .setItems(titles.toArray(new String[0]),(d,index)->{
                        if(first==1&&index==0){historyPage(Math.max(0,offset-50));return;}
                        if(index-first==count){historyPage(offset+50);return;}
                        session.work.execute(()->{
                            try{
                                AssistantConversation selected=ControlAssistantMemory.loadConversation(this,list.getJSONObject(index-first).getString("id"));
                                runOnUiThread(()->{if(!alive||session.busy()||session.conversation!=original)return;session.conversation=selected;session.status="";render();});
                            }catch(Exception failure){runOnUiThread(()->notice("This encrypted conversation could not be opened."));}
                        });
                    }).setNeutralButton("Delete current",(d,w)->deleteConversation()).setNegativeButton("Close",null).show();notice("");
            });}catch(Exception e){runOnUiThread(()->notice("Encrypted history could not be opened."));}
        });
    }
    private void deleteConversation(){if(!idle())return;AssistantConversation original=session.conversation;new AlertDialog.Builder(this).setTitle("Delete this conversation?").setMessage("Saved memories remain under Memory controls.").setNegativeButton("Cancel",null).setPositiveButton("Delete",(d,w)->{if(!idle()||session.conversation!=original)return;ControlAssistantMemory.deleteConversation(this,session.conversation.id);session.conversation=new AssistantConversation();session.status="";render();}).show();}
    private void modelSettings(){
        String[] modes={"Fast","Balanced","Deep","Memory and assistant settings","Installed model details","Import signed model files"};
        new AlertDialog.Builder(this).setTitle("Model and reasoning").setItems(modes,(d,index)->{
            if(index<3){ControlAssistantPreferences.save(this,new String[]{"fast","balanced","deep"}[index],ControlAssistantPreferences.guidance(this));render();}
            else if(index==3){startActivity(new Intent(this,MainActivity.class).putExtra("assistant_settings",true));}
            else if(index==5){chooseModelArtifact();}
            else session.work.execute(()->{try{JSONObject p=OnDeviceLlm.status(this);runOnUiThread(()->new AlertDialog.Builder(this).setTitle("Installed model").setMessage(p.optString("model_name")+"\n"+(p.optBoolean("model_loaded")?"Loaded":"Not loaded")+"\nContext: "+p.optInt("model_context_tokens")+" tokens\n"+p.optString("model_source")).setPositiveButton("Close",null).show());}catch(Exception e){runOnUiThread(()->notice("Model details unavailable."));}});
        }).setNegativeButton("Close",null).show();
    }
    private void chooseModelArtifact(){
        if(!idle())return;
        try{
            OnDeviceModelProfile profile=OnDeviceModelProfile.read(this);
            if(!profile.externalModelPack){notice("This signed release uses a bundled model; no separate model import is required.");return;}
            String[] options=profile.adapterFile.isEmpty()?new String[]{"Base · "+profile.file}:
                new String[]{"Base · "+profile.file,"Adapter · "+profile.adapterFile};
            new AlertDialog.Builder(this).setTitle("Install signed model pack")
                .setItems(options,(dialog,index)->{
                    if(!idle())return;
                    Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
                    picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);
                    try{startActivityForResult(picker,index==0?215:216);}
                    catch(Exception unavailable){notice("Model document picker unavailable.");}
                }).setNegativeButton("Cancel",null).show();
        }catch(Exception invalid){notice("Signed model profile unavailable.");}
    }
    private void voice(){try{Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"en-US");startActivityForResult(intent,210);}catch(Exception unavailable){notice("Speech recognition is unavailable. Check Android speech services.");}}
    private void exportArtifact(AssistantArtifact artifact){
        if(!idle())return;
        if(session.pendingArtifact!=null){notice("Finish the current file picker first.");return;}
        session.pendingArtifact=artifact;
        try{
            Intent intent=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(artifact.mime).addCategory(Intent.CATEGORY_OPENABLE);
            intent.putExtra(Intent.EXTRA_TITLE,artifact.filename);
            startActivityForResult(intent,212);
        }catch(Exception unavailable){session.pendingArtifact=null;notice("No document provider is available for this file.");}
    }
    private void attach(){
        if(!idle())return;
        new AlertDialog.Builder(this).setTitle("Attach or manage project sources")
            .setItems(new String[]{"Attach small text to next message","Import searchable project text (up to 2 MiB)","Manage imported project sources","Import PDF text by page range"},(dialog,which)->{
                if(!idle())return;
                if(which==2){showProjectSources(session.conversation.project);return;}
                if(which==3){
                    if(android.os.Build.VERSION.SDK_INT<35){notice("PDF text extraction requires Android 15 or newer.");return;}
                    pendingSourceProject=session.conversation.project;
                    try{startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("application/pdf")
                        .addCategory(Intent.CATEGORY_OPENABLE),214);}
                    catch(Exception unavailable){pendingSourceProject=null;notice("PDF picker unavailable.");}
                    return;
                }
                Intent picker=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
                picker.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"text/*","application/json","application/xml"});
                if(which==1)pendingSourceProject=session.conversation.project;
                try{startActivityForResult(picker,which==0?211:213);}
                catch(Exception unavailable){pendingSourceProject=null;notice("Document picker unavailable.");}
            }).setNegativeButton("Cancel",null).show();
    }
    private void showProjectSources(String scope){
        session.work.execute(()->{
            try{
                JSONArray sources=ControlAssistantMemory.projectSources(this,scope);
                runOnUiThread(()->{
                    if(!alive||!scope.equals(session.conversation.project))return;
                    String[] labels=new String[sources.length()];
                    for(int i=0;i<labels.length;i++){
                        JSONObject row=sources.optJSONObject(i);
                        labels[i]=row.optString("name")+" · "+row.optLong("bytes")+" bytes";
                    }
                    if(labels.length==0){new AlertDialog.Builder(this).setTitle("Project sources").setMessage("No imported text in this project.").setPositiveButton("Close",null).show();return;}
                    new AlertDialog.Builder(this).setTitle("Project sources · "+scope).setItems(labels,(d,index)->{
                        JSONObject selected=sources.optJSONObject(index);
                        new AlertDialog.Builder(this).setTitle(selected.optString("name"))
                            .setMessage("SHA-256: "+selected.optString("sha256")+"\nSource characters: "+selected.optLong("chars")+
                                "\nDelete the imported copy and all searchable passages? The original file is not changed.")
                            .setPositiveButton("Delete imported source",(x,y)->session.work.execute(()->{
                                try{
                                    boolean removed=ControlAssistantMemory.deleteProjectSource(this,scope,selected.optString("id"));
                                    runOnUiThread(()->{if(alive){notice(removed?"Imported copy deleted.":"Source not found.");showProjectSources(scope);}});
                                }catch(Exception failure){runOnUiThread(()->{if(alive)notice("Source deletion not confirmed.");});}
                            })).setNegativeButton("Keep",null).show();
                    }).setNegativeButton("Close",null).show();
                });
            }catch(Exception failure){runOnUiThread(()->{if(alive)notice("Encrypted sources unavailable.");});}
        });
    }
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);
        if(request==215||request==216){
            if(result!=RESULT_OK||data==null||!idle())return;
            java.util.ArrayList<android.net.Uri> documents=new java.util.ArrayList<>();
            ClipData clips=data.getClipData();
            if(clips!=null){
                if(clips.getItemCount()>32){notice("Select at most 32 model parts.");return;}
                for(int i=0;i<clips.getItemCount();i++)documents.add(clips.getItemAt(i).getUri());
            }else if(data.getData()!=null)documents.add(data.getData());
            if(documents.isEmpty())return;
            boolean adapter=request==216;
            new AlertDialog.Builder(this).setTitle(adapter?"Import verified adapter":"Import verified base model")
                .setMessage("Import "+documents.size()+" selected document(s) and verify the assembled bytes against the signed profile? The originals are not changed.")
                .setPositiveButton("Import",(d,w)->{if(idle())session.importModel(this,documents,adapter);})
                .setNegativeButton("Cancel",null).show();
            return;
        }
        if(request==212){
            AssistantArtifact artifact=session.pendingArtifact;session.pendingArtifact=null;
            if(result!=RESULT_OK||data==null||data.getData()==null)return;
            if(artifact==null){notice("Export context was lost before writing. No file write was attempted.");return;}
            android.net.Uri uri=data.getData();
            android.content.Context app=getApplicationContext();
            notice("Writing and verifying selected file");
            session.work.execute(()->{
                String outcome;
                try{
                    try(java.io.OutputStream out=app.getContentResolver().openOutputStream(uri,"w")){
                        if(out==null)throw new java.io.IOException("no_output_stream");
                        out.write(artifact.data());out.flush();
                    }
                    try(java.io.InputStream in=app.getContentResolver().openInputStream(uri)){
                        if(in==null||!artifact.verified(in.readNBytes(artifact.size()+1)))throw new java.io.IOException("readback_mismatch");
                    }
                    outcome="File saved and read-back verified ("+artifact.size()+" bytes).";
                }catch(Exception failure){outcome="Export outcome unverified. A partial file may exist at the selected destination.";}
                String report=outcome;runOnUiThread(()->{if(alive)notice(report);});
            });return;
        }
        if(request==214){
            String scope=pendingSourceProject;pendingSourceProject=null;
            if(result!=RESULT_OK||data==null||data.getData()==null||!idle())return;
            if(scope==null||!scope.equals(session.conversation.project)){notice("Project changed; PDF not imported.");return;}
            android.net.Uri uri=data.getData();
            LinearLayout fields=DesignSystem.vertical(this);fields.setPadding(dp(20),dp(8),dp(20),dp(8));
            fields.addView(label("Extract searchable text only. Maximum 50 selected pages, 64 MiB input. Scans and diagrams are not analyzed.",14,muted,false));
            EditText first=new EditText(this),last=new EditText(this);
            first.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);last.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
            first.setHint("First page");last.setHint("Last page");first.setText("1");last.setText("20");
            fields.addView(first);fields.addView(last);
            new AlertDialog.Builder(this).setTitle("Import PDF text into "+scope).setView(fields)
                .setPositiveButton("Extract and save",(d,w)->{
                    if(!idle()||!scope.equals(session.conversation.project))return;
                    try{
                        int a=Integer.parseInt(first.getText().toString()),z=Integer.parseInt(last.getText().toString());
                        if(a<1||z<a||z-a>=AssistantPdfExtractionService.MAX_PAGES||z>100000)
                            throw new IllegalArgumentException("page_range");
                        session.importPdf(this,uri,scope,a,z);
                    }catch(IllegalArgumentException invalid){notice("Choose a valid range of 1–50 pages.");}
                }).setNegativeButton("Cancel",null).show();
            return;
        }
        if(request==213){
            String scope=pendingSourceProject;pendingSourceProject=null;
            if(result!=RESULT_OK||data==null||data.getData()==null)return;
            if(scope==null||!scope.equals(session.conversation.project)){notice("Project changed; no source imported.");return;}
            android.net.Uri uri=data.getData();
            if(!"content".equals(uri.getScheme())){notice("Document provider required.");return;}
            new AlertDialog.Builder(this).setTitle("Import searchable project text")
                .setMessage("Store a private encrypted copy in "+scope+"? Only UTF-8 text up to 2 MiB is accepted. It is retrieved in local chat as reference data, not executed or uploaded.")
                .setPositiveButton("Import",(d,w)->{
                    if(!idle()||!scope.equals(session.conversation.project))return;
                    notice("Importing encrypted project source");
                    session.work.execute(()->{
                        try{
                            String name="Imported text";
                            try(Cursor cursor=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
                                if(cursor!=null&&cursor.moveToFirst())name=cursor.getString(0);
                            }
                            byte[] bytes;
                            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){
                                if(in==null)throw new java.io.IOException("no_source_stream");
                                bytes=in.readNBytes(ProjectSourceText.MAX_BYTES+1);
                            }
                            ProjectSourceText source;
                            try{source=new ProjectSourceText(name,bytes);}
                            finally{java.util.Arrays.fill(bytes,(byte)0);}
                            ControlAssistantMemory.importProjectSource(this,scope,source);
                            runOnUiThread(()->{if(alive)notice("Encrypted source available in "+scope+".");});
                        }catch(Exception failure){runOnUiThread(()->{if(alive)notice("Source not imported. Check UTF-8 encoding, size and local storage.");});}
                    });
                }).setNegativeButton("Cancel",null).show();
            return;
        }
        if(result!=RESULT_OK||data==null)return;
        if(request==210){java.util.ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())composer.append(words.get(0));}
        else if(request==211&&data.getData()!=null){android.net.Uri uri=data.getData();session.work.execute(()->{
            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){
                if(in==null)throw new java.io.IOException();byte[] bytes=in.readNBytes(16001);if(bytes.length>16000)throw new java.io.IOException();
                String attachment=new String(bytes,StandardCharsets.UTF_8);runOnUiThread(()->{if(alive)composer.append("\n\nAttached text:\n"+attachment);});
            }catch(Exception failure){runOnUiThread(()->notice("Choose a readable text file up to 16 KB."));}
        });}
    }
    private void reviewResearch(AssistantConversation owner,AssistantConversation.Message message,String query){
        if(!idle()||session.conversation!=owner||!owner.messages.contains(message))return;
        new AlertDialog.Builder(this).setTitle("Review external web search")
            .setMessage("Send only these search terms to the Browser's configured provider?\n\n"+query+
                "\n\nPin relevant pages to the encrypted research board to use captured evidence. No search has run yet.")
            .setNegativeButton("Cancel",null).setPositiveButton("Search",(d,w)->{
                if(!idle()||session.conversation!=owner||!owner.messages.contains(message))return;
                startActivity(new Intent(this,BrowserActivity.class).addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT)
                    .putExtra("assistant_search_query",query));
            }).show();
    }
    private void interpretReceipt(AssistantConversation owner,AssistantConversation.Message message){
        if(!idle()||session.conversation!=owner||message.actionRecord==null)return;
        String id=message.actionRecord.requestId;
        // A new local inference turn interprets existing evidence only. No
        // new app action, re-dispatch or automatic permission is granted.
        session.send(this,"Interpret the recorded signed partner receipt "+id+
            ". State the actual observed values, limitations and next useful step. "+
            "Treat provider status as a reported observation, not independent proof; do not invoke another action.");
    }
    private void reviewAction(AssistantConversation owner,AssistantConversation.Message message,JSONObject proposal){
        if(!idle()||session.conversation!=owner||message.actionRecord!=null)return;
        new AlertDialog.Builder(this).setTitle("Review application action").setMessage(proposal.optString("package")+"\n"+proposal.optString("action")+"\n\n"+proposal.optJSONObject("payload").toString())
            .setNegativeButton("Cancel",null).setPositiveButton("Authorize once",(d,w)->{
                try{session.authorize(this,owner,message,proposal);}
                catch(IllegalArgumentException invalid){notice("Invalid application action proposal; not submitted.");}
            }).show();
    }
}
