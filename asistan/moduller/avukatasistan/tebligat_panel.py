#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Avukat Asistanı (avukat_gui.py) işlevlerinin penceresiz (Tk'sız) karşılığı.

Masaüstündeki Tk penceresi telefonda açılamadığı için aynı işlemler bu betikle asistan paneline taşındı
(CanEditor → Hukuk Asistanı → Tebligatlar). Termux gerekmez; sunucu bu betiği alt süreç olarak çalıştırır.

Komutlar:
  liste                 Tüm tebligatların uçtan uca durumu (UETS CSV + EYP arşivi + TickTick + Notion) → JSON
  zorla --barkod B      Seçili tebligatı TickTick'e (EYP ekleriyle) zorla ekle / yenile — GUI'deki "⚡" düğmesi
  temizle               TickTick mükerrer temizliği ve sağlık denetimi — GUI'deki "🧹" düğmesi
  excel                 UYAP dosyalar.xlsx senkronizasyonu — GUI'deki "📑" düğmesi

Çıktı: son satır "@@SONUC@@" + JSON (öncesindeki satırlar canlı günlüktür).
"""
from __future__ import annotations

# Android (Termux'suz): gömülü glibc ad çözümleyemez → bağımsız DNS çözücüyü bu süreçte de kur
# (sitecustomize'a güvenmeden; v4.4.0'da nöbetçi "Temporary failure in name resolution" veriyordu)
if __import__("os").environ.get("CANASISTAN_ANDROID") == "1":
    try:
        import sys as _s, pathlib as _p
        _s.path.insert(0, str(_p.Path(__file__).resolve().parents[2]))
        import dns_cozucu as _dns
        _dns.yama_kur()
    except Exception:  # noqa: BLE001
        pass


import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ISARET = "@@SONUC@@"


def _sonuc(veri) -> None:
    sys.stdout.flush()
    print(ISARET + json.dumps(veri, ensure_ascii=False, default=str))


def liste() -> list[dict]:
    from autocontrol import inspect_all_tebligatlar
    out = []
    for d in inspect_all_tebligatlar() or []:
        nc = d.get("notion_case") or {}
        out.append({
            "idx": d.get("idx"), "barkod": d.get("barcode"), "mahkeme": d.get("court"), "esas": d.get("esas_no"),
            "gelis": d.get("gelis_str"), "son_gun": d.get("target_str"), "liste": d.get("list_name"),
            "eyp": bool(d.get("has_local_eyp")), "ek": bool(d.get("has_attachment")),
            "muvekkil": nc.get("client_name") or "", "notion_url": nc.get("url") or "",
            "durum_kodu": d.get("status_code"), "durum": d.get("status_desc"), "renk": d.get("status_color"),
        })
    return out


def zorla(barkod: str) -> dict:
    from autocontrol import inspect_all_tebligatlar
    from eyp_parser import parse_eyp_file
    from ticktick_sync import find_or_create_parent_task, create_or_update_uets_subtask

    item = next((d for d in inspect_all_tebligatlar() or [] if str(d.get("barcode")) == str(barkod)), None)
    if not item:
        raise SystemExit(f"Barkod bulunamadı: {barkod}")
    nc = item.get("notion_case") or {}
    raw = item["raw_item"]
    print(f"⚡ TickTick'e aktarılıyor: {item['court']} [{item['esas_no']}] (Barkod: {barkod})")
    parent = find_or_create_parent_task(item["court"], item["esas_no"], item["project_id"], nc.get("client_tag", ""), nc.get("url", ""))
    parent_id = parent[0] if isinstance(parent, (tuple, list)) else parent
    if item.get("local_eyp_path"):
        tam = parse_eyp_file(item["local_eyp_path"], extract_files=True)
        if tam:
            raw["documents"] = tam.get("documents", [])
            raw["extracted_paths"] = tam.get("extracted_paths", [])
            print(f"📎 EYP ekleri hazır: {len(raw['extracted_paths'])} dosya")
    res = create_or_update_uets_subtask(raw, item["project_id"], parent_id, client_tag=nc.get("client_tag", ""),
                                        notion_url=nc.get("url", ""), list_name=item["list_name"],
                                        is_cmk=nc.get("is_cmk", False), force=True)
    print(f"✅ Sonuç: {res}")
    return {"sonuc": str(res)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("komut", choices=["liste", "zorla", "temizle", "excel"])
    ap.add_argument("--barkod", default="")
    a = ap.parse_args()
    if a.komut == "liste":
        _sonuc({"tebligatlar": liste()})
    elif a.komut == "zorla":
        _sonuc(zorla(a.barkod))
    elif a.komut == "temizle":
        from ticktick_sync import audit_and_heal_all_tasks
        _sonuc({"sonuc": str(audit_and_heal_all_tasks())})
    elif a.komut == "excel":
        from sync_uyap_excel import run_sync
        run_sync(apply=True)
        _sonuc({"sonuc": "Excel senkronizasyonu tamamlandı"})


if __name__ == "__main__":
    main()
