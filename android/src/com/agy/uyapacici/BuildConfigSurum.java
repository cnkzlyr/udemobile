package com.agy.uyapacici;

import android.content.Context;

/** Uygulama sürüm adı (günlük başlığı için). */
final class BuildConfigSurum {
    private BuildConfigSurum() { }

    static String surum(Context c) {
        try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionName; } catch (Exception e) { return "?"; }
    }
}
