package com.agy.uyapacici;

import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;

/**
 * UYAP Editör mobil arayüzü — renkler, köşeli/yuvarlak zeminler, dalga (ripple) efektleri ve çizgi simgeler.
 * Simgeler vektör olarak çizilir (her yoğunlukta keskin; Google Dokümanlar mobil görünümüne benzer ince çizgi stili).
 */
final class Tasarim {
    private Tasarim() { }

    static final int ZEMIN = Color.rgb(248, 249, 250);
    static final int YUZEY = Color.WHITE;
    static final int METIN = Color.rgb(32, 33, 36);
    static final int IKINCIL = Color.rgb(95, 99, 104);
    static final int CIZGI = Color.rgb(218, 220, 224);
    static final int VURGU = Color.rgb(26, 115, 232);          // Google mavisi
    static final int VURGU_ACIK = Color.rgb(232, 240, 254);
    static final int SECILI = Color.rgb(210, 227, 252);
    static final int CAM = 0xD9FFFFFF;                         // bulanık zeminin üstündeki yarı saydam beyaz
    static final int CAM_ESKI = 0xF5FFFFFF;                    // bulanıklık desteklenmeyen cihazlar

    static int dp(Context c, float v) { return Math.round(v * c.getResources().getDisplayMetrics().density); }

    static GradientDrawable yuvarlak(int renk, float yaricap) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(renk);
        g.setCornerRadius(yaricap);
        return g;
    }

    static GradientDrawable ustYuvarlak(int renk, float yaricap) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(renk);
        g.setCornerRadii(new float[]{yaricap, yaricap, yaricap, yaricap, 0, 0, 0, 0});
        return g;
    }

    /** Dokununca yayılan dalga efekti; zemin null ise yalnızca dalga (yuvarlak maske). */
    static Drawable dalga(Drawable zemin, float yaricap) {
        Drawable maske = yuvarlak(Color.WHITE, yaricap);
        return new RippleDrawable(ColorStateList.valueOf(0x22000000), zemin, maske);
    }

    // ------------------------------------------------------------------------------------ simgeler
    enum S { MENU, GERI_AL, YINELE, DAHA, KLAVYE, BICIM, KALIN, ITALIK, ALTI, USTU_CIZILI, RENK, VURGULA,
        SOL, ORTA, SAG, IKI_YANA, MADDE, NUMARA, GIRINTI_AZ, GIRINTI_COK, TUSLAR, MOBIL, MASAUSTU, KAPAT, GERI,
        ARTI, EKSI, ALT_SIMGE, UST_SIMGE, TEMIZLE, SATIR_ARALIGI, KAYDET, AC, ARA, ILERI, KAYDIR, SECIM }

    static Drawable simge(Context c, S s, int renk) { return new Cizim(c, s, renk); }

    static final class Cizim extends Drawable {
        private final S s;
        private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final float d;
        private int renk;

        Cizim(Context c, S s, int renk) {
            this.s = s;
            this.renk = renk;
            d = c.getResources().getDisplayMetrics().density;
            p.setStrokeCap(Paint.Cap.ROUND);
            p.setStrokeJoin(Paint.Join.ROUND);
        }

        void renk(int r) { renk = r; invalidateSelf(); }

        @Override public int getIntrinsicWidth() { return Math.round(24 * d); }
        @Override public int getIntrinsicHeight() { return Math.round(24 * d); }

        @Override public void draw(Canvas c) {
            float w = getBounds().width(), h = getBounds().height();
            float k = Math.min(w, h) / 24f;              // 24 birimlik ızgara
            c.save();
            c.translate(getBounds().left + (w - 24 * k) / 2f, getBounds().top + (h - 24 * k) / 2f);
            c.scale(k, k);
            p.setColor(renk);
            p.setStyle(Paint.Style.STROKE);
            p.setStrokeWidth(2f);
            p.setTextAlign(Paint.Align.CENTER);
            switch (s) {
                case MENU: cizgi(c, 4, 7, 20, 7); cizgi(c, 4, 12, 20, 12); cizgi(c, 4, 17, 20, 17); break;
                case GERI_AL: ok(c, false); break;
                case YINELE: ok(c, true); break;
                case DAHA: nokta(c, 12, 6); nokta(c, 12, 12); nokta(c, 12, 18); break;
                case KLAVYE: {
                    c.drawRoundRect(new RectF(3, 6, 21, 18), 2, 2, p);
                    for (int i = 0; i < 4; i++) { nokta1(c, 7 + i * 3.4f, 10); nokta1(c, 7 + i * 3.4f, 13); }
                    cizgi(c, 8.5f, 15.5f, 15.5f, 15.5f);
                    break;
                }
                case BICIM: harf(c, "A", false, false, false, 17); cizgi(c, 6, 21, 18, 21); break;
                case KALIN: harf(c, "B", true, false, false, 17); break;
                case ITALIK: harf(c, "I", false, true, false, 17); break;
                case ALTI: harf(c, "U", false, false, false, 15); cizgi(c, 6.5f, 20.5f, 17.5f, 20.5f); break;
                case USTU_CIZILI: harf(c, "S", false, false, false, 17); cizgi(c, 5, 12, 19, 12); break;
                case RENK: {
                    harf(c, "A", false, false, false, 15);
                    p.setStyle(Paint.Style.FILL);
                    p.setColor(Color.rgb(217, 48, 37));
                    c.drawRoundRect(new RectF(5, 19, 19, 22), 1, 1, p);
                    break;
                }
                case VURGULA: {
                    Path y = new Path();
                    y.moveTo(14, 4); y.lineTo(19, 9); y.lineTo(10, 18); y.lineTo(5, 18); y.lineTo(5, 13); y.close();
                    c.drawPath(y, p);
                    p.setStyle(Paint.Style.FILL);
                    p.setColor(Color.rgb(251, 188, 4));
                    c.drawRoundRect(new RectF(4, 20, 20, 22.5f), 1, 1, p);
                    break;
                }
                case SOL: hizala(c, 0); break;
                case ORTA: hizala(c, 1); break;
                case SAG: hizala(c, 2); break;
                case IKI_YANA: hizala(c, 3); break;
                case MADDE: for (int i = 0; i < 3; i++) { nokta(c, 5.5f, 7 + i * 5); cizgi(c, 10, 7 + i * 5, 20, 7 + i * 5); } break;
                case NUMARA: {
                    p.setStyle(Paint.Style.FILL);
                    p.setTextSize(6.5f);
                    p.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
                    for (int i = 0; i < 3; i++) c.drawText(String.valueOf(i + 1), 5.5f, 9.3f + i * 5, p);
                    p.setStyle(Paint.Style.STROKE);
                    for (int i = 0; i < 3; i++) cizgi(c, 10, 7 + i * 5, 20, 7 + i * 5);
                    break;
                }
                case GIRINTI_AZ: case GIRINTI_COK: {
                    cizgi(c, 4, 5, 20, 5); cizgi(c, 11, 10, 20, 10); cizgi(c, 11, 14, 20, 14); cizgi(c, 4, 19, 20, 19);
                    Path y = new Path();
                    if (s == S.GIRINTI_COK) { y.moveTo(4, 9); y.lineTo(7.5f, 12); y.lineTo(4, 15); }
                    else { y.moveTo(7.5f, 9); y.lineTo(4, 12); y.lineTo(7.5f, 15); }
                    c.drawPath(y, p);
                    break;
                }
                case TUSLAR: {
                    c.drawRoundRect(new RectF(3, 7, 10, 14), 1.5f, 1.5f, p);
                    c.drawRoundRect(new RectF(14, 7, 21, 14), 1.5f, 1.5f, p);
                    c.drawRoundRect(new RectF(3, 16.5f, 21, 20), 1.5f, 1.5f, p);
                    p.setStyle(Paint.Style.FILL);
                    p.setTextSize(5f);
                    c.drawText("Esc", 6.5f, 12.3f, p);
                    c.drawText("Ctrl", 17.5f, 12.3f, p);
                    break;
                }
                case MOBIL: c.drawRoundRect(new RectF(7, 3, 17, 21), 2.5f, 2.5f, p); cizgi(c, 11, 18, 13, 18); break;
                case MASAUSTU: c.drawRoundRect(new RectF(3, 5, 21, 16), 1.5f, 1.5f, p); cizgi(c, 9, 20, 15, 20); cizgi(c, 12, 16, 12, 20); break;
                case KAPAT: cizgi(c, 6, 6, 18, 18); cizgi(c, 18, 6, 6, 18); break;
                case GERI: cizgi(c, 19, 12, 5, 12); cizgi(c, 5, 12, 11, 6); cizgi(c, 5, 12, 11, 18); break;
                case ILERI: cizgi(c, 9, 6, 15, 12); cizgi(c, 15, 12, 9, 18); break;
                case ARTI: cizgi(c, 12, 5, 12, 19); cizgi(c, 5, 12, 19, 12); break;
                case EKSI: cizgi(c, 5, 12, 19, 12); break;
                case ALT_SIMGE: harf(c, "x", false, false, false, 14); p.setTextSize(7); p.setStyle(Paint.Style.FILL); c.drawText("2", 18, 21, p); break;
                case UST_SIMGE: harf(c, "x", false, false, false, 14); p.setTextSize(7); p.setStyle(Paint.Style.FILL); c.drawText("2", 18, 9, p); break;
                case TEMIZLE: {
                    harf(c, "T", false, false, false, 15);
                    p.setStyle(Paint.Style.STROKE);
                    cizgi(c, 5, 4, 20, 21);
                    break;
                }
                case SATIR_ARALIGI: {
                    cizgi(c, 11, 6, 20, 6); cizgi(c, 11, 12, 20, 12); cizgi(c, 11, 18, 20, 18);
                    cizgi(c, 5.5f, 5, 5.5f, 19); cizgi(c, 3.5f, 7, 5.5f, 5); cizgi(c, 7.5f, 7, 5.5f, 5);
                    cizgi(c, 3.5f, 17, 5.5f, 19); cizgi(c, 7.5f, 17, 5.5f, 19);
                    break;
                }
                case KAYDET: {
                    c.drawRoundRect(new RectF(4, 4, 20, 20), 2, 2, p);
                    c.drawRect(new RectF(8, 4, 16, 9), p);
                    c.drawRect(new RectF(7.5f, 13, 16.5f, 20), p);
                    break;
                }
                case AC: {
                    Path y = new Path();
                    y.moveTo(3, 7); y.lineTo(3, 19); y.lineTo(21, 19); y.lineTo(21, 9); y.lineTo(12, 9); y.lineTo(10, 6); y.lineTo(4, 6); y.close();
                    c.drawPath(y, p);
                    break;
                }
                case ARA: c.drawCircle(10.5f, 10.5f, 6, p); cizgi(c, 15, 15, 20, 20); break;
                case KAYDIR: {
                    cizgi(c, 12, 4, 12, 20); cizgi(c, 9, 7, 12, 4); cizgi(c, 15, 7, 12, 4); cizgi(c, 9, 17, 12, 20); cizgi(c, 15, 17, 12, 20);
                    break;
                }
                case SECIM: {
                    cizgi(c, 12, 4, 12, 20); cizgi(c, 9, 4, 15, 4); cizgi(c, 9, 20, 15, 20);
                    break;
                }
                default: break;
            }
            c.restore();
        }

        private void cizgi(Canvas c, float x0, float y0, float x1, float y1) { c.drawLine(x0, y0, x1, y1, p); }

        private void nokta(Canvas c, float x, float y) {
            Paint.Style st = p.getStyle();
            p.setStyle(Paint.Style.FILL);
            c.drawCircle(x, y, 1.6f, p);
            p.setStyle(st);
        }

        private void nokta1(Canvas c, float x, float y) {
            Paint.Style st = p.getStyle();
            p.setStyle(Paint.Style.FILL);
            c.drawCircle(x, y, 0.9f, p);
            p.setStyle(st);
        }

        private void harf(Canvas c, String m, boolean kalin, boolean egik, boolean alti, float boy) {
            p.setStyle(Paint.Style.FILL);
            p.setTextSize(boy);
            p.setTypeface(android.graphics.Typeface.create(egik ? android.graphics.Typeface.SERIF : android.graphics.Typeface.SANS_SERIF,
                    (kalin ? android.graphics.Typeface.BOLD : 0) | (egik ? android.graphics.Typeface.ITALIC : 0)));
            p.setFakeBoldText(kalin);
            c.drawText(m, 12, 12 + boy * 0.36f, p);
            p.setFakeBoldText(false);
            p.setStyle(Paint.Style.STROKE);
        }

        private void hizala(Canvas c, int tur) {
            float[] uz = {16, 10, 16, 10};
            for (int i = 0; i < 4; i++) {
                float l = tur == 3 ? 16 : uz[i];
                float x0 = tur == 0 || tur == 3 ? 4 : tur == 1 ? 12 - l / 2 : 20 - l;
                cizgi(c, x0, 6 + i * 4, x0 + l, 6 + i * 4);
            }
        }

        private void ok(Canvas c, boolean ileri) {
            c.save();
            if (ileri) c.scale(-1, 1, 12, 12);
            Path y = new Path();
            y.moveTo(9, 6); y.lineTo(5, 10); y.lineTo(9, 14);
            c.drawPath(y, p);
            Path e = new Path();
            e.moveTo(5, 10); e.lineTo(14, 10); e.cubicTo(17.5f, 10, 20, 12.5f, 20, 15); e.cubicTo(20, 17.5f, 17.5f, 19, 14, 19); e.lineTo(11, 19);
            c.drawPath(e, p);
            c.restore();
        }

        @Override public void setAlpha(int a) { p.setAlpha(a); }
        @Override public void setColorFilter(ColorFilter cf) { p.setColorFilter(cf); }
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
}
