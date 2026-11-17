package uyaptermux;

import java.awt.AWTEvent;
import java.awt.Component;
import java.awt.Container;
import java.awt.GraphicsEnvironment;
import java.awt.Toolkit;
import java.awt.event.HierarchyEvent;
import java.awt.event.MouseWheelEvent;
import java.awt.event.MouseWheelListener;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import javax.swing.JScrollBar;
import javax.swing.JScrollPane;
import javax.swing.JViewport;
import javax.swing.SwingUtilities;
import javax.swing.Timer;

/**
 * Word/tarayici hissinde akici kaydirma (uyap-editor-modern SmoothScroller'dan uyarlandi).
 *
 * - Tekerlek her centikte animasyonu bastan baslatmaz; yalnizca HEDEFI oteler. Konum, kritik sonumlu bir
 *   yay (SmoothDamp) ile hedefi izler: hiz hicbir centikte ani sicramaz, durus yumusaktir.
 * - Ilerleme gercek gecen sureye (dt) baglidir; EDT gec kalsa da hiz degismez.
 * - UYAP'in metin bileseninin kendi tekerlek dinleyicisi devralinir; Ctrl/Shift/Alt + tekerlek
 *   (yakinlastirma, yatay kaydirma) ORIJINAL dinleyicilere iletilir. (v3'te bu olaylar da yutuluyordu.)
 * - Kare zamanlayici yalnizca animasyon suresince calisir (pil dostu).
 */
final class AkiciKaydirma implements MouseWheelListener {
    private static final Map<JScrollPane, AkiciKaydirma> KAYITLI = Collections.synchronizedMap(new WeakHashMap<>());
    private static volatile boolean acik = true;
    private static volatile boolean kuruldu = false;

    private static final double YUMUSATMA_SN = Double.parseDouble(System.getProperty("uyap.kaydirma.sure", "0.11"));
    private static final double ADIM = Double.parseDouble(System.getProperty("uyap.kaydirma.adim", "75"));

    private final JScrollPane pane;
    private final List<MouseWheelListener> devralinan = new ArrayList<>();
    private Component bagliGorunum;
    private final Timer suprgec;

    // yalnizca EDT
    private double konum, hedef, hiz;
    private long sonAdimNs, sonCentikNs;
    private double centikHiziEma;

    private volatile boolean calisiyor;
    private volatile Thread zamanlayici;
    private final AtomicBoolean bekleyenKare = new AtomicBoolean(false);

    static boolean acikMi() { return acik; }

    static boolean degistir() {
        acik = !acik;
        synchronized (KAYITLI) {
            for (Map.Entry<JScrollPane, AkiciKaydirma> e : KAYITLI.entrySet()) {
                e.getKey().setWheelScrollingEnabled(!acik);
                if (!acik) e.getValue().durdur();
            }
        }
        return acik;
    }

    /** Ekranda gorunen her JScrollPane'e otomatik baglanir. */
    static void kur() {
        if (kuruldu) return;
        kuruldu = true;
        Toolkit.getDefaultToolkit().addAWTEventListener(ev -> {
            HierarchyEvent he = (HierarchyEvent) ev;
            if ((he.getChangeFlags() & HierarchyEvent.SHOWING_CHANGED) != 0 && he.getComponent().isShowing()) {
                tara(he.getComponent());
            }
        }, AWTEvent.HIERARCHY_EVENT_MASK);
    }

    private static void tara(Component c) {
        if (c instanceof JScrollPane) bagla((JScrollPane) c);
        if (c instanceof Container) {
            for (Component k : ((Container) c).getComponents()) tara(k);
        }
    }

    private static void bagla(JScrollPane p) {
        synchronized (KAYITLI) {
            if (!KAYITLI.containsKey(p)) KAYITLI.put(p, new AkiciKaydirma(p));
        }
    }

    private AkiciKaydirma(JScrollPane p) {
        pane = p;
        pane.setWheelScrollingEnabled(!acik);
        pane.addMouseWheelListener(this);
        JViewport vp = pane.getViewport();
        if (vp != null) {
            vp.setScrollMode(JViewport.BACKINGSTORE_SCROLL_MODE);
            vp.addChangeListener(e -> gorunumeBaglan());
        }
        gorunumeBaglan();
        // UYAP bazi dinleyicileri sonradan ekliyor: periyodik olarak devral
        suprgec = new Timer(750, e -> { if (pane.isShowing()) gorunumeBaglan(); });
        suprgec.start();
    }

    private void gorunumeBaglan() {
        JViewport vp = pane.getViewport();
        Component v = vp == null ? null : vp.getView();
        if (v == null) return;
        if (v != bagliGorunum) {
            if (bagliGorunum != null) {
                bagliGorunum.removeMouseWheelListener(this);
                for (MouseWheelListener l : devralinan) bagliGorunum.addMouseWheelListener(l);
                devralinan.clear();
            }
            bagliGorunum = v;
            v.addMouseWheelListener(this);
        }
        for (MouseWheelListener l : v.getMouseWheelListeners()) {
            if (l == this) continue;
            if (!devralinan.contains(l)) devralinan.add(l);
            v.removeMouseWheelListener(l);
        }
    }

    private void orijinaleIlet(MouseWheelEvent e) {
        if (e.getSource() == bagliGorunum && !devralinan.isEmpty()) {
            for (MouseWheelListener l : new ArrayList<>(devralinan)) l.mouseWheelMoved(e);
        } else {
            // yedek: Swing'in kendi kaydirmasini tek olay icin calistir (kendimizi gecici cikararak: dongu olmasin)
            pane.removeMouseWheelListener(this);
            pane.setWheelScrollingEnabled(true);
            try {
                pane.dispatchEvent(e.getSource() == pane ? e
                        : SwingUtilities.convertMouseEvent((Component) e.getSource(), e, pane));
            } finally {
                pane.setWheelScrollingEnabled(!acik);
                pane.addMouseWheelListener(this);
            }
        }
    }

    @Override
    public void mouseWheelMoved(MouseWheelEvent e) {
        if (e.isConsumed()) return;
        if (!acik || e.isControlDown() || e.isShiftDown() || e.isAltDown() || e.isMetaDown()) {
            orijinaleIlet(e);
            return;
        }

        JScrollBar bar = pane.getVerticalScrollBar();
        if (bar == null || !bar.isVisible()) return;
        e.consume();

        long simdi = System.nanoTime();
        double ara = (simdi - sonCentikNs) / 1e9;
        sonCentikNs = simdi;
        if (ara > 0.30 || ara <= 0) {
            centikHiziEma = 0;
        } else {
            double h = 1.0 / ara;
            centikHiziEma = centikHiziEma == 0 ? h : 0.75 * centikHiziEma + 0.25 * h;
        }
        double ivme = 1.0 + Math.min(1.0, Math.max(0.0, (centikHiziEma - 12.0) / 28.0));
        double donus;
        try { donus = e.getPreciseWheelRotation(); } catch (Throwable t) { donus = e.getWheelRotation(); }

        int min = bar.getMinimum();
        int max = bar.getMaximum() - bar.getModel().getExtent();
        if (!calisiyor) {
            konum = bar.getValue();
            hedef = konum;
            hiz = 0;
        }
        hedef = Math.max(min, Math.min(max, hedef + donus * ADIM * ivme));
        if (!calisiyor) {
            calisiyor = true;
            sonAdimNs = System.nanoTime();
            zamanlayiciBaslat();
        }
    }

    private static int hedefHz() {
        int hz = Integer.getInteger("uyap.hz", 0);
        if (hz <= 0) {
            hz = 60;
            try {
                int r = GraphicsEnvironment.getLocalGraphicsEnvironment().getDefaultScreenDevice().getDisplayMode().getRefreshRate();
                if (r >= 60 && r <= 240) hz = r;
            } catch (Throwable ignored) { }
        }
        return Math.max(30, Math.min(240, hz));
    }

    private void zamanlayiciBaslat() {
        final long periyot = 1_000_000_000L / hedefHz();
        Thread t = new Thread(() -> {
            long sonraki = System.nanoTime();
            while (calisiyor && zamanlayici == Thread.currentThread()) {
                if (bekleyenKare.compareAndSet(false, true)) {
                    SwingUtilities.invokeLater(() -> {
                        try { adim(); } finally { bekleyenKare.set(false); }
                    });
                }
                sonraki += periyot;
                long kalan = sonraki - System.nanoTime();
                if (kalan < 0) { sonraki = System.nanoTime(); continue; }
                try {
                    Thread.sleep(kalan / 1_000_000L, (int) (kalan % 1_000_000L));
                } catch (InterruptedException ie) {
                    return;
                }
            }
        }, "uyap-akici-kaydirma");
        t.setDaemon(true);
        zamanlayici = t;
        t.start();
    }

    private void adim() {
        if (!calisiyor) return;
        JScrollBar bar = pane.getVerticalScrollBar();
        if (bar == null) { durdur(); return; }
        long simdi = System.nanoTime();
        double dt = (simdi - sonAdimNs) / 1e9;
        sonAdimNs = simdi;
        if (dt <= 0) return;
        if (dt > 0.05) dt = 0.05;

        // Kritik sonumlu yay (SmoothDamp)
        double omega = 2.0 / YUMUSATMA_SN;
        double x = omega * dt;
        double us = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x);
        double fark = konum - hedef;
        double gecici = (hiz + omega * fark) * dt;
        hiz = (hiz - omega * gecici) * us;
        konum = hedef + (fark + gecici) * us;

        int min = bar.getMinimum();
        int max = bar.getMaximum() - bar.getModel().getExtent();
        if (Math.abs(hedef - konum) < 0.35 && Math.abs(hiz) < 6.0) {
            bar.setValue((int) Math.round(Math.max(min, Math.min(max, hedef))));
            durdur();
            return;
        }
        konum = Math.max(min, Math.min(max, konum));
        bar.setValue((int) Math.round(konum));
    }

    private void durdur() {
        calisiyor = false;
        hiz = 0;
        zamanlayici = null;
    }
}
