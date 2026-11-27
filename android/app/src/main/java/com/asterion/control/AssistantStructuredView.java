package com.asterion.control;

import android.content.Context;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import java.util.ArrayList;
import java.util.Collections;
import java.util.function.Consumer;

/** Native-only widgets. User answers become a normal conversation message, never a tool call. */
final class AssistantStructuredView {
    private static int dp(Context c,int v){return DesignSystem.dp(c,v);}
    static View render(Context c,AssistantStructured data,int text,int muted,int panel,Consumer<String> send){
        LinearLayout box=DesignSystem.vertical(c);
        box.setPadding(dp(c,14),dp(c,12),dp(c,14),dp(c,12));
        box.setBackground(DesignSystem.shape(c,panel,0,14));
        box.addView(DesignSystem.text(c,data.title,17,text,true));
        if(data.type.equals(AssistantStructured.CHART)){
            for(int i=0;i<data.rows.size();i++){
                AssistantStructured.Row row=data.rows.get(i);
                TextView caption=DesignSystem.text(c,row.label+"  ·  "+row.display,14,text,false);
                caption.setPadding(0,dp(c,10),0,dp(c,4));box.addView(caption);
                LinearLayout track=DesignSystem.horizontal(c);
                track.setBackground(DesignSystem.shape(c,muted,0,6));
                track.setAlpha(.85f);
                float fraction=(float)data.fraction(i);
                if(fraction>0){
                    View bar=new View(c);bar.setBackground(DesignSystem.shape(c,0xFF7763D4,0,6));
                    track.addView(bar,new LinearLayout.LayoutParams(0,-1,fraction));
                }
                if(fraction<1)track.addView(new View(c),new LinearLayout.LayoutParams(0,-1,1-fraction));
                track.setContentDescription(row.label+": "+row.display);
                box.addView(track,new LinearLayout.LayoutParams(-1,dp(c,12)));
            }
        }else{
            ArrayList<Integer> choices=new ArrayList<>(Collections.nCopies(data.rows.size(),-1));
            TextView submit=DesignSystem.text(c,"Send selections",15,text,true);
            TextView state=DesignSystem.text(c,"Choose an answer for each question.",12,muted,false);
            for(int i=0;i<data.rows.size();i++){
                final int index=i;
                AssistantStructured.Row row=data.rows.get(i);
                TextView question=DesignSystem.text(c,row.label,15,text,true);
                question.setPadding(0,dp(c,14),0,dp(c,4));box.addView(question);
                RadioGroup group=new RadioGroup(c);group.setOrientation(RadioGroup.VERTICAL);
                for(String option:row.options){
                    RadioButton button=new RadioButton(c);button.setId(View.generateViewId());
                    button.setText(option);button.setTextColor(text);button.setMinHeight(dp(c,48));group.addView(button);
                }
                group.setOnCheckedChangeListener((g,id)->{
                    int selected=-1;for(int j=0;j<g.getChildCount();j++)if(g.getChildAt(j).getId()==id)selected=j;
                    choices.set(index,selected);
                    state.setText(choices.contains(-1)?"Choose an answer for each question.":"Ready to send as a message.");
                    submit.setEnabled(!choices.contains(-1));
                    submit.setAlpha(submit.isEnabled()?1f:.5f);
                });
                box.addView(group);
            }
            box.addView(state);
            submit.setMinHeight(dp(c,48));submit.setGravity(Gravity.CENTER);
            DesignSystem.clickable(submit,c,panel,muted,12);
            submit.setEnabled(false);submit.setAlpha(.5f);
            submit.setOnClickListener(v->{if(send!=null&&!choices.contains(-1))send.accept(data.submission(choices));});
            box.addView(submit);
        }
        return box;
    }
}
