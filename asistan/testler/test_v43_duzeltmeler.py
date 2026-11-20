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
        self.uw.DATA_DIR = Path(self.td.name)  # Drive yükleme defteri geçici dizine yazılsın
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


class DriveWebhookIndeksTesti(unittest.TestCase):
    """Drive'ın tamamı Apps Script 'list' ile sayfa sayfa indekslenir (telefonda eskiden /sdcard/Download taranıyordu)."""

    def test_sayfali_listeleme_ve_eski_kayitlarin_temizlenmesi(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import drive_indeks as di

        sayfalar = {
            None: {"status": "ok", "dosyalar": [{"id": f"a{i}", "ad": f"dilekce{i}.udf", "klasor": "Davalar/2025-104 E.", "boyut": 10, "mtime": 1700000000, "url": "https://drive/a"} for i in range(3)], "state": "S1"},
            "S1": {"status": "ok", "dosyalar": [{"id": "b1", "ad": "Bilirkişi Raporu.pdf", "klasor": "", "boyut": 2048, "mtime": 1700000001, "url": "u"},
                                                {"id": "g1", "ad": "Notlar", "klasor": "X", "boyut": 0, "mtime": 1, "url": "u", "mime": "application/vnd.google-apps.document"}], "state": None},
        }

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                g = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                body = _json.dumps(sayfalar[g.get("state")]).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td:
                db = Path(td) / "drive_indeks.db"
                # telefon klasöründen gelmiş eski kayıt (temizlenmeli)
                with di._db_ac(db) as c:
                    c.execute("INSERT INTO drive_dosya(rel_yol,ad) VALUES ('Download/eski.apk','eski.apk')")
                r = di.indeksle_webhook(db, f"http://127.0.0.1:{srv.server_port}/exec")
                self.assertEqual(r["toplam"], 5)
                self.assertEqual(r["silinen"], 1)
                a = di.ara(db, "bilirkisi")
                self.assertEqual([x["ad"] for x in a["sonuclar"]], ["Bilirkişi Raporu.pdf"])
                self.assertEqual(di.ara(db, "", uzanti="gdocument")["sonuclar"][0]["rel_yol"], "gdrive:g1")
                self.assertEqual(di.ara(db, "2025/104")["toplam"], 5)
                self.assertIn("Google Drive", di.indeks_ozeti(db)["kaynak"])
        finally:
            srv.shutdown()

    def test_eski_betik_anlasilir_hata(self):
        import drive_indeks as di
        self.assertIn("eski sürüm", di._eski_betik_mesaji({"status": "error", "message": "Exception: Invalid argument: base64"}))


class DriveEsitlemeDefteriTesti(unittest.TestCase):
    """Webhook modunda bir evrak yalnızca bir kez yüklenir; Apps Script hatası 'başarılı' sayılmaz."""

    def test_bir_kez_yukleme_ve_hata_sayimi(self):
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import drive_indeks as di
        gelen = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                g = _json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                gelen.append(g["filename"])
                yanit = {"status": "error", "message": "kota"} if g["filename"] == "bozuk.pdf" else {"status": "success", "fileId": "F" + g["filename"], "url": "u"}
                body = _json.dumps(yanit).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                (td / "watcher_config.json").write_text(_json.dumps({"google_drive_webhook": f"http://127.0.0.1:{srv.server_port}/exec"}))
                kat = td / "uyap_katalog.db"
                c = sqlite3.connect(str(kat))
                c.executescript("CREATE TABLE evrak(id INTEGER, path TEXT, pdf_path TEXT, durum TEXT, tarih TEXT, dkey TEXT);"
                                "CREATE TABLE dosya(dkey TEXT, birim TEXT, dosya_no TEXT);"
                                "INSERT INTO dosya VALUES ('d1','Ankara 3. Asliye','2025/104');")
                for i, ad in enumerate(["a.pdf", "b.pdf", "bozuk.pdf"]):
                    (td / ad).write_bytes(b"%PDF" + ad.encode())
                    c.execute("INSERT INTO evrak VALUES (?,?,?,'indirildi',?, 'd1')", (i, None, str(td / ad), f"2025-01-0{i+1}"))
                c.commit(); c.close()
                r1 = di.esitle_eksikler(kat, td)
                self.assertEqual((r1["aktarilan"], r1["hata"]), (2, 1))
                r2 = di.esitle_eksikler(kat, td)   # ikinci basış: yalnız bozuk olan yeniden denenir
                self.assertEqual((r2["aktarilan"], r2["hata"]), (0, 1))
                self.assertEqual(gelen.count("a.pdf"), 1)
                oz = di.esitleme_ozeti(kat, td)
                self.assertEqual((oz["indirilen"], oz["drivede"]), (3, 2))
        finally:
            srv.shutdown()


class DaireSuzgeciTesti(unittest.TestCase):
    def test_daire_desenleri(self):
        import hayfa_kopru as h
        self.assertTrue(h._daire_deseni("15HD").search("YARGITAY 15. HUKUK DAİRESİ E. 2014/1"))
        self.assertTrue(h._daire_deseni("8CD").search("Yargıtay 8.Ceza Dairesi"))
        self.assertFalse(h._daire_deseni("1HD").search("Yargıtay 11. Hukuk Dairesi"))
        self.assertTrue(h._daire_deseni("Danistay6").search("Danıştay 6. Daire"))


class AndroidDnsYayilimTesti(unittest.TestCase):
    def test_alt_surec_dns_yamasini_yukler(self):
        import subprocess
        env = dict(os.environ, CANASISTAN_ANDROID="1", PYTHONPATH=str(ASISTAN_DIR))
        kod = "import socket, dns_cozucu; print(socket.getaddrinfo is dns_cozucu._guvenli_getaddrinfo)"
        r = subprocess.run([sys.executable, "-c", kod], env=env, capture_output=True, text=True, cwd=tempfile.gettempdir())
        self.assertEqual(r.stdout.strip(), "True", r.stderr)


class MukerrerTahminTesti(unittest.TestCase):
    """Aynı dosyada aynı gönderenden aynı adlı ek 2 kez aynı içerikle gelince, sonrakiler HİÇ indirilmeden ayıklanır."""

    def test_ogrenme_ve_dogrulama(self):
        import evrak_katalog as ek
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            kat = ek.Katalog(td / "k.db")
            simdi = "2026-01-01T00:00:00"
            with kat.db:
                kat.db.execute("INSERT INTO dosya(dkey, birim, dosya_no) VALUES ('D1','Ankara 3. Asliye','2025/104')")
                for i in range(1, 7):  # 6 dilekçe, her birinde "Vekaletname" eki
                    kat.db.execute("INSERT INTO evrak(skey,dkey,is_ek,tur,gonderen,tarih,durum,ilk_gorulme,son_gorulme) "
                                   "VALUES (?,?,1,'Vekaletname','Av. Can',?, 'yeni',?,?)", (f"K|{i}|1", "D1", f"2026-01-0{i}", simdi, simdi))
                kat.db.execute("INSERT INTO evrak(skey,dkey,is_ek,tur,gonderen,tarih,durum,ilk_gorulme,son_gorulme) "
                               "VALUES ('K|9|1','D1',1,'Bilirkişi Raporu','Mahkeme','2026-01-09','yeni',?,?)", (simdi, simdi))
            m = ek.Motor(None, kat, td)
            m.min_d = m.max_d = 0.0
            m._sleep = lambda s: None
            m._sync_to_drive = lambda p: None
            m._queue_conversion = lambda f: None
            m.oturum = "x"
            cagrilan = []
            icerik = {"Vekaletname": b"%PDF-vekalet", "Bilirkişi Raporu": b"%PDF-rapor"}

            def sahte_fetch(eid, refreshed=None):
                cagrilan.append(eid)
                r = kat.get(eid)
                return icerik[r["tur"]], {"contentType": "application/pdf"}, r, ""

            m.fetch = sahte_fetch
            ids = [r["id"] for r in kat.db.execute("SELECT id FROM evrak ORDER BY id")]
            st = m.download(ids)
            # İlk iki vekaletname indirilir (biri asıl, biri içerikten mükerrer) → kalıp öğrenilir → kalan 4'ü indirilmez
            self.assertEqual(len(cagrilan), 3)  # 2 vekaletname + 1 rapor
            self.assertEqual(st["indirildi"], 2)
            self.assertEqual(st["tahmini_mukerrer"], 4)
            self.assertEqual(kat.db.execute("SELECT COUNT(*) FROM evrak WHERE hata=?", (m.TAHMIN_ISARETI,)).fetchone()[0], 4)
            # Sonraki çalışmada yeni gelen 7. vekaletname baştan (ön kontrolde) ayıklanır
            with kat.db:
                kat.db.execute("INSERT INTO evrak(skey,dkey,is_ek,tur,gonderen,tarih,durum,ilk_gorulme,son_gorulme) "
                               "VALUES ('K|7|1','D1',1,'Vekaletname','Av. Can','2026-01-07','yeni',?,?)", (simdi, simdi))
            yeni_id = kat.db.execute("SELECT id FROM evrak WHERE skey='K|7|1'").fetchone()[0]
            cagrilan.clear()
            kalan, plan = m.on_kontrol([yeni_id])
            self.assertEqual((kalan, plan["tahmini_mukerrer"]), ([], 1))
            # Boştaki doğrulama: biri aslında farklıysa indirilir ve kalıp artık kullanılmaz
            icerik["Vekaletname"] = b"%PDF-YENI-vekalet"
            d = m.tahminleri_dogrula(limit=1)
            self.assertEqual(d["dogrulanan"], 1)
            self.assertEqual(d["indirildi"], 1)
            self.assertEqual(m._tahmin_haritasi(), {})


class KararIstatistikTesti(unittest.TestCase):
    def test_en_son_karar_bulunur_bosluklara_ragmen(self):
        import hayfa_kopru as h
        mevcut = set(range(1, 123457)) - {500, 501, 90000, 123400}
        eski = h._karar_var_mi
        h._karar_var_mi = lambda k: k in mevcut
        try:
            with tempfile.TemporaryDirectory() as td:
                r = h.karar_istatistik(Path(td), yenile=True)
                self.assertEqual(r["en_son_karar_no"], 123456)
        finally:
            h._karar_var_mi = eski
