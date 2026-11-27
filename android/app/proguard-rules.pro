# R8 optimized release. Android components are registered by the manifest;
# no broad keep-all rule or debug-only behavior is needed.
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# JNI symbol names are bound to this exact class and native method names.
# R8 must not rename these entry points in owner-signed release APKs.
-keep class com.asterion.control.OnDeviceLlm { *; }

# JNI invokes these callbacks by exact name; preserve them in owner release.
-keep class com.asterion.control.OnDeviceLlm$NativeStream { public void onStart(boolean,int,int,int); public void onToken(byte[]); }

# Preserve JNI binary names with R8 9.1.
-dontrepackage
-keep class org.torproject.jni.TorService { *; }
