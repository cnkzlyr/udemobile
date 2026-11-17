#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak Yöneticisi — Sağ tık "PDF'e dönüştür" menüsü
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.

Kurulum / kaldırma (yönetici yetkisi gerekmez, yalnızca bu kullanıcı için):
    python sag_tik.py --kur
    python sag_tik.py --kaldir
Kullanım: Dosya Gezgini'nde .udf .tif .tiff .docx .doc .rtf .odt .jpg .png dosyalarını (tek veya çoklu)
seçip sağ tık > "PDF'e dönüştür (UYAP)". Windows 11'de menü "Daha fazla seçenek göster" altındadır;
ayrıca sağ tık > "Gönder" > "PDF'e dönüştür (UYAP)" çoklu seçimde tek seferde çalışır.
Linux (Nautilus/Dolphin) için de betik menüsü kurulur.

Çoklu seçimde Windows her dosya için ayrı işlem başlatır; bu betik dosyaları ortak bir kuyruğa
yazar ve tek bir pencerede sırayla dönüştürür.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import donusturucu as dn  # noqa: E402

MENU_ADI = "PDF'e dönüştür (UYAP)"
ANAHTAR = "UYAPEvrakPDF"
QDIR = Path(tempfile.gettempdir()) / "uyap_pdf_kuyruk"
LOCK = QDIR / ".kilit"


# ---------------------------------------------------------------------------
# Komut satırı (kayıt defterine yazılacak çağrı)
# ---------------------------------------------------------------------------
def _launcher() -> list[str]:
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        gui = exe.with_name("UYAPEvrak" + exe.suffix)  # konsol penceresi açmayan sürüm
        return [str(gui if gui.exists() else exe), "--pdf"]
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    return [str(pyw if pyw.exists() else py), str(Path(__file__).resolve())]


def kur() -> str:
    if os.name == "nt":
        import winreg
        cmd = " ".join(f'"{c}"' for c in _launcher()) + ' "%1"'
        icon = sys.executable
        for ext in sorted(dn.DESTEKLENEN):
            base = rf"Software\Classes\SystemFileAssociations\{ext}\shell\{ANAHTAR}"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base) as k:
                winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, MENU_ADI)
                winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, icon)
                winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\command") as k:
                winreg.SetValueEx(k, "", 0, winreg.REG_SZ, cmd)
        # "Gönder" menüsü: çoklu seçimi tek çağrıda verir
        sendto = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "SendTo" / f"{MENU_ADI}.lnk"
        lc = _launcher()
        ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK);"
              "$s.TargetPath=$env:TGT;$s.Arguments=$env:ARGS;$s.IconLocation=$env:TGT;$s.Save()")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False,
                       env=dict(os.environ, LNK=str(sendto), TGT=lc[0], ARGS=" ".join(f'"{a}"' for a in lc[1:])),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return "Sağ tık menüsü ve 'Gönder' kısayolu kuruldu."
    # Linux: Nautilus betiği + Dolphin servis menüsü
    lc = " ".join(f'"{c}"' for c in _launcher())
    nd = Path.home() / ".local/share/nautilus/scripts"
    nd.mkdir(parents=True, exist_ok=True)
    sc = nd / MENU_ADI
    sc.write_text(f'#!/bin/sh\nIFS="\n"\nexec {lc} $NAUTILUS_SCRIPT_SELECTED_FILE_PATHS\n', encoding="utf-8")
    sc.chmod(0o755)
    dd = Path.home() / ".local/share/kio/servicemenus"
    dd.mkdir(parents=True, exist_ok=True)
    mimes = "application/octet-stream;image/tiff;image/jpeg;image/png;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/msword"
    (dd / "uyap-pdf.desktop").write_text(
        "[Desktop Entry]\nType=Service\nX-KDE-ServiceTypes=KonqPopupMenu/Plugin\n"
        f"MimeType={mimes}\nActions=uyappdf\n\n[Desktop Action uyappdf]\nName={MENU_ADI}\nExec={lc} %F\n",
        encoding="utf-8")
    (dd / "uyap-pdf.desktop").chmod(0o755)
    return "Nautilus betiği ve Dolphin servis menüsü kuruldu."


def kaldir() -> str:
    if os.name == "nt":
        import winreg

        def rm(path):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_ALL_ACCESS) as k:
                    while True:
                        try:
                            rm(path + "\\" + winreg.EnumKey(k, 0))
                        except OSError:
                            break
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except OSError:
                pass
        for ext in sorted(dn.DESTEKLENEN):
            rm(rf"Software\Classes\SystemFileAssociations\{ext}\shell\{ANAHTAR}")
        try:
            (Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "SendTo" / f"{MENU_ADI}.lnk").unlink()
        except OSError:
            pass
        return "Sağ tık menüsü kaldırıldı."
    for p in (Path.home() / ".local/share/nautilus/scripts" / MENU_ADI,
              Path.home() / ".local/share/kio/servicemenus/uyap-pdf.desktop"):
        try:
            p.unlink()
        except OSError:
            pass
    return "Betik menüleri kaldırıldı."


def kurulu_mu() -> bool:
    if os.name == "nt":
        import winreg
        try:
            winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\SystemFileAssociations\.udf\shell\{ANAHTAR}").Close()
            return True
        except OSError:
            return False
    return (Path.home() / ".local/share/nautilus/scripts" / MENU_ADI).exists()


# ---------------------------------------------------------------------------
# Tek pencerede toplu dönüştürme (kuyruk + kilit)
# ---------------------------------------------------------------------------
def _enqueue(paths):
    QDIR.mkdir(parents=True, exist_ok=True)
    tmp = QDIR / f"{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps([str(Path(p).resolve()) for p in paths]), encoding="utf-8")
    tmp.replace(tmp.with_suffix(".json"))


def _take_lock() -> bool:
    QDIR.mkdir(parents=True, exist_ok=True)
    try:
        if LOCK.exists() and time.time() - LOCK.stat().st_mtime > 600:
            LOCK.unlink()  # eski/yarım kalmış kilit
        fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except OSError:
        return False


def _drain_queue() -> list[str]:
    out = []
    for f in sorted(QDIR.glob("*.json"), key=lambda x: x.stat().st_mtime):
        try:
            out += json.loads(f.read_text(encoding="utf-8"))
            f.unlink()
        except (OSError, ValueError):
            pass
    return out


def run_gui(paths):
    _enqueue(paths)
    time.sleep(0.4)  # aynı anda başlatılan kardeş işlemlerin dosyalarını kuyruğa yazmasını bekle
    if not _take_lock():
        return  # başka bir pencere zaten dönüştürüyor; dosyalarımız onun kuyruğunda
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.title("PDF'e dönüştür — UYAP Evrak Yöneticisi")
    root.geometry("520x170")
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)
    lbl = ttk.Label(frm, text="Hazırlanıyor…", wraplength=490)
    lbl.pack(anchor="w")
    bar = ttk.Progressbar(frm, mode="determinate", length=490)
    bar.pack(pady=8)
    info = ttk.Label(frm, text="", foreground="#555", wraplength=490, justify="left")
    info.pack(anchor="w")
    ttk.Label(frm, text="© Av. Can KIZILYAR", foreground="#999").pack(anchor="e", side="bottom")
    state = {"done": 0, "total": 0, "ok": 0, "var": 0, "err": [], "fin": False, "cur": ""}

    def worker():
        try:
            while True:
                batch = dn.collect(_drain_queue())
                if not batch:
                    time.sleep(1.2)
                    batch = dn.collect(_drain_queue())
                    if not batch:
                        break
                state["total"] += len(batch)
                for f in batch:
                    state["cur"] = f.name
                    st, _pdf, msg = dn.convert(f)
                    if st == "tamam":
                        state["ok"] += 1
                    elif st == "vardi":
                        state["var"] += 1
                    elif st == "hata":
                        state["err"].append(f"{f.name}: {msg}")
                    state["done"] += 1
        finally:
            try:
                LOCK.unlink()
            except OSError:
                pass
            state["fin"] = True

    def tick():
        bar.config(maximum=max(state["total"], 1), value=state["done"])
        if not state["fin"]:
            lbl.config(text=f"Dönüştürülüyor {state['done'] + 1}/{state['total']}: {state['cur']}")
            root.after(200, tick)
            return
        lbl.config(text=f"Bitti: {state['ok']} PDF oluşturuldu, {state['var']} zaten vardı, {len(state['err'])} hata.")
        if state["err"]:
            info.config(text="\n".join(state["err"][:4]) + ("\n…" if len(state["err"]) > 4 else ""), foreground="#a31515")
            root.after(20000, root.destroy)
        else:
            root.after(3500, root.destroy)

    threading.Thread(target=worker, daemon=True).start()
    root.after(200, tick)
    root.mainloop()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--kur" in argv:
        print(kur())
        return
    if "--kaldir" in argv:
        print(kaldir())
        return
    files = [a for a in argv if not a.startswith("--")]
    if files:
        run_gui(files)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
