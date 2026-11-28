package com.asterion.control;

import android.app.Service;
import android.content.Intent;
import android.graphics.pdf.PdfRenderer;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Message;
import android.os.Messenger;
import android.os.ParcelFileDescriptor;
import java.nio.charset.StandardCharsets;

/** Isolated, nonexported, permissionless process: only the selected read-only
 * document descriptor enters. No Control storage, credentials, or network. */
public final class AssistantPdfExtractionService extends Service {
    static final int REQUEST=1,RESULT=2,MAX_PAGES=50,MAX_TEXT_BYTES=180_000;
    static final long MAX_PDF_BYTES=64L*1024*1024;
    private HandlerThread thread;
    private Messenger messenger;
    @Override public void onCreate(){
        super.onCreate();
        thread=new HandlerThread("pdf-extraction");
        thread.start();
        messenger=new Messenger(new Handler(thread.getLooper(),this::extract));
    }
    @Override public IBinder onBind(Intent intent){return messenger.getBinder();}
    @Override public void onDestroy(){if(thread!=null)thread.quitSafely();super.onDestroy();}
    private boolean extract(Message message){
        if(message.what!=REQUEST||message.replyTo==null)return true;
        Bundle args=message.getData();
        Bundle out=new Bundle();
        out.putString("id",args.getString("id",""));
        ParcelFileDescriptor fd=args.getParcelable("pdf");
        try{
            int first=args.getInt("first"),last=args.getInt("last");
            if(Build.VERSION.SDK_INT<35)throw new IllegalArgumentException("pdf_text_api_unavailable");
            if(fd==null||fd.getStatSize()<5||fd.getStatSize()>MAX_PDF_BYTES||
               first<1||last<first||last-first>=MAX_PAGES||last>100000)
                throw new IllegalArgumentException("invalid_pdf_range_or_size");
            // PdfRenderer owns the descriptor only after successful creation.
            PdfRenderer opened=new PdfRenderer(fd);
            fd=null;
            try(PdfRenderer pdf=opened){
                int total=pdf.getPageCount(),end=Math.min(last,total);
                if(first>total)throw new IllegalArgumentException("page_range_outside_document");
                StringBuilder body=new StringBuilder();int bytes=0,blank=0;
                for(int n=first;n<=end;n++){
                    StringBuilder pageText=new StringBuilder();
                    try(PdfRenderer.Page page=pdf.openPage(n-1)){
                        for(android.graphics.pdf.content.PdfPageTextContent part:page.getTextContents()){
                            String value=part.getText();
                            if(value==null||value.isEmpty())continue;
                            if(value.length()>MAX_TEXT_BYTES||pageText.length()+value.length()+1>MAX_TEXT_BYTES)
                                throw new IllegalArgumentException("pdf_text_budget");
                            pageText.append(value).append('\n');
                        }
                    }
                    boolean empty=pageText.toString().isBlank();
                    if(empty)blank++;
                    String block="\n[PDF page "+n+"]\n"+(empty?"[No extractable text on this page]\n":pageText.toString());
                    bytes+=block.getBytes(StandardCharsets.UTF_8).length;
                    if(bytes>MAX_TEXT_BYTES)throw new IllegalArgumentException("pdf_text_budget");
                    body.append(block);
                }
                if(blank==end-first+1)throw new IllegalArgumentException("no_extractable_text");
                out.putBoolean("ok",true);out.putString("text",body.toString());
                out.putInt("first",first);out.putInt("last",end);out.putInt("pages",total);out.putInt("empty_pages",blank);
            }
        }catch(Exception failure){
            String reason=failure.getMessage();
            if(reason==null||!java.util.Set.of("pdf_text_api_unavailable","invalid_pdf_range_or_size",
                "page_range_outside_document","pdf_text_budget","no_extractable_text").contains(reason))
                reason="pdf_unreadable_or_encrypted";
            out.putBoolean("ok",false);out.putString("reason",reason);
        }finally{if(fd!=null)try{fd.close();}catch(Exception ignored){}}
        Message result=Message.obtain(null,RESULT);result.setData(out);
        try{message.replyTo.send(result);}catch(Exception disconnected){}
        return true;
    }
}
