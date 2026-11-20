# -*- coding: utf-8 -*-
"""
EVRAK ÖNİZLEME (indirmeden): sunucunun /api/evrak/onizle ucu bu betiği çağırır.

  python evrak_onizle.py --skey <skey>

1. Evrakın ORİJİNALİ (UDF / TIFF / PDF ...) yerelde yoksa UYAP'tan ÖNBELLEĞE alınır (indirme klasörüne değil;
   sonradan indirilirken buradan taşınır). Gizli UYAP oturumu (CDP 9223) kullanılır, görünür tarayıcı açılmaz.
2. PDF'i yoksa üretilir (UDF → Havelsan motoru, TIFF → çok sayfalı A4 PDF).
3. Çıktı: tek satır JSON  {"orijinal": yol, "pdf": yol|null, "uzanti": ".udf", "hata": ""}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("CANASISTAN_GORUNMEZ", "1")


def _var(p) -> Path | None:
    return Path(p) if p and os.path.isfile(p) and os.path.getsize(p) > 0 else None


def yerelde(row) -> tuple[Path | None, Path | None]:
    keys = row.keys()
    orj = _var(row["path"]) or (_var(row["cache_path"]) if "cache_path" in keys else None)
    pdf = _var(row["pdf_path"])
    if not pdf and orj:
        pdf = _var(orj.with_suffix(".pdf")) if orj.suffix.lower() != ".pdf" else orj
    return orj, pdf


def pdfe_cevir(orj: Path) -> Path | None:
    if orj.suffix.lower() == ".pdf":
        return orj
    try:
        import donusturucu as dn
        _st, pdf, _m = dn.convert(orj)
        if pdf:
            return Path(pdf)
    except Exception:  # noqa: BLE001
        pass
    if orj.suffix.lower() in (".tif", ".tiff"):
        import evrak_katalog as ek
        return ek.tiff_to_pdf(orj)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skey", required=True)
    ap.add_argument("--pdfsiz", action="store_true", help="PDF'e çevirme (yalnız orijinal)")
    a = ap.parse_args()
    import evrak_katalog as ek
    kat = ek.Katalog()
    row = kat.by_skey(a.skey)
    if not row:
        print(json.dumps({"hata": "Evrak katalogda yok"}), flush=True)
        return 2
    orj, pdf = yerelde(row)
    if not orj:
        import uyap_indirici as ui
        from uyap_watcher import _kayitli_pin
        bridge = ui.UyapBrowserBridge(port=ui.CDP_PORT)
        ok, msg = bridge.ensure_ready("uyap")
        if not ok:
            print(json.dumps({"hata": f"UYAP tarayıcısına bağlanılamadı: {msg}"}, ensure_ascii=False), flush=True)
            return 3
        if not bridge.is_logged_in():
            ok, msg = bridge.akilli_oturum_ac(pin=_kayitli_pin(ui), status_cb=lambda m: None, sure_siniri_s=240)
            if not ok:
                print(json.dumps({"hata": f"UYAP oturumu açılamadı: {msg}"}, ensure_ascii=False), flush=True)
                return 3
        motor = ek.Motor(bridge, kat, ek.DATA_DIR / "UYAP_Indirilenler", log=lambda m: None)
        motor.fetch_to_cache(row["id"])
        row = kat.by_skey(a.skey)
        orj, pdf = yerelde(row)
        if not orj:
            print(json.dumps({"hata": "UYAP evrakı vermedi (oturum ya da evrak silinmiş olabilir)"}, ensure_ascii=False), flush=True)
            return 4
    if not pdf and not a.pdfsiz:
        pdf = pdfe_cevir(orj)
    print(json.dumps({"orijinal": str(orj), "pdf": str(pdf) if pdf else None, "uzanti": orj.suffix.lower(), "hata": ""},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
