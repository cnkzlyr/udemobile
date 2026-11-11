package tr.gov.uyap.modernizer;

import javax.swing.*;
import java.awt.Component;
import java.awt.event.MouseWheelEvent;
import java.awt.event.MouseWheelListener;
import java.util.Collections;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Microsoft Word / modern tarayici hissinde akici kaydirma.
 *
 * Tekerlek her centikte animasyonu BASTAN BASLATMAZ; yalnizca hedef konumu oteler.
 * Gercek konum, hizi sureklilik gosteren kritik sonumlu bir yay (critically damped spring)
 * ile hedefi izler: hiz ve ivme hicbir centikte ani sicramaz, durus yumusaktir.
 * Kare zamani PrecisionTicker ile (120/144/240 Hz) hassas uretilir, ilerleme gercek gecen
 * sureye (dt) baglidir; EDT geç kalsa bile hareket hizi degismez.
 */
public class SmoothScroller implements MouseWheelListener {
    private static final Map<JScrollPane, SmoothScroller> activeScrollers =
            Collections.synchronizedMap(new WeakHashMap<>());

    // Yay yumusatma suresi (sn): kucuk = daha seri, buyuk = daha yagli. Word ~0.10-0.12.
    private static final double SMOOTH_TIME = 0.11;

    private final JScrollPane scrollPane;
    private PrecisionTicker.Handle animTask;
    private Timer sweeper;

    // Yalnizca EDT'de erisilir
    private double position;
    private double target;
    private double velocity;
    private long lastStepNanos;
    private double wheelRateEma = 0;
    private long lastWheelNanos = 0;

    private volatile boolean isRunning = false;
    private final AtomicBoolean isDispatchPending = new AtomicBoolean(false);

    public SmoothScroller(JScrollPane pane) {
        this.scrollPane = pane;
        this.scrollPane.setWheelScrollingEnabled(false);
        this.scrollPane.addMouseWheelListener(this);

        JViewport vp = this.scrollPane.getViewport();
        if (vp != null) {
            String sm = System.getProperty("uyap.scrollmode", "BACKINGSTORE");
            vp.setScrollMode("BLIT".equals(sm) ? JViewport.BLIT_SCROLL_MODE
                    : "SIMPLE".equals(sm) ? JViewport.SIMPLE_SCROLL_MODE : JViewport.BACKINGSTORE_SCROLL_MODE);
            vp.addChangeListener(e -> attachView());
        }
        attachView();
        sweeper = new Timer(750, e -> attachView());
        sweeper.setRepeats(true);
        sweeper.start();
    }

    // UYAP editor bileseni (text.t) kendi MouseWheelListener'ina sahip oldugu icin tekerlek olaylari
    // ScrollPane'e hic ulasmiyordu. Bilesenin dinleyicilerini devralip Ctrl+tekerlek gibi
    // islevleri orijinaline devrediyoruz.
    private Component hookedView;
    private final java.util.List<MouseWheelListener> delegates = new java.util.ArrayList<>();

    private void attachView() {
        JViewport vp = scrollPane.getViewport();
        Component view = vp == null ? null : vp.getView();
        if (view == null) return;
        if (view != hookedView) {
            detachView();
            hookedView = view;
            view.addMouseWheelListener(this);
        }
        sweepListeners();
    }

    private void sweepListeners() {
        Component view = hookedView;
        if (view == null) return;
        for (MouseWheelListener l : view.getMouseWheelListeners()) {
            if (l == this) continue;
            if (!delegates.contains(l)) delegates.add(l);
            view.removeMouseWheelListener(l);
        }
    }

    private void detachView() {
        if (hookedView == null) return;
        hookedView.removeMouseWheelListener(this);
        for (MouseWheelListener l : delegates) hookedView.addMouseWheelListener(l);
        delegates.clear();
        hookedView = null;
    }

    public static void hook(JScrollPane pane) {
        if (pane == null) return;
        synchronized (activeScrollers) {
            if (activeScrollers.containsKey(pane)) return;
            if (ModernizerConfig.isSmoothScrollEnabled()) {
                SmoothScroller scroller = new SmoothScroller(pane);
                activeScrollers.put(pane, scroller);
            }
        }
    }

    public static void updateAll() {
        boolean enabled = ModernizerConfig.isSmoothScrollEnabled();
        synchronized (activeScrollers) {
            if (!enabled) {
                for (SmoothScroller s : activeScrollers.values()) {
                    s.uninstallInternal();
                }
                activeScrollers.clear();
            } else {
                for (SmoothScroller s : activeScrollers.values()) {
                    s.restartIfRunning();
                }
            }
        }
    }

    @Override
    public void mouseWheelMoved(MouseWheelEvent e) {
        ScrollBench.WHEELS.incrementAndGet();
        if (!ModernizerConfig.isSmoothScrollEnabled()) {
            scrollPane.setWheelScrollingEnabled(true);
            return;
        }

        // Ctrl/Shift/Alt + tekerlek (yakinlastirma vb.) orijinal dinleyicilere birakilir
        if (e.isControlDown() || e.isShiftDown() || e.isAltDown()) {
            for (MouseWheelListener l : new java.util.ArrayList<>(delegates)) l.mouseWheelMoved(e);
            return;
        }

        JScrollBar vbar = scrollPane.getVerticalScrollBar();
        if (vbar == null || !vbar.isVisible()) return;

        long now = System.nanoTime();
        double sinceLast = (now - lastWheelNanos) / 1e9;
        lastWheelNanos = now;

        // Cark hizina bagli YUMUSAK ivmelenme (ani sicrama yok): hizli cevirince daha uzaga gider
        if (sinceLast > 0.30 || sinceLast <= 0) {
            wheelRateEma = 0;
        } else {
            double rate = 1.0 / sinceLast;
            wheelRateEma = wheelRateEma == 0 ? rate : (0.75 * wheelRateEma + 0.25 * rate);
        }
        double accel = 1.0 + Math.min(1.0, Math.max(0.0, (wheelRateEma - 12.0) / 28.0));

        double rotation;
        try {
            rotation = e.getPreciseWheelRotation();
        } catch (Throwable ignored) {
            rotation = e.getWheelRotation();
        }

        double step = ModernizerConfig.getScrollStep();
        if (step <= 0) step = 75.0;
        double delta = rotation * step * accel;

        int min = vbar.getMinimum();
        int max = vbar.getMaximum() - vbar.getModel().getExtent();

        if (!isRunning) {
            position = vbar.getValue();
            target = position;
            velocity = 0;
        }
        target = Math.max(min, Math.min(max, target + delta));

        synchronized (this) {
            if (!isRunning) {
                isRunning = true;
                lastStepNanos = System.nanoTime();
                startTimer();
            }
        }
    }

    private synchronized void startTimer() {
        int hz = ModernizerConfig.getTargetHz();
        if (hz <= 0) hz = 120;
        try {
            int screen = java.awt.GraphicsEnvironment.getLocalGraphicsEnvironment()
                    .getDefaultScreenDevice().getDisplayMode().getRefreshRate();
            if (screen >= 60 && screen <= 360) hz = Math.max(hz, screen);
        } catch (Throwable ignored) {}
        long periodNanos = 1_000_000_000L / hz;
        animTask = PrecisionTicker.schedule(this::tick, periodNanos);
    }

    private void tick() {
        if (ScrollBench.ENABLED) ScrollBench.TICKS.add(System.nanoTime());
        if (!isRunning) return;
        // EDT onceki kareyi hala isliyorsa yeni olay yigma (coalesce)
        if (isDispatchPending.compareAndSet(false, true)) {
            final long posted = System.nanoTime();
            SwingUtilities.invokeLater(() -> {
                if (ScrollBench.ENABLED) ScrollBench.LAT.add(System.nanoTime() - posted);
                try {
                    stepOnEdt();
                } finally {
                    isDispatchPending.set(false);
                }
            });
        }
    }

    private void stepOnEdt() {
        if (!isRunning) return;

        JScrollBar vbar = scrollPane.getVerticalScrollBar();
        if (vbar == null) {
            stopAnimation();
            return;
        }

        long now = System.nanoTime();
        double dt = (now - lastStepNanos) / 1e9;
        lastStepNanos = now;
        if (dt <= 0) return;
        if (dt > 0.05) dt = 0.05; // uzun donmada sicrama olmasin

        // Kritik sonumlu yay (SmoothDamp): konum ve hiz surekli
        double omega = 2.0 / SMOOTH_TIME;
        double x = omega * dt;
        double exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x);
        double change = position - target;
        double temp = (velocity + omega * change) * dt;
        velocity = (velocity - omega * temp) * exp;
        position = target + (change + temp) * exp;

        int min = vbar.getMinimum();
        int max = vbar.getMaximum() - vbar.getModel().getExtent();

        boolean done = Math.abs(target - position) < 0.35 && Math.abs(velocity) < 6.0;
        if (done) {
            position = target;
            vbar.setValue((int) Math.round(Math.max(min, Math.min(max, position))));
            stopAnimation();
            return;
        }
        position = Math.max(min, Math.min(max, position));
        if (position <= min || position >= max) {
            if (Math.abs(target - position) < 0.5) velocity = 0;
        }

        int value = (int) Math.round(position);
        if (ScrollBench.ENABLED) {
            final long t0 = System.nanoTime();
            final double req = position;
            vbar.setValue(value);
            final int actual = vbar.getValue();
            SwingUtilities.invokeLater(() -> ScrollBench.SAMPLES.add(new long[]{t0, System.nanoTime(), Double.doubleToLongBits(req), actual}));
        } else {
            vbar.setValue(value);
        }
    }

    private synchronized void stopAnimation() {
        isRunning = false;
        velocity = 0;
        if (animTask != null) {
            animTask.cancel(false);
            animTask = null;
        }
    }

    private synchronized void restartIfRunning() {
        if (isRunning) {
            if (animTask != null) {
                animTask.cancel(false);
                animTask = null;
            }
            startTimer();
        }
    }

    private void uninstallInternal() {
        stopAnimation();
        if (sweeper != null) sweeper.stop();
        detachView();
        scrollPane.removeMouseWheelListener(this);
        scrollPane.setWheelScrollingEnabled(true);
    }
}
