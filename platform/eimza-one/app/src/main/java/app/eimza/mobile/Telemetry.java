package app.eimza.mobile;

import android.content.Context;
import android.os.Bundle;

/** Optional Firebase adapter. It is inert until Firebase dependencies and consent are present. */
final class Telemetry {
    private static Object analytics;
    private static Object crashlytics;
    private static boolean enabled;

    private Telemetry() { }

    static void configure(Context context, boolean allowCollection) {
        enabled = allowCollection;
        if (!enabled) return;
        try {
            Class<?> analyticsClass = Class.forName("com.google.firebase.analytics.FirebaseAnalytics");
            analytics = analyticsClass.getMethod("getInstance", Context.class).invoke(null, context);
            analyticsClass.getMethod("setAnalyticsCollectionEnabled", boolean.class)
                    .invoke(analytics, true);
        } catch (Exception ignored) { analytics = null; }
        try {
            Class<?> crashClass = Class.forName("com.google.firebase.crashlytics.FirebaseCrashlytics");
            crashlytics = crashClass.getMethod("getInstance").invoke(null);
            crashClass.getMethod("setCrashlyticsCollectionEnabled", boolean.class)
                    .invoke(crashlytics, true);
        } catch (Exception ignored) { crashlytics = null; }
    }

    static void event(String name) { event(name, null); }

    static void event(String name, String value) {
        if (!enabled || analytics == null) return;
        try {
            Bundle bundle = new Bundle();
            if (value != null) bundle.putString("category", value);
            analytics.getClass().getMethod("logEvent", String.class, Bundle.class)
                    .invoke(analytics, name, bundle);
        } catch (Exception ignored) { }
    }

    static void breadcrumb(String message) {
        if (!enabled || crashlytics == null || message == null) return;
        try {
            crashlytics.getClass().getMethod("log", String.class).invoke(crashlytics, message);
        } catch (Exception ignored) { }
    }
}
