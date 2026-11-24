#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
caneditor — CanEditor'un TÜM yeteneklerinin terminal (komut satırı) karşılığı
==============================================================================

TR: Grafik arayüzdeki her düğme/sekme, Hukuk Asistanı yerel sunucusunun (sunucu.py) bir /api uç noktasını
    çağırır. Bu araç AYNI uç noktaları çağırır; bu yüzden terminalden yapılan iş, arayüzden yapılanla birebir
    aynıdır (aynı veritabanı, aynı günlük, aynı e-imza → mobil imza kuralı, aynı TickTick mükerrer denetimi).

    Çalışma biçimi:
      1. Açık bir CanEditor/sunucu varsa (127.0.0.1:8765) ona bağlanır (anahtar veri klasöründen okunur).
      2. Yoksa sunucuyu BU SÜREÇ İÇİNDE, rastgele bir portta, arka plan zamanlayıcıları OLMADAN başlatır,
         komutu çalıştırır ve kapatır. Kurulum, Python dışında bir şey gerektirmez.

    Platformlar: Windows (caneditor.bat / caneditor.ps1), macOS/Linux (caneditor), Android/Termux (caneditor),
    paketli masaüstü sürümünde Python olmadan:  asistan-sunucu --calistir caneditor_cli.py <komut>

EN: Terminal front-end for every GUI feature. It calls the very same local REST API that the GUI uses, so
    behaviour (database, logs, e-signature → mobile-signature fallback, TickTick de-duplication) is identical.

Örnekler / Examples:
    caneditor durum                         # sunucu, UYAP/UETS oturumu, e-imza, Java/jar, TickTick özeti
    caneditor evrak ara "tensip" --kategori tebligat --baslangic 2026-11-01
    caneditor pdf ~/UYAP_Indirilenler       # klasördeki tüm UDF/TIFF/görüntüleri PDF'e (resmî Havelsan motoru)
    caneditor donustur dilekce.udf --bicim docx
    caneditor imzala dilekce.udf            # takılı kart → sessiz e-imza; yoksa Mobil İmza (arka planda)
    caneditor gorev evrak-nobetci --izle    # GUI'deki "Görevler" listesindeki herhangi bir görev
    caneditor ticktick denetle              # mükerrer / eksik görev raporu (değişiklik yapmaz)
    caneditor ticktick duzenle              # raporu uygular (tamamlanan + yapılmayacak görevler de dikkate alınır)
    caneditor oz-denetim                    # kendi kendini test et, onar, günlüğe yaz
    caneditor api GET /api/ajanda gun=30    # her uç nokta doğrudan (gelişmiş)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

VARSAYILAN_PORT = int(os.environ.get("CANASISTAN_PORT") or 8765)


# ─────────────────────────────────────────────────────────────────────────────
# Sunucu bağlantısı / Server connection
# ─────────────────────────────────────────────────────────────────────────────
class Baglanti:
    """Çalışan sunucuya bağlanır ya da süreç içinde geçici bir sunucu açar.
    EN: connects to a running server or spins up an in-process one (no background schedulers)."""

    def __init__(self, port: int | None = None, yerel_zorla: bool = False):
        import sunucu  # noqa: WPS433 — aynı kod tabanı
        self.sunucu = sunucu
        self.anahtar = sunucu.anahtar_al()
        self.port = port or VARSAYILAN_PORT
        self._srv = None
        if yerel_zorla or not self._canli_mi():
            self._srv = sunucu.sunucu_olustur(0, self.anahtar)
            self.port = self._srv.server_address[1]
            threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def _canli_mi(self) -> bool:
        try:
            self.istek("GET", "/api/durum", zaman_asimi=2)
            return True
        except Exception:
            return False

    @property
    def gomulu(self) -> bool:
        return self._srv is not None

    def istek(self, yontem: str, yol: str, govde: dict | None = None, params: dict | None = None,
              zaman_asimi: float = 600, ham: bool = False):
        url = f"http://127.0.0.1:{self.port}{yol}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        veri = json.dumps(govde or {}).encode("utf-8") if yontem == "POST" else None
        r = urllib.request.Request(url, data=veri, method=yontem, headers={
            "X-Asistan-Anahtar": self.anahtar, "Content-Type": "application/json", "Host": f"127.0.0.1:{self.port}"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # yerel istek vekile gitmesin
        try:
            with opener.open(r, timeout=zaman_asimi) as y:
                b = y.read()
                if ham:
                    return b, y.headers
                return json.loads(b.decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                return {"hata": f"HTTP {e.code}"}

    def kapat(self):
        if self._srv:
            self._srv.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Çıktı biçimleri / Output
# ─────────────────────────────────────────────────────────────────────────────
JSON_CIKTI = False


def yaz(veri, baslik: str = ""):
    """--json verilirse ham JSON; değilse okunur tablo/özet. EN: pretty or raw JSON output."""
    if JSON_CIKTI:
        print(json.dumps(veri, ensure_ascii=False, indent=2, default=str))
        return
    if baslik:
        print(f"\n== {baslik} ==")
    if isinstance(veri, dict) and veri.get("hata"):
        print(f"HATA: {veri['hata']}", file=sys.stderr)
        return
    _agac(veri)


def _agac(v, girinti: int = 0, sinir: int = 200):
    bosluk = "  " * girinti
    if isinstance(v, dict):
        for k, d in v.items():
            if isinstance(d, (dict, list)) and d:
                print(f"{bosluk}{k}:")
                _agac(d, girinti + 1, sinir)
            else:
                print(f"{bosluk}{k}: {d}")
    elif isinstance(v, list):
        for i, d in enumerate(v[:sinir]):
            if isinstance(d, dict):
                ozet = " | ".join(str(d.get(k)) for k in ("tarih", "baslik", "ad", "evrak_adi", "tur", "dosya_no",
                                                         "birim", "birim_adi", "durum", "title", "dueDate")
                                  if d.get(k) not in (None, ""))
                print(f"{bosluk}- {ozet or json.dumps(d, ensure_ascii=False, default=str)[:200]}")
            else:
                print(f"{bosluk}- {d}")
        if len(v) > sinir:
            print(f"{bosluk}… (+{len(v) - sinir} kayıt; tümü için --json)")
    else:
        print(f"{bosluk}{v}")


def _kv(parcalar: list[str]) -> dict:
    out = {}
    for p in parcalar or []:
        k, _, d = p.partition("=")
        out[k] = d
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Komutlar / Commands
# ─────────────────────────────────────────────────────────────────────────────
def k_durum(b: Baglanti, a):
    d = b.istek("GET", "/api/durum")
    if not JSON_CIKTI:
        print(f"Sunucu: {'süreç içi (geçici)' if b.gomulu else 'çalışan CanEditor'} — port {b.port}")
    yaz(d, "Genel durum")
    yaz(b.istek("GET", "/api/imza/durum"), "E-imza / Mobil İmza")
    yaz(b.istek("GET", "/api/donustur/durum"), "PDF/ODT/DOCX dönüştürücü (Java + resmî jar)")


def k_gorevler(b: Baglanti, a):
    d = b.istek("GET", "/api/gorevler", params={"satir": a.satir})
    if JSON_CIKTI:
        return yaz(d)
    for g in d.get("gorevler", []):
        durum = "ÇALIŞIYOR" if g.get("calisiyor") else ("kullanılamaz" if g.get("kullanilamaz") else
                                                         (f"bitti ({g.get('kod')})" if g.get("kod") is not None else "hazır"))
        print(f"{g.get('kimlik', ''):<18} {durum:<14} {g.get('ad', '')}"
              + (f"  [{g['kullanilamaz']}]" if g.get("kullanilamaz") else ""))


def k_gorev(b: Baglanti, a):
    """GUI'deki görevi başlatır; --izle ile günlüğü canlı akıtır (Ctrl+C görevi durdurmaz)."""
    if a.durdur:
        return yaz(b.istek("POST", f"/api/gorev/{a.ad}/durdur"))
    r = b.istek("POST", f"/api/gorev/{a.ad}")
    yaz(r, f"Görev: {a.ad}")
    if not (a.izle or b.gomulu):
        return
    # Geçici sunucuda süreç kapanınca görev de kapanır: bu yüzden bitene kadar izlenir.
    goruldu = 0
    try:
        while True:
            d = b.istek("GET", "/api/gorevler", params={"satir": 400})
            g = next((x for x in d.get("gorevler", []) if x.get("kimlik") == a.ad or x.get("ad") == a.ad), None)
            if not g:
                break
            satirlar = g.get("gunluk") or g.get("satirlar") or []
            for s in satirlar[goruldu:] if goruldu <= len(satirlar) else satirlar:
                print(s)
            goruldu = len(satirlar)
            if not g.get("calisiyor", g.get("durum") == "çalışıyor"):
                print(f"[bitti] {g.get('durum', '')}")
                break
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n(izleme bırakıldı; görev arka planda sürüyor)")


def k_evrak(b: Baglanti, a):
    if a.islem == "ara":
        p = {"q": " ".join(a.sorgu), "limit": a.limit, "offset": a.offset, "kategori": a.kategori, "durum": a.durum,
             "muvekkil": a.muvekkil, "dosya_durum": a.dosya_durum, "baslangic": a.baslangic, "bitis": a.bitis,
             "tur": a.tur, "dkey": a.dkey}
        return yaz(b.istek("GET", "/api/evrak/ara", params=p), "Evrak arama")
    if a.islem == "yeni":
        return yaz(b.istek("GET", "/api/yenilikler", params={"q": " ".join(a.sorgu), "limit": a.limit}), "Yeni evraklar")
    if a.islem == "indir":
        bayt, h = b.istek("GET", "/api/evrak/onizle", params={"skey": a.sorgu[0], "bicim": a.bicim or "pdf"}, ham=True)
        hedef = Path(a.cikti or f"{a.sorgu[0]}.{a.bicim or 'pdf'}")
        hedef.write_bytes(bayt)
        print(f"Kaydedildi: {hedef}")
        return
    if a.islem == "toplu":
        return yaz(b.istek("POST", "/api/evrak/toplu_islem", {"eylem": a.eylem, "skeys": a.sorgu}))


def k_dosya(b: Baglanti, a):
    if a.islem == "liste":
        return yaz(b.istek("GET", "/api/dosyalar", params={"q": " ".join(a.arg), "durum": a.durum,
                                                          "muvekkil": a.muvekkil, "limit": a.limit}), "Dosyalar")
    if a.islem == "detay":
        return yaz(b.istek("GET", "/api/dosya/detay", params={"dkey": a.arg[0]}))
    if a.islem == "hesaplar":
        return yaz(b.istek("GET", "/api/dosya/hesaplar", params={"q": " ".join(a.arg), "muvekkil": a.muvekkil}))
    if a.islem == "tazele":
        return yaz(b.istek("POST", "/api/dosya/tazele", {"dkey": a.arg[0]}))
    if a.islem == "muvekkiller":
        return yaz(b.istek("GET", "/api/muvekkiller"))


def k_ajanda(b: Baglanti, a):
    yaz(b.istek("GET", "/api/ajanda", params={"gun": a.gun, "baslangic": a.baslangic, "bitis": a.bitis}), "Ajanda")


def k_tebligat(b: Baglanti, a):
    if a.islem == "liste":
        return yaz(b.istek("POST", "/api/tebligat/liste", {"tazele": a.tazele}), "UETS tebligatları")
    return yaz(b.istek("POST", f"/api/tebligat/{a.islem}", {"barkod": a.barkod or ""}))


def k_pdf(b: Baglanti, a):
    """Yerel dosya/klasör → PDF (sunucuya gerek yok; GUI'deki 'PDF'e çevir' ile aynı motor)."""
    sys.path.insert(0, str(KOK / "moduller" / "evrak"))
    import donusturucu
    sonuc = donusturucu.convert_many(a.yollar)
    yaz(sonuc, "PDF dönüştürme")


def k_donustur(b: Baglanti, a):
    import jar_donustur
    for y in a.dosyalar:
        p = Path(y)
        hedef = Path(a.cikti) if a.cikti and len(a.dosyalar) == 1 else p.with_suffix("." + a.bicim)
        if p.suffix.lower() == ".udf":
            r = jar_donustur.udf_jar_donustur(p, a.bicim, hedef)
        else:
            out, ad, _ = jar_donustur.bayttan_donustur(p.name, p.read_bytes(), a.bicim)
            hedef.write_bytes(out)
            r = hedef
        print(f"{p} → {r}")


def k_a4(b: Baglanti, a):
    yaz(b.istek("POST", "/api/a4", {"dosyalar": [str(Path(x).resolve()) for x in a.dosyalar],
                                     "cikti": str(Path(a.cikti).resolve()) if a.cikti else None}), "A4 PDF")


def k_imza(b: Baglanti, a):
    if a.islem == "durum":
        return yaz(b.istek("GET", "/api/imza/durum"), "E-imza durumu")
    for y in a.dosyalar:
        p = Path(y).resolve()
        govde = {"udf": str(p), "dosya": str(p), "yontem": a.yontem}
        if a.pin:
            govde["pin"] = a.pin
        if a.islem == "imzala":
            yaz(b.istek("POST", "/api/imza/imzala", govde, zaman_asimi=900), f"İmzala: {p.name}")
        else:
            yaz(b.istek("POST", "/api/imza/dogrula", govde), f"Doğrula: {p.name}")


def k_uyap(b: Baglanti, a):
    if a.islem == "durum":
        return yaz(b.istek("GET", "/api/uyap"), "UYAP oturumu")
    if a.islem == "giris":
        a.ad, a.izle, a.durdur = "evrak-giris", True, False
        return k_gorev(b, a)
    if a.islem == "simdi":
        return yaz(b.istek("POST", "/api/uyap/simdi", {}))
    if a.islem == "canli":
        return yaz(b.istek("GET", "/api/baglanti/canli", params={"yenile": "1"}), "Canlı bağlantılar")


def k_uets(b: Baglanti, a):
    if a.islem == "otp":
        return yaz(b.istek("POST", "/api/uets/otp", {"kod": a.kod}))
    a.ad = {"senkron": "uets-senkron", "cevrimdisi": "uets-cevrimdisi", "otokontrol": "uets-otokontrol"}[a.islem]
    a.izle, a.durdur = True, False
    return k_gorev(b, a)


def k_ticktick(b: Baglanti, a):
    if a.islem == "gorevler":
        return yaz(b.istek("GET", "/api/ticktick/gorevler", params={"limit": a.limit}), "TickTick")
    if a.islem in ("denetle", "duzenle"):
        # Doğrudan modül: tamamlanan + "yapılmayacak" görevler de mükerrer/eksik hesabına katılır
        sys.path.insert(0, str(KOK / "moduller" / "avukatasistan"))
        os.chdir(KOK / "moduller" / "avukatasistan")
        import ticktick_duzen
        arg = ["--uygula"] if a.islem == "duzenle" else []
        if JSON_CIKTI:
            arg.append("--json")
        return ticktick_duzen.main(arg)
    if a.islem == "ekle":
        return yaz(b.istek("POST", "/api/ticktick/ekle", {"baslik": a.baslik, "icerik": a.icerik or "",
                                                           "son_tarih": a.son_tarih or "", "mahkeme": a.mahkeme or ""}))


def k_drive(b: Baglanti, a):
    if a.islem == "durum":
        return yaz(b.istek("GET", "/api/drive/esitle_durum"))
    if a.islem == "esitle":
        return yaz(b.istek("POST", "/api/drive/esitle", {"limit": a.limit}))
    if a.islem == "ara":
        return yaz(b.istek("GET", "/api/drive/ara", params={"q": " ".join(a.sorgu), "limit": a.limit}))
    if a.islem == "indeksle":
        return yaz(b.istek("POST", "/api/drive/indeksle", {}))
    if a.islem == "kopya-temizle":
        return yaz(b.istek("POST", "/api/drive/kopya_temizle", {}))


def k_hayfa(b: Baglanti, a):
    q = " ".join(a.sorgu)
    yol = {"haber": ("/api/hayfa/haberler", {"q": q}), "karar": ("/api/hayfa/kararlar", {"q": q, "alan": a.alan}),
           "mevzuat": ("/api/hayfa/mevzuat", {"q": q, "yer": "madde" if a.madde else ""}),
           "resmi-gazete": ("/api/hayfa/resmi-gazete", {"tarih": q}),
           "adliye": ("/api/hayfa/adliyeler", {"q": q, "il": a.il})}[a.islem]
    yaz(b.istek("GET", yol[0], params=yol[1]), f"HAYFA {a.islem}")


def k_icra(b: Baglanti, a):
    yaz(b.istek("GET", "/api/icra/analiz"), "İcra analizi")


def k_denetim(b: Baglanti, a):
    yaz(b.istek("POST", "/api/denetim", {}) if a.calistir else b.istek("GET", "/api/denetim"), "Denetim")


def k_oz_denetim(b: Baglanti, a):
    import oz_denetim
    rapor = oz_denetim.tam_denetim(onar=not a.salt_oku, baglanti=b)
    yaz(rapor, "Öz-denetim (test + onarım)")
    return 0 if rapor.get("ozet", {}).get("hata", 0) == 0 else 1


def k_log(b: Baglanti, a):
    import oz_denetim
    for s in oz_denetim.son_kayitlar(a.satir, a.kaynak):
        print(s)
    if a.izle:
        try:
            for s in oz_denetim.izle(a.kaynak):
                print(s, flush=True)
        except KeyboardInterrupt:
            pass


def k_yedek(b: Baglanti, a):
    if a.islem == "durum":
        return yaz(b.istek("GET", "/api/ayar/yedek"))
    if a.islem == "simdi":
        return yaz(b.istek("POST", "/api/ayar/yedek/simdi", {"sifre": a.sifre or ""}))


def k_api(b: Baglanti, a):
    """Gelişmiş: herhangi bir uç noktayı doğrudan çağır. GET'te k=v parametre, POST'ta k=v gövde alanı."""
    kv = _kv(a.parametreler)
    if a.yontem.upper() == "GET":
        yaz(b.istek("GET", a.yol, params=kv))
    else:
        govde = json.loads(a.govde) if a.govde else kv
        yaz(b.istek("POST", a.yol, govde))


def k_sunucu(b, a):
    import sunucu
    return sunucu.main(["--port", str(a.port)])


def k_sure(b, a):
    """Tebliğ tarihinden yasal süre hesabı (UETS asistanının kuralı; arayüzdeki 'Süre hesabı' ile aynı)."""
    sys.path.insert(0, str(KOK / "moduller" / "avukatasistan"))
    import datetime as dt
    import utils
    t = dt.datetime.strptime(a.teblig, "%d.%m.%Y") if "." in a.teblig else dt.datetime.fromisoformat(a.teblig)
    yaz(utils.calculate_deadlines(t, a.merci or "", a.tur or ""), "Süre hesabı")


# ─────────────────────────────────────────────────────────────────────────────
def ayrıştırıcı() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="caneditor", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="Ham JSON çıktısı (betiklerde kullanmak için)")
    ap.add_argument("--port", type=int, default=None, help="Çalışan sunucu portu (varsayılan 8765)")
    ap.add_argument("--yerel", action="store_true", help="Çalışan sunucuya bağlanma; süreç içi geçici sunucu kullan")
    alt = ap.add_subparsers(dest="komut", metavar="KOMUT")

    def ekle(ad, fn, yardim, sunucusuz=False):
        p = alt.add_parser(ad, help=yardim, description=yardim)
        p.set_defaults(fn=fn, sunucusuz=sunucusuz)
        return p

    ekle("durum", k_durum, "Genel durum: sunucu, UYAP/UETS oturumu, e-imza, dönüştürücü")
    p = ekle("gorevler", k_gorevler, "Arayüzdeki tüm arka plan görevlerini ve durumlarını listele")
    p.add_argument("--satir", type=int, default=5)
    p = ekle("gorev", k_gorev, "Bir görevi başlat/durdur (ör. evrak-nobetci, uets-senkron, ticktick-duzen)")
    p.add_argument("ad"); p.add_argument("--izle", action="store_true"); p.add_argument("--durdur", action="store_true")

    p = ekle("evrak", k_evrak, "UYAP evrak kataloğu: ara | yeni | indir | toplu")
    p.add_argument("islem", choices=["ara", "yeni", "indir", "toplu"]); p.add_argument("sorgu", nargs="*")
    for o in ("kategori", "durum", "muvekkil", "dosya-durum", "baslangic", "bitis", "tur", "dkey", "bicim", "cikti", "eylem"):
        p.add_argument("--" + o, dest=o.replace("-", "_"), default="")
    p.add_argument("--limit", type=int, default=100); p.add_argument("--offset", type=int, default=0)

    p = ekle("dosya", k_dosya, "Dava/icra dosyaları: liste | detay DKEY | hesaplar | tazele DKEY | muvekkiller")
    p.add_argument("islem", choices=["liste", "detay", "hesaplar", "tazele", "muvekkiller"]); p.add_argument("arg", nargs="*")
    p.add_argument("--durum", default=""); p.add_argument("--muvekkil", default=""); p.add_argument("--limit", type=int, default=150)

    p = ekle("ajanda", k_ajanda, "Duruşma + tebligat süreleri ajandası")
    p.add_argument("--gun", type=int, default=60); p.add_argument("--baslangic", default=""); p.add_argument("--bitis", default="")

    p = ekle("tebligat", k_tebligat, "UETS tebligat paneli: liste | indir | isle | ... (barkod ile)")
    p.add_argument("islem"); p.add_argument("--barkod", default=""); p.add_argument("--tazele", action="store_true")

    p = ekle("pdf", k_pdf, "Dosya/klasördeki UDF, TIFF, görüntü ve Office belgelerini PDF'e çevir (yerel)", True)
    p.add_argument("yollar", nargs="+")
    p = ekle("donustur", k_donustur, "UDF → pdf/odt/docx (resmî Havelsan motoru); görüntü/TIFF → A4 PDF", True)
    p.add_argument("dosyalar", nargs="+"); p.add_argument("--bicim", default="pdf", choices=["pdf", "odt", "docx"])
    p.add_argument("-o", "--cikti", default="")
    p = ekle("a4", k_a4, "Birden çok dosyayı tek UYAP uyumlu A4 PDF'te birleştir (NAPS2 yöntemi)")
    p.add_argument("dosyalar", nargs="+"); p.add_argument("-o", "--cikti", default="")

    for ad, yardim in (("imzala", "UDF/PDF imzala: takılı kart → sessiz e-imza, yoksa Mobil İmza (arka planda)"),
                       ("dogrula", "İmzalı belgeyi doğrula")):
        p = ekle(ad, k_imza, yardim)
        p.set_defaults(islem=ad)
        p.add_argument("dosyalar", nargs="+"); p.add_argument("--yontem", default="oto", choices=["oto", "eimza", "mobil"])
        p.add_argument("--pin", default=os.environ.get("CANEDITOR_PIN", ""), help="(ya da CANEDITOR_PIN ortam değişkeni)")
    p = ekle("imza", k_imza, "E-imza / Mobil İmza durumu")
    p.set_defaults(islem="durum", dosyalar=[], yontem="oto", pin="")

    p = ekle("uyap", k_uyap, "UYAP oturumu: durum | giris (e-imza, olmazsa Mobil İmza) | simdi | canli")
    p.add_argument("islem", choices=["durum", "giris", "simdi", "canli"])
    p = ekle("uets", k_uets, "UETS: senkron | cevrimdisi | otokontrol | otp KOD")
    p.add_argument("islem", choices=["senkron", "cevrimdisi", "otokontrol", "otp"]); p.add_argument("kod", nargs="?", default="")

    p = ekle("ticktick", k_ticktick, "TickTick: gorevler | denetle | duzenle | ekle")
    p.add_argument("islem", choices=["gorevler", "denetle", "duzenle", "ekle"]); p.add_argument("--limit", type=int, default=80)
    p.add_argument("--baslik", default=""); p.add_argument("--icerik", default=""); p.add_argument("--son-tarih", dest="son_tarih", default="")
    p.add_argument("--mahkeme", default="")

    p = ekle("drive", k_drive, "Google Drive arşivi: durum | esitle | ara | indeksle | kopya-temizle")
    p.add_argument("islem", choices=["durum", "esitle", "ara", "indeksle", "kopya-temizle"]); p.add_argument("sorgu", nargs="*")
    p.add_argument("--limit", type=int, default=100000)

    p = ekle("hayfa", k_hayfa, "hayfahukuk.com: haber | karar | mevzuat | resmi-gazete | adliye")
    p.add_argument("islem", choices=["haber", "karar", "mevzuat", "resmi-gazete", "adliye"]); p.add_argument("sorgu", nargs="*")
    p.add_argument("--alan", default=""); p.add_argument("--il", default=""); p.add_argument("--madde", action="store_true",
                                                                                          help="Mevzuatta madde METNİ içinde ara")

    ekle("icra", k_icra, "İcra dosyaları kesinleşme / takipsizlik analizi")
    p = ekle("denetim", k_denetim, "Katalog/defter bütünlük denetimi (--calistir ile yeniden çalıştır)")
    p.add_argument("--calistir", action="store_true")
    p = ekle("oz-denetim", k_oz_denetim, "Kendi kendini test et, tutarsızlıkları onar ve günlüğe yaz")
    p.add_argument("--salt-oku", action="store_true", help="Yalnız raporla, onarma")
    p = ekle("log", k_log, "Birleşik günlük (tüm modüller); -f ile canlı izle", True)
    p.add_argument("--satir", type=int, default=80); p.add_argument("--kaynak", default=""); p.add_argument("-f", "--izle", action="store_true")
    p = ekle("yedek", k_yedek, "Şifreli ayar yedeği: durum | simdi")
    p.add_argument("islem", choices=["durum", "simdi"]); p.add_argument("--sifre", default="")
    p = ekle("sure", k_sure, "Tebliğ tarihinden yasal süre hesabı", True)
    p.add_argument("teblig", help="GG.AA.YYYY ya da YYYY-AA-GG"); p.add_argument("--merci", default=""); p.add_argument("--tur", default="")
    p = ekle("api", k_api, "Gelişmiş: herhangi bir /api uç noktasını çağır")
    p.add_argument("yontem", choices=["GET", "POST", "get", "post"]); p.add_argument("yol"); p.add_argument("parametreler", nargs="*")
    p.add_argument("--govde", default="", help="POST için ham JSON gövde")
    p = ekle("sunucu", k_sunucu, "Hukuk Asistanı sunucusunu ön planda başlat (GUI eşleştirmesi için)", True)
    p.add_argument("--port", type=int, default=VARSAYILAN_PORT)
    return ap


def main(argv=None) -> int:
    global JSON_CIKTI
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = ayrıştırıcı()
    a = ap.parse_args(argv)
    JSON_CIKTI = a.json
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    try:
        import oz_denetim
        oz_denetim.kaydet("cli", "caneditor " + " ".join(sys.argv[1:] if argv is None else argv))
    except Exception:
        pass
    b = None if a.sunucusuz else Baglanti(a.port, a.yerel)
    try:
        r = a.fn(b, a)
        return r if isinstance(r, int) else 0
    finally:
        if b:
            b.kapat()


if __name__ == "__main__":
    sys.exit(main())
