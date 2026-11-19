package com.asterion.control;

import android.app.assist.AssistStructure;
import android.content.ComponentName;
import android.os.CancellationSignal;
import android.service.autofill.AutofillService;
import android.service.autofill.Dataset;
import android.service.autofill.FillCallback;
import android.service.autofill.FillRequest;
import android.service.autofill.FillResponse;
import android.service.autofill.SaveCallback;
import android.service.autofill.SaveRequest;
import android.service.autofill.SaveInfo;
import android.text.InputType;
import android.view.autofill.AutofillId;
import android.view.autofill.AutofillValue;
import android.widget.RemoteViews;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Android system-approved Autofill service backed by the one Control Keystore
 * vault. For now, ONLY Asterion's own BrowserActivity can receive passwords:
 * native app/package to arbitrary website domain association is NOT trustworthy
 * without externally verified Digital Asset Links. Never fill iframes with a
 * second origin, non-HTTPS sites, unknown fields or unapproved callers.
 */
public final class ControlAutofillService extends AutofillService {
    private static final class Form {
        AutofillId username, password;
        String usernameValue="",passwordValue="";
        final Set<String> domains=new HashSet<>();
        String origin="";
        void observe(AssistStructure.ViewNode view,String inherited){
            String raw=view.getWebDomain();
            String domain=(raw==null||raw.isBlank())?inherited:raw.toLowerCase(Locale.ROOT);
            if(domain!=null&&!domain.isEmpty())domains.add(domain);
            AutofillId id=view.getAutofillId();
            String[] hints=view.getAutofillHints();
            boolean user=false,pass=false;
            if(hints!=null)for(String hint:hints){
                if(hint==null)continue;
                String lower=hint.toLowerCase(Locale.ROOT);
                if(lower.equals("username")||lower.equals("emailaddress")||
                    lower.equals("email"))user=true;
                if(lower.equals("password")||lower.equals("newpassword")||
                    lower.equals("currentpassword"))pass=true;
            }
            int type=view.getInputType()&InputType.TYPE_MASK_VARIATION;
            if(type==InputType.TYPE_TEXT_VARIATION_PASSWORD||
                type==InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD)
                pass=true;
            if(id!=null&&domain!=null&&!domain.isBlank()){
                if(pass&&!user&&password==null){
                    password=id;
                    AutofillValue value=view.getAutofillValue();
                    if(value!=null&&value.isText())passwordValue=value.getTextValue().toString();
                }else if(user&&!pass&&username==null){
                    username=id;
                    AutofillValue value=view.getAutofillValue();
                    if(value!=null&&value.isText())usernameValue=value.getTextValue().toString();
                }
            }
            for(int i=0;i<view.getChildCount();i++)
                observe(view.getChildAt(i),domain);
        }
        boolean valid(){
            if(username==null||password==null||domains.size()!=1)return false;
            String domain=domains.iterator().next();
            try{
                origin=ControlPasswordVault.exactOrigin("https://"+domain);
                return true;
            }catch(Exception failure){return false;}
        }
    }
    private Form parse(AssistStructure structure){
        ComponentName source=structure.getActivityComponent();
        if(source==null||
           !getPackageName().equals(source.getPackageName())||
           !BrowserActivity.class.getName().equals(source.getClassName()))
            return null;
        Form form=new Form();
        for(int i=0;i<structure.getWindowNodeCount();i++)
            form.observe(structure.getWindowNodeAt(i).getRootViewNode(),null);
        return form.valid()?form:null;
    }
    private Form latest(List<android.service.autofill.FillContext> contexts){
        if(contexts==null||contexts.isEmpty())return null;
        return parse(contexts.get(contexts.size()-1).getStructure());
    }
    @Override public void onFillRequest(FillRequest request,
            CancellationSignal signal,FillCallback callback){
        try{
            if(signal!=null&&signal.isCanceled()){callback.onSuccess(null);return;}
            Form form=latest(request.getFillContexts());
            if(form==null){callback.onSuccess(null);return;}
            FillResponse.Builder response=new FillResponse.Builder()
                .setSaveInfo(new SaveInfo.Builder(
                    SaveInfo.SAVE_DATA_TYPE_USERNAME|SaveInfo.SAVE_DATA_TYPE_PASSWORD,
                    new AutofillId[]{form.username,form.password}).build());
            List<ControlPasswordVault.Entry> entries=
                ControlPasswordVault.accounts(this,form.origin);
            for(ControlPasswordVault.Entry entry:entries){
                if(signal!=null&&signal.isCanceled()){callback.onSuccess(null);return;}
                RemoteViews presentation=new RemoteViews(getPackageName(),
                    android.R.layout.simple_list_item_1);
                presentation.setTextViewText(android.R.id.text1,
                    "Asterion Vault · "+entry.username);
                Dataset row=new Dataset.Builder(presentation)
                    .setValue(form.username,AutofillValue.forText(entry.username))
                    .setValue(form.password,AutofillValue.forText(entry.password))
                    .build();
                response.addDataset(row);
            }
            callback.onSuccess(response.build());
        }catch(Exception error){
            // Never print credentials, URLs or other app-private data.
            callback.onSuccess(null);
        }
    }
    @Override public void onSaveRequest(SaveRequest request,SaveCallback callback){
        try{
            Form form=latest(request.getFillContexts());
            if(form==null||form.usernameValue.isBlank()||
                form.passwordValue.isBlank()){
                callback.onFailure("No valid Asterion Browser HTTPS form to save");
                return;
            }
            // The Android OS Save UI is the user's explicit authorization.
            ControlPasswordVault.save(this,form.origin,
                form.usernameValue,form.passwordValue);
            callback.onSuccess();
        }catch(Exception ignored){
            callback.onFailure("Asterion Vault could not save this login");
        }
    }
}
