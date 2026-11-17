# -*- coding: utf-8 -*-
"""Bağlantı kopması (Wi-Fi -> mobil veri), yarım kalan işler ve bütünlük denetimi.
- yarım okumayla kart/görev KOPYASI açılmaz, hiçbir şey silinmez
- kısa kesintide yeniden denenir, uzun kesintide bağlantı beklenip KALDIĞI YERDEN devam edilir
- yanıtı kaybolan "oluştur" isteği tekrar gönderilmeden önce "oluşmuş mu?" diye bakılır
- mükerrer dava kartları birleştirilir (alt görevli kopya silinmez), yarım kalan yazmalar raporlanır
Gerçek hesaplara istek gitmez (yerel sahte sunucu)."""
import json, os, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AVUKAT_ENV_TASIMA"] = "0"
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")       # testte internet beklenmez
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")            # gerçek veri/ klasörüne günlük yazılmaz
os.environ["TICKTICK_TOKEN"] = "test"

import baglanti  # noqa: E402
import config  # noqa: E402
import kimlik  # noqa: E402
import ticktick_sync as tts  # noqa: E402

KART = {"id": "kart1", "projectId": "p1", "title": "Ankara 5. İş Mahkemesi - 2026/83 Esas", "status": 0,
        "content": "⚖️ **Dava Dosyası**"}


class _Sunucu(BaseHTTPRequestHandler):
    """İlk `hata_sayisi` GET'te 503; POST /task oluşturur (ilk `kopar` POST'ta yanıt vermeden bağlantıyı keser:
    sunucu görevi OLUŞTURMUŞ ama istemci yanıtı alamamış olur). DELETE'ler kaydedilir."""
    hata_sayisi = 0
    istek = 0
    kopar = 0
    postlar, silinenler, gorevler = [], [], []

    def log_message(self, *a):
        pass

    def _yanit(self, kod, govde):
        b = json.dumps(govde).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        S = type(self)
        S.istek += 1
        if S.istek <= S.hata_sayisi:
            return self._yanit(503, {})
        if self.path.endswith("/project"):
            return self._yanit(200, [{"id": "p1"}])
        self._yanit(200, {"tasks": [dict(t) for t in S.gorevler]})

    def do_POST(self):
        S = type(self)
        n = int(self.headers.get("Content-Length") or 0)
        govde = json.loads(self.rfile.read(n) or b"{}")
        S.postlar.append(govde)
        if self.path.endswith("/task"):
            yeni = dict(govde, id=f"g{len(S.postlar)}", status=0)
            S.gorevler.append(yeni)
            if S.kopar > 0:
                S.kopar -= 1
                self.close_connection = True
                self.connection.shutdown(2)        # yanıt yok: "Connection aborted"
                return
            return self._yanit(200, yeni)
        self._yanit(200, {"id": govde.get("id")})

    def do_DELETE(self):
        type(self).silinenler.append(self.path.rsplit("/", 1)[-1])
        self._yanit(200, {})


class BaglantiKopmasiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), _Sunucu)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.eski_base = config.CONFIG.get("TICKTICK_API_BASE")

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        config.CONFIG["TICKTICK_API_BASE"] = cls.eski_base

    def setUp(self):
        _Sunucu.istek, _Sunucu.hata_sayisi, _Sunucu.kopar = 0, 0, 0
        _Sunucu.postlar, _Sunucu.silinenler, _Sunucu.gorevler = [], [], [dict(KART)]
        tts._PROJECT_TASKS_CACHE.clear()
        tts._TUM_GOREVLER = None
        config.CONFIG["TICKTICK_API_BASE"] = f"http://127.0.0.1:{self.srv.server_port}/open/v1"
        self.eski = (baglanti.kisa_beklemeler, baglanti._uyu, baglanti.uzun_bekleme_sn, baglanti.internet_var)
        baglanti._uyu = lambda s: None
        baglanti.kisa_beklemeler = lambda: []

    def tearDown(self):
        (baglanti.kisa_beklemeler, baglanti._uyu, baglanti.uzun_bekleme_sn, baglanti.internet_var) = self.eski
        tts._PROJECT_TASKS_CACHE.clear()
        tts._TUM_GOREVLER = None

    # ------------------------------------------------------------------ okuma
    def test_okunamayan_liste_bos_sayilmaz(self):
        config.CONFIG["TICKTICK_API_BASE"] = "http://127.0.0.1:9/open/v1"            # internet yok
        with self.assertRaises(tts.TickTickOkumaHatasi):
            tts.get_project_tasks_live("p1")

    def test_okunamazsa_kart_kopyasi_acilmaz(self):
        _Sunucu.hata_sayisi = 99
        baglanti.kisa_beklemeler = lambda: [1, 1]
        with self.assertRaises(tts.TickTickOkumaHatasi):
            tts.find_or_create_parent_task("Ankara 5. İş Mahkemesi", "2026/83", "p1")
        self.assertEqual(_Sunucu.postlar, [])                                            # hiçbir şey yazılmadı

    def test_kisa_kesintide_yeniden_dener_ve_var_olan_karti_bulur(self):
        _Sunucu.hata_sayisi = 2                                                          # 2 başarısız, 3. başarılı
        baglanti.kisa_beklemeler = lambda: [1, 1, 1]
        kid, pid = tts.find_or_create_parent_task("Ankara 5. İş Mahkemesi", "2026/83", "p1")
        self.assertEqual((kid, pid), ("kart1", "p1"))
        self.assertFalse(tts.SON_KART_YENI)                                              # "açıldı" denmez
        self.assertEqual(_Sunucu.postlar, [])

    def test_uzun_kesintide_baglanti_beklenip_kaldigi_yerden_devam_edilir(self):
        _Sunucu.hata_sayisi = 3                                                          # kısa denemeler yetmez
        baglanti.kisa_beklemeler = lambda: [1, 1]
        baglanti.uzun_bekleme_sn = lambda: 600
        baglanti.internet_var = lambda hedef=None: True                                 # bağlantı geri geldi
        gorevler = tts.get_project_tasks_live("p1")
        self.assertEqual([g["id"] for g in gorevler], ["kart1"])

    def test_mukerrer_temizligi_yarim_okumayla_silmez(self):
        _Sunucu.hata_sayisi = 99
        with self.assertRaises(tts.TickTickOkumaHatasi):
            tts.clean_and_merge_duplicates()
        self.assertEqual((_Sunucu.postlar, _Sunucu.silinenler), ([], []))

    # ------------------------------------------------------------------ yazma
    def test_yaniti_kaybolan_olusturma_tekrar_gonderilmez(self):
        _Sunucu.kopar = 1                                    # sunucu görevi açtı ama yanıt gelmedi
        payload = {"title": "📨 TEBLİGAT - X - 2026/1 Esas", "projectId": "p1",
                   "content": kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="5001") + "\n\nnot"}
        sonuc = tts.tt_post(f"{config.CONFIG['TICKTICK_API_BASE']}/task", payload, what="tebligat görevi")
        self.assertEqual(sonuc.get("id"), "g1")                                          # oluşan görev bulundu
        self.assertEqual(len(_Sunucu.postlar), 1)                                        # İKİNCİ KEZ açılmadı
        self.assertEqual(sum(1 for g in _Sunucu.gorevler if g.get("title") == payload["title"]), 1)

    def test_olusmamis_gorev_bir_kez_daha_gonderilir(self):
        payload = {"title": "Yeni görev", "projectId": "p1", "content": "a"}
        _Sunucu.kopar = 1
        _Sunucu.gorevler = [dict(KART)]
        eski_dogrula = tts._olusturulmus_gorev
        tts._olusturulmus_gorev = lambda p: None                                         # sunucuda yok
        try:
            sonuc = tts.tt_post(f"{config.CONFIG['TICKTICK_API_BASE']}/task", payload)
        finally:
            tts._olusturulmus_gorev = eski_dogrula
        self.assertEqual(len(_Sunucu.postlar), 2)
        self.assertTrue(sonuc and sonuc.get("id"))


class ButunlukTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.eski_gunluk = baglanti.GUNLUK
        baglanti.GUNLUK = os.path.join(self.tmp.name, "gunluk.jsonl")
        os.environ["ISLEM_GUNLUGU"] = "1"

    def tearDown(self):
        baglanti.GUNLUK = self.eski_gunluk
        os.environ["ISLEM_GUNLUGU"] = "0"
        self.tmp.cleanup()

    def test_yarim_kalan_yazma_raporlanir_bir_kez(self):
        baglanti.gunluk_yaz({"islem": "TickTick ana dava kartı", "anahtar": "A - 2026/1 Esas", "durum": "basladi", "olusturma": True})
        baglanti.gunluk_yaz({"islem": "TickTick görev", "anahtar": "B", "durum": "basladi"})
        baglanti.gunluk_yaz({"islem": "TickTick görev", "anahtar": "B", "durum": "tamam"})
        yarim = baglanti.yarim_kalanlar(en_az_dk=0)
        self.assertEqual([k["anahtar"] for k in yarim], ["A - 2026/1 Esas"])
        import butunluk
        rapor = butunluk.yarim_islemler([{"title": "A - 2026/1 Esas"}, {"title": "A - 2026/1 Esas"}], en_az_dk=0)
        self.assertIn("2 kopya", rapor[0])
        self.assertEqual(baglanti.yarim_kalanlar(en_az_dk=0), [])                       # denetlendi: tekrar raporlanmaz

    def test_mukerrer_dava_karti_birlestirilir_alt_gorevli_kopya_korunur(self):
        import butunluk
        silinen, yazilan = [], []
        import requests
        eski = (requests.delete, tts.tt_post)
        requests.delete = lambda url, **k: silinen.append(url.rsplit("/", 1)[-1]) or type("R", (), {"status_code": 200})()
        tts.tt_post = lambda url, payload, **k: yazilan.append(payload) or {}
        try:
            gorevler = [
                {"id": "asil", "projectId": "p1", "title": "Ankara 5. İş Mahkemesi - 2026/83 Esas", "status": 0,
                 "childIds": ["c1"], "createdTime": "2026-10-20T01:00:00+0300", "tags": ["osman"], "content": "⚖️ **Dava Dosyası**"},
                {"id": "bos", "projectId": "p1", "title": "Ankara 5. İş Mahkemesi - 2026/83 Esas", "status": 0,
                 "createdTime": "2026-11-10T16:00:00+0300", "tags": ["osman", "yeni"], "content": "Kullanıcı notu: bilirkişi"},
                {"id": "alt", "projectId": "p1", "title": "Ankara 5. İş Mahkemesi 2026/83 Esas", "status": 0,
                 "childIds": ["c9"], "createdTime": "2026-11-10T16:01:00+0300", "content": ""},
                {"id": "baska", "projectId": "p1", "title": "Ankara 5. İş Mahkemesi - 2026/84 Esas", "status": 0, "content": ""},
            ]
            b, s, elle = butunluk.kart_mukerrerlerini_birlestir(gorevler)
        finally:
            requests.delete, tts.tt_post = eski
        self.assertEqual((b, s), (1, 1))
        self.assertEqual(silinen, ["bos"])                                                # yalnızca boş kopya silindi
        self.assertEqual(len(elle), 1)                                                    # alt görevli kopya raporlandı
        self.assertIn("Kullanıcı notu: bilirkişi", yazilan[0]["content"])                # not ana karta taşındı
        self.assertEqual(yazilan[0]["tags"], ["osman", "yeni"])


if __name__ == "__main__":
    unittest.main()
