package uyapmobil;

import java.awt.Component;
import java.awt.Container;
import java.awt.EventQueue;
import java.awt.Window;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import javax.swing.AbstractButton;
import javax.swing.JCheckBox;
import javax.swing.JComboBox;
import javax.swing.JComponent;
import javax.swing.JLabel;
import javax.swing.JList;
import javax.swing.JPasswordField;
import javax.swing.JRadioButton;
import javax.swing.JTable;
import javax.swing.JToggleButton;
import javax.swing.JTree;
import javax.swing.border.Border;
import javax.swing.border.TitledBorder;
import javax.swing.text.JTextComponent;

/**
 * Resmi editörün pencerelerini (mobil imza, e-imza PIN'i, sertifika seçimi, uyarı/soru pencereleri, imzalar…) Android'de
 * yerel, dokunmaya uygun bir panel olarak yansıtır (3.27.0).
 *
 *   → FORM <base64 json>   {"no":n,"b":"başlık","o":[öğe…]}   (açık pencere değişince yeniden; 400 ms'de bir denetlenir)
 *   → FORM 0               yansıtılan pencere yok
 *   ← FA n id <base64>     metin alanına yaz
 *   ← FT n id              düğmeye bas / seçeneği seç / kutuyu değiştir
 *   ← FS n id sıra [2]     liste, tablo, ağaç, açılır liste seçimi (2: çift dokunuş)
 *
 * öğe: {"t":"baslik|etiket|metin|alan|sifre|radyo|kutu|secim|liste|tablo|agac|dugme","id","m","v","s","l","e"}
 * Yansıtılamayan (ör. yazdırma önizlemesi gibi büyük çizim alanı olan) pencerelerde "FORM 0" gönderilir; Android
 * orijinal pencereyi büyüterek gösterir.
 */
final class Form {
    private Form() { }

    private static int no;
    private static Window bagli;
    private static final List<Component> ogeler = new ArrayList<>();
    private static String son = "";

    static {
        new javax.swing.Timer(400, e -> denetle()).start();
    }

    /** En üstteki görünür pencere (çerçeve olmayan). */
    private static Window ustPencere() {
        Window en = null;
        for (Window w : Window.getWindows())
            if (w.isShowing() && !(w instanceof java.awt.Frame) && w.getWidth() > 8 && w.getHeight() > 8
                    && !w.getClass().getName().startsWith("com.github.caciocavallosilano")
                    && !(w.getClass().getName().contains("Popup"))) en = w;
        return en;
    }

    static boolean yansitiliyor() { return bagli != null && !son.isEmpty(); }

    private static void denetle() {
        Window w = ustPencere();
        if (w == null) {
            if (!son.isEmpty() || bagli != null) { bagli = null; son = ""; ogeler.clear(); Kopru.bildir("FORM 0"); }
            return;
        }
        if (w != bagli) { bagli = w; no++; }
        ogeler.clear();
        StringBuilder o = new StringBuilder();
        boolean[] karmasik = {false};
        gez(w, o, karmasik);
        String j;
        if (karmasik[0] || ogeler.isEmpty()) j = "";
        else {
            String b = w instanceof java.awt.Dialog ? ((java.awt.Dialog) w).getTitle() : "";
            j = "{\"no\":" + no + ",\"b\":" + js(b) + ",\"o\":[" + o + "]}";
        }
        if (!j.equals(son)) {
            son = j;
            Kopru.bildir(j.isEmpty() ? "FORM 0" : "FORM " + Base64.getEncoder().encodeToString(j.getBytes(StandardCharsets.UTF_8)));
        }
    }

    private static int kaydet(Component c) { ogeler.add(c); return ogeler.size() - 1; }

    private static void ekle(StringBuilder o, String s) { if (o.length() > 0) o.append(','); o.append(s); }

    private static void gez(Container c, StringBuilder o, boolean[] karmasik) {
        if (c instanceof JComponent) {
            Border b = ((JComponent) c).getBorder();
            if (b instanceof TitledBorder && ((TitledBorder) b).getTitle() != null && !((TitledBorder) b).getTitle().trim().isEmpty())
                ekle(o, "{\"t\":\"baslik\",\"m\":" + js(((TitledBorder) b).getTitle()) + "}");
        }
        for (Component k : c.getComponents()) {
            if (!k.isVisible()) continue;
            if (k instanceof JPasswordField) {
                JPasswordField f = (JPasswordField) k;
                ekle(o, "{\"t\":\"sifre\",\"id\":" + kaydet(k) + ",\"v\":" + js(new String(f.getPassword())) + ",\"e\":" + (f.isEnabled() ? 1 : 0) + "}");
            } else if (k instanceof JTextComponent) {
                JTextComponent t = (JTextComponent) k;
                if (t.isEditable() && t.isEnabled())
                    ekle(o, "{\"t\":\"alan\",\"id\":" + kaydet(k) + ",\"v\":" + js(t.getText()) + ",\"cok\":" + (t instanceof javax.swing.JTextArea ? 1 : 0) + "}");
                else if (!t.getText().trim().isEmpty()) ekle(o, "{\"t\":\"metin\",\"m\":" + js(t.getText().trim()) + "}");
            } else if (k instanceof JRadioButton) {
                AbstractButton r = (AbstractButton) k;
                ekle(o, "{\"t\":\"radyo\",\"id\":" + kaydet(k) + ",\"m\":" + js(r.getText()) + ",\"s\":" + (r.isSelected() ? 1 : 0) + ",\"e\":" + (r.isEnabled() ? 1 : 0) + "}");
            } else if (k instanceof JCheckBox) {
                AbstractButton r = (AbstractButton) k;
                ekle(o, "{\"t\":\"kutu\",\"id\":" + kaydet(k) + ",\"m\":" + js(r.getText()) + ",\"s\":" + (r.isSelected() ? 1 : 0) + ",\"e\":" + (r.isEnabled() ? 1 : 0) + "}");
            } else if (k instanceof AbstractButton && !(k instanceof JToggleButton && ((AbstractButton) k).getText() == null)) {
                AbstractButton d = (AbstractButton) k;
                String m = d.getText();
                if (m == null || m.trim().isEmpty()) m = d.getToolTipText();
                if (m == null || m.trim().isEmpty()) {
                    if (k.getClass().getName().contains("ComboBox") || k.getClass().getName().contains("ScrollButton") || k.getClass().getName().contains("ArrowButton")) continue;
                    m = "•";
                }
                ekle(o, "{\"t\":\"dugme\",\"id\":" + kaydet(k) + ",\"m\":" + js(temiz(m)) + ",\"e\":" + (d.isEnabled() ? 1 : 0) + "}");
            } else if (k instanceof JComboBox) {
                JComboBox<?> cb = (JComboBox<?>) k;
                StringBuilder l = new StringBuilder();
                for (int i = 0; i < Math.min(cb.getItemCount(), 200); i++) { if (i > 0) l.append(','); l.append(js(String.valueOf(cb.getItemAt(i)))); }
                ekle(o, "{\"t\":\"secim\",\"id\":" + kaydet(k) + ",\"s\":" + cb.getSelectedIndex() + ",\"l\":[" + l + "],\"e\":" + (cb.isEnabled() ? 1 : 0) + "}");
                continue;
            } else if (k instanceof JList) {
                JList<?> li = (JList<?>) k;
                StringBuilder l = new StringBuilder();
                for (int i = 0; i < Math.min(li.getModel().getSize(), 300); i++) { if (i > 0) l.append(','); l.append(js(String.valueOf(li.getModel().getElementAt(i)))); }
                ekle(o, "{\"t\":\"liste\",\"id\":" + kaydet(k) + ",\"s\":" + li.getSelectedIndex() + ",\"l\":[" + l + "]}");
                continue;
            } else if (k instanceof JTable) {
                JTable t = (JTable) k;
                StringBuilder b = new StringBuilder(), r = new StringBuilder();
                for (int i = 0; i < t.getColumnCount(); i++) { if (i > 0) b.append(','); b.append(js(t.getColumnName(i))); }
                for (int i = 0; i < Math.min(t.getRowCount(), 100); i++) {
                    if (i > 0) r.append(',');
                    r.append('[');
                    for (int j = 0; j < t.getColumnCount(); j++) { if (j > 0) r.append(','); Object v = t.getValueAt(i, j); r.append(js(v == null ? "" : temiz(String.valueOf(v)))); }
                    r.append(']');
                }
                ekle(o, "{\"t\":\"tablo\",\"id\":" + kaydet(k) + ",\"s\":" + t.getSelectedRow() + ",\"b\":[" + b + "],\"l\":[" + r + "]}");
                continue;
            } else if (k instanceof JTree) {
                JTree t = (JTree) k;
                StringBuilder l = new StringBuilder();
                for (int i = 0; i < Math.min(t.getRowCount(), 200); i++) {
                    if (i > 0) l.append(',');
                    Object d = t.getPathForRow(i).getLastPathComponent();
                    String m = String.valueOf(d);
                    try {   // görüntülenen metin (hücre çizicisi) daha anlamlıysa onu kullan
                        Component r = t.getCellRenderer().getTreeCellRendererComponent(t, d, t.isRowSelected(i), t.isExpanded(i), t.getModel().isLeaf(d), i, false);
                        if (r instanceof JLabel && ((JLabel) r).getText() != null && !((JLabel) r).getText().isEmpty()) m = ((JLabel) r).getText();
                    } catch (Throwable ignored) { }
                    l.append('[').append(t.getPathForRow(i).getPathCount() - 1).append(',').append(js(temiz(m))).append(']');
                }
                int[] s = t.getSelectionRows();
                ekle(o, "{\"t\":\"agac\",\"id\":" + kaydet(k) + ",\"s\":" + (s != null && s.length > 0 ? s[0] : -1) + ",\"l\":[" + l + "]}");
                continue;
            } else if (k instanceof JLabel) {
                String m = ((JLabel) k).getText();
                if (m != null && !temiz(m).trim().isEmpty()) ekle(o, "{\"t\":\"etiket\",\"m\":" + js(temiz(m).trim()) + "}");
            } else if (k instanceof JComponent && !(k instanceof Container && ((Container) k).getComponentCount() > 0)
                    && k.getWidth() > 220 && k.getHeight() > 160 && !(k instanceof javax.swing.JScrollBar)
                    && !(k instanceof javax.swing.JSeparator) && !(k instanceof javax.swing.JViewport)) {
                karmasik[0] = true;      // çizim alanı (ör. yazdırma önizlemesi): yansıtılamaz
            }
            if (k instanceof Container) gez((Container) k, o, karmasik);
        }
    }

    private static String temiz(String m) {
        return m.replaceAll("(?i)<br\\s*/?>", "\n").replaceAll("<[^>]+>", "").replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">");
    }

    private static String js(String s) {
        if (s == null) return "\"\"";
        StringBuilder b = new StringBuilder("\"");
        for (char ch : s.toCharArray()) {
            if (ch == '"' || ch == '\\') b.append('\\').append(ch);
            else if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch));
            else b.append(ch);
        }
        return b.append('"').toString();
    }

    // ------------------------------------------------------------------------------------ Android'den
    static void komut(String[] p) {
        EventQueue.invokeLater(() -> {
            try {
                if (Integer.parseInt(p[1]) != no) return;
                int id = Integer.parseInt(p[2]);
                if (id < 0 || id >= ogeler.size()) return;
                Component c = ogeler.get(id);
                switch (p[0]) {
                    case "FA": {
                        String v = p.length > 3 ? new String(Base64.getDecoder().decode(p[3]), StandardCharsets.UTF_8) : "";
                        JTextComponent t = (JTextComponent) c;
                        if (!v.equals(t.getText())) { t.setText(v); t.setCaretPosition(v.length()); }
                        break;
                    }
                    case "FT": {
                        AbstractButton b = (AbstractButton) c;
                        if (b.isEnabled()) b.doClick(0);
                        break;
                    }
                    case "FS": {
                        int i = Integer.parseInt(p[3]);
                        boolean cift = p.length > 4 && "2".equals(p[4]);
                        if (c instanceof JComboBox) ((JComboBox<?>) c).setSelectedIndex(i);
                        else if (c instanceof JList) { JList<?> l = (JList<?>) c; l.setSelectedIndex(i); l.ensureIndexIsVisible(i); if (cift) ciftTik(l, l.getCellBounds(i, i)); }
                        else if (c instanceof JTable) { JTable t = (JTable) c; t.setRowSelectionInterval(i, i); if (cift) ciftTik(t, t.getCellRect(i, 0, true)); }
                        else if (c instanceof JTree) { JTree t = (JTree) c; t.setSelectionRow(i); if (cift) ciftTik(t, t.getRowBounds(i)); }
                        break;
                    }
                    default: break;
                }
                denetle();
            } catch (Throwable e) {
                Kopru.LOG.println("[uyapmobil] form komutu " + String.join(" ", p) + ": " + e);
            }
        });
    }

    private static void ciftTik(Component c, java.awt.Rectangle r) {
        if (r == null) return;
        int x = r.x + Math.min(10, r.width / 2), y = r.y + r.height / 2;
        long t = System.currentTimeMillis();
        for (int n = 1; n <= 2; n++) {
            c.dispatchEvent(new java.awt.event.MouseEvent(c, java.awt.event.MouseEvent.MOUSE_PRESSED, t, java.awt.event.InputEvent.BUTTON1_DOWN_MASK, x, y, n, false, java.awt.event.MouseEvent.BUTTON1));
            c.dispatchEvent(new java.awt.event.MouseEvent(c, java.awt.event.MouseEvent.MOUSE_RELEASED, t, 0, x, y, n, false, java.awt.event.MouseEvent.BUTTON1));
            c.dispatchEvent(new java.awt.event.MouseEvent(c, java.awt.event.MouseEvent.MOUSE_CLICKED, t, 0, x, y, n, false, java.awt.event.MouseEvent.BUTTON1));
        }
    }
}
