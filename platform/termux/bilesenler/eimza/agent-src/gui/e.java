// CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
// CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
// CKZ-MUHUR/1 dcNtDIqc9z5OXjRgmTyf8qInmR0MSdgJmZjDRuu9DRTULNH9v3xB4jJ+DmknGpOAKnNwVSOYziraCVzyo4ihBg==
package tr.gov.adalet.service.framework.adalet.eimza.eimzatray.gui;

import java.awt.Component;
import java.awt.FlowLayout;
import java.awt.GraphicsEnvironment;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import javax.swing.JDialog;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JPasswordField;
import javax.swing.Timer;
import javax.swing.border.EmptyBorder;

/**
 * UYAP-Termux: web sayfasi PIN gondermediginde PIN'i Android'in kendi penceresinden (termux-dialog) alir.
 * Termux'ta uygulamanin masaustu penceresi Chrome'un arkasinda kaldigi icin bu gereklidir.
 * termux-dialog kullanilamazsa (Termux:API yok/izin yok) ve uygulama GORUNUR bir ekrandaysa Swing penceresi acilir;
 * gorunmez Xvfb ekraninda (:99) Swing penceresi acilmaz (kimse goremeyecegi icin sonsuza dek beklerdi).
 * EIMZA_PIN_MODE=android -> yalnizca Android penceresi;  EIMZA_PIN_MODE=swing -> her zaman Swing.
 * PIN hicbir yere yazilmaz/loglanmaz; Swing alanindaki karakter dizisi kullanimdan sonra sifirlanir.
 *
 * (c) 2026 Av. Can KIZILYAR - Tum haklari saklidir. Bkz. LICENSE.txt
 */
public class e {
    private static final int TIMEOUT_SECONDS = 120;

    public static String a(Component parent) {
        String mode = System.getenv("EIMZA_PIN_MODE");
        if (mode == null) mode = "auto";
        if (!"swing".equalsIgnoreCase(mode)) {
            String[] r = android();
            if (r != null) return r[0];                 // r[0] == null: kullanici iptal etti
            if ("android".equalsIgnoreCase(mode)) return null;
        }
        return gorunurEkran() ? swing(parent) : null;
    }

    static boolean gorunurEkran() {
        if (GraphicsEnvironment.isHeadless()) return false;
        String d = System.getenv("DISPLAY");
        String gorunmez = System.getenv("EIMZA_GORUNMEZ_EKRAN");
        if (gorunmez == null || gorunmez.isEmpty()) gorunmez = ":99";
        return d != null && !d.isEmpty() && !d.equals(gorunmez) && !d.startsWith(gorunmez + ".");
    }

    /** @return null = termux-dialog kullanilamadi; {pin} = sonuc (pin null ise iptal) */
    static String[] android() {
        try {
            ProcessBuilder pb = new ProcessBuilder("termux-dialog", "text", "-t", "E-imza sifresi (PIN)", "-i", "PIN", "-p");
            Process p = pb.start();
            p.getOutputStream().close();
            ByteArrayOutputStream bo = new ByteArrayOutputStream();
            Thread t = new Thread(() -> {
                try (InputStream in = p.getInputStream()) {
                    byte[] b = new byte[512];
                    int n;
                    while ((n = in.read(b)) > 0) bo.write(b, 0, n);
                } catch (Exception ignored) { }
            });
            t.setDaemon(true);
            t.start();
            if (!p.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                p.destroyForcibly();
                return null;
            }
            t.join(1000);
            String out = new String(bo.toByteArray(), StandardCharsets.UTF_8);
            Matcher mc = Pattern.compile("\"code\"\\s*:\\s*(-?\\d+)").matcher(out);
            if (!mc.find()) return null;
            if (Integer.parseInt(mc.group(1)) != -1) return new String[]{null};
            Matcher mt = Pattern.compile("\"text\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"").matcher(out);
            if (!mt.find()) return new String[]{null};
            String s = unescape(mt.group(1));
            return new String[]{s.isEmpty() ? null : s};
        } catch (Exception ex) {
            return null;
        }
    }

    private static String unescape(String s) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c != '\\' || i + 1 >= s.length()) { sb.append(c); continue; }
            char n = s.charAt(++i);
            switch (n) {
                case 'n': sb.append('\n'); break;
                case 't': sb.append('\t'); break;
                case 'r': sb.append('\r'); break;
                case 'u':
                    if (i + 4 < s.length()) { sb.append((char) Integer.parseInt(s.substring(i + 1, i + 5), 16)); i += 4; }
                    break;
                default: sb.append(n);
            }
        }
        return sb.toString();
    }

    private static String swing(Component parent) {
        JPasswordField pf = new JPasswordField(12);
        JPanel panel = new JPanel(new FlowLayout());
        panel.setBorder(new EmptyBorder(24, 10, 10, 10));
        panel.add(new JLabel("E-imza \u015eifrenizi Giriniz:"));
        panel.add(pf);
        JOptionPane op = new JOptionPane(panel, JOptionPane.PLAIN_MESSAGE, JOptionPane.OK_CANCEL_OPTION);
        JDialog d = op.createDialog(parent, "E-imza \u015eifre Giri\u015fi");
        d.setAlwaysOnTop(true);
        d.setModal(true);
        Timer zamanAsimi = new Timer(TIMEOUT_SECONDS * 1000, ev -> d.dispose());
        zamanAsimi.setRepeats(false);
        zamanAsimi.start();
        d.addWindowListener(new java.awt.event.WindowAdapter() {
            @Override public void windowOpened(java.awt.event.WindowEvent ev) { pf.requestFocusInWindow(); }
        });
        d.toFront();
        d.setVisible(true);
        zamanAsimi.stop();
        char[] c = pf.getPassword();
        try {
            Object v = op.getValue();
            if (v instanceof Integer && (Integer) v == JOptionPane.OK_OPTION && c.length > 0) return new String(c);
            return null;
        } finally {
            java.util.Arrays.fill(c, '\0');
            pf.setText("");
        }
    }
}
