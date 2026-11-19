package com.asterion.control;

import android.app.Application;
import android.content.Context;
import android.util.AtomicFile;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * R02: best-effort last unhandled Java failure for all Control processes.
 * Records ONLY the exception type and source stack frames (no exception
 * messages, URLs, prompt text, bearer tokens, account data or raw logs).
 * The existing Android crash handler still runs; there is no swallowing of
 * failures or fake recovery. Protected by Android app-private storage.
 */
final class ControlCrashRecorder {
    private static final AtomicBoolean WRITING=new AtomicBoolean(false);
    private static final String PREFIX="asterion_control_java_crash_";
    private ControlCrashRecorder(){}
    static void install(Application owner){
        final Thread.UncaughtExceptionHandler previous=
            Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread,throwable)->{
            if(WRITING.compareAndSet(false,true)){
                try{write(owner,thread,throwable);}
                catch(Throwable ignored){/* never obstruct OS crash handling */}
                finally{WRITING.set(false);}
            }
            if(previous!=null)previous.uncaughtException(thread,throwable);
            else android.os.Process.killProcess(android.os.Process.myPid());
        });
    }
    private static String processSuffix(){
        String process=Application.getProcessName();
        return process!=null&&process.endsWith(":asterion_browser")?
            "browser":"main";
    }
    private static File destination(Context owner,String suffix){
        if(!suffix.equals("browser")&&!suffix.equals("main"))
            throw new IllegalArgumentException("Unsupported process");
        return new File(owner.getNoBackupFilesDir(),PREFIX+suffix+".json");
    }
    private static void write(Context owner,Thread thread,Throwable error)throws Exception {
        JSONObject document=new JSONObject()
            .put("schema_version",1)
            .put("timestamp_ms",System.currentTimeMillis())
            .put("process",processSuffix())
            .put("exception_type",error.getClass().getName())
            .put("thread_kind",thread==android.os.Looper.getMainLooper().getThread()?
                "main":"background")
            .put("exception_message_saved",false)
            .put("sensitive_data_saved",false);
        JSONArray frames=new JSONArray();
        StackTraceElement[] trace=error.getStackTrace();
        for(int i=0;i<Math.min(36,trace.length);i++){
            StackTraceElement frame=trace[i];
            frames.put(new JSONObject()
                .put("class",frame.getClassName())
                .put("method",frame.getMethodName())
                .put("source",frame.getFileName())
                .put("line",frame.getLineNumber()));
        }
        document.put("frames",frames);
        // Full exception causes/messages intentionally never persisted.
        AtomicFile file=new AtomicFile(destination(owner,processSuffix()));
        FileOutputStream out=null;
        try{
            out=file.startWrite();
            byte[] value=document.toString().getBytes(StandardCharsets.UTF_8);
            if(value.length>16000)throw new IllegalStateException("Crash record too large");
            out.write(value);
            file.finishWrite(out);
        }catch(Exception failure){
            if(out!=null)file.failWrite(out);
            throw failure;
        }
    }
    static JSONObject last(Context context,String process){
        try{
            File file=destination(context,process);
            if(!file.isFile()||file.length()>16000)return new JSONObject()
                .put("available",false);
            byte[] bytes;
            try(FileInputStream stream=new FileInputStream(file)){
                bytes=stream.readNBytes(16001);
            }
            if(bytes.length>16000)return new JSONObject().put("available",false);
            return new JSONObject(new String(bytes,StandardCharsets.UTF_8))
                .put("available",true);
        }catch(Exception ignored){
            return new JSONObject().put("available",false);
        }
    }
}
