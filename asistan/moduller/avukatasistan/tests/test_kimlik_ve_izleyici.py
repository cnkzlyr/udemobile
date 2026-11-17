# -*- coding: utf-8 -*-
"""Görev kimliği (🔖 KİMLİK), kullanıcı başlığının korunması, mükerrer birleştirme ve esas nosuz tebligat
için sahte TickTick sunucusuyla testler. Gerçek hesaba hiçbir istek gitmez."""
import json, os, re, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AVUKAT_ENV_TASIMA"] = "0"
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")       # testte internet beklenmez
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")            # gerçek veri/ klasörüne günlük yazılmaz
os.environ["TICKTICK_TOKEN"] = "test"

import kimlik  # noqa: E402


class SahteTickTick(BaseHTTPRequestHandler):
    gorevler = {}      # id -> görev
    istekler = []
    sayac = 0

    def log_message(self, *a):
        pass

    def _yaz(self, kod, veri):
        b = json.dumps(veri).encode()
        self.send_response(kod); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        p = self.path.split("/open/v1", 1)[-1]
        if p == "/project":
            pids = sorted({t["projectId"] for t in self.gorevler.values() if t["projectId"] != "inbox"})
            return self._yaz(200, [{"id": x, "name": x} for x in pids])
        m = re.match(r"/project/([^/]+)/data$", p)
        if m:
            return self._yaz(200, {"tasks": [t for t in self.gorevler.values() if t["projectId"] == m.group(1) and t.get("status", 0) == 0]})
        m = re.match(r"/project/([^/]+)/task/([^/]+)$", p)
        if m:
            t = self.gorevler.get(m.group(2))
            return self._yaz(200, t) if t else self._yaz(404, {})
        self._yaz(404, {})

    def do_POST(self):
        p = self.path.split("/open/v1", 1)[-1]
        n = int(self.headers.get("Content-Length", 0)); veri = json.loads(self.rfile.read(n) or b"{}")
        SahteTickTick.istekler.append(("POST", p, veri))
        if p == "/task/completed":
            return self._yaz(200, [t for t in self.gorevler.values() if t.get("status", 0) != 0])
        if p == "/task":
            SahteTickTick.sayac += 1
            veri["id"] = f"yeni{SahteTickTick.sayac}"; veri.setdefault("status", 0)
            self.gorevler[veri["id"]] = veri
            return self._yaz(200, veri)
        m = re.match(r"/task/([^/]+)$", p)
        if m and m.group(1) in self.gorevler:
            self.gorevler[m.group(1)].update(veri)
            return self._yaz(200, self.gorevler[m.group(1)])
        self._yaz(404, {})

    def do_DELETE(self):
        m = re.match(r".*/project/([^/]+)/task/([^/]+)$", self.path)
        SahteTickTick.istekler.append(("DELETE", self.path, None))
        if m:
            self.gorevler.pop(m.group(2), None)
        self._yaz(200, {})


class KimlikSatiriTest(unittest.TestCase):
    def test_uret_oku_ve_ticktick_kacislari(self):
        s = kimlik.satir("TEBLİGAT", mahkeme="Oltu 3. Asliye Hukuk Mahkemesi", esas="2026/24", barkod="5003283066058")
        kacisli = s.replace("(", "\\(").replace(".", "\\.") + "\n\nnot"
        k = kimlik.oku(kacisli)
        self.assertEqual((k["tur"], k["mahkeme"], k["esas"], k["barkod"]),
                         ("TEBLİGAT", "Oltu 3. Asliye Hukuk Mahkemesi", "2026/24", "5003283066058"))

    def test_ekle_ust_satira_koyar_notlari_korur(self):
        s = kimlik.satir("DURUŞMA", mahkeme="X", esas="2025/1", durusma="15/10/2026 09:30")
        icerik = kimlik.ekle("kullanıcı notu\nikinci satır", s)
        self.assertTrue(icerik.startswith("🔖 KİMLİK"))
        self.assertIn("kullanıcı notu\nikinci satır", icerik)
        self.assertEqual(kimlik.ekle(icerik, s).count("🔖 KİMLİK"), 1)   # ikinci kez eklenmez

    def test_kullanici_basligi(self):
        self.assertFalse(kimlik.kullanici_basligi_mi("📨 TEBLİGAT - Oltu 3. Asliye Hukuk Mahkemesi - 2026/24 Esas (Son Gün: 09.11.2026)"))
        self.assertFalse(kimlik.kullanici_basligi_mi("⚖️ DURUŞMA - Rize 1. İş Mahkemesi - 2025/257 Esas (Saat: 09:30)"))
        self.assertFalse(kimlik.kullanici_basligi_mi("Oltu 3. Asliye Hukuk Mahkemesi - 2026/24 Esas"))
        self.assertTrue(kimlik.kullanici_basligi_mi("Bilirkişi raporuna itiraz edilecek"))
        self.assertTrue(kimlik.kullanici_basligi_mi("Cevap dilekçesi yazılacak - Yapılacak"))

    def test_gatekeeper_yeniden_adlandirilan_gorevi_engellemez(self):
        import gatekeeper as gk
        t = {"title": "İstinaf dilekçesi yazılacak", "tags": ["uets", "erolatmaca"], "parentId": "p", "priority": 5,
             "dueDate": "x", "startDate": "x",
             "content": kimlik.satir("TEBLİGAT", mahkeme="Oltu", esas="2026/24", barkod="5003283066058") + "\n\nnot"}
        self.assertEqual(gk.infer_kind(t), "tebligat")
        self.assertEqual([c for c, sev, _ in gk.check(t) if sev == "blok"], [])


class TickTickAkisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), SahteTickTick)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        import config, ticktick_sync, state_manager
        cls.ts, cls.sm = ticktick_sync, state_manager
        config.CONFIG["TICKTICK_API_BASE"] = f"http://127.0.0.1:{cls.srv.server_port}/open/v1"
        cls.tmp = tempfile.TemporaryDirectory()
        state_manager.STATE_FILE = os.path.join(cls.tmp.name, "durum.json")
        os.environ["NO_PROXY"] = "127.0.0.1"; os.environ["no_proxy"] = "127.0.0.1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.tmp.cleanup()

    def setUp(self):
        SahteTickTick.gorevler.clear(); SahteTickTick.istekler.clear()
        self.ts._PROJECT_TASKS_CACHE.clear(); self.ts._TUM_GOREVLER = None
        self.ts._COMPLETED_TASKS_CACHE = None
        if os.path.exists(self.sm.STATE_FILE):
            os.remove(self.sm.STATE_FILE)

    def _tebligat(self, barkod="5003283066058"):
        from utils import calculate_deadlines
        from config import TZ_TURKEY
        return {"court": "Oltu 3. Asliye Hukuk Mahkemesi", "esas_no": "2026/24", "barcode": barkod,
                "deadlines": calculate_deadlines(datetime.now(TZ_TURKEY) - timedelta(hours=2), court="Oltu 3. Asliye Hukuk Mahkemesi"),
                "parties": [], "documents": [], "extracted_paths": [], "gonderen": "Oltu 3. Asliye Hukuk Mahkemesi"}

    def test_yeniden_adlandirilmis_ve_tasinmis_gorev_bulunur_baslik_etiket_oncelik_korunur(self):
        # Kullanıcı görevi başka listeye taşımış, başlığını değiştirmiş, kendi etiketini ve önceliğini vermiş
        SahteTickTick.gorevler["g1"] = {"id": "g1", "projectId": "baska_liste", "status": 0, "priority": 3,
            "title": "Cevap dilekçesi yazılacak", "tags": ["uets", "erolatmaca", "acil"],
            "content": kimlik.satir("TEBLİGAT", mahkeme="Oltu 3. Asliye Hukuk Mahkemesi", esas="2026/24", barkod="5003283066058") + "\n\nbenim notum"}
        tid, yeni, durum = self.ts.create_or_update_uets_subtask(self._tebligat(), "proje_x", None, client_tag="erolatmaca", force=True)
        self.assertEqual((tid, yeni), ("g1", False))
        g = SahteTickTick.gorevler["g1"]
        self.assertEqual(g["title"], "Cevap dilekçesi yazılacak")
        self.assertIn("acil", g["tags"])
        self.assertEqual(g["priority"], 3)
        self.assertIn("benim notum", g["content"])
        self.assertEqual(len([t for t in SahteTickTick.gorevler.values() if t["status"] == 0]), 1)   # mükerrer açılmadı

    def test_yeni_gorevde_kimlik_satiri_ve_esas_no(self):
        tid, yeni, _ = self.ts.create_or_update_uets_subtask(self._tebligat("5003283066999"), "proje_x", None, client_tag="erolatmaca", force=True)
        self.assertTrue(yeni)
        g = SahteTickTick.gorevler[tid]
        k = kimlik.oku(g["content"])
        self.assertEqual((k["esas"], k["barkod"], k["mahkeme"]), ("2026/24", "5003283066999", "Oltu 3. Asliye Hukuk Mahkemesi"))
        self.assertIn("2026/24 Esas", g["content"])

    def test_mukerrer_birlesmede_kullanici_basligi_kalir(self):
        icerik = kimlik.satir("TEBLİGAT", mahkeme="Oltu", esas="2026/24", barkod="5003283066058")
        SahteTickTick.gorevler["a"] = {"id": "a", "projectId": "inbox", "status": 0, "tags": ["uets"],
            "title": "📨 TEBLİGAT - Oltu - 2026/24 Esas (Son Gün: 09.11.2026)", "modifiedTime": "2026-11-01",
            "content": icerik + "\n\n" + "uzun sistem notu " * 50}
        SahteTickTick.gorevler["b"] = {"id": "b", "projectId": "inbox", "status": 0, "tags": ["uets"],
            "title": "Bilirkişi raporuna itiraz edilecek", "modifiedTime": "2026-11-05",
            "content": icerik + "\n\nkısa kullanıcı notu"}
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS["Inbox"] = "inbox"
        try:
            self.ts.clean_and_merge_duplicates()
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)
        kalan = [t for t in SahteTickTick.gorevler.values() if t["status"] == 0]
        self.assertEqual(len(kalan), 1)
        self.assertEqual(kalan[0]["title"], "Bilirkişi raporuna itiraz edilecek")
        self.assertIn("kısa kullanıcı notu", kalan[0]["content"])

    def test_farkli_barkodlar_birlesmez(self):
        for i, b in enumerate(["5003283066058", "5003283066059"]):
            SahteTickTick.gorevler[f"x{i}"] = {"id": f"x{i}", "projectId": "inbox", "status": 0, "tags": ["uets"],
                "title": "Yapılacak iş", "content": kimlik.satir("TEBLİGAT", mahkeme="Oltu", esas="2026/24", barkod=b)}
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS["Inbox"] = "inbox"
        try:
            self.ts.clean_and_merge_duplicates()
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)
        self.assertEqual(len(SahteTickTick.gorevler), 2)

    def test_esas_nosuz_tebligat_gorev_acar_ve_tekrarlamaz(self):
        from utils import calculate_deadlines
        from config import TZ_TURKEY
        item = {"konu_raw": "AZİLNAME", "court": "AZİLNAME", "gonderen": "TÜRKİYE NOTERLER BİRLİĞİ", "uets_no": "12a3-uuid",
                "deadlines": calculate_deadlines(datetime.now(TZ_TURKEY), court="AZİLNAME")}
        tid, yeni = self.ts.create_or_update_esassiz_tebligat(item)
        self.assertTrue(yeni)
        self.assertEqual(kimlik.oku(SahteTickTick.gorevler[tid]["content"]).get("uets_no"), "12a3-uuid")
        SahteTickTick.gorevler[tid]["title"] = "Azilname: vekâlet sona erdi, dosyalar kontrol edilecek"   # kullanıcı değiştirdi
        tid2, yeni2 = self.ts.create_or_update_esassiz_tebligat(item)
        self.assertEqual((tid2, yeni2), (tid, False))
        self.assertEqual(len(SahteTickTick.gorevler), 1)

    def test_denetim_eski_goreve_kimlik_ekler_basliga_dokunmaz(self):
        SahteTickTick.gorevler["e"] = {"id": "e", "projectId": "inbox", "status": 0, "tags": ["uets"], "parentId": "kart",
            "title": "Bilirkişi raporu itiraz", "dueDate": "2026-11-09T17:00:00+0300",
            "content": "🔔 YENİ ELEKTRONİK TEBLİGAT\n- **Merci:** Konya 1. İş Mahkemesi\n- **Dosya:** 2022/812 Esas\n- **Barkod:** `5003218402111`"}
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS["Inbox"] = "inbox"
        try:
            self.ts.audit_and_heal_all_tasks()
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)
        g = SahteTickTick.gorevler["e"]
        k = kimlik.oku(g["content"])
        self.assertEqual((k.get("mahkeme"), k.get("esas"), k.get("barkod")), ("Konya 1. İş Mahkemesi", "2022/812", "5003218402111"))
        self.assertEqual(g["title"], "Bilirkişi raporu itiraz")
        self.assertNotIn("priority", [kk for (_, p, v) in SahteTickTick.istekler if p == "/task/e" for kk in v])


class UstAltDuzeniTest(TickTickAkisTest):
    """Kullanıcının üst/alt görev düzeni, alt görevleri ve kontrol listeleri korunur."""
    test_yeniden_adlandirilmis_ve_tasinmis_gorev_bulunur_baslik_etiket_oncelik_korunur = None
    test_yeni_gorevde_kimlik_satiri_ve_esas_no = None
    test_mukerrer_birlesmede_kullanici_basligi_kalir = None
    test_farkli_barkodlar_birlesmez = None
    test_esas_nosuz_tebligat_gorev_acar_ve_tekrarlamaz = None
    test_denetim_eski_goreve_kimlik_ekler_basliga_dokunmaz = None

    def _teb_gorev(self, **ek):
        g = {"id": "g1", "projectId": "liste_a", "status": 0, "priority": 5, "title": "Kendi başlığım", "tags": ["uets"],
             "content": kimlik.satir("TEBLİGAT", mahkeme="Oltu 3. Asliye Hukuk Mahkemesi", esas="2026/24", barkod="5003283066058") + "\n\nnot"}
        g.update(ek)
        SahteTickTick.gorevler["g1"] = g
        return g

    def test_kullanicinin_sectigi_ust_gorev_degismez(self):
        SahteTickTick.gorevler["benim"] = {"id": "benim", "projectId": "liste_a", "status": 0, "title": "Benim ana görevim", "content": ""}
        SahteTickTick.gorevler["kart1"] = {"id": "kart1", "projectId": "liste_a", "status": 0, "title": "Oltu - 2026/24 Esas", "content": ""}
        self._teb_gorev(parentId="benim")
        self.ts.create_or_update_uets_subtask(self._tebligat(), "liste_a", "kart1", force=True)
        g = SahteTickTick.gorevler["g1"]
        self.assertEqual((g["parentId"], g["projectId"]), ("benim", "liste_a"))

    def test_yetim_gorev_ayni_listedeki_karta_baglanir_baska_listedekine_baglanmaz(self):
        SahteTickTick.gorevler["kart1"] = {"id": "kart1", "projectId": "liste_a", "status": 0, "title": "Oltu - 2026/24 Esas", "content": ""}
        self._teb_gorev()
        self.ts.update_task_details("g1", "liste_a", "kart1")
        self.assertEqual(SahteTickTick.gorevler["g1"].get("parentId"), "kart1")
        SahteTickTick.gorevler["g1"].pop("parentId")
        self.ts.update_task_details("g1", "liste_a", "baska_listedeki_kart")
        self.assertIsNone(SahteTickTick.gorevler["g1"].get("parentId"))

    def test_tasinan_gorev_geri_tasinmaz_kontrol_listesi_gonderilir(self):
        self._teb_gorev(projectId="liste_b", items=[{"id": "i1", "title": "madde 1", "status": 0}])
        self.ts.update_task_details("g1", "liste_a", None, tags=["uets", "acil"])
        son = [v for (m, p, v) in SahteTickTick.istekler if p == "/task/g1"][-1]
        self.assertEqual(son["projectId"], "liste_b")
        self.assertEqual(son["items"][0]["title"], "madde 1")

    def test_ekler_alt_gorev_olarak_eklenir_gorev_silinmez(self):
        self._teb_gorev(childIds=["alt1"])
        SahteTickTick.gorevler["alt1"] = {"id": "alt1", "projectId": "liste_a", "status": 0, "parentId": "g1", "title": "Kullanıcının alt görevi", "content": ""}

        def sahte_eposta(konu, govde, ekler):   # TickTick e-posta ile görev açar (dosya ekli, Inbox'a)
            SahteTickTick.sayac += 1
            gid = f"eposta{SahteTickTick.sayac}"
            SahteTickTick.gorevler[gid] = {"id": gid, "projectId": "inbox", "status": 0, "title": konu,
                                          "content": govde + "\n![file](x/ustyazi.pdf)"}
            return True
        eski_ep, eski_uyku = self.ts.send_task_via_email, self.ts.time.sleep
        self.ts.send_task_via_email = sahte_eposta
        self.ts.time.sleep = lambda s: None
        try:
            t = self._tebligat(); t["extracted_paths"] = ["/tmp/ustyazi.pdf"]
            self.ts.create_or_update_uets_subtask(t, "liste_a", None)
        finally:
            self.ts.send_task_via_email, self.ts.time.sleep = eski_ep, eski_uyku
        self.assertIn("g1", SahteTickTick.gorevler)                       # kullanıcının görevi silinmedi
        self.assertEqual(SahteTickTick.gorevler["g1"]["title"], "Kendi başlığım")
        self.assertIn("alt1", SahteTickTick.gorevler)                     # alt görevi duruyor
        ek = [g for g in SahteTickTick.gorevler.values() if kimlik.oku(g.get("content") or "").get("tur") == "EK"]
        self.assertEqual(len(ek), 1)
        self.assertEqual(ek[0].get("parentId"), "g1")                     # ekler alt görev olarak bağlandı
        self.assertTrue(self.ts.gercek_ek_var(SahteTickTick.gorevler["g1"], "5003283066058"))
        self.assertFalse(any(m == "DELETE" for (m, p, v) in SahteTickTick.istekler))
        # Ek görevi tebligat sanılıp ikinci tebligat görevi açılmamalı, mükerrer temizliği EK görevini silmemeli
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update({"Inbox": "inbox", "A": "liste_a"})
        try:
            self.ts.clean_and_merge_duplicates()
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)
        self.assertEqual(len(SahteTickTick.gorevler), 3)

    def test_alt_gorevli_mukerrer_silinmez(self):
        icerik = kimlik.satir("TEBLİGAT", mahkeme="Oltu", esas="2026/24", barkod="5003283066058")
        SahteTickTick.gorevler["a"] = {"id": "a", "projectId": "inbox", "status": 0, "tags": ["uets"], "title": "A",
                                      "content": icerik + "\n" + "x" * 900}
        SahteTickTick.gorevler["b"] = {"id": "b", "projectId": "inbox", "status": 0, "tags": ["uets"], "title": "B",
                                      "content": icerik, "childIds": ["c"]}
        SahteTickTick.gorevler["c"] = {"id": "c", "projectId": "inbox", "status": 0, "parentId": "b", "title": "alt", "content": ""}
        old_ids = dict(self.ts.PROJECT_IDS)
        self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS["Inbox"] = "inbox"
        try:
            self.ts.clean_and_merge_duplicates()
        finally:
            self.ts.PROJECT_IDS.clear(); self.ts.PROJECT_IDS.update(old_ids)
        self.assertIn("b", SahteTickTick.gorevler)   # alt görevli kopya ana görev olarak kaldı
        self.assertIn("c", SahteTickTick.gorevler)


class GercekCalismaHatalariTest(UstAltDuzeniTest):
    """10.11.2026 gerçek çalışmasında görülen hatalar."""
    test_kullanicinin_sectigi_ust_gorev_degismez = None
    test_yetim_gorev_ayni_listedeki_karta_baglanir_baska_listedekine_baglanmaz = None
    test_tasinan_gorev_geri_tasinmaz_kontrol_listesi_gonderilir = None
    test_ekler_alt_gorev_olarak_eklenir_gorev_silinmez = None
    test_alt_gorevli_mukerrer_silinmez = None

    def test_tamamlanmis_durusma_yeniden_acilmaz(self):
        yarin = (datetime.now() + timedelta(days=3)).strftime("%d/%m/%Y")
        SahteTickTick.gorevler["d1"] = {"id": "d1", "projectId": "liste_a", "status": 2,
            "title": "⚖️ DURUŞMA - Oltu 3. Asliye Hukuk Mahkemesi - 2026/6 Esas (Saat: 11:00)",
            "content": f"- **Dosya:** 2026/6 Esas\n- **Duruşma Tarihi:** {yarin}"}
        tid, yeni = self.ts.create_or_update_durusma_subtask("Oltu 3. Asliye Hukuk Mahkemesi", "2026/6", "liste_a", None, yarin, "11:00")
        self.assertEqual((tid, yeni), ("d1", False))
        self.assertEqual(len(SahteTickTick.gorevler), 1)

    def test_gecmis_durusmaya_gorev_acilmaz(self):
        dun = (datetime.now() - timedelta(days=4)).strftime("%d/%m/%Y")
        tid, yeni = self.ts.create_or_update_durusma_subtask("Oltu 3. Asliye Hukuk Mahkemesi", "2026/6", "liste_a", None, dun, "11:00")
        self.assertEqual((tid, yeni), (None, False))
        self.assertEqual(len(SahteTickTick.gorevler), 0)

    def test_gec_gelen_ek_gorevi_sonraki_turda_baglanir(self):
        self._teb_gorev()
        self.sm.update_barcode_state("5003283066058", "g1", has_eyp=True, project_id="liste_a", ek_gonderildi=time.time())
        SahteTickTick.gorevler["ek9"] = {"id": "ek9", "projectId": "inbox", "status": 0, "title": "📎 EYP ekleri - Oltu - 2026/24 Esas",
            "content": kimlik.satir("EK", mahkeme="Oltu 3. Asliye Hukuk Mahkemesi", esas="2026/24", barkod="5003283066058") + "\n![file](a/b.pdf)"}
        self.ts.create_or_update_uets_subtask(self._tebligat(), "liste_a", None)
        self.assertEqual(SahteTickTick.gorevler["ek9"].get("parentId"), "g1")
        self.assertEqual((self.sm.get_barcode_state("5003283066058") or {}).get("ek_gorevi"), "ek9")

    def test_esassiz_csv_ve_eyp_kaydi_tek_kayit_olur(self):
        import main
        from utils import calculate_deadlines
        from config import TZ_TURKEY
        d = calculate_deadlines(datetime.now(TZ_TURKEY))
        csv_k = {"source": "csv", "konu_raw": "AZİLNAME", "court": "AZİLNAME", "esas_no": "", "barcode": "",
                 "uets_no": "50e30414-dc43", "gonderen": "NOTER", "deadlines": d}
        eyp_k = {"eyp_path": "/sdcard/Download/UETS_Arsivi/50e30414-dc43.eyp", "court": "AZİLNAME", "esas_no": "",
                 "barcode": "", "konu_raw": "AZİLNAME", "deadlines": d}
        birlesik = main.merge_and_cross_validate([csv_k], [eyp_k])
        self.assertEqual(len(birlesik), 1)
        self.assertEqual(birlesik[0].get("uets_no"), "50e30414-dc43")


if __name__ == "__main__":
    unittest.main()
