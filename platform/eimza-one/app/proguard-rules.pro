# Android manifest entry point and JavaScript bridge methods must remain callable.
-keep public class app.eimza.mobile.MainActivity { public <init>(...); }
-keepclassmembers class app.eimza.mobile.MainActivity$ArkPageBridge {
    <methods>;
}
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Provider and certificate libraries use reflection for algorithm/provider names.
-keep class app.eimza.mobile.AndroidCcidProvider** { *; }
-keepclassmembers class app.eimza.mobile.AndroidCcidProvider** {
    public <init>();
    public <init>(...);
    *;
}
-keep class app.eimza.mobile.AndroidCardSession** { *; }
-keep class app.eimza.mobile.ArkSignerTokenBackend** { *; }
-keep class app.eimza.mobile.ArkSignerTokenDriver** { *; }
-keep class app.eimza.mobile.AkisSignerBackend** { *; }
-keep class app.eimza.mobile.DiagnosticLogger** { *; }
-keep class app.eimza.mobile.SignerBackend** { *; }
-keep class org.bouncycastle.** { *; }
-keep class tr.gov.tubitak.** { *; }
-keep class javax.smartcardio.** { *; }
-keepclassmembers class javax.smartcardio.** {
    public <init>();
    public <init>(...);
    *;
}
-dontwarn org.bouncycastle.**
-dontwarn org.slf4j.**
-dontwarn java.awt.**
-dontwarn javax.naming.**
-dontwarn javax.swing.**

# Do not retain source-level debug metadata in release artifacts.
-renamesourcefileattribute SourceFile
-keepattributes Exceptions,InnerClasses,Signature,*Annotation*
