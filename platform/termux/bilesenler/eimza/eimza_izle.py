#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""
eimza_izle.py - USB okuyucu takilinca koprusunu kendiliginden baslatir; cikarilip takilinca yeniden baslatir.

Her yeni takmada Android yeni bir cihaz yolu (/dev/bus/usb/001/0NN) ve yeni izin ister; bu yuzden
kopruyu bir kez baslatmak yetmez. Bu program arka planda `termux-usb -l` ile cihazlari izler:
  - kopru calisiyorsa dokunmaz,
  - calismiyorsa siradaki cihaz icin `termux-usb -r -e bridge_run.sh <cihaz>` dener,
  - CCID olmayan/izin verilmeyen cihazlari 5 dk boyunca tekrar denemez.
Izin penceresinde "Bu USB cihazi icin varsayilan olarak kullan" kutusunu isaretlerseniz pencere bir daha cikmaz.
"""
import json
import os
import signal
import subprocess
import sys
import time

DIR = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("EIMZA_DIR") or os.path.expanduser("~/.eimza")
TERMUX_USB = os.environ.get("EIMZA_TERMUX_USB", "termux-usb")
JSON_PATH = os.path.join(STATE, "bridge.json")
BAD_SECONDS = 300
PERMISSION_WAIT = 30


def log(*a):
    print(time.strftime("%H:%M:%S"), "[eimza-izle]", *a, flush=True)


def bridge_alive():
    try:
        with open(JSON_PATH) as f:
            pid = int(json.load(f).get("pid", 0))
        os.kill(pid, 0)
        return pid
    except Exception:
        return 0


def list_devices():
    try:
        out = subprocess.run([TERMUX_USB, "-l"], capture_output=True, text=True, timeout=15).stdout
        return [d for d in json.loads(out or "[]") if isinstance(d, str)]
    except Exception:
        return []


def main():
    os.makedirs(STATE, exist_ok=True)
    with open(os.path.join(STATE, "izle.pid"), "w") as f:
        f.write(str(os.getpid()))
    run = os.path.join(DIR, "bridge_run.sh")
    bad = {}
    running = True
    child = [None]

    def stop(*_):
        nonlocal running
        running = False

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, stop)
    log("basladi; okuyucu bekleniyor")
    last_state = None
    while running:
        pid = bridge_alive()
        if pid:
            if last_state != "up":
                log("kopru calisiyor (pid %d)" % pid)
                last_state = "up"
            time.sleep(2)
            continue
        if last_state == "up":
            log("kopru kapandi -> okuyucu yeniden aranacak")
        last_state = "down"
        devs = [d for d in list_devices() if time.time() - bad.get(d, 0) > BAD_SECONDS]
        for d in devs:
            if not running:
                break
            log("deneniyor:", d)
            p = subprocess.Popen([TERMUX_USB, "-r", "-e", run, d], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
            child[0] = p
            t0 = time.time()
            while time.time() - t0 < PERMISSION_WAIT and p.poll() is None and not bridge_alive() and running:
                time.sleep(0.3)
            if bridge_alive():
                log("kopru hazir:", d)
                last_state = "up"
                break
            if p.poll() is None:
                p.terminate()
            bad[d] = time.time()
            log("bu cihaz kopru olarak acilamadi (CCID degil ya da izin yok):", d)
        time.sleep(2)
    p = child[0]
    if p and p.poll() is None:
        p.terminate()
    log("durdu")


if __name__ == "__main__":
    main()
