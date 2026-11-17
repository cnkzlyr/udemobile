# -*- coding: utf-8 -*-
"""UETS API istemcisi, CSV biçimi, TickTick tarih/hata davranışı için yerel sahte sunucularla testler.
Çalıştırma: python3 -m unittest discover -s tests"""
import io, json, os, sys, tempfile, threading, unittest, zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AVUKAT_ENV_TASIMA"] = "0"   # testler gerçek gizli bilgileri taşımaz/okumaz
os.environ["TICKTICK_TOKEN"] = "test"
os.environ.setdefault("BAGLANTI_BEKLEME_SN", "0")       # testte internet beklenmez
os.environ.setdefault("TICKTICK_YENIDEN_DENEME", "0")
os.environ.setdefault("ISLEM_GUNLUGU", "0")

import uets_api  # noqa: E402
from config import TZ_TURKEY  # noqa: E402

TS = int(datetime(2026, 11, 2, 10, 51, tzinfo=TZ_TURKEY).timestamp())
MESAJLAR = [
    {"id": f"m{i}", "sender_name": "Konya 1. İş Mahkemesi", "status": "delivered", "size": 2048 + i,
     "subject": f"Konya 1. İş Mahkemesi [2022/{800 + i}] [Konya 1. İş Mahkemesi-50032184021{i:02d}-0-2022/{800 + i}]",
     "inserttime": TS - i * 3600}
    for i in range(23)
]
EYP = io.BytesIO()
with zipfile.ZipFile(EYP, "w") as z:
    z.writestr("ustyazi.pdf", b"%PDF-1.4 test")
EYP = EYP.getvalue()


class SahteUets(BaseHTTPRequestHandler):
    istekler = []
    TERS = False

    def log_message(self, *a):
        pass

    def do_GET(self):
        SahteUets.istekler.append(self.path)
        if self.headers.get("Authorization") != "Bearer gecerli":
            self.send_response(401); self.end_headers(); return
        if self.path.startswith("/messages?"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            start, count = int(q.get("start", ["0"])[0]), int(q.get("count", ["10"])[0])
            # Gerçek UETS: sort=inserttime -> yeniden eskiye, sort=-inserttime -> eskiden yeniye.
            # TERS=True: tersini yapan bir sunucu (istemci sırayı kendisi denetleyip çevirmeli).
            yeni_once = (q.get("sort", ["inserttime"])[0] == "inserttime") != SahteUets.TERS
            liste = MESAJLAR if yeni_once else list(reversed(MESAJLAR))
            govde = json.dumps(liste[start:start + count]).encode()
            self.send_response(200); self.send_header("X-Total-Count", str(len(MESAJLAR)))
            self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(govde); return
        if self.path == "/messages/m3/_download":
            self.send_response(200); self.send_header("Content-Disposition", 'attachment; filename="5003218402103.eyp"')
            self.end_headers(); self.wfile.write(EYP); return
        if self.path == "/messages/hata/_download":
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"error":"x"}'); return
        self.send_response(404); self.end_headers()


class SahteTickTick(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); veri = json.loads(self.rfile.read(n) or b"{}")
        if self.headers.get("Authorization") != "Bearer test":
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"errorMessage":"unauthorized"}'); return
        if "dueDate" in veri and "+0300" not in veri["dueDate"]:
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"errorMessage":"bad date"}'); return
        veri["id"] = "yeni1"
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(veri).encode())


def sunucu(handler):
    s = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"


class UetsApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.url = sunucu(SahteUets)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def test_tum_sayfalar_ve_siralama(self):
        SahteUets.istekler.clear()
        s = uets_api._oturum("gecerli")
        m = uets_api.mesajlari_listele(s, en_fazla=200, sayfa_boyu=10, api_url=self.url)
        self.assertEqual(len(m), 23)                     # 3 sayfa (10+10+3), ekrandaki 10 satırla sınırlı değil
        self.assertEqual(m[0]["id"], "m0")               # yeniden eskiye
        self.assertTrue(all("folders_id=1" in p and "sort=inserttime" in p for p in SahteUets.istekler if p.startswith("/messages?")))

    def test_ters_siralayan_sunucuda_en_yeniler_alinir(self):
        # 534 kaydın en eski 200'ünü alma hatasının tekrarı olmamalı
        SahteUets.TERS = True
        try:
            m = uets_api.mesajlari_listele(uets_api._oturum("gecerli"), en_fazla=5, sayfa_boyu=5, api_url=self.url)
        finally:
            SahteUets.TERS = False
        self.assertEqual([x["id"] for x in m], ["m0", "m1", "m2", "m3", "m4"])

    def test_eski_kayitta_sayfalama_durur(self):
        SahteUets.istekler.clear()
        m = uets_api.mesajlari_listele(uets_api._oturum("gecerli"), en_fazla=200, sayfa_boyu=5, api_url=self.url, en_eski_gun=0.2)
        # mesajlar saatte bir: ~5 saatlik sınır ilk sayfalarda aşılır, 23 kaydın hepsi istenmez
        self.assertLess(len(m), 23)

    def test_gecersiz_oturum(self):
        with self.assertRaises(uets_api.UetsApiHatasi):
            uets_api.mesajlari_listele(uets_api._oturum("eski"), api_url=self.url)

    def test_csv_portal_bicimi_ve_csv_parser(self):
        import csv_parser
        s = uets_api._oturum("gecerli")
        m = uets_api.mesajlari_listele(s, api_url=self.url)
        with tempfile.TemporaryDirectory() as d:
            yol = uets_api.csv_yaz(m, os.path.join(d, "tebligatlar.csv"))
            with open(yol, "rb") as f:
                self.assertTrue(f.read(3) == b"\xef\xbb\xbf")   # BOM (portal useBom)
            ogeler = csv_parser.parse_csv_file(yol)
        self.assertEqual(len(ogeler), 23)
        self.assertEqual(ogeler[0]["barcode"], "5003218402100")
        self.assertEqual(ogeler[0]["esas_no"], "2022/800")
        self.assertEqual(ogeler[0]["court"], "Konya 1. İş Mahkemesi")
        self.assertEqual(ogeler[0]["deadlines"]["gelis_str"], "02.11.2026 10:51")

    def test_eyp_indir_ve_zip_dogrulama(self):
        s = uets_api._oturum("gecerli")
        with tempfile.TemporaryDirectory() as d:
            yol = uets_api.eyp_indir(s, "m3", d, api_url=self.url)
            self.assertEqual(os.path.basename(yol), "5003218402103.eyp")
            self.assertTrue(zipfile.is_zipfile(yol))
            with self.assertRaises(uets_api.UetsApiHatasi):
                uets_api.eyp_indir(s, "hata", d, api_url=self.url)
            self.assertFalse(any(f.startswith("hata") for f in os.listdir(d)))  # hatalı yanıt EYP diye yazılmaz

    def test_barkod(self):
        self.assertEqual(uets_api.barkod_bul("X [2026/142] [Ankara 73. Asliye Ceza Mahkemesi-5003184040744-0-2026/142]"), "5003184040744")


class TarihVeTickTickTest(unittest.TestCase):
    def test_tarihler_gercek_ofsetle(self):
        from utils import calculate_deadlines, parse_hearing_datetime
        d = calculate_deadlines(datetime(2026, 10, 20, 10, 51, tzinfo=TZ_TURKEY), court="Konya 1. İş Mahkemesi")
        self.assertEqual(d["start_iso"], "2026-10-20T10:51:00+0300")   # eskiden ...+0000 -> TickTick'te 13:51
        self.assertTrue(d["due_iso"].endswith("T17:00:00+0300"))        # eskiden 20:00 görünüyordu
        _, iso = parse_hearing_datetime("15/10/2026", "09:30")
        self.assertEqual(iso, "2026-10-15T09:30:00+0300")              # eskiden 12:30 görünüyordu

    def test_tt_post_hata_gorunur(self):
        import ticktick_sync
        srv, url = sunucu(SahteTickTick)
        try:
            ok = ticktick_sync.tt_post(url + "/task", {"title": "t", "dueDate": "2026-10-15T09:30:00+0300"})
            self.assertEqual(ok["id"], "yeni1")
            buf = io.StringIO(); eski = sys.stdout; sys.stdout = buf
            try:
                self.assertIsNone(ticktick_sync.tt_post(url + "/task", {"title": "t", "dueDate": "2026-10-15T09:30:00+0000"}))
                tok = ticktick_sync.CONFIG["TICKTICK_TOKEN"]; ticktick_sync.CONFIG["TICKTICK_TOKEN"] = "eski"
                self.assertIsNone(ticktick_sync.tt_post(url + "/task", {"title": "t"}))
                ticktick_sync.CONFIG["TICKTICK_TOKEN"] = tok
            finally:
                sys.stdout = eski
            cikti = buf.getvalue()
            self.assertIn("HTTP 400", cikti)
            self.assertIn("TICKTICK_TOKEN", cikti)
        finally:
            srv.shutdown()


class EkKuraliTest(unittest.TestCase):
    def test_yazi_ek_sayilmaz_dosya_sayilir_yeni_gonderim_beklenir(self):
        import tempfile, time
        import state_manager, ticktick_sync
        with tempfile.TemporaryDirectory() as d:
            eski = getattr(state_manager, "STATE_FILE", None)
            if eski is not None:
                state_manager.STATE_FILE = os.path.join(d, "durum.json")
            try:
                yazi = {"id": "t1", "content": "📑 **EKLİ EVRAKLAR \\(EYP Paketi\\):**\n📁 **Cihazdaki Dosya Yolu:** /sdcard/x"}
                self.assertFalse(ticktick_sync.gercek_ek_var(yazi, "5003000000001"))      # yalnızca yazı: ek YOK
                self.assertTrue(ticktick_sync.gercek_ek_var({"content": "![file](abc/ustyazi.pdf)"}))
                if eski is not None:
                    state_manager.update_barcode_state("5003000000001", "t1", has_eyp=True, ek_gonderildi=time.time())
                    self.assertTrue(ticktick_sync.gercek_ek_var(yazi, "5003000000001"))   # 24 saat içinde gönderildi: bekle
                    state_manager.update_barcode_state("5003000000001", "t1", has_eyp=True, ek_gonderildi=time.time() - 2 * 86400)
                    self.assertFalse(ticktick_sync.gercek_ek_var(yazi, "5003000000001"))  # 2 gün önce: yeniden gönder
            finally:
                if eski is not None:
                    state_manager.STATE_FILE = eski


if __name__ == "__main__":
    unittest.main()
