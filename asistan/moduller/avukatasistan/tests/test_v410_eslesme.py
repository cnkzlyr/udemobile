# -*- coding: utf-8 -*-
"""v4.10.0: başlığı değiştirilmiş / kimlik satırı silinmiş görevler de mükerrer kontrolünde tanınmalı.
EN: title-independent duplicate detection, including completed and won't-do tasks."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("TICKTICK_TOKEN", "test")

import kimlik  # noqa: E402
import ticktick_sync as ts  # noqa: E402


def _gorev(baslik, icerik, status=0, tid="t1"):
    return {"id": tid, "title": baslik, "content": icerik, "status": status, "projectId": "p"}


def test_kimlik_satiri_silinmis_ve_baslik_degismis_kapali_gorev_taninir(monkeypatch):
    yeni = kimlik.satir("TEBLİGAT", mahkeme="Oltu 3. Asliye Hukuk", esas="2026/24", barkod="5003283066058")
    eski = _gorev("Cevap dilekçesi yazılacak (müvekkil aradı)", "Barkod: 5003283066058\nnot", status=-1)
    monkeypatch.setattr(ts, "get_completed_tasks_live", lambda force_refresh=False: [eski])
    assert ts.kapali_kopya_bul({"content": yeni, "title": "📨 TEBLİGAT - Oltu - 2026/24 Esas"}) is eski


def test_farkli_barkod_eslesmez(monkeypatch):
    yeni = kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="5003283066058")
    eski = _gorev("Başka iş", "Barkod: 5003283066999", status=2)
    monkeypatch.setattr(ts, "get_completed_tasks_live", lambda force_refresh=False: [eski])
    assert ts.kapali_kopya_bul({"content": yeni}) is None


def test_ek_alt_gorevi_tebligati_engellemez(monkeypatch):
    yeni = kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="5003283066058")
    ek = _gorev("📎 Ekler", kimlik.satir("EK", barkod="5003283066058"), status=2)
    monkeypatch.setattr(ts, "get_completed_tasks_live", lambda force_refresh=False: [ek])
    assert ts.kapali_kopya_bul({"content": yeni}) is None


def test_aktif_kopya_basliktan_bagimsiz(monkeypatch):
    yeni = kimlik.satir("TEBLİGAT", mahkeme="X", esas="2026/1", barkod="5003283066058")
    aktif = _gorev("Yeniden adlandırılmış", "kullanıcı notu 5003283066058")
    monkeypatch.setattr(ts, "tum_aktif_gorevler", lambda force=False: [aktif])
    assert ts.ayni_kimlikli_aktif(yeni) is aktif


def test_evrak_basina_gorev_acilmaz_toplu_liste(monkeypatch):
    """v4.10.0: aynı dosyaya gelen evraklar tek '📥 UYAP evrakları' görevinin kontrol listesinde toplanır."""
    gorevler, istekler = {}, []

    def tt_post(url, payload, what="", timeout=12):
        istekler.append((url, payload))
        if url.endswith("/task"):
            t = dict(payload, id=f"g{len(gorevler) + 1}", status=0)
            gorevler[t["id"]] = t
            return t
        t = gorevler[payload["id"]]
        t.update(payload)
        return t

    monkeypatch.setattr(ts, "tt_post", tt_post)
    monkeypatch.setattr(ts, "tum_aktif_gorevler", lambda force=False: [t for t in gorevler.values() if t["status"] == 0])
    monkeypatch.setattr(ts, "get_completed_tasks_live", lambda force_refresh=False: [])
    monkeypatch.setattr(ts, "gorev_getir", lambda pid, tid: gorevler.get(tid))
    monkeypatch.setattr(ts, "find_or_create_parent_task", lambda *a, **k: ("kart", "p"))
    for tur, tarih in (("Tensip Zaptı", "2020-03-10"), ("Bilirkişi Raporu", "2026-11-20"), ("Tensip Zaptı", "2020-03-10")):
        ts.uyap_evrak_gorevi("Kırıkkale 3. Asliye Hukuk Mahkemesi", "2026/419", tur, tarih=tarih)
    assert len(gorevler) == 1, "evrak başına görev açılmamalı"
    g = next(iter(gorevler.values()))
    assert len(g["items"]) == 2, "aynı evrak iki kez listelenmemeli"
    assert g["parentId"] == "kart" and "(2)" in g["title"]


def test_eski_evraka_sahte_son_gun_yazilmaz():
    import sys as _s
    from pathlib import Path as _P
    _s.path.insert(0, str(_P(__file__).resolve().parents[3]))
    import entegrasyon
    assert entegrasyon._yasal_son_gun_iso("Kırıkkale 3. Asliye Hukuk", True, "2021-02-18") == ""
    import datetime as _dt
    bugun = _dt.date.today().isoformat()
    assert entegrasyon._yasal_son_gun_iso("Kırıkkale 3. Asliye Hukuk", False, bugun) > bugun
