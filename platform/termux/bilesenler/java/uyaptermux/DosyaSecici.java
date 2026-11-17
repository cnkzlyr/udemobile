package uyaptermux;

import java.awt.AWTEvent;
import java.awt.BorderLayout;
import java.awt.Component;
import java.awt.Container;
import java.awt.Dimension;
import java.awt.GraphicsConfiguration;
import java.awt.Insets;
import java.awt.Rectangle;
import java.awt.Toolkit;
import java.awt.Window;
import java.awt.event.HierarchyEvent;
import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;
import javax.swing.Action;
import javax.swing.BorderFactory;
import javax.swing.Box;
import javax.swing.BoxLayout;
import javax.swing.Icon;
import javax.swing.JButton;
import javax.swing.JComponent;
import javax.swing.JFileChooser;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import javax.swing.filechooser.FileSystemView;

/**
 * UYAP'in dosya ac/kaydet pencerelerini (JFileChooser) modernlestirir:
 *  - Turkce etiketler (Java'da Turkce Swing metinleri yok: "Look In / Open / Cancel" yerine "Konum / Ac / Iptal")
 *  - sol tarafta hizli erisim: Indirilenler, UYAP Belgelerim, Belgeler, Masaustu, Ana klasor, son kullanilan
 *  - acilista ayrintili gorunum (ad / boyut / tarih), yeniden boyutlanabilir ve ekrana gore buyuk pencere
 * UYAP'in kendi ekleri (or. "Farkli Pencerede Ac") korunur: hizli erisim paneli bilesene degil, pencereye eklenir.
 */
final class DosyaSecici {
    private static final Map<JFileChooser, Boolean> ISLENDI = Collections.synchronizedMap(new WeakHashMap<>());

    private DosyaSecici() { }

    static void turkceMetinler() {
        String[][] m = {
            {"FileChooser.lookInLabelText", "Konum:"}, {"FileChooser.saveInLabelText", "Kayıt yeri:"},
            {"FileChooser.fileNameLabelText", "Dosya adı:"}, {"FileChooser.folderNameLabelText", "Klasör adı:"},
            {"FileChooser.filesOfTypeLabelText", "Dosya türü:"}, {"FileChooser.openButtonText", "Aç"},
            {"FileChooser.saveButtonText", "Kaydet"}, {"FileChooser.cancelButtonText", "İptal"},
            {"FileChooser.directoryOpenButtonText", "Aç"}, {"FileChooser.updateButtonText", "Yenile"},
            {"FileChooser.helpButtonText", "Yardım"}, {"FileChooser.openDialogTitleText", "Aç"},
            {"FileChooser.saveDialogTitleText", "Kaydet"}, {"FileChooser.acceptAllFileFilterText", "Tüm dosyalar"},
            {"FileChooser.upFolderToolTipText", "Üst klasör"}, {"FileChooser.homeFolderToolTipText", "Ana klasör"},
            {"FileChooser.newFolderToolTipText", "Yeni klasör"}, {"FileChooser.listViewButtonToolTipText", "Liste"},
            {"FileChooser.detailsViewButtonToolTipText", "Ayrıntılar"}, {"FileChooser.fileNameHeaderText", "Ad"},
            {"FileChooser.fileSizeHeaderText", "Boyut"}, {"FileChooser.fileTypeHeaderText", "Tür"},
            {"FileChooser.fileDateHeaderText", "Değiştirilme"}, {"FileChooser.fileAttrHeaderText", "Öznitelik"},
            {"FileChooser.newFolderErrorText", "Klasör oluşturulamadı"}, {"FileChooser.viewMenuLabelText", "Görünüm"},
            {"FileChooser.refreshActionLabelText", "Yenile"}, {"FileChooser.newFolderActionLabelText", "Yeni klasör"},
            {"FileChooser.listViewActionLabelText", "Liste"}, {"FileChooser.detailsViewActionLabelText", "Ayrıntılar"},
            {"OptionPane.yesButtonText", "Evet"}, {"OptionPane.noButtonText", "Hayır"},
            {"OptionPane.okButtonText", "Tamam"}, {"OptionPane.cancelButtonText", "İptal"},
            {"OptionPane.titleText", "Seçenek"}, {"OptionPane.messageDialogTitle", "İleti"},
            {"OptionPane.inputDialogTitle", "Giriş"},
        };
        for (String[] k : m) UIManager.put(k[0], k[1]);
    }

    static void kur() {
        turkceMetinler();
        Toolkit.getDefaultToolkit().addAWTEventListener(ev -> {
            HierarchyEvent he = (HierarchyEvent) ev;
            if ((he.getChangeFlags() & HierarchyEvent.SHOWING_CHANGED) != 0 && he.getComponent().isShowing()) {
                JFileChooser fc = bul(he.getComponent());
                if (fc != null && ISLENDI.put(fc, Boolean.TRUE) == null) {
                    SwingUtilities.invokeLater(() -> duzenle(fc));
                }
            }
        }, AWTEvent.HIERARCHY_EVENT_MASK);
    }

    private static JFileChooser bul(Component c) {
        if (c instanceof JFileChooser) return (JFileChooser) c;
        if (c instanceof Container) {
            for (Component k : ((Container) c).getComponents()) {
                JFileChooser f = bul(k);
                if (f != null) return f;
            }
        }
        return null;
    }

    /** Hizli erisim icin aday klasorler (var olanlar). */
    static List<Object[]> yerler(File sonKlasor) {
        String home = System.getenv().getOrDefault("HOME", System.getProperty("user.home"));
        List<Object[]> l = new ArrayList<>();
        ekle(l, "İndirilenler", new File(home, "storage/downloads"), new File("/sdcard/Download"), new File(home, "Downloads"),
                new File(home, "İndirilenler"));
        ekle(l, "UYAP Belgelerim", new File("/sdcard/Documents/UYAP_Belgelerim"));
        ekle(l, "Belgeler", new File(home, "storage/shared/Documents"), new File("/sdcard/Documents"), new File(home, "Documents"),
                new File(home, "Belgeler"));
        ekle(l, "Masaüstü", new File(home, "Desktop"), new File(home, "Masaüstü"));
        ekle(l, "Ana klasör", new File(home));
        if (sonKlasor != null) ekle(l, "Son klasör", sonKlasor);
        return l;
    }

    private static void ekle(List<Object[]> l, String ad, File... adaylar) {
        for (File f : adaylar) {
            if (f != null && f.isDirectory() && f.canRead()) {
                for (Object[] o : l) if (((File) o[1]).getAbsoluteFile().equals(f.getAbsoluteFile())) return;
                l.add(new Object[]{ad, f});
                return;
            }
        }
    }

    private static void duzenle(JFileChooser fc) {
        try {
            // ayrintili gorunum (ad/boyut/tarih) -- FlatLaf/Metal "viewTypeDetails" eylemi
            Action a = fc.getActionMap().get("viewTypeDetails");
            if (a != null && a.isEnabled()) a.actionPerformed(null);
        } catch (Throwable ignored) { }

        Window w = SwingUtilities.getWindowAncestor(fc);
        if (w == null) return;
        if (w instanceof java.awt.Dialog) ((java.awt.Dialog) w).setResizable(true);

        // hizli erisim paneli: pencerenin icerigini sarar (UYAP'in kendi eklerine dokunmadan)
        if (w instanceof javax.swing.RootPaneContainer && Boolean.parseBoolean(System.getProperty("uyap.dosya.hizli", "true"))) {
            javax.swing.RootPaneContainer rp = (javax.swing.RootPaneContainer) w;
            Container eski = rp.getContentPane();
            JPanel yeni = new JPanel(new BorderLayout());
            yeni.add(hizliErisim(fc), BorderLayout.WEST);
            JPanel orta = new JPanel(new BorderLayout());
            orta.add(eski, BorderLayout.CENTER);
            yeni.add(orta, BorderLayout.CENTER);
            rp.setContentPane(yeni);
        }

        // ekrana gore buyut: ekranin %70'i, en az 820x560
        GraphicsConfiguration gc = w.getGraphicsConfiguration();
        Rectangle ekran = gc != null ? gc.getBounds() : new Rectangle(Toolkit.getDefaultToolkit().getScreenSize());
        Insets ki = gc != null ? Toolkit.getDefaultToolkit().getScreenInsets(gc) : new Insets(0, 0, 0, 0);
        int gen = Math.min(ekran.width - ki.left - ki.right, Math.max(820, (int) (ekran.width * 0.7)));
        int yuk = Math.min(ekran.height - ki.top - ki.bottom, Math.max(560, (int) (ekran.height * 0.7)));
        Dimension d = w.getSize();
        w.setSize(Math.max(d.width, gen), Math.max(d.height, yuk));
        w.setLocationRelativeTo(w.getOwner());
        // ekran disina tasmasin
        Rectangle b = w.getBounds();
        int x = Math.max(ekran.x + ki.left, Math.min(b.x, ekran.x + ekran.width - ki.right - b.width));
        int y = Math.max(ekran.y + ki.top, Math.min(b.y, ekran.y + ekran.height - ki.bottom - b.height));
        w.setLocation(x, y);
        w.validate();
    }

    private static JComponent hizliErisim(JFileChooser fc) {
        JPanel p = new JPanel();
        p.setLayout(new BoxLayout(p, BoxLayout.Y_AXIS));
        p.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createMatteBorder(0, 0, 0, 1, UIManager.getColor("Separator.foreground") != null
                        ? UIManager.getColor("Separator.foreground") : java.awt.Color.LIGHT_GRAY),
                BorderFactory.createEmptyBorder(12, 8, 12, 8)));
        JLabel baslik = new JLabel("Hızlı erişim");
        baslik.setFont(baslik.getFont().deriveFont(java.awt.Font.BOLD));
        baslik.setBorder(BorderFactory.createEmptyBorder(0, 6, 8, 0));
        baslik.setAlignmentX(Component.LEFT_ALIGNMENT);
        p.add(baslik);
        FileSystemView fsv = fc.getFileSystemView();
        for (Object[] y : yerler(fc.getCurrentDirectory())) {
            File f = (File) y[1];
            Icon ic = null;
            try { ic = fsv.getSystemIcon(f); } catch (Throwable ignored) { }
            if (ic == null) ic = UIManager.getIcon("FileView.directoryIcon");
            JButton b = new JButton((String) y[0], ic);
            b.setToolTipText(f.getAbsolutePath());
            b.setHorizontalAlignment(SwingConstants.LEFT);
            b.setAlignmentX(Component.LEFT_ALIGNMENT);
            b.putClientProperty("JButton.buttonType", "toolBarButton");
            b.setMaximumSize(new Dimension(Integer.MAX_VALUE, b.getPreferredSize().height + 10));
            b.addActionListener(e -> fc.setCurrentDirectory(f));
            p.add(b);
            p.add(Box.createVerticalStrut(2));
        }
        p.add(Box.createVerticalGlue());
        return p;
    }
}
