package uyapmobil;

import java.awt.AWTEvent;
import java.awt.Component;
import java.awt.EventQueue;
import java.awt.KeyboardFocusManager;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.event.InputEvent;
import java.awt.event.KeyEvent;
import java.awt.image.BufferedImage;
import java.awt.image.DataBufferInt;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.RandomAccessFile;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteOrder;
import java.nio.IntBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * UYAP Mobil ekran köprüsü (-javaagent). X sunucusu olmadan (Caciocavallo) çalışan resmi UYAP Doküman Editörü'nün
 * ekranını Android uygulamasına aktarır ve dokunma/klavye olaylarını editöre iletir.
 *
 * Ekran: CTCScreen'in bellek tamponu her karede satır satır karşılaştırılır; yalnızca değişen satır aralığı paylaşılan
 * bellek dosyasına (uyapmobil.ekran) yazılır. Başlık (int): [0]=sihir 0x55594D31 [1]=genişlik [2]=yükseklik
 * [3]=kare no [4]=y0 [5]=y1 (değişen aralık, y1 hariç) ; [16..] piksel (ARGB, yerel bayt sırası).
 * Android kare no değişince [y0,y1) aralığını okur.
 *
 * Denetim (127.0.0.1, uyapmobil.port; ilk satır "AUTH jeton"):
 *   M x y | D x y düğme | U x y düğme | W x y adım | T metin(hex UTF-8) | K tuşKodu basılı(1/0) değiştiriciler | P yol.png
 */
public final class Kopru {
    static final int SIHIR = 0x55594D31, BASLIK = 16;
    private static volatile BufferedImage ekran;
    /** Köprü günlüğü: editör System.err'i kendi günlüğüne yönlendirebildiği için ayrı dosya (uyapmobil.gunluk). */
    static final java.io.PrintStream LOG = gunluk();

    private static java.io.PrintStream gunluk() {
        String g = System.getProperty("uyapmobil.gunluk");
        if (g != null) {
            try { return new java.io.PrintStream(new java.io.FileOutputStream(g, true), true, "UTF-8"); } catch (Exception ignored) { }
        }
        return System.err;
    }

    public static void premain(String args, Instrumentation inst) {
        Thread t = new Thread(Kopru::calis, "uyapmobil-kopru");
        t.setDaemon(true);
        t.start();
    }

    private static void calis() {
        try {
            // AWT/Cacio kurulana kadar bekle (editör ilk pencereyi açınca ekran nesnesi oluşur)
            BufferedImage img = null;
            for (int i = 0; i < 600 && img == null; i++) {
                Thread.sleep(100);
                img = ekranTamponu();
            }
            if (img == null) { LOG.println("[uyapmobil] Cacio ekranı bulunamadı"); return; }
            ekran = img;
            pencereleriOturt(img.getWidth(), img.getHeight());
            yaziTipiEslestir();
            LOG.println("[uyapmobil] ekran " + img.getWidth() + "x" + img.getHeight());
            String port = System.getProperty("uyapmobil.port");
            if (port != null) {
                Thread d = new Thread(() -> denetim(Integer.parseInt(port), System.getProperty("uyapmobil.jeton", "")), "uyapmobil-denetim");
                d.setDaemon(true);
                d.start();
            }
            String yol = System.getProperty("uyapmobil.ekran");
            if (yol != null) kareDongusu(img, new File(yol));
        } catch (Throwable e) {
            LOG.println("[uyapmobil] köprü hatası: " + e);
            e.printStackTrace();
        }
    }

    /** CTCScreen.getInstance().screenBuffer (Cacio 1.11 / 1.18 aynı paket). AWT daha başlamadıysa null. */
    static BufferedImage ekranTamponu() {
        try {
            if (!(Toolkit.getDefaultToolkit().getClass().getName().contains("caciocavallo"))) return null;
            Class<?> c = Class.forName("com.github.caciocavallosilano.cacio.ctc.CTCScreen");
            Method m = c.getDeclaredMethod("getInstance");
            m.setAccessible(true);
            Object s = m.invoke(null);
            Field f = c.getDeclaredField("screenBuffer");
            f.setAccessible(true);
            return (BufferedImage) f.get(s);
        } catch (Throwable e) {
            return null;
        }
    }

    private static void kareDongusu(BufferedImage img, File dosya) throws Exception {
        int w = img.getWidth(), h = img.getHeight();
        int[] px = ((DataBufferInt) img.getRaster().getDataBuffer()).getData();
        int[] once = new int[px.length];
        Arrays.fill(once, 1);    // ilk karede her şey "değişmiş" sayılır
        long boyut = 4L * (BASLIK + (long) w * h);
        try (RandomAccessFile raf = new RandomAccessFile(dosya, "rw"); FileChannel ch = raf.getChannel()) {
            raf.setLength(boyut);
            MappedByteBuffer mb = ch.map(FileChannel.MapMode.READ_WRITE, 0, boyut);
            mb.order(ByteOrder.nativeOrder());
            IntBuffer ib = mb.asIntBuffer();
            ib.put(1, w).put(2, h).put(0, SIHIR);
            int kare = 0;
            long hedefNs = 1_000_000_000L / Integer.getInteger("uyapmobil.fps", 60);
            while (true) {
                long t0 = System.nanoTime();
                int y0 = -1, y1 = -1;
                for (int y = 0; y < h; y++) {
                    int o = y * w;
                    if (Arrays.mismatch(px, o, o + w, once, o, o + w) >= 0) { if (y0 < 0) y0 = y; y1 = y + 1; }
                }
                if (y0 >= 0) {
                    int o = y0 * w, n = (y1 - y0) * w;
                    System.arraycopy(px, o, once, o, n);
                    ib.position(BASLIK + o);
                    ib.put(once, o, n);
                    ib.put(4, y0).put(5, y1).put(3, ++kare);   // kare no en son: okuyan taraf tutarlı aralığı görür
                }
                long kalan = hedefNs - (System.nanoTime() - t0);
                if (kalan > 0) Thread.sleep(kalan / 1_000_000, (int) (kalan % 1_000_000));
            }
        }
    }

    /** Mobil: ana çerçeveler (Frame) ekranı tam kaplar; ekrandan büyük diyaloglar ekrana sığdırılıp ortalanır. */
    private static void pencereleriOturt(int w, int h) {
        java.awt.event.AWTEventListener l = e -> {
            if (e.getID() != java.awt.event.WindowEvent.WINDOW_OPENED && e.getID() != java.awt.event.ComponentEvent.COMPONENT_RESIZED
                    && e.getID() != java.awt.event.ComponentEvent.COMPONENT_SHOWN) return;
            Object src = e.getSource();
            if (!(src instanceof Window)) return;
            Window win = (Window) src;
            java.awt.Rectangle b = win.getBounds();
            if (win instanceof java.awt.Frame) {
                if (b.x != 0 || b.y != 0 || b.width != w || b.height != h) EventQueue.invokeLater(() -> { win.setBounds(0, 0, w, h); yenidenCiz(win); });
            } else if (b.width > w || b.height > h || b.x < 0 || b.y < 0 || b.x + b.width > w || b.y + b.height > h) {
                int nw = Math.min(b.width, w), nh = Math.min(b.height, h);
                EventQueue.invokeLater(() -> { win.setBounds((w - nw) / 2, (h - nh) / 2, nw, nh); yenidenCiz(win); });
            }
        };
        Toolkit.getDefaultToolkit().addAWTEventListener(l, AWTEvent.WINDOW_EVENT_MASK | AWTEvent.COMPONENT_EVENT_MASK);
        EventQueue.invokeLater(() -> {
            for (Window win : Window.getWindows()) if (win.isShowing() && win instanceof java.awt.Frame) { win.setBounds(0, 0, w, h); yenidenCiz(win); }
        });
        panoIzle();
    }

    /**
     * Belgelerdeki Windows yazı tipleri cihazda yoksa ölçüleri birebir aynı Liberation yazı tipleriyle çizilir
     * (satır/sayfa kırılımları değişmez). Kullanıcı gerçek yazı tiplerini (~/.fonts) eklediyse eşleme yapılmaz.
     * JDK: SunFontManager.findFont2D önce fontNameCache'e "ad.stil" anahtarıyla bakar.
     */
    static void yaziTipiEslestir() {
        String[][] es = {{"Times New Roman", "Liberation Serif"}, {"Arial", "Liberation Sans"}, {"Courier New", "Liberation Mono"},
                {"Tahoma", "Liberation Sans"}, {"Verdana", "Liberation Sans"}, {"Calibri", "Liberation Sans"},
                {"Cambria", "Liberation Serif"}, {"Georgia", "Liberation Serif"}, {"Times", "Liberation Serif"}};
        String[] stil = {".plain", ".bold", ".italic", ".bolditalic"};
        try {
            Class<?> fu = Class.forName("sun.font.FontUtilities");
            Method getFont2D = fu.getMethod("getFont2D", java.awt.Font.class);
            Class<?> sfm = Class.forName("sun.font.SunFontManager");
            Object fm = sfm.getMethod("getInstance").invoke(null);
            Field cf = sfm.getDeclaredField("fontNameCache");
            cf.setAccessible(true);
            @SuppressWarnings("unchecked") java.util.Map<String, Object> cache = (java.util.Map<String, Object>) cf.get(fm);
            java.util.Set<String> aileler = new java.util.HashSet<>();
            for (String a : java.awt.GraphicsEnvironment.getLocalGraphicsEnvironment().getAvailableFontFamilyNames(java.util.Locale.ENGLISH))
                aileler.add(a.toLowerCase(java.util.Locale.ENGLISH));
            int n = 0;
            for (String[] e : es) {
                if (aileler.contains(e[0].toLowerCase(java.util.Locale.ENGLISH)) || !aileler.contains(e[1].toLowerCase(java.util.Locale.ENGLISH))) continue;
                for (int st = 0; st < 4; st++) {
                    Object f2d = getFont2D.invoke(null, new java.awt.Font(e[1], st, 12));
                    cache.put(e[0].toLowerCase(java.util.Locale.ENGLISH) + stil[st], f2d);
                }
                n++;
            }
            LOG.println("[uyapmobil] yazı tipi eşlemesi: " + n + " aile (Liberation)");
        } catch (Throwable t) {
            LOG.println("[uyapmobil] yazı tipi eşlemesi yapılamadı: " + t);
        }
    }

    /** Cacio pencere boyutu değişince kendiliğinden yeniden düzenleyip çizmiyor: elle tetiklenir. */
    static void yenidenCiz(Window win) {
        win.invalidate();
        win.validate();
        win.repaint();
    }

    // ------------------------------------------------------------------------------------ pano + istemciler
    private static final java.util.List<OutputStream> ISTEMCILER = new java.util.concurrent.CopyOnWriteArrayList<>();

    /** Köprüden Android'e bildirim satırı (ör. "PANO <hex>"). */
    static void bildir(String satir) {
        byte[] b = (satir + "\n").getBytes(StandardCharsets.UTF_8);
        for (OutputStream o : ISTEMCILER) {
            try { synchronized (o) { o.write(b); o.flush(); } } catch (Exception e) { ISTEMCILER.remove(o); }
        }
    }

    /** Editörde Kopyala/Kes yapılınca metin Android panosuna da gider. */
    private static void panoIzle() {
        try {
            java.awt.datatransfer.Clipboard c = Toolkit.getDefaultToolkit().getSystemClipboard();
            c.addFlavorListener(e -> {
                try {
                    Object v = c.getData(java.awt.datatransfer.DataFlavor.stringFlavor);
                    if (v instanceof String && !((String) v).equals(sonPano)) {
                        sonPano = (String) v;
                        bildir("PANO " + hex(((String) v).getBytes(StandardCharsets.UTF_8)));
                    }
                } catch (Exception ignored) { }
            });
        } catch (Exception e) {
            LOG.println("[uyapmobil] pano izlenemiyor: " + e);
        }
    }
    private static volatile String sonPano;

    static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) sb.append(Character.forDigit((x >> 4) & 15, 16)).append(Character.forDigit(x & 15, 16));
        return sb.toString();
    }

    static boolean modalAcik() {
        for (Window w : Window.getWindows())
            if (w.isShowing() && w instanceof java.awt.Dialog && ((java.awt.Dialog) w).isModal()) return true;
        return false;
    }

    /** Çalışan editörde yeni belge aç (resmi editörün kendi giriş noktası: WPAppManager getNewWPInstance). */
    static void belgeAc(String yol) {
        Thread t = new Thread(() -> {
            try {
                // Açık bir modal pencere (ör. açılıştaki "Son sürümlerde yapılan güncellemeler") kapanana kadar bekle:
                // modal pencere açıkken yeni belge penceresi engelleniyor.
                for (int i = 0; i < 600 && modalAcik(); i++) Thread.sleep(200);
                String tip = yol.toLowerCase(java.util.Locale.ROOT).endsWith(".usf") ? "EDITOR_TYPE_TEMPLATE" : "EDITOR_TYPE_DOCUMENT";
                Class<?> c = Class.forName("tr.com.havelsan.uyap.system.editor.common.WPAppManager", true, ClassLoader.getSystemClassLoader());
                c.getMethod("main", String[].class).invoke(null, (Object) new String[]{"getNewWPInstance", tip, yol});
                LOG.println("[uyapmobil] belge açıldı: " + yol);
            } catch (Throwable e) {
                LOG.println("[uyapmobil] belge açılamadı: " + e);
            }
        }, "uyapmobil-belge");
        t.setDaemon(true);
        t.start();
    }

    // ------------------------------------------------------------------------------------ olaylar
    private static void denetim(int port, String jeton) {
        try (ServerSocket ss = new ServerSocket(port, 4, InetAddress.getByName("127.0.0.1"))) {
            LOG.println("[uyapmobil] denetim 127.0.0.1:" + port);
            while (true) {
                Socket s = ss.accept();
                Thread t = new Thread(() -> istemci(s, jeton), "uyapmobil-istemci");
                t.setDaemon(true);
                t.start();
            }
        } catch (Exception e) {
            LOG.println("[uyapmobil] denetim hatası: " + e);
        }
    }

    private static void istemci(Socket s, String jeton) {
        try (Socket so = s; BufferedReader in = new BufferedReader(new InputStreamReader(so.getInputStream(), StandardCharsets.UTF_8));
             OutputStream out = so.getOutputStream()) {
            String ilk = in.readLine();
            if (ilk == null || !ilk.equals("AUTH " + jeton)) { out.write("ERR\n".getBytes()); return; }
            out.write("OK\n".getBytes());
            out.flush();
            ISTEMCILER.add(out);
            String satir;
            while ((satir = in.readLine()) != null) {
                try { isle(satir.trim()); } catch (Exception e) { LOG.println("[uyapmobil] komut hatası '" + satir + "': " + e); }
            }
        } catch (Exception ignored) { }
    }

    /** Cacio'nun Robot eşi (CTCRobotPeer) doğrudan, yansımayla: java.awt.Robot JDK 14'te Cacio 1.11 ile HeadlessException veriyor. */
    private static final class Fare {
        final Object eş;
        final Method hareket, bas, birak, teker;
        Fare() throws Exception {
            Class<?> c = Class.forName("com.github.caciocavallosilano.cacio.ctc.CTCRobotPeer");
            java.lang.reflect.Constructor<?> k = c.getDeclaredConstructor();
            k.setAccessible(true);
            eş = k.newInstance();
            hareket = c.getMethod("mouseMove", int.class, int.class);
            bas = c.getMethod("mousePress", int.class);
            birak = c.getMethod("mouseRelease", int.class);
            teker = c.getMethod("mouseWheel", int.class);
            for (Method m : new Method[]{hareket, bas, birak, teker}) m.setAccessible(true);
        }
        void mouseMove(int x, int y) throws Exception { hareket.invoke(eş, x, y); }
        void mousePress(int b) throws Exception { bas.invoke(eş, b); }
        void mouseRelease(int b) throws Exception { birak.invoke(eş, b); }
        void mouseWheel(int n) throws Exception { teker.invoke(eş, n); }
    }
    private static volatile Fare fare;

    private static Fare robot() throws Exception {
        if (fare == null) fare = new Fare();
        return fare;
    }

    private static int dugme(String b) {
        switch (b) {
            case "3": return InputEvent.BUTTON3_DOWN_MASK;
            case "2": return InputEvent.BUTTON2_DOWN_MASK;
            default: return InputEvent.BUTTON1_DOWN_MASK;
        }
    }

    static void isle(String c) throws Exception {
        if (c.isEmpty()) return;
        String[] p = c.split(" ");
        switch (p[0]) {
            case "M": robot().mouseMove(Integer.parseInt(p[1]), Integer.parseInt(p[2])); break;
            case "D": robot().mouseMove(Integer.parseInt(p[1]), Integer.parseInt(p[2])); robot().mousePress(dugme(p[3])); break;
            case "U": robot().mouseMove(Integer.parseInt(p[1]), Integer.parseInt(p[2])); robot().mouseRelease(dugme(p[3])); break;
            case "W": robot().mouseMove(Integer.parseInt(p[1]), Integer.parseInt(p[2])); robot().mouseWheel(Integer.parseInt(p[3])); break;
            case "T": yaz(new String(unhex(p[1]), StandardCharsets.UTF_8)); break;
            case "K": tus(Integer.parseInt(p[1]), "1".equals(p[2]), p.length > 3 ? Integer.parseInt(p[3]) : 0); break;
            case "P": javax.imageio.ImageIO.write(ekran, "png", new File(c.substring(2))); break;
            case "O": belgeAc(new String(unhex(p[1]), StandardCharsets.UTF_8)); break;
            case "Y": {   // Android panosundaki metni editör panosuna koy (ardından Ctrl+V gönderilir)
                String m = new String(unhex(p.length > 1 ? p[1] : ""), StandardCharsets.UTF_8);
                sonPano = m;
                Toolkit.getDefaultToolkit().getSystemClipboard().setContents(new java.awt.datatransfer.StringSelection(m), null);
                break;
            }
            case "X":     // kapat: ana pencerelere WINDOW_CLOSING (editör "kaydedilsin mi?" diye sorar)
                EventQueue.invokeLater(() -> {
                    for (Window w : Window.getWindows())
                        if (w.isShowing() && w instanceof java.awt.Frame)
                            gonder(new java.awt.event.WindowEvent(w, java.awt.event.WindowEvent.WINDOW_CLOSING));
                });
                break;
            case "L":   // tanı: açık pencereler ve odak
                for (Window w : Window.getWindows())
                    LOG.println("[uyapmobil] pencere " + w.getClass().getName() + " görünür=" + w.isShowing() + " " + w.getBounds() + " odak=" + w.isFocused());
                LOG.println("[uyapmobil] odak bileşeni: " + odak());
                break;
            case "R":   // tanı: tüm pencereleri yeniden düzenle ve çiz
                EventQueue.invokeLater(() -> { for (Window w : Window.getWindows()) if (w.isShowing()) { w.invalidate(); w.validate(); w.repaint(); } });
                break;
            case "G":   // tanı: fare/tuş olaylarını günlüğe yaz
                Toolkit.getDefaultToolkit().addAWTEventListener(e -> LOG.println("[uyapmobil] olay " + e.paramString() + " @ " + e.getSource().getClass().getSimpleName()),
                        AWTEvent.MOUSE_EVENT_MASK | AWTEvent.KEY_EVENT_MASK);
                break;
            default: break;
        }
    }

    private static Component odak() {
        Component f = KeyboardFocusManager.getCurrentKeyboardFocusManager().getFocusOwner();
        if (f == null) {
            Window a = KeyboardFocusManager.getCurrentKeyboardFocusManager().getActiveWindow();
            f = a;
        }
        return f;
    }

    private static void gonder(AWTEvent e) { Toolkit.getDefaultToolkit().getSystemEventQueue().postEvent(e); }

    /** Türkçe dahil her karakter KEY_TYPED olarak odaktaki bileşene (Robot tuş haritası gerektirmez). */
    static void yaz(String metin) {
        EventQueue.invokeLater(() -> {
            Component f = odak();
            if (f == null) return;
            long t = System.currentTimeMillis();
            metin.codePoints().forEach(cp -> {
                for (char ch : Character.toChars(cp)) {
                    if (ch == '\n') { tusOlay(f, KeyEvent.VK_ENTER, 0, t); continue; }
                    gonder(new KeyEvent(f, KeyEvent.KEY_TYPED, t, 0, KeyEvent.VK_UNDEFINED, ch));
                }
            });
        });
    }

    private static void tusOlay(Component f, int kod, int mod, long t) {
        char ch = kod == KeyEvent.VK_ENTER ? '\n' : kod == KeyEvent.VK_BACK_SPACE ? '\b' : kod == KeyEvent.VK_TAB ? '\t' : KeyEvent.CHAR_UNDEFINED;
        gonder(new KeyEvent(f, KeyEvent.KEY_PRESSED, t, mod, kod, ch));
        if (ch != KeyEvent.CHAR_UNDEFINED && (mod & (InputEvent.CTRL_DOWN_MASK | InputEvent.ALT_DOWN_MASK)) == 0)
            gonder(new KeyEvent(f, KeyEvent.KEY_TYPED, t, mod, KeyEvent.VK_UNDEFINED, ch));
        gonder(new KeyEvent(f, KeyEvent.KEY_RELEASED, t, mod, kod, ch));
    }

    /** Özel tuşlar (Enter, Sil, oklar, Ctrl+S ...). basili=false gelirse yalnızca bırakma olayı. */
    static void tus(int kod, boolean basili, int mod) {
        EventQueue.invokeLater(() -> {
            Component f = odak();
            if (f == null) return;
            long t = System.currentTimeMillis();
            if (basili) tusOlay(f, kod, mod, t);
        });
    }

    static byte[] unhex(String s) {
        byte[] b = new byte[s.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        return b;
    }

    private Kopru() { }
}
