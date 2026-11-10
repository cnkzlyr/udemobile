package com.agy.uyapacici;

import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * E-imza PIN penceresi (Adalet E-İmza, sayfa PIN göndermediğinde ister). Chrome'un üzerinde açılır.
 * PIN hiçbir yere kaydedilmez; yalnızca o anki imza işlemi için resmi uygulamaya iletilir.
 */
public class PinEkrani extends Activity {
    public static final String EXTRA_BASLIK = "baslik";
    private boolean cevaplandi = false;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        Tani.baglam(this);
        Tani.yaz("pin", "PIN penceresi açıldı");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE            // ekran görüntüsü/kayıt alınmaz
                | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON);
        setFinishOnTouchOutside(false);
        float d = getResources().getDisplayMetrics().density;
        LinearLayout kok = new LinearLayout(this);
        kok.setOrientation(LinearLayout.VERTICAL);
        int p = (int) (20 * d);
        kok.setPadding(p, p, p, p);
        TextView baslik = new TextView(this);
        String t = getIntent().getStringExtra(EXTRA_BASLIK);
        baslik.setText("🔐 " + (t == null || t.isEmpty() ? "E-imza şifrenizi (PIN) girin" : t));
        baslik.setTextSize(18);
        kok.addView(baslik);
        TextView aciklama = new TextView(this);
        aciklama.setText("Adalet E-İmza (UYAP) imza için kartınızın PIN'ini istiyor. PIN kaydedilmez.");
        aciklama.setTextSize(13);
        aciklama.setPadding(0, (int) (6 * d), 0, (int) (12 * d));
        kok.addView(aciklama);
        final EditText pin = new EditText(this);
        pin.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_VARIATION_PASSWORD);
        pin.setHint("PIN");
        pin.setImeOptions(EditorInfo.IME_ACTION_DONE);
        kok.addView(pin);
        LinearLayout dugmeler = new LinearLayout(this);
        dugmeler.setGravity(Gravity.END);
        Button iptal = new Button(this);
        iptal.setText("İptal");
        Button tamam = new Button(this);
        tamam.setText("İmzala");
        dugmeler.addView(iptal);
        dugmeler.addView(tamam);
        kok.addView(dugmeler);
        setContentView(kok);
        setTitle("E-imza PIN");
        iptal.setOnClickListener(v -> bitir(null));
        tamam.setOnClickListener(v -> {
            String s = pin.getText().toString();
            if (s.length() < 4) { pin.setError("PIN en az 4 haneli olmalı"); return; }
            bitir(s);
        });
        pin.setOnEditorActionListener((v, id, e) -> { tamam.performClick(); return true; });
        pin.requestFocus();
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_VISIBLE);
    }

    private void bitir(String pin) {
        if (cevaplandi) return;
        cevaplandi = true;
        AdaletServisi.pinGeldi(pin);
        finish();
    }

    @Override
    protected void onDestroy() {
        if (!cevaplandi) AdaletServisi.pinGeldi(null);   // geri tuşu / kapatma = iptal
        super.onDestroy();
    }
}
