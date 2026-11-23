# -*- coding: utf-8 -*-
"""v4.9.3 — Toplu öncelikli indirme isteği (ör. "UYAP: tebligat evraklarını indir").

Eskiden bu görev 731 dosyanın tamamını UYAP'ta yeniden listeliyor (147 paket, saatler), Senkron'la aynı gizli
tarayıcıyı paylaşıp ikisini de yavaşlatıyordu. Oysa tebligat/mazbata evrakları katalogda zaten var. Artık istek
öncelik kuyruğuna (oncelikli_dosyalar.json → "kategoriler") yazılır; Senkron (uyap_watcher) bunları her şeyden
önce indirir, PDF'e çevirir ve Drive'a eşitler. Bu betik yalnızca kuyruğa yazar ve ilerlemeyi canlı gösterir.

  python oncelik_kuyruk.py --kategori tebligat
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

DATA_DIR = Path(os.environ.get("UYAP_VERI_DIZINI") or Path(__file__).resolve().parent)
KUYRUK = DATA_DIR / "oncelikli_dosyalar.json"
KOSUL = {"tebligat": "(kategori='tebligat' OR lower(COALESCE(ara,'')) LIKE '%teblig%' OR lower(COALESCE(ara,'')) LIKE '%mazbata%')"}


def kuyruga_yaz(kategori: str) -> None:
    try:
        v = json.loads(KUYRUK.read_text(encoding="utf-8"))
        if not isinstance(v, dict):
            v = {}
    except (OSError, ValueError):
        v = {}
    kat = [x for x in v.get("kategoriler") or [] if x != kategori] + [kategori]
    v.update(kategoriler=kat, zaman=time.time())
    gecici = KUYRUK.with_suffix(".gorev.tmp")
    gecici.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    os.replace(gecici, KUYRUK)


def sayim(kategori: str) -> tuple[int, int]:
    db = DATA_DIR / "uyap_katalog.db"
    if not db.is_file():
        return 0, 0
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    try:
        k = KOSUL[kategori]
        toplam = c.execute(f"SELECT COUNT(*) FROM evrak WHERE {k}").fetchone()[0]
        kalan = c.execute(f"SELECT COUNT(*) FROM evrak WHERE {k} AND durum NOT IN ('indirildi','mukerrer','yok','hata') "
                          "AND (pdf_path IS NULL OR pdf_path='')").fetchone()[0]
        return toplam, kalan
    finally:
        c.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kategori", default="tebligat", choices=sorted(KOSUL))
    ap.add_argument("--en-cok-saat", type=float, default=12)
    a = ap.parse_args()
    toplam, kalan = sayim(a.kategori)
    if not kalan:
        print(f"✅ Katalogdaki {toplam} {a.kategori} evrakının tamamı zaten indirilmiş.", flush=True)
        return 0
    kuyruga_yaz(a.kategori)
    print(f"⚡ {kalan} / {toplam} {a.kategori} evrakı öncelik kuyruğuna alındı; Senkron her şeyden önce indirip "
          "Drive'a eşitleyecek (bu görev yalnızca ilerlemeyi gösterir).", flush=True)
    bas, onceki = time.time(), kalan
    while time.time() - bas < a.en_cok_saat * 3600:
        time.sleep(15)
        toplam, kalan = sayim(a.kategori)
        if kalan != onceki:
            print(f"   ↳ {toplam - kalan}/{toplam} indi · {kalan} kaldı", flush=True)
            onceki = kalan
        if not kalan:
            print(f"✅ Bitti: {toplam} {a.kategori} evrakının tamamı indi ve Drive'a eşitlendi.", flush=True)
            return 0
    print(f"⏳ Süre doldu; {kalan} evrak kuyrukta kalmaya devam ediyor (Senkron indirmeyi sürdürür).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
