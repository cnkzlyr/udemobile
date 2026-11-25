# -*- coding: utf-8 -*-
"""v4.10.1: UETS taze CSV alınamazsa ESKİ YEREL CSV ile devam edilmez; yalnız taze CSV'deki tebligatlar işlenir."""
import argparse
import os
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("TICKTICK_TOKEN", "test")

import main  # noqa: E402


def _args(**k):
    d = dict(autocontrol=False, excel=None, dedup=False, csv=None, offline=False, headless=True, count=None,
             watch=False, force=False, apply=False)
    d.update(k)
    return argparse.Namespace(**d)


def test_csv_inmezse_eski_csv_kullanilmaz(monkeypatch):
    monkeypatch.setitem(sys.modules, "baglanti", types.SimpleNamespace(on_kontrol=lambda: (True, [])))
    import uets_downloader

    def patla(**k):
        raise RuntimeError("UETS'ye girilemedi")

    monkeypatch.setattr(uets_downloader, "login_and_download", patla)
    cagrildi = []
    monkeypatch.setattr(main, "run_synchronization", lambda **k: cagrildi.append(k))
    with pytest.raises(SystemExit) as e:
        main._main(_args())
    assert e.value.code == 4
    assert not cagrildi, "eski yerel CSV ile senkron yapılmamalı"


def test_taze_csv_ile_senkron(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "baglanti", types.SimpleNamespace(on_kontrol=lambda: (True, [])))
    import uets_downloader
    csv = tmp_path / "tebligatlar.csv"
    csv.write_text("x", encoding="utf-8")
    monkeypatch.setattr(uets_downloader, "login_and_download", lambda **k: str(csv))
    cagrildi = []
    monkeypatch.setattr(main, "run_synchronization", lambda **k: cagrildi.append(k))
    main._main(_args())
    assert cagrildi and cagrildi[0]["csv_path"] == str(csv)
