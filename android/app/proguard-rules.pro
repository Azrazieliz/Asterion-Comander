# R8 optimized release. Android components are registered by the manifest;
# no broad keep-all rule or debug-only behavior is needed.
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# JNI symbol names are bound to this exact class and native method names.
# R8 must not rename these entry points in owner-signed release APKs.
-keep class com.asterion.control.OnDeviceLlm { *; }
