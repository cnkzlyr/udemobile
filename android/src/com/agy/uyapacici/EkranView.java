package com.agy.uyapacici;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.text.InputType;
import android.view.Choreographer;
import android.view.GestureDetector;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.ScaleGestureDetector;
import android.view.View;
import android.view.inputmethod.BaseInputConnection;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputConnection;
import android.view.inputmethod.InputMethodManager;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.ByteOrder;
import java.nio.IntBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;

/**
 * UYAP Mobil ekranı: Java tarafındaki köprünün paylaşılan bellek dosyasındaki (ekran.bin) kareyi çizer ve dokunma /
 * klavye olaylarını editöre (fare / tuş) çevirir.
 *
 * Kare: başlık int[16] = {sihir, genişlik, yükseklik, kareNo, y0, y1, ...} + ARGB pikseller. Her ekran yenilemesinde
 * (Choreographer) kare numarası değiştiyse yalnızca değişen satırlar Bitmap'e kopyalanır.
 *
 * Dokunma: tek dokunuş = tıklama · çift dokunuş = çift tıklama · uzun basma = sağ tık · tek parmak sürükleme =
 * kaydırma (fare tekerleği, ivmeli) ya da "seç" kipinde fare sürükleme · iki parmak = yakınlaştır / kaydır.
 * Klavye: kendi sanal klavye düğmesi (Android klavyesi, TYPE_NULL: tuş tuş), donanım klavyesi, fare ve kalem.
 */
public class EkranView extends View implements Choreographer.FrameCallback {
    static final int SIHIR = 0x55594D31, BASLIK = 16;
    static final int SHIFT = 64, CTRL = 128, ALT = 512;

    private Bitmap bmp;
    private int W, H;
    private IntBuffer ib;
    private RandomAccessFile raf;
    private int sonKare = -1;
    private int[] satirlar;
    private final Paint boya = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Matrix m = new Matrix(), ters = new Matrix();
    private float olcek = 1f, ox = 0, oy = 0;      // görünüm: ekran = mantıksal * olcek + (ox, oy)
    private boolean kullaniciYakinlasti = false;
    private boolean calisiyor;

    /** true: tek parmak kaydırır (okuma) · false: tek parmak fareyi sürükler (seçim). */
    public boolean kaydirKipi = true;
    /** Yapışkan değiştiriciler (ek tuş çubuğundan): bir sonraki tuşa/karaktere uygulanır. */
    public int yapiskan = 0;
    public interface DegistiriciDinleyici { void degisti(int yapiskan); }
    public DegistiriciDinleyici degistiriciDinleyici;

    private final GestureDetector jest;
    private final ScaleGestureDetector olcekJest;
    private float tekerBirikim = 0;
    private boolean surukluyor = false;

    public EkranView(Context c) {
        super(c);
        setFocusable(true);
        setFocusableInTouchMode(true);
        setBackgroundColor(Color.rgb(46, 52, 64));
        jest = new GestureDetector(c, new Jestler());
        jest.setIsLongpressEnabled(true);
        olcekJest = new ScaleGestureDetector(c, new ScaleGestureDetector.SimpleOnScaleGestureListener() {
            @Override public boolean onScale(ScaleGestureDetector d) {
                float yeni = Math.max(sigdirOlcegi() * 0.5f, Math.min(olcek * d.getScaleFactor(), sigdirOlcegi() * 5f));
                float f = yeni / olcek;
                ox = d.getFocusX() - (d.getFocusX() - ox) * f;
                oy = d.getFocusY() - (d.getFocusY() - oy) * f;
                olcek = yeni;
                kullaniciYakinlasti = true;
                sinirla();
                invalidate();
                return true;
            }
        });
    }

    // ------------------------------------------------------------------------------------ bağlantı
    /** Paylaşılan ekran dosyasına bağlan (köprü hazır olunca). */
    public void baglan(File ekran, int w, int h) {
        kapat();
        try {
            long boy = 4L * (BASLIK + (long) w * h);
            for (int i = 0; i < 100 && (!ekran.isFile() || ekran.length() < boy); i++) Thread.sleep(50);
            raf = new RandomAccessFile(ekran, "r");
            MappedByteBuffer mb = raf.getChannel().map(FileChannel.MapMode.READ_ONLY, 0, boy);
            mb.order(ByteOrder.nativeOrder());
            ib = mb.asIntBuffer();
            W = w;
            H = h;
            bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
            bmp.setHasAlpha(false);
            satirlar = new int[w * h];
            sonKare = -1;
            post(() -> { if (!kullaniciYakinlasti) sigdir(); });
        } catch (Exception e) {
            Tani.hata("uyapmobil", "ekran bağlantısı", e);
        }
    }

    public void kapat() {
        ib = null;
        try { if (raf != null) raf.close(); } catch (Exception ignored) { }
        raf = null;
    }

    @Override protected void onAttachedToWindow() {
        super.onAttachedToWindow();
        calisiyor = true;
        Choreographer.getInstance().postFrameCallback(this);
    }

    @Override protected void onDetachedFromWindow() {
        calisiyor = false;
        Choreographer.getInstance().removeFrameCallback(this);
        super.onDetachedFromWindow();
    }

    @Override public void doFrame(long zaman) {
        if (!calisiyor) return;
        IntBuffer b = ib;
        if (b != null && bmp != null) {
            try {
                if (b.get(0) == SIHIR) {
                    int k = b.get(3);
                    if (k != sonKare) {
                        int y0 = 0, y1 = H;
                        if (k == sonKare + 1) { y0 = Math.max(0, b.get(4)); y1 = Math.min(H, b.get(5)); }
                        if (y1 > y0) {
                            int n = (y1 - y0) * W;
                            b.position(BASLIK + y0 * W);
                            b.get(satirlar, 0, n);
                            bmp.setPixels(satirlar, 0, W, 0, y0, W, y1 - y0);
                            invalidate();
                        }
                        sonKare = k;
                    }
                }
            } catch (Exception ignored) { }
        }
        Choreographer.getInstance().postFrameCallback(this);
    }

    // ------------------------------------------------------------------------------------ görünüm
    float sigdirOlcegi() {
        if (W == 0 || getWidth() == 0) return 1f;
        return getWidth() / (float) W;      // genişliğe sığdır (klavye açılınca ölçek değişmez, dikey kaydırılır)
    }

    public void sigdir() {
        olcek = sigdirOlcegi();
        ox = 0;
        oy = Math.max(0, (getHeight() - H * olcek) / 2f);
        kullaniciYakinlasti = false;
        sinirla();
        invalidate();
    }

    private void sinirla() {
        float gw = W * olcek, gh = H * olcek;
        if (gw <= getWidth()) ox = (getWidth() - gw) / 2f; else ox = Math.min(0, Math.max(getWidth() - gw, ox));
        if (gh <= getHeight()) oy = Math.max(0, Math.min(oy, getHeight() - gh)); else oy = Math.min(0, Math.max(getHeight() - gh, oy));
    }

    @Override protected void onSizeChanged(int w, int h, int ow, int oh) {
        super.onSizeChanged(w, h, ow, oh);
        if (!kullaniciYakinlasti) sigdir(); else sinirla();
    }

    @Override protected void onDraw(Canvas c) {
        if (bmp == null) return;
        m.reset();
        m.postScale(olcek, olcek);
        m.postTranslate(ox, oy);
        c.drawBitmap(bmp, m, boya);
        for (View a : aynalar) a.invalidate();
        if (olcek != sonBildirilen && olcekDinleyici != null) { sonBildirilen = olcek; post(olcekDinleyici); }
    }

    // ------------------------------------------------------------------------------------ yakınlaştırma (alt kapsül)
    /** Ölçek değişince (yakınlaştırma kapsülündeki yüzde için). */
    Runnable olcekDinleyici;
    private float sonBildirilen = -1;

    /** Genişliğe sığdırmaya göre yüzde (CanEditor'daki "%100 Sığdır" gibi). */
    int yuzde() { return Math.round(olcek / sigdirOlcegi() * 100f); }

    void yakinlastir(float f) {
        float yeni = Math.max(sigdirOlcegi() * 0.5f, Math.min(olcek * f, sigdirOlcegi() * 5f));
        float cx = getWidth() / 2f, cy = getHeight() / 2f, k = yeni / olcek;
        ox = cx - (cx - ox) * k;
        oy = cy - (cy - oy) * k;
        olcek = yeni;
        kullaniciYakinlasti = true;
        sinirla();
        invalidate();
    }

    /** Mantıksal ekrandaki bir dikdörtgeni (ör. resmi editörün açtığı pencere) ekrana sığdırıp ortala. */
    void odakla(int x, int y, int w, int h) {
        if (W == 0 || getWidth() == 0 || w <= 0 || h <= 0) return;
        float k = Math.min(getWidth() * 0.97f / w, getHeight() * 0.92f / h);
        olcek = Math.max(sigdirOlcegi() * 0.5f, Math.min(k, sigdirOlcegi() * 3.2f));
        ox = getWidth() / 2f - (x + w / 2f) * olcek;
        oy = getHeight() / 2f - (y + h / 2f) * olcek;
        kullaniciYakinlasti = true;
        sinirla();
        invalidate();
    }

    /** Ekranın tamamını göster (tüm sayfa, CanEditor'daki "↕ Sayfa"). */
    void sayfaSigdir() {
        if (W == 0 || H == 0 || getWidth() == 0) return;
        olcek = Math.min(getWidth() / (float) W, getHeight() / (float) H);
        kullaniciYakinlasti = true;
        ox = 0;
        oy = 0;
        sinirla();
        invalidate();
    }

    /** Bulanık üst/alt çubuklar ekranın kendi altında kalan parçasını çizer (Arayuz.BulanikZemin). */
    final java.util.List<View> aynalar = new java.util.concurrent.CopyOnWriteArrayList<>();

    /** Görüntüyü başka bir tuvale çiz; (dx, dy): o görünümün bu görünüme göre konumu (eksi yönde kaydırılır). */
    void aynaCiz(Canvas c, float dx, float dy) {
        if (bmp == null) return;
        Matrix a = new Matrix();
        a.postScale(olcek, olcek);
        a.postTranslate(ox - dx, oy - dy);
        c.drawBitmap(bmp, a, boya);
    }

    private int[] mantiksal(float x, float y) {
        int lx = Math.round((x - ox) / olcek), ly = Math.round((y - oy) / olcek);
        return new int[]{Math.max(0, Math.min(W - 1, lx)), Math.max(0, Math.min(H - 1, ly))};
    }

    // ------------------------------------------------------------------------------------ dokunma
    private void fare(String tur, float x, float y, int dugme) {
        int[] p = mantiksal(x, y);
        UyapMobilServisi.gonder(tur + " " + p[0] + " " + p[1] + (dugme > 0 ? " " + dugme : ""));
    }

    private void tikla(float x, float y, int dugme) {
        fare("D", x, y, dugme);
        fare("U", x, y, dugme);
    }

    private class Jestler extends GestureDetector.SimpleOnGestureListener {
        @Override public boolean onDown(MotionEvent e) { tekerBirikim = 0; firlatmaDurdur(); return true; }

        @Override public boolean onSingleTapConfirmed(MotionEvent e) {
            requestFocus();
            tikla(e.getX(), e.getY(), 1);
            return true;
        }

        @Override public boolean onDoubleTap(MotionEvent e) {
            tikla(e.getX(), e.getY(), 1);
            tikla(e.getX(), e.getY(), 1);
            return true;
        }

        @Override public void onLongPress(MotionEvent e) {
            if (surukluyor) return;
            performHapticFeedback(android.view.HapticFeedbackConstants.LONG_PRESS);
            tikla(e.getX(), e.getY(), 3);       // sağ tık (bağlam menüsü)
        }

        @Override public boolean onScroll(MotionEvent e1, MotionEvent e2, float dx, float dy) {
            if (e2.getPointerCount() >= 2) {          // iki parmak: görünümü kaydır
                ox -= dx;
                oy -= dy;
                kullaniciYakinlasti = true;
                sinirla();
                invalidate();
                return true;
            }
            if (kaydirKipi) {                           // tek parmak: belgeyi kaydır (fare tekerleği)
                tekerBirikim += dy / olcek;
                int adim = 24;
                while (Math.abs(tekerBirikim) >= adim) {
                    int yon = tekerBirikim > 0 ? 1 : -1;
                    int[] p = mantiksal(e2.getX(), e2.getY());
                    UyapMobilServisi.gonder("W " + p[0] + " " + p[1] + " " + yon);
                    tekerBirikim -= yon * adim;
                }
                return true;
            }
            return false;
        }

        @Override public boolean onFling(MotionEvent e1, MotionEvent e2, float vx, float vy) {
            if (!kaydirKipi || e2.getPointerCount() >= 2) return false;
            firlat(e2.getX(), e2.getY(), vy);
            return true;
        }
    }

    // fırlatma: hız azalarak tekerlek adımları (kasmadan, ~60 Hz)
    private Runnable firlatma;
    private void firlat(final float x, final float y, final float vy0) {
        firlatmaDurdur();
        final int[] p = mantiksal(x, y);
        firlatma = new Runnable() {
            float v = -vy0 / olcek;   // mantıksal px/sn (aşağı kaydırma pozitif)
            float birikim = 0;
            @Override public void run() {
                if (Math.abs(v) < 40) return;
                birikim += v / 60f;
                while (Math.abs(birikim) >= 24) {
                    int yon = birikim > 0 ? 1 : -1;
                    UyapMobilServisi.gonder("W " + p[0] + " " + p[1] + " " + yon);
                    birikim -= yon * 24;
                }
                v *= 0.93f;
                postDelayed(this, 16);
            }
        };
        post(firlatma);
    }

    private void firlatmaDurdur() { if (firlatma != null) removeCallbacks(firlatma); firlatma = null; }

    @Override public boolean onTouchEvent(MotionEvent e) {
        if (W == 0) return true;
        if (e.isFromSource(InputDevice.SOURCE_MOUSE) || e.getToolType(0) == MotionEvent.TOOL_TYPE_MOUSE) return fareOlayi(e);
        olcekJest.onTouchEvent(e);
        if (!kaydirKipi && e.getPointerCount() == 1 && !olcekJest.isInProgress()) {
            // seçim kipi: doğrudan fare sürükleme (D … M … U)
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN: requestFocus(); surukluyor = false; fare("D", e.getX(), e.getY(), 1); return true;
                case MotionEvent.ACTION_MOVE: surukluyor = true; fare("M", e.getX(), e.getY(), 0); return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL: fare("U", e.getX(), e.getY(), 1); return true;
                default: return true;
            }
        }
        jest.onTouchEvent(e);
        return true;
    }

    /** Gerçek fare / touchpad: imleç doğrudan (hover = hareket, düğmeler, tekerlek). */
    private int fareDugmeleri = 0;
    private boolean fareOlayi(MotionEvent e) {
        int d = e.getButtonState();
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
            case MotionEvent.ACTION_BUTTON_PRESS:
                requestFocus();
                int db = (d & MotionEvent.BUTTON_SECONDARY) != 0 ? 3 : (d & MotionEvent.BUTTON_TERTIARY) != 0 ? 2 : 1;
                fareDugmeleri = db;
                fare("D", e.getX(), e.getY(), db);
                return true;
            case MotionEvent.ACTION_MOVE: fare("M", e.getX(), e.getY(), 0); return true;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_BUTTON_RELEASE:
                fare("U", e.getX(), e.getY(), fareDugmeleri == 0 ? 1 : fareDugmeleri);
                fareDugmeleri = 0;
                return true;
            default: return true;
        }
    }

    @Override public boolean onGenericMotionEvent(MotionEvent e) {
        if (W == 0) return false;
        if (e.getActionMasked() == MotionEvent.ACTION_HOVER_MOVE) { fare("M", e.getX(), e.getY(), 0); return true; }
        if (e.getActionMasked() == MotionEvent.ACTION_SCROLL) {
            float v = e.getAxisValue(MotionEvent.AXIS_VSCROLL);
            int[] p = mantiksal(e.getX(), e.getY());
            if ((e.getMetaState() & KeyEvent.META_CTRL_ON) != 0) { olcek *= v > 0 ? 1.1f : 0.9f; kullaniciYakinlasti = true; sinirla(); invalidate(); return true; }
            UyapMobilServisi.gonder("W " + p[0] + " " + p[1] + " " + (v > 0 ? -1 : 1));
            return true;
        }
        return super.onGenericMotionEvent(e);
    }

    // ------------------------------------------------------------------------------------ klavye
    @Override public boolean onCheckIsTextEditor() { return true; }

    @Override public InputConnection onCreateInputConnection(EditorInfo o) {
        o.inputType = InputType.TYPE_NULL;           // tuş tuş (Termux gibi): öneri/otomatik düzeltme editörü bozmasın
        o.imeOptions = EditorInfo.IME_FLAG_NO_FULLSCREEN | EditorInfo.IME_FLAG_NO_EXTRACT_UI;
        return new BaseInputConnection(this, false) {
            @Override public boolean commitText(CharSequence t, int yeni) {
                if (t != null && t.length() > 0) metin(t.toString());
                return true;
            }
            @Override public boolean deleteSurroundingText(int once, int sonra) {
                for (int i = 0; i < once; i++) tus(8, 0);
                for (int i = 0; i < sonra; i++) tus(127, 0);
                return true;
            }
            @Override public boolean sendKeyEvent(KeyEvent e) {
                if (e.getAction() == KeyEvent.ACTION_DOWN) onKeyDown(e.getKeyCode(), e);
                return true;
            }
            @Override public boolean setComposingText(CharSequence t, int yeni) { return true; }
            @Override public boolean finishComposingText() { return true; }
        };
    }

    public void klavyeAcKapa() {
        requestFocus();
        InputMethodManager imm = (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) imm.toggleSoftInput(InputMethodManager.SHOW_FORCED, 0);
    }

    public void klavyeKapat() {
        InputMethodManager imm = (InputMethodManager) getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(getWindowToken(), 0);
    }

    /** Metni editöre yazar; yapışkan Ctrl/Alt varsa harf kısayol olarak gider (Ctrl+S gibi). */
    public void metin(String s) {
        int mod = yapiskan;
        if ((mod & (CTRL | ALT)) != 0 && s.length() == 1) {
            int vk = vkKarakter(s.charAt(0));
            if (vk != 0) { tus(vk, mod); yapiskanBirak(); return; }
        }
        if ((mod & SHIFT) != 0) s = s.toUpperCase(new java.util.Locale("tr", "TR"));
        UyapMobilServisi.gonder("T " + UyapMobilServisi.hex(s.getBytes(StandardCharsets.UTF_8)));
        if (mod != 0) yapiskanBirak();
    }

    /** AWT tuş kodu (VK_*) + değiştiriciler. */
    public void tus(int vk, int mod) {
        UyapMobilServisi.gonder("K " + vk + " 1 " + (mod | yapiskan));
        if (yapiskan != 0) yapiskanBirak();
    }

    private void yapiskanBirak() {
        yapiskan = 0;
        if (degistiriciDinleyici != null) degistiriciDinleyici.degisti(0);
    }

    static int vkKarakter(char c) {
        char u = Character.toUpperCase(c);
        if (u >= 'A' && u <= 'Z') return u;
        if (c >= '0' && c <= '9') return c;
        return 0;
    }

    static int vkAndroid(int k) {
        if (k >= KeyEvent.KEYCODE_A && k <= KeyEvent.KEYCODE_Z) return 'A' + (k - KeyEvent.KEYCODE_A);
        if (k >= KeyEvent.KEYCODE_0 && k <= KeyEvent.KEYCODE_9) return '0' + (k - KeyEvent.KEYCODE_0);
        if (k >= KeyEvent.KEYCODE_F1 && k <= KeyEvent.KEYCODE_F12) return 112 + (k - KeyEvent.KEYCODE_F1);
        switch (k) {
            case KeyEvent.KEYCODE_DEL: return 8;
            case KeyEvent.KEYCODE_FORWARD_DEL: return 127;
            case KeyEvent.KEYCODE_ENTER: case KeyEvent.KEYCODE_NUMPAD_ENTER: return 10;
            case KeyEvent.KEYCODE_TAB: return 9;
            case KeyEvent.KEYCODE_ESCAPE: return 27;
            case KeyEvent.KEYCODE_DPAD_LEFT: return 37;
            case KeyEvent.KEYCODE_DPAD_UP: return 38;
            case KeyEvent.KEYCODE_DPAD_RIGHT: return 39;
            case KeyEvent.KEYCODE_DPAD_DOWN: return 40;
            case KeyEvent.KEYCODE_MOVE_HOME: return 36;
            case KeyEvent.KEYCODE_MOVE_END: return 35;
            case KeyEvent.KEYCODE_PAGE_UP: return 33;
            case KeyEvent.KEYCODE_PAGE_DOWN: return 34;
            case KeyEvent.KEYCODE_INSERT: return 155;
            case KeyEvent.KEYCODE_SPACE: return 32;
            default: return 0;
        }
    }

    private static boolean ozel(int k) {
        switch (k) {
            case KeyEvent.KEYCODE_DEL: case KeyEvent.KEYCODE_FORWARD_DEL: case KeyEvent.KEYCODE_ENTER: case KeyEvent.KEYCODE_NUMPAD_ENTER:
            case KeyEvent.KEYCODE_TAB: case KeyEvent.KEYCODE_ESCAPE: case KeyEvent.KEYCODE_DPAD_LEFT: case KeyEvent.KEYCODE_DPAD_UP:
            case KeyEvent.KEYCODE_DPAD_RIGHT: case KeyEvent.KEYCODE_DPAD_DOWN: case KeyEvent.KEYCODE_MOVE_HOME: case KeyEvent.KEYCODE_MOVE_END:
            case KeyEvent.KEYCODE_PAGE_UP: case KeyEvent.KEYCODE_PAGE_DOWN: case KeyEvent.KEYCODE_INSERT:
                return true;
            default:
                return k >= KeyEvent.KEYCODE_F1 && k <= KeyEvent.KEYCODE_F12;
        }
    }

    @Override public boolean onKeyDown(int k, KeyEvent e) {
        if (k == KeyEvent.KEYCODE_BACK || k == KeyEvent.KEYCODE_VOLUME_UP || k == KeyEvent.KEYCODE_VOLUME_DOWN
                || k == KeyEvent.KEYCODE_SHIFT_LEFT || k == KeyEvent.KEYCODE_SHIFT_RIGHT || k == KeyEvent.KEYCODE_CTRL_LEFT
                || k == KeyEvent.KEYCODE_CTRL_RIGHT || k == KeyEvent.KEYCODE_ALT_LEFT || k == KeyEvent.KEYCODE_ALT_RIGHT)
            return super.onKeyDown(k, e);
        int mod = 0;
        if (e.isShiftPressed()) mod |= SHIFT;
        if (e.isCtrlPressed()) mod |= CTRL;
        if (e.isAltPressed()) mod |= ALT;
        if (ozel(k)) { tus(vkAndroid(k), mod); return true; }
        if ((mod & (CTRL | ALT)) != 0 || (yapiskan & (CTRL | ALT)) != 0) {
            int vk = vkAndroid(k);
            if (vk != 0) { tus(vk, mod); return true; }
        }
        int u = e.getUnicodeChar(e.getMetaState());
        if (u != 0 && (u & KeyCharacterMapCOMBINING) == 0) { metin(new String(Character.toChars(u))); return true; }
        return super.onKeyDown(k, e);
    }

    private static final int KeyCharacterMapCOMBINING = 0x80000000;
}
