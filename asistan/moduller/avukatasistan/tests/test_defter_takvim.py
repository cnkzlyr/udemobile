# -*- coding: utf-8 -*-
"""Dosya defteri, UYAP listesi değişiklikleri, çıkar çatışması, kart kapatma koruması ve AJANDA takvim eşitlemesi.
Gerçek hesaplara istek gitmez (sahte TickTick sunucusu, geçici SQLite)."""
import os, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["AVUKAT_ENV_TASIMA"] = "0"
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")       # testte internet beklenmez
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")            # gerçek veri/ klasörüne günlük yazılmaz
os.environ["TICKTICK_TOKEN"] = "test"

import defter  # noqa: E402
import kimlik  # noqa: E402
import test_kimlik_ve_izleyici as _tk  # noqa: E402
SahteTickTick = _tk.SahteTickTick


def dosya(birim, esas, durum, taraflar, tur="Hukuk Dava Dosyası"):
    return {"birim": birim, "dosya_no": esas, "tur": tur, "durum": durum, "raw_durum": durum, "acilis_iso": "2026-01-01",
            "taraflar": taraflar}


class DefterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["DEFTER_URL"] = "sqlite:///" + os.path.join(self.tmp.name, "d.db")
        defter.sifirla_baglanti()

    def tearDown(self):
        defter.sifirla_baglanti()
        os.environ.pop("DEFTER_URL", None)
        self.tmp.cleanup()

    def test_aktarim_degisiklik_ozeti_ve_tekrar_islenmeme(self):
        l1 = [dosya("Ankara 1. Asliye Hukuk Mahkemesi", "2026/1", "Açık", ["1. Davacı:AYŞE YILMAZ", "2. Davalı:BETA LTD"]),
              dosya("Ankara 2. İş Mahkemesi", "2025/9", "Açık", ["1. Davacı:CEM KAYA"])]
        r1 = defter.liste_aktar(l1, "l1.xlsx", "ozet1", muvekkil_adlari=["AYŞE YILMAZ", "CEM KAYA"])
        self.assertEqual(len(r1["yeni"]), 2)
        self.assertTrue(defter.liste_aktar(l1, "l1.xlsx", "ozet1")["atlandi"])           # aynı liste ikinci kez işlenmez
        l2 = [dosya("Ankara 1. Asliye Hukuk Mahkemesi", "2026/1", "Kapalı", ["1. Davacı:AYŞE YILMAZ", "2. Davalı:BETA LTD"]),
              dosya("Ankara 3. Asliye Ceza Mahkemesi", "2026/77", "Açık", ["1. Sanık:DENİZ AK"])]
        r2 = defter.liste_aktar(l2, "l2.xlsx", "ozet2")
        self.assertEqual(r2["yeni"], ["Ankara 3. Asliye Ceza Mahkemesi 2026/77"])
        self.assertEqual(r2["durum_degisen"], [("Ankara 1. Asliye Hukuk Mahkemesi 2026/1", "Açık", "Kapalı")])
        self.assertEqual(r2["listeden_cikan"], ["Ankara 2. İş Mahkemesi 2025/9"])
        d = defter.dosya_bul("2026/1", "Ankara 1. Asliye Hukuk")
        self.assertTrue(defter.kapali_mi(d["durum"]))
        self.assertIn("Durumu değişen", defter.ozet_metni(r2))

    def test_muvekkil_isareti_kisa_adda_icerme_yapmaz(self):
        l = [dosya("X Mahkemesi", "2026/5", "Açık", ["1. Davacı:MURAT GÜL", "2. Davalı:MURAT GÜLER"])]
        defter.liste_aktar(l, "a", "o", muvekkil_adlari=["MURAT GÜL"])
        roller = {t["ad"]: t["muvekkil_mi"] for t in defter.dosya_bul("2026/5")["taraflar"]}
        self.assertEqual(roller, {"MURAT GÜL": True, "MURAT GÜLER": False})

    def test_cikar_catismasi_karsi_karsiya_muvekkiller(self):
        l = [dosya("A Mahkemesi", "2026/1", "Açık", ["1. Davacı:EFE A.Ş.", "2. Davalı:KAYA LTD"]),
             dosya("B Mahkemesi", "2026/2", "Açık", ["1. Sanık:ALİ VELİ", "2. Sanık:CAN TAN"]),       # aynı tarafta: çatışma değil
             dosya("C Mahkemesi", "2026/3", "Açık", ["1. İtiraz Eden (Davacı):DORA SU", "2. Karşı Taraf (Davalı):EFE A.Ş."])]
        defter.liste_aktar(l, "a", "o", muvekkil_adlari=["EFE A.Ş.", "KAYA LTD", "ALİ VELİ", "CAN TAN", "DORA SU"])
        c = {x["dosya"] for x in defter.catismalar()}
        self.assertEqual(c, {"A Mahkemesi 2026/1", "C Mahkemesi 2026/3"})
        self.assertEqual(len(defter.ad_ara("EFE A.Ş.")), 2)
        self.assertTrue(defter.uyari_yeni_mi("k1", "m"))
        self.assertFalse(defter.uyari_yeni_mi("k1", "m"))                                      # aynı uyarı tekrar gitmez

    def test_baska_veritabanina_tasima(self):
        defter.liste_aktar([dosya("A", "2026/1", "Açık", ["1. Davacı:X Y"])], "a", "o")
        hedef = "sqlite:///" + os.path.join(self.tmp.name, "hedef.db")
        sayilar = defter.tasi(hedef)
        self.assertEqual((sayilar["dosyalar"], sayilar["taraflar"]), (1, 1))
        with self.assertRaises(RuntimeError):
            defter.tasi(hedef)                                                                 # dolu hedefe yazmaz


class NotionKorumaTest(unittest.TestCase):
    def test_notion_okunamazsa_ve_olagandisi_coksa_notiona_yazilmaz(self):
        import openpyxl, sync_uyap_excel as su
        tmp = tempfile.TemporaryDirectory()
        os.environ["DEFTER_URL"] = "sqlite:///" + os.path.join(tmp.name, "d.db"); defter.sifirla_baglanti()
        yol = os.path.join(tmp.name, "dosyalar.xlsx")
        wb = openpyxl.Workbook(); ws = wb.active
        ws.append([None, "Birim", "Dosya No", "Taraf", "Tür", "Durum", "Açılış Tarihi"])
        for i in range(30):
            ws.append([str(i + 1), f"Ankara {i}. Asliye Hukuk Mahkemesi", f"2026/{i}", "1. Davacı:X Y", "Hukuk", "Açık", "01.01.2026"])
        wb.save(yol)
        yazilan = []
        eski = (su.fetch_all_notion_clients, su.fetch_all_notion_pages, su.create_notion_case, su.update_notion_status, su._telegram)
        su.create_notion_case = lambda **k: yazilan.append(k) or {"url": "x"}
        su.update_notion_status = lambda *a: yazilan.append(a) or True
        su._telegram = lambda m: None
        su.fetch_all_notion_clients = lambda: {}
        import ticktick_sync as _tts
        import butunluk as _bt
        eski_tt = (_tts.get_completed_tasks_live, su.get_project_tasks_live, _bt.tam_denetim)
        _tts.get_completed_tasks_live = lambda *a, **k: []                          # TickTick boş (okuma başarılı)
        su.get_project_tasks_live = lambda *a, **k: []
        _bt.tam_denetim = lambda **k: {}
        try:
            su.fetch_all_notion_pages = lambda: []                                     # Notion okunamadı
            r = su.run_sync(yol, mod="guvenli")
            self.assertIn("okunamadı", r.get("notion_engeli", ""))
            su.fetch_all_notion_pages = lambda: [{"id": "p", "title": "Başka - 2020/1", "esas_no": "2020/1", "durum": "Açık", "url": ""}]
            r2 = su.run_sync(yol, mod="guvenli")                                      # 30/30 yeni: olağandışı
            self.assertIn("olağandışı", r2.get("notion_engeli", ""))
            self.assertEqual(yazilan, [])
        finally:
            (su.fetch_all_notion_clients, su.fetch_all_notion_pages, su.create_notion_case, su.update_notion_status, su._telegram) = eski
            (_tts.get_completed_tasks_live, su.get_project_tasks_live, _bt.tam_denetim) = eski_tt
            defter.sifirla_baglanti(); os.environ.pop("DEFTER_URL", None); tmp.cleanup()


ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:olay1@google.com
DTSTART:{t1}
SUMMARY:DURUŞMA - 2026/45 Seferihisar 1. Asliye Hukuk Mahkemesi
DESCRIPTION:Dava Türü:Vakıf\\n\\nİhbar Olunan:ÖRNEK VAKIF MÜDÜRLÜĞÜ[Vekil: AV TEST]\\nDavacı:KİŞİ BİR[Vekil:
  BAŞKA AVUKAT]\\n\\nDURUŞMA NOTUM:\\n
END:VEVENT
BEGIN:VEVENT
UID:olay2@google.com
DTSTART:{t1}
SUMMARY:Duruşma
LOCATION:Seferihisar 1. Asliye Hukuk Mahkemesi
DESCRIPTION:2026/45 Hukuk Dava Dosyası
END:VEVENT
BEGIN:VEVENT
UID:ucak@google.com
DTSTART:{t1}
SUMMARY:Flight to İstanbul (TK 1848)
END:VEVENT
END:VCALENDAR
"""


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class TakvimTest(_tk.TickTickAkisTest):
    for _ad in [a for a in dir(_tk.TickTickAkisTest) if a.startswith("test_")]:
        locals()[_ad] = None

    def setUp(self):
        super().setUp()
        self.tmp2 = tempfile.TemporaryDirectory()
        os.environ["DEFTER_URL"] = "sqlite:///" + os.path.join(self.tmp2.name, "d.db")
        defter.sifirla_baglanti()
        import notion_sync
        notion_sync.find_notion_case = lambda *a, **k: None
        self.bildirimler = []

    def tearDown(self):
        defter.sifirla_baglanti()
        os.environ.pop("DEFTER_URL", None)
        self.tmp2.cleanup()

    def _ics(self, dt, iptal=False):
        m = ICS.format(t1=utc(dt))
        return m.replace("UID:olay1@google.com", "UID:olay1@google.com\nSTATUS:CANCELLED") if iptal else m

    def test_ayristirma_tekillestirme_muvekkil(self):
        import takvim
        from config import TZ_TURKEY
        t = datetime.now(TZ_TURKEY).replace(microsecond=0, second=0) + timedelta(days=5)
        d = [x for x in (takvim.ayristir(o) for o in takvim.ics_olaylari(self._ics(t))) if x]
        self.assertEqual(len(d), 2)                              # uçuş elendi
        tek = takvim.tekillestir(d)
        self.assertEqual(len(tek), 1)                            # aynı esas + saat: tek duruşma
        self.assertEqual((tek[0]["esas"], tek[0]["mahkeme"]), ("2026/45", "Seferihisar 1. Asliye Hukuk Mahkemesi"))
        self.assertEqual(tek[0]["baslangic"].strftime("%H:%M"), t.strftime("%H:%M"))   # UTC -> TR saati
        os.environ["AVUKAT_ADI"] = "AV TEST"
        try:
            self.assertEqual(takvim.muvekkiller(tek[0], takvim.avukat_adi(tek)), [("İhbar Olunan", "ÖRNEK VAKIF MÜDÜRLÜĞÜ")])
        finally:
            os.environ.pop("AVUKAT_ADI")

    def test_esitleme_yeni_tekrar_erteleme_iptal(self):
        import takvim
        from config import TZ_TURKEY
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update({"Inbox": "inbox"})
        import config; config.PROJECT_IDS.clear(); config.PROJECT_IDS.update({"Inbox": "inbox"})
        os.environ["AVUKAT_ADI"] = "AV TEST"
        try:
            t = (datetime.now(TZ_TURKEY) + timedelta(days=5)).replace(hour=9, minute=30, second=0, microsecond=0)
            o1 = takvim.esitle(self._ics(t), bildir=self.bildirimler.append)
            self.assertEqual(o1["yeni"], 1)
            durusma = [g for g in SahteTickTick.gorevler.values() if kimlik.oku(g.get("content") or "").get("tur") == "DURUŞMA"]
            self.assertEqual(len(durusma), 1)
            gid = durusma[0]["id"]
            self.assertIn("+0300", durusma[0]["dueDate"])
            SahteTickTick.gorevler[gid]["title"] = "Duruşmaya bilirkişi itirazıyla gidilecek"   # kullanıcı değiştirdi
            self.ts._TUM_GOREVLER = None
            o2 = takvim.esitle(self._ics(t), bildir=self.bildirimler.append)
            self.assertEqual((o2["yeni"], o2["ayni"]), (0, 1))
            t2 = t + timedelta(days=30, hours=2)                                               # ertelendi
            self.ts._TUM_GOREVLER = None
            o3 = takvim.esitle(self._ics(t2), bildir=self.bildirimler.append)
            self.assertEqual((o3["yeni"], o3["ertelenen"]), (0, 1))
            g = SahteTickTick.gorevler[gid]
            self.assertTrue(g["dueDate"].startswith(t2.strftime("%Y-%m-%dT%H:%M")))
            self.assertEqual(g["title"], "Duruşmaya bilirkişi itirazıyla gidilecek")          # başlık korundu
            self.assertEqual(len([x for x in SahteTickTick.gorevler.values()
                                  if kimlik.oku(x.get("content") or "").get("tur") == "DURUŞMA"]), 1)
            self.ts._TUM_GOREVLER = None
            o4 = takvim.esitle(self._ics(t2, iptal=True), bildir=self.bildirimler.append)
            self.assertEqual(o4["iptal"], 1)
            self.assertIn(gid, SahteTickTick.gorevler)                                         # silinmedi
            self.assertTrue(any("İPTAL" in b for b in self.bildirimler))
        finally:
            os.environ.pop("AVUKAT_ADI", None)
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)

    def test_tarihi_yalniz_tarih_alaninda_olan_eski_gorev_taninir_kopya_birlesir(self):
        import takvim
        from config import TZ_TURKEY
        import config
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update({"Inbox": "inbox"}); config.PROJECT_IDS.update({"Inbox": "inbox"})
        try:
            t = (datetime.now(TZ_TURKEY) + timedelta(days=8)).replace(hour=11, minute=25, second=0, microsecond=0)
            iso = t.strftime("%Y-%m-%dT%H:%M:00+0300")
            # Bulut betiği / elle açılmış eski görev: notunda tarih YOK, yalnızca tarih alanında
            SahteTickTick.gorevler["eski"] = {"id": "eski", "projectId": "liste", "status": 0, "priority": 3,
                "title": "⚖️ DURUŞMA - Seferihisar 1. Asliye Hukuk Mahkemesi - 2026/45 Esas", "tags": ["duruşma", "benim"],
                "content": "### DURUŞMA BEYANI:\nkendi notum\n**Dosya No:** 2026/45", "dueDate": iso, "startDate": iso,
                "createdTime": "2026-09-25T15:49:18+0300", "childIds": ["hazirlik"]}
            SahteTickTick.gorevler["hazirlik"] = {"id": "hazirlik", "projectId": "liste", "status": 0, "parentId": "eski",
                                                 "title": "Bilirkişi raporunu oku", "content": ""}
            o = takvim.esitle(self._ics(t), bildir=self.bildirimler.append)
            self.assertEqual(o["yeni"], 0)                                   # eski görev tanındı
            g = SahteTickTick.gorevler["eski"]
            self.assertEqual(kimlik.oku(g["content"]).get("esas"), "2026/45")
            self.assertIn("kendi notum", g["content"])
            # Önceki sürümün açtığı kopyayı temizleme
            SahteTickTick.gorevler["kopya"] = {"id": "kopya", "projectId": "inbox", "status": 0, "tags": ["duruşma"],
                "title": "⚖️ DURUŞMA - Seferihisar 1. Asliye Hukuk Mahkemesi - 2026/45 Esas (Saat: 11:25)",
                "content": kimlik.satir("DURUŞMA", mahkeme="Seferihisar 1. Asliye Hukuk Mahkemesi", esas="2026/45",
                                        durusma=t.strftime("%d/%m/%Y %H:%M")) + "\n\n⚖️ **DURUŞMA BİLGİSİ**",
                "dueDate": iso, "createdTime": "2026-11-10T12:00:00+0300"}
            b, sil = self.ts.durusma_mukerrerlerini_birlestir()
            self.assertEqual((b, sil), (1, 1))
            self.assertNotIn("kopya", SahteTickTick.gorevler)
            self.assertEqual(SahteTickTick.gorevler["eski"]["title"], "⚖️ DURUŞMA - Seferihisar 1. Asliye Hukuk Mahkemesi - 2026/45 Esas")
            self.assertIn("hazirlik", SahteTickTick.gorevler)
            self.assertIn("benim", SahteTickTick.gorevler["eski"]["tags"])
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)

    def test_altinda_acik_is_olan_kart_kapatilmaz(self):
        import sync_uyap_excel
        SahteTickTick.gorevler["kart"] = {"id": "kart", "projectId": "p", "status": 0, "title": "X - 2026/1 Esas", "childIds": ["t1", "t2"], "content": ""}
        SahteTickTick.gorevler["t1"] = {"id": "t1", "projectId": "p", "status": 2, "title": "bitti", "content": ""}
        SahteTickTick.gorevler["t2"] = {"id": "t2", "projectId": "p", "status": 0, "title": "Cevap yazılacak", "content": "", "childIds": ["t3"]}
        SahteTickTick.gorevler["t3"] = {"id": "t3", "projectId": "p", "status": 0, "title": "Alt adım", "content": ""}
        self.assertEqual(sorted(sync_uyap_excel.acik_alt_isler("p", "kart")), ["Alt adım", "Cevap yazılacak"])
        SahteTickTick.gorevler["t2"]["status"] = 2
        SahteTickTick.gorevler["t3"]["status"] = 2
        self.assertEqual(sync_uyap_excel.acik_alt_isler("p", "kart"), [])


if __name__ == "__main__":
    unittest.main()
