package uyaptermux;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Component;
import java.awt.Cursor;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.GridLayout;
import java.awt.Insets;
import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.JButton;
import javax.swing.JCheckBox;
import javax.swing.JColorChooser;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JFileChooser;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JSpinner;
import javax.swing.JTabbedPane;
import javax.swing.JTextArea;
import javax.swing.SpinnerNumberModel;
import javax.swing.SwingUtilities;
import javax.swing.SwingWorker;
import javax.swing.Timer;
import javax.swing.UIManager;
import javax.swing.filechooser.FileNameExtensionFilter;

/**
 * UYAP-Termux Kontrol Merkezi: editor / e-imza koprusu / Adalet E-Imza durum kartlari, tek dokunusla islemler
 * ve ayarlar.ini icin grafik ayar sayfasi. "uyap panel" ile acilir (ue.py --panel derler ve calistirir).
 * Kabuk islemleri ~/eimza ve ~/.local/bin altindaki betiklere devredilir; panel yalnizca onlari cagirir.
 */
public final class KontrolMerkezi {
    static final String HOME = System.getenv().getOrDefault("HOME", System.getProperty("user.home"));
    static final String STATE = System.getenv().getOrDefault("EIMZA_DIR", HOME + "/.eimza");
    static final File AYAR = new File(System.getenv().getOrDefault("XDG_CONFIG_HOME", HOME + "/.config"), "uyap-termux/ayarlar.ini");

    private final JFrame pencere = new JFrame("UYAP-Termux Kontrol Merkezi");
    private final Kart editorKart = new Kart("UYAP Editör");
    private final Kart okuyucuKart = new Kart("E-imza okuyucu");
    private final Kart adaletKart = new Kart("Adalet E-İmza");
    private final Kart javaKart = new Kart("Java / jar'lar");
    private final JTextArea cikti = new JTextArea(8, 40);
    private final Ini ini = Ini.oku(AYAR);

    public static void main(String[] args) {
        String tema = Ini.oku(AYAR).al("arayuz", "tema", "acik");
        if (System.getProperty("flatlaf.uiScale") == null) {
            System.setProperty("flatlaf.uiScale", String.valueOf(Baslatici.olcekHesapla(Ini.oku(AYAR).al("arayuz", "olcek", "1.2"), 0)));
        }
        try {
            String laf = Baslatici.lafSinifi(tema);
            UIManager.setLookAndFeel(laf != null ? laf : UIManager.getSystemLookAndFeelClassName());
            UIManager.put("Component.arc", 12);
            UIManager.put("Button.arc", 12);
        } catch (Throwable ignored) { }
        SwingUtilities.invokeLater(() -> new KontrolMerkezi().goster());
    }

    // ------------------------------------------------------------------ arayuz
    private void goster() {
        JTabbedPane sekmeler = new JTabbedPane();
        sekmeler.addTab("Durum", durumSayfasi());
        sekmeler.addTab("Ayarlar", ayarSayfasi());
        sekmeler.addTab("Yardım", yardimSayfasi());
        pencere.setContentPane(sekmeler);
        pencere.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        pencere.setMinimumSize(new Dimension(560, 520));
        pencere.pack();
        pencere.setLocationRelativeTo(null);
        pencere.setVisible(true);
        yenile();
        new Timer(3000, e -> yenile()).start();
    }

    private JComponent durumSayfasi() {
        JPanel kartlar = new JPanel(new GridLayout(2, 2, 10, 10));
        kartlar.add(editorKart);
        kartlar.add(okuyucuKart);
        kartlar.add(adaletKart);
        kartlar.add(javaKart);

        JPanel dugmeler = new JPanel(new GridLayout(0, 3, 8, 8));
        dugmeler.add(dugme("Editörü aç", () -> calistir(true, HOME + "/.local/bin/uyap-editor")));
        dugmeler.add(dugme("Belge aç…", this::belgeSec));
        dugmeler.add(dugme("Okuyucuyu yeniden bağla", () -> calistir(false, "bash", HOME + "/eimza/eimza_baslat.sh")));
        dugmeler.add(dugme("Adalet'i yeniden başlat", () -> calistir(false, "bash", HOME + "/eimza/adalet_baslat.sh", "restart", "--ekran")));
        dugmeler.add(dugme("Adalet'i durdur", () -> calistir(false, "bash", HOME + "/eimza/adalet_baslat.sh", "stop")));
        dugmeler.add(dugme("Okuyucu tanısı", () -> calistir(false, "bash", HOME + "/eimza/eimza_tani.sh")));
        dugmeler.add(dugme("Yedek al", () -> calistir(false, "bash", HOME + "/yedek_al.sh", "panel")));
        dugmeler.add(dugme("Times New Roman kur", () -> calistir(false, HOME + "/.local/bin/uyap", "yazitipi")));
        dugmeler.add(dugme("Günlükler", () -> calistir(false, HOME + "/.local/bin/uyap", "gunluk")));

        cikti.setEditable(false);
        cikti.setFont(new Font(Font.MONOSPACED, Font.PLAIN, cikti.getFont().getSize()));
        cikti.setText("Bir işlem seçin; çıktısı burada görünür.\n");
        JScrollPane ciktiKaydir = new JScrollPane(cikti);
        ciktiKaydir.setBorder(BorderFactory.createTitledBorder("Çıktı"));

        JPanel ust = new JPanel(new BorderLayout(0, 12));
        ust.add(kartlar, BorderLayout.NORTH);
        ust.add(dugmeler, BorderLayout.CENTER);
        JPanel p = new JPanel(new BorderLayout(0, 12));
        p.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12));
        p.add(ust, BorderLayout.NORTH);
        p.add(ciktiKaydir, BorderLayout.CENTER);
        return p;
    }

    private JComponent ayarSayfasi() {
        Secenek[] temalar = {new Secenek("acik", "Açık (IntelliJ)"), new Secenek("koyu", "Koyu (Darcula)"),
                new Secenek("macos-acik", "macOS açık"), new Secenek("macos-koyu", "macOS koyu"),
                new Secenek("sistem", "Sistem (FlatLaf kapalı)")};
        JComboBox<Secenek> tema = new JComboBox<>(temalar);
        String secili = ini.al("arayuz", "tema", "acik");
        for (Secenek t : temalar) if (t.deger.equalsIgnoreCase(secili)) tema.setSelectedItem(t);
        JComboBox<String> olcek = new JComboBox<>(new String[]{"otomatik", "1.0", "1.2", "1.25", "1.5", "1.75", "2.0", "2.5"});
        olcek.setEditable(true);
        olcek.setSelectedItem(ini.al("arayuz", "olcek", "1.2"));
        JCheckBox dokunmatik = new JCheckBox("Parmakla kullanım (kalın kaydırma çubuğu, geniş menüler)", evet(ini.al("arayuz", "dokunmatik", "hayir")));
        final String[] vurgu = {ini.al("arayuz", "vurgu", "")};
        JButton vurguDugme = new JButton(vurgu[0].isEmpty() ? "Tema rengi" : vurgu[0]);
        vurguDugme.addActionListener(e -> {
            Color c = JColorChooser.showDialog(pencere, "Vurgu rengi", vurgu[0].isEmpty() ? new Color(0x2675BF) : Color.decode(vurgu[0]));
            if (c != null) {
                vurgu[0] = String.format("#%02X%02X%02X", c.getRed(), c.getGreen(), c.getBlue());
                vurguDugme.setText(vurgu[0]);
            }
        });
        JButton vurguSifirla = new JButton("Sıfırla");
        vurguSifirla.addActionListener(e -> { vurgu[0] = ""; vurguDugme.setText("Tema rengi"); });
        JCheckBox akici = new JCheckBox("Akıcı kaydırma (editörde F9 ile anında aç/kapa)", evet(ini.al("kaydirma", "akici", "evet")));
        JSpinner adim = new JSpinner(new SpinnerNumberModel(sayi(ini.al("kaydirma", "adim", "75"), 75), 20, 300, 5));
        JComboBox<String> bellek = new JComboBox<>(new String[]{"otomatik", "768", "1024", "1536", "2048", "3072", "4096"});
        bellek.setEditable(true);
        bellek.setSelectedItem(ini.al("java", "bellek", "otomatik"));
        JCheckBox eimza = new JCheckBox("Editörde USB e-imza köprüsünü kullan", evet(ini.al("eimza", "aktif", "evet")));

        JPanel f = new JPanel(new GridBagLayout());
        f.setBorder(BorderFactory.createEmptyBorder(16, 16, 16, 16));
        int y = 0;
        y = satir(f, y, "Tema", tema);
        y = satir(f, y, "Arayüz ölçeği", olcek);
        y = satir(f, y, "", dokunmatik);
        JPanel vp = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
        vp.add(vurguDugme);
        vp.add(vurguSifirla);
        y = satir(f, y, "Vurgu rengi", vp);
        y = satir(f, y, "", akici);
        y = satir(f, y, "Tekerlek adımı (px)", adim);
        y = satir(f, y, "Java belleği (MB)", bellek);
        y = satir(f, y, "", eimza);

        JButton kaydet = new JButton("Kaydet");
        kaydet.putClientProperty("JButton.buttonType", "default");
        kaydet.addActionListener(e -> {
            ini.koy("arayuz", "tema", ((Secenek) tema.getSelectedItem()).deger);
            ini.koy("arayuz", "olcek", String.valueOf(olcek.getSelectedItem()).trim());
            ini.koy("arayuz", "dokunmatik", dokunmatik.isSelected() ? "evet" : "hayir");
            ini.koy("arayuz", "vurgu", vurgu[0]);
            ini.koy("kaydirma", "akici", akici.isSelected() ? "evet" : "hayir");
            ini.koy("kaydirma", "adim", String.valueOf(adim.getValue()));
            ini.koy("java", "bellek", String.valueOf(bellek.getSelectedItem()).trim());
            ini.koy("eimza", "aktif", eimza.isSelected() ? "evet" : "hayir");
            try {
                ini.yaz(AYAR);
                JOptionPane.showMessageDialog(pencere, "Kaydedildi. Editörü kapatıp yeniden açınca geçerli olur.",
                        "Ayarlar", JOptionPane.INFORMATION_MESSAGE);
            } catch (IOException ex) {
                JOptionPane.showMessageDialog(pencere, "Kaydedilemedi: " + ex.getMessage(), "Ayarlar", JOptionPane.ERROR_MESSAGE);
            }
        });
        GridBagConstraints g = new GridBagConstraints();
        g.gridx = 1; g.gridy = y; g.anchor = GridBagConstraints.EAST; g.insets = new Insets(16, 0, 0, 0);
        f.add(kaydet, g);
        g = new GridBagConstraints();
        g.gridy = y + 1; g.weighty = 1;
        f.add(Box.createGlue(), g);
        return new JScrollPane(f);
    }

    private JComponent yardimSayfasi() {
        JTextArea t = new JTextArea(
                "Kısayollar (editörde)\n"
              + "  F9               akıcı kaydırmayı aç/kapa\n"
              + "  Ctrl+Shift+F12   UYAP-Termux bilgisi\n"
              + "  Ctrl+tekerlek    editörün kendi yakınlaştırması\n\n"
              + "Terminal komutları\n"
              + "  uyap              menü\n"
              + "  uyap masaustu     Termux:X11 masaüstü\n"
              + "  uyap editor X.udf belgeyi aç (.usf şablon editöründe açılır)\n"
              + "  uyap durum        durum özeti\n"
              + "  uyap tani         sorun giderme raporu (panoya kopyalanır)\n\n"
              + "E-imza ile UYAP Avukat Portal\n"
              + "  1) Okuyucuyu OTG ile takın, Android'in izin sorusuna \"İzin ver\" deyin.\n"
              + "  2) \"E-imza okuyucu\" kartı yeşil olmalı; \"Adalet E-İmza\" kartı da yeşil olmalı.\n"
              + "  3) Telefonun Chrome'unda portala e-imza ile girin; \"yerel ağ\" izni sorulursa verin.\n\n"
              + "Ayar dosyası: " + AYAR + "\n");
        t.setEditable(false);
        t.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12));
        return new JScrollPane(t);
    }

    private static int satir(JPanel f, int y, String etiket, JComponent c) {
        GridBagConstraints g = new GridBagConstraints();
        g.gridx = 0; g.gridy = y; g.anchor = GridBagConstraints.WEST; g.insets = new Insets(6, 0, 6, 16);
        f.add(new JLabel(etiket), g);
        g = new GridBagConstraints();
        g.gridx = 1; g.gridy = y; g.anchor = GridBagConstraints.WEST; g.fill = GridBagConstraints.HORIZONTAL; g.weightx = 1;
        g.insets = new Insets(6, 0, 6, 0);
        f.add(c, g);
        return y + 1;
    }

    private JButton dugme(String ad, Runnable r) {
        JButton b = new JButton(ad);
        b.setCursor(Cursor.getPredefinedCursor(Cursor.HAND_CURSOR));
        b.addActionListener(e -> r.run());
        return b;
    }

    private void belgeSec() {
        JFileChooser fc = new JFileChooser(new File(HOME, "storage/downloads").isDirectory() ? new File(HOME, "storage/downloads") : new File(HOME));
        fc.setFileFilter(new FileNameExtensionFilter("UYAP belgeleri (*.udf, *.usf)", "udf", "usf"));
        if (fc.showOpenDialog(pencere) == JFileChooser.APPROVE_OPTION) {
            calistir(true, HOME + "/.local/bin/uyap-editor", fc.getSelectedFile().getAbsolutePath());
        }
    }

    /** Komutu arka planda calistirir; arkaPlan=false ise ciktisini panele yazar. */
    private void calistir(boolean arkaPlan, String... komut) {
        cikti.setText("$ " + String.join(" ", komut) + "\n");
        new SwingWorker<Integer, String>() {
            @Override protected Integer doInBackground() throws Exception {
                ProcessBuilder pb = new ProcessBuilder(komut).redirectErrorStream(true);
                pb.environment().putIfAbsent("DISPLAY", ":0");
                Process p = pb.start();
                p.getOutputStream().close();
                if (arkaPlan) {
                    publish("başlatıldı.\n");
                    return 0;
                }
                try (BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
                    String s;
                    while ((s = br.readLine()) != null) publish(s.replaceAll("\u001b\\[[0-9;]*m", "") + "\n");
                }
                return p.waitFor();
            }
            @Override protected void process(List<String> parcalar) {
                for (String s : parcalar) cikti.append(s);
                cikti.setCaretPosition(cikti.getDocument().getLength());
            }
            @Override protected void done() {
                try {
                    Integer rc = get();
                    if (!arkaPlan) cikti.append(rc == 0 ? "\n✔ tamamlandı\n" : "\n✖ çıkış kodu " + rc + "\n");
                } catch (Exception e) {
                    cikti.append("\n✖ " + e.getCause() + "\n");
                }
                yenile();
            }
        }.execute();
    }

    // ------------------------------------------------------------------ durum
    private void yenile() {
        new SwingWorker<Durum, Void>() {
            @Override protected Durum doInBackground() { return Durum.topla(); }
            @Override protected void done() {
                try {
                    Durum d = get();
                    editorKart.ayarla(d.editorAcik ? Seviye.IYI : Seviye.BILGI, d.editorAcik ? "Açık" : "Kapalı");
                    if (!d.izleyici) okuyucuKart.ayarla(Seviye.HATA, "İzleyici kapalı");
                    else if (d.okuyucu != null) okuyucuKart.ayarla(Seviye.IYI, "Bağlı: " + d.okuyucu);
                    else okuyucuKart.ayarla(Seviye.UYARI, "Okuyucu takılı değil");
                    if (!d.adaletKurulu) adaletKart.ayarla(Seviye.UYARI, "Kurulu değil");
                    else adaletKart.ayarla(d.adaletPort ? Seviye.IYI : Seviye.HATA,
                            d.adaletPort ? "Çalışıyor (5975)" + (d.adaletSurum.isEmpty() ? "" : " · " + d.adaletSurum) : "Kapalı");
                    javaKart.ayarla(d.jarSayisi > 0 ? Seviye.IYI : Seviye.HATA,
                            "Java " + System.getProperty("java.specification.version") + " · " + d.jarSayisi + " jar");
                } catch (Exception ignored) { }
            }
        }.execute();
    }

    static final class Durum {
        boolean editorAcik, izleyici, adaletKurulu, adaletPort;
        String okuyucu, adaletSurum = "";
        int jarSayisi;

        static Durum topla() {
            Durum d = new Durum();
            Map<String, String> inst = ozellikler(new File(HOME, ".uyap-editor/instance.properties"));
            d.editorAcik = pidCanli(inst.get("pid"));
            d.izleyici = pidCanli(oku(new File(STATE, "izle.pid")).trim());
            String bj = oku(new File(STATE, "bridge.json"));
            Matcher m = Pattern.compile("\"name\"\\s*:\\s*\"([^\"]*)\"").matcher(bj);
            d.okuyucu = m.find() ? m.group(1) : null;
            File jar = new File(HOME, "eimza/adalet/eimza-tray.jar");
            d.adaletKurulu = jar.isFile();
            d.adaletSurum = oku(new File(HOME, "eimza/adalet/surum.txt")).trim();
            d.adaletPort = portAcik(Integer.parseInt(System.getenv().getOrDefault("EIMZA_TRAY_PORT", "5975")));
            File[] jars = new File(HOME, "jars").listFiles((dir, n) -> n.endsWith(".jar"));
            d.jarSayisi = jars == null ? 0 : jars.length;
            return d;
        }
    }

    static boolean pidCanli(String pid) {
        if (pid == null || pid.isEmpty()) return false;
        try {
            return ProcessHandle.of(Long.parseLong(pid)).map(ProcessHandle::isAlive).orElse(false);
        } catch (NumberFormatException e) {
            return false;
        }
    }

    static boolean portAcik(int port) {
        try (Socket s = new Socket()) {
            s.connect(new InetSocketAddress("127.0.0.1", port), 400);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    static String oku(File f) {
        try { return new String(Files.readAllBytes(f.toPath()), StandardCharsets.UTF_8); } catch (IOException e) { return ""; }
    }

    static Map<String, String> ozellikler(File f) {
        Map<String, String> m = new LinkedHashMap<>();
        for (String s : oku(f).split("\n")) {
            int i = s.indexOf('=');
            if (i > 0) m.put(s.substring(0, i).trim(), s.substring(i + 1).trim());
        }
        return m;
    }

    static boolean evet(String s) {
        return s != null && java.util.Arrays.asList("1", "evet", "e", "true", "yes", "on", "acik")
                .contains(s.trim().toLowerCase(Locale.ROOT));
    }

    static int sayi(String s, int vars) {
        try { return Integer.parseInt(s.trim()); } catch (Exception e) { return vars; }
    }

    static final class Secenek {
        final String deger, ad;
        Secenek(String deger, String ad) { this.deger = deger; this.ad = ad; }
        @Override public String toString() { return ad; }
    }

    // ------------------------------------------------------------------ kart
    enum Seviye {
        IYI(new Color(0x2E7D32)), UYARI(new Color(0xEF8F00)), HATA(new Color(0xC62828)), BILGI(new Color(0x607D8B));
        final Color renk;
        Seviye(Color c) { renk = c; }
    }

    static final class Kart extends JPanel {
        private final JLabel nokta = new JLabel("●");
        private final JLabel deger = new JLabel("…");

        Kart(String baslik) {
            setLayout(new BoxLayout(this, BoxLayout.Y_AXIS));
            setBorder(BorderFactory.createCompoundBorder(
                    BorderFactory.createLineBorder(UIManager.getColor("Component.borderColor") != null
                            ? UIManager.getColor("Component.borderColor") : Color.LIGHT_GRAY, 1, true),
                    BorderFactory.createEmptyBorder(10, 12, 10, 12)));
            JPanel ust = new JPanel(new FlowLayout(FlowLayout.LEFT, 6, 0));
            ust.setOpaque(false);
            nokta.setFont(nokta.getFont().deriveFont(16f));
            JLabel b = new JLabel(baslik);
            b.setFont(b.getFont().deriveFont(Font.BOLD));
            ust.add(nokta);
            ust.add(b);
            ust.setAlignmentX(Component.LEFT_ALIGNMENT);
            deger.setAlignmentX(Component.LEFT_ALIGNMENT);
            deger.setBorder(BorderFactory.createEmptyBorder(4, 6, 0, 0));
            add(ust);
            add(deger);
        }

        void ayarla(Seviye s, String metin) {
            nokta.setForeground(s.renk);
            deger.setText(metin);
            deger.setToolTipText(metin);
        }
    }

    // ------------------------------------------------------------------ INI (yorumlari ve sirayi koruyan)
    static final class Ini {
        private final List<String> satirlar = new ArrayList<>();

        static Ini oku(File f) {
            Ini i = new Ini();
            String s = KontrolMerkezi.oku(f);
            if (!s.isEmpty()) for (String l : s.split("\n", -1)) i.satirlar.add(l);
            if (!i.satirlar.isEmpty() && i.satirlar.get(i.satirlar.size() - 1).isEmpty()) i.satirlar.remove(i.satirlar.size() - 1);
            return i;
        }

        private int bolum(String b) {
            for (int k = 0; k < satirlar.size(); k++) if (satirlar.get(k).trim().equalsIgnoreCase("[" + b + "]")) return k;
            return -1;
        }

        String al(String b, String ad, String vars) {
            int i = bolum(b);
            if (i < 0) return vars;
            for (int k = i + 1; k < satirlar.size(); k++) {
                String l = satirlar.get(k).trim();
                if (l.startsWith("[")) break;
                int e = l.indexOf('=');
                if (e > 0 && !l.startsWith("#") && !l.startsWith(";") && l.substring(0, e).trim().equalsIgnoreCase(ad)) {
                    String v = l.substring(e + 1).trim();
                    int yorum = v.indexOf(';');           // ue.py ile ayni: yalnizca ';' satir ici yorum
                    return yorum >= 0 ? v.substring(0, yorum).trim() : v;
                }
            }
            return vars;
        }

        void koy(String b, String ad, String deger) {
            int i = bolum(b);
            if (i < 0) {
                if (!satirlar.isEmpty()) satirlar.add("");
                satirlar.add("[" + b + "]");
                satirlar.add(ad + " = " + deger);
                return;
            }
            int son = i;
            for (int k = i + 1; k < satirlar.size(); k++) {
                String l = satirlar.get(k).trim();
                if (l.startsWith("[")) break;
                if (!l.isEmpty()) son = k;
                int e = l.indexOf('=');
                if (e > 0 && !l.startsWith("#") && l.substring(0, e).trim().equalsIgnoreCase(ad)) {
                    satirlar.set(k, ad + " = " + deger);
                    return;
                }
            }
            satirlar.add(son + 1, ad + " = " + deger);
        }

        void yaz(File f) throws IOException {
            f.getParentFile().mkdirs();
            Files.write(f.toPath(), (String.join("\n", satirlar) + "\n").getBytes(StandardCharsets.UTF_8));
        }
    }
}
