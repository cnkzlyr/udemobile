#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Tüm Dava Dosyalarını Eksiksiz Tarama ve Kataloglama Betiği
=============================================================
Telif Hakkı (c) 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.

UYAP Avukat Portalındaki tüm açık ve kapalı (729+) dava dosyalarının
evrak listelerini (duruşma, tensip, karar, dilekçe, ekler) eksiksiz çeker
ve 'uyap_katalog.db' veritabanına işler.
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:  # v4.10.0: PIN koda yazılmaz (asistan/kisisel_ayar.py)
    import kisisel_ayar as _ka
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import kisisel_ayar as _ka
from uyap_indirici import UyapBrowserBridge
from evrak_katalog import Katalog, Motor

def main():
    print("=================================================================")
    print("  UYAP TÜM DOSYALAR KAPSAMLI EVRAK TARAYICI")
    print("=================================================================")
    
    bridge = UyapBrowserBridge()
    ok, msg = bridge.ensure_browser(headless=True)
    if not ok:
        print(f"[!] Tarayıcı başlatılamadı: {msg}")
        return
    
    if not bridge.is_logged_in():
        print("[*] Aktif UYAP oturumu bulunamadı, takılı USB E-İmza ile giriş yapılıyor...")
        ok_l, msg_l = bridge.auto_relogin(pin=_ka.al("pin"))
        if not ok_l:
            print(f"[!] E-İmza ile otomatik oturum açılamadı: {msg_l}")
            print("    Lütfen USB E-İmzanızın takılı olduğundan ve ArkSigner servisinin açık olduğundan emin olun.")
            return
        print(f"[✓] {msg_l}")
        
    katalog = Katalog(BASE_DIR / "uyap_katalog.db")
    
    # Oturum düştüğünde USB E-İmza ile otomatik yeniden giriş fonksiyonu
    def relogin_handler() -> bool:
        print("[*] E-İmza ile otomatik oturum tazeleniyor (PIN: kisisel_ayar)...")
        ok_l, msg_l = bridge.auto_relogin(pin=_ka.al("pin"))
        if ok_l:
            print(f"[✓] Oturum başarıyla tazelendi: {msg_l}")
            return True
        print(f"[!] Oturum tazelenemedi: {msg_l}")
        return False

    motor = Motor(
        bridge,
        katalog,
        Path.home() / "UYAP_Indirilenler",
        log=print,
        relogin=relogin_handler
    )
    
    eksik = katalog.eksik_dkeys()
    print(f"[*] Taranmayı bekleyen dava dosyası sayısı: {len(eksik)}")
    
    if not eksik:
        print("[✓] Tüm dava dosyaları zaten eksiksiz taranmış durumda!")
        return
        
    print(f"[*] {len(eksik)} dosya taranmaya başlanıyor (batch=6)...")
    t0 = time.time()
    toplam_eklenen = motor.scan(include_closed=True, batch=6, only_dkeys=set(eksik))
    sure = round(time.time() - t0, 1)
    
    print("=================================================================")
    print(f"[✓] Tarama tamamlandı! ({sure} saniye)")
    print(f"    Eklenen Yeni Evrak Sayısı: {toplam_eklenen:,}")
    print("=================================================================")

if __name__ == "__main__":
    main()
