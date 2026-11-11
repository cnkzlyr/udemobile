package tr.gov.uyap.modernizer;

import javax.swing.*;
import java.awt.*;
import java.awt.event.InputEvent;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Gelistirici olcum araci (-Duyap.bench=true). Gercek pencerede Robot ile tekerlek olayi
 * gonderir, kare araligi ve cizim suresini dosyaya yazar. Normal kullanimda devre disidir.
 */
public class ScrollBench {
    public static final boolean ENABLED = Boolean.getBoolean("uyap.bench");
    public static final java.util.concurrent.atomic.AtomicInteger WHEELS = new java.util.concurrent.atomic.AtomicInteger();
    public static final List<Long> TICKS = Collections.synchronizedList(new ArrayList<>());
    public static final List<Long> LAT = Collections.synchronizedList(new ArrayList<>());
    public static final List<long[]> SAMPLES = Collections.synchronizedList(new ArrayList<>());

    public static void start() {
        if (!ENABLED) return;
        Thread t = new Thread(() -> {
            try {
                Thread.sleep(9000);
                JScrollPane best = null;
                long bestArea = 0;
                for (Window w : Window.getWindows()) {
                    best = findLargest(w, best);
                }
                if (best == null) { write("no scrollpane"); System.exit(2); }
                Window win = SwingUtilities.getWindowAncestor(best);
                SwingUtilities.invokeAndWait(() -> { win.setAlwaysOnTop(true); win.toFront(); win.requestFocus(); });
                Thread.sleep(1500);
                Point p = best.getLocationOnScreen();
                Robot r = new Robot();
                int cx = p.x + best.getWidth() / 2, cy = p.y + best.getHeight() / 2;
                r.mouseMove(cx, cy);
                Thread.sleep(500);
                StringBuilder sb = new StringBuilder();
                sb.append("pane=").append(best.getWidth()).append("x").append(best.getHeight())
                  .append(" view=").append(best.getViewport().getView().getClass().getName()).append("\n");
                JScrollBar vb = best.getVerticalScrollBar();
                sb.append("vbar visible=").append(vb.isVisible()).append(" value=").append(vb.getValue()).append(" max=").append(vb.getMaximum()).append(" ext=").append(vb.getModel().getExtent()).append("\n");
                sb.append("pane wheelListeners=").append(best.getMouseWheelListeners().length).append(" wheelScrollingEnabled=").append(best.isWheelScrollingEnabled()).append("\n");
                Component v = best.getViewport().getView();
                sb.append("view wheelListeners=").append(v.getMouseWheelListeners().length).append(" mouseListeners=").append(v.getMouseListeners().length).append("\n");
                for (java.awt.event.MouseWheelListener l : v.getMouseWheelListeners()) sb.append("  viewWL: ").append(l.getClass().getName()).append("\n");
                for (java.awt.event.MouseWheelListener l : best.getMouseWheelListeners()) sb.append("  paneWL: ").append(l.getClass().getName()).append("\n");
                for (Component ch : best.getViewport().getComponents()) sb.append("  vpChild: ").append(ch.getClass().getName()).append("\n");
                SAMPLES.clear(); TICKS.clear(); LAT.clear();
                final java.util.Map<String,Integer> hot = new java.util.concurrent.ConcurrentHashMap<>();
                final java.util.Map<String,Integer> top = new java.util.concurrent.ConcurrentHashMap<>();
                final int[] total = new int[1];
                final boolean[] sampling = {true};
                Thread sampler = new Thread(() -> {
                    Thread edt = null;
                    for (Thread th : Thread.getAllStackTraces().keySet()) if (th.getName().startsWith("AWT-EventQueue")) edt = th;
                    while (sampling[0] && edt != null) {
                        StackTraceElement[] st = edt.getStackTrace();
                        boolean idle = st.length == 0;
                        for (StackTraceElement e : st) if (e.getMethodName().equals("getNextEvent") || e.getMethodName().equals("wait")) { idle = true; break; }
                        if (!idle) {
                            total[0]++;
                            top.merge(st[0].getClassName() + "." + st[0].getMethodName(), 1, Integer::sum);
                            java.util.Set<String> seen = new java.util.HashSet<>();
                            for (StackTraceElement e : st) {
                                String k = e.getClassName() + "." + e.getMethodName();
                                if (seen.add(k)) hot.merge(k, 1, Integer::sum);
                            }
                        }
                        try { Thread.sleep(1); } catch (InterruptedException ie) { return; }
                    }
                }, "bench-sampler");
                sampler.setDaemon(true); sampler.start();
                int robotWheelsBefore = WHEELS.get();
                r.mouseWheel(3); Thread.sleep(300);
                sb.append("robot wheel received=").append(WHEELS.get() - robotWheelsBefore).append(" mouse=").append(MouseInfo.getPointerInfo().getLocation()).append(" target=").append(cx + "," + cy).append("\n");
                boolean synthetic = (WHEELS.get() - robotWheelsBefore) == 0;
                sb.append("synthetic=").append(synthetic).append("\n");
                final Component view2 = v;
                // 3 seri tekerlek hareketi: 25 centik x 40ms
                for (int round = 0; round < 4; round++) {
                    for (int dir = 1; dir >= -1; dir -= 2) {
                        for (int i = 0; i < 6; i++) {
                            if (synthetic) {
                                Toolkit.getDefaultToolkit().getSystemEventQueue().postEvent(new java.awt.event.MouseWheelEvent(view2, java.awt.event.MouseEvent.MOUSE_WHEEL, System.currentTimeMillis(), 0, 100, 100, 0, false, java.awt.event.MouseWheelEvent.WHEEL_UNIT_SCROLL, 3, 3 * dir));
                            } else { r.mouseWheel(3 * dir); }
                            Thread.sleep(60);
                        }
                        Thread.sleep(600);
                    }
                }
                Thread.sleep(500);
                sampling[0] = false;
                sb.append("EDT busy samples=").append(total[0]).append("\n--- self (top frame) ---\n");
                top.entrySet().stream().sorted((a, c) -> c.getValue() - a.getValue()).limit(12).forEach(en -> sb.append(String.format("%5d %s%n", en.getValue(), en.getKey())));
                sb.append("--- inclusive ---\n");
                hot.entrySet().stream().sorted((a, c) -> c.getValue() - a.getValue()).limit(40).forEach(en -> sb.append(String.format("%5d %s%n", en.getValue(), en.getKey())));
                List<long[]> s = new ArrayList<>(SAMPLES);
                sb.append("vbar value after=").append(vb.getValue()).append("\n");
                sb.append("steps=").append(s.size()).append("\n");
                List<Double> gaps = new ArrayList<>();
                List<Double> paints = new ArrayList<>();
                for (int i = 0; i < s.size(); i++) {
                    paints.add((s.get(i)[1] - s.get(i)[0]) / 1e6);
                    if (i > 0 && s.get(i)[0] - s.get(i - 1)[0] < 100_000_000L) {
                        gaps.add((s.get(i)[0] - s.get(i - 1)[0]) / 1e6);
                    }
                }
                List<Long> tk = new ArrayList<>(TICKS); List<Double> tg = new ArrayList<>();
                for (int i = 1; i < tk.size(); i++) { double g = (tk.get(i) - tk.get(i-1)) / 1e6; if (g < 100) tg.add(g); }
                List<Long> la = new ArrayList<>(LAT); List<Double> lm = new ArrayList<>();
                for (long x : la) lm.add(x / 1e6);
                sb.append("ticks=").append(tk.size()).append(" tickGap(ms) ").append(stats(tg)).append("\n");
                sb.append("posts=").append(la.size()).append(" invokeLater latency(ms) ").append(stats(lm)).append("\n");
                // Piksel hareketi duzgunlugu: kare basina delta ve ardisik delta farki (jerk)
                List<Double> dl = new ArrayList<>(); List<Double> jk = new ArrayList<>(); int quant = 0;
                for (int i = 0; i < s.size(); i++) {
                    double req = Double.longBitsToDouble(s.get(i)[2]);
                    if (Math.abs(req - s.get(i)[3]) > 1.0) quant++;
                    if (i > 0 && s.get(i)[0] - s.get(i-1)[0] < 100_000_000L) {
                        double dd = s.get(i)[3] - s.get(i-1)[3];
                        dl.add(dd);
                        if (dl.size() > 1) jk.add(Math.abs(dd - dl.get(dl.size()-2)));
                    }
                }
                sb.append("px/frame ").append(stats(dl)).append("\n");
                sb.append("jerk(px) ").append(stats(jk)).append(" requested!=actual frames=").append(quant).append("\n");
                sb.append("gap(ms) ").append(stats(gaps)).append("\n");
                sb.append("setValue->paintDone(ms) ").append(stats(paints)).append("\n");
                write(sb.toString());
            } catch (Throwable e) {
                write("bench error: " + e);
            }
            System.exit(0);
        }, "ScrollBench");
        t.setDaemon(true);
        t.start();
    }

    private static JScrollPane findLargest(Component c, JScrollPane best) {
        if (c instanceof JScrollPane) {
            JScrollPane sp = (JScrollPane) c;
            if (sp.isShowing() && (best == null || area(sp) > area(best))) best = sp;
        }
        if (c instanceof Container) {
            for (Component ch : ((Container) c).getComponents()) best = findLargest(ch, best);
        }
        return best;
    }

    private static long area(Component c) { return (long) c.getWidth() * c.getHeight(); }

    private static String stats(List<Double> v) {
        if (v.isEmpty()) return "n/a";
        List<Double> s = new ArrayList<>(v);
        Collections.sort(s);
        double sum = 0; for (double d : s) sum += d;
        return String.format("n=%d avg=%.1f p50=%.1f p90=%.1f p99=%.1f max=%.1f", s.size(), sum / s.size(),
                s.get(s.size() / 2), s.get((int) (s.size() * 0.9)), s.get(Math.min(s.size() - 1, (int) (s.size() * 0.99))),
                s.get(s.size() - 1));
    }

    private static void write(String text) {
        try (PrintWriter w = new PrintWriter(System.getenv("TEMP") + "\\uyap_bench.txt", "UTF-8")) {
            w.println(text);
        } catch (Exception ignored) {}
    }
}
