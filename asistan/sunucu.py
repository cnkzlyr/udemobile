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
import base64
import hashlib
import json
import os
import re
import runpy
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SURUM = "4.1.0"
KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import drive_indeks as _drive_indeks  # noqa: E402
import entegrasyon as _entegrasyon    # noqa: E402
import hayfa_kopru as _hayfa_kopru    # noqa: E402
import jar_donustur as _jar_donustur  # noqa: E402
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


class _KapananConn(sqlite3.Connection):
    """with blokundan çıkınca bağlantıyı gerçekten kapatır (Windows dosya kilidini önler)."""
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self.close()


def _ro(db: Path) -> sqlite3.Connection | None:
    if not db.is_file():
        return None
    c = sqlite3.connect(f"file:{urllib.parse.quote(str(db))}?mode=ro", uri=True, timeout=10, factory=_KapananConn)
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
    sonuc["ayar"] = _drive_indeks.drive_ayar_oku(vd)
    sonuc["indeks"] = _drive_indeks.indeks_ozeti(drive_indeks_yolu())
    return sonuc


def drive_indeks_yolu() -> Path:
    return evrak_veri_dizini() / "drive_indeks.db"


def dosya_not_db_yolu() -> Path:
    return veri_dizini() / "dosya_notlar.db"


def _not_db():
    import contextlib
    @contextlib.contextmanager
    def _cm():
        p = dosya_not_db_yolu()
        p.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(str(p), timeout=10)
        c.row_factory = sqlite3.Row
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS dosya_not (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dkey TEXT NOT NULL,
                esas_no TEXT NOT NULL DEFAULT '',
                baslik TEXT NOT NULL DEFAULT '',
                metin TEXT NOT NULL,
                zaman TEXT NOT NULL
            )""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_dn_dkey ON dosya_not(dkey)")
            yield c
            c.commit()
        finally:
            c.close()
    return _cm()


def dosyalar_listele(q: str = "", durum: str = "", limit: int = 150) -> dict:
    """UYAP kataloğundaki tüm dava dosyalarını filtreli listeler."""
    c = _ro(katalog_yolu())
    if c is None:
        return {"hazir": False, "toplam": 0, "acik": 0, "dosyalar": [],
                "mesaj": "UYAP dosya kataloğu henüz oluşturulmadı. Önce UYAP girişi yapıp tarama başlatın."}
    with c:
        kosul, param = [], []
        if durum and durum.lower() not in ("tumu", "tümü", "all"):
            kosul.append("COALESCE(durum,'') LIKE ?")
            param.append(f"%{durum}%")
        pos, neg = terimler(q)
        for t in pos:
            kosul.append("(COALESCE(birim,'') LIKE ? OR COALESCE(dosya_no,'') LIKE ? OR COALESCE(muvekkil_ara,'') LIKE ? OR COALESCE(taraf_ara,'') LIKE ? OR COALESCE(dosya_tur,'') LIKE ?)")
            param += [f"%{t}%"] * 5
        for t in neg:
            kosul.append("NOT (COALESCE(birim,'') LIKE ? OR COALESCE(taraf_ara,'') LIKE ?)")
            param += [f"%{t}%"] * 2
        where = ("WHERE " + " AND ".join(kosul)) if kosul else ""
        sql = (
            "SELECT dkey, birim, dosya_no, dosya_tur, durum, yargi, acilis, muvekkil, taraflar, evrak_sayisi, taranma "
            f"FROM dosya {where} "
            "ORDER BY CASE WHEN durum='Açık' THEN 0 ELSE 1 END, COALESCE(taranma,'') DESC, COALESCE(acilis,'') DESC LIMIT ?"
        )
        rows = _satirlar(c.execute(sql, (*param, max(1, min(limit, 500)))))
        toplam = c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
        acik = c.execute("SELECT COUNT(*) FROM dosya WHERE durum='Açık'").fetchone()[0]
    return {"hazir": True, "toplam": toplam, "acik": acik, "dosyalar": rows}


def dosya_detay(dkey: str) -> dict:
    """Tek bir UYAP dosyasının tüm ayrıntıları: evraklar, duruşmalar, tebligatlar, Drive dosyaları ve yerel notlar."""
    if not dkey:
        raise ValueError("dkey gerekli")
    c = _ro(katalog_yolu())
    if c is None:
        raise ValueError("UYAP kataloğu henüz yok")
    with c:
        d = c.execute("SELECT * FROM dosya WHERE dkey=?", (dkey,)).fetchone()
        if not d:
            raise ValueError("Dosya bulunamadı")
        dosya = dict(d)
        evraklar = _satirlar(c.execute(
            """SELECT skey, tur, aciklama, tarih, kategori, durum, uzanti, is_ek,
                      (pdf_path IS NOT NULL OR path IS NOT NULL) AS yerel
               FROM evrak WHERE dkey=? ORDER BY tarih DESC, id DESC LIMIT 300""",
            (dkey,),
        ))
        durusmalar = []
        if _tablo_var(c, "durusma"):
            durusmalar = _satirlar(c.execute(
                "SELECT tarih, saat, yer, aciklama, durum FROM durusma WHERE dosya_no=? ORDER BY tarih DESC LIMIT 50",
                (dosya.get("dosya_no") or "",),
            ))
        tebligatlar = []
        if _tablo_var(c, "tebligat"):
            tebligatlar = _satirlar(c.execute(
                "SELECT tebligat_turu, evrak_adi, eklenme FROM tebligat WHERE dosya_no=? ORDER BY eklenme DESC LIMIT 50",
                (dosya.get("dosya_no") or "",),
            ))
    with _not_db() as nc:
        notlar = _satirlar(nc.execute(
            "SELECT id, baslik, metin, zaman FROM dosya_not WHERE dkey=? ORDER BY id DESC LIMIT 50",
            (dkey,),
        ))
    drive_dosyalar = []
    if dosya.get("dosya_no") and drive_indeks_yolu().is_file():
        drive_dosyalar = _drive_indeks.ara(drive_indeks_yolu(), esas=dosya["dosya_no"], limit=40).get("sonuclar") or []
    return {
        "dosya": dosya,
        "evraklar": evraklar,
        "durusmalar": durusmalar,
        "tebligatlar": tebligatlar,
        "notlar": notlar,
        "drive_dosyalar": drive_dosyalar,
    }


def dosya_not_ekle(g: dict) -> dict:
    dkey = str(g.get("dkey") or "").strip()
    metin = str(g.get("metin") or "").strip()
    if not dkey or not metin:
        raise ValueError("dkey ve not metni zorunlu")
    baslik = str(g.get("baslik") or "Dosya Notu").strip()[:160]
    esas = str(g.get("esas_no") or "").strip()
    birim = str(g.get("birim") or "").strip()
    zaman = time.strftime("%Y-%m-%dT%H:%M:%S")
    with _not_db() as nc:
        cur = nc.execute(
            "INSERT INTO dosya_not(dkey, esas_no, baslik, metin, zaman) VALUES (?,?,?,?,?)",
            (dkey, esas, baslik, metin, zaman),
        )
        nid = cur.lastrowid
    sonuc = {"ok": True, "id": nid, "zaman": zaman, "senkron": None}
    if g.get("senkron_et") and esas:
        sonuc["senkron"] = _entegrasyon.uyap_otomatik_aktar(
            AVUKAT_DIR, birim=birim, dosya_no=esas, tur=baslik, aciklama=metin, tarih=zaman[:10]
        )
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
    "evrak-giris":      {"ad": "UYAP oturum aç (e-imza)", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "login"], "cdp": True},
    "evrak-islemlerim": {"ad": "UYAP: İşlemlerim evraklarını indir", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "islemlerim"], "cdp": True},
    "evrak-tebligat":   {"ad": "UYAP: tebligat evraklarını indir", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "dosyalar", "--evrak-turu", "tebligat", "--scope", "all"], "cdp": True},
    "evrak-durusmalar": {"ad": "UYAP: duruşma listesini çek", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "durusmalar"], "cdp": True},
    "evrak-nobetci":    {"ad": "UYAP nöbetçi: tek tarama turu", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_watcher.py", "--once"], "cdp": True},
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
        if ANDROID and self.tanim.get("cdp") and not os.environ.get("CANASISTAN_WEBVIEW_SOKET"):
            return "Gizli UYAP tarayıcısı hazır değil; CanEditor uygulamasını yeniden açın."
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


# ---------------------------------------------------------------------------
# UYAP oturumunu sürekli açık tut: e-İmza takılıysa e-İmza, değilse Mobil İmza (uyap_watcher --once
# içindeki akilli_oturum_ac). Oturum düşerse bir sonraki turda kendiliğinden yeniden kurulur.
# ---------------------------------------------------------------------------

def _uyap_cfg_yolu() -> Path:
    return evrak_veri_dizini() / ".uyap_config.json"


def _uyap_cfg() -> dict:
    try:
        return json.loads(_uyap_cfg_yolu().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _pin_var() -> bool:
    try:
        return bool((evrak_veri_dizini() / "pin.txt").read_text(encoding="utf-8").strip())
    except OSError:
        return bool(os.environ.get("UYAP_E_IMZA_PIN"))


def _maskele(s: str, acik: int = 3) -> str:
    s = str(s or "")
    return "" if not s else ("•" * max(0, len(s) - acik) + s[-acik:])


def uyap_ayar_oku() -> dict:
    c = _uyap_cfg()
    return {"tc": _maskele(c.get("tc", "")), "gsm": _maskele(c.get("gsm", "")), "operator": c.get("operator", ""),
            "tc_var": bool(c.get("tc")), "gsm_var": bool(c.get("gsm")), "pin_var": _pin_var(),
            "bagli_tut": c.get("canasistan_bagli_tut", True), "aralik_dk": int(c.get("canasistan_aralik_dk") or 10)}


def uyap_ayar_yaz(g: dict) -> dict:
    d = evrak_veri_dizini()
    d.mkdir(parents=True, exist_ok=True)
    c = _uyap_cfg()
    import re as _re
    if g.get("tc"):
        tc = _re.sub(r"\D", "", str(g["tc"]))
        if len(tc) != 11:
            raise ValueError("T.C. Kimlik No 11 haneli olmalı")
        c["tc"] = tc
    if g.get("gsm"):
        gsm = _re.sub(r"\D", "", str(g["gsm"]))[-10:]
        if len(gsm) != 10 or not gsm.startswith("5"):
            raise ValueError("GSM 5 ile başlayan 10 hane olmalı (5321234567)")
        c["gsm"] = gsm
    if g.get("operator") in ("turkcell", "turktelekom", "vodafone"):
        c["operator"] = g["operator"]
    if "bagli_tut" in g:
        c["canasistan_bagli_tut"] = bool(g["bagli_tut"])
    if g.get("aralik_dk"):
        c["canasistan_aralik_dk"] = max(3, min(240, int(g["aralik_dk"])))
    if g.get("sil") == "mobil":
        c.pop("tc", None), c.pop("gsm", None)
    yol = _uyap_cfg_yolu()
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, yol)
    pin_yolu = d / "pin.txt"
    if g.get("pin"):
        pin_yolu.write_text(str(g["pin"]).strip(), encoding="utf-8")
    elif g.get("sil") == "pin" and pin_yolu.exists():
        pin_yolu.unlink()
    for f in (yol, pin_yolu):
        try:
            os.chmod(f, 0o600)
        except OSError:
            pass
    BAGLI_TUT.uyandir()
    return uyap_ayar_oku()


class BagliTutucu:
    """Arka planda nöbetçi turlarını çalıştırır: her tur önce oturumu doğrular/yeniden açar, sonra tarar."""
    YENIDEN_DENE_S = 60

    def __init__(self):
        self.olay = threading.Event()
        self.sonraki = 0.0
        self.son_neden = ""

    def uyandir(self):
        self.sonraki = 0.0
        self.olay.set()

    def etkin(self) -> tuple[bool, str]:
        c = _uyap_cfg()
        if not c.get("canasistan_bagli_tut", True):
            return False, "Bağlı tut kapalı"
        if not (_pin_var() or (c.get("tc") and c.get("gsm"))):
            return False, "Giriş bilgisi yok: e-İmza PIN'i ya da Mobil İmza (TC + GSM) girin"
        return True, ""

    def durum(self) -> dict:
        g = GOREV_DURUM["evrak-nobetci"]
        ok, neden = self.etkin()
        gunluk = list(g.gunluk)
        oturum = None
        for satir in reversed(gunluk):
            k = satir.lower()
            if "oturum" in k and any(x in k for x in ("açılamadı", "doğrulanamadı", "açık değil")):
                oturum = False
                break
            if "girilemedi" in k:
                oturum = False
                break
            if "oturum" in k and any(x in k for x in ("doğrulandı", "açıldı", "oturumu açık", "aktif")):
                oturum = True
                break
        return {"etkin": ok, "neden": neden or g.kullanilamama_nedeni(), "calisiyor": g.calisiyor(),
                "son_baslangic": g.baslangic, "son_bitis": g.bitis, "son_kod": g.kod, "oturum": oturum,
                "sonraki": self.sonraki if ok else None, "gunluk": gunluk[-8:], "ayar": uyap_ayar_oku()}

    def dongu(self):
        while True:
            self.olay.wait(timeout=20)
            self.olay.clear()
            try:
                ok, self.son_neden = self.etkin()
                g = GOREV_DURUM["evrak-nobetci"]
                if not ok or g.calisiyor() or g.kullanilamama_nedeni() or time.time() < self.sonraki:
                    continue
                if g.bitis and g.kod not in (0, None) and time.time() - g.bitis < self.YENIDEN_DENE_S:
                    continue
                g.baslat()
                aralik = int(_uyap_cfg().get("canasistan_aralik_dk") or 10) * 60
                self.sonraki = time.time() + aralik
            except Exception as e:  # noqa: BLE001 — döngü asla ölmesin
                self.son_neden = str(e)
                self.sonraki = time.time() + self.YENIDEN_DENE_S

    def baslat(self):
        if os.environ.get("CANASISTAN_BAGLI_TUT", "1") != "0":
            threading.Thread(target=self.dongu, daemon=True, name="bagli-tut").start()


BAGLI_TUT = BagliTutucu()


def cdp_kopru_baslat(port: int = 9223) -> None:
    """Android: uygulamanın gizli WebView'ının DevTools soketini (soyut UNIX soketi) 127.0.0.1:port'a açar.
    UYAP modülleri masaüstündeki Chrome ile konuşur gibi bu WebView'ı kullanır: Chrome/Termux gerekmez."""
    soket_adi = os.environ.get("CANASISTAN_WEBVIEW_SOKET")
    if not soket_adi or not hasattr(socket, "AF_UNIX"):
        return

    def aktar(a, b):
        try:
            while True:
                veri = a.recv(65536)
                if not veri:
                    break
                b.sendall(veri)
        except OSError:
            pass
        finally:
            for x in (a, b):
                try:
                    x.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                x.close()

    def dinle():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", port))
        except OSError:
            return
        srv.listen(16)
        while True:
            istemci, _ = srv.accept()
            hedef = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                hedef.connect("\0" + soket_adi)
            except OSError:
                istemci.close()
                hedef.close()
                continue
            threading.Thread(target=aktar, args=(istemci, hedef), daemon=True).start()
            threading.Thread(target=aktar, args=(hedef, istemci), daemon=True).start()

    threading.Thread(target=dinle, daemon=True, name="cdp-kopru").start()


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

    def _govde(self, max_bayt: int = 1_000_000) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > max_bayt:
            raise ValueError("İstek gövdesi çok büyük")
        return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

    def _dosya_gonder(self, veri: bytes, dosya_adi: str, mime: str | None = None):
        if not mime:
            uz = Path(dosya_adi).suffix.lower()
            mime = {
                ".pdf": "application/pdf",
                ".odt": "application/vnd.oasis.opendocument.text",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".tif": "image/tiff", ".tiff": "image/tiff",
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            }.get(uz, "application/octet-stream")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", "inline; filename*=UTF-8''" + urllib.parse.quote(dosya_adi))
        self.send_header("Content-Length", str(len(veri)))
        self.end_headers()
        self.wfile.write(veri)

    def _on_kontrol(self) -> tuple[str, dict] | None:
        if not self._host_gecerli():
            self._json({"hata": "Geçersiz Host"}, 403)
            return None
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/merhaba":  # anahtarsız: yalnızca sunucunun varlığını bildirir
            self._json({"uygulama": "CanEditor Hukuk Asistanı", "surum": SURUM})
            return None
        if not self._yetkili():
            self._json({"hata": "Anahtar gerekli", "ipucu": "Asistan → Bağlantı"}, 401)
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
                                   "jar": _jar_donustur.durum(),
                                   "entegrasyon": _entegrasyon.ayar_ozeti(AVUKAT_DIR),
                                   "termux": os.environ.get("PREFIX", "").startswith("/data/data/com.termux")})
            if yol == "/api/dosyalar":
                return self._json(dosyalar_listele(q.get("q", ""), q.get("durum", ""), int(q.get("limit") or 150)))
            if yol == "/api/dosya/detay":
                return self._json(dosya_detay(q.get("dkey", "")))
            if yol == "/api/evrak/ara":
                return self._json(evrak_ara(q.get("q", ""), int(q.get("limit") or 100)))
            if yol == "/api/evrak/dosya":
                p = evrak_dosya_yolu(q.get("skey", ""))
                if not p:
                    return self._json({"hata": "Dosya bulunamadı"}, 404)
                return self._dosya_gonder(p.read_bytes(), p.name)
            if yol == "/api/yenilikler":
                return self._json(yenilikler(q.get("sonra", ""), int(q.get("limit") or 30)))
            if yol == "/api/drive":
                return self._json(drive_durumu())
            if yol == "/api/drive/ara":
                return self._json(_drive_indeks.ara(drive_indeks_yolu(), q.get("q", ""), q.get("uzanti", ""), q.get("esas", ""), int(q.get("limit") or 120)))
            if yol == "/api/drive/dosya":
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                p = _drive_indeks.guvenli_drive_dosyasi(Path(ayar["google_drive_dir"]), q.get("rel", "")) if ayar.get("google_drive_dir") else None
                if not p:
                    return self._json({"hata": "Drive dosyası bulunamadı"}, 404)
                return self._dosya_gonder(p.read_bytes(), p.name)
            if yol == "/api/donustur/durum":
                return self._json(_jar_donustur.durum())
            if yol == "/api/entegrasyon/ayar":
                return self._json(_entegrasyon.ayar_ozeti(AVUKAT_DIR))
            if yol == "/api/notion/dosyalar":
                return self._json(_entegrasyon.notion_dosyalar(AVUKAT_DIR, q.get("q", ""), int(q.get("limit") or 100), yenile=q.get("yenile") == "1"))
            if yol == "/api/ticktick/gorevler":
                return self._json(_entegrasyon.ticktick_gorevler(AVUKAT_DIR, q.get("project_id", ""), int(q.get("limit") or 80)))
            if yol == "/api/hayfa/haberler":
                return self._json(_hayfa_kopru.haberler(veri_dizini(), q.get("kategori", ""), q.get("q", ""), int(q.get("limit") or 24), yenile=q.get("yenile") == "1"))
            if yol == "/api/hayfa/haber":
                return self._json(_hayfa_kopru.haber_detay(veri_dizini(), q.get("id", "")))
            if yol == "/api/hayfa/resmi-gazete":
                return self._json(_hayfa_kopru.resmi_gazete(veri_dizini(), q.get("tarih", ""), yenile=q.get("yenile") == "1"))
            if yol == "/api/hayfa/kararlar":
                return self._json(_hayfa_kopru.karar_ara(veri_dizini(), q.get("q", ""), q.get("alan", ""), int(q.get("sayfa") or 1)))
            if yol == "/api/hayfa/karar":
                return self._json(_hayfa_kopru.karar_detay(veri_dizini(), q.get("id", "")))
            if yol == "/api/hayfa/mevzuat":
                return self._json(_hayfa_kopru.mevzuat_ara(veri_dizini(), q.get("q", ""), q.get("tur", "")))
            if yol == "/api/hayfa/adliyeler":
                return self._json(_hayfa_kopru.adliye_ara(q.get("q", ""), q.get("il", ""), q.get("tur", ""), int(q.get("limit") or 80)))
            if yol == "/api/uyap":
                return self._json(BAGLI_TUT.durum())
            if yol == "/api/ajanda":
                return self._json(ajanda(int(q.get("gun") or 60)))
            if yol == "/api/gorevler":
                return self._json({"gorevler": [g.ozet(int(q.get("satir") or 40)) for g in GOREV_DURUM.values()]})
            self._json({"hata": "Bulunamadı"}, 404)
        except (ValueError, RuntimeError) as e:
            self._json({"hata": str(e)}, 400)
        except Exception as e:  # noqa: BLE001 — istemciye anlamlı hata dön
            self._json({"hata": str(e)}, 500)

    def do_POST(self):
        r = self._on_kontrol()
        if r is None:
            return
        yol, _ = r
        try:
            govde = self._govde(max_bayt=25_000_000 if yol == "/api/donustur" else 1_000_000)
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
            if yol == "/api/uyap/ayar":
                return self._json(uyap_ayar_yaz(govde))
            if yol == "/api/uyap/simdi":
                BAGLI_TUT.uyandir()
                return self._json(BAGLI_TUT.durum())
            if yol == "/api/dosya/not":
                return self._json(dosya_not_ekle(govde))
            if yol == "/api/drive/ayar":
                return self._json(_drive_indeks.drive_ayar_yaz(evrak_veri_dizini(), govde))
            if yol == "/api/drive/indeksle":
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                dizin = str(govde.get("dizin") or ayar.get("google_drive_dir") or "").strip()
                if not dizin:
                    raise ValueError("Önce Google Drive klasör yolunu ayarlayın.")
                return self._json(_drive_indeks.indeksle(drive_indeks_yolu(), Path(dizin)))
            if yol == "/api/drive/esitle":
                return self._json(_drive_indeks.esitle_eksikler(katalog_yolu(), evrak_veri_dizini(), int(govde.get("limit") or 100)))
            if yol == "/api/donustur":
                fmt = str(govde.get("format") or "pdf").lower()
                if govde.get("skey"):
                    p = evrak_dosya_yolu(str(govde["skey"]))
                    if not p:
                        raise ValueError("Katalogda indirilmiş dosya bulunamadı.")
                    out, ad, mime = _jar_donustur.bayttan_donustur(p.name, p.read_bytes(), fmt)
                elif govde.get("drive_rel"):
                    ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                    p = _drive_indeks.guvenli_drive_dosyasi(Path(ayar["google_drive_dir"]), str(govde["drive_rel"])) if ayar.get("google_drive_dir") else None
                    if not p:
                        raise ValueError("Drive dosyası bulunamadı.")
                    out, ad, mime = _jar_donustur.bayttan_donustur(p.name, p.read_bytes(), fmt)
                elif govde.get("icerik_b64"):
                    ham = base64.b64decode(str(govde["icerik_b64"]))
                    out, ad, mime = _jar_donustur.bayttan_donustur(str(govde.get("dosya_adi") or "Belge.udf"), ham, fmt)
                else:
                    raise ValueError("skey, drive_rel veya icerik_b64 gerekli.")
                if govde.get("json"):
                    return self._json({"dosya_adi": ad, "mime": mime, "boyut": len(out), "icerik_b64": base64.b64encode(out).decode("ascii")})
                return self._dosya_gonder(out, ad, mime)
            if yol == "/api/entegrasyon/ayar":
                return self._json(_entegrasyon.ayar_kaydet(AVUKAT_DIR, govde))
            if yol == "/api/notion/not":
                return self._json(_entegrasyon.notion_not_ekle(
                    AVUKAT_DIR, str(govde.get("page_id") or ""), str(govde.get("baslik") or "Not"),
                    str(govde.get("metin") or ""), str(govde.get("son_tebligat") or ""), str(govde.get("durusma") or ""),
                ))
            if yol == "/api/ticktick/ekle":
                return self._json(_entegrasyon.ticktick_gorev_ekle(
                    AVUKAT_DIR, str(govde.get("baslik") or ""), str(govde.get("icerik") or ""),
                    str(govde.get("project_id") or ""), str(govde.get("mahkeme") or ""),
                    str(govde.get("son_tarih") or ""), int(govde.get("oncelik") or 3),
                    govde.get("etiketler") if isinstance(govde.get("etiketler"), list) else None,
                ))
            if yol == "/api/ticktick/tamamla":
                return self._json(_entegrasyon.ticktick_tamamla(AVUKAT_DIR, str(govde.get("project_id") or ""), str(govde.get("task_id") or "")))
            if yol == "/api/entegrasyon/uyap-aktar":
                return self._json(_entegrasyon.uyap_otomatik_aktar(
                    AVUKAT_DIR, str(govde.get("birim") or ""), str(govde.get("dosya_no") or ""),
                    str(govde.get("tur") or ""), str(govde.get("aciklama") or ""),
                    str(govde.get("tarih") or ""), str(govde.get("muvekkil") or ""),
                ))
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
    cdp_kopru_baslat()
    BAGLI_TUT.baslat()
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
