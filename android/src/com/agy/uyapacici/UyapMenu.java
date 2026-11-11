package com.agy.uyapacici;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.text.InputType;
import android.util.Base64;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * UYAP Editör — dokunmatik menüler (3.21.0).
 *
 * Resmi editörün şerit menüsü telefonda çok küçük. Köprü (Kopru.menuGonder) editörün gizli klasik menü çubuğundaki
 * TÜM komutları (Dosya, Giriş, Düzenle, Ekle, Biçim, Araçlar, Görünüm, Modernizasyon) simgeleriyle birlikte gönderir;
 * burada iki dokunmatik arayüzde gösterilir:
 *   ☰  soldan açılan çekmece: büyük satırlar, bölümler açılıp kapanır, uygulama ayarları en altta
 *   Aa biçim çubuğu: stil / yazı tipi / boyut ve Giriş araç çubuğunun düğmeleri (K, T, A, hizalama, liste…) büyük
 * Komutlar editörün kendi menü öğelerine tıklanarak çalıştırılır (MC/MS/MT), yani davranış birebir aynıdır.
 * Şerit menü isteğe göre gizlenir (SG), belgeye ~150 px daha yer kalır.
 */
final class UyapMenu {
    interface Uygulama {
        String[] uygulamaKomutlari();
        void uygulamaKomutu(int sira);
    }

    private final Activity a;
    private final FrameLayout alan;
    private final LinearLayout bicimKutusu;
    private final Uygulama uyg;
    private final SharedPreferences ayar;
    private final Map<String, Bitmap> simgeler = new HashMap<>();
    private final Set<String> acikBolumler = new HashSet<>();

    private FrameLayout cekmece;
    private LinearLayout icerik;
    private boolean cekmeceBekliyor;
    private JSONObject son;
    private int bosYanit;

    UyapMenu(Activity a, FrameLayout alan, LinearLayout bicimKutusu, SharedPreferences ayar, Uygulama uyg) {
        this.a = a;
        this.alan = alan;
        this.bicimKutusu = bicimKutusu;
        this.ayar = ayar;
        this.uyg = uyg;
        String k = ayar.getString("menu_acik", "Dosya");
        for (String s : k.split("\n")) if (!s.isEmpty()) acikBolumler.add(s);
        bicimKutusu.setVisibility(bicimAcik() ? View.VISIBLE : View.GONE);
    }

    // ------------------------------------------------------------------------------------ durum
    boolean seritGizli() { return ayar.getBoolean("serit_gizli", true); }
    boolean bicimAcik() { return ayar.getBoolean("bicim_cubugu", true); }

    /** Editör bağlanınca: şerit tercihini uygula, biçim çubuğu açıksa menüyü iste. */
    void hazir() {
        UyapMobilServisi.gonder("SG " + (seritGizli() ? "0" : "1"));
        if (bicimAcik()) iste(900);
    }

    void seritDegistir() {
        boolean gizle = !seritGizli();
        ayar.edit().putBoolean("serit_gizli", gizle).apply();
        UyapMobilServisi.gonder("SG " + (gizle ? "0" : "1"));
    }

    void bicimDegistir() {
        boolean ac = !bicimAcik();
        ayar.edit().putBoolean("bicim_cubugu", ac).apply();
        bicimKutusu.setVisibility(ac ? View.VISIBLE : View.GONE);
        if (ac) iste(0);
    }

    private void iste(long gecikme) {
        alan.postDelayed(() -> UyapMobilServisi.gonder("MN"), gecikme);
    }

    /** Köprüden menü geldi (ana iş parçacığı). */
    void geldi(String json) {
        JSONObject j;
        try { j = new JSONObject(json); } catch (Exception e) { Tani.hata("uyapmobil", "menü json", e); return; }
        JSONArray m = j.optJSONArray("m");
        if (m == null || m.length() == 0) {
            // editörün ana penceresi henüz kurulmadı (telefonda açılış uzun sürer): birazdan yeniden sor
            if (bosYanit++ < 60) iste(2000);
            return;
        }
        bosYanit = 0;
        son = j;
        if (bicimAcik()) bicimCiz();
        if (cekmece != null && (cekmeceBekliyor || cekmece.getParent() != null)) { cekmeceBekliyor = false; cekmeceCiz(); }
    }

    // ------------------------------------------------------------------------------------ çekmece (☰)
    boolean acikMi() { return cekmece != null && cekmece.getParent() != null; }

    void ac() {
        if (cekmece == null) {
            cekmece = new FrameLayout(a);
            cekmece.setBackgroundColor(0x88000000);
            cekmece.setOnClickListener(v -> kapat());
            ScrollView sv = new ScrollView(a);
            sv.setBackgroundColor(Color.rgb(250, 250, 250));
            sv.setClickable(true);
            icerik = new LinearLayout(a);
            icerik.setOrientation(LinearLayout.VERTICAL);
            sv.addView(icerik);
            int gen = Math.min(dp(380), Math.round(a.getResources().getDisplayMetrics().widthPixels * 0.88f));
            cekmece.addView(sv, new FrameLayout.LayoutParams(gen, ViewGroup.LayoutParams.MATCH_PARENT, Gravity.START));
        }
        if (cekmece.getParent() == null) alan.addView(cekmece, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        cekmeceBekliyor = true;
        cekmeceCiz();               // son bilinen menü (yoksa yalnızca uygulama bölümü) hemen; güncel hâli gelince yenilenir
        UyapMobilServisi.gonder("MN");
    }

    void kapat() {
        if (cekmece != null && cekmece.getParent() != null) alan.removeView(cekmece);
    }

    private void cekmeceCiz() {
        icerik.removeAllViews();
        // başlık
        LinearLayout bas = new LinearLayout(a);
        bas.setOrientation(LinearLayout.HORIZONTAL);
        bas.setBackgroundColor(Color.rgb(46, 52, 64));
        bas.setGravity(Gravity.CENTER_VERTICAL);
        bas.setPadding(dp(16), dp(10), dp(8), dp(10));
        TextView t = yazi("UYAP Editör", 19, Color.WHITE, true);
        bas.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        TextView x = yazi("✕", 22, Color.WHITE, true);
        x.setPadding(dp(14), dp(4), dp(14), dp(4));
        x.setOnClickListener(v -> kapat());
        bas.addView(x);
        icerik.addView(bas);
        // hızlı seçenekler
        LinearLayout hiz = new LinearLayout(a);
        hiz.setOrientation(LinearLayout.HORIZONTAL);
        hiz.setPadding(dp(8), dp(8), dp(8), dp(4));
        hiz.addView(cip(seritGizli() ? "Şeridi göster" : "Şeridi gizle", v -> { seritDegistir(); cekmeceCiz(); }), agirlik());
        hiz.addView(cip(bicimAcik() ? "Aa çubuğunu gizle" : "Aa biçim çubuğu", v -> { bicimDegistir(); cekmeceCiz(); }), agirlik());
        icerik.addView(hiz);
        if (son == null) icerik.addView(satirYazi("Editör menüsü yükleniyor…", Color.GRAY));
        else {
            JSONArray m = son.optJSONArray("m");
            for (int i = 0; m != null && i < m.length(); i++) {
                JSONObject b = m.optJSONObject(i);
                bolum(icerik, b.optString("t"), b.optJSONArray("o"), 0);
            }
        }
        // uygulama ayarları
        LinearLayout ub = bolumBasligi(icerik, "Uygulama (telefon)", 0);
        if (ub != null) {
            String[] k = uyg.uygulamaKomutlari();
            for (int i = 0; i < k.length; i++) {
                final int s = i;
                ub.addView(oge(null, k[i], true, -1, v -> { kapat(); uyg.uygulamaKomutu(s); }));
            }
        }
        View bos = new View(a);
        icerik.addView(bos, new LinearLayout.LayoutParams(1, dp(40)));
    }

    /** Bölüm başlığı; bölüm açıksa öğelerin ekleneceği kutuyu döndürür (kapalıysa null). */
    private LinearLayout bolumBasligi(LinearLayout ust, String ad, int girinti) {
        final boolean acik = acikBolumler.contains(ad);
        TextView h = yazi((acik ? "▾  " : "▸  ") + ad, girinti > 0 ? 16 : 17, Color.rgb(32, 33, 36), true);
        h.setPadding(dp(16 + girinti), dp(14), dp(16), dp(14));
        h.setBackgroundColor(girinti > 0 ? Color.rgb(244, 244, 244) : Color.rgb(236, 239, 244));
        h.setOnClickListener(v -> {
            if (acik) acikBolumler.remove(ad); else acikBolumler.add(ad);
            StringBuilder sb = new StringBuilder();
            for (String s : acikBolumler) sb.append(s).append('\n');
            ayar.edit().putString("menu_acik", sb.toString()).apply();
            cekmeceCiz();
        });
        ust.addView(h);
        View cizgi = new View(a);
        cizgi.setBackgroundColor(Color.rgb(220, 220, 220));
        ust.addView(cizgi, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1));
        if (!acik) return null;
        LinearLayout k = new LinearLayout(a);
        k.setOrientation(LinearLayout.VERTICAL);
        ust.addView(k);
        return k;
    }

    private void bolum(LinearLayout ust, String ad, JSONArray o, int girinti) {
        LinearLayout k = bolumBasligi(ust, ad, girinti);
        if (k == null || o == null) return;
        int combo = 0;
        for (int i = 0; i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            String tur = e.optString("k");
            switch (tur) {
                case "i": {
                    final int id = e.optInt("id");
                    k.addView(oge(e.optString("ic"), e.optString("t"), e.optInt("e") == 1, e.optInt("s", -1),
                            v -> { kapat(); UyapMobilServisi.gonder("MC " + id); }));
                    break;
                }
                case "g": bolum(k, e.optString("t"), e.optJSONArray("o"), girinti + 16); break;
                case "b": {
                    JSONArray d = e.optJSONArray("o");
                    if (d == null || d.length() == 0) break;
                    LinearLayout izgara = new LinearLayout(a);
                    izgara.setOrientation(LinearLayout.VERTICAL);
                    izgara.setPadding(dp(8), dp(4), dp(8), dp(4));
                    LinearLayout satir = null;
                    int sutun = 0, enFazla = Math.max(4, (Math.min(dp(380), Math.round(a.getResources().getDisplayMetrics().widthPixels * 0.88f)) - dp(16)) / dp(52));
                    for (int j = 0; j < d.length(); j++) {
                        JSONObject b = d.optJSONObject(j);
                        View v;
                        if ("c".equals(b.optString("k"))) {
                            v = comboDugmesi(b, comboAdi(combo++), false);
                            izgara.addView(v, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(50)));
                            satir = null;
                            continue;
                        }
                        if (satir == null || sutun >= enFazla) {
                            satir = new LinearLayout(a);
                            satir.setOrientation(LinearLayout.HORIZONTAL);
                            izgara.addView(satir);
                            sutun = 0;
                        }
                        satir.addView(simgeDugmesi(b, true), new LinearLayout.LayoutParams(dp(50), dp(50)));
                        sutun++;
                    }
                    k.addView(izgara);
                    break;
                }
                case "-": {
                    View c = new View(a);
                    c.setBackgroundColor(Color.rgb(230, 230, 230));
                    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 1);
                    lp.setMargins(dp(56), dp(2), 0, dp(2));
                    k.addView(c, lp);
                    break;
                }
                default: break;
            }
        }
    }

    private static String comboAdi(int sira) {
        switch (sira) { case 0: return "Stil"; case 1: return "Yazı tipi"; case 2: return "Boyut"; default: return "Seç"; }
    }

    // ------------------------------------------------------------------------------------ Aa biçim çubuğu
    private void bicimCiz() {
        bicimKutusu.removeAllViews();
        if (son == null) return;
        HorizontalScrollView hs = new HorizontalScrollView(a);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout s = new LinearLayout(a);
        s.setOrientation(LinearLayout.HORIZONTAL);
        s.setGravity(Gravity.CENTER_VERTICAL);
        s.setPadding(dp(4), 0, dp(4), 0);
        hs.addView(s);
        JSONArray m = son.optJSONArray("m");
        JSONObject giris = null;
        for (int i = 0; m != null && i < m.length(); i++)
            if ("Giriş".equals(m.optJSONObject(i).optString("t"))) giris = m.optJSONObject(i);
        if (giris == null && m != null && m.length() > 1) giris = m.optJSONObject(1);
        if (giris == null) return;
        JSONArray o = giris.optJSONArray("o");
        int combo = 0;
        for (int i = 0; o != null && i < o.length(); i++) {
            JSONObject e = o.optJSONObject(i);
            if (!"b".equals(e.optString("k"))) continue;
            JSONArray d = e.optJSONArray("o");
            for (int j = 0; d != null && j < d.length(); j++) {
                JSONObject b = d.optJSONObject(j);
                if ("c".equals(b.optString("k"))) {
                    LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(40));
                    lp.setMargins(dp(3), 0, dp(3), 0);
                    s.addView(comboDugmesi(b, comboAdi(combo++), true), lp);
                } else s.addView(simgeDugmesi(b, false), new LinearLayout.LayoutParams(dp(46), dp(46)));
            }
            View ayrac = new View(a);
            ayrac.setBackgroundColor(Color.rgb(80, 86, 100));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(1, dp(28));
            lp.setMargins(dp(4), 0, dp(4), 0);
            s.addView(ayrac, lp);
        }
        bicimKutusu.addView(hs, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(50)));
    }

    // ------------------------------------------------------------------------------------ parçalar
    private View simgeDugmesi(JSONObject b, final boolean cekmecede) {
        final int id = b.optInt("id");
        boolean etkin = b.optInt("e") == 1, secili = b.optInt("s", -1) == 1;
        ImageView iv = new ImageView(a);
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        int p = dp(cekmecede ? 9 : 8);
        iv.setPadding(p, p, p, p);
        Bitmap bm = simge(b.optString("ic"));
        if (bm != null) iv.setImageBitmap(bm);
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(8));
        g.setColor(secili ? Color.rgb(187, 222, 251) : (cekmecede ? Color.TRANSPARENT : Color.rgb(236, 239, 244)));
        iv.setBackground(g);
        iv.setAlpha(etkin ? 1f : 0.35f);
        String ip = b.optString("ip");
        if (!ip.isEmpty()) iv.setContentDescription(ip);
        if (etkin) iv.setOnClickListener(v -> {
            if (cekmecede) kapat();
            UyapMobilServisi.gonder("MC " + id);
            if (bicimAcik()) iste(350);   // seçili durumları (K, T, hizalama) güncelle
        });
        if (!cekmecede) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(46), dp(46));
            lp.setMargins(dp(2), 0, dp(2), 0);
            iv.setLayoutParams(lp);
        }
        return iv;
    }

    private View comboDugmesi(JSONObject b, final String ad, boolean kucuk) {
        final int id = b.optInt("id");
        final String deger = b.optString("t");
        final JSONArray l = b.optJSONArray("l");
        final boolean duzenlenir = b.optInt("ed") == 1;
        TextView t = yazi(kucuk ? deger + " ▾" : ad + ":  " + deger + "  ▾", kucuk ? 15 : 16, Color.rgb(32, 33, 36), false);
        t.setGravity(Gravity.CENTER_VERTICAL);
        t.setPadding(dp(12), 0, dp(12), 0);
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(8));
        g.setColor(Color.rgb(236, 239, 244));
        g.setStroke(1, Color.rgb(200, 204, 212));
        t.setBackground(g);
        t.setOnClickListener(v -> {
            int n = l == null ? 0 : l.length();
            String[] ogeler = new String[n + (duzenlenir ? 1 : 0)];
            for (int i = 0; i < n; i++) ogeler[i] = l.optString(i);
            if (duzenlenir) ogeler[n] = "Başka bir değer yaz…";
            new AlertDialog.Builder(a).setTitle(ad).setItems(ogeler, (d, w) -> {
                if (w < n) { kapat(); UyapMobilServisi.gonder("MS " + id + " " + w); if (bicimAcik()) iste(350); }
                else degerYaz(id, ad, deger);
            }).show();
        });
        return t;
    }

    private void degerYaz(final int id, String ad, String deger) {
        final EditText e = new EditText(a);
        e.setText(deger);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        e.setSelectAllOnFocus(true);
        new AlertDialog.Builder(a).setTitle(ad).setView(e).setPositiveButton("Tamam", (d, w) -> {
            kapat();
            String v = e.getText().toString().trim();
            if (!v.isEmpty()) UyapMobilServisi.gonder("MT " + id + " " + Base64.encodeToString(v.getBytes(StandardCharsets.UTF_8), Base64.NO_WRAP));
            if (bicimAcik()) iste(350);
        }).setNegativeButton("Vazgeç", null).show();
    }

    private View oge(String ic, String metin, boolean etkin, int secili, View.OnClickListener l) {
        LinearLayout r = new LinearLayout(a);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.CENTER_VERTICAL);
        r.setPadding(dp(16), 0, dp(16), 0);
        r.setMinimumHeight(dp(52));
        ImageView iv = new ImageView(a);
        Bitmap bm = ic == null ? null : simge(ic);
        if (bm != null) iv.setImageBitmap(bm);
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        r.addView(iv, new LinearLayout.LayoutParams(dp(28), dp(28)));
        String on = secili == 1 ? "☑  " : secili == 0 ? "☐  " : "";
        TextView t = yazi(on + metin, 17, Color.rgb(32, 33, 36), false);
        t.setPadding(dp(16), dp(10), 0, dp(10));
        r.addView(t, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        r.setAlpha(etkin ? 1f : 0.38f);
        if (etkin) {
            r.setOnClickListener(l);
            TypedValue tv = new TypedValue();
            if (a.getTheme().resolveAttribute(android.R.attr.selectableItemBackground, tv, true)) r.setBackgroundResource(tv.resourceId);
        }
        return r;
    }

    private TextView cip(String metin, View.OnClickListener l) {
        TextView t = yazi(metin, 14, Color.rgb(32, 33, 36), true);
        t.setGravity(Gravity.CENTER);
        t.setPadding(dp(8), dp(10), dp(8), dp(10));
        GradientDrawable g = new GradientDrawable();
        g.setCornerRadius(dp(20));
        g.setColor(Color.rgb(227, 236, 250));
        t.setBackground(g);
        t.setOnClickListener(l);
        return t;
    }

    private LinearLayout.LayoutParams agirlik() {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        lp.setMargins(dp(4), 0, dp(4), 0);
        return lp;
    }

    private TextView satirYazi(String m, int renk) {
        TextView t = yazi(m, 15, renk, false);
        t.setPadding(dp(16), dp(14), dp(16), dp(14));
        return t;
    }

    private TextView yazi(String m, int sp, int renk, boolean kalin) {
        TextView t = new TextView(a);
        t.setText(m);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(renk);
        if (kalin) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Bitmap simge(String b64) {
        if (b64 == null || b64.isEmpty()) return null;
        Bitmap b = simgeler.get(b64);
        if (b == null && !simgeler.containsKey(b64)) {
            try {
                byte[] d = Base64.decode(b64, Base64.DEFAULT);
                b = BitmapFactory.decodeByteArray(d, 0, d.length);
            } catch (Exception ignored) { }
            if (simgeler.size() > 400) simgeler.clear();
            simgeler.put(b64, b);
        }
        return b;
    }

    private int dp(int v) { return Math.round(v * a.getResources().getDisplayMetrics().density); }
}
