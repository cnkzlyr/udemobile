package tr.gov.uyap.modernizer;

import javax.swing.*;
import java.awt.*;
import java.awt.event.KeyEvent;
import java.io.File;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;

public class ModernizerUI {
    public static void injectMenu(JFrame frame) {
        if (frame == null) return;
        JMenuBar mb = frame.getJMenuBar();
        if (mb == null) return;

        for (int i = 0; i < mb.getMenuCount(); i++) {
            JMenu m = mb.getMenu(i);
            if (m != null && "Modernizasyon".equals(m.getText())) {
                return;
            }
        }

        JMenu modernMenu = new JMenu("Modernizasyon");
        modernMenu.setMnemonic(KeyEvent.VK_M);

        // Smooth Scroll Toggle
        JCheckBoxMenuItem smoothItem = new JCheckBoxMenuItem("Akıcı Kaydırma (Smooth Scroll)", ModernizerConfig.isSmoothScrollEnabled());
        smoothItem.setAccelerator(KeyStroke.getKeyStroke(KeyEvent.VK_F9, 0));
        smoothItem.addActionListener(e -> {
            boolean current = smoothItem.isSelected();
            ModernizerConfig.setSmoothScrollEnabled(current);
            SmoothScroller.updateAll();
        });
        modernMenu.add(smoothItem);

        // Hz Menu
        JMenu hzMenu = new JMenu("Ekran Yenileme Hızı (Hz)");
        ButtonGroup hzGroup = new ButtonGroup();
        int[] hzOptions = {60, 90, 120, 144, 165, 240};
        for (int hz : hzOptions) {
            JRadioButtonMenuItem rb = new JRadioButtonMenuItem(hz + " Hz", ModernizerConfig.getTargetHz() == hz);
            hzGroup.add(rb);
            rb.addActionListener(e -> {
                ModernizerConfig.setTargetHz(hz);
                SmoothScroller.updateAll();
            });
            hzMenu.add(rb);
        }
        modernMenu.add(hzMenu);

        // Theme Menu
        JMenu themeMenu = new JMenu("Arayüz Teması");
        ButtonGroup themeGroup = new ButtonGroup();
        String currentTheme = ModernizerConfig.getTheme();

        String[][] themes = {
            {"Sistem Teması", "system"},
            {"Modern Açık (Flat Light)", "flat-light"},
            {"Modern Koyu (Flat Dark)", "flat-dark"}
        };

        for (String[] t : themes) {
            JRadioButtonMenuItem rb = new JRadioButtonMenuItem(t[0], currentTheme.equalsIgnoreCase(t[1]));
            themeGroup.add(rb);
            rb.addActionListener(e -> {
                ModernizerConfig.setTheme(t[1]);
                ThemeManager.applyTheme(t[1]);
            });
            themeMenu.add(rb);
        }
        modernMenu.add(themeMenu);

        modernMenu.addSeparator();

        // E-Imza Diagnostic Tool
        JMenuItem eimzaDiag = new JMenuItem("E-İmza & Kart Teşhisi...");
        eimzaDiag.addActionListener(e -> showEimzaDiagnostics(frame));
        modernMenu.add(eimzaDiag);

        // About
        JMenuItem aboutItem = new JMenuItem("Modern Editör Hakkında");
        aboutItem.addActionListener(e -> {
            JOptionPane.showMessageDialog(frame,
                    "UYAP Editör Modernizer v2.1.0\n" +
                    "Geliştirici: Can Kızılyar (github.com/cnkzlyr)\n\n" +
                    "Özellikler:\n" +
                    "• 120Hz/240Hz Donanım Uyumlu Akıcı Kaydırma (F9)\n" +
                    "• Çift Tıklama ile .udf ve .usf Belge/Şablon Otomatik Açma\n" +
                    "• Otomatik Çift E-İmza Desteği (Arkİmza, TBB ACR39U, AKİS)\n" +
                    "• Lisans ve Akıllı Kart Çözümleyici Entegrasyonu\n" +
                    "• Modern FlatLaf Temaları ve HiDPI Optimizasyonu",
                    "UYAP Editör Modernizer", JOptionPane.INFORMATION_MESSAGE);
        });
        modernMenu.add(aboutItem);

        mb.add(modernMenu);
        mb.revalidate();
        mb.repaint();
    }

    private static void showEimzaDiagnostics(JFrame parent) {
        StringBuilder sb = new StringBuilder();
        sb.append("=== E-İMZA VE AKILLI KART DURUMU ===\n\n");

        try {
            Class<?> scmClass = Class.forName("tr.com.havelsan.uyap.system.editor.common.pki.SmartCardManager");
            Method m = scmClass.getMethod("b");
            List<?> certs = (List<?>) m.invoke(null);

            if (certs == null || certs.isEmpty()) {
                sb.append("Bağlı e-imza kartı bulunamadı.\n");
                sb.append("Lütfen token/kart okuyucunuzun takılı olduğundan ve sürücülerin çalıştığından emin olun.");
            } else {
                sb.append("Tespit edilen sertifikalar (").append(certs.size()).append(" adet):\n\n");
                int idx = 1;
                for (Object c : certs) {
                    sb.append("[").append(idx++).append("] ").append(c.toString().trim()).append("\n\n");
                }
            }
        } catch (Throwable t) {
            sb.append("Kart sorgulanırken hata oluştu:\n").append(t.toString());
        }

        JTextArea ta = new JTextArea(sb.toString(), 18, 55);
        ta.setEditable(false);
        ta.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        JScrollPane sp = new JScrollPane(ta);

        JOptionPane.showMessageDialog(parent, sp, "E-İmza Teşhis Paneli", JOptionPane.INFORMATION_MESSAGE);
    }

    public static void applyWindowMetadata(JFrame frame, String appName) {
        if (frame == null) return;

        // 1. Peer üzerinden WM_CLASS zorla ayarla (X11 / GNOME dock eşleşmesi için)
        try {
            Field peerField = Component.class.getDeclaredField("peer");
            peerField.setAccessible(true);
            Object peer = peerField.get(frame);
            if (peer != null) {
                Method setWMClass = peer.getClass().getMethod("setWMClass", String[].class);
                setWMClass.invoke(peer, (Object) new String[]{appName, appName});
            }
        } catch (Throwable ignored) {
        }

        // 2. Yüksek çözünürlüklü pencere ikonlarını frame'e uygula
        try {
            List<Image> icons = loadAppIcons(appName);
            if (!icons.isEmpty()) {
                frame.setIconImages(icons);
            }
        } catch (Throwable ignored) {
        }
    }

    private static List<Image> loadAppIcons(String appName) {
        List<Image> list = new ArrayList<>();
        int[] sizes = {16, 32, 48, 64, 128, 256};
        String prefix = "sablon".contains(appName) ? "application-usf" : "application-udf";

        // 1. JAR içi /icons/ kaynaklarından oku
        for (int size : sizes) {
            try {
                InputStream in = ModernizerUI.class.getResourceAsStream("/icons/" + prefix + "-" + size + ".png");
                if (in != null) {
                    Image img = ImageIO.read(in);
                    if (img != null) list.add(img);
                }
            } catch (Throwable ignored) {
            }
        }

        // 2. Yerel sistem dizinlerinden oku
        if (list.isEmpty()) {
            String home = System.getProperty("user.home");
            String[] baseDirs = {
                home + "/.local/share/icons/hicolor",
                "/usr/share/icons/hicolor"
            };
            for (int size : sizes) {
                for (String baseDir : baseDirs) {
                    File f = new File(baseDir + "/" + size + "x" + size + "/mimetypes/" + prefix + ".png");
                    if (!f.exists()) {
                        f = new File(baseDir + "/" + size + "x" + size + "/apps/" + appName + ".png");
                    }
                    if (!f.exists()) {
                        f = new File(baseDir + "/" + size + "x" + size + "/apps/uyap-editor.png");
                    }
                    if (f.exists()) {
                        try {
                            Image img = ImageIO.read(f);
                            if (img != null) {
                                list.add(img);
                                break;
                            }
                        } catch (Throwable ignored) {
                        }
                    }
                }
            }
        }
        return list;
    }
}
