package com.agy.uyapacici;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Context;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.os.Build;
import android.webkit.CookieManager;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.WebChromeClient;
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
    /** UETS için ayrı gizli sayfa: UETS girişi UYAP oturumunu bozmasın (CdpSurucu "#uets" sayfasını seçer). */
    static final String UETS_BOS = "about:blank#uets";
    private static WebView wv;
    private static WebView wvUets;

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
            wv = olustur(c, UYAP);
            Tani.yaz("asistan", "gizli UYAP tarayıcısı hazır: " + soketAdi());
        } catch (Throwable t) {
            wv = null;
            Tani.yaz("asistan", "gizli tarayıcı açılamadı: " + t);
        }
        try {
            if (wvUets == null) wvUets = olustur(c, UETS_BOS);
        } catch (Throwable t) {
            wvUets = null;
            Tani.yaz("asistan", "gizli UETS tarayıcısı açılamadı: " + t);
        }
    }

    /** Ekrana HİÇ eklenmeyen WebView (DevTools'ta never_attached=true görünür; sunucu yalnızca bunları kullanır). */
    @SuppressLint("SetJavaScriptEnabled")
    private static WebView olustur(Context c, String url) {
        WebView wv;
        {
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
            // Arka planda çalışan e-Devlet/UYAP sayfalarındaki JS alert/confirm kutuları oturumu kilitlemesin
            wv.setWebChromeClient(new WebChromeClient() {
                @Override
                public boolean onJsAlert(WebView view, String url, String message, JsResult result) {
                    Tani.yaz("asistan", "gizli tarayıcı alert: " + message);
                    result.confirm();
                    return true;
                }
                @Override
                public boolean onJsConfirm(WebView view, String url, String message, JsResult result) {
                    Tani.yaz("asistan", "gizli tarayıcı confirm: " + message);
                    result.confirm();
                    return true;
                }
                @Override
                public boolean onJsPrompt(WebView view, String url, String message, String defaultValue, JsPromptResult result) {
                    result.cancel();
                    return true;
                }
            });
            // Ekran dışı da olsa düzen boyutu olsun (sayfa betikleri genişlik ölçer)
            wv.layout(0, 0, 1366, 900);
            wv.loadUrl(url);
        }
        return wv;
    }

    static boolean hazir() { return wv != null; }

    /**
     * v4.9.1: Otomasyon WebView'larını öndeki etkinliğin penceresine EKRAN DIŞINDA (-20000 px) ekler.
     *
     * Hiç pencereye eklenmemiş WebView'ı Chromium "gizli sekme" sayar: zamanlayıcıları 5 dk sonra dakikada bire
     * indirilir (intensive wake-up throttling). UYAP giriş ve e-Devlet Mobil İmza sayfaları zincirleme
     * zamanlayıcılarla çalıştığı için v4.9.0'da Mobil İmza formu hiç gönderilemiyor, süre doluyordu.
     * Pencereye eklenmiş ama ekran dışında duran WebView "görünür" sayılır (tam hızda çalışır), kullanıcı ise
     * hiçbir şey görmez ve dokunamaz. Görünür Asistan/editör ekranı sunucu köprüsünde yerel adresinden ayıklanır.
     */
    static synchronized void ekranaBagla(Activity a) {
        if (a == null) return;
        ViewGroup kok;
        try {
            kok = (ViewGroup) a.getWindow().getDecorView();
        } catch (Throwable t) {
            return;
        }
        for (WebView v : new WebView[]{wv, wvUets}) {
            if (v == null || v.getParent() == kok) continue;
            try {
                if (v.getParent() instanceof ViewGroup) ((ViewGroup) v.getParent()).removeView(v);
                v.setFocusable(false);
                v.setFocusableInTouchMode(false);
                v.setClickable(false);
                v.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
                v.setTranslationX(-20000f);
                v.setTranslationY(-20000f);
                kok.addView(v, new FrameLayout.LayoutParams(1366, 900));
                v.onResume();
                v.resumeTimers();
            } catch (Throwable t) {
                Tani.yaz("asistan", "gizli tarayıcı pencereye eklenemedi: " + t);
            }
        }
    }

    /** Etkinlik kapanırken WebView'ları o pencereden ayırır (sızıntı olmasın); WebView'lar yaşamaya devam eder. */
    static synchronized void ekrandanAyir(Activity a) {
        if (a == null) return;
        try {
            View kok = a.getWindow().getDecorView();
            for (WebView v : new WebView[]{wv, wvUets}) {
                if (v != null && v.getParent() == kok) ((ViewGroup) kok).removeView(v);
            }
        } catch (Throwable t) {
            Tani.yaz("asistan", "gizli tarayıcı ayrılamadı: " + t);
        }
    }
}
