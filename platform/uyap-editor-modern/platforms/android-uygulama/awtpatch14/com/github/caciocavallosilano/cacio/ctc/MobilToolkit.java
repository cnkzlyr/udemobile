package com.github.caciocavallosilano.cacio.ctc;

/**
 * UYAP Mobil: Cacio araç takımı + masaüstü uygulamalarının beklediği küçük eksikler.
 * UYAP Editör her tuşta Caps/Num Lock durumunu sorar (durum çubuğu); Cacio desteklemediği için
 * UnsupportedOperationException ile tuş olayı yarıda kalıyordu.
 */
public class MobilToolkit extends CTCToolkit {
    private final boolean[] kilit = new boolean[4];

    private static int idx(int k) {
        switch (k) {
            case java.awt.event.KeyEvent.VK_CAPS_LOCK: return 0;
            case java.awt.event.KeyEvent.VK_NUM_LOCK: return 1;
            case java.awt.event.KeyEvent.VK_SCROLL_LOCK: return 2;
            case java.awt.event.KeyEvent.VK_KANA_LOCK: return 3;
            default: throw new IllegalArgumentException("invalid key for Toolkit.getLockingKeyState");
        }
    }

    @Override public boolean getLockingKeyState(int keyCode) { return kilit[idx(keyCode)]; }
    @Override public void setLockingKeyState(int keyCode, boolean on) { kilit[idx(keyCode)] = on; }
}
