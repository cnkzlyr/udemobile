# -*- coding: utf-8 -*-
"""UYAP oturum kuralı (uyap_indirici.UyapBrowserBridge.akilli_oturum_ac):

  * e-İmza kartı takılıysa e-İmza ile girilir.
  * Kart takılı değilse ya da bağlantı koptuysa oturum açılana kadar Mobil İmza gönderilir.
  * Beklerken kart takılırsa hemen e-İmzaya dönülür.
  * Kartın reddettiği PIN asla yeniden denenmez.

Gerçek tarayıcı/kart/telefon yerine davranışı kaydeden sahte köprü kullanılır; zaman da sahtedir.
"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "moduller" / "evrak"))
import uyap_indirici as ui  # noqa: E402


class SahteSaat:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def uyu(self, sn):
        self.t += max(sn, 0.001)


class SahteKopru(ui.UyapBrowserBridge):
    """Ağ/tarayıcı yok: yalnız akilli_oturum_ac'ın kullandığı yöntemler taklit edilir."""

    def __init__(self, saat, kart=lambda t: False, mobil_sonuclari=(), eimza_sonucu=(True, "e-İmza ile girildi")):
        self._rejected_pins = set()
        self.saat, self._kart, self.mobil_sonuclari = saat, kart, list(mobil_sonuclari)
        self.eimza_sonucu, self.olaylar, self.oturum = eimza_sonucu, [], False

    def is_logged_in(self):
        return self.oturum

    def kart_takili_mi(self):
        return self._kart(self.saat.t)

    def auto_relogin(self, pin="", _restarted=False):
        self.olaylar.append(("eimza", round(self.saat.t)))
        ok, msg = self.eimza_sonucu
        if not ok and "PIN" in msg:
            self._rejected_pins.add(hashlib.sha256(pin.encode()).hexdigest())
        self.oturum = ok
        return ok, msg

    def login_with_mobil_imza(self, tc, gsm, operator="", status_cb=None, timeout_s=240.0):
        self.olaylar.append(("mobil", round(self.saat.t)))
        ok, msg = self.mobil_sonuclari.pop(0) if self.mobil_sonuclari else (False, "telefon onaylanmadı")
        self.saat.t += 30  # telefon onayı beklemesi
        self.oturum = ok
        return ok, msg


class OturumKuraliTest(unittest.TestCase):
    def setUp(self):
        self.saat = SahteSaat()
        self._eski = ui.time.monotonic
        ui.time.monotonic = self.saat.monotonic

    def tearDown(self):
        ui.time.monotonic = self._eski

    def ac(self, kopru, **kw):
        kw.setdefault("tc", "11111111111")
        kw.setdefault("gsm", "5321234567")
        return kopru.akilli_oturum_ac(uyku=self.saat.uyu, status_cb=lambda m: None, **kw)

    def test_kart_takiliysa_eimza_kullanilir_mobil_gonderilmez(self):
        k = SahteKopru(self.saat, kart=lambda t: True)
        ok, _ = self.ac(k, pin="1234")
        self.assertTrue(ok)
        self.assertEqual([o[0] for o in k.olaylar], ["eimza"])

    def test_kart_yoksa_baglanana_kadar_mobil_imza(self):
        k = SahteKopru(self.saat, mobil_sonuclari=[(False, "zaman aşımı"), (False, "onaylanmadı"), (True, "Mobil İmza ile girildi")])
        ok, msg = self.ac(k, pin="1234")
        self.assertTrue(ok, msg)
        self.assertEqual([o[0] for o in k.olaylar], ["mobil", "mobil", "mobil"])
        # Telefon bildirimle boğulmasın: denemeler arasında kademeli bekleme
        araliklar = [b[1] - a[1] for a, b in zip(k.olaylar, k.olaylar[1:])]
        self.assertGreaterEqual(araliklar[0], 60 + 30)
        self.assertGreaterEqual(araliklar[1], 120 + 30)

    def test_beklerken_kart_takilirsa_eimzaya_donulur(self):
        k = SahteKopru(self.saat, kart=lambda t: t >= 50, mobil_sonuclari=[(False, "onaylanmadı")])
        ok, _ = self.ac(k, pin="1234")
        self.assertTrue(ok)
        self.assertEqual([o[0] for o in k.olaylar], ["mobil", "eimza"])
        self.assertLess(k.olaylar[1][1], 30 + 60)  # tam bekleme bitmeden

    def test_eimza_baglanti_hatasinda_mobile_gecilir(self):
        k = SahteKopru(self.saat, kart=lambda t: True, eimza_sonucu=(False, "ArkSigner'a imza isteği gönderilemedi"),
                       mobil_sonuclari=[(True, "Mobil İmza ile girildi")])
        ok, _ = self.ac(k, pin="1234")
        self.assertTrue(ok)
        self.assertEqual([o[0] for o in k.olaylar], ["eimza", "mobil"])

    def test_reddedilen_pin_tekrar_denenmez(self):
        k = SahteKopru(self.saat, kart=lambda t: True, eimza_sonucu=(False, "e-İmza PIN hatası: yanlış PIN"),
                       mobil_sonuclari=[(False, "x"), (False, "y"), (True, "girildi")])
        ok, _ = self.ac(k, pin="9999")
        self.assertTrue(ok)
        self.assertEqual([o[0] for o in k.olaylar].count("eimza"), 1)

    def test_oturum_zaten_aciksa_hicbir_sey_gonderilmez(self):
        k = SahteKopru(self.saat)
        k.oturum = True
        self.assertTrue(self.ac(k, pin="1234")[0])
        self.assertEqual(k.olaylar, [])

    def test_sure_siniri_ve_bilgi_yoksa(self):
        k = SahteKopru(self.saat)
        ok, msg = self.ac(k, pin="1234", sure_siniri_s=1000)
        self.assertFalse(ok)
        self.assertIn("süre doldu", msg)
        self.assertGreater(len(k.olaylar), 2)
        k2 = SahteKopru(self.saat)
        ok, msg = k2.akilli_oturum_ac(pin="", tc="", gsm="", status_cb=lambda m: None)
        self.assertFalse(ok)
        self.assertIn("tanımlı değil", msg)

    def test_yalniz_eimza_tanimliysa_kart_beklenir(self):
        k = SahteKopru(self.saat, kart=lambda t: t >= 500)
        ok, _ = k.akilli_oturum_ac(pin="1234", tc="", gsm="", uyku=self.saat.uyu, status_cb=lambda m: None)
        self.assertTrue(ok)
        self.assertEqual([o[0] for o in k.olaylar], ["eimza"])


if __name__ == "__main__":
    unittest.main()
