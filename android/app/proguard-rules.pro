# R8 optimized release. Android components are registered by the manifest;
# no broad keep-all rule or debug-only behavior is needed.
-keepattributes *Annotation*,Signature,InnerClasses,EnclosingMethod
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
