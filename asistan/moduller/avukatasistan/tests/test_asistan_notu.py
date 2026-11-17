# -*- coding: utf-8 -*-
"""🧭 Asistan notu: var olan içerik korunur, yalnız işaretli bölüm eklenir/güncellenir, silinince geri gelmez,
eksikler ve yardımcı bilgiler doğru çıkar. Gerçek hesaplara istek gitmez."""
import os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AVUKAT_ENV_TASIMA"] = "0"
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")
os.environ["TICKTICK_TOKEN"] = "test"

import asistan_notu as an  # noqa: E402
import kimlik  # noqa: E402

TZ = timezone(timedelta(hours=3))
SIMDI = datetime(2026, 11, 10, 12, 0, tzinfo=TZ)

TEB = {"id": "t1", "projectId": "p1", "parentId": "kart", "status": 0, "tags": ["uets", "erolatmaca"],
       "title": "📨 TEBLİGAT - Oltu 3. Asliye Hukuk Mahkemesi - 2026/24 Esas (Son Gün: 30.11.2026)",
       "dueDate": "2026-11-30T17:00:00+0300",
       "content": kimlik.satir("TEBLİGAT", mahkeme="Oltu 3. Asliye Hukuk Mahkemesi", esas="2026/24", barkod="5003283066058")
       + "\n\n🔗 **Notion Dosyası:** https://app.notion.com/p/x\n\n📑 **EKLİ EVRAKLAR \\(EYP Paketi\\):**\n"
       "- 📄 `(2)BilirkisiRaporu.pdf`\n\n### YAPILACAK İŞLEM & CEVAP NOTU:\nMüvekkil ile görüşüldü, itiraz yazılacak.\n"}
DUR1 = {"id": "d1", "projectId": "p1", "parentId": None, "status": 0, "tags": ["duruşma"],
        "title": "⚖️ DURUŞMA - Ankara 46. Asliye Hukuk Mahkemesi - 2025/149 Esas", "dueDate": "2026-11-19T12:15:00+0300",
        "content": kimlik.satir("DURUŞMA", mahkeme="Ankara 46. Asliye Hukuk Mahkemesi", esas="2025/149", durusma="19/11/2026 12:15")
        + "\n\n### DURUŞMA TUTANAĞI:\n\n### DURUŞMA BEYANI:\n\n### ÖNCEKİ TENSİP/DURUŞMA TUTANAĞI:\n"}
DUR2 = {"id": "d2", "projectId": "p2", "parentId": "k2", "status": 0, "tags": ["duruşma", "naturel"],
        "title": "⚖️ DURUŞMA - Ankara 42. Asliye Hukuk Mahkemesi - 2026/368 Esas", "dueDate": "2026-11-19T13:00:00+0300",
        "content": kimlik.satir("DURUŞMA", mahkeme="Ankara 42. Asliye Hukuk Mahkemesi", esas="2026/368", durusma="19/11/2026 13:00")
        + "\n🔗 **Notion Dosyası:** x"}
KART = {"id": "kart", "projectId": "p1", "status": 0, "tags": ["erolatmaca"], "childIds": ["t1"],
        "title": "Oltu 3. Asliye Hukuk Mahkemesi - 2026/24 Esas", "content": "🔗 **Notion Dosyası:** x\n\nKullanıcının kart notu"}


def baglam(gorevler, defter=None):
    return {"gorevler": gorevler, "simdi": SIMDI, "ek_var": lambda t, b: True,
            "defter": (lambda e, m: (defter or {}).get(e)), "kapali_mi": lambda d: (d or "").startswith("Kapal"),
            "defter_dolu": True, "notion_var": lambda e, m: True}


class AsistanNotuTest(unittest.TestCase):
    def test_tebligat_ipucu_ve_icerik_korunur(self):
        g = [TEB, KART, DUR1, DUR2]
        sat = an.not_satirlari(TEB, baglam(g, {"2026/24": {"durum": "Açık", "ham_durum": "Açık", "taraflar": [
            {"rol": "Davalı", "ad": "ATMACA MADENCİLİK", "muvekkil_mi": True}]}}))
        metin = "\n".join(sat["bilgi"])
        self.assertIn("HMK m.281", metin)                       # bilirkişi raporu ipucu
        self.assertIn("Son gün: 30.11.2026 Pzt 17:00", metin)
        self.assertEqual(sat["eksik"], [])
        yeni = an.blok_yerlestir(TEB["content"], an.blok_metni(sat))
        self.assertTrue(yeni.startswith(TEB["content"].rstrip("\n")))   # var olan içerik AYNEN başta
        self.assertIn("Müvekkil ile görüşüldü, itiraz yazılacak.", yeni)

    def test_ikinci_calismada_yalniz_bolum_degisir_ve_ayni_ise_degismez(self):
        sat = an.not_satirlari(TEB, baglam([TEB, KART]))
        bir = an.blok_yerlestir(TEB["content"], an.blok_metni(sat))
        t2 = dict(TEB, content=bir + "\nKullanıcı sonradan bunu ekledi.\n")
        sat2 = an.not_satirlari(t2, baglam([t2, KART]))
        iki = an.blok_yerlestir(t2["content"], an.blok_metni(sat2))
        self.assertEqual(iki, t2["content"])                     # değişiklik yoksa aynen kalır (yazılmaz)
        self.assertEqual(iki.count(an.BAS), 1)                   # bölüm çoğalmaz
        self.assertIn("Kullanıcı sonradan bunu ekledi.", iki)

    def test_durusma_cakisma_ve_eksikler(self):
        sat = an.not_satirlari(DUR1, baglam([DUR1, DUR2]))
        e = "\n".join(sat["eksik"])
        self.assertIn("Çakışma: 13:00 Ankara 42. Asliye Hukuk Mahkemesi 2026/368", e)
        self.assertIn("Dava kartına bağlı değil", e)
        self.assertIn("Müvekkil etiketi yok", e)
        self.assertIn("Notion dosya bağlantısı yok", e)
        self.assertIn("tutanağı henüz eklenmemiş", "\n".join(sat["bilgi"]))

    def test_dava_karti_ozeti_ve_kapali_uyarisi(self):
        sat = an.not_satirlari(KART, baglam([TEB, KART], {"2026/24": {"durum": "Kapalı", "ham_durum": "Kapalı (Karar)", "taraflar": []}}))
        b, e = "\n".join(sat["bilgi"]), "\n".join(sat["eksik"])
        self.assertIn("UYAP durumu: Kapalı (Karar)", b)
        self.assertIn("Açık tebligat: 1 · en yakın son gün 30.11.2026 Pzt", b)
        self.assertIn("UYAP'ta dosya kapalı", e)

    def test_silinen_not_geri_eklenmez_ve_yazma_yalniz_not_alanini_degistirir(self):
        import ticktick_sync as tts
        tmp = tempfile.TemporaryDirectory()
        eski = (an.DURUM, tts.tum_aktif_gorevler, tts.gorev_getir, tts.tt_post, an._baglam)
        an.DURUM = os.path.join(tmp.name, "durum.json")
        yazilan = []
        gorevler = [dict(TEB, reminders=["TRIGGER:-PT900M"], items=[{"title": "madde"}], startDate="2026-11-10T10:09:00+0300")]
        tts.tum_aktif_gorevler = lambda force=False: gorevler
        tts.gorev_getir = lambda pid, tid: next((g for g in gorevler if g["id"] == tid), None)
        tts.tt_post = lambda url, payload, **k: yazilan.append(payload) or {}
        an._baglam = lambda g: baglam(g)
        try:
            o = an.ticktick_notlari(uygula=True)
            self.assertEqual(o["yazilan"], 1)
            p = yazilan[0]
            for alan in ("title", "tags", "dueDate", "startDate", "reminders", "items"):
                self.assertEqual(p[alan], gorevler[0][alan])            # diğer alanlar AYNEN geri gönderildi
            self.assertTrue(p["content"].startswith(TEB["content"].rstrip("\n")))
            # kullanıcı bölümü sildi -> bir daha eklenmez
            gorevler[0] = dict(gorevler[0], content=TEB["content"])
            yazilan.clear()
            o2 = an.ticktick_notlari(uygula=True)
            self.assertEqual((o2["yazilan"], o2["kapatilmis"]), (0, 1))
            self.assertEqual(yazilan, [])
        finally:
            an.DURUM, tts.tum_aktif_gorevler, tts.gorev_getir, tts.tt_post, an._baglam = eski
            tmp.cleanup()

    def test_kullanici_okuma_sonrasi_degistirdiyse_yazilmaz(self):
        import ticktick_sync as tts
        eski = (tts.gorev_getir, tts.tt_post)
        tts.gorev_getir = lambda pid, tid: dict(TEB, content=TEB["content"] + "yeni not")
        tts.tt_post = lambda *a, **k: self.fail("yazılmamalıydı")
        try:
            self.assertFalse(an._guvenli_icerik_yaz(TEB, TEB["content"] + "x"))
        finally:
            tts.gorev_getir, tts.tt_post = eski

    def test_baska_mahkemenin_ayni_esasi_karistirilmaz(self):
        baska = dict(DUR2, id="x", title="⚖️ DURUŞMA - Bursa 1. İş Mahkemesi - 2026/24 Esas", dueDate="2026-11-20T10:00:00+0300",
                     content=kimlik.satir("DURUŞMA", mahkeme="Bursa 1. İş Mahkemesi", esas="2026/24"))
        sat = an.not_satirlari(KART, baglam([TEB, KART, baska]))
        self.assertNotIn("Sıradaki duruşma", "\n".join(sat["bilgi"]))

    def test_notion_notu(self):
        sayfa = {"id": "n1", "title": "Oltu 3. Asliye Hukuk Mahkemesi - 2026/24", "esas_no": "2026/24",
                 "court": "Oltu 3. Asliye Hukuk Mahkemesi", "durum": "Açık", "tur": "Asliye Hukuk Mahkemesi", "client_rel_count": 0}
        d = {"durum": "Açık", "ham_durum": "Açık", "muvekkil": "ATMACA MADENCİLİK", "taraflar": [{"rol": "Davalı", "ad": "ATMACA MADENCİLİK"}]}
        sat = an.notion_satirlari(sayfa, [TEB, KART], lambda e, m: d, lambda x: False, simdi=SIMDI)
        metin = an.notion_blok_metni(sat)
        self.assertTrue(metin.startswith(an.NOTION_BAS))
        self.assertIn("MÜVEKKİLLER alanı boş", metin)
        self.assertIn("ticktick.com/webapp/#p/p1/tasks/kart", metin)


if __name__ == "__main__":
    unittest.main()
