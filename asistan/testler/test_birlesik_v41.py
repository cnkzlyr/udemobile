#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CanEditor v4.1 Birleşik Hukuk Platformu — kapsamlı birim & entegrasyon testleri."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ASISTAN_DIR = Path(__file__).resolve().parents[1]
if str(ASISTAN_DIR) not in sys.path:
    sys.path.insert(0, str(ASISTAN_DIR))

import drive_indeks
import entegrasyon
import hayfa_kopru
import jar_donustur
import sunucu


class DriveIndeksTesti(unittest.TestCase):
    def test_indeksle_ara_ve_traversal_koruma(self):
        with tempfile.TemporaryDirectory() as td:
            kok = Path(td) / "drive"
            (kok / "DAVA_EVRAKLARI" / "Ankara 3. Asliye Hukuk" / "2025_142").mkdir(parents=True)
            f1 = kok / "DAVA_EVRAKLARI" / "Ankara 3. Asliye Hukuk" / "2025_142" / "Bilirkişi_Raporu.pdf"
            f1.write_bytes(b"%PDF-1.4 test icerik")
            f2 = kok / "Dilekce_2024-88.udf"
            f2.write_bytes(b"PK\x03\x04")

            db = Path(td) / "drive_indeks.db"
            r = drive_indeks.indeksle(db, kok)
            self.assertEqual(r["toplam"], 2)
            self.assertEqual(r["yeni"], 2)

            # Türkçe harf duyarsız arama ve esas no çıkarımı
            s = drive_indeks.ara(db, q="bilirkisi 2025/142")
            self.assertTrue(s["hazir"])
            self.assertEqual(len(s["sonuclar"]), 1)
            self.assertEqual(s["sonuclar"][0]["esas_no"], "2025/142")

            # İkinci indekslemede değişmeyen dosya yeniden yazılmaz
            r2 = drive_indeks.indeksle(db, kok)
            self.assertEqual(r2["yeni"], 0)
            self.assertEqual(r2["guncellenen"], 0)

            # Path traversal engellenir
            self.assertIsNone(drive_indeks.guvenli_drive_dosyasi(kok, "../drive_indeks.db"))
            self.assertIsNotNone(drive_indeks.guvenli_drive_dosyasi(kok, "Dilekce_2024-88.udf"))


class EntegrasyonAyarTesti(unittest.TestCase):
    def test_env_maskeleme_ve_kayit(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            eski_nt = os.environ.pop("NOTION_TOKEN", None)
            eski_tt = os.environ.pop("TICKTICK_TOKEN", None)
            try:
                oz = entegrasyon.ayar_kaydet(d, {
                    "notion_token": "ntn_test_gizli_1234567890",
                    "ticktick_token": "tp_test_gizli_abcdef1234",
                    "otomatik_senkron": True,
                })
                self.assertTrue(oz["notion_bagli"])
                self.assertTrue(oz["ticktick_bagli"])
                self.assertIn("••••", oz["notion_token"])
                self.assertNotIn("gizli", oz["notion_token"])
                self.assertTrue((d / ".env").is_file())
            finally:
                os.environ.pop("NOTION_TOKEN", None)
                os.environ.pop("TICKTICK_TOKEN", None)
                if eski_nt is not None:
                    os.environ["NOTION_TOKEN"] = eski_nt
                if eski_tt is not None:
                    os.environ["TICKTICK_TOKEN"] = eski_tt


class HayfaCevrimdisiTesti(unittest.TestCase):
    def test_adliye_rehberi_cevrimdisi(self):
        r = hayfa_kopru.adliye_ara(q="Ankara 1. Genel İcra")
        self.assertGreaterEqual(r["bina_sayisi"], 10)
        self.assertGreaterEqual(r["birim_sayisi"], 50)
        self.assertGreaterEqual(len(r["birimler"]), 1)
        self.assertTrue(any("TR" in ib.get("iban", "") for ib in r["birimler"][0].get("ibanlar", [])))


class UyapHataDuzeltmeTesti(unittest.TestCase):
    def test_android_webview_ws_url_normalizasyon(self):
        evrak_dir = ASISTAN_DIR / "moduller" / "evrak"
        if str(evrak_dir) not in sys.path:
            sys.path.insert(0, str(evrak_dir))
        import uyap_indirici as ui
        b = ui.UyapBrowserBridge(port=9223)
        self.assertEqual(b._ws_url({"webSocketDebuggerUrl": "ws://localhost/devtools/page/1"}), "ws://127.0.0.1:9223/devtools/page/1")
        self.assertEqual(b._ws_url({"webSocketDebuggerUrl": "ws:///devtools/page/2"}), "ws://127.0.0.1:9223/devtools/page/2")
        self.assertEqual(b._ws_url({"webSocketDebuggerUrl": "ws://localhost:9223/devtools/page/3"}), "ws://127.0.0.1:9223/devtools/page/3")

    def test_watcher_olmayan_surucude_cokmez(self):
        evrak_dir = ASISTAN_DIR / "moduller" / "evrak"
        if str(evrak_dir) not in sys.path:
            sys.path.insert(0, str(evrak_dir))
        import uyap_watcher as uw
        with tempfile.TemporaryDirectory() as td:
            eski_data = uw.DATA_DIR
            try:
                uw.DATA_DIR = Path(td)
                cfg = uw.load_config()
                cfg["google_drive_dir"] = r"Q:\Olmayan_Surucu_999\UYAP_Arsiv"
                w = uw.UyapWatcher(cfg)
                self.assertTrue(w.download_dir.is_dir())
            finally:
                uw.DATA_DIR = eski_data


class BirlesikApiTesti(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.kok = Path(cls.td.name)
        cls.eski_env = {k: os.environ.get(k) for k in ("CANASISTAN_VERI", "UYAP_VERI_DIZINI")}
        os.environ["CANASISTAN_VERI"] = str(cls.kok / "veri")
        os.environ["UYAP_VERI_DIZINI"] = str(cls.kok / "evrak")
        (cls.kok / "evrak").mkdir(parents=True, exist_ok=True)
        (cls.kok / "drive").mkdir(parents=True, exist_ok=True)
        (cls.kok / "drive" / "2025_77_Karar.pdf").write_bytes(b"%PDF-1.4 karar")

        # Sahte katalog DB oluştur
        c = sqlite3.connect(str(cls.kok / "evrak" / "uyap_katalog.db"))
        c.executescript("""
            CREATE TABLE dosya(dkey TEXT PRIMARY KEY, birim TEXT, dosya_no TEXT, dosya_tur TEXT, durum TEXT,
                               yargi TEXT, acilis TEXT, dosya_id TEXT, taraflar TEXT, taraf_ara TEXT,
                               muvekkil TEXT, muvekkil_ara TEXT, evrak_sayisi INTEGER, taranma TEXT, oturum TEXT);
            CREATE TABLE evrak(id INTEGER PRIMARY KEY, skey TEXT UNIQUE, dkey TEXT, tur TEXT, aciklama TEXT,
                               tarih TEXT, kategori TEXT, durum TEXT, uzanti TEXT, is_ek INTEGER DEFAULT 0,
                               ara TEXT, path TEXT, pdf_path TEXT, ilk_gorulme TEXT);
            INSERT INTO dosya VALUES ('d1','Ankara 2. Asliye Hukuk','2025/77','Hukuk','Açık','Hukuk','2025-01-10',
                                      'id1','Ali Veli','ali veli','Ali Veli','ali veli',1,'2026-11-18','o1');
            INSERT INTO evrak VALUES (1,'s1','d1','Bilirkişi Raporu','Ek rapor','2026-11-17','bilirkisi',
                                      'indirildi','pdf',0,'bilirkisi raporu',NULL,NULL,'2026-11-18T10:00:00');
        """)
        c.commit()
        c.close()

        cls.anahtar = "test-anahtar-v41"
        cls.srv = sunucu.sunucu_olustur(0, cls.anahtar)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        for k, v in cls.eski_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls.td.cleanup()

    def _istek(self, yol: str, govde=None):
        data = json.dumps(govde).encode("utf-8") if govde is not None else None
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{yol}",
            data=data,
            headers={"X-Asistan-Anahtar": self.anahtar, "Content-Type": "application/json"},
            method="POST" if govde is not None else "GET",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_dosyalar_not_drive_hayfa_jar_uclari(self):
        kod, v = self._istek("/api/dosyalar?durum=A%C3%A7%C4%B1k")
        self.assertEqual(kod, 200)
        self.assertEqual(v["toplam"], 1)
        self.assertEqual(v["dosyalar"][0]["dosya_no"], "2025/77")

        # Not ekle ve detayda doğrula
        kod, n = self._istek("/api/dosya/not", {"dkey": "d1", "esas_no": "2025/77", "baslik": "Test Not", "metin": "İtiraz hazırlanacak"})
        self.assertEqual(kod, 200)
        self.assertTrue(n["ok"])

        # Drive ayar + indeksle + ara
        kod, _ = self._istek("/api/drive/ayar", {"google_drive_dir": str(self.kok / "drive")})
        self.assertEqual(kod, 200)
        kod, idx = self._istek("/api/drive/indeksle", {})
        self.assertEqual(kod, 200)
        self.assertEqual(idx["toplam"], 1)

        kod, det = self._istek("/api/dosya/detay?dkey=d1")
        self.assertEqual(kod, 200)
        self.assertEqual(len(det["notlar"]), 1)
        self.assertEqual(len(det["drive_dosyalar"]), 1)

        # HAYFA çevrimdışı adliye rehberi
        kod, adl = self._istek("/api/hayfa/adliyeler?q=Ankara")
        self.assertEqual(kod, 200)
        self.assertGreaterEqual(len(adl["birimler"]), 1)

        # JAR durum ucu
        kod, jd = self._istek("/api/donustur/durum")
        self.assertEqual(kod, 200)
        self.assertIn("hazir", jd)


if __name__ == "__main__":
    unittest.main()
