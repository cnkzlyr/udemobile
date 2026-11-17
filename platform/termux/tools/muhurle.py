# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""YAZAR TARAFI arac: kaynaklara telif basligi + bireysel muhur gomer, surumun manifestini Ed25519 ile imzalar.

  python3 muhurle.py --anahtar-olustur [--sifreli]        (bir kez; ozel anahtar ~/.ckz-muhur/ed25519.pem, izin 600)
  python3 muhurle.py --imzala KLASOR [--anahtar YOL]      (basliklari yaz, dosya muhurlerini ve MUHUR/MANIFEST'i imzala)

OZEL ANAHTAR YALNIZCA YAZARIN CIHAZINDA DURMALIDIR. Dogrulama icin bkz. dogrula.py (herkes kullanabilir)."""
import argparse
import base64
import getpass
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gizli_iz  # noqa: E402

YAZAR = "Av. Can KIZILYAR"
YIL = "2026"
HDR = "CKZ-HDR/1"
MUH = "CKZ-MUHUR/1"
ISARETLENEN = {".sh": "#", ".py": "#", ".java": "//", ".md": "<!--"}
VARSAYILAN_DIZIN = os.path.expanduser("~/.ckz-muhur")


def _cryptography():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        return serialization, Ed25519PrivateKey
    except ImportError:
        sys.exit("python 'cryptography' gerekli (Termux: pkg install python-cryptography)")


def anahtar_olustur(dizin, sifreli):
    ser, Priv = _cryptography()
    os.makedirs(dizin, exist_ok=True)
    os.chmod(dizin, 0o700)
    yol = os.path.join(dizin, "ed25519.pem")
    if os.path.exists(yol):
        sys.exit("Anahtar zaten var: %s (uzerine yazilmadi)" % yol)
    k = Priv.generate()
    enc = ser.NoEncryption()
    if sifreli:
        p1, p2 = getpass.getpass("Anahtar parolasi: "), getpass.getpass("Tekrar: ")
        if p1 != p2 or not p1:
            sys.exit("Parolalar uyusmuyor")
        enc = ser.BestAvailableEncryption(p1.encode())
    pem = k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, enc)
    fd = os.open(yol, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    with open(os.path.join(dizin, "public.hex"), "w") as f:
        f.write(pub.hex() + "\n")
    print("Anahtar olusturuldu: %s" % yol)
    print("Genel anahtar parmak izi: %s" % parmak(pub))
    print("!! Ozel anahtari YEDEKLEYIN (USB/sifreli) ve kimseyle paylasmayin; kaybolursa yeni surumleri ayni kimlikle imzalayamazsiniz.")


def parmak(pub):
    h = hashlib.sha256(pub).hexdigest()[:32].upper()
    return "-".join(h[i:i + 4] for i in range(0, 32, 4))


def anahtar_yukle(yol):
    ser, _ = _cryptography()
    with open(yol, "rb") as f:
        data = f.read()
    parola = None
    if b"ENCRYPTED" in data:
        parola = getpass.getpass("Anahtar parolasi: ").encode()
    return ser.load_pem_private_key(data, parola), ser


def satirlar(b):
    return b.splitlines(keepends=True)


def govde_hash(b):
    govde = b"".join(l for l in satirlar(b) if not MARK_RE.match(l))
    return hashlib.sha256(govde).digest()


def imza_mesaji(h):
    return b"CKZ-FILE/1\n" + h.hex().encode()


def baslik_satirlari(yorum):
    iz = gizli_iz.kodla()
    a = "\u00a9 %s %s%s | T\u00fcm haklar\u0131 sakl\u0131d\u0131r." % (YIL, YAZAR, iz)
    b = "Yaz\u0131l\u0131 izin olmadan \u00e7o\u011falt\u0131lamaz, de\u011fi\u015ftirilemez, da\u011f\u0131t\u0131lamaz; bu bildirim kald\u0131r\u0131lamaz. Bkz. LICENSE.txt"
    if yorum == "<!--":
        return ["<!-- %s | %s -->" % (HDR, a), "<!-- %s | %s -->" % (HDR, b)], lambda s: "<!-- %s %s -->" % (MUH, s)
    return ["%s %s | %s" % (yorum, HDR, a), "%s %s | %s" % (yorum, HDR, b)], lambda s: "%s %s %s" % (yorum, MUH, s)


CODING = re.compile(rb"^#.*coding[:=]")
MARK_RE = re.compile(rb"^\s*(#|//|<!--)\s*CKZ-MUHUR/1\b")
HDR_RE = re.compile(rb"^\s*(#|//|<!--)\s*CKZ-HDR/1\b")


def isaretle(yol, key):
    ext = os.path.splitext(yol)[1].lower()
    yorum = ISARETLENEN[ext]
    with open(yol, "rb") as f:
        ham = f.read()
    ls = [l for l in satirlar(ham) if not HDR_RE.match(l) and not MARK_RE.match(l)]
    idx = 0
    if ls and ls[0].startswith(b"#!"):
        idx = 1
        if ext == ".py" and len(ls) > 1 and CODING.match(ls[1]):
            idx = 2
    elif ext == ".py" and ls and CODING.match(ls[0]):
        idx = 1
    hd, mk = baslik_satirlari(yorum)
    ekle = [(x + "\n").encode("utf-8") for x in hd] + [(mk("MUHURSUZ") + "\n").encode("utf-8")]
    yeni = b"".join(ls[:idx] + ekle + ls[idx:])
    if key is not None:
        sig = key.sign(imza_mesaji(govde_hash(yeni)))
        muhur = (mk(base64.b64encode(sig).decode()) + "\n").encode("utf-8")
        yeni = yeni.replace((mk("MUHURSUZ") + "\n").encode("utf-8"), muhur, 1)
    with open(yol, "wb") as f:
        f.write(yeni)


def manifest_olustur(kok):
    satir = []
    for root, dirs, files in os.walk(kok):
        dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__", "MUHUR"))
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, kok).replace(os.sep, "/")
            if rel.endswith((".pyc", ".class")):
                continue
            with open(p, "rb") as fh:
                d = fh.read()
            satir.append("%s  %d  %s" % (hashlib.sha256(d).hexdigest(), len(d), rel))
    return ("\n".join(sorted(satir, key=lambda s: s.split("  ", 2)[2])) + "\n").encode("utf-8")


def imzala(kok, anahtar_yolu):
    key, ser = anahtar_yukle(anahtar_yolu)
    pub = key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    n = 0
    for root, dirs, files in os.walk(kok):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "MUHUR")]
        for f in files:
            if os.path.splitext(f)[1].lower() in ISARETLENEN:
                isaretle(os.path.join(root, f), key)
                n += 1
    md = os.path.join(kok, "MUHUR")
    os.makedirs(md, exist_ok=True)
    m = manifest_olustur(kok)
    sig = key.sign(b"CKZ-MANIFEST/1\n" + m)
    with open(os.path.join(md, "MANIFEST.txt"), "wb") as f:
        f.write(m)
    with open(os.path.join(md, "MANIFEST.sig"), "w") as f:
        f.write(base64.b64encode(sig).decode() + "\n")
    with open(os.path.join(md, "PUBKEY.hex"), "w") as f:
        f.write(pub.hex() + "\n")
    print("%d dosya muhurlendi; manifest imzalandi. Genel anahtar parmak izi: %s" % (n, parmak(pub)))
    return pub


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--anahtar-olustur", action="store_true")
    ap.add_argument("--sifreli", action="store_true")
    ap.add_argument("--imzala", metavar="KLASOR")
    ap.add_argument("--anahtar", default=os.path.join(VARSAYILAN_DIZIN, "ed25519.pem"))
    ap.add_argument("--dizin", default=VARSAYILAN_DIZIN)
    a = ap.parse_args()
    if a.anahtar_olustur:
        anahtar_olustur(a.dizin, a.sifreli)
    elif a.imzala:
        imzala(a.imzala, a.anahtar)
    else:
        ap.print_help()
