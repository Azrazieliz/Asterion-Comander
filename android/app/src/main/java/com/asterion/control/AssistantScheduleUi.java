package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Spinner;
import android.widget.ArrayAdapter;
import android.text.InputType;
import org.json.JSONArray;
import org.json.JSONObject;
import java.text.DateFormat;
import java.util.Date;
import java.util.function.Consumer;

/** Owner-local scheduling UI. No automatic action is approved by generated text. */
final class AssistantScheduleUi {
    private static void notice(Activity a,String msg){new AlertDialog.Builder(a).setMessage(msg).setPositiveButton("Close",null).show();}
    private static String date(long at){return at>0?DateFormat.getDateTimeInstance().format(new Date(at)):"None";}
    static void show(Activity a){
        if(a.isFinishing())return;
        try{
            JSONArray list=AssistantSchedules.list(a);
            String[] labels=new String[list.length()+1];labels[0]="Create local scheduled task";
            for(int i=0;i<list.length();i++){
                JSONObject r=list.getJSONObject(i);
                labels[i+1]=r.getString("title")+" · "+(r.optBoolean("enabled")?"Enabled":"No next execution")+
                    "\nNext: "+date(r.getLong("next_ms"))+" · Last: "+r.optString("last_state");
            }
            new AlertDialog.Builder(a).setTitle("Scheduled tasks")
                .setMessage(AgentService.running?"Existing Control service is active. Tasks run when the device permits; overdue intervals are not replayed.":"Control service is stopped. Tasks remain saved but do not execute until you enable it.")
                .setItems(labels,(d,which)->{
                    if(which==0)create(a);
                    else try{detail(a,list.getJSONObject(which-1));}catch(Exception failure){notice(a,"Task unavailable.");}
                }).setNegativeButton("Close",null).show();
        }catch(Exception failure){notice(a,"Encrypted scheduled tasks unavailable.");}
    }
    private static EditText field(Activity a,LinearLayout form,String hint,String value,boolean numeric){
        EditText e=new EditText(a);e.setHint(hint);e.setText(value);e.setSaveEnabled(false);
        e.setImportantForAutofill(android.view.View.IMPORTANT_FOR_AUTOFILL_NO);
        if(numeric)e.setInputType(InputType.TYPE_CLASS_NUMBER);
        form.addView(e);return e;
    }
    private static void create(Activity a){
        LinearLayout form=new LinearLayout(a);form.setOrientation(LinearLayout.VERTICAL);
        form.setPadding(DesignSystem.dp(a,20),0,DesignSystem.dp(a,20),0);
        Spinner mode=new Spinner(a);
        mode.setAdapter(new ArrayAdapter<>(a,android.R.layout.simple_spinner_dropdown_item,new String[]{"Reminder","Offline AI answer"}));
        form.addView(mode);
        EditText title=field(a,form,"Title","",false),prompt=field(a,form,"Reminder text or AI instructions","",false);
        EditText delay=field(a,form,"Delay in minutes","15",true),interval=field(a,form,"Repeat minutes (0 = once)","0",true);
        new AlertDialog.Builder(a).setTitle("Create scheduled task").setView(form)
            .setPositiveButton("Review",(d,w)->{
                try{
                    AssistantSchedulePlan p=new AssistantSchedulePlan(mode.getSelectedItemPosition()==0?"reminder":"inference",
                        title.getText().toString(),Integer.parseInt(delay.getText().toString()),
                        Integer.parseInt(interval.getText().toString()),prompt.getText().toString());
                    review(a,p,null,ignored->show(a));
                }catch(Exception invalid){notice(a,"Invalid task. Enter a title and instructions; delay 1–525600 minutes, recurrence 0 or 15–525600.");}
            }).setNegativeButton("Cancel",null).show();
    }
    static void review(Activity a,AssistantSchedulePlan p,String id,Consumer<String> created){
        new AlertDialog.Builder(a).setTitle("Authorize local schedule")
            .setMessage(p.title+"\nType: "+p.kind+"\nFirst execution: "+p.delayMinutes+" minutes after approval"+
                "\nRepeat: "+(p.intervalMinutes==0?"Once":p.intervalMinutes+" minutes")+"\n\n"+p.prompt+
                "\n\nInstructions and latest result are encrypted on this phone. No external actions are authorized. "+
                (AgentService.running?"Control service is active.":"Control service is stopped; enable it before execution."))
            .setPositiveButton("Save schedule",(d,w)->{
                try{String saved=AssistantSchedules.create(a,p,id);created.accept(saved);}
                catch(Exception failure){notice(a,"Schedule was not saved: "+failure.getClass().getSimpleName());}
            }).setNegativeButton("Cancel",null).show();
    }
    private static void detail(Activity a,JSONObject r)throws Exception{
        String id=r.getString("id");
        boolean active=AssistantSchedules.active(r),enabled=r.optBoolean("enabled");
        String result=r.optString("last_result","");
        String summary="Type: "+r.getString("kind")+"\nNext: "+date(r.getLong("next_ms"))+
            "\nInterval: "+r.getInt("interval_minutes")+" minutes (0 = once)"+
            "\nLast state: "+r.optString("last_state")+"\nLast finished: "+date(r.optLong("last_finished_ms"))+
            "\nNotification: "+r.optString("notification","not attempted")+"\n\nInstructions:\n"+r.getString("prompt")+
            (result.isEmpty()?"":"\n\nLatest result:\n"+result);
        String[] options=active?new String[]{"Pause future runs","Cancel current inference","Close"}:
            new String[]{enabled?"Pause":"Resume","Delete task","Close"};
        new AlertDialog.Builder(a).setTitle(r.getString("title")).setMessage(summary)
            .setItems(options,(d,which)->{
                try{
                    if(which==0)AssistantSchedules.pause(a,id,!active&&!enabled);
                    else if(which==1){
                        if(active)AssistantSchedules.cancel(a,id);
                        else {new AlertDialog.Builder(a).setTitle("Delete this schedule and retained result?")
                            .setPositiveButton("Delete",(x,y)->{try{AssistantSchedules.delete(a,id);show(a);}catch(Exception failure){notice(a,"Unable to delete.");}})
                            .setNegativeButton("Cancel",null).show();return;}
                    }
                    show(a);
                }catch(Exception failure){notice(a,failure.getMessage()==null?"Task change unavailable.":failure.getMessage());}
            }).setNegativeButton("Back",(d,w)->show(a)).show();
    }
}
