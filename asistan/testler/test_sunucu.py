# -*- coding: utf-8 -*-
"""Birleşik asistan sunucusu: güvenlik kuralları ve iki modülün gerçek şemalarıyla uçtan uca test.

Katalog tablolarını evrak modülünün kendi Katalog sınıfı, defter tablolarını avukatasistan'ın
kendi defter modülü oluşturur; böylece sunucunun sorguları modül şemalarıyla uyumlu kalır.
Çalıştırma:  python3 -m unittest discover -s asistan/testler -v
"""
import http.client
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

GECICI = tempfile.mkdtemp(prefix="canasistan-test-")
os.environ["UYAP_VERI_DIZINI"] = GECICI
os.environ["DEFTER_URL"] = "sqlite:///" + os.path.join(GECICI, "defter.db")
os.environ["CANASISTAN_VERI"] = os.path.join(GECICI, "sunucu")

import sunucu  # noqa: E402

ANAHTAR = "test-anahtari-123"


def _katalog_hazirla():
    sys.path.insert(0, str(KOK / "moduller" / "evrak"))
    import evrak_katalog as ek
    k = ek.Katalog(Path(GECICI) / "uyap_katalog.db")
    db = k.db
    db.execute("INSERT INTO dosya(dkey,birim,dosya_no,taraflar,taraf_ara,muvekkil) VALUES(?,?,?,?,?,?)",
               ("d1", "İstanbul 3. Asliye Hukuk Mahkemesi", "2026/145", "ÇAĞLAR YILMAZ; ŞİRKET A.Ş.",
                ek.fold("ÇAĞLAR YILMAZ; ŞİRKET A.Ş."), "ÇAĞLAR YILMAZ"))
    pdf = Path(GECICI) / "bilirkisi.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    db.execute("INSERT INTO evrak(skey,dkey,tur,aciklama,tarih,kategori,ara,pdf_path,durum) VALUES(?,?,?,?,?,?,?,?,?)",
               ("s1", "d1", "Bilirkişi Raporu", "Bilirkişi Raporu", "2026-11-01", "Bilirkişi",
                ek.fold("Bilirkişi Raporu"), str(pdf), "indirildi"))
    db.execute("INSERT INTO evrak(skey,dkey,tur,aciklama,tarih,kategori,ara,durum) VALUES(?,?,?,?,?,?,?,?)",
               ("s2", "d1", "Ara Karar", "Duruşma Ara Kararı", "2026-10-01", "Karar", ek.fold("Duruşma Ara Kararı"), "yeni"))
    yarin = (datetime.now() + timedelta(days=3)).strftime("%d.%m.%Y")
    db.execute("INSERT INTO durusma(dkey,birim,dosya_no,tarih,saat,yer,aciklama) VALUES(?,?,?,?,?,?,?)",
               ("d1", "İstanbul 3. Asliye Hukuk Mahkemesi", "2026/145", yarin, "10:30", "Salon 4", "Ön inceleme"))
    db.commit()


def _defter_hazirla():
    sys.path.insert(0, str(KOK / "moduller" / "avukatasistan"))
    import defter
    son = datetime.now() + timedelta(days=10)
    defter.tebligat_kaydet({"barcode": "5003283066058", "court": "Ankara 2. İş Mahkemesi", "esas_no": "2026/77",
                            "konu_raw": "Gerekçeli karar", "deadlines": {"target_str": son.strftime("%d.%m.%Y"),
                                                                       "gelis_dt": datetime.now()}})
    # Aynı duruşma hem defterde hem katalogda → ajandada tek görünmeli
    gun = (datetime.now() + timedelta(days=3)).replace(hour=10, minute=30, second=0, microsecond=0)
    defter.durusma_kaydet("uid-1", "İstanbul 3. Asliye Hukuk Mahkemesi", "2026/145", gun, baslik="Ön inceleme")


class SunucuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _katalog_hazirla()
        _defter_hazirla()
        cls.srv = sunucu.sunucu_olustur(0, ANAHTAR)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def istek(self, yol, yontem="GET", anahtar=ANAHTAR, host=None, govde=None, origin=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        h = {"Host": host or f"127.0.0.1:{self.port}"}
        if anahtar:
            h["X-Asistan-Anahtar"] = anahtar
        if origin:
            h["Origin"] = origin
        veri = None
        if govde is not None:
            veri = json.dumps(govde).encode()
            h["Content-Type"] = "application/json"
        c.request(yontem, yol, body=veri, headers=h)
        r = c.getresponse()
        ham = r.read()
        try:
            return r.status, json.loads(ham), r
        except ValueError:
            return r.status, ham, r

    # --- güvenlik ---
    def test_anahtarsiz_reddedilir(self):
        self.assertEqual(self.istek("/api/durum", anahtar=None)[0], 401)
        self.assertEqual(self.istek("/api/durum", anahtar="yanlis")[0], 401)

    def test_merhaba_anahtarsiz(self):
        k, v, _ = self.istek("/api/merhaba", anahtar=None)
        self.assertEqual(k, 200)
        self.assertIn("surum", v)

    def test_dns_rebinding_host_reddedilir(self):
        self.assertEqual(self.istek("/api/durum", host="kotu.ornek.com")[0], 403)

    def test_cors_yalniz_izinli_koken(self):
        _, _, r = self.istek("/api/durum", origin="tauri://localhost")
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "tauri://localhost")
        _, _, r = self.istek("/api/durum", origin="https://kotu.ornek.com")
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_bilinmeyen_gorev(self):
        self.assertEqual(self.istek("/api/gorev/rm-rf", "POST", govde={})[0], 404)

    # --- işlev ---
    def test_durum(self):
        k, v, _ = self.istek("/api/durum")
        self.assertEqual(k, 200)
        self.assertTrue(v["moduller"]["evrak"]["katalog"])
        self.assertTrue(v["moduller"]["avukatasistan"]["var"])

    def test_evrak_ara_turkce_duyarsiz(self):
        for q in ("bilirkisi", "BİLİRKİŞİ", "çağlar rapor", "caglar -ara"):
            k, v, _ = self.istek("/api/evrak/ara?q=" + __import__("urllib.parse").parse.quote(q))
            self.assertEqual(k, 200, q)
            self.assertEqual([r["skey"] for r in v["sonuclar"]], ["s1"], q)
        k, v, _ = self.istek("/api/evrak/ara?q=")
        self.assertEqual(len(v["sonuclar"]), 2)

    def test_evrak_dosya_yalniz_katalogdaki(self):
        k, v, r = self.istek("/api/evrak/dosya?skey=s1")
        self.assertEqual(k, 200)
        self.assertTrue(v.startswith(b"%PDF"))
        self.assertEqual(self.istek("/api/evrak/dosya?skey=s2")[0], 404)  # indirilmemiş
        self.assertEqual(self.istek("/api/evrak/dosya?skey=../../etc/passwd")[0], 404)

    def test_ajanda_birlesik_ve_tekil(self):
        k, v, _ = self.istek("/api/ajanda?gun=30")
        self.assertEqual(k, 200)
        turler = [o["tur"] for o in v["olaylar"]]
        self.assertEqual(turler.count("durusma"), 1, v["olaylar"])
        self.assertEqual(turler.count("sure"), 1, v["olaylar"])

    def test_gorev_calistir_ve_gunluk(self):
        sunucu.GOREV_DURUM["deneme"] = sunucu.Gorev("deneme", {"ad": "deneme", "cwd": KOK,
                                                               "cmd": [sys.executable, "-c", "print('merhaba')"]})
        try:
            k, v, _ = self.istek("/api/gorev/deneme", "POST", govde={})
            self.assertEqual(k, 200)
            for _ in range(50):
                if not sunucu.GOREV_DURUM["deneme"].calisiyor() and sunucu.GOREV_DURUM["deneme"].kod is not None:
                    break
                time.sleep(0.1)
            g = [g for g in self.istek("/api/gorevler")[1]["gorevler"] if g["kimlik"] == "deneme"][0]
            self.assertEqual(g["kod"], 0)
            self.assertIn("merhaba", g["gunluk"])
        finally:
            del sunucu.GOREV_DURUM["deneme"]

    def test_android_tarayicili_gorevler_kullanilamaz(self):
        eski = sunucu.ANDROID
        sunucu.ANDROID = True
        try:
            k, v, _ = self.istek("/api/gorev/uets-senkron", "POST", govde={})
            self.assertEqual(k, 400)
            self.assertIn("masaüstü", v["hata"])
            g = {g["kimlik"]: g for g in self.istek("/api/gorevler")[1]["gorevler"]}
            self.assertTrue(g["evrak-islemlerim"]["kullanilamaz"])
            self.assertTrue(g["evrak-katalog"]["kullanilamaz"])          # masaüstü penceresi
            self.assertFalse(g["uets-cevrimdisi"]["kullanilamaz"])       # tarayıcısız görev çalışır
        finally:
            sunucu.ANDROID = eski

    def test_gorev_listesi_izinli_komutlar(self):
        for g in sunucu.GOREVLER.values():
            betik = next(c for c in g["cmd"] if str(c).endswith(".py"))
            self.assertTrue((Path(g["cwd"]) / betik).is_file(), g["cmd"])

    def test_a4_birlestir(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow yok")
        img = Path(GECICI) / "tarama.png"
        Image.new("RGB", (1200, 800), "white").save(img)
        k, v, _ = self.istek("/api/a4", "POST", govde={"dosyalar": [str(img)], "cikti": str(Path(GECICI) / "cikti.pdf")})
        self.assertEqual(k, 200, v)
        self.assertTrue(Path(v["cikti"]).read_bytes().startswith(b"%PDF"))


class PaketTest(unittest.TestCase):
    """Gömülü (PyInstaller) paket yardımcıları: modül eşitleme ve --calistir."""

    def test_moduller_eslenir_ve_kullanici_verisi_korunur(self):
        kaynak = Path(tempfile.mkdtemp()) / "moduller"
        (kaynak / "m").mkdir(parents=True)
        (kaynak / "m" / "kod.py").write_text("SURUM = 1\n")
        (kaynak / "m" / "ayar.json").write_text('{"varsayilan": true}')
        hedef = Path(tempfile.mkdtemp()) / "moduller"
        sunucu.moduller_hazirla(kaynak, hedef)
        self.assertEqual((hedef / "m" / "kod.py").read_text(), "SURUM = 1\n")
        # kullanıcı ayarı değiştirir, veri üretir
        (hedef / "m" / "ayar.json").write_text('{"kullanici": true}')
        (hedef / "m" / "veri.db").write_bytes(b"sqlite")
        # yeni sürüm: kod güncellenir, ayar ve veri korunur
        (kaynak / "m" / "kod.py").write_text("SURUM = 2  # yeni\n")
        sunucu.moduller_hazirla(kaynak, hedef)
        self.assertIn("SURUM = 2", (hedef / "m" / "kod.py").read_text())
        self.assertEqual((hedef / "m" / "ayar.json").read_text(), '{"kullanici": true}')
        self.assertEqual((hedef / "m" / "veri.db").read_bytes(), b"sqlite")

    def test_calistir_betigi_ana_modul_olarak_calistirir(self):
        d = Path(tempfile.mkdtemp())
        (d / "yardimci.py").write_text("DEGER = 42\n")
        (d / "ana.py").write_text("import sys, yardimci\nprint('SONUC', yardimci.DEGER, sys.argv[1:], __name__)\n")
        import subprocess
        r = subprocess.run([sys.executable, str(KOK / "sunucu.py"), "--calistir", "ana.py", "--bayrak"],
                           cwd=d, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("SONUC 42 ['--bayrak'] __main__", r.stdout)

    def test_gorev_ortami_gomulu_java_ve_jarlar(self):
        jh = Path(tempfile.mkdtemp()); (jh / "bin").mkdir()
        jars = Path(tempfile.mkdtemp()); (jars / "editor_lib.jar").write_bytes(b"PK")
        eski = dict(os.environ)
        try:
            os.environ.update(CANASISTAN_JAVA_HOME=str(jh), CANASISTAN_UYAP_JARS=str(jars))
            os.environ.pop("UYAP_JARS", None)
            env = sunucu.gorev_ortami()
            self.assertEqual(env["JAVA_HOME"], str(jh))
            self.assertTrue(env["PATH"].startswith(str(jh / "bin")))
            self.assertEqual(env["UYAP_JARS"], str(jars))
            self.assertEqual(env["CANASISTAN_GORUNMEZ"], "1")  # tarayıcı asla ön planda değil
        finally:
            os.environ.clear(); os.environ.update(eski)

    def test_gorev_ortami_gomulu_tarayici(self):
        d = Path(tempfile.mkdtemp())
        chrome, surucu = d / "chrome-headless-shell", d / "chromedriver"
        chrome.write_bytes(b"x"); surucu.write_bytes(b"x")
        eski = dict(os.environ)
        try:
            for k in ("UYAP_CHROME_BIN", "UETS_CHROME_BIN", "UETS_CHROMEDRIVER", "SE_CHROMEDRIVER"):
                os.environ.pop(k, None)
            os.environ.update(CANASISTAN_CHROME=str(chrome), CANASISTAN_CHROMEDRIVER=str(surucu))
            env = sunucu.gorev_ortami()
            self.assertEqual(env["UYAP_CHROME_BIN"], str(chrome))
            self.assertEqual(env["UETS_CHROME_BIN"], str(chrome))
            self.assertEqual(env["UETS_CHROMEDRIVER"], str(surucu))
        finally:
            os.environ.clear(); os.environ.update(eski)


if __name__ == "__main__":
    unittest.main()
