package com.asterion.control;

import android.content.Context;
import android.os.PowerManager;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

/** Observe Android resource pressure even before first token. Never kill other
 * apps, change clocks, or lower the signed allocation estimate. */
final class InferenceResourceGuard implements AutoCloseable {
    private static final ScheduledExecutorService WATCH=
        Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"asterion-ai-resource");t.setDaemon(true);return t;});
    private final AtomicReference<String> failure=new AtomicReference<>("");
    private final ScheduledFuture<?> future;
    private volatile boolean closed;
    InferenceResourceGuard(Context c,InferenceGate gate,InferenceGate.Request request){
        Context app=c.getApplicationContext();
        future=WATCH.scheduleWithFixedDelay(()->{
            if(closed||request.isCancelled()||!failure.get().isEmpty())return;
            try{
                OnDeviceModelResources sample=new OnDeviceModelResources(app);
                String reason=sample.memory.lowMemory?"android_memory_pressure":
                    sample.thermalStatus>=PowerManager.THERMAL_STATUS_SEVERE?"android_thermal_pressure":"";
                if(!reason.isEmpty()&&!closed&&failure.compareAndSet("",reason))
                    gate.abortActive(request);
            }catch(RuntimeException ignored){
                // Failed observation is not permission to increase allocations.
            }
        },1000,1000,TimeUnit.MILLISECONDS);
    }
    String failure(){return failure.get();}
    void check(){
        String reason=failure();
        if(!reason.isEmpty())throw new IllegalStateException(reason);
    }
    @Override public void close(){closed=true;future.cancel(false);}
}
