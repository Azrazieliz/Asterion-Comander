package com.asterion.control;

import android.app.Application;

/** Asterion process-wide, owner-private Java crash evidence installer. */
public final class ControlApplication extends Application {
    @Override public void onCreate(){
        super.onCreate();
        ControlCrashRecorder.install(this);
    }
}
