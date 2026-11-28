package com.asterion.control;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.widget.EditText;
import java.util.Locale;

/** Shared language selection; does not install packs, start a microphone or change voice route. */
final class VoiceLanguageSettings {
    private static final String KEY="owner_voice_locale";
    private static final String[] TAGS={"en-US","en-GB","fr-FR","ja-JP","de-DE","es-ES","it-IT","pt-BR","ko-KR","zh-CN"};
    private VoiceLanguageSettings(){}
    static String locale(Context c){
        try{return VoiceReplyPolicy.canonicalLocale(c.getSharedPreferences("voice_style",Context.MODE_PRIVATE).getString(KEY,"en-US"));}
        catch(IllegalArgumentException invalid){return "en-US";}
    }
    static void save(Context c,String tag){
        String value=VoiceReplyPolicy.canonicalLocale(tag);
        if(VoiceDialogueService.active!=null)throw new IllegalStateException("Stop the voice session before changing its language.");
        if(!c.getSharedPreferences("voice_style",Context.MODE_PRIVATE).edit().putString(KEY,value).commit())
            throw new IllegalStateException("Voice language could not be saved.");
    }
    static String display(String tag){
        Locale l=Locale.forLanguageTag(tag);
        return l.getDisplayName(l)+" ("+tag+")";
    }
    static void show(Activity owner,Runnable changed){
        if(VoiceDialogueService.active!=null){
            new AlertDialog.Builder(owner).setTitle("Voice language").setMessage("Stop the active voice session before changing its language.")
                .setPositiveButton("Close",null).show();return;
        }
        String selected=locale(owner);String[] labels=new String[TAGS.length+1];int checked=TAGS.length;
        for(int i=0;i<TAGS.length;i++){labels[i]=display(TAGS[i]);if(TAGS[i].equals(selected))checked=i;}
        labels[TAGS.length]="Other language tag";
        new AlertDialog.Builder(owner).setTitle("Voice language · "+display(selected))
            .setSingleChoiceItems(labels,checked,(d,i)->{
                d.dismiss();
                if(i<TAGS.length){commit(owner,TAGS[i],changed);return;}
                EditText tag=new EditText(owner);tag.setSingleLine(true);tag.setText(selected);
                new AlertDialog.Builder(owner).setTitle("Language tag, e.g. nl-NL").setView(tag)
                    .setPositiveButton("Save",(x,y)->commit(owner,tag.getText().toString().strip(),changed))
                    .setNegativeButton("Cancel",null).show();
            }).setNegativeButton("Cancel",null)
            .setMessage(null).show();
    }
    private static void commit(Activity owner,String tag,Runnable changed){
        try{
            save(owner,tag);changed.run();
            new AlertDialog.Builder(owner).setTitle("Voice language saved")
                .setMessage("Recognition and playback require Android language support. Install the relevant offline speech packs when needed. The existing Android system recognizer may use network speech when an offline pack is unavailable.")
                .setPositiveButton("Close",null).show();
        }catch(Exception invalid){
            new AlertDialog.Builder(owner).setTitle("Language not changed").setMessage(invalid.getMessage()).setPositiveButton("Close",null).show();
        }
    }
}
