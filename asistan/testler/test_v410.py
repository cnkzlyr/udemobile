# -*- coding: utf-8 -*-
"""v4.10.0 regresyon testleri / regression tests:
  * udf_to_pdf(p, hedef) ikinci argümanı HEDEF yoludur (eskiden timeout sanılıp bozuk yedek motora düşülüyordu)
  * yedek (ReportLab) motor Türkçe glifli TTF gömer, UDF ofset modelini ve paragrafları korur
  * kişisel değerler koddan değil kisisel_ayar'dan gelir (PIN/TC/token koda yazılmaz)
  * caneditor CLI tüm komutları ayrıştırır; öz-denetim günlüğü PIN'i maskeler"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "moduller" / "evrak"))

import donusturucu  # noqa: E402
import kisisel_ayar  # noqa: E402
import oz_denetim  # noqa: E402


class V410(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.dir = Path(self.td.name)
        os.environ["CANASISTAN_VERI"] = str(self.dir / "veri")
        self.udf = self.dir / "dilekce.udf"
        oz_denetim._ornek_udf(self.udf)

    def tearDown(self):
        self.td.cleanup()

    def test_yedek_motor_turkce_ve_font(self):
        pdf = donusturucu.udf_python_to_pdf(self.udf, self.dir / "y.pdf")
        self.assertIsNotNone(pdf)
        metin, gomulu = oz_denetim._pdf_metin_font(pdf)
        self.assertIn("Öztürk", metin)
        self.assertIn("ASLİYE", metin)
        self.assertTrue(gomulu, "TTF gömülmeli (Helvetica değil)")
        self.assertEqual(oz_denetim._bozuk_pdf_mi(pdf), "")

    def test_ikinci_arguman_hedef_yol(self):
        hedef = self.dir / "alt" / "hedef.pdf"
        r = donusturucu.udf_to_pdf(self.udf, hedef, timeout=120)
        self.assertEqual(Path(r), hedef)
        self.assertGreater(hedef.stat().st_size, 0)
        r2 = donusturucu.udf_to_pdf(self.udf, 120)  # geriye uyum: int → timeout
        self.assertTrue(Path(r2).is_file())

    def test_kisisel_ayar_ortamdan(self):
        os.environ["EIMZA_PIN"] = "000000"
        try:
            self.assertEqual(kisisel_ayar.al("pin"), "000000")
        finally:
            del os.environ["EIMZA_PIN"]
        self.assertEqual(kisisel_ayar.operator_kodu("Vodafone"), 3)

    def test_koda_sabit_pin_tc_token_yazilmamis(self):
        # Değerlerin kendisi yerine BİÇİM aranır: PIN = "<6 rakam>" atanması, 11 haneli TC, Telegram bot token'ı
        kaliplar = [re.compile(r"""(?i)\bpin\s*=\s*["']\d{4,8}["']"""),
                    re.compile(r"""(?i)\b(tc|tckn|user_tc)\w*\s*=\s*["'][1-9]\d{10}["']"""),
                    re.compile(r"""["']\d{8,10}:AA[A-Za-z0-9_-]{30,}["']""")]
        for f in list(KOK.rglob("*.py")) + list((KOK.parent / "scripts").glob("*.py")):
            if "testler" in f.parts or "tests" in f.parts:
                continue
            icerik = f.read_text(encoding="utf-8", errors="ignore")
            for k in kaliplar:
                self.assertIsNone(k.search(icerik), f"{f}: kişisel değer koda yazılmış ({k.pattern})")

    def test_cli_ayristirici(self):
        import caneditor_cli
        ap = caneditor_cli.ayrıştırıcı()
        for argv in (["durum"], ["evrak", "ara", "x", "--kategori", "tebligat"], ["pdf", "a.udf"],
                     ["imzala", "a.udf", "--yontem", "mobil"], ["ticktick", "denetle"], ["oz-denetim", "--salt-oku"],
                     ["hayfa", "mevzuat", "kira", "--madde"], ["api", "GET", "/api/durum"], ["log", "-f"]):
            self.assertTrue(ap.parse_args(argv).fn)

    def test_gunluk_pin_maskelenir(self):
        oz_denetim.kaydet("test", "pin=123456 ile denendi")
        self.assertIn("pin=******", "\n".join(oz_denetim.son_kayitlar(5)))


if __name__ == "__main__":
    unittest.main()
