package com.asterion.control;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Message;
import android.os.Messenger;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/** Owner-selected PDF -> temporary bounded source -> isolated page extraction
 * -> existing encrypted exact-text store. The PDF itself is never persisted. */
final class AssistantPdfImport {
    private AssistantPdfImport(){}
    static ProjectSourceText extract(Context context,Uri uri,int first,int last)throws Exception{
        if(Looper.myLooper()==Looper.getMainLooper())throw new IllegalStateException("pdf_worker_required");
        if(uri==null||!"content".equals(uri.getScheme())||first<1||last<first||
            last-first>=AssistantPdfExtractionService.MAX_PAGES||last>100000)
            throw new IllegalArgumentException("invalid_pdf_range_or_size");
        String name="Selected PDF";
        try(android.database.Cursor cursor=context.getContentResolver().query(uri,
            new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){
            if(cursor!=null&&cursor.moveToFirst()&&cursor.getString(0)!=null)name=cursor.getString(0);
        }
        name=name.replaceAll("[\\p{Cntrl}]"," ").strip();
        if(name.isEmpty())name="Selected PDF";
        if(name.length()>100)name=name.substring(0,100);
        File temp=File.createTempFile("assistant-pdf-",".tmp",context.getCacheDir());
        try(ParcelFileDescriptor file=ParcelFileDescriptor.open(temp,ParcelFileDescriptor.MODE_READ_ONLY)){
            MessageDigest digest=MessageDigest.getInstance("SHA-256");long size=0;
            try(FileOutputStream out=new FileOutputStream(temp);
                InputStream in=context.getContentResolver().openInputStream(uri)){
                // Keep only open descriptors. Even a crash after this point
                // leaves no named plaintext PDF in the app cache.
                if(!temp.delete())throw new IllegalStateException("pdf_temporary_unlink_failed");
                if(in==null)throw new IllegalArgumentException("pdf_unreadable_or_encrypted");
                byte[] buffer=new byte[65536];
                for(int n;(n=in.read(buffer))!=-1;){
                    if(Thread.currentThread().isInterrupted())throw new InterruptedException();
                    size+=n;if(size>AssistantPdfExtractionService.MAX_PDF_BYTES)
                        throw new IllegalArgumentException("invalid_pdf_range_or_size");
                    digest.update(buffer,0,n);out.write(buffer,0,n);
                }
            }
            if(size<5)throw new IllegalArgumentException("invalid_pdf_range_or_size");
            StringBuilder hash=new StringBuilder();for(byte v:digest.digest())hash.append(String.format(java.util.Locale.ROOT,"%02x",v&255));
            String id=UUID.randomUUID().toString();
            CountDownLatch finished=new CountDownLatch(1);
            AtomicReference<Bundle> result=new AtomicReference<>();
            Handler handler=new Handler(Looper.getMainLooper(),reply->{
                if(reply.what==AssistantPdfExtractionService.RESULT&&id.equals(reply.getData().getString("id"))){
                    result.compareAndSet(null,reply.getData());finished.countDown();
                }
                return true;
            });
            {
                ServiceConnection connection=new ServiceConnection(){
                    @Override public void onServiceConnected(ComponentName n,IBinder binder){
                        try{
                            Message request=Message.obtain(null,AssistantPdfExtractionService.REQUEST);
                            Bundle data=new Bundle();data.putParcelable("pdf",file);data.putString("id",id);
                            data.putInt("first",first);data.putInt("last",last);
                            request.setData(data);request.replyTo=new Messenger(handler);
                            new Messenger(binder).send(request);
                        }catch(Exception failure){finished.countDown();}
                    }
                    @Override public void onServiceDisconnected(ComponentName n){finished.countDown();}
                    @Override public void onBindingDied(ComponentName n){finished.countDown();}
                    @Override public void onNullBinding(ComponentName n){finished.countDown();}
                };
                boolean bound=context.bindService(new Intent(context,AssistantPdfExtractionService.class),connection,Context.BIND_AUTO_CREATE);
                if(!bound)throw new IllegalStateException("pdf_extractor_unavailable");
                try{
                    if(!finished.await(60,TimeUnit.SECONDS))throw new IllegalStateException("pdf_extraction_timeout");
                    Bundle reply=result.get();
                    if(reply==null)throw new IllegalStateException("pdf_extractor_disconnected");
                    if(!reply.getBoolean("ok"))throw new IllegalArgumentException(reply.getString("reason","pdf_unreadable_or_encrypted"));
                    String text=reply.getString("text");
                    int start=reply.getInt("first"),end=reply.getInt("last"),pages=reply.getInt("pages"),empty=reply.getInt("empty_pages");
                    if(text==null||start!=first||end<start||end>last||pages<end||empty<0||empty>=end-start+1||
                        text.getBytes(StandardCharsets.UTF_8).length>AssistantPdfExtractionService.MAX_TEXT_BYTES)
                        throw new IllegalStateException("invalid_pdf_extraction_receipt");
                    String header="PDF text extraction (not image or OCR analysis)\nOriginal PDF SHA-256: "+hash+
                        "\nPages "+start+"–"+end+" of "+pages+"; pages without text: "+empty+
                        "\nSource: "+name+"\n";
                    return new ProjectSourceText(name+" · pages "+start+"–"+end,
                        (header+text).getBytes(StandardCharsets.UTF_8));
                }finally{context.unbindService(connection);}
            }
        }finally{if(temp.exists())temp.delete();}
    }
}
