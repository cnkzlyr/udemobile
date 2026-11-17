# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""Gorunmez iz (sifir-genislikli karakterler): metnin icine yazar kimligini gomer / bulup cozer.
Kullanim:  python3 gizli_iz.py --ara KLASOR     (dosyalarda gomulu izleri listeler)
           python3 gizli_iz.py --kodla "metin"  (gomulecek gorunmez diziyi yazdirir)"""
import os
import sys

Z0, Z1, SEP = "\u200b", "\u200c", "\u2060"          # 0, 1, sinirlayici
YUK = "CKZ-2026-CK"


def kodla(metin=YUK):
    bits = "".join(format(b, "08b") for b in metin.encode("utf-8"))
    return SEP + "".join(Z1 if c == "1" else Z0 for c in bits) + SEP


def coz_hepsi(s):
    out, i = [], 0
    while True:
        a = s.find(SEP, i)
        if a < 0:
            break
        b = s.find(SEP, a + 1)
        if b < 0:
            break
        seg = s[a + 1:b]
        if seg and set(seg) <= {Z0, Z1} and len(seg) % 8 == 0:
            by = bytes(int("".join("1" if c == Z1 else "0" for c in seg[k:k + 8]), 2) for k in range(0, len(seg), 8))
            try:
                out.append(by.decode("utf-8"))
            except UnicodeDecodeError:
                pass
        i = b + 1
    return out


def ara(klasor):
    n = 0
    for root, dirs, files in os.walk(klasor):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for f in files:
            p = os.path.join(root, f)
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    izler = coz_hepsi(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            if izler:
                n += 1
                print("%-50s iz: %s (x%d)" % (os.path.relpath(p, klasor), izler[0], len(izler)))
    print("%d dosyada gizli iz bulundu." % n)
    return n


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--ara":
        sys.exit(0 if ara(sys.argv[2]) else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == "--kodla":
        print(kodla(sys.argv[2]))
        sys.exit(0)
    print(__doc__)
