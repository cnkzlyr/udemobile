#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.3 hata düzeltmelerinin gerileme testleri.

* Nöbetçi döngüsü: sqlite3.Row üzerinde .get() çağrısı her turda çöküyordu.
* Arşiv eşitleme: 'yok' (UYAP'ta artık yok) evraklar sonsuza dek yeniden deneniyor, bekleme moduna hiç geçilmiyordu.
* Sunucu: tarama yapılmamış (evrak tablosu olmayan) katalogda tüm sekmeler 500 "no such table" veriyordu.
* Tanı ekranı: istek sayacı hiç artmıyordu.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ASISTAN_DIR = Path(__file__).resolve().parents[1]
EVRAK_DIR = ASISTAN_DIR / "moduller" / "evrak"
for p in (ASISTAN_DIR, EVRAK_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import sunucu  # noqa: E402


class SahteKatalog:
    def __init__(self, db):
        self.db = db

    def get(self, eid):
        return self.db.execute("SELECT * FROM evrak WHERE id=?", (eid,)).fetchone()


class SahteMotor:
    def download(self, ids):
        return {"indirildi": 0, "onbellek": 0, "mukerrer": len(ids), "hata": 0}


class SahteBulut:
    is_configured = True

    def __init__(self):
        self.yuklenen = []

    def upload_file(self, p, remote_folder_path=""):
        self.yuklenen.append((Path(p).name, remote_folder_path))


class NobetciTesti(unittest.TestCase):
    def setUp(self):
        import uyap_watcher as uw
        self.uw = uw
        self.td = tempfile.TemporaryDirectory()
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.executescript("""
            CREATE TABLE evrak(id INTEGER PRIMARY KEY, durum TEXT, pdf_path TEXT, kategori TEXT, tarih TEXT,
                               birim TEXT, dosya_no TEXT);
        """)
        pdf = Path(self.td.name) / "a.pdf"
        pdf.write_bytes(b"%PDF")
        db.execute("INSERT INTO evrak VALUES (1,'yeni',?, 'karar','2024-01-01','Ankara 1. Asliye','2024/1')", (str(pdf),))
        db.execute("INSERT INTO evrak VALUES (2,'yok',NULL,'karar','2024-01-02','X','1')")
        db.execute("INSERT INTO evrak VALUES (3,'hata',NULL,'karar','2024-01-03','X','2')")
        db.execute("INSERT INTO evrak VALUES (4,'yeni',NULL,'dilekce','2024-01-04','X','3')")
        self.db = db

    def tearDown(self):
        self.td.cleanup()

    def _w(self):
        w = self.uw.UyapWatcher.__new__(self.uw.UyapWatcher)
        w.katalog = SahteKatalog(self.db)
        w.bridge = object()
        w.motor = SahteMotor()
        w.cloud = SahteBulut()
        return w

    def test_row_get_cokmesi_yok_ve_drive_yuklenir(self):
        w = self._w()
        w.get_missing_doc_ids = lambda limit=50: [1]
        w.reconcile_missing_docs(max_batch=5)  # eskiden: 'sqlite3.Row' object has no attribute 'get'
        self.assertEqual(w.cloud.yuklenen, [("a.pdf", "DAVA_EVRAKLARI/Ankara 1. Asliye/2024/1")])

    def test_yok_atlanir_hata_en_sona(self):
        w = self._w()
        ids = w.get_priority_backlog_ids(limit=10)
        self.assertNotIn(2, ids)
        self.assertEqual(ids[-1], 3)


class SunucuTesti(unittest.TestCase):
    def test_taranmamis_katalog_500_vermez(self):
        with tempfile.TemporaryDirectory() as td:
            eski = os.environ.get("UYAP_VERI_DIZINI")
            os.environ["UYAP_VERI_DIZINI"] = td
            try:
                c = sqlite3.connect(str(Path(td) / "uyap_katalog.db"))
                c.execute("CREATE TABLE gorev_sure(id INTEGER)")  # yalnız süre modülünün tablosu
                c.commit()
                c.close()
                self.assertFalse(sunucu.evrak_ara("ahmet")["hazir"])
                self.assertFalse(sunucu.dosyalar_listele().get("hazir", False))
            finally:
                if eski is None:
                    os.environ.pop("UYAP_VERI_DIZINI", None)
                else:
                    os.environ["UYAP_VERI_DIZINI"] = eski

    def test_istek_sayaci_ve_kesinti(self):
        once = sunucu.TOPLAM_ISTEK
        sunucu.istek_say()
        self.assertEqual(sunucu.TOPLAM_ISTEK, once + 1)
        k0 = sunucu.KESINTI_SAYISI
        sunucu.kesinti_kaydet(True)
        sunucu.kesinti_kaydet(False)
        self.assertEqual(sunucu.KESINTI_SAYISI, k0 + 1)
        self.assertTrue(sunucu.SON_KESINTI)


if __name__ == "__main__":
    unittest.main()
