#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak Yöneticisi — tek giriş noktası (masaüstü uygulaması / paketlenmiş exe)
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.

Kullanım:
  UYAPEvrak                       -> Evrak kataloğu arayüzü (varsayılan)
  UYAPEvrak --pdf DOSYA...        -> PDF'e dönüştür penceresi (sağ tık menüsü bunu çağırır)
  UYAPEvrak --sag-tik-kur | --sag-tik-kaldir
  UYAPEvrak --tebligat_yoneticisi | --enrich_and_rename_documents
  UYAPEvrak --donustur DOSYA...   -> komut satırından PDF dönüştürme
  UYAPEvrak --cli ...  / --browser-only / --katalog-tara ...   -> uyap_indirici komut satırı
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "UYAPEvrak"


def _user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.environ.get("PREFIX", "").startswith("/data/data/com.termux"):
        base = Path.home()
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def _download_dir() -> Path:
    for c in (Path("/sdcard/Download"), Path.home() / "storage" / "downloads"):
        if c.exists():
            return c / "UYAP_Indirilenler"
    docs = Path.home() / "Documents"
    return (docs if docs.exists() else Path.home()) / "UYAP_Indirilenler"


def _prepare_environment():
    """Paketlenmiş (frozen) uygulamada program klasörü yazılamaz olabilir: veriler kullanıcı klasörüne gider."""
    if getattr(sys, "frozen", False):
        data = Path(os.environ.get("UYAP_VERI_DIZINI") or _user_data_dir())
        data.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("UYAP_VERI_DIZINI", str(data))
        os.environ.setdefault("UYAP_INDIRME_DIZINI", str(_download_dir()))
        os.chdir(data)
        # Kullanıcının koyduğu jar klasörünü de ara
        if not os.environ.get("UYAP_JARS") and (data / "jars").exists():
            os.environ["UYAP_JARS"] = str(data / "jars")
    here = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def main():
    _prepare_environment()
    args = sys.argv[1:]
    if not args or args[0] in ("--katalog", "--gui"):
        try:
            import katalog_gui
            katalog_gui.main()
            return
        except Exception as e:
            # Grafik ekran yoksa (ör. SSH / headless sunucu) terminal menüsüne geç
            print(f"[i] Grafik arayüz başlatılamadı ({e}), terminal konsoluna geçiliyor...")
            import baslat
            baslat.main()
            return

    a0 = args[0]
    if a0 in ("--cli", "--terminal", "--konsol", "-c"):
        sys.argv = [sys.argv[0]] + args[1:]
        import baslat
        baslat.main()
    elif a0 in ("--arsiv", "--dosya-arsivle"):
        sys.argv = [sys.argv[0]] + args[1:]
        import dosya_arsivle
        dosya_arsivle.main()
    elif a0 == "--drive-esitle":
        sys.argv = [sys.argv[0]] + args[1:]
        import drive_arsiv_esitle
        drive_arsiv_esitle.main()
    elif a0 == "--drive-denetle":
        sys.argv = [sys.argv[0]] + args[1:]
        import drive_arsiv_denetle
        drive_arsiv_denetle.main()
    elif a0 in ("--imzala", "--uyap-imzala"):
        sys.argv = [sys.argv[0]] + args[1:]
        import uyap_imzala
        uyap_imzala.main()
    elif a0 in ("--nobetci", "--watcher"):
        sys.argv = [sys.argv[0]] + args[1:]
        import uyap_watcher
        uyap_watcher.main()
    elif a0 == "--pdf":
        import sag_tik
        sag_tik.run_gui(args[1:])
    elif a0 == "--sag-tik-kur":
        import sag_tik
        print(sag_tik.kur())
    elif a0 == "--sag-tik-kaldir":
        import sag_tik
        print(sag_tik.kaldir())
    elif a0 == "--donustur":
        import donusturucu
        r = donusturucu.convert_many(args[1:], progress=lambda d, t, n: print(f"[{d}/{t}] {n}") if n else None)
        print(f"Bitti: {r['tamam']} dönüştürüldü, {r['vardi']} zaten vardı, {r['hata']} hata.")
    elif a0 == "--tebligat_yoneticisi":
        sys.argv = [sys.argv[0]] + args[1:]
        import tebligat_yoneticisi
        tebligat_yoneticisi.scan_and_sync_all_tebligats()
    elif a0 == "--enrich_and_rename_documents":
        sys.argv = [sys.argv[0]] + args[1:]
        import enrich_and_rename_documents
        enrich_and_rename_documents.main()
    elif a0 in ("--surum", "--version"):
        import gui_ekler
        print(f"{gui_ekler.UYGULAMA_ADI} {gui_ekler.SURUM}\n{gui_ekler.IMZA}")
    else:
        import uyap_indirici
        uyap_indirici.main()


if __name__ == "__main__":
    main()
