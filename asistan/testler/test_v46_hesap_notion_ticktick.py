#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v4.6.0 gerileme testleri.

* Dosya hesapları: uydurma (karma) rakamlar yerine UYAP yanıtlarından gerçek hesap; icra kapak hesabı, artan avans,
  harç kalemleri; hesabı çekilmemiş dosyada tutar YOK (None).
* Dosya detayı: taraflar satır satır, hesap ve dosya konusu birlikte.
* Dosya konusu: yapay zekâsız çıkarımsal özet 5-10 cümle, uydurma bilgi içermez.
* Notion eşitleme yardımcıları: taraf ayırma, dosya türü, esas biçimi.
* TickTick: kapalı (tamamlanan + yapılmayacak) kopya engeli, standart biçim/eksik denetimi, konu bloğu.
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
AVUKAT_DIR = ASISTAN_DIR / "moduller" / "avukatasistan"
for p in (ASISTAN_DIR, EVRAK_DIR, AVUKAT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ["AVUKAT_ENV_TASIMA"] = "0"
os.environ.setdefault("TICKTICK_TOKEN", "test")
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")

import dosya_ozet  # noqa: E402
import notion_uyap  # noqa: E402
import sunucu  # noqa: E402
import uyap_finans_safahat as fin  # noqa: E402


def katalog_olustur(yol: Path):
    c = sqlite3.connect(str(yol))
    c.executescript("""
    CREATE TABLE dosya(dkey TEXT PRIMARY KEY, birim TEXT, dosya_no TEXT, dosya_tur TEXT, durum TEXT, yargi TEXT,
      acilis TEXT, dosya_id TEXT, taraflar TEXT, taraf_ara TEXT, muvekkil TEXT, muvekkil_ara TEXT,
      evrak_sayisi INTEGER DEFAULT 0, taranma TEXT, oturum TEXT);
    CREATE TABLE evrak(id INTEGER PRIMARY KEY, skey TEXT UNIQUE, dkey TEXT, tur TEXT, aciklama TEXT, tarih TEXT,
      kategori TEXT, durum TEXT, uzanti TEXT, is_ek INTEGER DEFAULT 0, path TEXT, pdf_path TEXT);
    CREATE VIRTUAL TABLE evrak_fts USING fts5(metin);
    """)
    c.execute("INSERT INTO dosya VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("ankara 3 asliye hukuk|2025/10", "Ankara 3. Asliye Hukuk Mahkemesi", "2025/10", "Hukuk Dava Dosyası", "Açık",
               "Hukuk", "2025-02-03", "\"x1\"", "AHMET YILMAZ (Davacı) vekil: CAN KIZILYAR; ÖRNEK A.Ş. (Davalı)", "",
               "AHMET YILMAZ (Davacı)", "", 3, "", ""))
    c.execute("INSERT INTO dosya VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("ankara 5 icra dairesi|2024/99", "Ankara 5. İcra Dairesi", "2024/99", "İcra Dosyası", "Açık",
               "İcra", "2024-05-01", "\"x2\"", "AHMET YILMAZ (Alacaklı); MEHMET KAYA (Borçlu)", "",
               "AHMET YILMAZ (Alacaklı)", "", 0, "", ""))
    c.execute("INSERT INTO evrak(id, skey, dkey, tur, aciklama, tarih) VALUES(1,'a','ankara 3 asliye hukuk|2025/10','Dava Dilekçesi','','2025-02-03')")
    c.execute("INSERT INTO evrak(id, skey, dkey, tur, aciklama, tarih) VALUES(2,'b','ankara 3 asliye hukuk|2025/10','Tensip Zaptı','','2025-02-10')")
    c.execute("INSERT INTO evrak(id, skey, dkey, tur, aciklama, tarih) VALUES(3,'c','ankara 3 asliye hukuk|2025/10','Bilirkişi Raporu','','2025-09-01')")
    c.execute("INSERT INTO evrak_fts(rowid, metin) VALUES(1, ?)",
              ("ANKARA NÖBETÇİ ASLİYE HUKUK MAHKEMESİNE\nDAVACI: AHMET YILMAZ\nKONU: Kira alacağının tahsili ile tahliye talebimizden ibarettir.\n\nAÇIKLAMALAR: ...",))
    c.commit()
    c.close()


class FinansCozumleme(unittest.TestCase):
    def test_kapak_hesabi_ascii_ve_turkce(self):
        k = fin.kapak_hesabi_coz([
            {"degerAlan": 1000, "textAlan": "Takipte Kesinlesen Miktar"},
            {"degerAlan": 50.5, "textAlan": "Toplam Faiz Miktari"},
            {"degerAlan": "1.250,00", "textAlan": "Vekalet Ücreti"},
            {"degerAlan": 30, "textAlan": "Masraf Miktari"},
            {"degerAlan": 200, "textAlan": "Yatan Para"},
            {"textAlan": "Basvurma Harci"},
        ])
        self.assertEqual(k["takip_kesinlesen_miktar"], 1000)
        self.assertEqual(k["vekalet_ucreti"], 1250.0)
        self.assertEqual(k["toplam_alacak"], 2330.5)
        self.assertEqual(k["bakiye_borc"], 2130.5)

    def test_artan_avans_ve_harc_kalemleri(self):
        r = fin.tahsilat_reddiyat_coz({"toplamTahsilat": 1500, "toplamreddiyat": 600, "toplamKalan": 472.4,
                                       "harcList": [{"harcMasrafAdi": "Başvurma Harcı", "miktar": "427,60"}]})
        self.assertEqual(r["kalan_bakiye"], 472.4)
        self.assertEqual(r["harc_kalemleri"], [{"ad": "Başvurma Harcı", "tutar": 427.6}])

    def test_icra_mi(self):
        self.assertTrue(fin.icra_mi("Ankara 5. İcra Dairesi", ""))
        self.assertFalse(fin.icra_mi("Ankara 2. İcra Hukuk Mahkemesi", "Hukuk Dava Dosyası"))


class HesapVeDetay(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "uyap_katalog.db"
        katalog_olustur(self.db)
        fin.init_finans_tables(str(self.db))
        self._eski = sunucu.katalog_yolu
        sunucu.katalog_yolu = lambda: self.db

    def tearDown(self):
        sunucu.katalog_yolu = self._eski
        self.tmp.cleanup()

    def test_cekilmemis_hesapta_uydurma_rakam_yok(self):
        v = sunucu.dosya_hesaplari()
        self.assertTrue(v["hazir"])
        for h in v["hesaplar"]:
            self.assertFalse(h["cekildi"])
            self.assertIsNone(h.get("toplam_borc"))
        icra = [h for h in v["hesaplar"] if h["is_icra"]]
        self.assertEqual(len(icra), 1, "icra dosyası Dosya Hesapları'nda görünmeli")

    def test_cekilmis_hesap_gercek_degerler(self):
        c = sqlite3.connect(str(self.db))
        c.execute("""INSERT INTO dosya_finans(dkey, toplam_tahsilat, toplam_reddiyat, toplam_harc, kalan_bakiye, son_guncelleme,
                     is_icra, harc_kalemleri_json) VALUES('ankara 3 asliye hukuk|2025/10', 1500, 600, 427.6, 472.4, '2026-11-20 10:00:00', 0,
                     '[{"ad": "Başvurma Harcı", "tutar": 427.6}]')""")
        c.execute("""INSERT INTO icra_hesap(dkey, takip_kesinlesen_miktar, toplam_faiz, vekalet_ucreti, masraf_miktari, tahsil_harci,
                     toplam_alacak, yatan_para, bakiye_borc, kesinlesme_durumu, borclular_json, son_guncelleme)
                     VALUES('ankara 5 icra dairesi|2024/99', 1000, 100, 200, 50, 0, 1350, 300, 1050, 'Kesinleşti',
                     '[{"ad_soyad": "MEHMET KAYA"}]', '2026-11-20 10:00:00')""")
        c.commit()
        c.close()
        v = sunucu.dosya_hesaplari()
        hs = {h["dkey"]: h for h in v["hesaplar"]}
        dava = hs["ankara 3 asliye hukuk|2025/10"]
        self.assertEqual(dava["artan_avans"], 472.4)
        self.assertEqual(dava["masraf_harc"], 427.6)
        icra = hs["ankara 5 icra dairesi|2024/99"]
        self.assertEqual(icra["toplam_borc"], 1350)
        self.assertEqual(icra["kalan_borc"], 1050)
        self.assertEqual(icra["borclular"], ["MEHMET KAYA"])
        self.assertEqual(v["istatistik"]["toplam_avans"], 472.4)
        d = sunucu.dosya_detay("ankara 3 asliye hukuk|2025/10")
        self.assertEqual(d["hesap"]["artan_avans"], 472.4)
        self.assertEqual([t["ad"] for t in d["taraf_listesi"]], ["AHMET YILMAZ", "ÖRNEK A.Ş."])
        self.assertTrue(d["taraf_listesi"][0]["muvekkil"])
        self.assertIn("Kira alacağının tahsili", d["konu"]["metin"])


class OzetVeNotion(unittest.TestCase):
    def test_cikarimsal_ozet_5_10_cumle(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "k.db"
            katalog_olustur(p)
            c = sqlite3.connect(str(p))
            o = dosya_ozet.ozetle(c, "ankara 3 asliye hukuk|2025/10", {})
            c.close()
        self.assertEqual(o["kaynak"], "otomatik (evraklardan)")
        cumle = [x for x in o["metin"].split(". ") if x.strip()]
        self.assertTrue(5 <= len(cumle) <= 10, o["metin"])
        self.assertIn("AHMET YILMAZ", o["metin"])
        self.assertIn("bilirkişi raporu", o["metin"])

    def test_taraf_ayir(self):
        biz, karsi = notion_uyap.taraf_ayir("AHMET YILMAZ (Davacı) vekil: X; ÖRNEK A.Ş. (Davalı); K.H. (Katılan)",
                                            "AHMET YILMAZ (Davacı)")
        self.assertEqual(biz, ["AHMET YILMAZ"])
        self.assertEqual(karsi, ["ÖRNEK A.Ş."])

    def test_tur_ve_esas(self):
        self.assertEqual(notion_uyap.map_dosya_turu("Ankara 32. Ağır Ceza Mahkemesi"), "Ağır Ceza Mahkemesi")
        self.assertEqual(notion_uyap.map_dosya_turu("Ankara 5. İcra Dairesi"), "İcra Takibi")
        self.assertEqual(notion_uyap.map_dosya_turu("Ankara 2. İcra Hukuk Mahkemesi"), "İcra Hukuk Mahkemesi")
        self.assertEqual(notion_uyap.esas_norm("2026/034 Esas"), "2026/34")


class TickTickDuzeni(unittest.TestCase):
    def test_eksik_tebligat_ve_isaret(self):
        import gorev_format as gf
        import kimlik
        t = {"title": "📨 TEBLİGAT - X - 2026/1 Esas", "dueDate": "2026-12-01T17:00:00+0300",
             "content": kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="123") + "\n\n- **Merci:** X\n- **Geliş:** 1\n"}
        e = gf.eksikler(t, ek_var=False)
        self.assertIn("üstyazı ve ekler", e)
        self.assertIn("tebliğ tarihi", e)
        c, tags, degisti = gf.eksik_isaretle(t["content"], ["uets"], e)
        self.assertTrue(degisti)
        self.assertIn("eksik", tags)
        self.assertTrue(c.splitlines()[1].startswith(gf.EKSIK_ONEK))
        c2, tags2, _ = gf.eksik_isaretle(c, tags, [])
        self.assertNotIn(gf.EKSIK_ONEK, c2)
        self.assertNotIn("eksik", tags2)

    def test_konu_blogu_kullanici_notunu_korur(self):
        import gorev_format as gf
        c = gf.dosya_karti_icerigi("Ankara 32. Ağır Ceza Mahkemesi", "2026/34") + "\nKullanıcı notu: tanık listesi"
        c1 = gf.konu_blogu(c, "Birinci konu.")
        c2 = gf.konu_blogu(c1, "İkinci konu.")
        self.assertEqual(gf.konu_oku(c2), "İkinci konu.")
        self.assertIn("Kullanıcı notu: tanık listesi", c2)
        self.assertEqual(c2.count(gf.KONU_BAS), 1)

    def test_kapali_kopya_acilmaz(self):
        import kimlik
        import ticktick_sync as ts
        kapali = {"id": "k1", "status": -1, "content": kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="555")}
        eski = ts.get_completed_tasks_live
        ts.get_completed_tasks_live = lambda force_refresh=False: [kapali]
        try:
            r = ts.tt_post("https://ornek.invalid/open/v1/task",
                           {"title": "📨 TEBLİGAT", "projectId": "p", "content": kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="555")})
            self.assertEqual(r["id"], "k1")
            self.assertIsNone(ts.kapali_kopya_bul({"content": kimlik.satir("TEBLİGAT", barkod="556")}))
            d = ts.kapali_kopya_bul({"content": kimlik.satir("DOSYA", mahkeme="X", esas="2026/1")})
            self.assertIsNone(d)
        finally:
            ts.get_completed_tasks_live = eski


if __name__ == "__main__":
    unittest.main()


class PaketliMasaustu(unittest.TestCase):
    """v4.6.1: Fedora/RPM gibi salt-okunur kurulumda görevlerin çökmemesi."""

    def test_moduller_salt_okunur_paket_klasorune_yazmaz(self):
        for ad in ("uyap_watcher.py", "drive_aktarici.py"):
            kaynak = (EVRAK_DIR / ad).read_text(encoding="utf-8")
            self.assertNotIn('getattr(sys, "_MEIPASS"', kaynak, ad)

    def test_calistir_dash_c(self):
        with tempfile.TemporaryDirectory() as t:
            hedef = Path(t) / "ok.txt"
            eski_argv, eski_yol = list(sys.argv), list(sys.path)
            try:
                sunucu.calistir(["-c", f"open({str(hedef)!r}, 'w').write('1')"])
            finally:
                sys.argv, sys.path[:] = eski_argv, eski_yol
            self.assertTrue(hedef.is_file())

    def test_eslenen_kopya_yazilabilir(self):
        with tempfile.TemporaryDirectory() as t:
            kaynak, hedef = Path(t) / "paket", Path(t) / "kopya"
            (kaynak / "evrak" / "loglar").mkdir(parents=True)
            f = kaynak / "evrak" / "loglar" / "watcher.log"
            f.write_text("x")
            f.chmod(0o444)
            sunucu.moduller_hazirla(kaynak, hedef)
            self.assertTrue(os.access(hedef / "evrak" / "loglar" / "watcher.log", os.W_OK))
            (kaynak / "evrak" / "yeni.py").write_text("y")
            sunucu.moduller_hazirla(kaynak, hedef)   # ikinci eşitleme (sürüm yükseltme) de çökmemeli
            self.assertTrue((hedef / "evrak" / "yeni.py").is_file())


class V47Testleri(unittest.TestCase):
    """v4.7.0: icra kesinleşme/takipsizlik analizi, hızlı birleşik evrak arama, dosya bulma, Gmail kodu okuyucu."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "uyap_katalog.db"
        katalog_olustur(self.db)
        fin.init_finans_tables(str(self.db))
        c = sqlite3.connect(str(self.db))
        c.executescript("""CREATE TABLE IF NOT EXISTS tebligat(id INTEGER PRIMARY KEY, barkod_delil TEXT UNIQUE, dkey TEXT, birim TEXT,
            dosya_no TEXT, muvekkil TEXT, muhatap TEXT, tebligat_turu TEXT, gonderim_tarihi TEXT, teblig_tarihi TEXT, sonuc TEXT,
            yasal_sure_notu TEXT, evrak_id TEXT, evrak_adi TEXT, eklenme TEXT);""")
        c.execute("INSERT INTO evrak(id, skey, dkey, tur, aciklama, tarih) VALUES(10,'oe','ankara 5 icra dairesi|2024/99','Ödeme Emri','Örnek 7','2024-05-02')")
        c.execute("INSERT INTO tebligat(barkod_delil, dkey, birim, dosya_no, muhatap, tebligat_turu, evrak_adi, teblig_tarihi, sonuc) VALUES "
                  "('RR1','ankara 5 icra dairesi|2024/99','Ankara 5. İcra Dairesi','2024/99','MEHMET KAYA','Ödeme Emri','Ödeme emri','2024-05-10','Bizzat')")
        c.commit()
        c.close()
        self._eski = sunucu.katalog_yolu
        sunucu.katalog_yolu = lambda: self.db

    def tearDown(self):
        sunucu.katalog_yolu = self._eski
        self.tmp.cleanup()

    def test_kesinlestirilebilir_ve_takipsizlik(self):
        import datetime as dt
        import icra_analiz
        c = sqlite3.connect(str(self.db))
        a = icra_analiz.analiz(c, "ankara 5 icra dairesi|2024/99", bugun=dt.date(2025, 6, 1))
        c.close()
        self.assertEqual(a["kesinlesme"]["durum"], "kesinlestirilebilir")
        self.assertIn("MEHMET KAYA", a["kesinlesme"]["aciklama"])
        self.assertIn("17.05.2024", a["kesinlesme"]["aciklama"])   # 10.05 + 7 gün
        self.assertEqual(a["takipsizlik"]["seviye"], "kirmizi")   # son işlem 2024-05: 1 yılı aştı

    def test_itiraz_kesinlestirmeyi_engeller(self):
        import datetime as dt
        import icra_analiz
        c = sqlite3.connect(str(self.db))
        c.execute("INSERT INTO evrak(id, skey, dkey, tur, aciklama, tarih) VALUES(11,'it','ankara 5 icra dairesi|2024/99','Borçlu İtiraz Dilekçesi','','2024-05-14')")
        a = icra_analiz.analiz(c, "ankara 5 icra dairesi|2024/99", bugun=dt.date(2024, 6, 1))
        c.close()
        self.assertEqual(a["kesinlesme"]["durum"], "itiraz")

    def test_birlesik_arama_ve_dosya_bul(self):
        v = sunucu.evrak_ara("yilmaz", drive_dahil=False)
        self.assertTrue(v["hazir"])
        self.assertGreaterEqual(len(v["sonuclar"]), 3)          # taraf adıyla dosyanın tüm evrakı bulunur
        self.assertIn("drive", v["sonuclar"][0])
        v2 = sunucu.evrak_ara("bilirkisi", drive_dahil=False)
        self.assertEqual([r["tur"] for r in v2["sonuclar"]], ["Bilirkişi Raporu"])
        self.assertEqual(sunucu.dosya_bul("Ankara 3. Asliye Hukuk Mahkemesi", "2025/10 Esas")["dkey"], "ankara 3 asliye hukuk|2025/10")
        d = sunucu.dosya_detay("ankara 5 icra dairesi|2024/99")
        self.assertEqual(d["icra"]["kesinlesme"]["durum"], "kesinlestirilebilir")

    def test_icra_ozet_listesi(self):
        r = sunucu.icra_analizi()
        self.assertEqual(r["ozet"]["toplam"], 1)
        self.assertEqual(r["ozet"]["kesinlestirilebilir"], 1)


class GmailKodu(unittest.TestCase):
    def test_html_govdeden_kod(self):
        import gmail_otp
        self.assertEqual(gmail_otp.kod_bul("<p>Sayın CAN,</p><b>482913</b> kodunu kullanınız"), "482913")
        self.assertEqual(gmail_otp._imap_klasor("UETS Giriş Kodu"), '"UETS Giri&AV8- Kodu"')


class AyarYedegi(unittest.TestCase):
    """v4.8.0: anahtarları bir kez gir — şifreli yedek, yanlış şifre reddi, yeni cihaza tek adımda geri yükleme."""

    def test_sifrele_coz_ve_yanlis_sifre(self):
        import ayar_yedek
        blob = ayar_yedek.sifrele({"env": {"NOTION_TOKEN": "ntn_x"}}, "gizli-123")
        self.assertNotIn(b"ntn_x", blob)
        self.assertEqual(ayar_yedek.coz(blob, "gizli-123")["env"]["NOTION_TOKEN"], "ntn_x")
        with self.assertRaises(ValueError):
            ayar_yedek.coz(blob, "yanlis-123")
        bozuk = blob.replace(b'"ct": "', b'"ct": "A')
        with self.assertRaises(ValueError):
            ayar_yedek.coz(bozuk, "gizli-123")

    def test_eski_cihazdan_yeni_cihaza(self):
        import ayar_yedek
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            eski, yeni = t / "eski", t / "yeni"
            (eski / "av").mkdir(parents=True)
            (eski / "av" / ".env").write_text("NOTION_TOKEN=ntn_a\nTICKTICK_TOKEN=tp_b\nAYAR_YEDEK_SIFRE=gizli-123\n")
            (eski / "ev").mkdir()
            (eski / "ev" / "watcher_config.json").write_text('{"google_drive_webhook": "https://script.google.com/x/exec"}')
            (eski / "ev" / ".uyap_config.json").write_text('{"tc": "12345678901", "gsm": "5321234567"}')
            (eski / "ev" / "pin.txt").write_text("123456")
            veri = ayar_yedek.topla(eski / "av" / ".env", eski / "ev", eski / "ev" / ".uyap_config.json")
            self.assertNotIn("AYAR_YEDEK_SIFRE", veri["env"])
            self.assertNotIn("pin", veri)                       # PIN yalnız açıkça istenirse
            blob = ayar_yedek.sifrele(veri, "gizli-123")
            (yeni / "av").mkdir(parents=True)
            (yeni / "av" / ".env").write_text("OZET_MODEL=x\n")
            s = ayar_yedek.uygula(ayar_yedek.coz(blob, "gizli-123"), yeni / "av" / ".env", yeni / "ev", yeni / "ev" / ".uyap_config.json")
            self.assertEqual(s["anahtar"], 2)
            env = ayar_yedek._env_oku(yeni / "av" / ".env")
            self.assertEqual(env["TICKTICK_TOKEN"], "tp_b")
            self.assertEqual(env["OZET_MODEL"], "x")               # var olan ayar korunur
            self.assertIn("script.google.com", (yeni / "ev" / "watcher_config.json").read_text())
            self.assertIn("5321234567", (yeni / "ev" / ".uyap_config.json").read_text())
