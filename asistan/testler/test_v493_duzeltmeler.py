# -*- coding: utf-8 -*-
"""v4.9.3: müvekkil gruplama, paylaşılan 429 bekleme, liste okunurken mükerrer ayıklama, uzun Windows yolu,
oturum durumunun kalıcı izlenmesi, UYAP 'login' modu."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "moduller" / "avukatasistan"))
sys.path.insert(0, str(KOK / "moduller" / "evrak"))


class MuvekkilTesti(unittest.TestCase):
    def setUp(self):
        import sunucu
        self.s = sunucu
        self.d = tempfile.mkdtemp()
        self.db = Path(self.d) / "uyap_katalog.db"
        c = sqlite3.connect(self.db)
        c.execute("CREATE TABLE dosya(dkey TEXT, birim TEXT, dosya_no TEXT, muvekkil TEXT, muvekkil_ara TEXT)")
        c.execute("CREATE TABLE evrak(id INTEGER)")
        for i, m in enumerate(["AHMET SUNGUR (Sanık)", "AHMET  SUNGUR (Şüpheli)", "ABC İNŞAAT LTD. ŞTİ. (Davacı)",
                               "ABC INSAAT LIMITED SIRKETI (Alacaklı)", "MEHMET YILMAZ (Davalı)", "MEHMET YILDIZ (Davalı)"]):
            c.execute("INSERT INTO dosya VALUES(?,?,?,?,?)", (f"d{i}", "Ankara 1. Asliye", f"2025/{i}", m, sunucu.fold(m)))
        c.commit(); c.close()

    def test_benzer_adlar_gruplanir(self):
        with mock.patch.object(self.s, "katalog_yolu", return_value=self.db):
            v = self.s.muvekkil_listesi()
        ad = {m["ad"]: m for m in v["muvekkiller"]}
        self.assertIn("AHMET SUNGUR", ad)
        self.assertIn("ABC INSAAT LIMITED SIRKETI", ad["ABC İNŞAAT LTD. ŞTİ."]["grup"])
        # farklı kişiler (Yılmaz / Yıldız) gruplanmaz
        self.assertNotIn("MEHMET YILDIZ", ad["MEHMET YILMAZ"]["grup"])

    def test_muvekkil_kosulu(self):
        k, p = self.s._muvekkil_kosul("AHMET SUNGUR (Sanık)|ABC")
        self.assertEqual(p, ["%ahmet sungur%", "%abc%"])
        self.assertIn(" OR ", k)


class IstekSiniriTesti(unittest.TestCase):
    def test_429_paylasilan_bekleme_tek_satir(self):
        import baglanti
        d = tempfile.mkdtemp()
        yanit429 = mock.Mock(status_code=429, headers={"Retry-After": "7"})
        yanit200 = mock.Mock(status_code=200, headers={})
        uyku = []
        with mock.patch.dict(os.environ, {"UYAP_VERI_DIZINI": d, "TICKTICK_YENIDEN_DENEME": "4"}), \
             mock.patch.object(baglanti.requests, "request", side_effect=[yanit429, yanit200]), \
             mock.patch.object(baglanti, "_uyu", side_effect=lambda sn: uyku.append(sn)), \
             mock.patch("builtins.print") as yaz:
            r = baglanti.oku("GET", "https://api.ticktick.com/open/v1/x", {}, ne="TickTick test")
            self.assertEqual(r.status_code, 200)
            self.assertGreater(baglanti.sinir_kalan("https://api.ticktick.com/open/v1/y"), 0)
        self.assertEqual(sum(1 for c in yaz.call_args_list if "429" in str(c)), 1)
        self.assertTrue(uyku and uyku[0] > 0)


class ListeMukerrerTesti(unittest.TestCase):
    def test_ayni_ad_anahtari_liste_okunurken_ayiklanir(self):
        d = tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"UYAP_VERI_DIZINI": d}):
            import importlib
            import evrak_katalog as ek
            importlib.reload(ek)
            k = ek.Katalog(Path(d) / "k.db")
            sayfa = [{"tumEvraklar": {"g": [{"tur": "Dilekçe", "evrakId": "1", "onaylandigiTarih": "01/02/2025",
                                             "ekEvrakListesi": [{"anaEvrakId": "A1", "sira": 1, "ekTuru": "Tarama 202501011234567"}]},
                                            {"tur": "Dilekçe", "evrakId": "2", "onaylandigiTarih": "02/02/2025",
                                             "ekEvrakListesi": [{"anaEvrakId": "A2", "sira": 1, "ekTuru": "Tarama 202501011234567"}]}]}}]
            k.ingest_pages("dk1", sayfa, "o")
            durumlar = [r[0] for r in k.db.execute("SELECT durum FROM evrak WHERE is_ek=1 ORDER BY skey")]
            self.assertEqual(sorted(durumlar), ["mukerrer", "yeni"])


class OturumTesti(unittest.TestCase):
    def test_oturum_satiri(self):
        import sunucu
        self.assertTrue(sunucu.oturum_satiri_coz("✅ UYAP oturumu doğrulandı: Sayın X"))
        self.assertFalse(sunucu.oturum_satiri_coz("[!] UYAP oturumu düştü, yeniden giriş deneniyor..."))
        self.assertIsNone(sunucu.oturum_satiri_coz("Finans güncellendi"))

    def test_login_modu_tanimli(self):
        kaynak = (KOK / "moduller" / "evrak" / "uyap_indirici.py").read_text(encoding="utf-8")
        self.assertIn('"login"]', kaynak)


class ArsivOnceligiTesti(unittest.TestCase):
    def test_asil_evrak_eklerden_once(self):
        import uyap_watcher as uw
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE evrak(id INTEGER PRIMARY KEY, durum TEXT, pdf_path TEXT, kategori TEXT, tarih TEXT, is_ek INTEGER)")
        db.execute("INSERT INTO evrak VALUES (1,'yeni',NULL,'karar','2025-01-01',1)")
        db.execute("INSERT INTO evrak VALUES (2,'yeni',NULL,'yazisma','2020-01-01',0)")
        w = uw.UyapWatcher.__new__(uw.UyapWatcher)
        w.katalog = type("K", (), {"db": db})()
        self.assertEqual(w.get_priority_backlog_ids(10), [2, 1])


if __name__ == "__main__":
    unittest.main()
