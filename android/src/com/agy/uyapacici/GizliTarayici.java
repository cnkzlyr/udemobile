package com.agy.uyapacici;

import android.annotation.SuppressLint;
import android.content.Context;
import android.os.Build;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Asistanın UYAP / e-Devlet oturumu için GÖRÜNMEZ tarayıcı (Termux'suz, Chrome'suz).
 *
 * Ekrana hiç eklenmeyen bir WebView UYAP portalını açık tutar. DevTools'u açılır; Android bunu
 * yalnızca AYNI uygulamanın (aynı UID) erişebildiği "webview_devtools_remote_<pid>" soyut soketinde
 * sunar. Asistan sunucusu (sunucu.py cdp_kopru_baslat) bu soketi 127.0.0.1:9223'e köprüler; UYAP
 * modülleri masaüstündeki gizli Chrome'la konuştukları CDP ile aynen bu WebView'ı kullanır:
 * e-İmza (kart takılıysa) ya da Mobil İmza ile oturum açılır ve oturum açık tutulur.
 */
final class GizliTarayici {
    static final String UYAP = "https://avukat.uyap.gov.tr";
    private static WebView wv;

    private GizliTarayici() { }

    /** Asistan sunucusuna verilecek DevTools soketinin adı. */
    static String soketAdi() {
        return "webview_devtools_remote_" + android.os.Process.myPid();
    }

    /** Ana iş parçacığından çağrılır; bir kez oluşturur. */
    @SuppressLint("SetJavaScriptEnabled")
    static synchronized void hazirla(Context c) {
        if (wv != null) return;
        try {
            WebView.setWebContentsDebuggingEnabled(true);
            wv = new WebView(c.getApplicationContext());
            WebSettings s = wv.getSettings();
            s.setJavaScriptEnabled(true);
            s.setDomStorageEnabled(true);
            s.setJavaScriptCanOpenWindowsAutomatically(false);
            s.setSupportMultipleWindows(false);   // açılır pencereler aynı sekmede açılır
            s.setUseWideViewPort(true);
            s.setLoadWithOverviewMode(true);
            // Masaüstü UYAP arayüzü (modüller masaüstü sayfa yapısını bekler)
            s.setUserAgentString("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    + "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36");
            if (Build.VERSION.SDK_INT >= 21) {
                s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
                CookieManager.getInstance().setAcceptThirdPartyCookies(wv, true);
            }
            CookieManager.getInstance().setAcceptCookie(true);
            wv.setWebViewClient(new WebViewClient());
            // Ekran dışı da olsa düzen boyutu olsun (sayfa betikleri genişlik ölçer)
            wv.layout(0, 0, 1366, 900);
            wv.loadUrl(UYAP);
            Tani.yaz("asistan", "gizli UYAP tarayıcısı hazır: " + soketAdi());
        } catch (Throwable t) {
            wv = null;
            Tani.yaz("asistan", "gizli tarayıcı açılamadı: " + t);
        }
    }

    static boolean hazir() { return wv != null; }
}
