"""UYAP giriş ayarları, 'bağlı tut' döngüsü ve Android CDP köprüsü."""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from unittest import mock

os.environ.setdefault("CANASISTAN_VERI", tempfile.mkdtemp())
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sunucu  # noqa: E402


class AyarTesti(unittest.TestCase):
    def setUp(self):
        global GECICI
        GECICI = tempfile.mkdtemp()
        y = mock.patch.object(sunucu, "evrak_veri_dizini", lambda: Path(GECICI))
        y.start()
        self.addCleanup(y.stop)
        e = mock.patch.dict(os.environ, {"UYAP_E_IMZA_PIN": ""})
        e.start()
        self.addCleanup(e.stop)

    def test_bilgi_yokken_etkin_degil(self):
        ok, neden = sunucu.BAGLI_TUT.etkin()
        self.assertFalse(ok)
        self.assertIn("Giriş bilgisi yok", neden)

    def test_mobil_imza_kaydet_ve_maskele(self):
        a = sunucu.uyap_ayar_yaz({"tc": "12345678901", "gsm": "0532 123 45 67", "operator": "vodafone"})
        self.assertTrue(a["tc_var"] and a["gsm_var"])
        self.assertTrue(a["tc"].endswith("901") and "123456" not in a["tc"])
        cfg = json.loads((Path(GECICI) / ".uyap_config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["gsm"], "5321234567")
        self.assertEqual(cfg["operator"], "vodafone")
        self.assertTrue(sunucu.BAGLI_TUT.etkin()[0])

    def test_pin_dosyasi_ve_silme(self):
        sunucu.uyap_ayar_yaz({"pin": "123456"})
        self.assertEqual((Path(GECICI) / "pin.txt").read_text(encoding="utf-8"), "123456")
        self.assertTrue(sunucu.uyap_ayar_oku()["pin_var"])
        sunucu.uyap_ayar_yaz({"sil": "pin"})
        self.assertFalse(sunucu.uyap_ayar_oku()["pin_var"])

    def test_gecersiz_girdi(self):
        with self.assertRaises(ValueError):
            sunucu.uyap_ayar_yaz({"tc": "123"})
        with self.assertRaises(ValueError):
            sunucu.uyap_ayar_yaz({"gsm": "2121234567"})

    def test_bagli_tut_kapatilabilir(self):
        sunucu.uyap_ayar_yaz({"pin": "1111", "bagli_tut": False})
        ok, neden = sunucu.BAGLI_TUT.etkin()
        self.assertFalse(ok)
        self.assertIn("kapalı", neden)

    def test_oturum_durumu_gunlukten(self):
        g = sunucu.GOREV_DURUM["evrak-nobetci"]
        g.gunluk.clear()
        g.gunluk.extend(["⚠️ UYAP oturumu açık değil!", "✅ UYAP oturumu doğrulandı: Sayın Avukat"])
        self.assertTrue(sunucu.BAGLI_TUT.durum()["oturum"])
        g.gunluk.append("❌ UYAP oturumu açılamadı: süre doldu")
        self.assertFalse(sunucu.BAGLI_TUT.durum()["oturum"])
        g.gunluk.clear()


@unittest.skipUnless(sys.platform.startswith("linux"), "soyut UNIX soketi yalnız Linux/Android")
class KopruTesti(unittest.TestCase):
    def test_tcp_soyut_sokete_aktarir(self):
        ad = f"caneditor_test_{os.getpid()}"
        hedef = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        hedef.bind("\0" + ad)
        hedef.listen(1)

        def yanki():
            c, _ = hedef.accept()
            c.sendall(b"ECHO:" + c.recv(100))
            c.close()
        threading.Thread(target=yanki, daemon=True).start()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        os.environ["CANASISTAN_WEBVIEW_SOKET"] = ad
        try:
            sunucu.cdp_kopru_baslat(port)
            for _ in range(50):
                try:
                    c = socket.create_connection(("127.0.0.1", port), timeout=1)
                    break
                except OSError:
                    time.sleep(0.05)
            c.sendall(b"GET /json/version")
            self.assertEqual(c.recv(100), b"ECHO:GET /json/version")
            c.close()
        finally:
            del os.environ["CANASISTAN_WEBVIEW_SOKET"]


if __name__ == "__main__":
    unittest.main()
