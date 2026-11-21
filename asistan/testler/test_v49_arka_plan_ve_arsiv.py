#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.9.0 gerileme testleri.

* Android CDP köprüsü yalnızca ekrana hiç eklenmemiş (gizli) WebView'ları listeler: UYAP/UETS otomasyonu
  görünür Asistan ekranını ele geçirmez.
* Arşiv kataloğu: UYAP'ın kalıcı hata verdiği dosyalar sıranın başını tıkayıp arşivin geri kalanını engellemez.
* Tebligat süreçleri: mazbata CSV'si + katalogdaki tebligat evrakları dosya penceresinde.
* "Evraklarını Drive'a indir": dosya indirme sırasının başına alınır.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ASISTAN_DIR = Path(__file__).resolve().parents[1]
EVRAK_DIR = ASISTAN_DIR / "moduller" / "evrak"
AVUKAT_DIR = ASISTAN_DIR / "moduller" / "avukatasistan"
for p in (ASISTAN_DIR, EVRAK_DIR, AVUKAT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ["AVUKAT_ENV_TASIMA"] = "0"

import sunucu  # noqa: E402


class GizliHedef(unittest.TestCase):
    def test_gorunur_webview_elenir(self):
        gorunur = {"type": "page", "url": "https://avukat.uyap.gov.tr/",
                   "description": json.dumps({"attached": True, "never_attached": False, "visible": True})}
        asistan = {"type": "page", "url": "http://127.0.0.1:8765/asistan", "description": "{}"}
        gizli = {"type": "page", "url": "https://avukat.uyap.gov.tr/",
                 "description": json.dumps({"attached": False, "never_attached": True, "visible": False})}
        uets = {"type": "page", "url": "about:blank#uets",
                "description": json.dumps({"attached": False, "never_attached": True})}
        # Etkinlik ekranı kapanıp ayrılmış görünür WebView: never_attached=False → yine elenir
        ayrilmis = {"type": "page", "url": "https://x/", "description": json.dumps({"attached": False, "never_attached": False})}
        secilen = [t for t in (gorunur, asistan, gizli, uets, ayrilmis) if sunucu._gizli_hedef_mi(t)]
        self.assertEqual(secilen, [gizli, uets])

    def test_eski_webview_never_attached_yoksa_attached_kullanilir(self):
        self.assertTrue(sunucu._gizli_hedef_mi({"type": "page", "url": "https://a/", "description": '{"attached":false}'}))
        self.assertFalse(sunucu._gizli_hedef_mi({"type": "page", "url": "https://a/", "description": '{"attached":true}'}))


class ArsivKatalogSirasi(unittest.TestCase):
    def test_kalici_hatalilar_sirayi_tikamaz(self):
        import uyap_watcher as uw
        with tempfile.TemporaryDirectory() as td:
            db = sqlite3.connect(str(Path(td) / "k.db"))
            db.execute("CREATE TABLE dosya(dkey TEXT PRIMARY KEY, tarama TEXT, taranma TEXT, taraflar TEXT, dosya_id TEXT)")
            simdi = dt.datetime.now().isoformat(timespec="seconds")
            # İlk 50 dosya az önce denenmiş ve UYAP kalıcı hata vermiş; 50 dosya hiç denenmemiş
            for i in range(50):
                db.execute("INSERT INTO dosya VALUES(?,?,?,?,?)", (f"B|{i}", "hata: 123 yetki yok", simdi, "X (Davacı)", ""))
            db.commit()
            secilen = []

            class Motor:
                @staticmethod
                def _case_dkey(c):
                    return c["k"]

                def scan(self, include_closed, only_dkeys):
                    secilen.append(set(only_dkeys))

            class Kat:
                pass
            w = uw.UyapWatcher.__new__(uw.UyapWatcher)
            w.motor = Motor()
            w.katalog = Kat()
            w.katalog.db = db
            w.bridge = type("B", (), {"query_tum_dosyalar": lambda self, include_closed=True: [{"k": f"B|{i}"} for i in range(100)]})()
            w._taraf_tamamla = lambda cases: None
            uw.DATA_DIR = Path(td)
            w._arsiv_katalogla(adet=40)
            self.assertEqual(len(secilen), 1)
            self.assertTrue(all(int(k.split("|")[1]) >= 50 for k in secilen[0]), "hiç denenmemiş dosyalar önce gelmeli")

    def test_oncelikli_dosya_en_basta(self):
        import uyap_watcher as uw
        with tempfile.TemporaryDirectory() as td:
            db = sqlite3.connect(str(Path(td) / "k.db"))
            db.execute("CREATE TABLE dosya(dkey TEXT PRIMARY KEY, tarama TEXT, taranma TEXT, taraflar TEXT, dosya_id TEXT)")
            db.commit()
            (Path(td) / "oncelikli_dosyalar.json").write_text(json.dumps({"dkeyler": ["B|99"]}), encoding="utf-8")
            secilen = []
            w = uw.UyapWatcher.__new__(uw.UyapWatcher)
            w.motor = type("M", (), {"_case_dkey": staticmethod(lambda c: c["k"]),
                                     "scan": lambda self, include_closed, only_dkeys: secilen.append(set(only_dkeys))})()
            w.katalog = type("K", (), {})()
            w.katalog.db = db
            w.bridge = type("B", (), {"query_tum_dosyalar": lambda self, include_closed=True: [{"k": f"B|{i}"} for i in range(100)]})()
            w._taraf_tamamla = lambda cases: None
            uw.DATA_DIR = Path(td)
            w._arsiv_katalogla(adet=1)
            self.assertEqual(secilen[0], {"B|99"})


class TebligatSurecleri(unittest.TestCase):
    def test_csv_ve_katalog_birlesir(self):
        with tempfile.TemporaryDirectory() as td:
            eski = os.environ.get("UYAP_VERI_DIZINI")
            os.environ["UYAP_VERI_DIZINI"] = td
            try:
                (Path(td) / "tebligat_takip_listesi.csv").write_text(
                    "Gonderim_Tarihi,Tebligat_Turu,Dosya_No,Tebligat_Muhatabi,Muhatap_Rolu,Barkod_Veya_Delil_No,"
                    "Hukuki_Teblig_Tarihi,Teblig_Durumu_Sonuc,Yasal_Sure_Hesabi_Notu,Evrak_Adi,Evrak_Id\n"
                    "2026-10-01,Fiziki,2025/149,ALİ VELİ,Davalı,RR123TR,2026-10-05,Bizzat tebliğ,7 gün,Mazbata,5\n"
                    "2026-10-01,Fiziki,2024/1,BAŞKA,Davalı,RR9TR,,,,,6\n", encoding="utf-8")
                r = sunucu.tebligat_surecleri("2025/149", [{"tur": "Tebligat Mazbatası", "tarih": "2026-11-01", "skey": "s1",
                                                            "kategori": "", "yerel": 0, "aciklama": ""}])
            finally:
                if eski is None:
                    os.environ.pop("UYAP_VERI_DIZINI", None)
                else:
                    os.environ["UYAP_VERI_DIZINI"] = eski
        self.assertEqual(len(r), 2)
        self.assertEqual(r[1]["muhatap"], "ALİ VELİ")
        self.assertEqual(r[1]["teblig_tarihi"], "2026-10-05")
        self.assertEqual(r[0]["sonuc"], "henüz indirilmedi")


class DriveOncelik(unittest.TestCase):
    def test_dosya_siranin_basina_alinir(self):
        with tempfile.TemporaryDirectory() as td:
            eski = os.environ.get("UYAP_VERI_DIZINI")
            os.environ["UYAP_VERI_DIZINI"] = td
            ek = (sunucu.dosya_tazele_baslat, sunucu._ro, sunucu.GOREV_DURUM)
            sunucu.dosya_tazele_baslat = lambda dkey: {}
            sunucu._ro = lambda p: None
            sunucu.GOREV_DURUM = {}  # Senkron gerçekten başlatılmasın
            try:
                (Path(td) / "oncelikli_dosyalar.json").write_text(json.dumps({"dkeyler": ["A", "B"]}), encoding="utf-8")
                sunucu.dosya_drive_indir("B")
                v = json.loads((Path(td) / "oncelikli_dosyalar.json").read_text(encoding="utf-8"))
            finally:
                sunucu.dosya_tazele_baslat, sunucu._ro, sunucu.GOREV_DURUM = ek
                if eski is None:
                    os.environ.pop("UYAP_VERI_DIZINI", None)
                else:
                    os.environ["UYAP_VERI_DIZINI"] = eski
        self.assertEqual(v["dkeyler"], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
