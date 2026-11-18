#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive Sürekli Senkronizasyon & Drive → SQLite Veritabanı İndeksleyici
============================================================================
Google Drive arşiv klasöründeki (ör. G:\\Drive'ım\\UYAP_Arsiv) tüm dosyaları
yerel bir SQLite veritabanına (drive_indeks.db) artımlı olarak indeksler.
Böylece:
  * Google Drive'daki yüz binlerce evrak Türkçe-duyarsız ve anında aranır.
  * Klasör ve dosya adlarından otomatik esas no (2025/123) ve mahkeme tahmini yapılır.
  * CanEditor içinden herhangi bir Drive dosyası doğrudan açılabilir veya paylaşılabilir.
  * UYAP'tan yerel indirilen ama henüz Drive'a gitmemiş evraklar yerel klasöre ya da
    Apps Script Webhook'una (Android/uzak cihaz) tek tıkla / arka planda eşitlenir.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path

try:
    import dns_cozucu
    dns_cozucu.yama_kur()
except Exception:
    pass

_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
    "Î": "i", "î": "i", "Û": "u", "û": "u",
})
_ESAS_RX = re.compile(r"(?<!\d)(19\d{2}|20\d{2})[-/_ ](\d{1,6})(?!\d)")

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS drive_dosya (
    rel_yol TEXT PRIMARY KEY,
    ad TEXT NOT NULL,
    klasor TEXT NOT NULL DEFAULT '',
    uzanti TEXT NOT NULL DEFAULT '',
    boyut INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    esas_no TEXT NOT NULL DEFAULT '',
    ara TEXT NOT NULL DEFAULT '',
    indeks_zaman TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_dd_uzanti ON drive_dosya(uzanti);
CREATE INDEX IF NOT EXISTS ix_dd_esas ON drive_dosya(esas_no);
CREATE INDEX IF NOT EXISTS ix_dd_mtime ON drive_dosya(mtime DESC);
CREATE TABLE IF NOT EXISTS drive_meta (
    anahtar TEXT PRIMARY KEY,
    deger TEXT
);
"""


def fold(metin) -> str:
    return re.sub(r"\s+", " ", str(metin or "").translate(_FOLD).lower()).strip()


def _esas_cikar(yol_metni: str) -> str:
    m = _ESAS_RX.search(yol_metni or "")
    return f"{m.group(1)}/{m.group(2)}" if m else ""


@contextlib.contextmanager
def _db_ac(db_yolu: Path):
    db_yolu.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(db_yolu), timeout=15)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(SCHEMA)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def drive_ayar_oku(evrak_veri_dizini: Path) -> dict:
    p = evrak_veri_dizini / "watcher_config.json"
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}
    return {
        "google_drive_dir": str(cfg.get("google_drive_dir") or ""),
        "google_drive_webhook": str(cfg.get("google_drive_webhook") or ""),
        "interval_minutes": int(cfg.get("interval_minutes") or 15),
        "auto_download_missing": bool(cfg.get("auto_download_missing", True)),
        "drive_auto_index": bool(cfg.get("drive_auto_index", True)),
        "telegram_token_var": bool(cfg.get("telegram_token")),
        "telegram_chat_id": str(cfg.get("telegram_chat_id") or ""),
    }


def drive_ayar_yaz(evrak_veri_dizini: Path, girdi: dict) -> dict:
    evrak_veri_dizini.mkdir(parents=True, exist_ok=True)
    p = evrak_veri_dizini / "watcher_config.json"
    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cfg = {}

    if "google_drive_dir" in girdi:
        d = str(girdi["google_drive_dir"] or "").strip()
        if d.startswith("http://") or d.startswith("https://"):
            # Kullanıcı web URL'sini yerel klasör kutusuna yapıştırmış
            if not cfg.get("google_drive_webhook"):
                cfg["google_drive_webhook"] = d
            cfg["google_drive_dir"] = ""
        else:
            cfg["google_drive_dir"] = d
    if "google_drive_webhook" in girdi:
        url = str(girdi["google_drive_webhook"] or "").strip()
        if url and not (url.startswith("https://") or url.startswith("http://")):
            raise ValueError("Webhook adresi https:// ile başlamalı")
        cfg["google_drive_webhook"] = url
    if "interval_minutes" in girdi and girdi["interval_minutes"]:
        cfg["interval_minutes"] = max(3, min(240, int(girdi["interval_minutes"])))
    if "auto_download_missing" in girdi:
        cfg["auto_download_missing"] = bool(girdi["auto_download_missing"])
    if "drive_auto_index" in girdi:
        cfg["drive_auto_index"] = bool(girdi["drive_auto_index"])
    if girdi.get("telegram_token"):
        cfg["telegram_token"] = str(girdi["telegram_token"]).strip()
    if "telegram_chat_id" in girdi:
        cfg["telegram_chat_id"] = str(girdi["telegram_chat_id"] or "").strip()

    gecici = p.with_suffix(".tmp")
    gecici.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, p)
    return drive_ayar_oku(evrak_veri_dizini)


def indeksle(db_yolu: Path, drive_dizini: Path, max_dosya: int = 200_000) -> dict:
    """Google Drive klasörünü artımlı olarak SQLite veritabanına indeksler."""
    kok = Path(drive_dizini)
    if not kok.is_dir():
        try:
            kok.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise ValueError(f"Drive klasörü bulunamadı ve oluşturulamadı: {kok}")

    t0 = time.monotonic()
    simdi_iso = time.strftime("%Y-%m-%dT%H:%M:%S")
    yeni = guncel = silinen = 0

    with _db_ac(db_yolu) as c:
        mevcut = {r["rel_yol"]: (r["boyut"], r["mtime"]) for r in c.execute("SELECT rel_yol, boyut, mtime FROM drive_dosya")}
        gorulen: set[str] = set()
        eklenecek: list[tuple] = []
        yigin = [kok]
        sayac = 0

        while yigin and sayac < max_dosya:
            d = yigin.pop()
            try:
                with os.scandir(d) as it:
                    for g in it:
                        ad = g.name
                        if ad.startswith(".") or ad in ("desktop.ini", "Thumbs.db", "$RECYCLE.BIN"):
                            continue
                        if g.is_dir(follow_symlinks=False):
                            yigin.append(Path(g.path))
                        elif g.is_file(follow_symlinks=False):
                            sayac += 1
                            st = g.stat()
                            rel = Path(g.path).relative_to(kok).as_posix()
                            gorulen.add(rel)
                            eski = mevcut.get(rel)
                            if eski and eski[0] == st.st_size and abs(eski[1] - st.st_mtime) < 1.0:
                                continue
                            klasor = str(Path(rel).parent.as_posix())
                            if klasor == ".":
                                klasor = ""
                            uz = Path(ad).suffix.lower().lstrip(".")
                            esas = _esas_cikar(rel)
                            ara_metin = fold(f"{rel} {esas}")
                            eklenecek.append((rel, ad, klasor, uz, st.st_size, st.st_mtime, esas, ara_metin, simdi_iso))
                            if eski:
                                guncel += 1
                            else:
                                yeni += 1
                            if len(eklenecek) >= 500:
                                c.executemany(
                                    "INSERT OR REPLACE INTO drive_dosya(rel_yol,ad,klasor,uzanti,boyut,mtime,esas_no,ara,indeks_zaman) "
                                    "VALUES (?,?,?,?,?,?,?,?,?)",
                                    eklenecek,
                                )
                                eklenecek.clear()
            except OSError:
                continue

        if eklenecek:
            c.executemany(
                "INSERT OR REPLACE INTO drive_dosya(rel_yol,ad,klasor,uzanti,boyut,mtime,esas_no,ara,indeks_zaman) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                eklenecek,
            )

        eksik_yollar = [k for k in mevcut if k not in gorulen]
        if eksik_yollar and sayac < max_dosya:
            silinen = len(eksik_yollar)
            for i in range(0, len(eksik_yollar), 500):
                parca = eksik_yollar[i:i + 500]
                c.execute(f"DELETE FROM drive_dosya WHERE rel_yol IN ({','.join('?' * len(parca))})", parca)

        c.execute("INSERT OR REPLACE INTO drive_meta(anahtar, deger) VALUES ('son_indeks', ?)", (simdi_iso,))
        c.execute("INSERT OR REPLACE INTO drive_meta(anahtar, deger) VALUES ('kok_dizin', ?)", (str(kok),))
        toplam = c.execute("SELECT COUNT(*) FROM drive_dosya").fetchone()[0]
        toplam_boyut = c.execute("SELECT COALESCE(SUM(boyut), 0) FROM drive_dosya").fetchone()[0]

    return {
        "toplam": toplam,
        "boyut_mb": round(toplam_boyut / 1_048_576, 1),
        "yeni": yeni,
        "guncellenen": guncel,
        "silinen": silinen,
        "son_indeks": simdi_iso,
        "sure_ms": round((time.monotonic() - t0) * 1000),
    }


def indeks_ozeti(db_yolu: Path) -> dict:
    if not db_yolu.is_file():
        return {"hazir": False, "toplam": 0, "boyut_mb": 0.0, "son_indeks": None, "uzantilar": []}
    with _db_ac(db_yolu) as c:
        toplam = c.execute("SELECT COUNT(*) FROM drive_dosya").fetchone()[0]
        boyut = c.execute("SELECT COALESCE(SUM(boyut), 0) FROM drive_dosya").fetchone()[0]
        son = c.execute("SELECT deger FROM drive_meta WHERE anahtar='son_indeks'").fetchone()
        uzlar = [dict(r) for r in c.execute(
            "SELECT uzanti, COUNT(*) AS sayi FROM drive_dosya GROUP BY uzanti ORDER BY sayi DESC LIMIT 8"
        ).fetchall()]
    return {
        "hazir": True,
        "toplam": toplam,
        "boyut_mb": round(boyut / 1_048_576, 1),
        "son_indeks": son["deger"] if son else None,
        "uzantilar": uzlar,
    }


def ara(db_yolu: Path, q: str = "", uzanti: str = "", esas: str = "", limit: int = 100) -> dict:
    if not db_yolu.is_file():
        return {"hazir": False, "toplam": 0, "sonuclar": [], "mesaj": "Drive veritabanı henüz indekslenmedi. 'Drive'ı İndeksle' düğmesine tıklayın."}
    kosul, param = [], []
    if uzanti:
        kosul.append("uzanti = ?")
        param.append(uzanti.lower().lstrip("."))
    if esas:
        kosul.append("esas_no = ?")
        param.append(esas.strip())
    for kelime in [fold(w) for w in str(q or "").split() if w.strip()][:8]:
        if kelime.startswith("-") and len(kelime) > 1:
            kosul.append("ara NOT LIKE ?")
            param.append(f"%{kelime[1:]}%")
        elif kelime:
            kosul.append("ara LIKE ?")
            param.append(f"%{kelime}%")
    where = ("WHERE " + " AND ".join(kosul)) if kosul else ""
    with _db_ac(db_yolu) as c:
        toplam = c.execute("SELECT COUNT(*) FROM drive_dosya").fetchone()[0]
        rows = [dict(r) for r in c.execute(
            f"SELECT rel_yol, ad, klasor, uzanti, boyut, mtime, esas_no FROM drive_dosya {where} "
            "ORDER BY mtime DESC LIMIT ?",
            (*param, max(1, min(limit, 500))),
        ).fetchall()]
    return {"hazir": True, "toplam": toplam, "sonuclar": rows}


def guvenli_drive_dosyasi(drive_dizini: Path, rel_yol: str) -> Path | None:
    """Path traversal'a kapalı biçimde Drive klasörü içindeki dosyanın gerçek yolunu döner."""
    if not drive_dizini or not rel_yol:
        return None
    kok = Path(drive_dizini).resolve()
    hedef = (kok / rel_yol).resolve()
    try:
        hedef.relative_to(kok)
    except ValueError:
        return None
    return hedef if hedef.is_file() else None


def esitle_eksikler(katalog_db: Path, evrak_veri_dizini: Path, limit: int = 100) -> dict:
    """Yerel indirilen ancak henüz Google Drive'a kopyalanmamış/yüklenmemiş evrakları eşitler."""
    ayar = drive_ayar_oku(evrak_veri_dizini)
    dizin = Path(ayar["google_drive_dir"]) if ayar["google_drive_dir"] else None
    webhook = ayar["google_drive_webhook"]
    if not (webhook or (dizin and dizin.is_dir())):
        raise ValueError("Ne erişilebilir bir yerel Google Drive klasörü ne de Bulut Webhook adresi yapılandırılmış.")
    if not katalog_db.is_file():
        return {"aktarilan": 0, "atlanan": 0, "hata": 0, "mesaj": "UYAP evrak kataloğu henüz yok."}

    c = sqlite3.connect(str(katalog_db), timeout=15)
    c.row_factory = sqlite3.Row
    aktarilan = atlanan = hata = 0
    try:
        onek = str(dizin).rstrip("/\\") if (dizin and dizin.is_dir()) else ""
        if onek:
            rows = c.execute(
                """SELECT e.id, e.path, e.pdf_path, d.birim, d.dosya_no
                   FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey
                   WHERE e.durum='indirildi'
                     AND (e.pdf_path IS NOT NULL OR e.path IS NOT NULL)
                     AND COALESCE(e.pdf_path,'') NOT LIKE ? AND COALESCE(e.path,'') NOT LIKE ?
                   ORDER BY e.tarih DESC LIMIT ?""",
                (onek + "%", onek + "%", limit),
            ).fetchall()
        else:
            rows = c.execute(
                """SELECT e.id, e.path, e.pdf_path, d.birim, d.dosya_no
                   FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey
                   WHERE e.durum='indirildi' AND (e.pdf_path IS NOT NULL OR e.path IS NOT NULL)
                   ORDER BY e.tarih DESC LIMIT ?""",
                (limit,),
            ).fetchall()

        for r in rows:
            kaynak = Path(r["pdf_path"] or r["path"])
            if not kaynak.is_absolute():
                kaynak = katalog_db.parent / kaynak
            if not kaynak.is_file():
                atlanan += 1
                continue
            birim = re.sub(r'[<>:"/\\|?*]', "_", str(r["birim"] or "Diger")).strip()[:60] or "Diger"
            dno = re.sub(r'[<>:"/\\|?*]', "_", str(r["dosya_no"] or "Genel")).strip()[:40] or "Genel"
            rel_klasor = f"DAVA_EVRAKLARI/{birim}/{dno}"

            if dizin and dizin.is_dir():
                hedef = dizin / rel_klasor / kaynak.name
                try:
                    if hedef.is_file() and hedef.stat().st_size == kaynak.stat().st_size:
                        atlanan += 1
                        continue
                    hedef.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(kaynak, hedef)
                    aktarilan += 1
                except OSError:
                    hata += 1
            elif webhook:
                try:
                    import base64
                    import urllib.request
                    govde = json.dumps({
                        "filename": kaynak.name,
                        "folder_path": rel_klasor,
                        "content": base64.b64encode(kaynak.read_bytes()).decode("ascii"),
                    }).encode("utf-8")
                    istek = urllib.request.Request(webhook, data=govde, headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(istek, timeout=60) as resp:
                        if resp.status == 200:
                            aktarilan += 1
                        else:
                            hata += 1
                except Exception:
                    hata += 1

        # Katalog yedeğini de yerel Drive'a al
        if dizin and dizin.is_dir():
            try:
                yedek = dizin / "uyap_katalog_yedek.db"
                with sqlite3.connect(str(yedek)) as dst:
                    c.backup(dst)
            except Exception:
                pass
    finally:
        c.close()

    return {"aktarilan": aktarilan, "atlanan": atlanan, "hata": hata}
