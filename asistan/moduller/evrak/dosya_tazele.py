# -*- coding: utf-8 -*-
"""
TEK DOSYAYI UYAP'TAN ŞİMDİ GETİR: sunucunun /api/dosya/tazele ucu bu betiği çağırır.

  python dosya_tazele.py --dkey "<birim>|<esas>"

Gizli UYAP oturumu (CDP 9223) kullanılır; görünür tarayıcı açılmaz. Sırasıyla:
  1. Dosyanın bu oturumdaki kimliği (dosya_id) tazelenir,
  2. Taraflar (müvekkil tespiti dahil),
  3. Evrak listesinin TAMAMI (kataloğa; indirmeden),
  4. Hesap: icra ise kapak hesabı + safahat (ödeme emri tebliği, itiraz, haciz...), değilse tahsilat/reddiyat/harç.
Çıktı: son satırda tek satır JSON {"taraf": n, "evrak": n, "hesap": bool, "safahat": bool, "hata": ""}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("CANASISTAN_GORUNMEZ", "1")


def yaz(d: dict) -> None:
    print(json.dumps(d, ensure_ascii=False), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dkey", required=True)
    a = ap.parse_args()
    import evrak_katalog as ek
    import uyap_indirici as ui
    from uyap_watcher import _kayitli_pin

    kat = ek.Katalog()
    bridge = ui.UyapBrowserBridge(port=ui.CDP_PORT)
    ok, msg = bridge.ensure_ready("uyap")
    if not ok:
        yaz({"hata": f"UYAP tarayıcısına bağlanılamadı: {msg}"})
        return 3
    if not bridge.is_logged_in():
        print("UYAP oturumu açılıyor (Mobil İmza onayı telefonunuza gelebilir)...", flush=True)
        ok, msg = bridge.akilli_oturum_ac(pin=_kayitli_pin(ui), status_cb=lambda m: print(m, flush=True), sure_siniri_s=300)
        if not ok:
            yaz({"hata": f"UYAP oturumu açılamadı: {msg}"})
            return 3
    motor = ek.Motor(bridge, kat, ek.DATA_DIR / "UYAP_Indirilenler", log=lambda m: print(m, flush=True))
    cases = bridge.query_tum_dosyalar(include_closed=True, use_cache=False) or []
    case = next((c for c in cases if motor._case_dkey(c) == a.dkey), None)
    if not case:
        yaz({"hata": "Dosya UYAP'taki dosya listenizde bulunamadı (vekâlet kaydı kalkmış olabilir)."})
        return 4
    cid = str(case.get("dosyaId") or case.get("dosyaID") or "")
    sonuc = {"taraf": 0, "evrak": 0, "hesap": False, "safahat": False, "hata": ""}

    print("Taraflar alınıyor...", flush=True)
    taraf = motor._taraflar_batch([cid]).get(cid)
    from uyap_indirici import infer_yargi_kategorisi
    avukat = motor._avukat_adi([taraf] if taraf else [])
    kat.upsert_dosya(case, taraf if taraf else None, avukat, infer_yargi_kategorisi(str(case.get("birimAdi") or "")), "")
    kat.db.commit()
    sonuc["taraf"] = len(taraf or [])

    print("Evrak listesi alınıyor...", flush=True)
    sayfalar = motor._evraklar_batch([cid]).get(cid)
    if isinstance(sayfalar, list):
        sonuc["evrak"] = kat.ingest_pages(a.dkey, sayfalar, "")
        kat.set_tarama(a.dkey, "tamam")
    elif isinstance(sayfalar, dict):
        sonuc["hata"] = f"UYAP evrak listesini vermedi: {sayfalar.get('err')} {sayfalar.get('msg', '')}".strip()
    with kat.db:
        kat.db.execute("UPDATE dosya SET dosya_id=? WHERE dkey=?", (cid, a.dkey))

    print("Hesap ve safahat alınıyor...", flush=True)
    try:
        from uyap_finans_safahat import UyapFinansSafahatManager, icra_mi
        fm = UyapFinansSafahatManager(bridge=bridge)
        birim = str(case.get("birimAdi") or "")
        dno = str(case.get("dosyaNo") or case.get("dosyaNO") or "")
        if icra_mi(birim, str(case.get("dosyaTur") or "")):
            fm.fetch_icra_hesap(cid, a.dkey, birim, dno)
            sonuc["hesap"] = True
        else:
            fm.fetch_finans(cid, a.dkey, birim, dno, is_icra=False)
            sonuc["hesap"] = True
        try:
            fm.fetch_safahat(cid, a.dkey, birim, dno)
            sonuc["safahat"] = True
        except Exception as e:  # noqa: BLE001
            print(f"Safahat alınamadı: {e}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"Hesap alınamadı: {e}", flush=True)
    yaz(sonuc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
