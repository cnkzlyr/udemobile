package com.agy.uyapacici;

import android.annotation.SuppressLint;
import android.content.Context;
import android.graphics.Color;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

/**
 * Anlık mobil görünüm (3.24.0): resmi UYAP Editör'ün BELLEKTEKİ belgesi telefon genişliğinde, satır kırarak gösterilir
 * (köprü: uyapmobil.Mobil → MOBIL / MKARET / MRESIM). Kaydetme ya da başka bir editöre aktarma yoktur; belge, imzalar ve
 * dosya olduğu gibi kalır. Dokunulan yer resmi editörde imlecin konumu olur (MK); klavye girişi resmi editöre gider
 * (odak EkranView'da kalır), değişiklikler burada hemen görünür.
 */
final class MobilGorunum extends WebView {
    private boolean hazir;
    private final List<String> bekleyen = new ArrayList<>();
    private float olcek = 1f;

    @SuppressLint({"SetJavaScriptEnabled", "AddJavascriptInterface"})
    MobilGorunum(Context c) {
        super(c);
        setBackgroundColor(Color.rgb(232, 234, 237));
        WebSettings s = getSettings();
        s.setJavaScriptEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setTextZoom(100);
        s.setSupportZoom(false);
        // klavye odağı resmi editörde (EkranView) kalsın: yazılanlar oraya gider
        setFocusable(false);
        setFocusableInTouchMode(false);
        setVerticalScrollBarEnabled(false);
        addJavascriptInterface(new Kopru(), "K");
        setWebViewClient(new WebViewClient() {
            @Override public void onPageFinished(WebView v, String url) {
                hazir = true;
                js(yaziTipleri(getContext()));
                js("olcek(" + olcek + ")");
                for (String b : bekleyen) js(b);
                bekleyen.clear();
            }
        });
        loadUrl("file:///android_asset/uyapmobil/mobil.html");
    }

    private final class Kopru {
        @JavascriptInterface public void imlec(int a, int b) {
            UyapMobilServisi.gonder("MK " + a + (b >= 0 ? " " + b : ""));
        }
    }

    /** Köprüden gelen satır: "MOBIL <b64> a b" · "MKARET a b" · "MRESIM no png". */
    void satir(String s) {
        if (s.startsWith("MOBIL ")) {
            String[] p = s.split(" ");
            if (p.length < 4) return;
            // base64 → UTF-8 JS içinde çözülür (büyük dizeyi Java'da kaçışlamaktan hızlı)
            calistir("icerik(decodeURIComponent(escape(atob('" + p[1] + "')))," + p[2] + "," + p[3] + ")");
        } else if (s.startsWith("MKARET ")) {
            String[] p = s.split(" ");
            if (p.length >= 3) calistir("imlec(" + p[1] + "," + p[2] + ",false)");
        } else if (s.startsWith("MRESIM ")) {
            String[] p = s.split(" ", 3);
            if (p.length == 3) calistir("resim('" + p[1] + "','" + p[2] + "')");
        }
    }

    void yakinlastir(float k) {
        olcek = Math.max(0.6f, Math.min(2.2f, olcek * k));
        calistir("olcek(" + olcek + ")");
    }

    int yuzde() { return Math.round(olcek * 100); }

    void olcekSifirla() { olcek = 1f; calistir("olcek(1)"); }

    private void calistir(String j) {
        if (hazir) js(j); else {
            if (j.startsWith("icerik(")) bekleyen.removeIf(x -> x.startsWith("icerik("));
            bekleyen.add(j);
        }
    }

    private void js(String j) { evaluateJavascript(j, null); }

    /** Liberation yazı tipleri (Times New Roman / Arial / Courier New ile ölçüleri aynı) ve kullanıcının eklediği TTF'ler. */
    private static String yaziTipleri(Context c) {
        StringBuilder css = new StringBuilder();
        File rt = new File(UyapMobil.rt(c), "fonts");
        String[][] eslem = {{"Liberation Serif", "LiberationSerif"}, {"Times New Roman", "LiberationSerif"},
                {"Liberation Sans", "LiberationSans"}, {"Arial", "LiberationSans"}, {"Liberation Mono", "LiberationMono"}, {"Courier New", "LiberationMono"}};
        String[][] stil = {{"Regular", "normal", "normal"}, {"Bold", "bold", "normal"}, {"Italic", "normal", "italic"}, {"BoldItalic", "bold", "italic"}};
        for (String[] e : eslem)
            for (String[] s : stil) {
                File f = new File(rt, e[1] + "-" + s[0] + ".ttf");
                if (f.isFile()) css.append("@font-face{font-family:'").append(e[0]).append("';src:url('file://").append(f.getAbsolutePath())
                        .append("');font-weight:").append(s[1]).append(";font-style:").append(s[2]).append(";}");
            }
        // kullanıcının eklediği gerçek yazı tipleri (ör. times.ttf) öncelikli
        File[] ek = UyapMobil.yaziTipleri(c).listFiles();
        if (ek != null) for (File f : ek) {
            String ad = f.getName().toLowerCase(java.util.Locale.ROOT);
            if (!ad.endsWith(".ttf") && !ad.endsWith(".otf")) continue;
            String aile = ad.startsWith("times") ? "Times New Roman" : ad.startsWith("arial") ? "Arial" : ad.startsWith("cour") ? "Courier New"
                    : ad.startsWith("georgia") ? "Georgia" : ad.startsWith("verdana") ? "Verdana" : ad.startsWith("tahoma") ? "Tahoma" : null;
            if (aile == null) continue;
            boolean kalin = ad.contains("bd") || ad.contains("bold"), egik = ad.contains("i.") || ad.contains("italic") || ad.contains("bi.");
            css.append("@font-face{font-family:'").append(aile).append("';src:url('file://").append(f.getAbsolutePath())
                    .append("');font-weight:").append(kalin ? "bold" : "normal").append(";font-style:").append(egik ? "italic" : "normal").append(";}");
        }
        String k = css.toString().replace("\\", "\\\\").replace("'", "\\'");
        return "(function(){var s=document.createElement('style');s.textContent='" + k + "';document.head.appendChild(s);})()";
    }
}
