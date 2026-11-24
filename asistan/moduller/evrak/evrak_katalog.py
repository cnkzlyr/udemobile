#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
"""
UYAP Evrak Kataloğu
-------------------
Tüm dava dosyalarındaki evrakları ve eklerini (yüz binlerce kayıt) indirmeden önce
yerel bir SQLite veritabanına yazar. Böylece:

  * Taraf / müvekkil / açıklama / içerik / tarih / birim / evrak türü / uzantı /
    açık-kapalı gibi filtrelerle saniyeler içinde süzülüp seçilerek indirilir.
  * Her evrak yalnızca BİR KEZ indirilir:
      - Kalıcı anahtar: asıl evrak için (gönderen birim, birim evrak no, tarih, tür),
        ek için (UYAP'ın gerçek ana evrak no'su, ek sırası). UYAP'ın şifreli
        evrakId'si oturumdan oturuma değiştiği için kullanılmaz.
      - İstinaf / birleşen / talimat dosyalarında görünen aynı evrak tek kayıttır.
      - Başka evrakın ekinde tekrar gelen aynı dosya: indirilen içerik SHA-256 ile
        karşılaştırılır, aynısı varsa ikinci kopya diske yazılmaz ("mükerrer" olarak işaretlenir).
      - Ek adı benzersiz bir dosya adıysa (ör. 2025070416582311037.tif) indirmeden
        önce de mükerrer sayılır.
  * İndirilen UDF'ler PDF'e, TIF/TIFF'ler (çok sayfalı) A4 PDF'e aynı adla dönüştürülür.
  * Ekler, ait oldukları evrakın adıyla başlar:  <asıl evrak adı>__EK01_<ek adı>.tif
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import os
import random
import re
import sqlite3
import subprocess
import threading
import time
import zipfile
from pathlib import Path

import logging
import shutil
import sys
from logging.handlers import RotatingFileHandler

BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or BASE_DIR)
KATALOG_DB = DATA_DIR / "uyap_katalog.db"
CACHE_DIR = DATA_DIR / ".onbellek"
LOG_DIR = DATA_DIR / "loglar"

# Ayrıntılı (verbose) günlük: ekranda görünmeyen bağlantı/oturum/deneme ayrıntıları da buraya yazılır.
klog = logging.getLogger("uyap.katalog")
if not klog.handlers:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        _h = RotatingFileHandler(LOG_DIR / "katalog.log", maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8")
        _h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(threadName)s: %(message)s"))
        klog.addHandler(_h)
    except OSError:
        pass
    klog.setLevel(logging.DEBUG)
    klog.propagate = False

# ---------------------------------------------------------------------------
# Metin yardımcıları
# ---------------------------------------------------------------------------
_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a",
    "Î": "i", "î": "i", "Û": "u", "û": "u",
})


def fold(text) -> str:
    """Türkçe harf/büyük-küçük farkını yok sayan arama biçimi ('ÇAĞLAR' -> 'caglar')."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text).translate(_FOLD).lower()).strip()


def iso_date(val) -> str:
    """'10/07/2025', '2025-07-10 12:00', '10.07.2025' -> '2025-07-10'."""
    s = str(val or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    m = re.match(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""


def safe_part(value, max_len: int = 60, default: str = "_") -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip()
    s = re.sub(r"\s+", " ", s).strip(". ")
    if len(s) > max_len:
        s = s[:max_len].rstrip(". _")
    return s or default


def win_extended_path(p: Path | str) -> str:
    """Windows MAX_PATH (260 karakter) sınırlamasını aşmak için \\\\?\\ önekini uygular."""
    sp = str(p)
    if os.name == "nt":
        abs_p = os.path.abspath(sp)
        if not abs_p.startswith("\\\\?\\"):
            if abs_p.startswith("\\\\"):
                return "\\\\?\\UNC\\" + abs_p[2:]
            return "\\\\?\\" + abs_p
        return abs_p
    return sp


def safe_write_bytes(path: Path | str, data: bytes) -> Path:
    """Windows'ta 260 karakterden uzun yollara dahi güvenli dosya yazar."""
    p = Path(path)
    ext_p = win_extended_path(p)
    parent_dir = os.path.dirname(ext_p)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(ext_p, "wb") as f:
        f.write(data)
    return p


def safe_replace_file(src: Path | str, dst: Path | str) -> None:
    """Windows ve POSIX üzerinde uzun yollu dosyayı güvenle taşır/değiştirir."""
    ext_src = win_extended_path(src)
    ext_dst = win_extended_path(dst)
    parent_dir = os.path.dirname(ext_dst)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    for deneme in range(3):
        try:
            os.replace(ext_src, ext_dst)
            return
        except OSError:
            if deneme == 2:
                try:
                    if os.path.exists(ext_dst):
                        os.remove(ext_dst)
                    os.replace(ext_src, ext_dst)
                    return
                except Exception:
                    pass
                raise
            time.sleep(0.1 * (deneme + 1))


_EXT_RX = re.compile(r"\.(tiff?|pdf|udf|eyp|jpe?g|png|gif|bmp|docx?|xlsx?|odt|rtf|txt|zip|rar|7z|mp3|mp4|wav|avi|mov|xml|html?)$", re.I)


def ext_hint(name: str) -> str:
    m = _EXT_RX.search(str(name or "").strip())
    if not m:
        return ""
    e = m.group(1).lower()
    return {"tiff": "tif", "jpeg": "jpg", "htm": "html"}.get(e, e)


def strip_ext(name: str) -> str:
    return _EXT_RX.sub("", str(name or "").strip())


# ---------------------------------------------------------------------------
# Kategoriler: gerçek UYAP evrak türlerinden çıkarılmış sınıflandırma (evrak_turleri.py)
# ---------------------------------------------------------------------------
from evrak_turleri import (  # noqa: E402
    KATEGORILER, KATEGORI_ADI, KLASOR_ADI, kategori_of, ek_kategori_of,
)

__all__ = ["KATEGORILER", "KATEGORI_ADI", "KLASOR_ADI", "kategori_of", "ek_kategori_of", "Katalog", "Motor",
           "export_csv", "fold", "iso_date", "DURUMLAR"]

KATALOG_SURUMU = 2  # sınıflandırma değişince artırılır; açılışta kategoriler yeniden hesaplanır


# ---------------------------------------------------------------------------
# Veritabanı
# ---------------------------------------------------------------------------
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
CREATE TABLE IF NOT EXISTS dosya(
  dkey TEXT PRIMARY KEY, birim TEXT, dosya_no TEXT, dosya_tur TEXT, durum TEXT, yargi TEXT,
  acilis TEXT, dosya_id TEXT, taraflar TEXT, taraf_ara TEXT, muvekkil TEXT, muvekkil_ara TEXT,
  evrak_sayisi INTEGER DEFAULT 0, taranma TEXT, tarama TEXT, oturum TEXT);
CREATE TABLE IF NOT EXISTS evrak(
  id INTEGER PRIMARY KEY, skey TEXT UNIQUE NOT NULL, dkey TEXT, grup TEXT, is_ek INTEGER,
  parent_skey TEXT, sira INTEGER, tur TEXT, ust_tur TEXT, aciklama TEXT, tarih TEXT, tip TEXT,
  gonderen TEXT, gonderen_dosya TEXT, birim_evrak_no TEXT, gercek_id TEXT,
  kategori TEXT, ust_kategori TEXT, uzanti TEXT, ad_anahtar TEXT, ara TEXT,
  ilk_ad INTEGER DEFAULT 1,
  evrak_id TEXT, oturum TEXT,
  durum TEXT DEFAULT 'yeni', dup_of TEXT, path TEXT, pdf_path TEXT, sha256 TEXT, size INTEGER,
  indirildi TEXT, ilk_gorulme TEXT, son_gorulme TEXT, hata TEXT);
CREATE TABLE IF NOT EXISTS evrak_dosya(skey TEXT, dkey TEXT, PRIMARY KEY(skey, dkey)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS ix_e_dkey ON evrak(dkey);
CREATE INDEX IF NOT EXISTS ix_e_tarih ON evrak(tarih);
CREATE INDEX IF NOT EXISTS ix_e_kat ON evrak(kategori);
CREATE INDEX IF NOT EXISTS ix_e_durum ON evrak(durum);
CREATE INDEX IF NOT EXISTS ix_e_sha ON evrak(sha256);
CREATE INDEX IF NOT EXISTS ix_e_ad ON evrak(ad_anahtar);
CREATE INDEX IF NOT EXISTS ix_e_parent ON evrak(parent_skey);
CREATE INDEX IF NOT EXISTS ix_e_ust ON evrak(ust_tur);
CREATE INDEX IF NOT EXISTS ix_ed_dkey ON evrak_dosya(dkey);
CREATE VIRTUAL TABLE IF NOT EXISTS evrak_fts USING fts5(metin, tokenize="unicode61 remove_diacritics 2");
CREATE TABLE IF NOT EXISTS tebligat(
  id INTEGER PRIMARY KEY,
  barkod_delil TEXT UNIQUE,
  dkey TEXT,
  birim TEXT,
  dosya_no TEXT,
  muvekkil TEXT,
  muhatap TEXT,
  tebligat_turu TEXT,
  gonderim_tarihi TEXT,
  teblig_tarihi TEXT,
  sonuc TEXT,
  yasal_sure_notu TEXT,
  evrak_id TEXT,
  evrak_adi TEXT,
  path TEXT,
  pdf_path TEXT,
  ozet TEXT,
  durum TEXT DEFAULT 'yeni',
  eklenme TEXT
);
CREATE INDEX IF NOT EXISTS ix_teb_dkey ON tebligat(dkey);
CREATE INDEX IF NOT EXISTS ix_teb_barkod ON tebligat(barkod_delil);

CREATE TABLE IF NOT EXISTS durusma(
  id INTEGER PRIMARY KEY,
  dkey TEXT,
  birim TEXT,
  dosya_no TEXT,
  tarih TEXT,
  saat TEXT,
  yer TEXT,
  aciklama TEXT,
  durum TEXT DEFAULT 'bekliyor',
  UNIQUE(dkey, tarih, saat)
);
CREATE INDEX IF NOT EXISTS ix_dur_tarih ON durusma(tarih);
"""

DURUMLAR = {
    "yeni": "İndirilmedi",
    "indirildi": "İndirildi",
    "mukerrer": "Mükerrer (başka kopyası var)",
    "yok": "UYAP'ta dosyası yok",
    "hata": "Hata",
}


class Katalog:
    """Thread başına ayrı bağlantı kullanır (GUI + indirme iş parçacığı)."""

    def __init__(self, path: Path = KATALOG_DB):
        self.path = Path(path)
        self._local = threading.local()
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(dosya)")}
        if "tarama" not in cols:  # eski kataloglar için şema güncellemesi
            self.db.execute("ALTER TABLE dosya ADD COLUMN tarama TEXT")
            self.db.execute("UPDATE dosya SET tarama='tamam' WHERE evrak_sayisi > 0")
        self.db.execute("UPDATE evrak SET hata=NULL WHERE hata='UYAP listesinde artık yok' AND durum='yeni'")
        ecols = {r[1] for r in self.db.execute("PRAGMA table_info(evrak)")}
        if "cache_path" not in ecols:
            self.db.execute("ALTER TABLE evrak ADD COLUMN cache_path TEXT")
        self.db.commit()
        if self.db.execute("PRAGMA user_version").fetchone()[0] < KATALOG_SURUMU:
            self.reclassify()

    def reclassify(self):
        """Kategorileri güncel sınıflandırmayla tek geçişte yeniden hesaplar (tür adları önbellekli)."""
        self.db.create_function("kat_of", 1, kategori_of, deterministic=True)
        self.db.create_function("ek_kat_of", 2, ek_kategori_of, deterministic=True)
        with self.db:
            self.db.execute("""UPDATE evrak SET
                  ust_tur = CASE WHEN is_ek=0 THEN tur ELSE ust_tur END,
                  kategori = CASE WHEN is_ek=0 THEN kat_of(tur) ELSE ek_kat_of(tur, ust_tur) END,
                  ust_kategori = kat_of(CASE WHEN is_ek=0 THEN tur ELSE ust_tur END)""")
            self.db.execute(f"PRAGMA user_version={KATALOG_SURUMU}")

    def set_tarama(self, dkey: str, durum: str):
        with self.db:
            cur = self.db.execute("UPDATE dosya SET tarama=? WHERE dkey=?", (durum, dkey))
            if cur.rowcount == 0:
                self.db.execute(
                    "INSERT INTO dosya(dkey, birim, dosya_no, tarama) VALUES(?, 'Bilinmeyen', 'Bilinmeyen', ?) "
                    "ON CONFLICT(dkey) DO UPDATE SET tarama=excluded.tarama",
                    (dkey, durum)
                )

    def eksik_dkeys(self) -> set:
        return {r[0] for r in self.db.execute(
            "SELECT dkey FROM dosya WHERE tarama IS NULL OR tarama <> 'tamam'")}

    @property
    def db(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(str(self.path), timeout=60)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=60000")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return c

    def _execute_with_retry(self, fn, max_retries: int = 12, delay: float = 0.5):
        """Veritabanı kilitlenme (database is locked / busy) durumlarında otomatik yeniden dener."""
        for attempt in range(max_retries):
            try:
                return fn()
            except sqlite3.OperationalError as e:
                err_str = str(e).lower()
                if ("locked" in err_str or "busy" in err_str) and attempt < max_retries - 1:
                    time.sleep(delay * (1 + attempt * 0.5))
                    continue
                raise

    # -------------------------------------------------------------- dosyalar
    @staticmethod
    def dkey_of(birim: str, dosya_no: str) -> str:
        return f"{fold(birim)}|{str(dosya_no or '').strip()}"

    def upsert_dosya(self, case: dict, taraflar: list | None, avukat: str, yargi: str, oturum: str) -> str:
        birim = str(case.get("birimAdi") or case.get("mahkemeAdi") or "").strip()
        dno = str(case.get("dosyaNo") or case.get("dosyaNO") or "").strip()
        dkey = self.dkey_of(birim, dno)
        durum_txt = str(case.get("dosyaDurum") or "")
        if durum_txt.lower().startswith("kapal"):
            durum = "Kapalı"
        elif durum_txt.lower().startswith("açık") or durum_txt.lower().startswith("acik"):
            durum = "Açık"
        else:
            durum = str(case.get("dosyaDurumGenel") or "")
        taraf_txt, muv = "", []
        av = fold(avukat)
        if isinstance(taraflar, list):
            parts = []
            for t in taraflar:
                if not isinstance(t, dict):
                    continue
                adi, rol, vek = str(t.get("adi") or ""), str(t.get("rol") or ""), str(t.get("vekil") or "")
                parts.append(f"{adi} ({rol}){' vekil: ' + vek.strip('[]') if vek else ''}")
                if av and av in fold(vek):
                    muv.append(f"{adi} ({rol})")
            taraf_txt = "; ".join(parts)
        cur = self.db.execute("SELECT taraflar, muvekkil FROM dosya WHERE dkey=?", (dkey,)).fetchone()
        if cur and taraflar is None:  # taraf sorgusu başarısızsa eskisini koru
            taraf_txt, muv_txt = cur["taraflar"] or "", cur["muvekkil"] or ""
        else:
            muv_txt = "; ".join(muv)
        self.db.execute(
            """INSERT INTO dosya(dkey,birim,dosya_no,dosya_tur,durum,yargi,acilis,dosya_id,taraflar,taraf_ara,
                                 muvekkil,muvekkil_ara,taranma,oturum)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(dkey) DO UPDATE SET dosya_tur=excluded.dosya_tur, durum=excluded.durum,
                 yargi=excluded.yargi, acilis=excluded.acilis, dosya_id=excluded.dosya_id,
                 taraflar=excluded.taraflar, taraf_ara=excluded.taraf_ara, muvekkil=excluded.muvekkil,
                 muvekkil_ara=excluded.muvekkil_ara, taranma=excluded.taranma, oturum=excluded.oturum""",
            (dkey, birim, dno, str(case.get("dosyaTur") or ""), durum, yargi,
             iso_date(case.get("dosyaAcilisTarihi")), str(case.get("dosyaId") or case.get("dosyaID") or ""),
             taraf_txt, fold(taraf_txt), muv_txt, fold(muv_txt),
             dt.datetime.now().isoformat(timespec="seconds"), oturum),
        )
        return dkey

    # -------------------------------------------------------------- evraklar
    @staticmethod
    def _top_skey(ev: dict, tarih: str) -> str:
        no = str(ev.get("birimEvrakNo") or "").strip()
        ident = no or fold(ev.get("aciklama"))[:60]
        return f"T|{fold(ev.get('gonderenYerKisi'))}|{ident}|{tarih}|{fold(ev.get('tur'))}"

    def ingest_pages(self, dkey: str, pages: list, oturum: str) -> int:
        """list_dosya_evraklar.ajx yanıtını kataloğa yazar. Yazılan kayıt sayısını döner."""
        now = dt.datetime.now().isoformat(timespec="seconds")
        rows, links = [], []

        def tops():
            for p in pages or []:
                if isinstance(p, dict):
                    tum = p.get("tumEvraklar")
                    if isinstance(tum, dict):
                        for grup, lst in tum.items():
                            for ev in lst or []:
                                yield grup, ev
                    elif isinstance(tum, list):
                        for ev in tum:
                            yield "", ev
                elif isinstance(p, list):
                    for ev in p:
                        yield "", ev

        for grup, ev in tops():
            if not isinstance(ev, dict):
                continue
            tarih = iso_date(ev.get("onaylandigiTarih")) or iso_date(ev.get("sistemeGonderildigiTarih"))
            tur = str(ev.get("tur") or "Evrak").strip()
            acik = str(ev.get("aciklama") or "").strip()
            skey = self._top_skey(ev, tarih)
            ekler = [e for e in (ev.get("ekEvrakListesi") or []) if isinstance(e, dict)]
            gercek = str(ekler[0].get("anaEvrakId") or "") if ekler else ""
            kat = kategori_of(tur)
            gonderen = str(ev.get("gonderenYerKisi") or "")
            gdno = str(ev.get("gonderenDosyaNo") or "")
            rows.append((
                skey, dkey, grup, 0, None, 0, tur, tur, acik, tarih, str(ev.get("tip") or ""),
                gonderen, gdno, str(ev.get("birimEvrakNo") or ""), gercek, kat, kat, ext_hint(tur) or "",
                None, fold(" ".join((tur, acik, gonderen, gdno, grup))),
                str(ev.get("evrakId") or ""), oturum, now, now,
            ))
            links.append((skey, dkey))
            for ek in ekler:
                ana = str(ek.get("anaEvrakId") or gercek or "")
                sira = int(ek.get("sira") or 0)
                ek_tur = str(ek.get("ekTuru") or "Ek").strip()
                ek_skey = f"K|{ana}|{sira}" if ana else f"K|{skey}|{sira}"
                # Benzersiz görünen dosya adları (tarama zaman damgası gibi) indirmeden önce mükerrer sayılır
                m = re.search(r"\d{12,}", ek_tur)
                ad_key = f"F|{m.group(0)}" if m else None
                rows.append((
                    ek_skey, dkey, grup, 1, skey, sira, ek_tur, tur, acik, tarih, "",
                    gonderen, gdno, str(ev.get("birimEvrakNo") or ""), ana, ek_kategori_of(ek_tur, tur), kat,
                    ext_hint(ek_tur), ad_key, fold(" ".join((ek_tur, tur, acik, gonderen, gdno, grup))),
                    str(ek.get("evrakId") or ""), oturum, now, now,
                ))
                links.append((ek_skey, dkey))

        if not rows:
            return 0
        def _do_ingest():
            with self.db:
                self.db.executemany(
                    """INSERT INTO evrak(skey,dkey,grup,is_ek,parent_skey,sira,tur,ust_tur,aciklama,tarih,tip,
                         gonderen,gonderen_dosya,birim_evrak_no,gercek_id,kategori,ust_kategori,uzanti,ad_anahtar,ara,
                         evrak_id,oturum,ilk_gorulme,son_gorulme)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(skey) DO UPDATE SET evrak_id=excluded.evrak_id, oturum=excluded.oturum,
                         son_gorulme=excluded.son_gorulme,
                         -- Şifreli evrakId, görüldüğü dosyanın bağlamına aittir: ikisi birlikte güncellenir
                         dkey=excluded.dkey""",
                    rows,
                )
                self.db.executemany("INSERT OR IGNORE INTO evrak_dosya(skey,dkey) VALUES(?,?)", links)
                # v4.9.3: mükerrerler LİSTE OKUNURKEN ayıklanır (indirme sırasında bekletilmez)
                self._liste_mukerrer(dkey, [r[0] for r in rows])
                self.db.execute(
                    "UPDATE dosya SET evrak_sayisi=(SELECT COUNT(*) FROM evrak_dosya WHERE dkey=?) WHERE dkey=?",
                    (dkey, dkey),
                )
        self._execute_with_retry(_do_ingest)
        return len(rows)

    LISTE_TAHMIN_ISARETI = "tahmini mükerrer (indirilmedi, sonra doğrulanacak)"

    def _liste_mukerrer(self, dkey: str, skeys: list) -> int:
        """v4.9.3 — "Liste okudukça mükerrere bak": bir dosyanın evrak listesi kataloğa yazılırken, yalnızca o
        listenin satırları için iki ucuz ve güvenli kural uygulanır; böylece indirme döngüsü mükerrer aramak için
        hiç beklemez (eskiden her mükerrerde 247 bin satırlık tabloda GROUP BY yeniden çalışıyordu):
          1) Aynı benzersiz dosya adı anahtarı (ad_anahtar: taramadaki 12+ haneli zaman damgası) → ilki asıl.
          2) Bu dosyada geçmişte en az 2 kez AYNI içerikle (SHA-256) gelmiş ek kalıbı (tür + gönderen) → asıl
             kopyaya bağlanır, indirilmez; boştayken tahminleri_dogrula() ile doğrulanır.
        EN: per-listing duplicate marking (name key + learned attachment pattern) so downloads never stall."""
        if not skeys:
            return 0
        n = 0
        for i in range(0, len(skeys), 800):
            parca = skeys[i:i + 800]
            ph = ",".join("?" * len(parca))
            n += self.db.execute(f"""
                UPDATE evrak SET durum='mukerrer',
                  dup_of=(SELECT MIN(e2.skey) FROM evrak e2 WHERE e2.ad_anahtar=evrak.ad_anahtar AND e2.durum<>'mukerrer')
                WHERE skey IN ({ph}) AND ad_anahtar IS NOT NULL AND durum='yeni'
                  AND skey <> (SELECT MIN(e2.skey) FROM evrak e2 WHERE e2.ad_anahtar=evrak.ad_anahtar
                               AND e2.durum <> 'mukerrer')""", parca).rowcount or 0
        if os.environ.get("UYAP_MUKERRER_TAHMIN", "1") == "0":
            return n
        kaliplar = {}
        for r in self.db.execute("""SELECT lower(trim(tur)) t, lower(trim(COALESCE(gonderen,''))) g,
                                      COUNT(*) c, COUNT(DISTINCT sha256) d,
                                      MIN(CASE WHEN durum='indirildi' THEN skey END) asil,
                                      MIN(CASE WHEN durum='indirildi' THEN path END) yol
                                    FROM evrak WHERE dkey=? AND is_ek=1 AND sha256 IS NOT NULL
                                      AND durum IN ('indirildi','mukerrer')
                                    GROUP BY t, g HAVING c >= 2 AND d = 1 AND asil IS NOT NULL""", (dkey,)).fetchall():
            kaliplar[(r["t"] or "", r["g"] or "")] = (r["asil"], r["yol"])
        if not kaliplar:
            return n
        for (t, g) in [k for k in kaliplar if self.db.execute(
                "SELECT 1 FROM evrak WHERE dkey=? AND is_ek=1 AND hata='tahmin yanlış çıktı' AND lower(trim(tur))=? "
                "AND lower(trim(COALESCE(gonderen,'')))=? LIMIT 1", (dkey, k[0], k[1])).fetchone()]:
            kaliplar.pop((t, g), None)
        simdi = dt.datetime.now().isoformat(timespec="seconds")
        for i in range(0, len(skeys), 800):
            parca = skeys[i:i + 800]
            ph = ",".join("?" * len(parca))
            for r in self.db.execute(f"""SELECT id, lower(trim(tur)) t, lower(trim(COALESCE(gonderen,''))) g FROM evrak
                                        WHERE skey IN ({ph}) AND is_ek=1 AND durum='yeni'""", parca).fetchall():
                hedef = kaliplar.get((r["t"] or "", r["g"] or ""))
                if hedef:
                    self.db.execute("UPDATE evrak SET durum='mukerrer', dup_of=?, path=?, indirildi=?, hata=? WHERE id=?",
                                    (hedef[0], hedef[1], simdi, self.LISTE_TAHMIN_ISARETI, r["id"]))
                    n += 1
        return n

    def sync_disk(self, en_az_aralik_sn: int = 0) -> int:
        """Diskte artık bulunmayan (silinmiş/taşınmış) indirmeleri 'İndirilmedi' durumuna döndürür.
        Mükerrer kayıtlardan asıl kopyası silinenler de yeniden indirilebilir hale gelir.
        v4.9.3: en_az_aralik_sn verilirse bu süre dolmadan tekrar taranmaz — her indirme partisinin başında
        on binlerce yolu Google Drive sanal diskinde (G:) tek tek yoklamak indirmeyi dakikalarca bekletiyordu."""
        if en_az_aralik_sn and time.time() - getattr(self, "_son_sync_disk", 0) < en_az_aralik_sn:
            return 0
        self._son_sync_disk = time.time()
        rows = self.db.execute(
            "SELECT id, path FROM evrak WHERE durum IN ('indirildi','mukerrer') AND path IS NOT NULL").fetchall()
        exists: dict = {}
        gone = []
        for r in rows:
            pth = r["path"]
            if pth not in exists:
                exists[pth] = os.path.exists(pth)
            if not exists[pth]:
                gone.append(r["id"])
        if gone:
            with self.db:
                for i in range(0, len(gone), 900):
                    ch = gone[i:i + 900]
                    ph = ",".join("?" * len(ch))
                    self.db.execute(f"""UPDATE evrak SET durum='yeni', path=NULL, pdf_path=NULL, sha256=NULL,
                                        dup_of=NULL, indirildi=NULL, hata=NULL WHERE id IN ({ph})""", ch)
                    self.db.execute(f"DELETE FROM evrak_fts WHERE rowid IN ({ph})", ch)
        return len(gone)

    def finalize_scan(self):
        """Tarama sonrası mükerrer işaretleri ve 'aynı adlı ilk ek' bayraklarını hesaplar."""
        with self.db:
            # Aynı benzersiz dosya adına sahip ekler: ilki asıl, diğerleri mükerrer
            self.db.execute("""
                UPDATE evrak SET durum='mukerrer',
                  dup_of=(SELECT MIN(e2.skey) FROM evrak e2 WHERE e2.ad_anahtar=evrak.ad_anahtar)
                WHERE ad_anahtar IS NOT NULL AND durum='yeni'
                  AND skey <> (SELECT MIN(e2.skey) FROM evrak e2 WHERE e2.ad_anahtar=evrak.ad_anahtar
                                AND e2.durum <> 'mukerrer')""")
            # Tahmini mükerrer: aynı dosyada aynı adlı eklerden yalnızca ilki ilk_ad=1
            self.db.execute("UPDATE evrak SET ilk_ad=1")
            self.db.execute("""
                UPDATE evrak SET ilk_ad=0 WHERE is_ek=1 AND id NOT IN (
                  SELECT MIN(id) FROM evrak WHERE is_ek=1 GROUP BY dkey, lower(tur))""")

    # -------------------------------------------------------------- disk eşleştirme (eski indirmeler)
    def match_existing_disk(self, roots: list[Path], log=print) -> int:
        """Bu sistemden önce indirilmiş dosyaları (eski adlandırma) bulup 'indirildi' işaretler."""
        top_idx, ek_idx = {}, {}
        rx = re.compile(r"_(?:evrak_)?(\d+)$")
        for root in roots:
            if not root or not Path(root).exists():
                continue
            for dirpath, _d, files in os.walk(root):
                if "ISLEMLERIM" in dirpath.upper():
                    continue
                for fn in files:
                    stem, _, ext = fn.rpartition(".")
                    if not stem or ext.lower() in ("part", "csv", "json", "md", "ics", "pdf"):
                        continue
                    if not re.match(r"^\d{4}-\d{2}-\d{2}_", stem):
                        continue
                    m = rx.search(stem)
                    if not m:
                        continue
                    full = os.path.join(dirpath, fn)
                    num = m.group(1).lower()
                    if "_EK_" in stem:
                        ek_idx.setdefault(num, []).append((fold(stem), full))
                    else:
                        top_idx.setdefault((stem[:10], num), full)
        if not top_idx and not ek_idx:
            return 0
        n = 0
        cur = self.db.execute(
            "SELECT id, is_ek, tarih, birim_evrak_no, gercek_id, tur FROM evrak WHERE durum='yeni'")
        updates = []
        for r in cur:
            path = None
            if r["is_ek"]:
                cands = ek_idx.get(str(r["gercek_id"] or "").lower())
                if cands:
                    want = "_ek_" + fold(strip_ext(r["tur"]))[:25]
                    path = next((p for s, p in cands if want in s), None)
            else:
                path = top_idx.get((r["tarih"], str(r["birim_evrak_no"] or "").lower()))
            if path:
                pdf = str(Path(path).with_suffix(".pdf"))
                updates.append((path, pdf if os.path.exists(pdf) else None, r["id"]))
        with self.db:
            self.db.executemany(
                "UPDATE evrak SET durum='indirildi', path=?, pdf_path=?, hata='eski indirme' WHERE id=?", updates)
        n = len(updates)
        log(f"[✓] Diskte daha önce indirilmiş {n} evrak katalogda 'indirildi' olarak işaretlendi.")
        return n

    # -------------------------------------------------------------- sorgu / filtre
    def facets(self) -> dict:
        q = self.db.execute
        return {
            "birimler": [r[0] for r in q("SELECT DISTINCT birim FROM dosya ORDER BY birim")],
            "dosya_turleri": [r[0] for r in q("SELECT DISTINCT dosya_tur FROM dosya WHERE dosya_tur<>'' ORDER BY 1")],
            "yargi": [r[0] for r in q("SELECT DISTINCT yargi FROM dosya WHERE yargi<>'' ORDER BY 1")],
            "muvekkiller": sorted({m.strip() for (s,) in q("SELECT muvekkil FROM dosya WHERE muvekkil<>''")
                                   for m in s.split(";") if m.strip()}),
            "uzantilar": [r[0] for r in q("SELECT uzanti FROM evrak WHERE uzanti<>'' GROUP BY uzanti ORDER BY COUNT(*) DESC LIMIT 25")],
            "kategori_sayilari": {r[0]: r[1] for r in q("SELECT kategori, COUNT(*) FROM evrak GROUP BY kategori")},
        }

    def stats(self) -> dict:
        r = self.db.execute("""SELECT COUNT(*) n, SUM(is_ek) ek, SUM(durum='indirildi') ind,
               SUM(durum='mukerrer') muk, SUM(durum='yeni') yeni FROM evrak""").fetchone()
        d = self.db.execute("SELECT COUNT(*) FROM dosya").fetchone()[0]
        return {"evrak": r["n"] or 0, "ek": r["ek"] or 0, "indirildi": r["ind"] or 0,
                "mukerrer": r["muk"] or 0, "yeni": r["yeni"] or 0, "dosya": d}

    # Üç durumlu liste filtreleri: {"sec": {anahtar: {"dahil": [...], "haric": [...]}}}
    FASETLER = {
        "kategori": "e.kategori", "tur": "e.ust_tur", "uzanti": "e.uzanti", "durum": "e.durum",
        "birim": "d.birim", "dosya_tur": "d.dosya_tur", "yargi": "d.yargi", "dosya_durum": "d.durum",
    }

    def _faset_col(self, key: str, f: dict) -> str:
        if key == "kategori" and f.get("kategori_ust"):
            return "e.ust_kategori"
        return self.FASETLER[key]

    @staticmethod
    def split_terms(text) -> tuple[list, list]:
        """'ahmet -mehmet "ağır ceza"' -> (['ahmet', 'agir ceza'], ['mehmet']). Başında '-' olan hariç tutulur."""
        pos, neg = [], []
        for m in re.finditer(r'(-?)"([^"]+)"|(-?)([^\s"]+)', str(text or "")):
            minus = (m.group(1) or m.group(3) or "") == "-"
            term = fold(m.group(2) or m.group(4) or "")
            if term and term != "-":
                (neg if minus else pos).append(term)
        return pos, neg

    def build_where(self, f: dict) -> tuple[str, list]:
        """Filtre sözlüğünden SQL WHERE üretir. Metin aramaları Türkçe-duyarsızdır; '-kelime' hariç tutar."""
        w, p = [], []

        def text_filter(cols: list, text: str):
            pos, neg = self.split_terms(text)
            for tok in pos:
                w.append("(" + " OR ".join(f"{c} LIKE ?" for c in cols) + ")")
                p.extend([f"%{tok}%"] * len(cols))
            for tok in neg:
                w.append("NOT (" + " OR ".join(f"COALESCE({c},'') LIKE ?" for c in cols) + ")")
                p.extend([f"%{tok}%"] * len(cols))

        if f.get("aciklama"):
            text_filter(["e.ara"], f["aciklama"])
        if f.get("taraf"):
            text_filter(["e.ara", "d.taraf_ara"], f["taraf"])
        if f.get("muvekkil"):
            text_filter(["d.muvekkil_ara"], f["muvekkil"])
        if f.get("sadece_muvekkilli"):
            w.append("d.muvekkil <> ''")
        if f.get("icerik"):
            pos, neg = self.split_terms(f["icerik"])
            fts = lambda terms: " ".join('"' + t.replace('"', '') + '"' for t in terms)  # noqa: E731
            if pos:
                w.append("e.id IN (SELECT rowid FROM evrak_fts WHERE evrak_fts MATCH ?)")
                p.append(fts(pos))
            for t in neg:
                w.append("e.id NOT IN (SELECT rowid FROM evrak_fts WHERE evrak_fts MATCH ?)")
                p.append(fts([t]))
        if f.get("birim"):
            text_filter(["fold_ac(d.birim)"], f["birim"])
        if f.get("dosya_no"):
            pos, neg = self.split_terms(f["dosya_no"])
            for t in pos:
                w.append("(d.dosya_no LIKE ? OR e.gonderen_dosya LIKE ? OR e.grup LIKE ?)")
                p += [f"%{t}%"] * 3
            for t in neg:
                w.append("NOT (d.dosya_no LIKE ? OR COALESCE(e.gonderen_dosya,'') LIKE ? OR COALESCE(e.grup,'') LIKE ?)")
                p += [f"%{t}%"] * 3
        if f.get("tur"):
            text_filter(["fold_ac(e.tur)"], f["tur"])
        if f.get("baslangic"):
            w.append("e.tarih >= ?")
            p.append(f["baslangic"])
        if f.get("bitis"):
            w.append("e.tarih <= ?")
            p.append(f["bitis"])
        if f.get("son_gun"):
            try:
                gun = (dt.date.today() - dt.timedelta(days=int(f["son_gun"]))).isoformat()
                w.append("e.tarih >= ?")
                p.append(gun)
            except (TypeError, ValueError):
                pass
        for key, sel in (f.get("sec") or {}).items():
            if key not in self.FASETLER or not sel:
                continue
            col = f"COALESCE({self._faset_col(key, f)}, '')"
            dahil, haric = list(sel.get("dahil") or []), list(sel.get("haric") or [])
            if dahil:
                w.append(f"{col} IN ({','.join('?' * len(dahil))})")
                p += dahil
            if haric:
                w.append(f"{col} NOT IN ({','.join('?' * len(haric))})")
                p += haric
        # --- eski (CLI / önceki sürüm) anahtarları
        if f.get("dosya_tur"):
            w.append("d.dosya_tur = ?")
            p.append(f["dosya_tur"])
        if f.get("yargi"):
            w.append("d.yargi = ?")
            p.append(f["yargi"])
        if f.get("dosya_durum") in ("Açık", "Kapalı"):
            w.append("d.durum = ?")
            p.append(f["dosya_durum"])
        turler = f.get("turler") or []
        if turler:
            w.append(f"e.ust_tur {'NOT IN' if f.get('tur_secim_haric') else 'IN'} ({','.join('?' * len(turler))})")
            p += list(turler)
        kats = f.get("kategoriler") or []
        if kats:
            col = "e.ust_kategori" if f.get("kategori_ust") else "e.kategori"
            w.append(f"{col} {'NOT IN' if f.get('kategori_haric') else 'IN'} ({','.join('?' * len(kats))})")
            p += list(kats)
        if f.get("tur_haric"):
            for tok in [t.strip() for t in str(f["tur_haric"]).split(",") if t.strip()]:
                w.append("e.ara NOT LIKE ?")
                p.append(f"%{fold(tok)}%")
        uz = f.get("uzantilar") or []
        if uz:
            w.append(f"e.uzanti IN ({','.join('?' * len(uz))})")
            p += list(uz)
        ek = f.get("ek")
        if ek == "asil":
            w.append("e.is_ek = 0")
        elif ek == "ek":
            w.append("e.is_ek = 1")
        durum = f.get("durum")
        if durum and durum != "hepsi":
            w.append("e.durum = ?")
            p.append(durum)
        if f.get("mukerrer_gizle", True):
            w.append("e.durum <> 'mukerrer'")
        if f.get("ayni_ad_tek"):
            w.append("e.ilk_ad = 1")
        return (" AND ".join(w) if w else "1=1"), p

    def facet_counts(self, f: dict, key: str, limit: int = 3000) -> list:
        """Bir liste filtresinin değerleri ve diğer filtrelere göre sayıları (kendi seçimi hariç)."""
        self._ensure_funcs()
        g = dict(f)
        g["sec"] = {k: v for k, v in (f.get("sec") or {}).items() if k != key}
        where, prm = self.build_where(g)
        col = self._faset_col(key, f)
        return [tuple(r) for r in self.db.execute(
            f"SELECT COALESCE({col}, ''), COUNT(*) {self._BASE_FROM} WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT ?",
            prm + [limit])]

    _BASE_FROM = "FROM evrak e LEFT JOIN dosya d ON d.dkey = e.dkey"

    def _ensure_funcs(self):
        if not getattr(self._local, "funcs", False):
            self.db.create_function("fold_ac", 1, fold, deterministic=True)
            self._local.funcs = True

    def count(self, f: dict) -> int:
        self._ensure_funcs()
        where, p = self.build_where(f)
        return self.db.execute(f"SELECT COUNT(*) {self._BASE_FROM} WHERE {where}", p).fetchone()[0]

    def query(self, f: dict, limit: int = 1000, offset: int = 0, order: str = "e.tarih DESC, e.dkey, e.id") -> list:
        self._ensure_funcs()
        where, p = self.build_where(f)
        sql = (f"SELECT e.*, d.birim, d.dosya_no, d.dosya_tur, d.durum AS dosya_durum, d.muvekkil, d.yargi "
               f"{self._BASE_FROM} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?")
        return self.db.execute(sql, p + [limit, offset]).fetchall()

    def ids_for(self, f: dict) -> list[int]:
        self._ensure_funcs()
        where, p = self.build_where(f)
        return [r[0] for r in self.db.execute(
            f"SELECT e.id {self._BASE_FROM} WHERE {where} ORDER BY e.dkey, e.tarih, e.parent_skey, e.sira", p)]

    def tur_counts(self, f: dict) -> list:
        """Asıl evrak türleri ve (filtreye göre) sayıları; ekler ait oldukları evrakın türünde sayılır."""
        self._ensure_funcs()
        g = dict(f)
        g["turler"] = []
        where, p = self.build_where(g)
        return self.db.execute(
            f"SELECT e.ust_tur, COUNT(*) {self._BASE_FROM} WHERE {where} GROUP BY e.ust_tur ORDER BY 2 DESC", p).fetchall()

    def category_counts(self, f: dict) -> dict:
        self._ensure_funcs()
        g = dict(f)
        g["kategoriler"] = []
        where, p = self.build_where(g)
        return {r[0]: r[1] for r in self.db.execute(
            f"SELECT e.kategori, COUNT(*) {self._BASE_FROM} WHERE {where} GROUP BY e.kategori", p)}

    def get(self, eid: int):
        return self._execute_with_retry(lambda: self.db.execute(
            f"SELECT e.*, d.birim, d.dosya_no, d.dosya_tur, d.durum AS dosya_durum, d.yargi, d.dosya_id AS case_dosya_id "
            f"{self._BASE_FROM} WHERE e.id=?", (eid,)).fetchone())

    def by_skey(self, skey: str):
        return self._execute_with_retry(lambda: self.db.execute("SELECT * FROM evrak WHERE skey=?", (skey,)).fetchone())

    def find_sha(self, sha: str):
        return self._execute_with_retry(lambda: self.db.execute(
            "SELECT skey, path FROM evrak WHERE sha256=? AND durum='indirildi' AND path IS NOT NULL LIMIT 1",
            (sha,)).fetchone())

    def set_result(self, eid: int, **kw):
        cols = ", ".join(f"{k}=?" for k in kw)
        def _do():
            with self.db:
                self.db.execute(f"UPDATE evrak SET {cols} WHERE id=?", list(kw.values()) + [eid])
        self._execute_with_retry(_do)

    def set_text(self, eid: int, text: str):
        if not text:
            return
        def _do():
            with self.db:
                self.db.execute("DELETE FROM evrak_fts WHERE rowid=?", (eid,))
                self.db.execute("INSERT INTO evrak_fts(rowid, metin) VALUES(?,?)", (eid, text[:200000]))
        self._execute_with_retry(_do)

    def upsert_tebligat(self, item: dict) -> int:
        now = dt.datetime.now().isoformat()[:19]
        barkod = str(item.get("Barkod_Veya_Delil_No") or item.get("barkod_delil") or "").strip()
        if not barkod:
            barkod = f"TEB_{item.get('Evrak_Id') or item.get('evrak_id') or now}"
        with self.db:
            cur = self.db.execute(
                """INSERT INTO tebligat(
                     barkod_delil, dkey, birim, dosya_no, muvekkil, muhatap,
                     tebligat_turu, gonderim_tarihi, teblig_tarihi, sonuc,
                     yasal_sure_notu, evrak_id, evrak_adi, path, pdf_path,
                     ozet, durum, eklenme
                   ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(barkod_delil) DO UPDATE SET
                     teblig_tarihi=COALESCE(excluded.teblig_tarihi, tebligat.teblig_tarihi),
                     sonuc=COALESCE(excluded.sonuc, tebligat.sonuc),
                     yasal_sure_notu=COALESCE(excluded.yasal_sure_notu, tebligat.yasal_sure_notu),
                     pdf_path=COALESCE(excluded.pdf_path, tebligat.pdf_path),
                     path=COALESCE(excluded.path, tebligat.path),
                     ozet=COALESCE(excluded.ozet, tebligat.ozet)""",
                (
                    barkod,
                    self.dkey_of(str(item.get("Birim_Adi") or item.get("birim") or ""), str(item.get("Dosya_No") or item.get("dosya_no") or "")),
                    str(item.get("Birim_Adi") or item.get("birim") or ""),
                    str(item.get("Dosya_No") or item.get("dosya_no") or ""),
                    str(item.get("Dosyadaki_Muvekkil") or item.get("muvekkil") or ""),
                    str(item.get("Tebligat_Muhatabi") or item.get("muhatap") or ""),
                    str(item.get("Tebligat_Turu") or item.get("tebligat_turu") or ""),
                    str(item.get("Gonderim_Tarihi") or item.get("gonderim_tarihi") or ""),
                    str(item.get("Hukuki_Teblig_Tarihi") or item.get("teblig_tarihi") or ""),
                    str(item.get("Teblig_Durumu_Sonuc") or item.get("sonuc") or ""),
                    str(item.get("Yasal_Sure_Hesabi_Notu") or item.get("yasal_sure_notu") or ""),
                    str(item.get("Evrak_Id") or item.get("evrak_id") or ""),
                    str(item.get("Evrak_Adi") or item.get("evrak_adi") or ""),
                    str(item.get("Dosya_Yolu") or item.get("path") or ""),
                    str(item.get("pdf_path") or ""),
                    str(item.get("Detayli_Icerik_Ozeti") or item.get("ozet") or ""),
                    str(item.get("durum") or "yeni"),
                    now,
                )
            )
            return cur.lastrowid or 0

    def upsert_durusma(self, item: dict) -> int:
        birim = str(item.get("birim") or item.get("birimAdi") or item.get("mahkeme") or "")
        dno = str(item.get("dosyaNo") or item.get("dosya_no") or "")
        tarih = str(item.get("tarih") or item.get("durusmaTarihi") or "")
        saat = str(item.get("saat") or item.get("durusmaSaati") or "")
        yer = str(item.get("yer") or item.get("durusmaYeri") or item.get("salon") or "")
        acik = str(item.get("aciklama") or item.get("durusmaAciklama") or "")
        dkey = self.dkey_of(birim, dno)
        with self.db:
            cur = self.db.execute(
                """INSERT INTO durusma(dkey, birim, dosya_no, tarih, saat, yer, aciklama, durum)
                   VALUES(?, ?, ?, ?, ?, ?, ?, 'bekliyor')
                   ON CONFLICT(dkey, tarih, saat) DO UPDATE SET
                     yer=excluded.yer, aciklama=excluded.aciklama""",
                (dkey, birim, dno, tarih, saat, yer, acik)
            )
            return cur.lastrowid or 0

    def cloud_backup(self, target_path: Path | str) -> bool:
        """SQLite yerleşik backup API'si ile çalışan veritabanını kilitlemeden
        Google Drive veya hedef klasöre tutarlı anlık yedek çıkarır.
        v4.9.4: Windows ve bulut sürücülerinde (Google Drive, OneDrive) doğrudan yerel hazırlık dosyasından
        hedefe kopyalanır. Sanal sürücü içerisinde .tmp.db oluşturup os.replace yapmak bulut senkronizasyon
        istemcilerinin dosyayı kilitlemesi nedeniyle [WinError 32] hatası veriyordu."""
        import shutil
        try:
            target = Path(target_path)
            target_ext = win_extended_path(target)
            target_parent = os.path.dirname(target_ext)
            if target_parent:
                os.makedirs(target_parent, exist_ok=True)
            yerel = DATA_DIR / "uyap_katalog_yedek.hazirlik.db"
            dst = sqlite3.connect(str(yerel))
            try:
                self.db.backup(dst, pages=100)
            finally:
                dst.close()
            # Varsa eski kalmış .tmp.db'yi temizle
            try:
                eski_tmp = target.with_suffix(".tmp.db")
                if os.path.exists(win_extended_path(eski_tmp)):
                    os.unlink(win_extended_path(eski_tmp))
            except OSError:
                pass
            # Bulut istemcisi kilitliyse kısa aralıklarla dene
            for deneme in range(5):
                try:
                    shutil.copyfile(str(yerel), target_ext)
                    break
                except OSError:
                    if deneme == 4:
                        raise
                    time.sleep(1.5 * (deneme + 1))
            try:
                yerel.unlink()
            except OSError:
                pass
            return True
        except Exception as e:
            klog.error("Cloud backup hatası: %s", e)
            return False


# ---------------------------------------------------------------------------
# Dosya adı ve klasör düzeni
# ---------------------------------------------------------------------------
def _short_dno(dno: str) -> str:
    return safe_part(str(dno or "").replace("/", "-"), 30)


def doc_stem(row) -> str:
    """Asıl evrak adı: 2025-07-10_Talimat Üst Yazısı_[açıklama]_no68987"""
    tur = safe_part(strip_ext(row["tur"] if not row["is_ek"] else row["ust_tur"]), 45)
    acik = safe_part(row["aciklama"], 35, default="") if row["aciklama"] else ""
    no = safe_part(row["birim_evrak_no"] or (row["gercek_id"] or "")[:12], 14, default="")
    parts = [row["tarih"] or "tarihsiz", tur]
    if acik:
        parts.append(acik)
    if no:
        parts.append(f"no{no}")
    return "_".join(parts)


def target_path_for(row, base: Path, ext: str) -> Path:
    """Klasör: <yargı>/<birim>/<dosya no>/[<gönderen dosya (farklıysa)>]/<asıl evrak kategorisi>/
    Ekler asıl evrakın adıyla başlar ve aynı klasöre yazılır, böylece yan yana sıralanır."""
    folder = base / safe_part(row["yargi"] or "Diger", 30) / safe_part(row["birim"], 55) / _short_dno(row["dosya_no"])
    grup = str(row["grup"] or "")
    gm = re.match(r"\s*(\d{4}/\d+)", grup)
    if gm and gm.group(1) != str(row["dosya_no"] or "").strip():
        folder = folder / safe_part(grup.replace("/", "-"), 45)
    folder = folder / KLASOR_ADI.get(row["ust_kategori"] or row["kategori"] or "diger", "DIGER_EVRAKLAR")
    stem = doc_stem(row)
    if row["is_ek"]:
        stem = f"{stem}__EK{int(row['sira'] or 0):02d}_{safe_part(strip_ext(row['tur']), 40)}"
    ext = ext if ext.startswith(".") else f".{ext}"
    # Windows yol sınırı (260): adı gerekirse kısalt (.part ve uzantı için pay bırak)
    room = 230 - len(str(folder)) - len(ext) - 6
    if room < 25:
        room = 25
    if len(stem) > room:
        stem = stem[:room].rstrip(". _")
    return folder / f"{stem}{ext}"


def unique_path(p: Path) -> Path:
    ext_p = win_extended_path(p)
    if not os.path.exists(ext_p):
        return p
    for i in range(2, 1000):
        q = p.with_name(f"{p.stem}_{i}{p.suffix}")
        if not os.path.exists(win_extended_path(q)):
            return q
    return p


# ---------------------------------------------------------------------------
# Dönüştürme ve metin çıkarma
# ---------------------------------------------------------------------------
A4_PX = (1654, 2339)  # 200 dpi


def tiff_to_pdf(src: Path) -> Path | None:
    """Tek/çok sayfalı TIF/TIFF'i A4 boyutlu çok sayfalı PDF'e çevirir (aynı ad, .pdf)."""
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        return None
    dst = src.with_suffix(".pdf")
    ext_dst = win_extended_path(dst)
    if os.path.exists(ext_dst) and os.path.getsize(ext_dst) > 0:
        return dst
    pages = []
    try:
        with Image.open(win_extended_path(src)) as im:
            for frame in ImageSequence.Iterator(im):
                fr = frame.copy()
                mode = "1" if fr.mode == "1" else ("L" if fr.mode in ("L", "P", "LA", "I;16", "I") else "RGB")
                fr = fr.convert(mode if mode != "1" else "L")
                w, h = fr.size
                landscape = w > h
                pw, ph = (A4_PX[1], A4_PX[0]) if landscape else A4_PX
                scale = min(pw / w, ph / h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
                fr = fr.resize((nw, nh), Image.LANCZOS)
                page = Image.new(fr.mode, (pw, ph), 255 if fr.mode == "L" else (255, 255, 255))
                page.paste(fr, ((pw - nw) // 2, (ph - nh) // 2))
                pages.append(page)
        if not pages:
            return None
        tmp = dst.with_suffix(".pdf.part")
        pages[0].save(win_extended_path(tmp), "PDF", resolution=200.0, save_all=True, append_images=pages[1:])
        safe_replace_file(tmp, dst)
        return dst
    except Exception:
        return None


def udf_folder_to_pdf(folder: Path, timeout: int = 600) -> None:
    """Klasördeki (alt klasörler dahil) PDF'i olmayan tüm UDF'leri Havelsan motoruyla tek JVM'de çevirir."""
    if not folder.exists():
        return
    jars = BASE_DIR / "jars"
    if not jars.exists():
        jars = BASE_DIR.parent / "jars"
    if not jars.exists():
        jars = Path("/data/data/com.termux/files/home/jars")
    cmd = [
        "java", "-Xmx512m", "-Djava.awt.headless=true",
        "--add-opens=java.base/java.util=ALL-UNNAMED", "--add-opens=java.base/java.lang=ALL-UNNAMED",
        "--add-opens=java.desktop/java.awt=ALL-UNNAMED", "--add-opens=java.desktop/javax.swing=ALL-UNNAMED",
        "-cp", f"{BASE_DIR}{os.pathsep}{jars / '*'}", "uyap.UdfBatchPdfConverter", str(folder),
    ]
    try:
        kw = {"creationflags": 0x08000000} if os.name == "nt" else {}  # CREATE_NO_WINDOW
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, **kw)
    except Exception:
        pass


def content_fingerprint(raw: bytes) -> str:
    """Aynı evrakın farklı indirmelerinde değişmeyen özet.
    UYAP, UDF'yi her indirmede yeniden paketler (zip zaman damgası ve documentproperties.xml değişir);
    bu yüzden UDF/zip için yalnızca içerik dosyaları (content.xml, sign.sgn ...) özetlenir."""
    if raw[:2] == b"PK":
        try:
            h = hashlib.sha256()
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                names = sorted(n for n in z.namelist() if not n.lower().endswith("documentproperties.xml"))
                for n in names:
                    h.update(n.encode("utf-8", "ignore") + b"\0" + z.read(n) + b"\0")
            return "z:" + h.hexdigest()
        except Exception:
            pass
    return hashlib.sha256(raw).hexdigest()


def extract_text(path: Path, raw: bytes | None = None) -> str:
    """İçerik araması için metin: UDF (content.xml) ve PDF (pypdf, ilk 30 sayfa)."""
    try:
        ext = path.suffix.lower()
        data = raw if raw is not None else path.read_bytes()
        if ext == ".udf" or data[:2] == b"PK":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                name = next((n for n in z.namelist() if n.lower().endswith("content.xml")), None)
                if name:
                    xml = z.read(name).decode("utf-8", "ignore")
                    m = re.search(r"<!\[CDATA\[(.*?)\]\]>", xml, re.S)
                    txt = m.group(1) if m else re.sub(r"<[^>]+>", " ", xml)
                    return re.sub(r"\s+", " ", txt).strip()
        if ext == ".pdf" or data[:4] == b"%PDF":
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            return re.sub(r"\s+", " ", " ".join((pg.extract_text() or "") for pg in r.pages[:30])).strip()
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Tarama ve indirme motoru (GUI ve CLI ortak)
# ---------------------------------------------------------------------------
class Motor:
    """UYAP tarama + indirme. Tüm köprü (tarayıcı) çağrıları tek iş parçacığından yapılmalıdır."""

    def __init__(self, bridge, katalog: Katalog, download_dir: Path, log=print, progress=None, relogin=None):
        self.bridge = bridge
        self.kat = katalog
        self.download_dir = Path(download_dir)
        self.base = self.download_dir / "DAVA_EVRAKLARI"
        self._ui_log = log
        self.dbg = klog.debug
        self.progress = progress or (lambda done, total, text="": None)
        self.stop_flag = threading.Event()
        # v4.9.3: kesme() True dönerse (elle "indir" denen öncelikli iş geldi) uzun paket/tarama yarıda bırakılır;
        # bırakılan evraklar 'yeni' kalır, sonraki turda kaldığı yerden devam edilir.
        self.kesme = None
        self.pause_flag = threading.Event()
        self.oturum = ""
        self.case_ids: dict[str, str] = {}
        self.relogin = relogin  # () -> bool ; GUI/CLI tarafından atanır
        self.min_d, self.max_d, self.batch_n, self.batch_pause = 0.6, 1.2, 30, 6.0

    def log(self, msg: str):
        """Hem ekrana hem ayrıntılı günlük dosyasına (loglar/katalog.log) yazar."""
        klog.info(msg)
        try:
            self._ui_log(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------ yardımcılar
    def _new_session(self):
        self.oturum = dt.datetime.now().strftime("%Y%m%d%H%M%S") + f"{random.randint(0, 999):03d}"
        self.case_ids = {}

    def _kesilsin_mi(self) -> bool:
        try:
            return bool(self.kesme and self.kesme())
        except Exception:  # noqa: BLE001
            return False

    def _sleep(self, s: float):
        end = time.time() + s
        while time.time() < end and not self.stop_flag.is_set() and not self._kesilsin_mi():
            time.sleep(0.1)
        while self.pause_flag.is_set() and not self.stop_flag.is_set():
            time.sleep(0.2)

    def _avukat_adi(self, all_taraf: list) -> str:
        try:
            info = self.bridge.check_login_and_user() or {}
            u = info.get("user") or {}
            ad = " ".join(str(u.get(k) or "") for k in ("adi", "soyadi")).strip()
            if ad:
                return ad
        except Exception:
            pass
        # En çok dosyada vekil olarak geçen isim avukatın kendisidir
        cnt = {}
        for tl in all_taraf:
            names = set()
            for t in tl or []:
                for n in str((t or {}).get("vekil") or "").strip("[]").split(","):
                    n = n.strip()
                    if n:
                        names.add(n)
            for n in names:
                cnt[n] = cnt.get(n, 0) + 1
        return max(cnt, key=cnt.get) if cnt else ""

    def _taraflar_batch(self, ids: list) -> dict:
        import json as _json
        js = """(async () => { const ids = %s; const out = {};
          await Promise.all(ids.map(async (id) => { try {
            const r = await fetch("/dosya_taraf_bilgileri_brd.ajx", {method:"POST",
              headers:{"Content-Type":"application/json"}, body: JSON.stringify({dosyaId: id})});
            const d = await r.json(); out[id] = Array.isArray(d) ? d : null; } catch(e) { out[id] = null; } }));
          return out; })()""" % _json.dumps(ids)
        try:
            res = self.bridge.eval_js(js, timeout=60.0)
            return res if isinstance(res, dict) else {}
        except Exception:
            return {}

    def _evraklar_batch(self, ids: list) -> dict:
        """Dosyaların TÜM evrak sayfalarını paralel çeker (sayfa sınırı yok).
        Başarılıysa {id: [sayfalar]}, değilse {id: {"err": "oturum"|"<UYAP hata kodu>"|..., "msg": ...}}."""
        import json as _json
        js = """(async () => { const ids = %s; const out = {};
          const post = (u, b) => fetch(u, {method:"POST", headers:{"Content-Type":"application/json","Cache-Control":"no-cache"}, body: JSON.stringify(b)});
          await Promise.all(ids.map(async (id) => { try {
            const pages = [];
            const r1 = await post("/list_dosya_evraklar.ajx", {dosyaId: id, pageNumber: 1});
            const ct = r1.headers.get("content-type") || "";
            const txt = await r1.text();
            if (!r1.ok || ct.includes("text/html") || /^\\s*</.test(txt)) { out[id] = {err: "oturum", msg: "HTTP " + r1.status}; return; }
            let d1; try { d1 = JSON.parse(txt); } catch(e) { out[id] = {err: "oturum", msg: "JSON değil"}; return; }
            if (d1 && !Array.isArray(d1) && d1.errorCode) { out[id] = {err: String(d1.errorCode), msg: String(d1.error || "")}; return; }
            pages.push(d1);
            let total = Number(d1 && d1.pageTotal) || 1;
            if (total <= 1) { try { const t = await (await post("/listDosyaEvraklarPageTotal.ajx", {dosyaId: id, pageNumber: 1})).json();
                 total = typeof t === "number" ? t : (Number(t && t.total) || 1); } catch(e) {} }
            // Büyük (icra) dosyalarda yüzlerce sayfa olabilir: 5'erli paralel; 240 sn sınırına takılıp
            // bütün grubun boşa gitmesi önlenir.
            const son = Math.min(total, 600);
            for (let p = 2; p <= son; p += 5) {
              const grup = [];
              for (let q = p; q < p + 5 && q <= son; q++) grup.push(post("/list_dosya_evraklar.ajx", {dosyaId: id, pageNumber: q})
                .then(r => r.ok ? r.json() : null).catch(() => null));
              for (const v of await Promise.all(grup)) if (v) pages.push(v);
            }
            out[id] = pages; } catch(e) { out[id] = {err: "ag", msg: String(e)}; } }));
          return out; })()""" % _json.dumps(ids)
        try:
            res = self.bridge.eval_js(js, timeout=900.0)
            return res if isinstance(res, dict) else {}
        except Exception:
            return {}

    # ------------------------------------------------------------------ tarama
    @staticmethod
    def _case_dkey(c: dict) -> str:
        return Katalog.dkey_of(c.get("birimAdi") or c.get("mahkemeAdi"), c.get("dosyaNo") or c.get("dosyaNO"))

    def _fetch_cases(self, include_closed: bool) -> list:
        cases = self.bridge.query_tum_dosyalar(include_closed=include_closed, use_cache=False) or []
        self.case_ids = {self._case_dkey(c): str(c.get("dosyaId") or c.get("dosyaID") or "") for c in cases}
        return cases

    def scan(self, include_closed: bool = True, batch: int = 6, only_dkeys: set | None = None) -> int:
        """Dosyaların evrak listelerini kataloğa yazar. Oturum düşerse yeniden giriş yaptırıp
        kaldığı dosyadan devam eder; taranamayan dosyalar 'tarama' sütununda işaretli kalır
        (sonra only_dkeys=katalog.eksik_dkeys() ile yalnızca onlar taranabilir)."""
        from uyap_indirici import infer_yargi_kategorisi
        self._new_session()
        self.log("[*] UYAP'taki tüm dosyalar sorgulanıyor...")
        cases = self._fetch_cases(include_closed)
        if not cases:
            if self._session_dead() and self._relogin():
                cases = self._fetch_cases(include_closed)
            if not cases:
                self.log("[!] Dosya listesi alınamadı (oturum kapalı olabilir).")
                return 0
        if only_dkeys is not None:
            cases = [c for c in cases if self._case_dkey(c) in only_dkeys]
        self.log(f"[✓] {len(cases)} dosya taranacak. Taraf ve evrak listeleri çekiliyor...")
        taraf_map = {}  # dkey -> taraf listesi
        for i in range(0, len(cases), 6):  # UYAP çok sayıda eşzamanlı isteği reddedebiliyor
            if self.stop_flag.is_set():
                return 0
            chunk = cases[i:i + 6]
            res = self._taraflar_batch([str(c.get("dosyaId") or c.get("dosyaID") or "") for c in chunk])
            for c in chunk:
                v = res.get(str(c.get("dosyaId") or c.get("dosyaID") or ""))
                if v:
                    taraf_map[self._case_dkey(c)] = v
            self.progress(min(i + 6, len(cases)), len(cases), "Taraf bilgileri")
        avukat = self._avukat_adi(list(taraf_map.values()))
        if avukat:
            self.log(f"[i] Müvekkil tespiti için vekil adı: {avukat}")

        total_rows, done, n_ok, n_err = 0, 0, 0, 0
        pending = list(cases)
        relogins = 0
        while pending:
            if self.stop_flag.is_set():
                self.log("[!] Tarama durduruldu.")
                break
            if self._kesilsin_mi():
                self.log("⚡ Öncelikli indirme isteği geldi: katalog taraması sonraki tura bırakıldı.")
                break
            chunk, pending = pending[:batch], pending[batch:]
            res = self._evraklar_batch([self.case_ids.get(self._case_dkey(c), "") for c in chunk])
            retry = []
            for c in chunk:
                dkey = self._case_dkey(c)
                cid = self.case_ids.get(dkey, "")
                self.kat.upsert_dosya(c, taraf_map.get(dkey), avukat,
                                      infer_yargi_kategorisi(str(c.get("birimAdi") or "")), self.oturum)
                pages = res.get(cid)
                if isinstance(pages, list):
                    total_rows += self.kat.ingest_pages(dkey, pages, self.oturum)
                    self.kat.set_tarama(dkey, "tamam")
                    n_ok += 1
                    done += 1
                elif isinstance(pages, dict) and pages.get("err") not in ("oturum", "ag", None):
                    # UYAP'ın kalıcı yanıtı (ör. vekil kaydı yok): tekrar denemeye gerek yok
                    self.kat.set_tarama(dkey, f"hata: {pages.get('err')} {pages.get('msg', '')[:120]}")
                    n_err += 1
                    done += 1
                else:
                    retry.append(c)
            if retry:
                if self._session_dead():
                    relogins += 1
                    if relogins > 5 or not self._relogin():
                        for c in retry + pending:
                            self.kat.set_tarama(self._case_dkey(c), "hata: oturum düştü")
                        self.log(f"[x] Oturum yenilenemedi. {len(retry) + len(pending)} dosya taranamadı; "
                                 "tekrar giriş yapıp 'Yalnızca eksikleri tara' ile devam edin.")
                        pending = []
                    else:
                        self._fetch_cases(include_closed)  # dosya kimlikleri oturuma özgü: tazele
                        pending = retry + pending
                else:
                    # Geçici ağ/sunucu hatası: bir kez daha, sonra hatalı say
                    for c in retry:
                        c["_deneme"] = c.get("_deneme", 0) + 1
                        if c["_deneme"] >= 3:
                            self.kat.set_tarama(self._case_dkey(c), "hata: yanıt alınamadı")
                            n_err += 1
                            done += 1
                        else:
                            pending.append(c)
                    self._sleep(3.0)
            self.kat.db.commit()
            self.progress(done, len(cases), f"Evrak listeleri ({total_rows} kayıt, {n_err} hatalı)")
            self._sleep(0.3)
        self.log(f"[i] Tarama: {n_ok} dosya tamam, {n_err} dosya UYAP'tan liste vermedi"
                 + (", kalanlar oturum nedeniyle yarım" if pending or self.stop_flag.is_set() else "") + ".")
        self.kat.finalize_scan()
        self.kat.match_existing_disk([self.download_dir / n for n in (
            "DAVA_EVRAKLARI", "DURUSMA_TUTANAKLARI", "GEREKCELI_KARARLAR", "TEBLIGATLAR",
            "BILIRKISI_RAPORLARI", "TENSIP_ZAPITLARI", "DILEKCELER_LAYIHALAR", "IDDIANAMELER",
            "MUZEKKERE_VE_KURUM_CEVAPLARI", "KESINLESME_SERHLERI")], log=self.log)
        st = self.kat.stats()
        self.log(f"[✓] Katalog güncel: {st['dosya']} dosya, {st['evrak']} evrak ({st['ek']} ek), "
                 f"{st['mukerrer']} mükerrer, {st['indirildi']} indirilmiş, {st['yeni']} indirilmemiş.")
        return total_rows

    # ------------------------------------------------------------------ indirme
    def _refresh_case(self, dkey: str) -> bool:
        """Bu oturum için dosyanın taze (şifreli) kimliklerini alır ve kataloğu günceller."""
        if not self.case_ids:
            cases = self.bridge.query_tum_dosyalar(include_closed=True, use_cache=False) or []
            for c in cases:
                self.case_ids[Katalog.dkey_of(c.get("birimAdi"), c.get("dosyaNo") or c.get("dosyaNO"))] = \
                    str(c.get("dosyaId") or c.get("dosyaID") or "")
        cid = self.case_ids.get(dkey)
        if not cid:
            # Liste eksik gelmiş olabilir (UYAP bazı istekleri reddedebiliyor): bir kez daha çek
            cases = self.bridge.query_tum_dosyalar(include_closed=True, use_cache=False) or []
            self.case_ids.update({Katalog.dkey_of(c.get("birimAdi"), c.get("dosyaNo") or c.get("dosyaNO")):
                                  str(c.get("dosyaId") or c.get("dosyaID") or "") for c in cases})
            cid = self.case_ids.get(dkey)
            klog.debug("Dosya listede yoktu, liste yeniden çekildi (%d dosya): %s -> %s", len(cases), dkey, bool(cid))
        if not cid:
            return False
        res = self._evraklar_batch([cid])
        pages = res.get(cid)
        if not isinstance(pages, list):
            return False
        self.kat.ingest_pages(dkey, pages, self.oturum)
        self.kat.set_tarama(dkey, "tamam")
        with self.kat.db:
            self.kat.db.execute("UPDATE dosya SET dosya_id=?, oturum=? WHERE dkey=?", (cid, self.oturum, dkey))
        return True

    def _session_dead(self) -> bool:
        try:
            return not self.bridge.is_logged_in()
        except Exception:
            return True

    def _relogin(self) -> bool:
        klog.warning("Oturum yenileme başlatıldı")
        self.log("[!] UYAP oturumu düştü, yeniden giriş deneniyor...")
        ok = bool(self.relogin and self.relogin())
        if ok:
            self._new_session()
            self.log("[✓] Oturum yenilendi.")
        else:
            self.log("[x] Oturum yenilenemedi; işlem durduruldu.")
        return ok

    # ------------------------------------------------------------------ tek evrakı UYAP'tan çek (indirme + önizleme ortak)
    def _ensure_row_fresh(self, eid: int, refreshed: set | None = None):
        """Evrakın şifreli kimlikleri bu oturuma ait değilse dosyanın evrak listesini tazeler."""
        row = self.kat.get(eid)
        if not row:
            return None
        if row["oturum"] == self.oturum:
            return row
        dk = row["dkey"]
        if refreshed is not None and dk in refreshed:
            return row
        if refreshed is not None:
            refreshed.add(dk)
        t0 = time.time()
        ok = self._refresh_case(dk)
        self.dbg("Dosya kimlikleri tazelendi: %s -> %s (%.1fs)", dk, ok, time.time() - t0)
        if not ok and self._session_dead():
            if self._relogin():
                ok = self._refresh_case(dk)
            else:
                self.stop_flag.set()  # giriş yapılamadı: kalan evrakları boşuna denemeden dur
        return self.kat.get(eid)

    def fetch(self, eid: int, refreshed: set | None = None) -> tuple:
        """(raw_bytes | None, resp, row, neden). Oturum düşerse yeniden giriş yapar; takılan isteği
        zaman aşımıyla keser ve en fazla 5 kez dener. Bozuk/HTML yanıt asla geçerli sayılmaz."""
        from uyap_indirici import is_valid_document_bytes
        import base64
        if not self.oturum:
            self._new_session()
        row = self._ensure_row_fresh(eid, refreshed)
        if not row:
            return None, {}, None, "kayıt yok"
        if self.stop_flag.is_set():
            return None, {}, row, "oturum yenilenemedi"
        if row["oturum"] != self.oturum:
            return None, {}, row, "UYAP listesinde artık yok"
        resp, reason = {}, ""
        # Tek evrak dakikalarca takılmasın (v4.4.0 günlüğü: 8 dk 25 sn): UYAP aynı boş/çok küçük yanıtı 2 kez
        # verirse ve oturum ayaktaysa evrak "UYAP'ta içerik yok" sayılır; yeniden giriş evrak başına en çok 1 kez.
        kucuk_sayac, giris_sayac = 0, 0
        for attempt in range(1, 6):
            if self.stop_flag.is_set():
                return None, resp, row, "durduruldu"
            cid = self.case_ids.get(row["dkey"]) or row["case_dosya_id"]
            t0 = time.time()
            resp = self.bridge.download_document({"dosyaId": cid, "evrakId": row["evrak_id"]}, timeout_s=40.0) or {}
            raw = base64.b64decode(resp.get("base64") or "") if resp.get("base64") else b""
            ok, reason = is_valid_document_bytes(raw, resp.get("contentType") or "")
            self.dbg("İndirme denemesi %d id=%s durum=%s boyut=%d ct=%s süre=%.1fs geçerli=%s neden=%s hata=%s",
                     attempt, eid, resp.get("status"), len(raw), resp.get("contentType"), time.time() - t0, ok,
                     reason, resp.get("error") or resp.get("errorHeader"))
            if ok:
                return raw, resp, row, ""
            if not resp.get("timeout") and len(raw) < 128 and "html" not in (resp.get("contentType") or "").lower():
                kucuk_sayac += 1
                if kucuk_sayac >= 2 and not self._session_dead():
                    return None, resp, row, "yok"
            if resp.get("timeout"):
                self.log(f"[!] UYAP 40 sn içinde yanıt vermedi ({str(row['tur'])[:40]}); yeniden deneniyor ({attempt}/5)...")
                self._sleep(3.0 * attempt)
                continue
            if self._session_dead():
                if giris_sayac >= 1:
                    return None, resp, row, reason or "oturum tekrar koptu (evrak atlandı, sonraki turda denenecek)"
                giris_sayac += 1
                self.log("[!] Bağlantı/oturum koptu; yeniden giriş yapılıp aynı evrak tekrar denenecek.")
                if not self._relogin():
                    self.stop_flag.set()
                    return None, resp, row, "oturum yenilenemedi"
                self._refresh_case(row["dkey"])
                row = self.kat.get(eid)
                continue
            if resp.get("ok") and "html" not in (resp.get("contentType") or "").lower():
                return None, resp, row, "yok"  # UYAP'ta fiziksel dosya yok
            self._sleep(2.0 * attempt)
        return None, resp, row, reason or "yanıt alınamadı"

    @staticmethod
    def _ext_of(resp: dict, raw: bytes) -> str:
        from uyap_indirici import guess_extension
        cd = resp.get("contentDisposition") or ""
        m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^;"\']+)', cd, re.I)
        ext = guess_extension(m.group(1) if m else "", resp.get("contentType") or "", raw)
        return ext if ext.startswith(".") else f".{ext}"

    def fetch_to_cache(self, eid: int) -> Path | None:
        """Önizleme: evrakı indirme klasörüne değil önbelleğe alır (PDF'i de üretilir) ve açılacak yolu döner."""
        row = self.kat.get(eid)
        if row and row["path"] and os.path.exists(row["path"]):
            return Path(row["pdf_path"] if row["pdf_path"] and os.path.exists(row["pdf_path"]) else row["path"])
        if row and row["cache_path"] and os.path.exists(row["cache_path"]):
            cp = Path(row["cache_path"])
            return cp.with_suffix(".pdf") if cp.with_suffix(".pdf").exists() else cp
        raw, resp, row, why = self.fetch(eid)
        if raw is None:
            self.log(f"[x] Önizleme alınamadı: {why}")
            return None
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = CACHE_DIR / f"{eid}_{safe_part(strip_ext(row['tur']), 50)}{self._ext_of(resp, raw)}"
        p.write_bytes(raw)
        self.kat.set_result(eid, cache_path=str(p))
        self.log(f"[✓] Önbelleğe alındı (indirirken buradan taşınacak): {p.name}")
        try:
            import donusturucu as dn
            _st, pdf, _m = dn.convert(p)
            if pdf:
                return pdf
        except Exception as e:
            self.dbg("Önbellek PDF dönüşümü başarısız: %s", e)
        return p

    def _sync_to_drive(self, local_file: Path | str | None):
        """İndirilen veya PDF'e dönüştürülen dosyayı anında Google Drive klasörüne yansıtır."""
        if not local_file:
            return
        try:
            lf = Path(local_file)
            if not lf.exists() or lf.stat().st_size == 0:
                return
            drive_dir = getattr(self, "_drive_dir", None)
            if drive_dir is None:
                cands = [
                    Path("G:/Drive'ım/UYAP_Arsiv"),
                    Path("G:/My Drive/UYAP_Arsiv"),
                    Path.home() / "Google Drive" / "UYAP_Arsiv",
                    Path.home() / "GoogleDrive" / "UYAP_Arsiv",
                ]
                self._drive_dir = False
                for c in cands:
                    if c.parent.exists():
                        self._drive_dir = c
                        break
                drive_dir = self._drive_dir
            if not drive_dir:
                return
            try:
                rel = lf.resolve().relative_to(self.download_dir.resolve())
            except Exception:
                rel = lf.name
            target = drive_dir / rel
            if lf.resolve() == target.resolve():
                return
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists() or target.stat().st_size != lf.stat().st_size:
                shutil.copy2(lf, target)
                self.log(f"[cloud] Google Drive'a aktarıldı: {target.name}")
        except Exception:
            pass

    # ------------------------------------------------------------------ PDF dönüşümü (arka plan)
    def _conv_worker(self):
        import donusturucu as dn
        while True:
            fo = self._conv_q.get()
            try:
                t0 = time.time()
                udfs = [f for f in Path(fo).glob("*.udf") if not f.with_suffix(".pdf").exists()]
                if udfs:
                    dn.udf_to_pdf(Path(fo), timeout=90 + 15 * len(udfs))
                done = [f for f in udfs if f.with_suffix(".pdf").exists()]
                for f in done:
                    self.log(f"[pdf] PDF'e çevrildi: {f.with_suffix('.pdf').name}")
                    self._sync_to_drive(f.with_suffix(".pdf"))
                if len(done) < len(udfs):
                    ok, why = dn.udf_hazir_mi()
                    self.log(f"[!] {len(udfs) - len(done)} UDF PDF'e çevrilemedi ({Path(fo).name})"
                             + (f": {why}" if not ok else "."))
                if done:
                    def _update_pdfs():
                        with self.kat.db:
                            for f in done:
                                self.kat.db.execute("UPDATE evrak SET pdf_path=? WHERE path=?",
                                                    (str(f.with_suffix(".pdf")), str(f)))
                    self.kat._execute_with_retry(_update_pdfs)
                self.dbg("Klasör dönüşümü %s: %d/%d (%.1fs)", fo, len(done), len(udfs), time.time() - t0)
            except Exception as e:
                klog.exception("PDF dönüşüm hatası %s: %s", fo, e)
            finally:
                self._conv_q.task_done()

    def _queue_conversion(self, folder: Path):
        import queue as _q
        if getattr(self, "_conv_q", None) is None:
            self._conv_q = _q.Queue()
            threading.Thread(target=self._conv_worker, daemon=True, name="pdf-donusum").start()
        self._conv_q.put(str(folder))

    # ------------------------------------------------------------------ toplu ön kontrol (mükerrer tahmini)
    # İçerik mükerreri (aynı vekaletname/ek her dilekçeye eklenmiş gibi) ancak indirince SHA-256 ile anlaşılabiliyordu:
    # her biri UYAP bekleme süresiyle tek tek indirilip atılıyordu. Artık geçmiş indirmelerden öğrenilir:
    # aynı dosyada, aynı gönderenden, aynı adlı ek en az 2 kez indirilmiş ve HEPSİ aynı içerikse, sonrakiler
    # indirilmeden "mükerrer (tahmini)" işaretlenir. Tahminler boşta (nöbetçi bekleme modunda) tek tek doğrulanır;
    # içerik farklı çıkarsa evrak indirilir ve o kalıp bir daha tahmin için kullanılmaz.
    TAHMIN_ISARETI = "tahmini mükerrer (indirilmedi, sonra doğrulanacak)"

    @staticmethod
    def _imza(row) -> tuple:
        return (row["dkey"] or "", (row["tur"] or "").strip().lower(), (row["gonderen"] or "").strip().lower())

    def _tahmin_haritasi(self) -> dict:
        """imza → (asıl skey, asıl path): yalnız ekler için, geçmişte ≥2 kez aynı içerikle gelmiş kalıplar."""
        if os.environ.get("UYAP_MUKERRER_TAHMIN", "1") == "0":
            return {}
        sorgu = """SELECT dkey, lower(trim(tur)) t, lower(trim(COALESCE(gonderen,''))) g,
                          COUNT(*) n, COUNT(DISTINCT sha256) d,
                          MIN(CASE WHEN durum='indirildi' THEN skey END) asil,
                          MIN(CASE WHEN durum='indirildi' THEN path END) yol
                   FROM evrak WHERE is_ek=1 AND sha256 IS NOT NULL AND durum IN ('indirildi','mukerrer')
                   GROUP BY dkey, t, g HAVING n >= 2 AND d = 1 AND asil IS NOT NULL"""
        harita = {}
        for r in self.kat._execute_with_retry(lambda: self.kat.db.execute(sorgu).fetchall()):
            if r["yol"] and os.path.exists(r["yol"]):
                harita[(r["dkey"] or "", r["t"] or "", r["g"] or "")] = (r["asil"], r["yol"])
        # Doğrulamada farklı çıkan kalıplar güvenilmez sayılır
        for r in self.kat._execute_with_retry(lambda: self.kat.db.execute(
                "SELECT DISTINCT dkey, lower(trim(tur)) t, lower(trim(COALESCE(gonderen,''))) g FROM evrak "
                "WHERE is_ek=1 AND hata='tahmin yanlış çıktı'").fetchall()):
            harita.pop((r["dkey"] or "", r["t"] or "", r["g"] or ""), None)
        return harita

    def on_kontrol(self, ids: list[int], tahmin: bool = True) -> tuple[list[int], dict]:
        """İndirmeden ÖNCE tek seferde: zaten inmiş olanları ve tahmini mükerrerleri ayıklar, planı yazar."""
        plan = {"istenen": len(ids), "zaten": 0, "tahmini_mukerrer": 0, "indirilecek": 0}
        if not ids:
            return [], plan
        satirlar = {}
        for i in range(0, len(ids), 900):
            parca = ids[i:i + 900]
            for r in self.kat._execute_with_retry(lambda p=parca: self.kat.db.execute(
                    f"SELECT id, durum, is_ek, dkey, tur, gonderen FROM evrak WHERE id IN ({','.join('?' * len(p))})", p).fetchall()):
                satirlar[r["id"]] = r
        harita = self._tahmin_haritasi() if tahmin else {}
        simdi = dt.datetime.now().isoformat(timespec="seconds")
        kalan = []
        for eid in ids:
            r = satirlar.get(eid)
            if not r or r["durum"] in ("indirildi", "mukerrer"):
                plan["zaten"] += 1
                continue
            hedef = harita.get(self._imza(r)) if r["is_ek"] else None
            if hedef:
                self.kat.set_result(eid, durum="mukerrer", dup_of=hedef[0], path=hedef[1], indirildi=simdi,
                                    hata=self.TAHMIN_ISARETI)
                plan["tahmini_mukerrer"] += 1
                continue
            kalan.append(eid)
        plan["indirilecek"] = len(kalan)
        self.log(f"[plan] {plan['istenen']} evrak tek seferde kontrol edildi: {plan['zaten']} zaten var, "
                 f"{plan['tahmini_mukerrer']} mükerrer olacağı bilindiği için indirilmeyecek, {plan['indirilecek']} indirilecek.")
        return kalan, plan

    def tahminleri_dogrula(self, limit: int = 10) -> dict:
        """Boştayken: 'tahmini mükerrer' işaretlenenleri gerçekten indirip SHA-256 ile doğrular."""
        rows = self.kat._execute_with_retry(lambda: self.kat.db.execute(
            "SELECT id FROM evrak WHERE durum='mukerrer' AND hata=? ORDER BY tarih DESC LIMIT ?",
            (self.TAHMIN_ISARETI, int(limit))).fetchall())
        ids = [r["id"] for r in rows]
        if not ids:
            return {"dogrulanan": 0}
        for eid in ids:
            self.kat.set_result(eid, durum="yeni", dup_of=None, path=None, indirildi=None, hata="tahmin doğrulanıyor")
        st = self.download(ids, tahmin=False)
        # Mükerrer çıkmayıp indirilenler: tahmin yanlıştı → o kalıp artık kullanılmaz
        with self.kat.db:
            for eid in ids:
                r = self.kat.get(eid)
                if r and r["durum"] == "indirildi":
                    self.kat.db.execute("UPDATE evrak SET hata='tahmin yanlış çıktı' WHERE id=?", (eid,))
        return {"dogrulanan": len(ids), **st}

    # ------------------------------------------------------------------ indirme
    def download(self, ids: list[int], tahmin: bool = True) -> dict:
        stats = {"indirildi": 0, "mukerrer": 0, "yok": 0, "hata": 0, "atlandi": 0, "onbellek": 0, "tahmini_mukerrer": 0}
        n_gone = self.kat.sync_disk(en_az_aralik_sn=6 * 3600)
        if n_gone:
            self.log(f"[i] Diskte bulunamayan {n_gone} evrak yeniden indirilecek olarak işaretlendi.")
        if not ids:
            return stats
        istenen = len(ids)
        ids, plan = self.on_kontrol(list(ids), tahmin=tahmin)
        stats["atlandi"] += plan["zaten"]
        stats["tahmini_mukerrer"] = plan["tahmini_mukerrer"]
        stats["mukerrer"] += plan["tahmini_mukerrer"]
        if not ids:
            self.log(f"[✓] İndirilecek yeni evrak yok ({istenen} evrağın tamamı zaten var veya mükerrer).")
            return stats
        # Aynı çalışmada da öğren: bir kalıp ikinci kez aynı içerikle gelince kalanlar indirilmeden geçilir
        canli_harita = self._tahmin_haritasi() if tahmin else {}
        if not self.oturum:
            self._new_session()
        total = len(ids)
        t_start, done, since_pause, bytes_total = time.time(), 0, 0, 0
        refreshed: set = set()
        pending_folders: set = set()
        last_dkey = None
        self.log(f"[*] {total} evrak indirilecek ({self.min_d}-{self.max_d} sn bekleme, "
                 f"her {self.batch_n} evrakta {self.batch_pause:.0f} sn mola). Takılan istek 40 sn'de kesilir.")
        for eid in ids:
            if self.stop_flag.is_set():
                break
            if len(ids) > 1 and self._kesilsin_mi():
                self.log("⚡ Öncelikli indirme isteği geldi: bu paket yarıda bırakıldı (kalanlar sonra iner).")
                break
            done += 1
            try:
                row = self.kat.get(eid)
                if not row or row["durum"] in ("indirildi", "mukerrer"):
                    stats["atlandi"] += 1
                    continue
                if last_dkey and row["dkey"] != last_dkey:  # dosya değişti: önceki klasörleri arka planda PDF'e çevir
                    for fo in pending_folders:
                        self._queue_conversion(fo)
                    pending_folders.clear()
                last_dkey = row["dkey"]
                if tahmin and row["is_ek"] and self._imza(row) in canli_harita:
                    hedef = canli_harita[self._imza(row)]
                    self.kat.set_result(eid, durum="mukerrer", dup_of=hedef[0], path=hedef[1], hata=self.TAHMIN_ISARETI,
                                        indirildi=dt.datetime.now().isoformat(timespec="seconds"))
                    stats["mukerrer"] += 1
                    stats["tahmini_mukerrer"] += 1
                    continue
                from_cache = bool(row["cache_path"] and os.path.exists(row["cache_path"]))
                if from_cache:
                    raw, resp, why = Path(row["cache_path"]).read_bytes(), {}, ""
                    ext = Path(row["cache_path"]).suffix
                else:
                    raw, resp, row2, why = self.fetch(eid, refreshed)
                    row = row2 or row
                    ext = self._ext_of(resp, raw) if raw is not None else ""
                if raw is None:
                    if why in ("durduruldu", "oturum yenilenemedi"):
                        if why == "oturum yenilenemedi":
                            self.log("[x] UYAP'a yeniden giriş yapılamadığı için indirme durduruldu. "
                                     "Giriş yaptıktan sonra aynı filtreyle tekrar başlatın; kalan evraklar indirilecek.")
                        break
                    st = "yok" if why == "yok" else "hata"
                    stats[st] += 1
                    if why == "UYAP listesinde artık yok":
                        self.kat.set_result(eid, hata=why)
                    else:
                        self.kat.set_result(eid, durum=st, hata=why[:200])
                    self.log(f"[-] {row['tur']} ({row['birim']} {row['dosya_no']}): alınamadı — {why}")
                else:
                    sha = content_fingerprint(raw)
                    dup = self.kat.find_sha(sha)
                    if dup and dup["path"] and os.path.exists(dup["path"]):
                        stats["mukerrer"] += 1
                        self.kat.set_result(eid, durum="mukerrer", dup_of=dup["skey"], sha256=sha, size=len(raw),
                                            path=dup["path"], indirildi=dt.datetime.now().isoformat(timespec="seconds"))
                        self.log(f"[=] Mükerrer (aynı içerik zaten var, kaydedilmedi): {row['tur']} → {Path(dup['path']).name}")
                        if tahmin and row["is_ek"]:
                            # v4.9.3: tüm tabloyu yeniden taramak yerine kalıp yerinde öğrenilir (indirme beklemez)
                            canli_harita[self._imza(row)] = (dup["skey"], dup["path"])
                    else:
                        path = unique_path(target_path_for(row, self.base, ext))
                        os.makedirs(win_extended_path(path.parent), exist_ok=True)
                        if from_cache:
                            cpdf = Path(row["cache_path"]).with_suffix(".pdf")
                            safe_replace_file(row["cache_path"], path)
                            if os.path.exists(win_extended_path(cpdf)):
                                safe_replace_file(str(cpdf), str(path.with_suffix(".pdf")))
                            stats["onbellek"] += 1
                        else:
                            tmp = path.with_name(path.name + ".part")
                            safe_write_bytes(tmp, raw)
                            safe_replace_file(tmp, path)
                        pending_folders.add(path.parent)
                        pdf = path.with_suffix(".pdf") if path.with_suffix(".pdf").exists() else None
                        if ext.lower() in (".tif", ".tiff") and not pdf:
                            pdf = tiff_to_pdf(path)
                            if pdf:
                                self.log(f"[pdf] TIF → A4 PDF: {pdf.name}")
                        elif ext.lower() == ".pdf":
                            pdf = path
                        self.kat.set_result(eid, durum="indirildi", path=str(path), pdf_path=str(pdf) if pdf else None,
                                            sha256=sha, size=len(raw), uzanti=ext.lstrip(".").lower(), hata=None,
                                            cache_path=None, indirildi=dt.datetime.now().isoformat(timespec="seconds"))
                        self.kat.set_text(eid, extract_text(path, raw))
                        self._sync_to_drive(path)
                        if pdf:
                            self._sync_to_drive(pdf)
                        stats["indirildi"] += 1
                        since_pause += 1
                        bytes_total += len(raw)
                        self.log(f"[{done}/{total}] {len(raw)//1024} KB{' (önbellekten)' if from_cache else ''}  "
                                 f"{row['birim']} ({row['dosya_no']})  →  {path.name}")
            except Exception as e:
                klog.exception("Evrak indirme döngüsü hatası id=%s: %s", eid, e)
                self.log(f"[!] Evrak #{eid} işlenirken hata oluştu ({e}); sonraki evraka geçiliyor...")
                stats["hata"] += 1
            el = time.time() - t_start
            rate = done / el if el > 0 else 0
            kalan = (total - done) / rate if rate > 0 else 0
            self.progress(done, total, f"%{done * 100 / total:.1f} · {stats['indirildi']} indirildi · "
                                       f"{stats['mukerrer']} mükerrer · {stats['hata']} hata · "
                                       f"kalan ~{_sure(kalan)} · {bytes_total / 1048576:.1f} MB")
            if from_cache:
                continue
            if since_pause and since_pause % self.batch_n == 0:
                since_pause = 0
                self._sleep(self.batch_pause)
            else:
                self._sleep(random.uniform(self.min_d, self.max_d))
        for fo in pending_folders:
            self._queue_conversion(fo)
        if getattr(self, "_conv_q", None) is not None and self._conv_q.unfinished_tasks:
            self.log("[*] Kalan UDF'ler PDF'e çevriliyor...")
            self._conv_q.join()
        self.log(f"[✓] Bitti ({_sure(time.time() - t_start)}): {stats['indirildi']} indirildi "
                 f"({stats['onbellek']} önbellekten), {stats['mukerrer']} mükerrer (kaydedilmedi; "
                 f"{stats['tahmini_mukerrer']} tanesi hiç indirilmeden ayıklandı), "
                 f"{stats['yok']} UYAP'ta dosyası yok, {stats['hata']} hata, {stats['atlandi']} zaten vardı.")
        return stats


def _sure(sn: float) -> str:
    sn = int(max(0, sn))
    if sn < 60:
        return f"{sn} sn"
    if sn < 3600:
        return f"{sn // 60} dk {sn % 60:02d} sn"
    return f"{sn // 3600} sa {(sn % 3600) // 60:02d} dk"


def export_csv(katalog: Katalog, f: dict, path: Path) -> int:
    import csv
    rows = katalog.query(f, limit=10_000_000)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Tarih", "Birim", "Dosya No", "Dosya Durumu", "Asıl/Ek", "Evrak Türü", "Üst Evrak",
                    "Açıklama", "Kategori", "Müvekkil", "Durum", "Dosya Yolu", "PDF"])
        for r in rows:
            w.writerow([r["tarih"], r["birim"], r["dosya_no"], r["dosya_durum"], "Ek" if r["is_ek"] else "Asıl",
                        r["tur"], r["ust_tur"], r["aciklama"], KATEGORI_ADI.get(r["kategori"], r["kategori"]),
                        r["muvekkil"], DURUMLAR.get(r["durum"], r["durum"]), r["path"] or "", r["pdf_path"] or ""])
    return len(rows)
