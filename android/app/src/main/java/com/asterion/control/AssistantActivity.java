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
        send=control("Send",()->{if(session.conversation.running())session.cancel();else submit();});send.setTextColor(accent);actions.addView(send);box.addView(actions);root.addView(box);
        if(state!=null){draft=state.getString("draft","");composer.setText(draft);}
        speech=new TextToSpeech(this,result->{speechReady=result==TextToSpeech.SUCCESS;});
        session.listeners.add(observer);render();
        String previous=getSharedPreferences("control",MODE_PRIVATE).getString("assistant_last_conversation","");
        if(session.conversation.messages.isEmpty()&&!previous.isEmpty()&&ControlAssistantPreferences.saveHistory(this)){
            final String emptyId=session.conversation.id;
            session.work.execute(()->{try{AssistantConversation saved=ControlAssistantMemory.loadConversation(this,previous);
                runOnUiThread(()->{if(alive&&session.conversation.id.equals(emptyId)&&session.conversation.messages.isEmpty()){session.conversation=saved;render();}});
            }catch(Exception ignored){}});
        }
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
        send.setText(c.running()?"Stop":"Send");
        send.setEnabled(!session.busy()||c.running());
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
                    AssistantMarkdown.render(this,answer,m.text,text,muted,panel,selection->submitSelection(c,m,selection));
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
                        }else try{JSONObject proposal=m.state.equals("completed")?AssistantCapabilities.proposal(m.text):null;if(proposal!=null)tools.addView(control("Review action",()->reviewAction(c,m,proposal)));}catch(Exception ignored){}
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
    private void history(){
        if(!idle())return;notice("Opening encrypted history");
        AssistantConversation original=session.conversation;
        session.work.execute(()->{
            try{JSONArray list=ControlAssistantMemory.conversations(this);runOnUiThread(()->{
                if(!alive||session.busy()||session.conversation!=original)return;String[] titles=new String[list.length()];for(int i=0;i<list.length();i++){JSONObject item=list.optJSONObject(i);titles[i]=item.optString("title")+"\n"+item.optString("project");}
                new AlertDialog.Builder(this).setTitle("Conversations").setItems(titles,(d,index)->{
                    session.work.execute(()->{try{AssistantConversation selected=ControlAssistantMemory.loadConversation(this,list.getJSONObject(index).getString("id"));runOnUiThread(()->{if(!alive||session.busy()||session.conversation!=original)return;session.conversation=selected;session.status="";render();});}catch(Exception failure){runOnUiThread(()->notice("This encrypted conversation could not be opened."));}});
                }).setNeutralButton("Delete current",(d,w)->deleteConversation()).setNegativeButton("Close",null).show();notice("");
            });}catch(Exception e){runOnUiThread(()->notice("Encrypted history could not be opened."));}
        });
    }
    private void deleteConversation(){if(!idle())return;AssistantConversation original=session.conversation;new AlertDialog.Builder(this).setTitle("Delete this conversation?").setMessage("Saved memories remain under Memory controls.").setNegativeButton("Cancel",null).setPositiveButton("Delete",(d,w)->{if(!idle()||session.conversation!=original)return;ControlAssistantMemory.deleteConversation(this,session.conversation.id);session.conversation=new AssistantConversation();session.status="";render();}).show();}
    private void modelSettings(){
        String[] modes={"Fast","Balanced","Deep","Memory and assistant settings","Installed model details"};
        new AlertDialog.Builder(this).setTitle("Model and reasoning").setItems(modes,(d,index)->{
            if(index<3){ControlAssistantPreferences.save(this,new String[]{"fast","balanced","deep"}[index],ControlAssistantPreferences.guidance(this));render();}
            else if(index==3){startActivity(new Intent(this,MainActivity.class).putExtra("assistant_settings",true));}
            else session.work.execute(()->{try{JSONObject p=OnDeviceLlm.status(this);runOnUiThread(()->new AlertDialog.Builder(this).setTitle("Installed model").setMessage(p.optString("model_name")+"\n"+(p.optBoolean("model_loaded")?"Loaded":"Not loaded")+"\nContext: "+p.optInt("model_context_tokens")+" tokens\n"+p.optString("model_source")).setPositiveButton("Close",null).show());}catch(Exception e){runOnUiThread(()->notice("Model details unavailable."));}});
        }).setNegativeButton("Close",null).show();
    }
    private void voice(){try{Intent intent=new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE,"en-US");startActivityForResult(intent,210);}catch(Exception unavailable){notice("Speech recognition is unavailable. Check Android speech services.");}}
    private void attach(){Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("text/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(intent,211);}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null)return;
        if(request==210){java.util.ArrayList<String> words=data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);if(words!=null&&!words.isEmpty())composer.append(words.get(0));}
        else if(request==211&&data.getData()!=null){android.net.Uri uri=data.getData();session.work.execute(()->{
            try(java.io.InputStream in=getContentResolver().openInputStream(uri)){
                if(in==null)throw new java.io.IOException();byte[] bytes=in.readNBytes(16001);if(bytes.length>16000)throw new java.io.IOException();
                String attachment=new String(bytes,StandardCharsets.UTF_8);runOnUiThread(()->{if(alive)composer.append("\n\nAttached text:\n"+attachment);});
            }catch(Exception failure){runOnUiThread(()->notice("Choose a readable text file up to 16 KB."));}
        });}
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
