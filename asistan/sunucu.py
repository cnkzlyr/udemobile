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

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path

SURUM = "4.9.4"
KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

try:
    import dns_cozucu
    dns_cozucu.yama_kur()
except Exception:
    pass

import drive_indeks as _drive_indeks  # noqa: E402
import entegrasyon as _entegrasyon    # noqa: E402
import hayfa_kopru as _hayfa_kopru    # noqa: E402
import jar_donustur as _jar_donustur  # noqa: E402
# Pakete gömülü (PyInstaller) ikili: Python kurulu olmadan çalışır. Modül kodu paketin içinde salt okunurdur;
# modüller verilerini kendi klasörlerine yazdığı için ilk açılışta kullanıcı veri dizinine eşitlenir.
DONDURULMUS = bool(getattr(sys, "frozen", False))


def _ssl_sertifika_ayarla() -> str:
    """Paketli (PyInstaller) sunucuda HTTPS sertifika doğrulaması.

    Paketin kendi OpenSSL'i derlendiği makinenin (Ubuntu) sertifika yolunu arar; Fedora/openSUSE/macOS'ta orada
    dosya olmadığı için Notion, TickTick, Telegram, Drive, İçtihat/Haber/Mevzuat/Resmî Gazete istekleri
    "CERTIFICATE_VERIFY_FAILED" ile düşüyordu (v4.6.1 kullanıcı raporu). Sistemin sertifika deposu (kurumsal
    kök sertifikalar dahil) varsa o, yoksa certifi kullanılır. Alt görevler de aynı ortamı devralır."""
    if os.environ.get("SSL_CERT_FILE") and os.path.isfile(os.environ["SSL_CERT_FILE"]):
        return os.environ["SSL_CERT_FILE"]
    adaylar = ["/etc/pki/tls/certs/ca-bundle.crt", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
               "/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/ca-bundle.pem", "/etc/ssl/cert.pem"]
    yol = next((p for p in adaylar if os.path.isfile(p)), "")
    if not yol:
        try:
            import certifi
            yol = certifi.where()
        except Exception:  # noqa: BLE001
            yol = ""
    if yol and os.name != "nt":
        os.environ["SSL_CERT_FILE"] = yol
        if os.path.isdir("/etc/ssl/certs"):
            os.environ.setdefault("SSL_CERT_DIR", "/etc/ssl/certs")
        os.environ.setdefault("REQUESTS_CA_BUNDLE", yol)
    return yol


if DONDURULMUS or sys.platform == "darwin":
    SSL_SERTIFIKA = _ssl_sertifika_ayarla()
else:
    SSL_SERTIFIKA = os.environ.get("SSL_CERT_FILE", "")
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
        if os.name != "nt":
            # Paket dosyaları salt-okunur kurulabilir (/usr/lib, izinler 444/555): kopyalar KULLANICIYA yazılabilir
            # olmalı, yoksa modüller kendi klasörlerine günlük/veri yazamaz ve sonraki sürüm eşitlemesi de çöker.
            for k in [d.parent, *d.parent.relative_to(hedef).parents]:
                kd = hedef / k if not k.is_absolute() else k
                try:
                    if kd.is_dir() and not os.access(kd, os.W_OK):
                        kd.chmod(kd.stat().st_mode | 0o700)
                except OSError:
                    pass
            if d.exists() and not os.access(d, os.W_OK):
                try:
                    d.chmod(d.stat().st_mode | 0o600)
                except OSError:
                    pass
        shutil.copy2(f, d)
        if os.name != "nt":
            d.chmod(d.stat().st_mode | 0o600 | (0o111 if os.access(f, os.X_OK) else 0))
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
if str(EVRAK_DIR) not in sys.path:
    sys.path.append(str(EVRAK_DIR))   # uyap_finans_safahat.icra_mi vb. sunucu içinden de kullanılır
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
    """Salt okunur bağlantı. Katalog dosyası var ama henüz UYAP taraması yapılmamışsa (evrak/dosya tabloları yok:
    süre/finans modülleri aynı dosyada yalnız kendi tablolarını açar) None döner; böylece yeni kurulumda tüm
    sekmeler '500 no such table' yerine 'henüz tarama yapılmadı' mesajı gösterir."""
    if not db.is_file():
        return None
    c = sqlite3.connect(f"file:{urllib.parse.quote(str(db))}?mode=ro", uri=True, timeout=10, factory=_KapananConn)
    c.row_factory = sqlite3.Row
    try:
        if db.name == "uyap_katalog.db" and not (_tablo_var(c, "evrak") and _tablo_var(c, "dosya")):
            c.close()
            return None
    except sqlite3.DatabaseError:
        c.close()
        return None
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


# ---------------------------------------------------------------------------
# v4.9.3 Müvekkil seçici: her sekmede aynı müvekkil filtresi. Aynı kişi/şirket UYAP'ta farklı yazılmış olabilir
# ("AHMET SUNGUR (Sanık)", "AHMET  SUNGUR", "ABC İNŞAAT LTD. ŞTİ." / "ABC INSAAT LIMITED SIRKETI"): benzer adlar
# gruplanır ve seçicide "birlikte seç" diye önerilir. EN: client list with fuzzy grouping of name variants.
# ---------------------------------------------------------------------------
_SIRKET_EKLERI = re.compile(
    r"\b(ltd|limited|sti|sirketi|sirket|a ?s|anonim|ticaret|tic|sanayi|san|ve|insaat|ins|pazarlama|paz|"
    r"ithalat|ihracat|ith|ihr|turizm|tur|gida|nakliyat|lojistik|holding|koop|kooperatifi)\b")


def muvekkil_ad_temiz(ad: str) -> str:
    """'AHMET SUNGUR (Sanık)' → 'AHMET SUNGUR' (rol ve vekil ekleri atılır)."""
    ad = re.sub(r"\([^)]*\)", " ", str(ad or ""))
    ad = re.sub(r"\bvekil:.*$", " ", ad, flags=re.I)
    return re.sub(r"\s+", " ", ad).strip(" ;,-")


def _muvekkil_anahtar(ad: str) -> str:
    """Benzerlik anahtarı: Türkçe harfler katlanır, noktalama ve şirket ekleri atılır, kelimeler sıralanır."""
    f = re.sub(r"[^a-z0-9 ]+", " ", fold(ad))
    f = _SIRKET_EKLERI.sub(" ", f)
    return " ".join(sorted(w for w in f.split() if len(w) > 1))


def muvekkil_listesi() -> dict:
    """Katalogdaki tüm müvekkiller: ad, dosya sayısı, dkey'ler ve benzer yazılmış adların grubu."""
    import difflib
    c = _ro(katalog_yolu())
    if c is None:
        return {"hazir": False, "muvekkiller": [], "gruplar": []}
    with c:
        rows = c.execute("SELECT dkey, birim, dosya_no, muvekkil FROM dosya WHERE COALESCE(muvekkil,'') <> ''").fetchall()
    adlar: dict[str, dict] = {}
    for r in rows:
        for parca in str(r["muvekkil"] or "").split(";"):
            ad = muvekkil_ad_temiz(parca)
            if len(ad) < 3:
                continue
            m = adlar.setdefault(ad, {"ad": ad, "anahtar": _muvekkil_anahtar(ad), "dkeyler": [], "dosyalar": []})
            if r["dkey"] not in m["dkeyler"]:
                m["dkeyler"].append(r["dkey"])
                m["dosyalar"].append(f"{r['birim'] or ''}|{r['dosya_no'] or ''}")
    liste = sorted(adlar.values(), key=lambda x: (-len(x["dkeyler"]), x["ad"]))
    # Gruplama (birleşim-bul): aynı anahtar, biri diğerinin kelimelerini kapsıyor ya da yazım benzerliği ≥ %88.
    # Yalnız en az bir uzun kelimeyi paylaşan adlar karşılaştırılır (binlerce adda da hızlı).
    ebeveyn = list(range(len(liste)))

    def bul(i):
        while ebeveyn[i] != i:
            ebeveyn[i] = ebeveyn[ebeveyn[i]]
            i = ebeveyn[i]
        return i

    kova: dict[str, list[int]] = {}
    for i, m in enumerate(liste):
        for w in set(m["anahtar"].split()):
            if len(w) >= 3:
                kova.setdefault(w, []).append(i)
    for idx in kova.values():
        if len(idx) > 60:          # çok yaygın kelime (ör. "mehmet"): tek başına benzerlik kanıtı değil
            continue
        for a_i, i in enumerate(idx):
            for j in idx[a_i + 1:]:
                if bul(i) == bul(j):
                    continue
                a, b = liste[i]["anahtar"], liste[j]["anahtar"]
                if not a or not b:
                    continue
                ka, kb = set(a.split()), set(b.split())
                ayni = a == b or (min(len(ka), len(kb)) >= 2 and (ka <= kb or kb <= ka))
                if not ayni:
                    sm = difflib.SequenceMatcher(None, a, b)
                    ayni = sm.real_quick_ratio() >= 0.88 and sm.quick_ratio() >= 0.88 and sm.ratio() >= 0.88
                if ayni:
                    ebeveyn[bul(i)] = bul(j)
    gruplar: dict[int, list[str]] = {}
    for i, m in enumerate(liste):
        gruplar.setdefault(bul(i), []).append(m["ad"])
    for i, m in enumerate(liste):
        m["grup"] = [x for x in gruplar[bul(i)] if x != m["ad"]]
        m.pop("anahtar", None)
    return {"hazir": True, "muvekkiller": liste,
            "gruplar": [g for g in gruplar.values() if len(g) > 1]}


def _muvekkil_kosul(muvekkil: str, sutun: str = "muvekkil_ara") -> tuple[str, list]:
    """'AD1|AD2' → SQL koşulu (dosya tablosunda müvekkil adlarından biri geçen dosyalar)."""
    adlar = [fold(muvekkil_ad_temiz(x)) for x in str(muvekkil or "").split("|") if x.strip()]
    adlar = [a for a in adlar if a][:50]
    if not adlar:
        return "", []
    return "(" + " OR ".join(f"COALESCE({sutun},'') LIKE ?" for _ in adlar) + ")", [f"%{a}%" for a in adlar]


def _drive_defteri(ids: list) -> dict:
    """Katalog evrak id -> Drive yükleme kaydı (url, zaman)."""
    p = drive_indeks_yolu()
    if not ids or not p.is_file():
        return {}
    try:
        c = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
        c.row_factory = sqlite3.Row
        try:
            if not _tablo_var(c, "drive_yukleme"):
                return {}
            ph = ",".join("?" * len(ids))
            return {r["evrak_id"]: {"url": r["url"], "zaman": r["zaman"]} for r in
                    c.execute(f"SELECT evrak_id, url, zaman FROM drive_yukleme WHERE evrak_id IN ({ph})", [str(i) for i in ids])}
        finally:
            c.close()
    except sqlite3.Error:
        return {}


def evrak_ara(q: str, limit: int = 100, dkey: str = "", kategori: str = "", durum: str = "", offset: int = 0,
              drive_dahil: bool = True, muvekkil: str = "", dosya_durum: str = "", baslangic: str = "",
              bitis: str = "", tur_q: str = "") -> dict:
    """UYAP evrak kataloğunda (kapalı dosyalar dahil tüm arşiv) + Drive indeksinde arama.

    Hız: her terim katlanmış 'ara' sütununda ya da (küçük) dosya tablosunda eşleşen dosyaların evrakında aranır;
    eskisi gibi her terim için 10 sütun × harf varyantı taranmaz (yüz binlerce evrakta donma yapıyordu)."""
    c = _ro(katalog_yolu())
    if c is None:
        return {"hazir": False, "sonuclar": [], "drive": None,
                "mesaj": "UYAP evrak kataloğu henüz yok. Ana Ekran'da Senkron'u açın; tüm arşivin listesi arka planda çıkarılır."}
    with c:
        c.create_function("fold", 1, fold, deterministic=True)
        kosul, param = [], []
        pos, neg = terimler(q)
        sut = {r[1] for r in c.execute("PRAGMA table_info(evrak)").fetchall()}
        ara_s = "COALESCE(e.ara,'')" if "ara" in sut else "fold(COALESCE(e.tur,'') || ' ' || COALESCE(e.aciklama,''))"
        for t in pos:
            kosul.append(f"({ara_s} LIKE ? OR e.dkey IN (SELECT dkey FROM dosya WHERE "
                         "fold(COALESCE(birim,'') || ' ' || COALESCE(dosya_no,'') || ' ' || COALESCE(taraflar,'') || ' ' || "
                         "COALESCE(muvekkil,'')) LIKE ?))")
            param += [f"%{t}%"] * 2
        for t in neg:
            kosul.append(f"{ara_s} NOT LIKE ?")
            param.append(f"%{t}%")
        if dkey:
            kosul.append("e.dkey = ?")
            param.append(dkey)
        if kategori:
            # v4.9.3: "tebligat" filtresi kategori dışında türü/açıklaması tebligat olanları da kapsar
            # (Kapalı Tebligat, e-Tebligat, Tebliğ Mazbatası, Tebligat Parçası, PTT Teslim...)
            if kategori == "tebligat":
                kosul.append(f"(e.kategori = 'tebligat' OR {ara_s} LIKE '%teblig%' OR {ara_s} LIKE '%mazbata%')")
            else:
                kosul.append("e.kategori = ?")
                param.append(kategori)
        mk, mp = _muvekkil_kosul(muvekkil)
        if mk:
            kosul.append(f"e.dkey IN (SELECT dkey FROM dosya WHERE {mk})")
            param += mp
        if dosya_durum == "acik":
            kosul.append("e.dkey IN (SELECT dkey FROM dosya WHERE durum='Açık')")
        elif dosya_durum == "kapali":
            kosul.append("e.dkey IN (SELECT dkey FROM dosya WHERE COALESCE(durum,'') <> 'Açık')")
        if baslangic:
            kosul.append("e.tarih >= ?")
            param.append(baslangic[:10])
        if bitis:
            kosul.append("e.tarih <= ?")
            param.append(bitis[:10] + "T99")
        if tur_q:
            kosul.append("fold(COALESCE(e.tur,'')) LIKE ?")
            param.append(f"%{fold(tur_q)}%")
        if durum == "indirildi":
            kosul.append("(e.path IS NOT NULL OR e.pdf_path IS NOT NULL)")
        elif durum == "indirilmedi":
            kosul.append("(e.path IS NULL AND e.pdf_path IS NULL)")
        where = ("WHERE " + " AND ".join(kosul)) if kosul else ""
        kolonlar = ("e.id, e.skey, e.dkey, e.tur, e.aciklama, e.tarih, e.kategori, e.durum, e.uzanti, e.is_ek, "
                    "(e.pdf_path IS NOT NULL OR e.path IS NOT NULL) AS yerel, d.birim, d.dosya_no, d.muvekkil, d.durum AS dosya_durum")
        rows = _satirlar(c.execute(
            f"SELECT {kolonlar} FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey {where} "
            "ORDER BY e.tarih DESC, e.id DESC LIMIT ? OFFSET ?", (*param, max(1, min(limit, 500)), max(0, offset))))
        toplam = c.execute("SELECT COUNT(*) FROM evrak").fetchone()[0]
        dosya_say = c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
        dsut = {r[1] for r in c.execute("PRAGMA table_info(dosya)").fetchall()}
        taranan = c.execute("SELECT COUNT(*) FROM dosya WHERE tarama='tamam'").fetchone()[0] if "tarama" in dsut else dosya_say
        indirilen = c.execute("SELECT COUNT(*) FROM evrak WHERE path IS NOT NULL OR pdf_path IS NOT NULL").fetchone()[0]
        eslesen = None
        if kosul and len(rows) < max(1, min(limit, 500)) and offset == 0:
            eslesen = len(rows)
    defter = _drive_defteri([r["id"] for r in rows])
    for r in rows:
        k = defter.get(str(r["id"]))
        r["drive"] = bool(k)
        r["drive_url"] = (k or {}).get("url") or ""
    drive = None
    if drive_dahil and drive_indeks_yolu().is_file() and (pos or neg):
        try:
            drive = _drive_indeks.ara(drive_indeks_yolu(), q, "", "", 60)
        except Exception as e:  # noqa: BLE001
            drive = {"hazir": False, "sonuclar": [], "mesaj": str(e)}
    # Dosya düzeyinde eşleşme (taraf / müvekkil / birim / esas): evrak listesi henüz alınmamış dosyalar da çıkar
    dosyalar = []
    if pos and offset == 0:
        try:
            dosyalar = dosyalar_listele(q, "", 25, muvekkil=muvekkil).get("dosyalar") or []
        except Exception:  # noqa: BLE001
            dosyalar = []
    return {"hazir": True, "toplam_evrak": toplam, "dosya_sayisi": dosya_say, "taranan_dosya": taranan,
            "indirilen": indirilen, "eslesen": eslesen, "sonuclar": rows, "drive": drive, "dosyalar": dosyalar}


_ONIZLE_KILIT: dict = {}


def evrak_onizle(skey: str, bicim: str = "pdf") -> tuple[bytes, str, str]:
    """İndirmeden önizleme: (bayt, dosya_adı, biçim). bicim='pdf' → PDF'e çevrilmiş hali (yoksa orijinal);
    'orijinal' → UDF/TIFF/PDF olduğu gibi. Yerelde yoksa UYAP'tan önbelleğe alınır (evrak_onizle.py)."""
    if not skey:
        raise ValueError("skey gerekli")
    c = _ro(katalog_yolu())
    if c is None:
        raise ValueError("Katalog yok")
    with c:
        r = c.execute("SELECT * FROM evrak WHERE skey=?", (skey,)).fetchone()
    if not r:
        raise ValueError("Evrak katalogda yok")
    r = dict(r)

    def var(p):
        if not p:
            return None
        pp = Path(p)
        if not pp.is_absolute():
            pp = katalog_yolu().parent / pp
        return pp if pp.is_file() and pp.stat().st_size > 0 else None

    def yerel():
        orj = var(r.get("path")) or var(r.get("cache_path"))
        pdf = var(r.get("pdf_path")) or (var(orj.with_suffix(".pdf")) if orj and orj.suffix.lower() != ".pdf" else orj)
        return orj, pdf

    orj, pdf = yerel()
    gerek = (not pdf) if bicim == "pdf" else (not orj)
    if gerek:
        kilit = _ONIZLE_KILIT.setdefault(skey, threading.Lock())
        with kilit:
            cmd = [*PY, "evrak_onizle.py", "--skey", skey] + (["--pdfsiz"] if bicim != "pdf" else [])
            try:
                pr = subprocess.run(cmd, cwd=str(EVRAK_DIR), env=gorev_ortami(), capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=300)
            except subprocess.TimeoutExpired:
                raise ValueError("UYAP 5 dakikada yanıt vermedi (oturum açılıyor olabilir).")
            sonuc = {}
            for satir in reversed((pr.stdout or "").splitlines()):
                if satir.strip().startswith("{"):
                    try:
                        sonuc = json.loads(satir)
                    except ValueError:
                        pass
                    break
            if sonuc.get("hata"):
                raise ValueError(sonuc["hata"])
            orj = var(sonuc.get("orijinal")) or orj
            pdf = var(sonuc.get("pdf")) or pdf
    hedef = pdf if (bicim == "pdf" and pdf) else orj
    if not hedef:
        raise ValueError("Evrak alınamadı")
    ad = f"{(r.get('tur') or 'Evrak').strip()[:80]}{hedef.suffix.lower()}"
    return hedef.read_bytes(), ad, hedef.suffix.lower().lstrip(".")


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


def ajanda(gun: int = 60, baslangic: str = "", bitis: str = "") -> dict:
    """Yaklaşan duruşmalar ve tebligat son günleri — UETS ve UYAP tebligat/duruşma verilerini birleştirir."""
    bugun = time.strftime("%Y-%m-%d")
    import datetime
    b_date = datetime.date.today()

    if baslangic:
        alt_sinir = baslangic
    else:
        alt_sinir = (b_date - datetime.timedelta(days=7)).strftime("%Y-%m-%d") if gun > 0 else "1970-01-01"

    if bitis:
        ust_sinir = bitis
    else:
        ust_sinir = (b_date + datetime.timedelta(days=max(1, gun))).strftime("%Y-%m-%d") if gun > 0 else "2099-12-31"

    olaylar: list[dict] = []

    d = _ro(defter_yolu())
    if d is not None:
        with d:
            if _tablo_var(d, "tebligatlar"):
                for r in d.execute("SELECT birim, esas, konu, son_gun, barkod FROM tebligatlar WHERE son_gun IS NOT NULL"):
                    iso = _tr_tarih_iso(r["son_gun"])
                    if iso and alt_sinir <= iso <= ust_sinir:
                        olaylar.append({"tur": "sure", "tarih": iso, "saat": "17:00", "birim": r["birim"], "esas": r["esas"],
                                        "baslik": r["konu"] or "Tebligat son günü", "kaynak": "UETS", "barkod": r["barkod"]})
            if _tablo_var(d, "durusmalar"):
                for r in d.execute("SELECT birim, esas, baslangic, baslik, yer FROM durusmalar WHERE COALESCE(iptal,0)=0"):
                    ts = str(r["baslangic"] or "")
                    if alt_sinir <= ts[:10] <= ust_sinir:
                        olaylar.append({"tur": "durusma", "tarih": ts[:10], "saat": ts[11:16], "birim": r["birim"], "esas": r["esas"],
                                        "baslik": r["baslik"] or "Duruşma", "yer": r["yer"], "kaynak": "Takvim"})

    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            if _tablo_var(k, "durusma"):
                for r in k.execute("SELECT birim, dosya_no, tarih, saat, yer, aciklama FROM durusma WHERE durum != 'iptal'"):
                    iso = _tr_tarih_iso(r["tarih"])
                    if iso and alt_sinir <= iso <= ust_sinir:
                        olaylar.append({"tur": "durusma", "tarih": iso, "saat": r["saat"] or "", "birim": r["birim"], "esas": r["dosya_no"],
                                        "baslik": r["aciklama"] or "Duruşma", "yer": r["yer"], "kaynak": "UYAP"})
            if _tablo_var(k, "tebligat"):
                for r in k.execute("SELECT birim, dosya_no, teblig_tarihi, muhatap, evrak_adi, barkod_delil, yasal_sure_notu FROM tebligat WHERE teblig_tarihi IS NOT NULL"):
                    iso = _tr_tarih_iso(r["teblig_tarihi"])
                    if iso and alt_sinir <= iso <= ust_sinir:
                        olaylar.append({"tur": "sure", "tarih": iso, "saat": "17:00", "birim": r["birim"], "esas": r["dosya_no"],
                                        "baslik": (r["evrak_adi"] or "UYAP Tebligatı") + (f" — {r['yasal_sure_notu']}" if r["yasal_sure_notu"] else ""),
                                        "kaynak": "UYAP Tebligat", "barkod": r["barkod_delil"]})

    # Aynı olay tekilleştirilir ve kalan gün hesaplanır
    gorulen, tekil = set(), []
    for o in sorted(olaylar, key=lambda o: (o["tarih"], o.get("saat") or "")):
        anahtar = (o["tur"], tr_kucuk(o.get("esas") or ""), o["tarih"], o.get("saat") or "")
        if anahtar not in gorulen:
            gorulen.add(anahtar)
            try:
                dt = datetime.datetime.strptime(o["tarih"][:10], "%Y-%m-%d").date()
                o["kalan_gun"] = (dt - b_date).days
            except Exception:
                o["kalan_gun"] = 0
            tekil.append(o)
    return {"olaylar": tekil, "bugun": bugun, "kaynaklar": {"defter": defter_yolu().is_file(), "katalog": katalog_yolu().is_file()}}


def evrak_veri_dizini() -> Path:
    return Path(os.environ.get("UYAP_VERI_DIZINI") or EVRAK_DIR)


def yenilikler(sonra: str = "", limit: int = 50, offset: int = 0, q_filtre: str = "", durum_filtre: str = "") -> dict:
    """'sonra' anından (ISO) beri düşen yeni evrak / tebligatlar — Asistan rozeti, arama, filtre ve sayfalama için."""
    if not sonra:
        sonra = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - 86400))
    sonra = sonra[:19]
    limit = max(1, min(int(limit or 50), 500))
    offset = max(0, int(offset or 0))
    sonuc = {
        "sonra": sonra,
        "evrak_sayisi": 0,
        "filtrelenen_evrak": 0,
        "evraklar": [],
        "tebligat_sayisi": 0,
        "tebligatlar": [],
        "en_yeni": sonra,
        "limit": limit,
        "offset": offset
    }
    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            sonuc["evrak_sayisi"] = k.execute("SELECT COUNT(*) FROM evrak WHERE ilk_gorulme > ? AND COALESCE(is_ek,0)=0",
                                              (sonra,)).fetchone()[0]

            where_clauses = ["e.ilk_gorulme > ?", "COALESCE(e.is_ek,0)=0"]
            params = [sonra]

            if durum_filtre == "yerel":
                where_clauses.append("(e.pdf_path IS NOT NULL OR e.path IS NOT NULL)")
            elif durum_filtre == "indirilmedi":
                where_clauses.append("(e.pdf_path IS NULL AND e.path IS NULL)")

            if q_filtre:
                pos, _ = terimler(q_filtre)
                for t in pos:
                    where_clauses.append("(COALESCE(e.tur,'') LIKE ? OR COALESCE(e.aciklama,'') LIKE ? OR COALESCE(d.birim,'') LIKE ? OR COALESCE(d.dosya_no,'') LIKE ? OR COALESCE(d.muvekkil,'') LIKE ?)")
                    params += [f"%{t}%"] * 5

            where_sql = " AND ".join(where_clauses)
            sayi_sql = f"SELECT COUNT(*) FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey WHERE {where_sql}"
            sonuc["filtrelenen_evrak"] = k.execute(sayi_sql, params).fetchone()[0]

            evrak_sql = f"""SELECT e.skey, e.dkey, e.tur, e.aciklama, e.tarih, e.ilk_gorulme, e.durum,
                                   (e.pdf_path IS NOT NULL OR e.path IS NOT NULL) AS yerel,
                                   COALESCE(e.pdf_path, '') AS pdf_var,
                                   d.birim, d.dosya_no, d.muvekkil
                            FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey
                            WHERE {where_sql}
                            ORDER BY e.ilk_gorulme DESC LIMIT ? OFFSET ?"""
            sonuc["evraklar"] = _satirlar(k.execute(evrak_sql, (*params, limit, offset)))

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
    sonuc["yukleme"] = _drive_indeks.esitleme_ozeti(katalog_yolu(), vd)
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


def dosyalar_listele(q: str = "", durum: str = "", limit: int = 150, muvekkil: str = "") -> dict:
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
        mk, mp = _muvekkil_kosul(muvekkil)
        if mk:
            kosul.append(mk)
            param += mp
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
            """SELECT id, skey, tur, aciklama, tarih, kategori, durum, uzanti, is_ek,
                      (pdf_path IS NOT NULL OR path IS NOT NULL) AS yerel
               FROM evrak WHERE dkey=? ORDER BY tarih DESC, id DESC LIMIT 5000""",
            (dkey,),
        ))
        safahat, tahsilat, reddiyat, icra = [], [], [], None
        try:
            if _tablo_var(c, "dosya_safahat"):
                safahat = _satirlar(c.execute(
                    "SELECT safahat_tarihi_str AS tarih, safahat_turu AS tur, aciklama, islem_yapan_birim AS birim "
                    "FROM dosya_safahat WHERE dkey=? ORDER BY safahat_tarihi DESC, id DESC LIMIT 1000", (dkey,)))
            if _tablo_var(c, "dosya_finans"):
                f = c.execute("SELECT tahsilat_list_json, reddiyat_list_json FROM dosya_finans WHERE dkey=?", (dkey,)).fetchone()
                if f:
                    tahsilat, reddiyat = _json_yukle(f[0]), _json_yukle(f[1])
            import icra_analiz as _ia
            from uyap_finans_safahat import icra_mi as _icra_mi  # type: ignore
            if _icra_mi(dosya.get("birim") or "", dosya.get("dosya_tur") or ""):
                icra = _ia.analiz(c, dkey)
        except Exception:  # noqa: BLE001 — eksik tablo/modül detayı engellemesin
            pass
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
        try:
            hesap = dosya_hesap_getir(c, dkey)
        except sqlite3.Error:
            hesap = None
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
        "taraf_listesi": taraflari_coz(dosya.get("taraflar") or "", dosya.get("muvekkil") or ""),
        "hesap": hesap,
        "konu": dosya_konusu_getir(dkey),
        "safahat": safahat,
        "tahsilat": tahsilat,
        "reddiyat": reddiyat,
        "icra": icra,
        "drive_defter": {k: v for k, v in _drive_defteri([e["id"] for e in evraklar]).items()},
        "tazele": dosya_tazele_durum(dkey),
        "tebligat_surecleri": tebligat_surecleri(dosya.get("dosya_no") or "", evraklar),
        "eksik": {"taraf": not (dosya.get("taraflar") or "").strip(), "evrak": dosya.get("tarama") != "tamam" and not evraklar,
                  "hesap": not (hesap or {}).get("cekildi")},
        "drive_yuklenen": sum(1 for _ in _drive_defteri([e["id"] for e in evraklar])),
        "indirilmemis": sum(1 for e in evraklar if not e.get("yerel")),
    }


def tebligat_surecleri(dosya_no: str, evraklar: list) -> list:
    """Dosyanın tebligat süreçleri: UYAP'tan indirilen mazbatalardan çıkarılan sonuçlar (muhatap, sonuç, yasal
    tebliğ tarihi, süre notu — tebligat_takip_listesi.csv) + katalogdaki tebligat evrakları (indirilmemiş olsa da)."""
    import csv as _csv
    out, gorulen = [], set()
    dn = re.sub(r"\s+", "", dosya_no or "")
    yollar = [evrak_veri_dizini() / "tebligat_takip_listesi.csv",
              evrak_veri_dizini() / "UYAP_Indirilenler" / "TEBLIGATLAR" / "tebligat_takip_listesi.csv",
              Path("/sdcard/Download/UYAP_Indirilenler/TEBLIGATLAR/tebligat_takip_listesi.csv")]
    for y in yollar:
        try:
            if not y.is_file():
                continue
            with y.open(encoding="utf-8-sig", newline="") as f:
                for r in _csv.DictReader(f):
                    if dn and re.sub(r"\s+", "", r.get("Dosya_No") or "") != dn:
                        continue
                    anahtar = (r.get("Evrak_Id") or "") + (r.get("Barkod_Veya_Delil_No") or "")
                    if anahtar in gorulen:
                        continue
                    gorulen.add(anahtar)
                    out.append({"kaynak": "UYAP mazbata", "tarih": r.get("Gonderim_Tarihi") or "", "tur": r.get("Tebligat_Turu") or "",
                                "muhatap": r.get("Tebligat_Muhatabi") or "", "rol": r.get("Muhatap_Rolu") or "",
                                "barkod": r.get("Barkod_Veya_Delil_No") or "", "teblig_tarihi": r.get("Hukuki_Teblig_Tarihi") or "",
                                "sonuc": r.get("Teblig_Durumu_Sonuc") or "", "sure_notu": r.get("Yasal_Sure_Hesabi_Notu") or "",
                                "evrak": r.get("Evrak_Adi") or ""})
        except (OSError, _csv.Error):
            continue
    for e in evraklar:
        t = fold(f"{e.get('tur') or ''} {e.get('kategori') or ''}")
        if "tebli" in t or "mazbata" in t:
            out.append({"kaynak": "UYAP evrak", "tarih": e.get("tarih") or "", "tur": e.get("tur") or "", "muhatap": "",
                        "rol": "", "barkod": "", "teblig_tarihi": "", "sonuc": "indirildi, okunuyor" if e.get("yerel") else "henüz indirilmedi",
                        "sure_notu": "", "evrak": e.get("aciklama") or "", "skey": e.get("skey")})
    out.sort(key=lambda x: str(x.get("tarih") or ""), reverse=True)
    return out[:200]


def _json_yukle(v, varsayilan=None):
    try:
        return json.loads(v) if v else (varsayilan if varsayilan is not None else [])
    except (TypeError, ValueError):
        return varsayilan if varsayilan is not None else []


def taraflari_coz(taraf_txt: str, muvekkil_txt: str = "") -> list:
    """Katalogdaki 'ADI (Rol) vekil: X; ...' metnini satırlara böler; müvekkil satırları işaretlenir."""
    muv = {m.strip() for m in (muvekkil_txt or "").split(";") if m.strip()}
    out = []
    for parca in (taraf_txt or "").split(";"):
        parca = parca.strip()
        if not parca:
            continue
        m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*(?:vekil:\s*(.*))?$", parca)
        ad, rol, vekil = (m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()) if m else (parca, "", "")
        out.append({"ad": ad, "rol": rol, "vekil": vekil, "muvekkil": f"{ad} ({rol})" in muv})
    return out


def _hesap_satiri(r: dict) -> dict:
    """Katalog + dosya_finans + icra_hesap satırını ekrana hazır hesap kaydına çevirir. UYAP'tan HİÇ çekilmemiş
    dosyada tutarlar None kalır (eskiden uydurma rakamlar gösteriliyordu)."""
    is_icra = bool(r.get("ih_guncelleme")) or bool(r.get("f_icra"))
    if not is_icra:
        try:
            sys.path.insert(0, str(EVRAK_DIR)) if str(EVRAK_DIR) not in sys.path else None
            from uyap_finans_safahat import icra_mi  # type: ignore
            is_icra = icra_mi(r.get("birim") or "", r.get("dosya_tur") or "")
        except Exception:  # noqa: BLE001
            is_icra = "icra dairesi" in (r.get("birim") or "").lower().replace("İ", "i")
    cekildi = bool(r.get("f_guncelleme") or r.get("ih_guncelleme"))
    h = {k: r.get(k) for k in ("dkey", "birim", "dosya_no", "dosya_tur", "durum", "acilis", "muvekkil")}
    h.update({"is_icra": is_icra, "cekildi": cekildi, "son_guncelleme": r.get("ih_guncelleme") or r.get("f_guncelleme"),
              "hata": r.get("f_hata"), "para_birimi": "TL"})
    if not cekildi:
        return h
    tahsilat = float(r.get("f_tahsilat") or 0)
    reddiyat = float(r.get("f_reddiyat") or 0)
    harc = float(r.get("f_harc") or 0)
    kalan = float(r.get("f_kalan") or 0)
    if is_icra:
        asil = float(r.get("ih_asil") or 0)
        faiz = float(r.get("ih_faiz") or 0)
        vek = float(r.get("ih_vekalet") or 0)
        masraf = float(r.get("ih_masraf") or 0) + float(r.get("ih_tahsil_harci") or 0)
        toplam = float(r.get("ih_toplam") or 0) or round(asil + faiz + vek + masraf, 2)
        yatan = float(r.get("ih_yatan") or 0) or tahsilat
        bakiye = float(r.get("ih_bakiye") or 0) if r.get("ih_bakiye") is not None else max(0.0, toplam - yatan)
        h.update({"asil_alacak": asil, "islemis_faiz": faiz, "vekalet_ucreti": vek, "masraf_harc": round(masraf, 2),
                  "toplam_borc": round(toplam, 2), "tahsilat": round(yatan, 2), "kalan_borc": round(bakiye, 2),
                  "reddiyat": reddiyat, "kasada_bekleyen": round(max(0.0, tahsilat - reddiyat), 2),
                  "artan_avans": None, "kesinlesme": r.get("ih_kesinlesme") or "",
                  "borclular": [b.get("ad_soyad") for b in _json_yukle(r.get("ih_borclular")) if isinstance(b, dict)]})
    else:
        h.update({"asil_alacak": None, "islemis_faiz": None, "vekalet_ucreti": None, "masraf_harc": round(harc, 2),
                  "toplam_borc": None, "tahsilat": round(tahsilat, 2), "reddiyat": round(reddiyat, 2),
                  "kalan_borc": None, "artan_avans": round(kalan, 2)})
    h["harc_kalemleri"] = _json_yukle(r.get("f_harc_kalemleri"))
    return h


_HESAP_SQL = """
    SELECT d.dkey, d.birim, d.dosya_no, d.dosya_tur, d.durum, d.acilis, d.muvekkil, d.taraflar,
           f.toplam_tahsilat AS f_tahsilat, f.toplam_reddiyat AS f_reddiyat, f.toplam_harc AS f_harc,
           f.kalan_bakiye AS f_kalan, f.son_guncelleme AS f_guncelleme, {f_ek}
           i.takip_kesinlesen_miktar AS ih_asil, i.toplam_faiz AS ih_faiz, i.vekalet_ucreti AS ih_vekalet,
           i.masraf_miktari AS ih_masraf, i.tahsil_harci AS ih_tahsil_harci, i.toplam_alacak AS ih_toplam,
           i.yatan_para AS ih_yatan, i.bakiye_borc AS ih_bakiye, i.kesinlesme_durumu AS ih_kesinlesme,
           i.borclular_json AS ih_borclular, i.son_guncelleme AS ih_guncelleme
    FROM dosya d LEFT JOIN dosya_finans f ON f.dkey = d.dkey LEFT JOIN icra_hesap i ON i.dkey = d.dkey
"""


def _hesap_sql(c) -> str | None:
    if not (_tablo_var(c, "dosya_finans") and _tablo_var(c, "icra_hesap")):
        return None
    sutunlar = {r[1] for r in c.execute("PRAGMA table_info(dosya_finans)").fetchall()}
    ek = []
    for s, ad in (("is_icra", "f_icra"), ("hata", "f_hata"), ("harc_kalemleri_json", "f_harc_kalemleri")):
        ek.append(f"f.{s} AS {ad}," if s in sutunlar else f"NULL AS {ad},")
    return _HESAP_SQL.format(f_ek=" ".join(ek))


def dosya_hesap_getir(c, dkey: str) -> dict | None:
    sql = _hesap_sql(c)
    if not sql:
        return None
    r = c.execute(sql + " WHERE d.dkey = ?", (dkey,)).fetchone()
    return _hesap_satiri(dict(r)) if r else None


def dosya_bul(birim: str, dosya_no: str) -> dict:
    """Birim + esas no ile katalog dkey'i (ajanda/tebligat/yenilik satırlarından 'Dosyayı gör')."""
    c = _ro(katalog_yolu())
    if c is None or not dosya_no:
        return {"dkey": None}
    no = re.sub(r"\s+", "", str(dosya_no)).replace("Esas", "").replace("E.", "")
    m = re.search(r"(\d{4})/(\d+)", no)
    with c:
        adaylar = c.execute("SELECT dkey, birim, dosya_no FROM dosya WHERE dosya_no LIKE ?",
                            (f"{m.group(1)}/{int(m.group(2))}%" if m else f"%{no}%",)).fetchall()
    fb = fold(birim)
    for a in adaylar:
        fa = fold(a["birim"])
        if not fb or fa == fb or fa in fb or fb in fa:
            return {"dkey": a["dkey"], "birim": a["birim"], "dosya_no": a["dosya_no"]}
    return {"dkey": adaylar[0]["dkey"] if len(adaylar) == 1 else None}


def icra_analizi() -> dict:
    """Tüm açık icra dosyalarında kesinleşme ve takipsizlik uyarıları (icra_analiz.py)."""
    c = _ro(katalog_yolu())
    if c is None:
        return {"ozet": {}, "dosyalar": [], "mesaj": "Katalog yok"}
    import icra_analiz as _ia
    with c:
        return _ia.tum_icra(c)


def dosya_konusu_getir(dkey: str) -> dict | None:
    """Dosya konusu: Notion'a yazılmış/Notion'daki konu (notion_uyap eşlemesi); yoksa katalogdan anında çıkarımsal özet."""
    try:
        import notion_uyap  # type: ignore
        k = notion_uyap.konu_getir(dkey)
        if k and k.get("metin"):
            return k
    except Exception:  # noqa: BLE001
        k = None
    try:
        import dosya_ozet  # type: ignore
        c = _ro(katalog_yolu())
        if c is None:
            return k
        with c:
            v = dosya_ozet.veri_topla(c, dkey)
        if v:
            return {"metin": dosya_ozet.cikarimsal_ozet(v), "kaynak": "otomatik (evraklardan, henüz Notion'a yazılmadı)",
                    "url": (k or {}).get("url", "")}
    except Exception:  # noqa: BLE001
        pass
    return k


def dosya_hesaplari(q: str = "", muvekkil: str = "", dosya_tur: str = "", durum: str = "") -> dict:
    """İcra ve dava dosyalarının UYAP'tan çekilmiş GERÇEK hesapları: icra kapak hesabı (asıl alacak, faiz, vekâlet,
    masraf, tahsilat, bakiye), dava dosyalarında tahsilat/reddiyat, harç kalemleri ve kasada kalan (artan) avans."""
    c = _ro(katalog_yolu())
    if c is None:
        return {"hazir": False, "istatistik": {}, "hesaplar": [], "muvekkiller": [],
                "mesaj": "UYAP dosya kataloğu henüz yok. Önce Senkron ile UYAP dosyalarını tarayın."}
    with c:
        sql = _hesap_sql(c)
        where, params = [], []
        if muvekkil:
            where.append("COALESCE(d.muvekkil,'') LIKE ?")
            params.append(f"%{muvekkil}%")
        if durum and durum.lower() not in ("tumu", "tümü"):
            where.append("COALESCE(d.durum,'') LIKE ?")
            params.append(f"%{durum}%")
        if dosya_tur:
            if dosya_tur.lower() in ("icra", "İcra".lower()):
                where.append("(d.birim LIKE '%İcra Dairesi%' OR d.birim LIKE '%icra dairesi%' OR d.dosya_tur LIKE '%İcra%')")
            else:
                where.append("(COALESCE(d.dosya_tur,'') LIKE ? OR COALESCE(d.birim,'') LIKE ?)")
                params += [f"%{dosya_tur}%", f"%{dosya_tur}%"]
        for t in terimler(q)[0]:
            where.append("(COALESCE(d.birim,'') LIKE ? OR COALESCE(d.dosya_no,'') LIKE ? OR COALESCE(d.muvekkil,'') LIKE ? OR COALESCE(d.taraflar,'') LIKE ?)")
            params += [f"%{t}%"] * 4
        w = (" WHERE " + " AND ".join(where)) if where else ""
        if sql:
            rows = [dict(r) for r in c.execute(
                sql + w + " ORDER BY CASE WHEN COALESCE(i.son_guncelleme, f.son_guncelleme) IS NULL THEN 1 ELSE 0 END, "
                "CASE WHEN d.birim LIKE '%İcra Dairesi%' THEN 0 ELSE 1 END, d.durum='Açık' DESC, d.acilis DESC LIMIT 500",
                params).fetchall()]
        else:
            rows = [dict(r) for r in c.execute(
                "SELECT d.dkey, d.birim, d.dosya_no, d.dosya_tur, d.durum, d.acilis, d.muvekkil, d.taraflar FROM dosya d"
                + w + " ORDER BY d.durum='Açık' DESC, d.acilis DESC LIMIT 500", params).fetchall()]
        hesaplar = [_hesap_satiri(r) for r in rows]
        muvekkiller = [r[0] for r in c.execute(
            "SELECT DISTINCT muvekkil FROM dosya WHERE COALESCE(muvekkil,'') != '' ORDER BY muvekkil").fetchall()]
        toplam_dosya = c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
        icra_toplam = c.execute("SELECT COUNT(*) FROM dosya WHERE birim LIKE '%İcra Dairesi%' OR dosya_tur LIKE '%İcra%'").fetchone()[0]
        cekilen = c.execute("SELECT COUNT(*) FROM dosya_finans").fetchone()[0] if sql else 0
    cek = [h for h in hesaplar if h.get("cekildi")]
    icra = [h for h in cek if h["is_icra"]]
    dava = [h for h in cek if not h["is_icra"]]
    alacak = sum(h.get("toplam_borc") or 0 for h in icra)
    tahsil = sum(h.get("tahsilat") or 0 for h in icra)
    istatistik = {
        "toplam_dosya": toplam_dosya, "listelenen": len(hesaplar), "hesabi_cekilen": cekilen,
        "hesabi_bekleyen": max(0, toplam_dosya - cekilen), "icra_dosya": icra_toplam,
        "toplam_alacak": round(alacak, 2), "toplam_tahsilat": round(tahsil, 2),
        "kalan_alacak": round(sum(h.get("kalan_borc") or 0 for h in icra), 2),
        "toplam_avans": round(sum(h.get("artan_avans") or 0 for h in dava), 2),
        "avansli_dosya": sum(1 for h in dava if (h.get("artan_avans") or 0) > 0),
        "toplam_harc": round(sum(h.get("masraf_harc") or 0 for h in dava), 2),
        "tahsilat_yuzdesi": round(tahsil / alacak * 100, 1) if alacak else 0.0,
    }
    return {"hazir": True, "istatistik": istatistik, "hesaplar": hesaplar, "muvekkiller": muvekkiller}


def hesap_yenile(dkey: str) -> dict:
    """Tek dosyanın hesabını UYAP'tan şimdi çeker (gizli oturumla; görünür tarayıcı açılmaz)."""
    if not dkey:
        raise ValueError("dkey gerekli")
    try:
        r = subprocess.run([*PY, "uyap_finans_safahat.py", "--dkey", dkey, "--saat", "0"], cwd=str(EVRAK_DIR),
                           env=gorev_ortami(), capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=240)
    except subprocess.TimeoutExpired:
        raise ValueError("UYAP 4 dakikada yanıt vermedi; oturum açılıyor olabilir, biraz sonra yeniden deneyin.")
    if r.returncode != 0:
        satir = [x for x in (r.stdout or "").splitlines() + (r.stderr or "").splitlines() if x.strip()]
        raise ValueError((satir[-1] if satir else "Hesap çekilemedi")[:300])
    c = _ro(katalog_yolu())
    if c is None:
        raise ValueError("Katalog yok")
    with c:
        return {"hesap": dosya_hesap_getir(c, dkey)}


# ---------------------------------------------------------------------------
# Tek dosyayı UYAP'tan şimdi getir (taraflar + tüm evrak listesi + hesap + safahat) ve
# "Bu dosyanın evraklarını Drive'a indir" önceliği. İkisi de gizli oturumla, arka planda çalışır.
# ---------------------------------------------------------------------------
_DOSYA_TAZE: dict = {}
_DOSYA_TAZE_KILIT = threading.Lock()


def dosya_tazele_baslat(dkey: str) -> dict:
    if not dkey:
        raise ValueError("dkey gerekli")
    with _DOSYA_TAZE_KILIT:
        d = _DOSYA_TAZE.get(dkey)
        if d and d.get("calisiyor"):
            return d
        d = {"dkey": dkey, "calisiyor": True, "basla": time.time(), "mesaj": "UYAP'a bağlanılıyor...", "sonuc": None, "hata": ""}
        _DOSYA_TAZE[dkey] = d

    def is_():
        try:
            pr = subprocess.Popen([*PY, "dosya_tazele.py", "--dkey", dkey], cwd=str(EVRAK_DIR), env=gorev_ortami(),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                  errors="replace")
            son = ""
            bitis = time.time() + 900
            for satir in pr.stdout:  # type: ignore[union-attr]
                satir = satir.strip()
                if not satir:
                    continue
                son = satir
                if not satir.startswith("{"):
                    d["mesaj"] = satir[:200]
                if time.time() > bitis:
                    pr.kill()
                    d["hata"] = "UYAP 15 dakikada yanıt vermedi."
                    break
            pr.wait(timeout=30)
            if son.startswith("{"):
                try:
                    r = json.loads(son)
                    d["sonuc"] = r
                    d["hata"] = r.get("hata") or d["hata"]
                except ValueError:
                    pass
            elif not d["hata"]:
                d["hata"] = son[:300] or "Dosya getirilemedi"
        except Exception as e:  # noqa: BLE001
            d["hata"] = str(e)[:300]
        finally:
            d["calisiyor"] = False
            d["bitis"] = time.time()
    threading.Thread(target=is_, daemon=True, name="dosya-tazele").start()
    return d


def dosya_tazele_durum(dkey: str) -> dict:
    return _DOSYA_TAZE.get(dkey) or {"dkey": dkey, "calisiyor": False}


# ---------------------------------------------------------------------------
# v4.9.3 ÖNCELİK KUYRUĞU: elle "indir" denen her şey (dosyanın tüm evrakı ya da tek tek seçilen evraklar)
# oncelikli_dosyalar.json'a yazılır. Senkron (uyap_watcher) bu dosyayı HER evrak arasında yoklar: o an ne
# yapıyorsa (arşiv paketi, katalog listeleme, açık dosya taraması) bırakır, önce bunları indirip PDF'e çevirir ve
# Drive'a eşitler, sonra kaldığı işe döner. EN: shared priority queue polled by the watcher between documents.
# ---------------------------------------------------------------------------
_ONCELIK_KILIT = threading.Lock()


def _oncelik_yolu() -> Path:
    return evrak_veri_dizini() / "oncelikli_dosyalar.json"


def oncelik_oku() -> dict:
    try:
        v = json.loads(_oncelik_yolu().read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def oncelik_ekle(dkeyler: list | None = None, skeyler: list | None = None) -> dict:
    with _ONCELIK_KILIT:
        v = oncelik_oku()
        dk = [x for x in (v.get("dkeyler") or []) if x not in (dkeyler or [])]
        sk = [x for x in (v.get("skeyler") or []) if x not in (skeyler or [])]
        v = {"dkeyler": (list(dkeyler or []) + dk)[:50], "skeyler": (list(skeyler or []) + sk)[:5000],
             "zaman": time.time()}
        _oncelik_yolu().parent.mkdir(parents=True, exist_ok=True)
        gecici = _oncelik_yolu().with_suffix(".tmp")
        gecici.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        os.replace(gecici, _oncelik_yolu())
    # Senkron kapalıysa açılır; açıksa bir sonraki evrakta (≈1-2 sn) öncelikli işe geçer
    g = GOREV_DURUM.get("evrak-akis")
    acildi = False
    if g is not None and not g.calisiyor() and not g.kullanilamama_nedeni():
        try:
            g.baslat()
            acildi = True
        except RuntimeError:
            pass
    return {"sirada": True, "senkron_acildi": acildi, "senkron_calisiyor": bool(g and g.calisiyor())}


def oncelik_durum(dkey: str = "", skeyler: list | None = None) -> dict:
    """Öncelikli işin ilerlemesi: kaç evrak indi, kaçı Drive'da, kaçı kaldı."""
    c = _ro(katalog_yolu())
    v = oncelik_oku()
    sonuc = {"sirada": bool(dkey and dkey in (v.get("dkeyler") or [])) or bool(set(skeyler or []) & set(v.get("skeyler") or [])),
             "toplam": 0, "inen": 0, "kalan": 0, "hata": 0, "tarama": "", "drive": 0}
    if c is None:
        return sonuc
    with c:
        if dkey:
            r = c.execute("SELECT tarama FROM dosya WHERE dkey=?", (dkey,)).fetchone()
            sonuc["tarama"] = (r[0] if r else "") or ""
            rows = c.execute("SELECT id, durum, path, pdf_path FROM evrak WHERE dkey=?", (dkey,)).fetchall()
        elif skeyler:
            ph = ",".join("?" * len(skeyler[:900]))
            rows = c.execute(f"SELECT id, durum, path, pdf_path FROM evrak WHERE skey IN ({ph})", skeyler[:900]).fetchall()
        else:
            rows = []
    for r in rows:
        sonuc["toplam"] += 1
        if r["durum"] in ("indirildi", "mukerrer") or r["path"] or r["pdf_path"]:
            sonuc["inen"] += 1
        elif r["durum"] in ("hata", "yok"):
            sonuc["hata"] += 1
        else:
            sonuc["kalan"] += 1
    try:
        idler = [r["id"] for r in rows]
        sonuc["drive"] = sum(len(_drive_defteri(idler[i:i + 900])) for i in range(0, len(idler), 900))
    except Exception:  # noqa: BLE001
        pass
    g = GOREV_DURUM.get("evrak-akis")
    sonuc["senkron_calisiyor"] = bool(g and g.calisiyor())
    if g is not None:
        son = [x for x in list(g.gunluk)[-30:] if "⚡" in x]
        sonuc["son"] = son[-1].split("] ", 2)[-1][:200] if son else ""
    return sonuc


def dosya_drive_indir(dkey: str) -> dict:
    """Dosyayı ÖNCELİK kuyruğunun başına alır: Senkron o an ne yapıyorsa bırakır, evrak listesi yoksa önce listeyi
    alır, sonra tüm evrakı indirip PDF'e çevirir ve Drive'a yükler."""
    if not dkey:
        raise ValueError("dkey gerekli")
    r = oncelik_ekle(dkeyler=[dkey])
    d = oncelik_durum(dkey)
    return {**r, "bekleyen": d["kalan"], "liste_aliniyor": d["tarama"] != "tamam"}


def denetim_ozeti() -> dict:
    """Düzen & Durum → Denetim: UYAP kataloğu, Drive ve (son denetim turlarından) Notion/TickTick için
    sade "doğru mu, eksik mi" tablosu. Notion/TickTick'e yazmaz; onların sayıları önizleme görevlerinden gelir."""
    k = {}
    c = _ro(katalog_yolu())
    if c is not None:
        with c:
            ds = {r[1] for r in c.execute("PRAGMA table_info(dosya)").fetchall()}
            k["dosya"] = c.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
            k["acik"] = c.execute("SELECT COUNT(*) FROM dosya WHERE durum='Açık'").fetchone()[0]
            k["liste_alinan"] = c.execute("SELECT COUNT(*) FROM dosya WHERE tarama='tamam'").fetchone()[0] if "tarama" in ds else 0
            k["liste_hatali"] = c.execute("SELECT COUNT(*) FROM dosya WHERE tarama LIKE 'hata%'").fetchone()[0] if "tarama" in ds else 0
            k["tarafsiz"] = c.execute("SELECT COUNT(*) FROM dosya WHERE COALESCE(taraflar,'')=''").fetchone()[0]
            k["muvekkilsiz"] = c.execute("SELECT COUNT(*) FROM dosya WHERE COALESCE(muvekkil,'')='' AND COALESCE(taraflar,'')<>''").fetchone()[0]
            k["evrak"] = c.execute("SELECT COUNT(*) FROM evrak").fetchone()[0]
            k["indirilen"] = c.execute("SELECT COUNT(*) FROM evrak WHERE path IS NOT NULL OR pdf_path IS NOT NULL").fetchone()[0]
            k["kategorisiz"] = c.execute("SELECT COUNT(*) FROM evrak WHERE COALESCE(kategori,'') IN ('','Diğer','Diger')").fetchone()[0]
            k["hesap_cekilen"] = (c.execute("SELECT COUNT(*) FROM dosya_finans").fetchone()[0]
                                  if _tablo_var(c, "dosya_finans") else 0)
            k["hata_ornek"] = [dict(r) for r in c.execute(
                "SELECT birim, dosya_no, tarama FROM dosya WHERE tarama LIKE 'hata%' LIMIT 6").fetchall()] if "tarama" in ds else []
    drive = _drive_indeks.esitleme_ozeti(katalog_yolu(), evrak_veri_dizini())
    drive["indeks"] = _drive_indeks.indeks_ozeti(drive_indeks_yolu()).get("toplam", 0) if drive_indeks_yolu().is_file() else 0

    def son(kimlik):
        g = GOREV_DURUM.get(kimlik)
        if not g:
            return None
        for x in reversed(list(g.gunluk)):
            if "@@SONUC@@" in x:
                try:
                    r = json.loads(x.split("@@SONUC@@", 1)[1])
                    r["_bitis"] = g.bitis
                    return r
                except ValueError:
                    return None
        return {"_calisiyor": g.calisiyor()} if g.calisiyor() else None
    return {"katalog": k, "drive": drive, "notion": son("notion-denetle"), "ticktick": son("ticktick-denetle"),
            "calisiyor": any(GOREV_DURUM[x].calisiyor() for x in ("notion-denetle", "ticktick-denetle"))}


SUNUCU_BASLAMA = time.time()
TOPLAM_ISTEK = 0
KESINTI_SAYISI = 0
SON_KESINTI = ""
_SAYAC_KILIT = threading.Lock()
_PING_ONBELLEK: dict = {"t": 0.0, "ms": None}


def istek_say() -> None:
    """Her yetkili /api isteğinde çağrılır (eskiden sayaç hiç artmıyordu, tanı ekranı hep 0 gösteriyordu)."""
    global TOPLAM_ISTEK
    with _SAYAC_KILIT:
        TOPLAM_ISTEK += 1


def kesinti_kaydet(oturum_simdi) -> None:
    """UYAP oturumu açıktan kapalıya döndüğünde kesinti sayar ve zamanını tutar."""
    global KESINTI_SAYISI, SON_KESINTI
    onceki = getattr(kesinti_kaydet, "_onceki", None)
    if onceki is True and oturum_simdi is False:
        with _SAYAC_KILIT:
            KESINTI_SAYISI += 1
            SON_KESINTI = time.strftime("%Y-%m-%d %H:%M:%S")
    if oturum_simdi is not None:
        kesinti_kaydet._onceki = oturum_simdi


_DNS_TANI: dict = {"t": 0.0, "v": None}


def dns_tanisi() -> dict:
    """Tanı dosyası için: DNS hem bu süreçte hem de görev alt sürecinde (nöbetçi/UETS ile aynı ortam) çalışıyor mu?
    5 dk önbellekli. v4.4.0 günlüğünde sunucu çözebilirken nöbetçi çözemiyordu; bu alan farkı doğrudan gösterir."""
    if _DNS_TANI["v"] is not None and time.time() - _DNS_TANI["t"] < 300:
        return _DNS_TANI["v"]
    sonuc: dict = {}
    try:
        import dns_cozucu
        sonuc["sunucu"] = dns_cozucu.tani()
    except Exception as e:  # noqa: BLE001
        sonuc["sunucu"] = {"hata": str(e)[:200]}
    kod = ("import json,sys,os;sys.path.insert(0,os.environ.get('CANASISTAN_KOK',''));import socket;"
           "import dns_cozucu as d;print(json.dumps(d.tani()))")
    try:
        env = gorev_ortami()
        env["CANASISTAN_KOK"] = str(KOK)
        # sitecustomize'ın alt süreçte yüklenip yüklenmediğini ayrıca ölç (import'tan ÖNCE)
        on = ("import socket,json,sys;print(json.dumps({'sitecustomize_yama': getattr(socket.getaddrinfo,'__name__','')=="
              "'_guvenli_getaddrinfo'}))")
        r0 = subprocess.run([*PY, "-c", on], cwd=str(EVRAK_DIR), env=env, capture_output=True, text=True, timeout=20)
        r = subprocess.run([*PY, "-c", kod], cwd=str(EVRAK_DIR), env=env, capture_output=True, text=True, timeout=30)
        alt = json.loads((r.stdout or "{}").strip().splitlines()[-1]) if r.stdout.strip() else {"hata": (r.stderr or "")[-300:]}
        try:
            alt.update(json.loads(r0.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            alt["sitecustomize_yama"] = f"ölçülemedi: {(r0.stderr or '')[-200:]}"
        sonuc["gorev_sureci"] = alt
    except Exception as e:  # noqa: BLE001
        sonuc["gorev_sureci"] = {"hata": str(e)[:200]}
    _DNS_TANI.update(t=time.time(), v=sonuc)
    return sonuc


def uyap_ping_ms() -> int | None:
    """UYAP Avukat Portal'a gerçek TCP bağlantı süresi (60 sn önbellekli). Eskiden sabit 1 ms yazılıyordu."""
    simdi = time.time()
    if simdi - _PING_ONBELLEK["t"] < 60:
        return _PING_ONBELLEK["ms"]
    ms = None
    try:
        t0 = time.perf_counter()
        with socket.create_connection(("avukat.uyap.gov.tr", 443), timeout=2.5):
            ms = int((time.perf_counter() - t0) * 1000)
    except OSError:
        ms = None
    _PING_ONBELLEK.update(t=simdi, ms=ms)
    return ms


_PANO_KATALOG: dict = {"t": 0.0, "v": None}


def _katalog_ozet() -> dict | None:
    """Ana ekran için katalog sayıları (700 bin satırda da hızlı: tek GROUP BY, 20 sn önbellek)."""
    if _PANO_KATALOG["v"] is not None and time.time() - _PANO_KATALOG["t"] < 20:
        return _PANO_KATALOG["v"]
    k = _ro(katalog_yolu())
    if k is None:
        return None
    try:
        durumlar = {r[0] or "yeni": r[1] for r in k.execute("SELECT durum, COUNT(*) FROM evrak GROUP BY durum")}
        tahmini = k.execute("SELECT COUNT(*) FROM evrak WHERE durum='mukerrer' AND hata LIKE 'tahmini%'").fetchone()[0]
        dosya = k.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
        son = k.execute("SELECT MAX(indirildi) FROM evrak WHERE durum='indirildi'").fetchone()[0]
    finally:
        k.close()
    toplam = sum(durumlar.values())
    v = {"dosya": dosya, "evrak": toplam, "indirildi": durumlar.get("indirildi", 0),
         "mukerrer": durumlar.get("mukerrer", 0), "tahmini_mukerrer": tahmini, "yok": durumlar.get("yok", 0),
         "hata": durumlar.get("hata", 0), "atlandi": durumlar.get("atlandi", 0),
         "bekleyen": durumlar.get("yeni", 0) + durumlar.get("hata", 0), "son_indirme": son}
    _PANO_KATALOG.update(t=time.time(), v=v)
    return v


def pano() -> dict:
    """Sade ana ekranın tek isteği: senkron, tebligat izleyici, Drive, içtihat."""
    b = BAGLI_TUT.durum()
    akis = GOREV_DURUM["evrak-akis"]
    vd = evrak_veri_dizini()
    try:
        drive = _drive_indeks.esitleme_ozeti(katalog_yolu(), vd)
        drive["ayar"] = bool(_drive_indeks.drive_ayar_oku(vd).get("google_drive_webhook") or _drive_indeks.drive_ayar_oku(vd).get("google_drive_dir"))
    except Exception as e:  # noqa: BLE001
        drive = {"hata": str(e)[:200]}
    uets = GOREV_DURUM["uets-senkron"]
    # Son anlamlı satır: kullanıcıya "şu an ne yapıyor" göstergesi
    def son_satir(g):
        for x in reversed(list(g.gunluk)):
            x = x.split("] ", 2)[-1].strip() if "] " in x else x.strip()
            if x and not x.startswith("="):
                return x[:220]
        return ""
    return {
        "senkron": {"acik": bool(b["ayar"].get("bagli_tut")) and b["etkin"], "ayarli": b["etkin"], "neden": b["neden"],
                    "calisiyor": akis.calisiyor(), "oturum": b.get("oturum"), "nabiz": b.get("nabiz"),
                    "son_hata": b.get("son_hata"), "simdi": son_satir(akis), "baslangic": akis.baslangic},
        "katalog": _katalog_ozet(),
        "drive": drive,
        "duzen": DUZEN_ZAMAN.durum(),
        "tebligat": {**UETS_ZAMAN.ayar(), "calisiyor": uets.calisiyor(), "son_bitis": uets.bitis, "son_kod": uets.kod,
                     "simdi": son_satir(uets), "kullanilamaz": uets.kullanilamama_nedeni()},
        "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def baglanti_istatistikleri() -> dict:
    calisma_suresi_sn = int(time.time() - SUNUCU_BASLAMA)
    saat = calisma_suresi_sn // 3600
    dakika = (calisma_suresi_sn % 3600) // 60
    saniye = calisma_suresi_sn % 60

    ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
    webhook = ayar.get("google_drive_webhook", "")

    oturum_durum = BAGLI_TUT.durum()
    kesinti_kaydet(oturum_durum.get("oturum"))
    return {
        "calisma_suresi": f"{saat} sa {dakika} dk {saniye} sn",
        "toplam_istek": TOPLAM_ISTEK,
        "kesinti_sayisi": KESINTI_SAYISI,
        "son_kesinti": SON_KESINTI or "Kesinti yaşanmadı (kesintisiz aktif)",
        "ping_ms": uyap_ping_ms(),
        "dns": dns_tanisi(),
        "drive_webhook_tanimli": bool(webhook),
        "drive_yerel_klasor": ayar.get("google_drive_dir") or "Klasör ayarlanmadı",
        "uyap_oturum": oturum_durum,
        "sunucu_zamani": time.strftime("%Y-%m-%d %H:%M:%S")
    }


_CANLI: dict = {"t": 0.0, "v": None}
_SERVIS_GECMIS: deque = deque(maxlen=60)
_SERVIS_SON: dict = {}


def _ping(ad: str, fn) -> dict:
    t0 = time.monotonic()
    try:
        durum, mesaj = fn()
    except Exception as e:  # noqa: BLE001
        durum, mesaj = "hata", str(e)[:180]
    ms = round((time.monotonic() - t0) * 1000)
    onceki = _SERVIS_SON.get(ad)
    if onceki and onceki != durum and durum in ("ok", "hata"):
        _SERVIS_GECMIS.appendleft({"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "servis": ad,
                                   "olay": "yeniden bağlandı" if durum == "ok" else "bağlantı koptu", "mesaj": mesaj})
    _SERVIS_SON[ad] = durum
    return {"ad": ad, "durum": durum, "mesaj": mesaj, "ms": ms}


def _https_get(url: str, basliklar: dict | None = None, zaman: int = 10) -> tuple[int, bytes]:
    import urllib.request
    req = urllib.request.Request(url, headers=basliklar or {})
    with urllib.request.urlopen(req, timeout=zaman) as r:
        return r.status, r.read(4096)


def canli_panel(yenile: bool = False) -> dict:
    """Bağlantı sekmesi: tüm servislerin GERÇEK canlı durumu (paralel, 45 sn önbellek) + arşiv sayıları +
    kopma/yeniden bağlanma kayıtları. Test mesajı göndermez (Telegram için getMe kullanılır)."""
    if not yenile and _CANLI["v"] and time.time() - _CANLI["t"] < 45:
        return _CANLI["v"]
    e = _entegrasyon.env_oku(AVUKAT_DIR)
    drive_ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
    b = BAGLI_TUT.durum()

    def uyap():
        ms = uyap_ping_ms()
        yontem = "e-İmza (PIN kayıtlı)" if b.get("ayar", {}).get("pin_var") else ("Mobil İmza" if b.get("ayar", {}).get("gsm_var") else "giriş bilgisi yok")
        if b.get("oturum") is True:
            return "ok", f"Oturum açık · {yontem} · {ms if ms is not None else '?'} ms"
        if ms is None:
            return "hata", "UYAP'a ulaşılamıyor"
        return ("uyari" if b.get("etkin") else "yok"), f"Oturum kapalı · {yontem} · portal {ms} ms"

    def uets():
        g = GOREV_DURUM["uets-senkron"]
        if not (e.get("UETS_TCKN") and e.get("UETS_PASSWORD")):
            return "yok", "UETS T.C. / şifre girilmemiş"
        if g.calisiyor():
            return "ok", "Şu anda çalışıyor"
        if g.kod == 0:
            return "ok", f"Son tur başarılı · {time.strftime('%d.%m %H:%M', time.localtime(g.bitis or time.time()))}"
        if g.kod is None:
            return "uyari", "Henüz çalışmadı"
        son = next((x for x in reversed(list(g.gunluk)) if x.strip()), "")
        return "hata", f"Son tur hata (kod {g.kod}): {son[-140:]}"

    def gmail():
        if not (e.get("GMAIL_USER") and e.get("GMAIL_APP_PASS")):
            return "yok", "Gmail (UETS kodu) girilmemiş"
        sys.path.insert(0, str(AVUKAT_DIR)) if str(AVUKAT_DIR) not in sys.path else None
        import gmail_otp  # type: ignore
        r = gmail_otp.baglanti_testi(e["GMAIL_USER"], e["GMAIL_APP_PASS"])
        return ("ok" if r["ok"] else "hata"), r["mesaj"]

    def drive():
        url = str(drive_ayar.get("google_drive_webhook") or "")
        if not url:
            return ("ok", "Yerel Drive klasörü") if drive_ayar.get("google_drive_dir") else ("yok", "Webhook / klasör yok")
        kod, _ = _https_get(url, zaman=15)
        oz = _drive_indeks.indeks_ozeti(drive_indeks_yolu())
        return ("ok" if kod < 400 else "hata"), f"Webhook yanıt veriyor · indekste {oz.get('toplam', 0):,} dosya".replace(",", ".")

    def notion():
        if not e.get("NOTION_TOKEN"):
            return "yok", "Token girilmemiş"
        _https_get("https://api.notion.com/v1/users/me", {"Authorization": f"Bearer {e['NOTION_TOKEN']}", "Notion-Version": "2022-06-28"})
        return "ok", "API erişilebilir"

    def ticktick():
        if not e.get("TICKTICK_TOKEN"):
            return "yok", "Token girilmemiş"
        _, ham = _https_get("https://api.ticktick.com/open/v1/project", {"Authorization": f"Bearer {e['TICKTICK_TOKEN']}"}, 15)
        return "ok", "API erişilebilir"

    def telegram():
        if not e.get("TELEGRAM_BOT_TOKEN"):
            return "yok", "Bot token girilmemiş"
        _https_get(f"https://api.telegram.org/bot{e['TELEGRAM_BOT_TOKEN']}/getMe")
        return "ok", "Bot erişilebilir"

    isler = [("UYAP", uyap), ("UETS", uets), ("Gmail (UETS kodu)", gmail), ("Google Drive", drive), ("Notion", notion),
             ("TickTick", ticktick), ("Telegram", telegram)]
    sonuclar: dict = {}
    th = [threading.Thread(target=lambda a=a, f=f: sonuclar.__setitem__(a, _ping(a, f)), daemon=True) for a, f in isler]
    for t in th:
        t.start()
    for t in th:
        t.join(25)
    servisler = [sonuclar.get(a) or {"ad": a, "durum": "hata", "mesaj": "zaman aşımı", "ms": 25000} for a, _ in isler]

    sayilar: dict = {}
    try:
        sayilar["drive_dosya"] = _drive_indeks.indeks_ozeti(drive_indeks_yolu()).get("toplam", 0)
        sayilar["drive_yuklenen"] = _drive_indeks.esitleme_ozeti(katalog_yolu(), evrak_veri_dizini()).get("drivede", 0)
    except Exception:  # noqa: BLE001
        pass
    k = _ro(katalog_yolu())
    if k is not None:
        with k:
            sayilar["dosya"] = k.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
            sayilar["acik_dosya"] = k.execute("SELECT COUNT(*) FROM dosya WHERE durum='Açık'").fetchone()[0]
            sayilar["evrak"] = k.execute("SELECT COUNT(*) FROM evrak").fetchone()[0]
            sayilar["indirilen"] = k.execute("SELECT COUNT(*) FROM evrak WHERE path IS NOT NULL OR pdf_path IS NOT NULL").fetchone()[0]
            sayilar["son7_evrak"] = k.execute("SELECT COUNT(*) FROM evrak WHERE tarih >= date('now','-7 day')").fetchone()[0]
    d = _ro(defter_yolu())
    if d is not None:
        with d:
            if _tablo_var(d, "tebligatlar"):
                sayilar["tebligat"] = d.execute("SELECT COUNT(*) FROM tebligatlar").fetchone()[0]
                sayilar["son7_tebligat"] = d.execute("SELECT COUNT(*) FROM tebligatlar WHERE kayit >= datetime('now','-7 day')").fetchone()[0]
    try:
        aj = ajanda(gun=7)
        sayilar["sure_3gun"] = sum(1 for o in aj["olaylar"] if o.get("tur") == "sure" and 0 <= (o.get("kalan_gun") if o.get("kalan_gun") is not None else 99) <= 3)
        sayilar["durusma_7gun"] = sum(1 for o in aj["olaylar"] if o.get("tur") == "durusma" and 0 <= (o.get("kalan_gun") if o.get("kalan_gun") is not None else 99) <= 7)
    except Exception:  # noqa: BLE001
        pass
    try:
        ki = _hayfa_kopru._cache_oku_bayat(veri_dizini(), "karar_istatistik")
        if isinstance(ki, dict):
            sayilar["yargitay_karar"] = ki.get("en_son_karar_no")
    except Exception:  # noqa: BLE001
        pass
    v = {"servisler": servisler, "sayilar": sayilar, "kesintiler": list(_SERVIS_GECMIS),
         "uyap_kesinti": {"sayi": KESINTI_SAYISI, "son": SON_KESINTI}, "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
         "ssl_sertifika": SSL_SERTIFIKA or "sistem varsayılanı", "surum": SURUM, "calisma_sn": int(time.time() - SUNUCU_BASLAMA)}
    _CANLI.update(t=time.time(), v=v)
    return v


def loglar_zip() -> bytes:
    import zipfile, io
    buf = io.BytesIO()
    log_dir = evrak_veri_dizini() / "LOGLAR"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if log_dir.is_dir():
            for f in sorted(log_dir.glob("*.log*")):
                try:
                    z.write(f, f.name)
                except Exception:
                    pass
        diag = {
            "surum": SURUM,
            "zaman": time.strftime("%Y-%m-%d %H:%M:%S"),
            "istatistik": baglanti_istatistikleri()
        }
        z.writestr("sistem_teshis.json", json.dumps(diag, indent=2, ensure_ascii=False))
    return buf.getvalue()


def evrak_toplu_islem(g: dict) -> dict:
    eylem = g.get("eylem", "indir")
    skeys = g.get("skeys", [])
    if not skeys:
        return {"ok": False, "mesaj": "Hiç evrak seçilmedi"}
    c = _ro(katalog_yolu())
    if not c:
        return {"ok": False, "mesaj": "Katalog bulunamadı"}
    basarili = 0
    hatalar = []
    if eylem == "pdf":
        try:
            from moduller.evrak import donusturucu
            for skey in skeys:
                try:
                    p = evrak_dosya_yolu(skey)
                    if p and p.suffix.lower() == ".udf":
                        pdf_p = p.with_suffix(".pdf")
                        if not pdf_p.is_file():
                            donusturucu.udf_to_pdf(p, pdf_p)
                        basarili += 1
                    elif p and p.suffix.lower() == ".pdf":
                        basarili += 1
                except Exception as ex:
                    hatalar.append(f"{skey}: {ex}")
            mesaj = f"{basarili} evrak başarıyla PDF'e dönüştürüldü."
        except Exception as e:
            return {"ok": False, "mesaj": f"PDF dönüştürme motoru hatası: {e}"}
    elif eylem == "drive":
        try:
            ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
            if ayar.get("google_drive_dir") or ayar.get("google_drive_webhook"):
                _drive_indeks.esitle(katalog_yolu(), ayar)
                basarili = len(skeys)
                mesaj = f"{basarili} evrak için Google Drive eşitlemesi kuyruğa alındı."
            else:
                return {"ok": False, "mesaj": "Google Drive yapılandırılmamış (Drive sekmesinden ayarlayınız)."}
        except Exception as e:
            return {"ok": False, "mesaj": f"Drive eşitleme hatası: {e}"}
    elif eylem == "indir":
        # v4.9.3: eskiden yalnız nöbetçi uyandırılıyordu, seçilen evraklar HİÇBİR sıraya girmiyordu.
        oncelik_ekle(skeyler=[str(x) for x in skeys])
        basarili = len(skeys)
        mesaj = f"⚡ {basarili} evrak öncelikle indiriliyor; birkaç saniye içinde başlar, inince Drive'a eşitlenir."
    else:
        basarili = len(skeys)
        mesaj = f"{basarili} evrak için işlem tamamlandı."
    return {"ok": True, "eylem": eylem, "etkilenen": basarili, "hatalar": hatalar[:5], "mesaj": mesaj}


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
    # v4.9.3: 731 dosyayı yeniden listelemek yerine katalogdaki tebligat/mazbatalar ÖNCELİK kuyruğuna alınır;
    # Senkron her şeyden önce indirir ve Drive'a eşitler (bu görev ilerlemeyi gösterir).
    "evrak-tebligat":   {"ad": "UYAP: tebligat evraklarını indir", "cwd": EVRAK_DIR, "cmd": [*PY, "oncelik_kuyruk.py", "--kategori", "tebligat"], "senkron_gerekir": True},
    "evrak-durusmalar": {"ad": "UYAP: duruşma listesini çek", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_indirici.py", "--cli", "--mode", "durusmalar"], "cdp": True},
    "evrak-nobetci":    {"ad": "UYAP nöbetçi: tek tarama turu", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_watcher.py", "--once"], "cdp": True},
    # Sürekli UYAP → Google Drive akışı (Senkron düğmesi): arşiv durmadan iner, açık dosyalar aralıkla taranır
    "evrak-akis":       {"ad": "UYAP → Drive sürekli senkronizasyon", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_watcher.py"], "cdp": True},
    # Tüm dosyaların GERÇEK UYAP hesapları (icra kapak hesabı, tahsilat/reddiyat, harçlar, artan avans)
    "hesap-tara":       {"ad": "UYAP dosya hesaplarını çek (icra, avans, harç)", "cwd": EVRAK_DIR, "cmd": [*PY, "uyap_finans_safahat.py", "--saat", "12"], "cdp": True},
    # UYAP kataloğu → Notion (Dosyalar, Müvekkiller, Diğer Taraflar), dosya konuları; ardından TickTick düzeni
    # Paketli masaüstünde asistan/*.py betik olarak diskte YOK (ikilinin içinde): modül olarak çalıştırılır
    "notion-esitle":    {"ad": "UYAP → Notion eşitle (taraflar, birim, açılış, konu)", "cwd": KOK,
                         "cmd": [*PY, "-c", "import sys, notion_uyap; sys.argv = ['notion_uyap', '--uygula']; sys.exit(notion_uyap.main())"]},
    "ticktick-duzen":   {"ad": "TickTick düzeni: mükerrer, eksik tebligat, dosya kartları", "cwd": AVUKAT_DIR, "cmd": [*PY, "ticktick_duzen.py", "--uygula"]},
    # Denetim: aynı iki araç DEĞİŞİKLİK YAPMADAN (önizleme) çalışır; "neler bozuk / eksik" raporu
    "notion-denetle":   {"ad": "Notion denetimi (değişiklik yapmaz)", "cwd": KOK,
                         "cmd": [*PY, "-c", "import sys, notion_uyap; sys.argv = ['notion_uyap']; sys.exit(notion_uyap.main())"]},
    "ticktick-denetle": {"ad": "TickTick denetimi (değişiklik yapmaz)", "cwd": AVUKAT_DIR, "cmd": [*PY, "ticktick_duzen.py"]},
}


def tebligat_panel(komut: str, barkod: str = "", zaman_asimi: int = 300) -> dict:
    """Avukat Asistanı penceresinin (Tk) işlevlerini penceresiz çalıştırır (telefonda da): tebligat_panel.py."""
    if komut not in ("liste", "zorla", "temizle", "excel"):
        raise ValueError("Geçersiz komut")
    cmd = [*PY, "tebligat_panel.py", komut] + (["--barkod", str(barkod)] if barkod else [])
    try:
        r = subprocess.run(cmd, cwd=str(AVUKAT_DIR), env=gorev_ortami(), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=zaman_asimi)
    except subprocess.TimeoutExpired:
        raise ValueError(f"İşlem {zaman_asimi} sn içinde bitmedi (internet yavaş olabilir).")
    satirlar = (r.stdout or "").splitlines()
    gunluk = [x for x in satirlar if not x.startswith("@@SONUC@@")][-60:]
    for x in reversed(satirlar):
        if x.startswith("@@SONUC@@"):
            veri = json.loads(x[len("@@SONUC@@"):])
            veri["gunluk"] = gunluk
            return veri
    hata = ((r.stderr or "").strip().splitlines() or ["bilinmeyen hata"])[-1]
    raise ValueError(f"Tebligat işlemi başarısız: {hata[:300]}" + ("\n" + "\n".join(gunluk[-5:]) if gunluk else ""))


# v4.9.3: Tebligat listesi (UETS + EYP + TickTick + Notion) TickTick istek sınırındayken dakikalarca sürüyor,
# sekme "taranıyor…" diye takılı kalıyordu. Son liste bellekte tutulur ve HEMEN döner; 5 dk'dan eskiyse arka
# planda tazelenir (yanıtta "tazeleniyor": true). İlk açılışta (önbellek yoksa) bir kez beklenir.
_TEB_ONBELLEK: dict = {"veri": None, "zaman": 0.0, "calisiyor": False, "hata": ""}
_TEB_KILIT = threading.Lock()


def _teb_tazele():
    try:
        v = tebligat_panel("liste")
        _TEB_ONBELLEK.update(veri=v, zaman=time.time(), hata="")
    except Exception as e:  # noqa: BLE001
        _TEB_ONBELLEK["hata"] = str(e)[:300]
    finally:
        _TEB_ONBELLEK["calisiyor"] = False


def tebligat_liste_onbellekli(tazele: bool = False) -> dict:
    with _TEB_KILIT:
        eski = time.time() - _TEB_ONBELLEK["zaman"] > 300
        if (eski or tazele) and not _TEB_ONBELLEK["calisiyor"]:
            _TEB_ONBELLEK["calisiyor"] = True
            if _TEB_ONBELLEK["veri"] is None:
                _teb_tazele()
            else:
                threading.Thread(target=_teb_tazele, daemon=True, name="tebligat-liste").start()
    if _TEB_ONBELLEK["veri"] is None:
        raise ValueError(_TEB_ONBELLEK["hata"] or "Tebligat listesi alınamadı")
    return {**_TEB_ONBELLEK["veri"], "zaman": _TEB_ONBELLEK["zaman"], "tazeleniyor": _TEB_ONBELLEK["calisiyor"],
            "son_hata": _TEB_ONBELLEK["hata"]}


def gorev_ortami() -> dict:
    """Görev alt süreçlerinin ortamı: gömülü Java ve indirilmiş resmî UYAP Editör jar'ları modüllere tanıtılır."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    _ld_geri_yukle(env)
    # Tüm görevler aynı, YAZILABİLİR veri klasörünü kullansın (katalog, günlük, ayar). Verilmezse modül kendi
    # klasörünü seçer; paketli kurulumda bu salt-okunur program klasörü olabiliyordu.
    env.setdefault("UYAP_VERI_DIZINI", str(evrak_veri_dizini()))
    env["CANASISTAN_AVUKAT_DIR"], env["CANASISTAN_EVRAK_DIR"] = str(AVUKAT_DIR), str(EVRAK_DIR)
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
    # Görevler (nöbetçi, UETS) Telegram/Notion/TickTick anahtarlarını arayüzde kaydedilen .env'den alır
    try:
        _e = _entegrasyon.env_oku(AVUKAT_DIR)
        for k_env, k_mod in (("TELEGRAM_BOT_TOKEN", "UYAP_TELEGRAM_TOKEN"), ("TELEGRAM_CHAT_ID", "UYAP_TELEGRAM_CHAT_ID")):
            if _e.get(k_env):
                env.setdefault(k_env, _e[k_env])
                env.setdefault(k_mod, _e[k_env])
        for k in ("NOTION_TOKEN", "NOTION_DB_DOSYALAR", "TICKTICK_TOKEN"):
            if _e.get(k):
                env.setdefault(k, _e[k])
    except Exception:
        pass
    # Android: alt görevler de DNS yedeğini (sitecustomize → dns_cozucu) yüklesin diye uygulama klasörü PYTHONPATH'e
    if ANDROID:
        yollar = [str(KOK)] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p and p != str(KOK)]
        env["PYTHONPATH"] = os.pathsep.join(yollar)
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


def oturum_satiri_coz(satir: str) -> bool | None:
    """Bir günlük satırı UYAP oturumunun açıldığını (True) ya da düştüğünü (False) söylüyor mu?"""
    k = satir.lower()
    if "oturum" in k and any(x in k for x in ("açılamadı", "doğrulanamadı", "açık değil", "düştü", "sonlanmış", "yenilenemedi")):
        return False
    if "girilemedi" in k:
        return False
    if ("oturum" in k and any(x in k for x in ("doğrulandı", "açıldı", "oturumu açık", "oturum açık"))) or "giriş başarılı" in k:
        return True
    return None


class Gorev:
    def __init__(self, kimlik: str, tanim: dict):
        self.kimlik, self.tanim = kimlik, tanim
        self.proc: subprocess.Popen | None = None
        self.baslangic = self.bitis = None
        self.kod: int | None = None
        self.gunluk: deque[str] = deque(maxlen=400)
        # v4.9.3: UYAP oturum durumu satır satır izlenip KALICI tutulur. Eskiden durum yalnız son 400 günlük
        # satırında aranıyordu; sürekli akışta "oturum doğrulandı" satırı birkaç dakikada tampondan düşüyor,
        # arayüz oturum açıkken bile "Bağlanılıyor…" gösteriyordu.
        self.oturum: bool | None = None
        self.oturum_zaman: float | None = None
        self.oturum_satir = ""

    def kullanilamama_nedeni(self) -> str:
        """Android'de tarayıcı otomasyonu ve masaüstü pencereleri yoktur; bu görevler masaüstünde çalışır."""
        if ANDROID and self.tanim.get("cdp") and not os.environ.get("CANASISTAN_WEBVIEW_SOKET"):
            return "Gizli UYAP tarayıcısı hazır değil; CanEditor uygulamasını yeniden açın."
        if ANDROID and self.tanim.get("tarayici") and not os.environ.get("CANASISTAN_WEBVIEW_SOKET"):
            # UETS artık telefonda da çalışır (cdp_surucu: gizli WebView'ı Selenium gibi sürer)
            return "Gizli tarayıcı hazır değil; CanEditor uygulamasını yeniden açın."
        if ANDROID and self.tanim.get("pencere"):
            return "Telefonda bu pencerenin işlevleri asistan panelindedir."
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
        self.oturum = None
        self.kod, self.bitis, self.baslangic = None, None, time.time()
        self.proc = subprocess.Popen(self.tanim["cmd"], cwd=str(self.tanim["cwd"]), env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     text=True, encoding="utf-8", errors="replace")
        threading.Thread(target=self._oku, daemon=True).start()
        if self.tanim.get("senkron_gerekir"):
            akis = GOREV_DURUM.get("evrak-akis")
            if akis is not None and not akis.calisiyor() and not akis.kullanilamama_nedeni():
                try:
                    akis.baslat()
                except RuntimeError:
                    pass

    def _oku(self):
        assert self.proc and self.proc.stdout
        with self.proc.stdout:
            for satir in self.proc.stdout:
                satir = satir.rstrip("\n")
                self.gunluk.append(satir)
                durum = oturum_satiri_coz(satir)
                if durum is not None:
                    self.oturum, self.oturum_zaman, self.oturum_satir = durum, time.time(), satir.split("] ", 2)[-1][:200]
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
        g = GOREV_DURUM["evrak-akis"] if (GOREV_DURUM["evrak-akis"].calisiyor() or GOREV_DURUM["evrak-akis"].gunluk) else GOREV_DURUM["evrak-nobetci"]
        ok, neden = self.etkin()
        gunluk = list(g.gunluk)
        oturum = g.oturum
        if oturum is None:          # henüz satır satır izlenmediyse (yeni başlamış görev) tampona bakılır
            for satir in reversed(gunluk):
                oturum = oturum_satiri_coz(satir)
                if oturum is not None:
                    break
        # Nabız (4 dk'da bir hafif istek) daha yeni bir sonuç verdiyse o geçerlidir
        if NABIZ.son_durum is not None and NABIZ.son and NABIZ.son > (g.oturum_zaman or 0):
            oturum = NABIZ.son_durum
        # Son turdaki gerçek hata (ör. "Nöbetçi döngü hatası") rozette görünsün; eskiden yalnız ham günlükte kalıyordu
        son_hata = ""
        for satir in reversed(gunluk):
            if "[ERROR]" in satir or "Traceback" in satir:
                son_hata = satir.split("] ", 2)[-1].strip()[:300]
                break
            if "[✓] Bitti" in satir or "tamamlandı" in satir.lower():
                break
        return {"etkin": ok, "neden": neden or g.kullanilamama_nedeni(), "calisiyor": g.calisiyor(), "son_hata": son_hata,
                "son_baslangic": g.baslangic, "son_bitis": g.bitis, "son_kod": g.kod, "oturum": oturum,
                "oturum_zaman": g.oturum_zaman, "oturum_satir": g.oturum_satir,
                "sonraki": self.sonraki if ok else None, "gunluk": gunluk[-40:], "ayar": uyap_ayar_oku(),
                "nabiz": {"son": NABIZ.son or None, "oturum_acik": NABIZ.son_durum, "basarili": NABIZ.basarili}}

    def dongu(self):
        """Senkron açıkken sürekli akış görevini (evrak-akis) ayakta tutar; kapanırsa 60 sn sonra yeniden başlatır.
        Eskiden 10 dk'da bir tek tur (--once) çalışıp yalnız 50 arşiv evrakı indiriyordu (700 bin evrak ≈ 97 gün)."""
        while True:
            self.olay.wait(timeout=20)
            self.olay.clear()
            try:
                ok, self.son_neden = self.etkin()
                g = GOREV_DURUM["evrak-akis"]
                if not ok:
                    if g.calisiyor():
                        g.durdur()
                    continue
                if g.calisiyor() or g.kullanilamama_nedeni() or GOREV_DURUM["evrak-nobetci"].calisiyor() or time.time() < self.sonraki:
                    continue
                if g.bitis and time.time() - g.bitis < self.YENIDEN_DENE_S:
                    continue
                g.baslat()
                self.sonraki = time.time() + self.YENIDEN_DENE_S
            except Exception as e:  # noqa: BLE001 — döngü asla ölmesin
                self.son_neden = str(e)
                self.sonraki = time.time() + self.YENIDEN_DENE_S

    def baslat(self):
        if os.environ.get("CANASISTAN_BAGLI_TUT", "1") != "0":
            threading.Thread(target=self.dongu, daemon=True, name="bagli-tut").start()


BAGLI_TUT = BagliTutucu()


class AyarYedekleyici:
    """Anahtarları bir kez girin: her ayar değişikliğinden 15 sn sonra şifreli yedek kullanıcının Drive'ına
    (Apps Script webhook) ve masaüstünde ~/CanEditor/ altına yazılır. Yeni kurulumda tek adımda geri yüklenir.
    Yedek şifresi (AYAR_YEDEK_SIFRE) yalnızca bu cihazdaki .env'de durur, yedeğin içine girmez."""

    def __init__(self):
        self._zaman = None
        self.son: dict = {}
        self._kilit = threading.Lock()

    def _yollar(self):
        return _entegrasyon.env_dosyasi(AVUKAT_DIR), evrak_veri_dizini(), _uyap_cfg_yolu()

    def sifre(self) -> str:
        return _entegrasyon.env_oku(AVUKAT_DIR).get("AYAR_YEDEK_SIFRE", "")

    def tetikle(self):
        if not self.sifre():
            return
        if self._zaman:
            self._zaman.cancel()
        self._zaman = threading.Timer(15, self.yedekle)
        self._zaman.daemon = True
        self._zaman.start()

    def yedekle(self, sifre: str = "") -> dict:
        import ayar_yedek
        sifre = sifre or self.sifre()
        if not sifre:
            raise ValueError("Önce bir yedek şifresi belirleyin.")
        with self._kilit:
            blob = ayar_yedek.sifrele(ayar_yedek.topla(*self._yollar()), sifre)
            sonuc = {"zaman": time.strftime("%Y-%m-%d %H:%M:%S"), "bulut": None, "yerel": None, "hata": []}
            yerel = ayar_yedek.yerel_yedek_yolu()
            if yerel:
                try:
                    yerel.parent.mkdir(parents=True, exist_ok=True)
                    yerel.write_bytes(blob)
                    os.chmod(yerel, 0o600)
                    sonuc["yerel"] = str(yerel)
                except OSError as e:
                    sonuc["hata"].append(f"Yerel yedek: {e}")
            webhook = str(_drive_indeks.drive_ayar_oku(evrak_veri_dizini()).get("google_drive_webhook") or "")
            if webhook:
                try:
                    sonuc["bulut"] = ayar_yedek.bulut_yedekle(webhook, blob)
                except Exception as e:  # noqa: BLE001
                    sonuc["hata"].append(f"Drive: {str(e)[:160]}")
            self.son = sonuc
            return sonuc

    def durum(self) -> dict:
        import ayar_yedek
        e = _entegrasyon.env_oku(AVUKAT_DIR)
        yerel = ayar_yedek.yerel_yedek_yolu()
        return {"sifre_kayitli": bool(e.get("AYAR_YEDEK_SIFRE")),
                "webhook_var": bool(_drive_indeks.drive_ayar_oku(evrak_veri_dizini()).get("google_drive_webhook")),
                "yerel_yedek": str(yerel) if yerel and yerel.is_file() else "",
                "yerel_zaman": time.strftime("%Y-%m-%d %H:%M", time.localtime(yerel.stat().st_mtime)) if yerel and yerel.is_file() else "",
                "bos_kurulum": not any(e.get(k) for k in ("NOTION_TOKEN", "TICKTICK_TOKEN", "TELEGRAM_BOT_TOKEN", "GMAIL_APP_PASS", "UETS_PASSWORD")),
                "son": self.son}

    def geri_yukle(self, g: dict) -> dict:
        """g: {sifre, kaynak: 'yerel' | 'bulut' | 'dosya', webhook?, icerik (base64)?, hatirla: bool}"""
        import base64 as _b64
        import ayar_yedek
        sifre = str(g.get("sifre") or "")
        kaynak = g.get("kaynak") or "dosya"
        if kaynak == "yerel":
            y = ayar_yedek.yerel_yedek_yolu()
            if not y or not y.is_file():
                raise ValueError("Bu cihazda yerel yedek yok.")
            ham = y.read_bytes()
        elif kaynak == "bulut":
            webhook = str(g.get("webhook") or _drive_indeks.drive_ayar_oku(evrak_veri_dizini()).get("google_drive_webhook") or "").strip()
            ham = ayar_yedek.bulut_son_yedek(webhook)
        else:
            ham = _b64.b64decode(str(g.get("icerik") or ""))
        veri = ayar_yedek.coz(ham, sifre)
        if kaynak == "bulut" and g.get("webhook"):
            veri.setdefault("watcher_config", {}).setdefault("google_drive_webhook", str(g["webhook"]).strip())
        sayi = ayar_yedek.uygula(veri, *self._yollar())
        if g.get("hatirla", True):   # sonraki değişiklikler de otomatik yedeklensin
            p = _entegrasyon.env_dosyasi(AVUKAT_DIR)
            m = ayar_yedek._env_oku(p)
            m["AYAR_YEDEK_SIFRE"] = sifre
            p.write_text("\n".join(f"{k}={v}" for k, v in m.items()) + "\n", encoding="utf-8")
            os.chmod(p, 0o600)
        for k, v in (veri.get("env") or {}).items():
            os.environ[k] = str(v)
        BAGLI_TUT.uyandir()
        _CANLI.update(t=0.0, v=None)
        return {"ok": True, "sayi": sayi, "durum": self.durum()}

    def sifre_kaydet(self, sifre: str) -> dict:
        import ayar_yedek
        if not sifre or len(sifre) < 6:
            raise ValueError("Yedek şifresi en az 6 karakter olmalı.")
        p = _entegrasyon.env_dosyasi(AVUKAT_DIR)
        m = ayar_yedek._env_oku(p)
        m["AYAR_YEDEK_SIFRE"] = sifre
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(f"{k}={v}" for k, v in m.items()) + "\n", encoding="utf-8")
        os.chmod(p, 0o600)
        return {"yedek": self.yedekle(sifre), "durum": self.durum()}


class DriveIndeksZamanlayici:
    """Drive'daki UYAP arşivinin dosya sayısı her zaman görünsün: webhook tanımlıysa indeks boşken hemen,
    sonra 12 saatte bir arka planda yenilenir (elle 'İndeksle' basmak gerekmez)."""

    def dongu(self):
        time.sleep(90)
        while True:
            try:
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                webhook = str(ayar.get("google_drive_webhook") or "").strip()
                if webhook and not _drive_indeks.WEBHOOK_ILERLEME.get("calisiyor"):
                    oz = _drive_indeks.indeks_ozeti(drive_indeks_yolu())
                    son = oz.get("son_indeks") or ""
                    eski = (not oz.get("toplam")) or (not son) or (time.time() - time.mktime(time.strptime(son[:19], "%Y-%m-%dT%H:%M:%S")) > 12 * 3600)
                    if eski:
                        _drive_indeks.indeksle_webhook_arkaplan(drive_indeks_yolu(), webhook, str(ayar.get("google_drive_kok") or ""))
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1800)

    def baslat(self):
        threading.Thread(target=self.dongu, daemon=True, name="drive-indeks-zamanlayici").start()


class DuzenZamanlayici:
    """Sürekli düzen: Notion ve TickTick anahtarları girilmişse her DUZEN_ARALIK_SAAT (varsayılan 6) saatte bir
    sırayla 'notion-esitle' (UYAP kataloğu → Notion: taraflar, birim, açılış, konu, ikonlar) ve 'ticktick-duzen'
    (mükerrer, eksik tebligat, her Notion dosyasına kart) çalıştırır. İkisi de kendi güvenlik sınırlarıyla yazar."""

    def __init__(self):
        self.sonraki = 0.0
        self.son: dict = {}

    def dongu(self):
        while True:
            time.sleep(60)
            try:
                e = _entegrasyon.env_oku(AVUKAT_DIR)
                if not (e.get("NOTION_TOKEN") and e.get("TICKTICK_TOKEN")) or e.get("DUZEN_KAPALI") == "1":
                    continue
                try:
                    saat = float(e.get("DUZEN_ARALIK_SAAT") or 6)
                except ValueError:
                    saat = 6.0
                if not self.sonraki:
                    self.sonraki = time.time() + 600  # açılıştan 10 dk sonra ilk tur
                if time.time() < self.sonraki:
                    continue
                self.sonraki = time.time() + max(1.0, saat) * 3600
                self.tur()
            except Exception:  # noqa: BLE001 — döngü asla ölmesin
                self.sonraki = time.time() + 1800

    def tur(self):
        """Bir düzen turu: önce Notion eşitleme (bitmesini bekler), sonra TickTick düzeni."""
        gn, gt = GOREV_DURUM["notion-esitle"], GOREV_DURUM["ticktick-duzen"]
        if gn.calisiyor() or gt.calisiyor():
            return False
        gn.baslat()
        bas = time.time()
        while gn.calisiyor() and time.time() - bas < 3 * 3600:
            time.sleep(10)
        gt.baslat()
        self.son = {"zaman": time.strftime("%Y-%m-%d %H:%M:%S")}
        return True

    def simdi(self):
        threading.Thread(target=self.tur, daemon=True, name="duzen-simdi").start()

    def durum(self) -> dict:
        e = _entegrasyon.env_oku(AVUKAT_DIR)

        def g(k):
            gr = GOREV_DURUM[k]
            sonuc = None
            for x in reversed(list(gr.gunluk)):
                if "@@SONUC@@" in x:
                    try:
                        sonuc = json.loads(x.split("@@SONUC@@", 1)[1])
                    except ValueError:
                        pass
                    break
            son = ""
            for x in reversed(list(gr.gunluk)):
                x = x.split("] ", 2)[-1].strip() if "] " in x else x.strip()
                if x and "@@SONUC@@" not in x and not x.startswith("="):
                    son = x[:200]
                    break
            return {"calisiyor": gr.calisiyor(), "son_bitis": gr.bitis, "son_kod": gr.kod, "simdi": son, "sonuc": sonuc}
        return {"hazir": bool(e.get("NOTION_TOKEN") and e.get("TICKTICK_TOKEN")), "kapali": e.get("DUZEN_KAPALI") == "1",
                "sonraki": self.sonraki or None, "notion": g("notion-esitle"), "ticktick": g("ticktick-duzen")}

    def baslat(self):
        threading.Thread(target=self.dongu, daemon=True, name="duzen-zamanlayici").start()


class UetsZamanlayici:
    """UETS'e arka planda düzenli girer (uets-senkron): taze CSV + eksik EYP → TickTick (eklerle) + Notion.
    Aralık avukatasistan/.env içindeki UETS_OTOMATIK_DK (0 = kapalı). Telefonda gizli WebView ile çalışır."""

    def __init__(self):
        self.sonraki = 0.0

    def ayar(self) -> dict:
        e = _entegrasyon.env_oku(AVUKAT_DIR)
        try:
            dk = int(e.get("UETS_OTOMATIK_DK") or 0)
        except ValueError:
            dk = 0
        return {"aralik_dk": dk, "hazir": bool(e.get("UETS_TCKN") and e.get("UETS_PASSWORD")),
                "sonraki": self.sonraki if dk else None}

    def ayar_yaz(self, dk: int) -> dict:
        dk = max(0, min(int(dk), 24 * 60))
        e = _entegrasyon.env_oku(AVUKAT_DIR)
        e["UETS_OTOMATIK_DK"] = str(dk)
        satirlar = ["# CanEditor Hukuk Asistanı gizli ayarları (git'e eklenmez, yerel cihazda saklanır)"]
        satirlar += [f"{k}={v}" for k, v in sorted(e.items()) if v]
        p = _entegrasyon.env_dosyasi(AVUKAT_DIR)
        p.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
        self.sonraki = time.time() + 60 if dk else 0.0
        return self.ayar()

    def dongu(self):
        while True:
            time.sleep(30)
            try:
                a = self.ayar()
                g = GOREV_DURUM["uets-senkron"]
                if not a["aralik_dk"] or not a["hazir"] or g.calisiyor() or g.kullanilamama_nedeni():
                    continue
                if not self.sonraki:
                    self.sonraki = time.time() + 120  # sunucu açılışından 2 dk sonra ilk tur
                if time.time() >= self.sonraki:
                    g.baslat()
                    self.sonraki = time.time() + a["aralik_dk"] * 60
            except Exception:  # noqa: BLE001 — döngü asla ölmesin
                self.sonraki = time.time() + 300

    def baslat(self):
        threading.Thread(target=self.dongu, daemon=True, name="uets-zamanlayici").start()


UETS_ZAMAN = UetsZamanlayici()
DUZEN_ZAMAN = DuzenZamanlayici()
AYAR_YEDEK = AyarYedekleyici()
DRIVE_ZAMAN = DriveIndeksZamanlayici()


class OturumNabzi:
    """UYAP oturumunu turlar ARASINDA canlı tutar (gizli tarayıcıda 4 dk'da bir hafif istek).

    Neden: nöbetçi 10 dk'da bir çalışıp kapanıyordu; aradaki boşlukta UYAP oturumu düşüyor ve her tur yeniden
    giriş = telefona her 10 dk'da bir Mobil İmza isteği demekti. Nabız oturumu açık tuttuğu için yeniden giriş
    yalnızca oturum gerçekten koptuğunda yapılır (kart takılıysa e-İmza ile, PIN sorulmadan)."""
    ARALIK_S = 240

    def __init__(self):
        self.son = 0.0
        self.son_durum = None
        self.basarili = 0

    def vur(self) -> bool | None:
        import urllib.request as _u
        port = int(os.environ.get("CANASISTAN_CDP_PORT", "9223"))
        try:
            sekmeler = json.loads(_u.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read())
        except Exception:  # noqa: BLE001 — tarayıcı yok
            return None
        sayfa = next((t for t in sekmeler if "uyap.gov.tr" in (t.get("url") or "") and t.get("webSocketDebuggerUrl")), None)
        if not sayfa:
            return None
        import websocket
        ws = websocket.create_connection(sayfa["webSocketDebuggerUrl"], timeout=15, suppress_origin=True)
        try:
            ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {
                "expression": "fetch('/kullanici_bilgileri.uyap',{method:'POST',credentials:'include',"
                              "headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json()).then(d=>!!(d&&(d.tcKimlikNo||d.tckn))).catch(()=>false)",
                "awaitPromise": True, "returnByValue": True}}))
            bitis = time.time() + 15
            while time.time() < bitis:
                m = json.loads(ws.recv())
                if m.get("id") == 1:
                    return bool(m.get("result", {}).get("result", {}).get("value"))
        finally:
            ws.close()
        return None

    def dongu(self):
        while True:
            time.sleep(30)
            try:
                if not BAGLI_TUT.etkin()[0]:
                    continue
                # Görevler tarayıcıyı kullanırken araya girme
                if any(GOREV_DURUM[k].calisiyor() for k in GOREV_DURUM if GOREVLER[k].get("cdp") or GOREVLER[k].get("tarayici")):
                    self.son = time.time()
                    continue
                if time.time() - self.son < self.ARALIK_S:
                    continue
                self.son = time.time()
                self.son_durum = self.vur()
                if self.son_durum:
                    self.basarili += 1
                elif self.son_durum is False:
                    # Oturum düştü: beklemeden nöbetçiyi başlat (kart takılıysa e-İmza ile yeniden girer)
                    BAGLI_TUT.uyandir()
            except Exception:  # noqa: BLE001
                pass

    def baslat(self):
        threading.Thread(target=self.dongu, daemon=True, name="oturum-nabzi").start()


NABIZ = OturumNabzi()


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

    def unix_baglan():
        hedef = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        hedef.connect("\0" + soket_adi)
        return hedef

    def baglan(istemci):
        # /json ve /json/list yanıtları süzülür: süreçteki TÜM WebView'lar (görünür Asistan/editör ekranı dahil)
        # DevTools'ta listelenir. Modüller "ilk sayfa"yı alıp UYAP/UETS'e yönlendirince kullanıcının ekranı
        # UYAP/UETS giriş sayfasına dönüyordu. Artık yalnızca ekrana HİÇ eklenmemiş gizli WebView'lar görünür.
        try:
            istemci.settimeout(15)
            ilk = istemci.recv(8192, socket.MSG_PEEK)
        except OSError:
            istemci.close()
            return
        satir = ilk.split(b"\r\n", 1)[0].split(b" ")
        yol = satir[1].decode("latin-1", "replace").split("?")[0].rstrip("/") if len(satir) > 1 else ""
        if satir and satir[0] in (b"GET", b"PUT") and yol in ("/json", "/json/list"):
            try:
                veri = b""
                while b"\r\n\r\n" not in veri and len(veri) < 65536:
                    parca = istemci.recv(8192)
                    if not parca:
                        break
                    veri += parca
                hedefler = _cdp_hedefleri(unix_baglan)
                govde = json.dumps([t for t in hedefler if _gizli_hedef_mi(t)]).encode("utf-8")
                istemci.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json; charset=UTF-8\r\n"
                                + f"Content-Length: {len(govde)}\r\nConnection: close\r\n\r\n".encode() + govde)
            except Exception:  # noqa: BLE001
                pass
            finally:
                istemci.close()
            return
        if satir and satir[0] in (b"GET", b"PUT") and yol.startswith("/json/new"):
            # Telefonda yeni sekme açılamaz; görünür ekranı ele geçirmemek için reddedilir
            istemci.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            istemci.close()
            return
        istemci.settimeout(None)
        try:
            hedef = unix_baglan()
        except OSError:
            istemci.close()
            return
        threading.Thread(target=aktar, args=(istemci, hedef), daemon=True).start()
        threading.Thread(target=aktar, args=(hedef, istemci), daemon=True).start()

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
            threading.Thread(target=baglan, args=(istemci,), daemon=True).start()

    threading.Thread(target=dinle, daemon=True, name="cdp-kopru").start()


def _cdp_hedefleri(baglan) -> list:
    """WebView DevTools soketinden ham /json/list okur (Connection: close, Content-Length'e göre)."""
    h = baglan()
    try:
        h.settimeout(10)
        h.sendall(b"GET /json/list HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
        ham = b""
        while True:
            p = h.recv(65536)
            if not p:
                break
            ham += p
            if b"\r\n\r\n" in ham:
                bas, _, govde = ham.partition(b"\r\n\r\n")
                m = re.search(rb"content-length:\s*(\d+)", bas, re.I)
                if m and len(govde) >= int(m.group(1)):
                    break
    finally:
        h.close()
    _, _, govde = ham.partition(b"\r\n\r\n")
    v = json.loads(govde.decode("utf-8", "replace") or "[]")
    return v if isinstance(v, list) else []


_YEREL_URL = ("http://127.0.0.1", "http://localhost", "https://localhost", "file:", "content:", "https://appassets",
              "http://appassets", "data:", "blob:")


def _gizli_hedef_mi(t: dict) -> bool:
    """Otomasyona açık WebView sayfası mı?

    Görünür ekranlar (editör, Asistan, UYAP mobil görünümü) her zaman YEREL adresten (file:///android_asset,
    127.0.0.1) açılır; bunlar asla verilmez. v4.9.0'da yalnızca "pencereye hiç eklenmemiş" WebView'lar veriliyordu;
    o WebView'larda Chromium zamanlayıcıları kıstığı için Mobil İmza girişi çalışmadı. v4.9.1'de otomasyon
    WebView'ları pencereye ekran dışında eklenir; ayrım yerel adres üzerinden yapılır. Boş (about:blank) sayfa
    yalnızca UETS'e ayrılmışsa ya da pencereye bağlı değilse verilir (yeni açılmış görünür bir WebView olabilir)."""
    if t.get("type") not in (None, "page"):
        return False
    url = str(t.get("url") or "")
    if url.startswith(_YEREL_URL):
        return False
    if url.startswith("about:") and "#uets" not in url:
        try:
            d = json.loads(t.get("description") or "{}")
        except (TypeError, ValueError):
            d = {}
        if isinstance(d, dict) and d.get("attached") and d.get("visible") and float(d.get("screenX") or 0) > -5000:
            return False
    return True

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
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition")
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
        istek_say()
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
                return self._json(dosyalar_listele(q.get("q", ""), q.get("durum", ""), int(q.get("limit") or 150),
                                                   muvekkil=q.get("muvekkil", "")))
            if yol == "/api/oncelik/durum":
                return self._json(oncelik_durum(q.get("dkey", ""), [x for x in q.get("skeyler", "").split(",") if x]))
            if yol == "/api/muvekkiller":
                return self._json(muvekkil_listesi())
            if yol == "/api/dosya/detay":
                return self._json(dosya_detay(q.get("dkey", "")))
            if yol == "/api/dosya/bul":
                return self._json(dosya_bul(q.get("birim", ""), q.get("dosya_no", "")))
            if yol == "/api/dosya/tazele":
                return self._json(dosya_tazele_durum(q.get("dkey", "")))
            if yol == "/api/denetim":
                return self._json(denetim_ozeti())
            if yol == "/api/evrak/ara":
                return self._json(evrak_ara(q.get("q", ""), int(q.get("limit") or 100), q.get("dkey", ""),
                                            q.get("kategori", ""), q.get("durum", ""), int(q.get("offset") or 0),
                                            q.get("drive", "1") != "0", muvekkil=q.get("muvekkil", ""),
                                            dosya_durum=q.get("dosya_durum", ""), baslangic=q.get("baslangic", ""),
                                            bitis=q.get("bitis", ""), tur_q=q.get("tur", "")))
            if yol == "/api/icra/analiz":
                return self._json(icra_analizi())
            if yol == "/api/evrak/onizle":
                bayt, ad, bc = evrak_onizle(q.get("skey", ""), q.get("bicim", "pdf"))
                return self._dosya_gonder(bayt, ad)
            if yol == "/api/evrak/dosya":
                p = evrak_dosya_yolu(q.get("skey", ""))
                if not p:
                    return self._json({"hata": "Dosya bulunamadı"}, 404)
                return self._dosya_gonder(p.read_bytes(), p.name)
            if yol == "/api/yenilikler":
                return self._json(yenilikler(
                    q.get("sonra", ""),
                    int(q.get("limit") or 50),
                    int(q.get("offset") or 0),
                    q.get("q", ""),
                    q.get("durum", "")
                ))
            if yol == "/api/drive":
                return self._json(drive_durumu())
            if yol == "/api/drive/ara":
                return self._json(_drive_indeks.ara(drive_indeks_yolu(), q.get("q", ""), q.get("uzanti", ""), q.get("esas", ""), int(q.get("limit") or 120)))
            if yol == "/api/drive/esitle_durum":
                d = {k: v for k, v in _drive_indeks.ESITLE_ILERLEME.items()}
                d["gecen_sn"] = round((d["bitis"] or time.time()) - d["basla"]) if d.get("basla") else 0
                d["ozet"] = _drive_indeks.esitleme_ozeti(katalog_yolu(), evrak_veri_dizini())
                return self._json(d)
            if yol == "/api/drive/indeks_durum":
                d = dict(_drive_indeks.WEBHOOK_ILERLEME)
                d["gecen_sn"] = round(time.time() - d["basla"]) if d.get("basla") else 0
                return self._json(d)
            if yol == "/api/drive/dosya" and q.get("id"):
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                if not ayar.get("google_drive_webhook"):
                    return self._json({"hata": "Webhook ayarlı değil"}, 400)
                veri, ad = _drive_indeks.webhook_dosya_getir(ayar["google_drive_webhook"], q["id"])
                return self._dosya_gonder(veri, ad)
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
            if yol == "/api/dosya/hesaplar":
                return self._json(dosya_hesaplari(q.get("q", ""), q.get("muvekkil", ""), q.get("dosya_tur", ""), q.get("durum", "")))
            if yol == "/api/hayfa/mevzuat/detay":
                return self._json(_hayfa_kopru.mevzuat_detay(veri_dizini(), q.get("url", "")))
            if yol == "/api/ayar/yedek":
                return self._json(AYAR_YEDEK.durum())
            if yol == "/api/baglanti/canli":
                return self._json(canli_panel(q.get("yenile") == "1"))
            if yol == "/api/baglanti/istatistik":
                return self._json(baglanti_istatistikleri())
            if yol == "/api/loglar/indir":
                return self._dosya_gonder(loglar_zip(), "CanEditor_Loglar.zip", mime="application/zip")
            if yol == "/api/uyap":
                return self._json(BAGLI_TUT.durum())
            if yol == "/api/pano":
                return self._json(pano())
            if yol == "/api/hayfa/karar-istatistik":
                return self._json(_hayfa_kopru.karar_istatistik(veri_dizini(), yenile=q.get("yenile") == "1"))
            if yol == "/api/ajanda":
                return self._json(ajanda(int(q.get("gun") or 60), q.get("baslangic", ""), q.get("bitis", "")))
            if yol == "/api/uets/ayar":
                return self._json(UETS_ZAMAN.ayar())
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
                r = uyap_ayar_yaz(govde)
                AYAR_YEDEK.tetikle()
                return self._json(r)
            if yol == "/api/ayar/yedek/sifre":
                return self._json(AYAR_YEDEK.sifre_kaydet(str(govde.get("sifre") or "")))
            if yol == "/api/ayar/yedek/simdi":
                return self._json(AYAR_YEDEK.yedekle(str(govde.get("sifre") or "")))
            if yol == "/api/ayar/yedek/geri":
                return self._json(AYAR_YEDEK.geri_yukle(govde))
            if yol == "/api/ayar/yedek/disa":
                import ayar_yedek as _ay
                sifre = str(govde.get("sifre") or "") or AYAR_YEDEK.sifre()
                blob = _ay.sifrele(_ay.topla(*AYAR_YEDEK._yollar(), pin_dahil=bool(govde.get("pin"))), sifre)
                return self._dosya_gonder(blob, f"CanEditor-ayar-yedegi-{time.strftime('%Y%m%d')}.cnayar")
            if yol == "/api/pano/senkron":
                # Tek düğme: UYAP → Drive sürekli senkronu aç/kapat
                ac = bool(govde.get("ac"))
                uyap_ayar_yaz({"bagli_tut": ac})
                if not ac and GOREV_DURUM["evrak-akis"].calisiyor():
                    GOREV_DURUM["evrak-akis"].durdur()
                BAGLI_TUT.uyandir()
                return self._json(pano())
            if yol == "/api/pano/tebligat":
                # Tek düğme: tebligat izleyici (UETS arka plan) aç/kapat; açılınca hemen bir tur
                ac = bool(govde.get("ac"))
                UETS_ZAMAN.ayar_yaz(int(govde.get("aralik_dk") or 60) if ac else 0)
                g = GOREV_DURUM["uets-senkron"]
                if ac and not g.calisiyor() and not g.kullanilamama_nedeni() and UETS_ZAMAN.ayar()["hazir"]:
                    g.baslat()
                if not ac and g.calisiyor():
                    g.durdur()
                return self._json(pano())
            if yol == "/api/uyap/simdi":
                BAGLI_TUT.uyandir()
                return self._json(BAGLI_TUT.durum())
            if yol == "/api/dosya/not":
                return self._json(dosya_not_ekle(govde))
            if yol == "/api/pano/duzen":
                DUZEN_ZAMAN.simdi()
                time.sleep(0.5)
                return self._json(pano())
            if yol == "/api/dosya/tazele":
                return self._json(dosya_tazele_baslat(str(govde.get("dkey") or "")))
            if yol == "/api/denetim":
                for x in ("notion-denetle", "ticktick-denetle"):
                    if not GOREV_DURUM[x].calisiyor() and not GOREV_DURUM[x].kullanilamama_nedeni():
                        GOREV_DURUM[x].baslat()
                return self._json(denetim_ozeti())
            if yol == "/api/dosya/drive_indir":
                return self._json(dosya_drive_indir(str(govde.get("dkey") or "")))
            if yol == "/api/dosya/hesap_yenile":
                return self._json(hesap_yenile(str(govde.get("dkey") or "")))
            if yol == "/api/evrak/toplu_islem":
                return self._json(evrak_toplu_islem(govde))
            if yol == "/api/drive/ayar":
                sonuc = _drive_indeks.drive_ayar_yaz(evrak_veri_dizini(), govde)
                AYAR_YEDEK.tetikle()
                # Telegram tek kaynak: Drive sekmesinden girilen bilgiler Notion/TT ayarlarına (.env) da yazılır
                tg = {k2: govde[k1] for k1, k2 in (("telegram_token", "telegram_bot_token"), ("telegram_chat_id", "telegram_chat_id")) if govde.get(k1)}
                if tg:
                    _entegrasyon.ayar_kaydet(AVUKAT_DIR, tg)
                return self._json(sonuc)
            if yol == "/api/drive/test_webhook":
                url = str(govde.get("url") or "").strip()
                if not url:
                    ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                    url = ayar.get("google_drive_webhook", "")
                if not url:
                    raise ValueError("Webhook URL boş. Lütfen önce Webhook linkini girin.")
                if "/edit" in url or "/sharing" in url or ("/d/" in url and not url.endswith("/exec")):
                    raise ValueError("Girdiğiniz adres düzenleme/paylaşım linkidir (/edit). Lütfen Google Apps Script'te 'Dağıt > Yeni dağıtım > Web uygulaması' URL'sini (/exec) kullanın.")
                if not (url.startswith("http://") or url.startswith("https://")):
                    raise ValueError("Webhook URL https:// ile başlamalıdır.")
                try:
                    import urllib.request
                    test_govde = json.dumps({"action": "ping", "test": True}).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=test_govde,
                        headers={"Content-Type": "application/json", "User-Agent": "CanEditor/4.1"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        durum = resp.getcode()
                        try:
                            veri = json.loads(resp.read().decode("utf-8"))
                            if veri.get("status") in ("ok", "success") or "message" in veri:
                                return self._json({"tamam": True, "mesaj": f"✓ Webhook başarıyla yanıt verdi (HTTP {durum})! Google Apps Script bağlantısı aktif."})
                        except Exception:
                            pass
                        return self._json({"tamam": True, "mesaj": f"✓ Webhook başarıyla yanıt verdi (HTTP {durum})! Google Drive bağlantısı çalışıyor."})
                except urllib.error.HTTPError as he:
                    if he.code in (302, 200, 201):
                        return self._json({"tamam": True, "mesaj": f"✓ Webhook doğrulandı (HTTP {he.code})! Google Drive bağlantısı hazır."})
                    if he.code in (401, 403):
                        raise ValueError(f"Webhook HTTP {he.code} erişim hatası verdi. Google Apps Script dağıtımında 'Erişimi olanlar' (Who has access) kısmını 'Herkes' (Anyone) yaptığınızdan emin olun.")
                    raise ValueError(f"Webhook HTTP {he.code} hatası verdi: {he.reason}")
                except Exception as ex:
                    msg = str(ex)
                    if "Temporary failure in name resolution" in msg or "Name or service not known" in msg:
                        raise ValueError("İnternet veya DNS bağlantı hatası: script.google.com çözümlenemedi. Lütfen internet bağlantınızı kontrol edin.")
                    raise ValueError(f"Webhook testinde hata: {msg}")
            if yol == "/api/drive/indeksle":
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                dizin = str(govde.get("dizin") or ayar.get("google_drive_dir") or "").strip()
                webhook = str(govde.get("webhook") or ayar.get("google_drive_webhook") or "").strip()
                if dizin.startswith(("http://", "https://")):
                    webhook, dizin = webhook or dizin, ""
                # 1) Bilgisayarda Google Drive klasörü bağlıysa: yerel tarama (hızlı)
                if dizin and Path(dizin).is_dir() and not govde.get("bulut"):
                    return self._json(_drive_indeks.indeksle(drive_indeks_yolu(), Path(dizin)))
                # 2) Telefonda / klasör yoksa: Drive'ın TAMAMI Apps Script üzerinden (arka planda, sayfa sayfa).
                #    Eskiden burada sessizce /sdcard/Download taranıyor ve Drive diye gösteriliyordu.
                if webhook.startswith("https://"):
                    if webhook != ayar.get("google_drive_webhook"):
                        _drive_indeks.drive_ayar_yaz(evrak_veri_dizini(), {"google_drive_webhook": webhook})
                    return self._json({"arkaplan": True, **_drive_indeks.indeksle_webhook_arkaplan(
                        drive_indeks_yolu(), webhook, str(govde.get("kok") or "").strip())})
                raise ValueError("Google Drive bağlı değil: bilgisayarda Drive klasörünü ya da telefonda Apps Script "
                                 "Webhook (/exec) adresini girip kaydedin.")
            if yol == "/api/uets/ayar":
                return self._json(UETS_ZAMAN.ayar_yaz(int(govde.get("aralik_dk") or 0)))
            if yol == "/api/uets/otp":
                kod = re.sub(r"\D", "", str(govde.get("kod") or ""))
                if not 4 <= len(kod) <= 8:
                    raise ValueError("Geçersiz kod")
                (AVUKAT_DIR / "uets_otp.txt").write_text(kod, encoding="utf-8")
                return self._json({"ok": True})
            if yol == "/api/tebligat/liste":
                return self._json(tebligat_liste_onbellekli(bool(govde.get("tazele"))))
            if yol.startswith("/api/tebligat/"):
                r = tebligat_panel(yol.rsplit("/", 1)[-1], str(govde.get("barkod") or ""))
                _TEB_ONBELLEK["zaman"] = 0          # değişiklik yapıldı: liste bir sonraki istekte tazelenir
                return self._json(r)
            if yol == "/api/drive/esitle":
                # Arka planda, ilerlemeli; tüm eksikler (limitsiz) — /api/drive/esitle_durum ile izlenir
                return self._json(_drive_indeks.esitle_arkaplan(katalog_yolu(), evrak_veri_dizini(), int(govde.get("limit") or 100000)))
            if yol == "/api/drive/kopya_temizle":
                ayar = _drive_indeks.drive_ayar_oku(evrak_veri_dizini())
                if not ayar.get("google_drive_webhook"):
                    raise ValueError("Webhook ayarlı değil.")
                return self._json(_drive_indeks.kopya_temizle(ayar["google_drive_webhook"]))
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
                sonuc = _entegrasyon.ayar_kaydet(AVUKAT_DIR, govde)
                AYAR_YEDEK.tetikle()
                # ... ve tersi: nöbetçi (uyap_watcher) Telegram'ı watcher_config.json'dan okur
                tg = {k2: str(govde[k1]).strip() for k1, k2 in (("telegram_bot_token", "telegram_token"), ("telegram_chat_id", "telegram_chat_id"))
                      if str(govde.get(k1) or "").strip() and "••••" not in str(govde.get(k1))}
                if tg:
                    _drive_indeks.drive_ayar_yaz(evrak_veri_dizini(), tg)
                return self._json(sonuc)
            if yol == "/api/entegrasyon/test":
                return self._json(_entegrasyon.baglanti_testi(AVUKAT_DIR))
            if yol == "/api/telegram/test":
                return self._json(_entegrasyon.telegram_gonder(AVUKAT_DIR, "🔔 <b>CanEditor test bildirimi</b>\nTelegram bağlantısı çalışıyor."))
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
    _ld_geri_yukle(os.environ)
    if argv[0] == "-c":
        # "python -c KOD" karşılığı (DNS tanısı vb.). Eskiden "-c" betik adı sanılıp çöküyordu.
        if len(argv) < 2:
            return 2
        sys.argv = ["-c", *argv[2:]]
        sys.path.insert(0, os.getcwd())
        if hasattr(sys, "frozen"):
            del sys.frozen
        exec(compile(argv[1], "<-c>", "exec"), {"__name__": "__main__"})
        return 0
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
    UETS_ZAMAN.baslat()
    DUZEN_ZAMAN.baslat()
    DRIVE_ZAMAN.baslat()
    NABIZ.baslat()
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
