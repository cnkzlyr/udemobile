package com.agy.uyapacici;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.DecelerateInterpolator;
import android.view.animation.PathInterpolator;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Resmi editörün pencereleri için yerel mobil panel (3.27.0) — mobil imza, e-imza PIN'i, sertifika/imza seçimi,
 * uyarı ve soru pencereleri. Köprü (uyapmobil.Form) pencerenin alanlarını gönderir (FORM); burada alttan kayan,
 * dokunmaya uygun bir panel olarak çizilir; yazılan/seçilen her şey orijinal pencereye geri yazılır (FA/FT/FS),
 * düğmeler orijinal düğmeye basar. Kağıt, mobil ve orijinal görünümün hepsinde aynı panel kullanılır.
 * Pencere değiştikçe (ör. mobil imzada doğrulama kodu gelince) panel yerinde güncellenir; yazılan alan ve klavye kaybolmaz.
 */
final class FormPaneli {
    interface Dinleyici { void orijinaliGoster(); }

    private final Activity a;
    private final FrameLayout kok;
    private final Dinleyici din;
    private FrameLayout perde;
    private LinearLayout panel, icerik, dugmeler;
    private TextView baslikTv;
    private int no = -1;
    private String imza = "";
    private final Map<Integer, EditText> alanlar = new HashMap<>();
    private final Map<Integer, CheckBox> kutular = new HashMap<>();
    private final Map<Integer, View> radyolar = new HashMap<>();
    private final Map<Integer, LinearLayout> listeler = new HashMap<>();
    private final java.util.List<TextView> metinler = new java.util.ArrayList<>();
    private JSONObject son;

    FormPaneli(Activity a, FrameLayout kok, Dinleyici din) {
        this.a = a;
        this.kok = kok;
        this.din = din;
    }

    boolean acik() { return perde != null && perde.getParent() != null; }

    /** Orijinal pencerenin "Kapat / İptal / Vazgeç / Hayır" düğmesine bas (geri tuşu). */
    boolean geri() {
        if (!acik() || son == null) return false;
        JSONArray o = son.optJSONArray("o");
        for (String ad : new String[]{"Kapat", "İptal", "Vazgeç", "Hayır", "Cancel", "Tamam"})
            for (int i = 0; o != null && i < o.length(); i++) {
                JSONObject e = o.optJSONObject(i);
                if ("dugme".equals(e.optString("t")) && ad.equalsIgnoreCase(e.optString("m").trim())) { gonder("FT " + no + " " + e.optInt("id")); return true; }
            }
        return true;
    }

    void kapat() {
        if (!acik()) return;
        final FrameLayout p = perde;
        no = -1;
        imza = "";
        son = null;
        panel.animate().translationY(panel.getHeight()).setDuration(200).setInterpolator(new DecelerateInterpolator()).start();
        p.animate().alpha(0f).setDuration(200).withEndAction(() -> { if (p.getParent() != null) kok.removeView(p); }).start();
        android.view.inputmethod.InputMethodManager imm = (android.view.inputmethod.InputMethodManager) a.getSystemService(Activity.INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(kok.getWindowToken(), 0);
    }

    /** FORM json geldi. */
    void goster(String json) {
        JSONObject j;
        try { j = new JSONObject(json); } catch (Exception e) { return; }
        int yeniNo = j.optInt("no");
        String yeniImza = imzaHesapla(j);
        son = j;
        if (acik() && yeniNo == no && yeniImza.equals(imza)) { guncelle(j); return; }
        no = yeniNo;
        imza = yeniImza;
        kur(j);
    }

    private static String imzaHesapla(JSONObject j) {
        StringBuilder sb = new StringBuilder(j.optString("b"));
        JSONArray o = j.optJSONArray("o");
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            sb.append('|').append(e.optString("t")).append(e.optInt("id", -1));
            if ("dugme".equals(e.optString("t")) || "radyo".equals(e.optString("t")) || "kutu".equals(e.optString("t"))) sb.append(e.optString("m"));
        }
        return sb.toString();
    }

    // ------------------------------------------------------------------------------------ kurulum
    private void kur(JSONObject j) {
        boolean yeniPerde = !acik();
        if (yeniPerde) {
            perde = new FrameLayout(a);
            perde.setBackgroundColor(0x66000000);
            perde.setClickable(true);
            panel = new LinearLayout(a);
            panel.setOrientation(LinearLayout.VERTICAL);
            panel.setBackground(Tasarim.ustYuvarlak(Color.WHITE, dp(26)));
            panel.setClickable(true);
            if (Build.VERSION.SDK_INT >= 21) panel.setElevation(dp(20));
            View tutamak = new View(a);
            tutamak.setBackground(Tasarim.yuvarlak(Tasarim.CIZGI, dp(3)));
            LinearLayout.LayoutParams tl = new LinearLayout.LayoutParams(dp(40), dp(5));
            tl.gravity = Gravity.CENTER_HORIZONTAL;
            tl.setMargins(0, dp(10), 0, dp(4));
            panel.addView(tutamak, tl);
            LinearLayout bas = new LinearLayout(a);
            bas.setOrientation(LinearLayout.HORIZONTAL);
            bas.setGravity(Gravity.CENTER_VERTICAL);
            bas.setPadding(dp(22), dp(6), dp(12), dp(6));
            baslikTv = yazi("", 20, Tasarim.METIN, true);
            bas.addView(baslikTv, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
            TextView orj = yazi("Orijinal", 13, Tasarim.VURGU, true);
            orj.setPadding(dp(12), dp(8), dp(12), dp(8));
            orj.setBackground(Tasarim.dalga(Tasarim.yuvarlak(Tasarim.VURGU_ACIK, dp(16)), dp(16)));
            orj.setOnClickListener(v -> din.orijinaliGoster());
            bas.addView(orj);
            panel.addView(bas);
            ScrollView sv = new ScrollView(a);
            sv.setVerticalScrollBarEnabled(false);
            icerik = new LinearLayout(a);
            icerik.setOrientation(LinearLayout.VERTICAL);
            icerik.setPadding(dp(22), dp(4), dp(22), dp(8));
            sv.addView(icerik);
            panel.addView(sv, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
            HorizontalScrollView dh = new HorizontalScrollView(a);
            dh.setHorizontalScrollBarEnabled(false);
            dh.setFillViewport(true);
            dugmeler = new LinearLayout(a);
            dugmeler.setOrientation(LinearLayout.HORIZONTAL);
            dugmeler.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
            dugmeler.setPadding(dp(16), dp(10), dp(16), dp(18));
            dh.addView(dugmeler, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
            panel.addView(dh);
            FrameLayout.LayoutParams pl = new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
            perde.addView(panel, pl);
            kok.addView(perde, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        }
        alanlar.clear(); kutular.clear(); radyolar.clear(); listeler.clear(); metinler.clear();
        icerik.removeAllViews();
        dugmeler.removeAllViews();
        String b = j.optString("b");
        baslikTv.setText(b.trim().isEmpty() ? "UYAP Editör" : b);
        JSONArray o = j.optJSONArray("o");
        String sonEtiket = "";
        LinearLayout radyoSatiri = null;
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            String t = e.optString("t");
            if (!"radyo".equals(t)) radyoSatiri = null;
            switch (t) {
                case "baslik": {
                    TextView v = yazi(e.optString("m").trim().toUpperCase(new Locale("tr", "TR")), 12, Tasarim.IKINCIL, true);
                    v.setLetterSpacing(0.06f);
                    v.setPadding(0, dp(14), 0, dp(4));
                    icerik.addView(v);
                    metinler.add(v);
                    break;
                }
                case "etiket": {
                    String m = e.optString("m");
                    sonEtiket = m;
                    TextView v = yazi(m.replaceAll("\\s*:\\s*$", ""), 16, Tasarim.METIN, false);
                    v.setPadding(0, dp(10), 0, dp(4));
                    if (m.toUpperCase(new Locale("tr", "TR")).contains("DOĞRULAMA KODU")) { v.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18); v.setTypeface(Typeface.DEFAULT_BOLD); v.setTextColor(Tasarim.VURGU); }
                    icerik.addView(v);
                    metinler.add(v);
                    break;
                }
                case "metin": {
                    TextView v = yazi(e.optString("m"), 13, Tasarim.METIN, false);
                    v.setTypeface(Typeface.MONOSPACE);
                    v.setTextIsSelectable(true);
                    v.setPadding(dp(12), dp(10), dp(12), dp(10));
                    v.setBackground(Tasarim.yuvarlak(Tasarim.ZEMIN, dp(10)));
                    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                    lp.setMargins(0, dp(6), 0, dp(6));
                    icerik.addView(v, lp);
                    metinler.add(v);
                    break;
                }
                case "alan": case "sifre": icerik.addView(alan(e, sonEtiket, "sifre".equals(t))); break;
                case "radyo": {
                    if (radyoSatiri == null) {
                        radyoSatiri = new LinearLayout(a);
                        radyoSatiri.setOrientation(LinearLayout.HORIZONTAL);
                        HorizontalScrollView h = new HorizontalScrollView(a);
                        h.setHorizontalScrollBarEnabled(false);
                        h.addView(radyoSatiri);
                        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                        lp.setMargins(0, dp(4), 0, dp(4));
                        icerik.addView(h, lp);
                    }
                    radyoSatiri.addView(radyo(e));
                    break;
                }
                case "kutu": {
                    CheckBox c = new CheckBox(a);
                    c.setText(e.optString("m"));
                    c.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
                    c.setChecked(e.optInt("s") == 1);
                    c.setEnabled(e.optInt("e", 1) == 1);
                    c.setPadding(dp(4), dp(10), 0, dp(10));
                    final int id = e.optInt("id");
                    c.setOnClickListener(v -> gonder("FT " + no + " " + id));
                    kutular.put(id, c);
                    icerik.addView(c);
                    break;
                }
                case "secim": case "liste": case "agac": case "tablo": {
                    LinearLayout l = new LinearLayout(a);
                    l.setOrientation(LinearLayout.VERTICAL);
                    l.setBackground(Tasarim.yuvarlak(Tasarim.ZEMIN, dp(14)));
                    l.setPadding(dp(4), dp(4), dp(4), dp(4));
                    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                    lp.setMargins(0, dp(6), 0, dp(6));
                    icerik.addView(l, lp);
                    listeler.put(e.optInt("id"), l);
                    listeDoldur(l, e);
                    break;
                }
                case "dugme": dugmeler.addView(dugme(e)); break;
                default: break;
            }
        }
        if (yeniPerde) {
            perde.setAlpha(0f);
            perde.animate().alpha(1f).setDuration(200).start();
            panel.setTranslationY(dp(400));
            panel.animate().translationY(0).setDuration(320).setInterpolator(Build.VERSION.SDK_INT >= 21 ? new PathInterpolator(0.2f, 0f, 0f, 1f) : new DecelerateInterpolator()).start();
        }
        // en fazla ekranın %80'i
        panel.post(() -> {
            int en = Math.round(kok.getHeight() * 0.82f);
            ViewGroup.LayoutParams lp = panel.getLayoutParams();
            if (panel.getHeight() > en && lp.height != en) { lp.height = en; panel.setLayoutParams(lp); }
        });
        // ilk boş alana odaklan
        for (EditText et : alanlar.values()) if (et.getText().length() == 0 && et.isEnabled()) { et.requestFocus(); break; }
    }

    /** Aynı pencere, yalnızca değerler değişti: alanlar/klavye korunur. */
    private void guncelle(JSONObject j) {
        JSONArray o = j.optJSONArray("o");
        int m = 0;
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            String t = e.optString("t");
            int id = e.optInt("id", -1);
            switch (t) {
                case "baslik": case "etiket": case "metin": {
                    if (m < metinler.size()) {
                        String yeni = "baslik".equals(t) ? e.optString("m").trim().toUpperCase(new Locale("tr", "TR"))
                                : "etiket".equals(t) ? e.optString("m").replaceAll("\\s*:\\s*$", "") : e.optString("m");
                        TextView v = metinler.get(m);
                        if (!yeni.contentEquals(v.getText())) {
                            v.setText(yeni);
                            v.setAlpha(0.3f);
                            v.animate().alpha(1f).setDuration(250).start();
                        }
                    }
                    m++;
                    break;
                }
                case "alan": case "sifre": {
                    EditText et = alanlar.get(id);
                    if (et != null && !et.hasFocus() && !e.optString("v").contentEquals(et.getText())) { et.setTag("dis"); et.setText(e.optString("v")); et.setTag(null); }
                    break;
                }
                case "kutu": { CheckBox c = kutular.get(id); if (c != null) c.setChecked(e.optInt("s") == 1); break; }
                case "radyo": { View r = radyolar.get(id); if (r != null) radyoDurum((TextView) r, e.optInt("s") == 1); break; }
                case "secim": case "liste": case "agac": case "tablo": { LinearLayout l = listeler.get(id); if (l != null) listeDoldur(l, e); break; }
                default: break;
            }
        }
    }

    // ------------------------------------------------------------------------------------ parçalar
    private View alan(JSONObject e, String etiket, boolean sifre) {
        final int id = e.optInt("id");
        final EditText et = new EditText(a);
        et.setText(e.optString("v"));
        et.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        et.setSingleLine(e.optInt("cok") != 1);
        et.setPadding(dp(16), dp(14), dp(16), dp(14));
        GradientDrawable g = Tasarim.yuvarlak(Color.WHITE, dp(12));
        g.setStroke(dp(1), Tasarim.CIZGI);
        et.setBackground(g);
        String k = etiket.toUpperCase(new Locale("tr", "TR"));
        boolean sayi = k.contains("NUMARA") || k.contains("GSM") || k.contains("TC ") || k.contains("KİMLİK") || k.contains("PIN") || k.contains("ŞİFRE") || k.contains("KOD");
        int tur = sayi ? InputType.TYPE_CLASS_NUMBER : InputType.TYPE_CLASS_TEXT;
        if (sifre) tur |= sayi ? InputType.TYPE_NUMBER_VARIATION_PASSWORD : InputType.TYPE_TEXT_VARIATION_PASSWORD;
        if (k.contains("GSM")) tur = InputType.TYPE_CLASS_PHONE;
        et.setInputType(tur);
        if (k.contains("05XX")) et.setHint("05XXXXXXXXX");
        final Runnable[] bekleyen = {null};
        et.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int st, int c, int af) { }
            @Override public void onTextChanged(CharSequence s, int st, int b, int c) { }
            @Override public void afterTextChanged(Editable s) {
                if ("dis".equals(et.getTag())) return;
                if (bekleyen[0] != null) et.removeCallbacks(bekleyen[0]);
                final String v = s.toString();
                bekleyen[0] = () -> gonder("FA " + no + " " + id + " " + Base64.encodeToString(v.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
                et.postDelayed(bekleyen[0], 180);
            }
        });
        alanlar.put(id, et);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(2), 0, dp(6));
        et.setLayoutParams(lp);
        return et;
    }

    private View radyo(JSONObject e) {
        final int id = e.optInt("id");
        TextView t = yazi(e.optString("m"), 15, Tasarim.METIN, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(18), dp(12), dp(18), dp(12));
        radyoDurum(t, e.optInt("s") == 1);
        t.setEnabled(e.optInt("e", 1) == 1);
        t.setOnClickListener(v -> {
            for (View r : radyolar.values()) if (r.getParent() == v.getParent()) radyoDurum((TextView) r, r == v);
            gonder("FT " + no + " " + id);
        });
        radyolar.put(id, t);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, dp(8), 0);
        t.setLayoutParams(lp);
        return t;
    }

    private void radyoDurum(TextView t, boolean s) {
        GradientDrawable g = Tasarim.yuvarlak(s ? Tasarim.VURGU_ACIK : Color.WHITE, dp(22));
        g.setStroke(dp(s ? 2 : 1), s ? Tasarim.VURGU : Tasarim.CIZGI);
        t.setBackground(Tasarim.dalga(g, dp(22)));
        t.setTextColor(s ? Tasarim.VURGU : Tasarim.METIN);
    }

    private void listeDoldur(LinearLayout l, JSONObject e) {
        l.removeAllViews();
        final int id = e.optInt("id");
        final String t = e.optString("t");
        int sec = e.optInt("s", -1);
        JSONArray s = e.optJSONArray("l");
        if ("tablo".equals(t)) {
            JSONArray b = e.optJSONArray("b");
            StringBuilder sb = new StringBuilder();
            for (int i = 0; b != null && i < b.length(); i++) { if (i > 0) sb.append(" · "); sb.append(b.optString(i)); }
            if (sb.length() > 0) { TextView h = yazi(sb.toString(), 12, Tasarim.IKINCIL, true); h.setPadding(dp(12), dp(8), dp(12), dp(4)); l.addView(h); }
        }
        for (int i = 0; s != null && i < s.length(); i++) {
            final int sira = i;
            String m;
            int girinti = 0;
            if ("agac".equals(t)) { JSONArray r = s.optJSONArray(i); girinti = r.optInt(0); m = r.optString(1); }
            else if ("tablo".equals(t)) {
                JSONArray r = s.optJSONArray(i);
                StringBuilder sb = new StringBuilder();
                for (int k = 0; r != null && k < r.length(); k++) { if (r.optString(k).trim().isEmpty()) continue; if (sb.length() > 0) sb.append("\n"); sb.append(r.optString(k)); }
                m = sb.toString();
            } else m = s.optString(i);
            boolean bu = i == sec;
            TextView v = yazi(m, 15, bu ? Tasarim.VURGU : Tasarim.METIN, bu);
            v.setPadding(dp(14 + girinti * 18), dp(14), dp(14), dp(14));
            v.setBackground(Tasarim.dalga(bu ? Tasarim.yuvarlak(Tasarim.SECILI, dp(10)) : null, dp(10)));
            final long[] son = {0};
            v.setOnClickListener(x -> {
                long simdi = System.currentTimeMillis();
                boolean cift = simdi - son[0] < 400;
                son[0] = simdi;
                gonder("FS " + no + " " + id + " " + sira + (cift ? " 2" : ""));
            });
            l.addView(v);
        }
    }

    private View dugme(JSONObject e) {
        final int id = e.optInt("id");
        String m = e.optString("m").trim();
        String k = m.toLowerCase(new Locale("tr", "TR"));
        boolean ana = k.equals("imzala") || k.equals("tamam") || k.equals("evet") || k.equals("seç") || k.equals("onayla") || k.equals("gönder")
                || k.equals("ok") || k.equals("open") || k.equals("aç") || k.equals("kaydet") || k.equals("devam");
        TextView t = yazi(m, 16, ana ? Color.WHITE : Tasarim.VURGU, true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(22), dp(13), dp(22), dp(13));
        GradientDrawable g = Tasarim.yuvarlak(ana ? Tasarim.VURGU : Color.WHITE, dp(24));
        if (!ana) g.setStroke(dp(1), Tasarim.CIZGI);
        t.setBackground(Tasarim.dalga(g, dp(24)));
        boolean etkin = e.optInt("e", 1) == 1;
        t.setAlpha(etkin ? 1f : 0.4f);
        if (etkin) t.setOnClickListener(v -> {
            v.animate().scaleX(0.94f).scaleY(0.94f).setDuration(70).withEndAction(() -> v.animate().scaleX(1f).scaleY(1f).setDuration(120).start()).start();
            // açık alanların son hâli önce gitsin
            for (Map.Entry<Integer, EditText> a2 : alanlar.entrySet())
                gonder("FA " + no + " " + a2.getKey() + " " + Base64.encodeToString(a2.getValue().getText().toString().getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            gonder("FT " + no + " " + id);
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(dp(8), 0, 0, 0);
        t.setLayoutParams(lp);
        return t;
    }

    private void gonder(String k) { UyapMobilServisi.gonder(k); }

    private TextView yazi(String m, int sp, int renk, boolean kalin) {
        TextView t = new TextView(a);
        t.setText(m);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(renk);
        t.setTypeface(Typeface.create(kalin ? "sans-serif-medium" : "sans-serif", Typeface.NORMAL));
        return t;
    }

    private int dp(float v) { return Tasarim.dp(a, v); }
}
