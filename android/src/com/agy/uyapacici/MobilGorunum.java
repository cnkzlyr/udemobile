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
    interface Eylem { void eylem(String e); }
    Eylem eylemDinleyici;
    private boolean hazir;
    private final List<String> bekleyen = new ArrayList<>();
    private float olcek = 1f;
    private volatile float olcekDegeri = -1;

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

        /** İki parmakla yakınlaştırma bitti: kapsüldeki yüzde güncellensin. */
        @JavascriptInterface public void olcek(float k) {
            olcekDegeri = k;
            Eylem d = eylemDinleyici;
            if (d != null) post(() -> d.eylem("olcek"));
        }

        /** Seçim eylem çubuğu: kes / kopyala / yapistir / tumu. */
        @JavascriptInterface public void eylem(String e) {
            Eylem d = eylemDinleyici;
            if (d != null) post(() -> d.eylem(e));
        }

        /** Kağıt görünümünde dokunulan motor koordinatı (x2 ≥ 0: seçim sonu). */
        @JavascriptInterface public void nokta(int x, int y, int x2, int y2) {
            UyapMobilServisi.gonder("MP " + x + " " + y + (x2 >= 0 ? " " + x2 + " " + y2 : ""));
        }
    }

    /** Köprüden gelen satır: "MOBIL <b64> a b" · "MKAGIT <b64> a b [x y h]" · "MKARET a b [x y h]" · "MRESIM no png". */
    void satir(String s) {
        String[] p = s.split(" ");
        if (s.startsWith("MKAGIT ") || s.startsWith("MOBIL ")) {
            if (p.length < 4) return;
            String im = p.length >= 7 ? "," + p[4] + "," + p[5] + "," + p[6] : "";
            calistir((s.startsWith("MKAGIT ") ? "kagitCiz(" : "mobilCiz(") + "b64('" + p[1] + "')," + p[2] + "," + p[3] + im + ")");
        } else if (s.startsWith("MKARET ")) {
            if (p.length >= 3) calistir("imlec(" + p[1] + "," + p[2] + (p.length >= 6 ? "," + p[3] + "," + p[4] + "," + p[5] : "") + ")");
        } else if (s.startsWith("MRESIM ")) {
            String[] q = s.split(" ", 3);
            if (q.length == 3) calistir("resim('" + q[1] + "','" + q[2] + "')");
        }
    }

    /** Klavyeden yazılan metni motor yanıtını beklemeden göster. */
    void yerel(String t) {
        if (!hazir || t == null || t.isEmpty()) return;
        String k = t.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "");
        if (!k.isEmpty()) js("yerel('" + k + "')");
    }

    void yakinlastir(float k) {
        olcek = Math.max(0.6f, Math.min(2.2f, olcek * k));
        calistir("olcek(" + olcek + ")");
    }

    int yuzde() { if (olcekDegeri > 0) { olcek = olcekDegeri; olcekDegeri = -1; } return Math.round(olcek * 100); }

    void olcekSifirla() { olcek = 1f; calistir("olcek(1)"); }

    private void calistir(String j) {
        if (hazir) js(j); else {
            if (j.startsWith("mobilCiz(") || j.startsWith("kagitCiz(")) bekleyen.removeIf(x -> x.startsWith("mobilCiz(") || x.startsWith("kagitCiz("));
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
        // Windows yazı tipleri (YaziTipleri: corefonts) ve kullanıcının eklediği TTF'ler — dosya adı → aile/biçim
        String[][] dosyalar = {
                {"times", "Times New Roman", "n", "n"}, {"timesbd", "Times New Roman", "b", "n"}, {"timesi", "Times New Roman", "n", "i"}, {"timesbi", "Times New Roman", "b", "i"},
                {"arial", "Arial", "n", "n"}, {"arialbd", "Arial", "b", "n"}, {"ariali", "Arial", "n", "i"}, {"arialbi", "Arial", "b", "i"}, {"ariblk", "Arial Black", "n", "n"},
                {"cour", "Courier New", "n", "n"}, {"courbd", "Courier New", "b", "n"}, {"couri", "Courier New", "n", "i"}, {"courbi", "Courier New", "b", "i"},
                {"georgia", "Georgia", "n", "n"}, {"georgiab", "Georgia", "b", "n"}, {"georgiai", "Georgia", "n", "i"}, {"georgiaz", "Georgia", "b", "i"},
                {"verdana", "Verdana", "n", "n"}, {"verdanab", "Verdana", "b", "n"}, {"verdanai", "Verdana", "n", "i"}, {"verdanaz", "Verdana", "b", "i"},
                {"trebuc", "Trebuchet MS", "n", "n"}, {"trebucbd", "Trebuchet MS", "b", "n"}, {"trebucit", "Trebuchet MS", "n", "i"}, {"trebucbi", "Trebuchet MS", "b", "i"},
                {"comic", "Comic Sans MS", "n", "n"}, {"comicbd", "Comic Sans MS", "b", "n"}, {"impact", "Impact", "n", "n"},
                {"andalemo", "Andale Mono", "n", "n"}, {"webdings", "Webdings", "n", "n"},
                {"tahoma", "Tahoma", "n", "n"}, {"tahomabd", "Tahoma", "b", "n"}, {"calibri", "Calibri", "n", "n"}, {"calibrib", "Calibri", "b", "n"},
                {"calibrii", "Calibri", "n", "i"}, {"calibriz", "Calibri", "b", "i"}, {"cambria", "Cambria", "n", "n"}, {"segoeui", "Segoe UI", "n", "n"},
        };
        java.util.Map<String, String[]> esle = new java.util.HashMap<>();
        for (String[] d : dosyalar) esle.put(d[0], d);
        File[] ek = UyapMobil.yaziTipleri(c).listFiles();
        if (ek != null) for (File f : ek) {
            String ad = f.getName().toLowerCase(java.util.Locale.ROOT);
            if (!ad.endsWith(".ttf") && !ad.endsWith(".otf")) continue;
            String[] d = esle.get(ad.substring(0, ad.length() - 4));
            if (d == null) continue;
            css.append("@font-face{font-family:'").append(d[1]).append("';src:url('file://").append(f.getAbsolutePath())
                    .append("');font-weight:").append("b".equals(d[2]) ? "bold" : "normal").append(";font-style:").append("i".equals(d[3]) ? "italic" : "normal").append(";}");
        }
        String k = css.toString().replace("\\", "\\\\").replace("'", "\\'");
        return "(function(){var s=document.createElement('style');s.textContent='" + k + "';document.head.appendChild(s);})()";
    }
}
