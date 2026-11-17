package uyaptermux;

import java.awt.KeyEventDispatcher;
import java.awt.KeyboardFocusManager;
import java.awt.event.KeyEvent;

/**
 * Tek basina Alt'a basilinca editorun kisayol harflerini (Office tarzi KeyTips) ve menu odagini engeller.
 *
 * UYAP Editor'de yanlislikla Alt'a bir kez dokunmak serit uzerinde harfler acar; sonraki tuslar belgeye yazilmaz,
 * sekme/komut secer. Bu sinif, yalnizca "Alt basildi -> baska tus olmadan Alt birakildi" dizisini yutar:
 *  - Alt+harf, Alt+Tab vb. kombinasyonlar oldugu gibi gecer (Alt basilisi da gecer; yalnizca tek basina
 *    birakilisi yutulur).
 *  - AltGr (VK_ALT_GRAPH; Turkce klavyede @, €, ~, \\, |, ...) hic etkilenmez.
 *  - Bazi X11 duzenlerinde AltGr, sag Alt olarak gelir: sag Alt (KEY_LOCATION_RIGHT) da etkilenmez.
 * KeyEventDispatcher, bilesenler ve UYAP'in kendi dinleyicilerinden ONCE calisir.
 */
final class TekAltEngeli implements KeyEventDispatcher {
    private boolean altBekliyor;
    private boolean basilisYutuldu;

    private TekAltEngeli() { }

    static void kur() {
        KeyboardFocusManager.getCurrentKeyboardFocusManager().addKeyEventDispatcher(new TekAltEngeli());
    }

    /** @return true = olay yutuldu */
    boolean isle(int id, int tus, int konum, boolean digerDegistiriciler) {
        boolean solAlt = tus == KeyEvent.VK_ALT && konum != KeyEvent.KEY_LOCATION_RIGHT;
        if (id == KeyEvent.KEY_PRESSED) {
            if (solAlt && !digerDegistiriciler) {
                // Alt basilisini da yut: UYAP bazi surumlerde KeyTips'i basista hazirlar.
                // Alt+X kombinasyonlarinda X olayinin kendi ALT_DOWN maskesi oldugu icin bunlar etkilenmez.
                altBekliyor = true;
                basilisYutuldu = true;
                return true;
            }
            altBekliyor = false;
            return false;
        }
        if (id == KeyEvent.KEY_RELEASED && solAlt) {
            boolean yut = altBekliyor || basilisYutuldu;
            altBekliyor = false;
            basilisYutuldu = false;
            return yut;
        }
        return false;
    }

    @Override
    public boolean dispatchKeyEvent(KeyEvent e) {
        if (e.getID() == KeyEvent.KEY_TYPED) return false;
        int mods = e.getModifiersEx() & ~KeyEvent.ALT_DOWN_MASK;
        boolean diger = (mods & (KeyEvent.CTRL_DOWN_MASK | KeyEvent.SHIFT_DOWN_MASK | KeyEvent.META_DOWN_MASK
                | KeyEvent.ALT_GRAPH_DOWN_MASK)) != 0;
        if (isle(e.getID(), e.getKeyCode(), e.getKeyLocation(), diger)) {
            e.consume();
            return true;
        }
        return false;
    }
}
