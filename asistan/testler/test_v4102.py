# -*- coding: utf-8 -*-
"""v4.10.2: arşiv onarımı (bozuk/eksik PDF → resmî motor), Drive yolu temizliği, tebligat arşivi.
EN: archive repair, Drive path normalisation, tebligat archive registry."""
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "moduller" / "evrak"))
sys.path.insert(0, str(KOK / "moduller" / "avukatasistan"))

import oz_denetim  # noqa: E402


def _bozuk_pdf(yol: Path):
    """Eski (v4.9.x) yedek motorun ürettiği türden PDF: ReportLab + gömülmemiş Helvetica."""
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(yol))
    c.setFont("Helvetica", 11)
    c.drawString(50, 800, "T.C. ANKARA MAHKEMES")
    c.save()


class ArsivOnar(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        os.environ["UYAP_VERI_DIZINI"] = str(self.d)
        os.environ["CANASISTAN_VERI"] = str(self.d / "veri")
        import importlib
        import arsiv_onar
        self.ao = importlib.reload(arsiv_onar)
        self.udf = self.d / "evrak.udf"
        oz_denetim._ornek_udf(self.udf)
        self.pdf = self.d / "evrak.pdf"
        _bozuk_pdf(self.pdf)
        k = sqlite3.connect(str(self.d / "uyap_katalog.db"))
        k.executescript("""CREATE TABLE dosya(dkey TEXT PRIMARY KEY, birim TEXT, dosya_no TEXT);
            CREATE TABLE evrak(id INTEGER PRIMARY KEY, skey TEXT, dkey TEXT, path TEXT, pdf_path TEXT, durum TEXT,
                               sha256 TEXT, indirildi TEXT, hata TEXT);""")
        k.execute("INSERT INTO dosya VALUES ('d1','Ankara 1. Asliye Hukuk','2026/1')")
        k.execute("INSERT INTO evrak VALUES (1,'s1','d1',?,?,'indirildi',NULL,NULL,NULL)", (str(self.udf), str(self.pdf)))
        k.execute("INSERT INTO evrak VALUES (2,'s2','d1',?,?,'indirildi',NULL,NULL,NULL)",
                  (str(self.d / "kayip.udf"), str(self.d / "kayip.pdf")))
        k.commit()
        k.close()

    def tearDown(self):
        self.td.cleanup()
        os.environ.pop("UYAP_VERI_DIZINI", None)

    def test_bozuk_tespit_ve_onarim(self):
        self.assertIn("yedek motor", self.ao.bozuk_mu(self.pdf))
        r = self.ao.onar(sinir=10, salt_oku=False, drive_tara=False, log=lambda m: None)
        self.assertEqual(r["bozuk"], 2)
        self.assertEqual(r["onarilan"], 1)
        self.assertEqual(r["yeniden_indirilecek"], 1, "kaynağı olmayan evrak UYAP'tan yeniden indirilmeli")
        self.assertEqual(self.ao.bozuk_mu(self.pdf), "")
        self.assertIn(b"/FontFile2", self.pdf.read_bytes())
        k = sqlite3.connect(str(self.d / "uyap_katalog.db"))
        self.assertEqual(k.execute("SELECT durum FROM evrak WHERE id=2").fetchone()[0], "yeni")
        k.close()
        # ikinci tur: onarılan tekrar işlenmez
        r2 = self.ao.onar(sinir=10, salt_oku=True, drive_tara=False, log=lambda m: None)
        self.assertEqual(r2["bozuk"], 0)

    def test_salt_oku_degistirmez(self):
        once = self.pdf.read_bytes()
        r = self.ao.onar(sinir=10, salt_oku=True, drive_tara=False, log=lambda m: None)
        self.assertEqual(r["onarilan"], 0)
        self.assertEqual(self.pdf.read_bytes(), once)


class DriveYolu(unittest.TestCase):
    def test_ic_ice_kok_atilir(self):
        import google_drive_entegrasyonu as g
        self.assertEqual(g.GoogleDriveCloudClient.temiz_yol("UYAP_Arsiv/UYAP_Arsiv/DAVA_EVRAKLARI/x"), "DAVA_EVRAKLARI/x")
        self.assertEqual(g.GoogleDriveCloudClient.temiz_yol("DAVA_EVRAKLARI\\a\\b"), "DAVA_EVRAKLARI/a/b")

    def test_betik_tek_kaynak_v3(self):
        gs = (KOK / "drive_webhook.gs").read_text(encoding="utf-8")
        self.assertIn("var BETIK_SURUM = 3;", gs)
        self.assertIn("uzerine_yaz", gs)
        self.assertIn(gs.strip()[:200], (KOK.parent / "frontend" / "public" / "hayfa.js").read_text(encoding="utf-8"))



class TebligatArsivi(unittest.TestCase):
    def setUp(self):
        import datetime as dt
        import zipfile
        import importlib
        self.td = tempfile.TemporaryDirectory()
        self.d = Path(self.td.name)
        os.environ["UYAP_VERI_DIZINI"] = str(self.d)          # watcher_config yok → Drive yok → yerel arşiv
        import tebligat_arsiv
        self.ta = importlib.reload(tebligat_arsiv)
        self.ta.VERI = self.d / "veri"
        self.ta.DB = self.ta.VERI / "tebligat_arsiv.db"
        self.eyp = self.d / "5003283066058.eyp"
        with zipfile.ZipFile(self.eyp, "w") as z:
            z.writestr("ustyazi.txt", "deneme")
        self.csv = self.d / "tebligatlar.csv"
        self.csv.write_text("Gönderen;Konu\nX;Y\n", encoding="utf-8")
        g = dt.datetime(2026, 11, 20, 10, 0)
        self.item = {"barcode": "5003283066058", "uets_no": "U1", "court": "Ankara 1. Asliye Hukuk Mahkemesi",
                     "esas_no": "2026/12", "gonderen": "Ankara 1. AHM", "konu_raw": "Tensip zaptı",
                     "csv_path": str(self.csv), "deadlines": {"gelis_dt": g, "target_str": "09.12.2026", "target_dt": g}}

    def tearDown(self):
        self.td.cleanup()
        os.environ.pop("UYAP_VERI_DIZINI", None)

    def test_tur_yerel_arsiv_ve_arama(self):
        r = self.ta.tur(str(self.csv), [self.item], {"5003283066058": str(self.eyp)}, log=lambda m: None)
        self.assertEqual(r["arsivlenen"], 1)
        kok = self.ta.VERI / "tebligat_arsiv" / "UETS_Tebligat" / "Ankara 1. Asliye Hukuk Mahkemesi" / "2026-12"
        klasor = next(kok.glob("2026-11-20_5003283066058"))
        self.assertTrue((klasor / "5003283066058.eyp").is_file())
        kayit = json.loads((klasor / "tebligat.json").read_text(encoding="utf-8"))
        self.assertEqual(kayit["esas"], "2026/12")
        self.assertIn("Tensip", (klasor / "ozet.md").read_text(encoding="utf-8"))
        self.assertTrue(list((self.ta.VERI / "tebligat_arsiv" / "UETS_Tebligat" / "_CSV").rglob("*.csv")))
        # ikinci tur: mükerrer yazılmaz
        r2 = self.ta.tur(str(self.csv), [self.item], {"5003283066058": str(self.eyp)}, log=lambda m: None)
        self.assertEqual(r2["zaten"], 1)
        self.assertEqual(r2["csv"]["durum"], "zaten")
        self.assertTrue(self.ta.arsivde_mi("5003283066058"))
        self.assertEqual(self.ta.ara("tensip -istinaf")["toplam"], 1)
        self.assertEqual(self.ta.ara("istinaf")["toplam"], 0)
        self.assertIn("ozet_md", self.ta.detay("5003283066058"))


if __name__ == "__main__":
    unittest.main()
