#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CanEditor Hukuk Asistanı — birleşik yerel arka uç (masaüstü + Termux).

CanEditor arayüzü (Tauri masaüstü, Android WebView, taşınabilir web) bu sunucuyla
http://127.0.0.1:<port> üzerinden konuşur. Sunucu, depoya birleştirilen modülleri tek
çatı altında sunar:

  moduller/avukatasistan  UETS e-tebligat → süre → TickTick/Notion/Telegram, dosya defteri
  moduller/evrak          UYAP Avukat Portal evrak kataloğu, indirme, PDF dönüştürme
  moduller/a4             NAPS2 yöntemli A4 PDF motoru (görsel/PDF/UDF → tek A4 PDF)

Yalnızca Python standart kütüphanesi kullanılır; modüllerin kendi bağımlılıkları
(selenium, sqlalchemy, Pillow…) yalnızca o modülün görevi başlatılırken gerekir.

Güvenlik
  * Yalnızca 127.0.0.1'e bağlanır; Host başlığı localhost/127.0.0.1 değilse reddedilir
    (DNS rebinding koruması).
  * Her /api isteğinde X-Asistan-Anahtar başlığı zorunludur. Anahtar ilk açılışta
    üretilir: <veri>/anahtar (izin 600). Özel başlık, başka sitelerin tarayıcı üzerinden
    istek atmasını CORS ön kontrolüyle engeller; CORS yalnızca CanEditor kökenlerine açıktır.
  * Görevler sabit bir izin listesinden başlatılır; istemci komut satırı gönderemez.
  * /api/evrak/dosya yalnızca katalogda kayıtlı (indirilmiş) dosyaları verir.

Kullanım
  python3 asistan/sunucu.py                # varsayılan port 8765
  python3 asistan/sunucu.py --port 9000
  python3 asistan/sunucu.py --anahtar      # eşleştirme anahtarını yazdır ve çık
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import runpy
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SURUM = "1.0.0"
KOK = Path(__file__).resolve().parent
# Pakete gömülü (PyInstaller) ikili: Python kurulu olmadan çalışır. Modül kodu paketin içinde salt okunurdur;
# modüller verilerini kendi klasörlerine yazdığı için ilk açılışta kullanıcı veri dizinine eşitlenir.
DONDURULMUS = bool(getattr(sys, "frozen", False))
PAKET_MODULLER = (Path(getattr(sys, "_MEIPASS", KOK)) / "moduller") if DONDURULMUS else KOK / "moduller"

VARSAYILAN_PORT = 8765
IZINLI_KOKENLER = {
    "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost",
    "null",  # file:// (taşınabilir web) ve Android file:///android_asset
}


def veri_dizini() -> Path:
    """Sunucunun kendi verisi (anahtar, görev günlükleri)."""
    d = os.environ.get("CANASISTAN_VERI")
    if d:
        p = Path(d)
    elif os.name == "nt":
        p = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "CanEditor" / "asistan"
    else:
        p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "caneditor" / "asistan"
    p.mkdir(parents=True, exist_ok=True)
    return p


# Eşitlemede kullanıcının değiştirmiş olabileceği yapılandırma/veri dosyalarının üzerine yazılmaz
KORUNAN_UZANTILAR = {".env", ".db", ".sqlite", ".sqlite3", ".ini", ".json"}


def _paket_damgasi(kok: Path) -> str:
    h = hashlib.sha256(SURUM.encode())
    for f in sorted(kok.rglob("*")):
        if f.is_file():
            h.update(f"{f.relative_to(kok).as_posix()}:{f.stat().st_size}".encode())
    return h.hexdigest()[:16]


def moduller_hazirla(kaynak: Path | None = None, hedef: Path | None = None) -> Path:
    """Gömülü pakette modül kodunu yazılabilir veri dizinine eşitler (sürüm değişince günceller)."""
    if not DONDURULMUS and kaynak is None:
        return PAKET_MODULLER
    kaynak = kaynak or PAKET_MODULLER
    hedef = hedef or (veri_dizini() / "moduller")
    damga_dosyasi = hedef / ".paket_damgasi"
    damga = _paket_damgasi(kaynak)
    try:
        if damga_dosyasi.read_text(encoding="utf-8").strip() == damga:
            return hedef
    except OSError:
        pass
    for f in kaynak.rglob("*"):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        d = hedef / f.relative_to(kaynak)
        if d.exists() and d.suffix.lower() in KORUNAN_UZANTILAR:
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        if os.name != "nt" and os.access(f, os.X_OK):
            d.chmod(d.stat().st_mode | 0o111)
    damga_dosyasi.write_text(damga + "\n", encoding="utf-8")
    return hedef


def anahtar_al() -> str:
    env = os.environ.get("CANASISTAN_ANAHTAR", "").strip()
    if env:
        return env
    yol = veri_dizini() / "anahtar"
    try:
        k = yol.read_text(encoding="utf-8").strip()
        if k:
            return k
    except OSError:
        pass
    k = secrets.token_urlsafe(24)
    yol.write_text(k + "\n", encoding="utf-8")
    try:
        os.chmod(yol, 0o600)
    except OSError:
        pass
    return k


MODULLER = moduller_hazirla()
AVUKAT_DIR = MODULLER / "avukatasistan"
EVRAK_DIR = MODULLER / "evrak"
A4_DIR = MODULLER / "a4"


# ---------------------------------------------------------------------------
# Veri kaynakları (salt okunur)
# ---------------------------------------------------------------------------

def katalog_yolu() -> Path:
    """UYAP evrak kataloğu: modülle aynı kural (UYAP_VERI_DIZINI > modül dizini)."""
    return Path(os.environ.get("UYAP_VERI_DIZINI") or EVRAK_DIR) / "uyap_katalog.db"


def defter_yolu() -> Path:
    """Avukat Asistanı dosya defteri: modülle aynı kural (DEFTER_URL sqlite ise o dosya)."""
    url = os.environ.get("DEFTER_URL", "")
    if url.startswith("sqlite:///"):
        return Path(url[len("sqlite:///"):])
    return AVUKAT_DIR / "veri" / "defter.db"


def _ro(db: Path) -> sqlite3.Connection | None:
    if not db.is_file():
        return None
    c = sqlite3.connect(f"file:{urllib.parse.quote(str(db))}?mode=ro", uri=True, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def _satirlar(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def _tablo_var(c: sqlite3.Connection, ad: str) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE name=?", (ad,)).fetchone() is not None


def tr_kucuk(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


# Evrak kataloğunun arama sütunlarıyla (evrak_katalog.fold) birebir aynı katlama:
# Türkçe harf ve büyük/küçük farkı yok sayılır ('ÇAĞLAR' → 'caglar').
_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
    "Î": "i", "î": "i", "Û": "u", "û": "u",
})


def fold(metin) -> str:
    return re.sub(r"\s+", " ", str(metin or "").translate(_FOLD).lower()).strip()


def terimler(metin: str) -> tuple[list[str], list[str]]:
    """'ahmet -mehmet "ağır ceza"' → (['ahmet', 'agir ceza'], ['mehmet'])."""
    pos, neg = [], []
    for m in re.finditer(r'(-?)"([^"]+)"|(-?)([^\s"]+)', str(metin or "")):
        eksi = (m.group(1) or m.group(3) or "") == "-"
        t = fold(m.group(2) or m.group(4) or "")
        if t and t != "-":
            (neg if eksi else pos).append(t)
    return pos[:8], neg[:8]


def evrak_ara(q: str, limit: int = 100) -> dict:
    c = _ro(katalog_yolu())
    if c is None:
        return {"hazir": False, "sonuclar": [], "mesaj": "Evrak kataloğu henüz oluşturulmadı. Önce 'UYAP evrak tarama' görevini çalıştırın."}
    with c:
        kolonlar = "e.skey, e.tur, e.aciklama, e.tarih, e.kategori, e.durum, e.uzanti, e.pdf_path IS NOT NULL OR e.path IS NOT NULL AS yerel, d.birim, d.dosya_no, d.muvekkil"
        kosul, param = [], []
        pos, neg = terimler(q)
        for t in pos:
            kosul.append("(COALESCE(e.ara,'') LIKE ? OR COALESCE(d.taraf_ara,'') LIKE ? OR COALESCE(d.dosya_no,'') LIKE ?)")
            param += [f"%{t}%"] * 3
        for t in neg:
            kosul.append("NOT (COALESCE(e.ara,'') LIKE ? OR COALESCE(d.taraf_ara,'') LIKE ?)")
            param += [f"%{t}%"] * 2
        where = ("WHERE " + " AND ".join(kosul)) if kosul else ""
        sql = f"SELECT {kolonlar} FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey {where} ORDER BY e.tarih DESC LIMIT ?"
        rows = _satirlar(c.execute(sql, (*param, max(1, min(limit, 500)))))
        toplam = c.execute("SELECT COUNT(*) FROM evrak").fetchone()[0]
    return {"hazir": True, "toplam_evrak": toplam, "sonuclar": rows}


def evrak_dosya_yolu(skey: str) -> Path | None:
    """Yalnızca katalogda kayıtlı ve diskte bulunan dosya döner (yol istemciden alınmaz)."""
    c = _ro(katalog_yolu())
    if c is None:
        return None
    with c:
        r = c.execute("SELECT pdf_path, path FROM evrak WHERE skey=?", (skey,)).fetchone()
    if not r:
        return None
    for aday in (r["pdf_path"], r["path"]):
        if aday:
            p = Path(aday)
            if not p.is_absolute():
                p = katalog_yolu().parent / p
            if p.is_file():
                return p
    return None


def ajanda(gun: int = 60) -> dict:
    """Yaklaşan duruşmalar ve tebligat son günleri — iki modülün verisi birleştirilir."""
    bugun = time.strftime("%Y-%m-%d")
    sinir = time.strftime("%Y-%m-%d", time.localtime(time.time() + gun * 86400))
    olaylar: list[dict] = []

    d = _ro(defter_yolu())
    if d is not None:
        with d:
            if _tablo_var(d, "tebligatlar"):
                for r in d.execute("SELECT birim, esas, konu, son_gun, barkod FROM tebligatlar WHERE son_gun IS NOT NULL"):
                    iso = _tr_tarih_iso(r["son_gun"])
                    if iso and bugun <= iso <= sinir:
                        olaylar.append({"tur": "sure", "tarih": iso, "saat": "17:00", "birim": r["birim"], "esas": r["esas"],
                                        "baslik": r["konu"] or "Tebligat son günü", "kaynak": "UETS", "barkod": r["barkod"]})
            if _tablo_var(d, "durusmalar"):
                for r in d.execute("SELECT birim, esas, baslangic, baslik, yer FROM durusmalar WHERE COALESCE(iptal,0)=0"):
                    ts = str(r["baslangic"] or "")
                    if bugun <= ts[:10] <= sinir:
                        olaylar.append({"tur": "durusma", "tarih": ts[:10], "saat": ts[11:16], "birim": r["birim"], "esas": r["esas"],
                                        "baslik": r["baslik"] or "Duruşma", "yer": r["yer"], "kaynak": "Takvim"})

    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            if _tablo_var(k, "durusma"):
                for r in k.execute("SELECT birim, dosya_no, tarih, saat, yer, aciklama FROM durusma WHERE durum != 'iptal'"):
                    iso = _tr_tarih_iso(r["tarih"])
                    if iso and bugun <= iso <= sinir:
                        olaylar.append({"tur": "durusma", "tarih": iso, "saat": r["saat"] or "", "birim": r["birim"], "esas": r["dosya_no"],
                                        "baslik": r["aciklama"] or "Duruşma", "yer": r["yer"], "kaynak": "UYAP"})

    # Aynı duruşma iki kaynakta da olabilir: birim+esas+tarih+saat ile tekilleştir
    gorulen, tekil = set(), []
    for o in sorted(olaylar, key=lambda o: (o["tarih"], o.get("saat") or "")):
        anahtar = (o["tur"], tr_kucuk(o.get("esas") or ""), o["tarih"], o.get("saat") or "")
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            tekil.append(o)
    return {"olaylar": tekil, "kaynaklar": {"defter": defter_yolu().is_file(), "katalog": katalog_yolu().is_file()}}


def evrak_veri_dizini() -> Path:
    return Path(os.environ.get("UYAP_VERI_DIZINI") or EVRAK_DIR)


def yenilikler(sonra: str = "", limit: int = 30) -> dict:
    """'sonra' anından (ISO) beri düşen yeni evrak / tebligatlar — Asistan rozeti ve bildirimleri için."""
    if not sonra:
        sonra = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 86400))
    sonra = sonra[:19]
    sonuc = {"sonra": sonra, "evrak_sayisi": 0, "evraklar": [], "tebligat_sayisi": 0, "tebligatlar": [], "en_yeni": sonra}
    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            sonuc["evrak_sayisi"] = k.execute("SELECT COUNT(*) FROM evrak WHERE ilk_gorulme > ? AND COALESCE(is_ek,0)=0",
                                              (sonra,)).fetchone()[0]
            sonuc["evraklar"] = _satirlar(k.execute(
                """SELECT e.skey, e.tur, e.aciklama, e.tarih, e.ilk_gorulme, e.durum,
                          (e.pdf_path IS NOT NULL OR e.path IS NOT NULL) AS yerel, d.birim, d.dosya_no, d.muvekkil
                   FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey
                   WHERE e.ilk_gorulme > ? AND COALESCE(e.is_ek,0)=0 ORDER BY e.ilk_gorulme DESC LIMIT ?""",
                (sonra, max(1, min(limit, 200)))))
            if sonuc["evraklar"]:
                sonuc["en_yeni"] = max(sonuc["en_yeni"], sonuc["evraklar"][0]["ilk_gorulme"] or "")
            if _tablo_var(k, "tebligat"):
                for r in k.execute("SELECT birim, dosya_no, tebligat_turu, evrak_adi, eklenme FROM tebligat WHERE eklenme > ? "
                                   "ORDER BY eklenme DESC LIMIT ?", (sonra, limit)):
                    sonuc["tebligatlar"].append({"kaynak": "UYAP", "birim": r["birim"], "esas": r["dosya_no"],
                                                 "baslik": r["evrak_adi"] or r["tebligat_turu"], "zaman": r["eklenme"]})
    d = _ro(defter_yolu())
    if d is not None:
        with d:
            if _tablo_var(d, "tebligatlar"):
                # SQLAlchemy DateTime "YYYY-MM-DD HH:MM:SS" yazar
                for r in d.execute("SELECT birim, esas, konu, son_gun, kayit FROM tebligatlar WHERE kayit > ? "
                                   "ORDER BY kayit DESC LIMIT ?", (sonra.replace("T", " "), limit)):
                    sonuc["tebligatlar"].append({"kaynak": "UETS", "birim": r["birim"], "esas": r["esas"],
                                                 "baslik": r["konu"], "son_gun": r["son_gun"],
                                                 "zaman": str(r["kayit"] or "").replace(" ", "T")})
    sonuc["tebligat_sayisi"] = len(sonuc["tebligatlar"])
    for t in sonuc["tebligatlar"]:
        if (t.get("zaman") or "") > sonuc["en_yeni"]:
            sonuc["en_yeni"] = t["zaman"][:19]
    return sonuc


def _klasor_ozeti(kok: Path, sure_s: float = 2.0, en_cok: int = 50000) -> dict:
    """Drive klasörünü zaman sınırıyla tarar (büyük arşivde arayüz beklemesin)."""
    sayi, boyut, son = 0, 0, 0.0
    bas, yigin, tam = time.monotonic(), [kok], True
    while yigin:
        if time.monotonic() - bas > sure_s or sayi >= en_cok:
            tam = False
            break
        try:
            with os.scandir(yigin.pop()) as it:
                for g in it:
                    if g.is_dir(follow_symlinks=False):
                        yigin.append(g.path)
                    elif g.is_file(follow_symlinks=False):
                        st = g.stat()
                        sayi, boyut, son = sayi + 1, boyut + st.st_size, max(son, st.st_mtime)
        except OSError:
            continue
    return {"dosya": sayi, "boyut_mb": round(boyut / 1_048_576, 1), "tam_sayim": tam,
            "son_degisiklik": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(son)) if son else None}


def drive_durumu() -> dict:
    """Google Drive eşitlemesinin durumu: yapılandırma, klasör, katalog yedeği, nöbetçinin son turu."""
    vd = evrak_veri_dizini()
    try:
        cfg = json.loads((vd / "watcher_config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    try:
        nobet = json.loads((vd / "watcher_durum.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        nobet = None
    dizin = str(cfg.get("google_drive_dir") or "")
    sonuc = {"yapilandirildi": bool(dizin or cfg.get("google_drive_webhook")),
             "mod": "yerel" if dizin else ("webhook" if cfg.get("google_drive_webhook") else "yok"),
             "dizin": dizin, "dizin_var": False, "yazilabilir": False, "klasor": None, "yedek": None,
             "katalog": None, "nobetci": None, "uyarilar": []}
    if dizin:
        p = Path(dizin)
        sonuc["dizin_var"] = p.is_dir()
        if p.is_dir():
            sonuc["yazilabilir"] = os.access(p, os.W_OK)
            sonuc["klasor"] = _klasor_ozeti(p)
            y = p / "uyap_katalog_yedek.db"
            if y.is_file():
                sonuc["yedek"] = {"zaman": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(y.stat().st_mtime)),
                                  "boyut_mb": round(y.stat().st_size / 1_048_576, 1)}
        else:
            sonuc["uyarilar"].append("Drive klasörü bulunamadı: Google Drive masaüstü uygulaması açık ve oturumu açık mı?")
    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            ind = k.execute("SELECT COUNT(*) FROM evrak WHERE durum='indirildi'").fetchone()[0]
            bekleyen = k.execute("SELECT COUNT(*) FROM evrak WHERE durum='yeni' AND COALESCE(is_ek,0)=0").fetchone()[0]
            drivede = None
            if dizin:
                onek = dizin.rstrip("/\\")
                drivede = k.execute("SELECT COUNT(*) FROM evrak WHERE durum='indirildi' AND (path LIKE ? OR pdf_path LIKE ?)",
                                    (onek + "%", onek + "%")).fetchone()[0]
            sonuc["katalog"] = {"indirilen": ind, "indirilmeyi_bekleyen": bekleyen, "drivede": drivede,
                                "driveda_olmayan": (ind - drivede) if drivede is not None else None}
    if nobet:
        yas_dk = None
        try:
            yas_dk = round((time.time() - time.mktime(time.strptime(nobet["bitis"][:19], "%Y-%m-%dT%H:%M:%S"))) / 60)
        except (KeyError, ValueError, OverflowError):
            pass
        aralik = int(nobet.get("sonraki_dk") or 15)
        sonuc["nobetci"] = {"son_tur": nobet.get("bitis"), "dakika_once": yas_dk, "aralik_dk": aralik,
                            "istatistik": nobet.get("istatistik") or {},
                            "gecikti": yas_dk is not None and yas_dk > 3 * aralik}
        if sonuc["nobetci"]["gecikti"]:
            sonuc["uyarilar"].append(f"Nöbetçi {yas_dk} dakikadır tarama yapmadı (aralık {aralik} dk): çalışıyor mu?")
    elif sonuc["yapilandirildi"]:
        sonuc["uyarilar"].append("Nöbetçi henüz hiç tur tamamlamadı.")
    return sonuc


def _tr_tarih_iso(s) -> str | None:
    """'GG.AA.YYYY', 'GG/AA/YYYY' veya 'YYYY-AA-GG…' → 'YYYY-AA-GG'."""
    s = str(s or "").strip()
    if len(s) >= 10 and s[4] == "-":
        return s[:10]
    parca = s.replace("/", ".").split(".")
    if len(parca) >= 3 and all(p[:4].isdigit() for p in parca[:3]):
        g, a, y = parca[0], parca[1], parca[2][:4]
        if len(y) == 4:
            return f"{y}-{int(a):02d}-{int(g):02d}"
    return None


# ---------------------------------------------------------------------------
# Görevler (izin listesi)
# ---------------------------------------------------------------------------

# Gömülü pakette görevler aynı ikiliyle çalışır: "<ikili> --calistir betik.py ..." (Python kurulumu gerekmez)
PY = [sys.executable, "--calistir"] if DONDURULMUS else [sys.executable or "python3"]
# Android (Termux'suz): Python, APK'daki glibc yükleyicisiyle başlatılır; alt görevler de aynı önekle çalışmalı
if os.environ.get("CANASISTAN_PYTHON_KOMUT"):
    try:
        PY = [str(x) for x in json.loads(os.environ["CANASISTAN_PYTHON_KOMUT"])]
    except (ValueError, TypeError):
        pass
ANDROID = os.environ.get("CANASISTAN_ANDROID") == "1"
GOREVLER: dict[str, dict] = {
    "uets-senkron":     {"ad": "UETS tebligatlarını indir ve işle", "cwd": AVUKAT_DIR, "cmd": [*PY, "main.py", "--headless"], "tarayici": True},
    "uets-cevrimdisi":  {"ad": "UETS: yerel CSV/arşivle işle (portala bağlanmadan)", "cwd": AVUKAT_DIR, "cmd": [*PY, "main.py", "--offline"]},
    "uets-otokontrol":  {"ad": "Tebligat otokontrol raporu", "cwd": AVUKAT_DIR, "cmd": [*PY, "main.py", "--autocontrol", "--offline"]},
    "asistan-gui":      {"ad": "Avukat Asistanı penceresi", "cwd": AVUKAT_DIR, "cmd": [*PY, "avukat_gui.py"], "pencere": True},
    "evrak-katalog":    {"ad": "UYAP Evrak Kataloğu penceresi", "cwd": EVRAK_DIR, "cmd": [*PY, "katalog_gui.py"], "pencere": True},
    "evrak-giris":      {"ad": "UYAP oturum aç (e-imza)", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "login"], "tarayici": True},
    "evrak-islemlerim": {"ad": "UYAP: İşlemlerim evraklarını indir", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "islemlerim"], "tarayici": True},
    "evrak-tebligat":   {"ad": "UYAP: tebligat evraklarını indir", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", "tebligat", "--scope", "all"], "tarayici": True},
    "evrak-durusmalar": {"ad": "UYAP: duruşma listesini çek", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "durusmalar"], "tarayici": True},
    "evrak-nobetci":    {"ad": "UYAP nöbetçi: tek tarama turu", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_watcher.py", "--once"], "tarayici": True},
}


def gorev_ortami() -> dict:
    """Görev alt süreçlerinin ortamı: gömülü Java ve indirilmiş resmî UYAP Editör jar'ları modüllere tanıtılır."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    _ld_geri_yukle(env)
    jh = os.environ.get("CANASISTAN_JAVA_HOME")
    if jh and (Path(jh) / "bin").is_dir():
        env["JAVA_HOME"] = jh
        env["PATH"] = str(Path(jh) / "bin") + os.pathsep + env.get("PATH", "")
    # Gömülü tarayıcı (Chrome for Testing — chrome-headless-shell + chromedriver): kullanıcı Chrome kurmaz.
    # Modüllerin kendi değişken adlarıyla verilir; tarayıcı HİÇBİR ZAMAN ön planda açılmaz.
    chrome, surucu = os.environ.get("CANASISTAN_CHROME"), os.environ.get("CANASISTAN_CHROMEDRIVER")
    if chrome and Path(chrome).is_file():
        env.setdefault("UYAP_CHROME_BIN", chrome)
        env.setdefault("UETS_CHROME_BIN", chrome)
    if surucu and Path(surucu).is_file():
        env.setdefault("UETS_CHROMEDRIVER", surucu)
        env.setdefault("SE_CHROMEDRIVER", surucu)
    if env.get("CANASISTAN_GORUNMEZ", "1") != "0":
        env["CANASISTAN_GORUNMEZ"] = "1"
    else:
        env.pop("CANASISTAN_GORUNMEZ", None)
    jars = os.environ.get("CANASISTAN_UYAP_JARS")
    if jars and (Path(jars) / "editor_lib.jar").is_file() and not env.get("UYAP_JARS"):
        env["UYAP_JARS"] = jars
    return env


def _ld_geri_yukle(env) -> None:
    """PyInstaller (Linux) kendi kütüphane yolunu LD_LIBRARY_PATH'e ekler; Java/Chrome gibi dış programlar
    paketin kütüphaneleriyle çakışmasın diye özgün değer geri yüklenir."""
    if "LD_LIBRARY_PATH_ORIG" in env:
        env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
    elif DONDURULMUS:
        env.pop("LD_LIBRARY_PATH", None)


class Gorev:
    def __init__(self, kimlik: str, tanim: dict):
        self.kimlik, self.tanim = kimlik, tanim
        self.proc: subprocess.Popen | None = None
        self.baslangic = self.bitis = None
        self.kod: int | None = None
        self.gunluk: deque[str] = deque(maxlen=400)

    def kullanilamama_nedeni(self) -> str:
        """Android'de tarayıcı otomasyonu ve masaüstü pencereleri yoktur; bu görevler masaüstünde çalışır."""
        if ANDROID and self.tanim.get("tarayici"):
            return "Bu görev tarayıcı otomasyonu gerektirir; CanEditor masaüstü uygulamasında çalışır."
        if ANDROID and self.tanim.get("pencere"):
            return "Bu pencere masaüstü uygulamasında açılır."
        return ""

    def calisiyor(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def baslat(self):
        if self.calisiyor():
            raise RuntimeError("Görev zaten çalışıyor")
        neden = self.kullanilamama_nedeni()
        if neden:
            raise RuntimeError(neden)
        env = gorev_ortami()
        self.gunluk.clear()
        self.kod, self.bitis, self.baslangic = None, None, time.time()
        self.proc = subprocess.Popen(self.tanim["cmd"], cwd=str(self.tanim["cwd"]), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._oku, daemon=True).start()

    def _oku(self):
        assert self.proc and self.proc.stdout
        with self.proc.stdout:
            for satir in self.proc.stdout:
                self.gunluk.append(satir.rstrip("\n"))
        self.kod = self.proc.wait()
        self.bitis = time.time()

    def durdur(self):
        if self.calisiyor():
            self.proc.terminate()

    def ozet(self, satir: int = 40) -> dict:
        return {"kimlik": self.kimlik, "ad": self.tanim["ad"], "pencere": bool(self.tanim.get("pencere")),
                "kullanilamaz": self.kullanilamama_nedeni(),
                "calisiyor": self.calisiyor(), "baslangic": self.baslangic, "bitis": self.bitis, "kod": self.kod,
                "gunluk": list(self.gunluk)[-satir:]}


GOREV_DURUM: dict[str, Gorev] = {k: Gorev(k, v) for k, v in GOREVLER.items()}


def modul_durumu() -> dict:
    def var(*mod):
        import importlib.util
        return all(importlib.util.find_spec(m) is not None for m in mod)
    return {
        # Android'de tarayıcı otomasyonu (selenium) yoktur; tarayıcısız görevlerin bağımlılıkları denetlenir
        "avukatasistan": {"var": AVUKAT_DIR.is_dir(),
                          "bagimliliklar": var("requests", "sqlalchemy", "openpyxl", *(() if ANDROID else ("selenium",))),
                          "yapilandirildi": (AVUKAT_DIR / ".env").is_file() or bool(os.environ.get("TICKTICK_TOKEN"))},
        "evrak": {"var": EVRAK_DIR.is_dir(), "bagimliliklar": var("requests"), "katalog": katalog_yolu().is_file()},
        "a4": {"var": A4_DIR.is_dir(), "bagimliliklar": var("PIL", "reportlab", "pypdf")},
    }


def a4_birlestir(dosyalar: list[str], cikti: str | None) -> dict:
    """Yerel dosyaları NAPS2 yöntemiyle tek A4 PDF'te birleştirir (masaüstü yolları)."""
    sys.path.insert(0, str(A4_DIR / "python"))
    import a4_pdf_engine  # noqa: E402 — isteğe bağlı bağımlılıklar burada yüklenir
    yollar = [str(Path(f).expanduser()) for f in dosyalar if Path(f).expanduser().is_file()]
    if not yollar:
        raise ValueError("Geçerli dosya bulunamadı")
    if not cikti:
        cikti = str(Path(yollar[0]).with_name(Path(yollar[0]).stem + "_A4.pdf"))
    a4_pdf_engine.merge_all_to_single_pdf(yollar, cikti)
    return {"cikti": cikti, "sayfa_kaynagi": len(yollar)}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class Isleyici(BaseHTTPRequestHandler):
    server_version = f"CanAsistan/{SURUM}"
    anahtar = ""

    def log_message(self, fmt, *args):
        if os.environ.get("CANASISTAN_DEBUG"):
            super().log_message(fmt, *args)

    # --- yardımcılar ---
    def _cors(self):
        o = self.headers.get("Origin")
        if o and (o in IZINLI_KOKENLER or o.startswith("http://localhost:") or o.startswith("http://127.0.0.1:")):
            self.send_header("Access-Control-Allow-Origin", o)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Asistan-Anahtar")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, veri, kod=200):
        ham = json.dumps(veri, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(kod)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(ham)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(ham)

    def _host_gecerli(self) -> bool:
        h = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        return h in ("127.0.0.1", "localhost", "::1")

    def _yetkili(self) -> bool:
        k = self.headers.get("X-Asistan-Anahtar", "")
        return bool(k) and secrets.compare_digest(k.encode(), self.anahtar.encode())

    def _govde(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > 1_000_000:
            raise ValueError("İstek gövdesi çok büyük")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def _on_kontrol(self) -> tuple[str, dict] | None:
        if not self._host_gecerli():
            self._json({"hata": "Geçersiz Host"}, 403)
            return None
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/merhaba":  # anahtarsız: yalnızca sunucunun varlığını bildirir
            self._json({"uygulama": "CanEditor Hukuk Asistanı", "surum": SURUM})
            return None
        if not self._yetkili():
            self._json({"hata": "Anahtar gerekli", "ipucu": "python3 asistan/sunucu.py --anahtar"}, 401)
            return None
        return u.path, {k: v[-1] for k, v in urllib.parse.parse_qs(u.query).items()}

    # --- yöntemler ---
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self):
        r = self._on_kontrol()
        if r is None:
            return
        yol, q = r
        try:
            if yol == "/api/durum":
                return self._json({"surum": SURUM, "moduller": modul_durumu(), "katalog": str(katalog_yolu()),
                                   "defter": str(defter_yolu()), "platform": sys.platform,
                                   "termux": os.environ.get("PREFIX", "").startswith("/data/data/com.termux")})
            if yol == "/api/evrak/ara":
                return self._json(evrak_ara(q.get("q", ""), int(q.get("limit") or 100)))
            if yol == "/api/evrak/dosya":
                p = evrak_dosya_yolu(q.get("skey", ""))
                if not p:
                    return self._json({"hata": "Dosya bulunamadı"}, 404)
                veri = p.read_bytes()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/pdf" if p.suffix.lower() == ".pdf" else "application/octet-stream")
                self.send_header("Content-Disposition", "inline; filename*=UTF-8''" + urllib.parse.quote(p.name))
                self.send_header("Content-Length", str(len(veri)))
                self.end_headers()
                self.wfile.write(veri)
                return
            if yol == "/api/yenilikler":
                return self._json(yenilikler(q.get("sonra", ""), int(q.get("limit") or 30)))
            if yol == "/api/drive":
                return self._json(drive_durumu())
            if yol == "/api/ajanda":
                return self._json(ajanda(int(q.get("gun") or 60)))
            if yol == "/api/gorevler":
                return self._json({"gorevler": [g.ozet(int(q.get("satir") or 40)) for g in GOREV_DURUM.values()]})
            self._json({"hata": "Bulunamadı"}, 404)
        except Exception as e:  # noqa: BLE001 — istemciye anlamlı hata dön
            self._json({"hata": str(e)}, 500)

    def do_POST(self):
        r = self._on_kontrol()
        if r is None:
            return
        yol, _ = r
        try:
            govde = self._govde()
            if yol.startswith("/api/gorev/"):
                kimlik, _, eylem = yol[len("/api/gorev/"):].partition("/")
                g = GOREV_DURUM.get(kimlik)
                if g is None:
                    return self._json({"hata": "Bilinmeyen görev"}, 404)
                if eylem == "durdur":
                    g.durdur()
                else:
                    g.baslat()
                return self._json(g.ozet())
            if yol == "/api/a4":
                return self._json(a4_birlestir(list(govde.get("dosyalar") or []), govde.get("cikti")))
            self._json({"hata": "Bulunamadı"}, 404)
        except (ValueError, RuntimeError) as e:
            self._json({"hata": str(e)}, 400)
        except Exception as e:  # noqa: BLE001
            self._json({"hata": str(e)}, 500)


def sunucu_olustur(port: int, anahtar: str) -> ThreadingHTTPServer:
    Isleyici.anahtar = anahtar
    return ThreadingHTTPServer(("127.0.0.1", port), Isleyici)


def calistir(argv: list[str]) -> int:
    """Gömülü pakette bir modül betiğini "python betik.py ..." gibi çalıştırır."""
    if not argv:
        print("Kullanım: --calistir betik.py [argümanlar]", file=sys.stderr)
        return 2
    betik = Path(argv[0])
    if not betik.is_absolute():
        betik = Path.cwd() / betik
    sys.argv = [str(betik), *argv[1:]]
    sys.path.insert(0, str(betik.parent))
    _ld_geri_yukle(os.environ)
    # Modüller sys.frozen'a bakıp veri yolunu ikilinin klasörü sanmasın: kendi (eşitlenmiş) klasörlerini kullansınlar
    if hasattr(sys, "frozen"):
        del sys.frozen
    runpy.run_path(str(betik), run_name="__main__")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "--calistir":
        return calistir(argv[1:])
    ap = argparse.ArgumentParser(description="CanEditor Hukuk Asistanı yerel sunucusu")
    ap.add_argument("--port", type=int, default=int(os.environ.get("CANASISTAN_PORT") or VARSAYILAN_PORT))
    ap.add_argument("--anahtar", action="store_true", help="Eşleştirme anahtarını yazdır ve çık")
    a = ap.parse_args(argv)
    k = anahtar_al()
    if a.anahtar:
        print(k)
        return 0
    srv = sunucu_olustur(a.port, k)
    print(f"CanEditor Hukuk Asistanı {SURUM} — http://127.0.0.1:{a.port}", flush=True)
    print(f"Eşleştirme anahtarı: {k}", flush=True)
    print("CanEditor → Asistan → Bağlan penceresine bu anahtarı girin (masaüstü uygulamada otomatik).", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for g in GOREV_DURUM.values():
            g.durdur()
    return 0


if __name__ == "__main__":
    sys.exit(main())
