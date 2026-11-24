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
