# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""Herkesin kullanabilecegi DOGRULAMA araci: surumun yazar tarafindan imzalanip imzalanmadigini ve degistirilip
degistirilmedigini kontrol eder (ek bagimlilik gerektirmez).

  python3 dogrula.py KLASOR [--pub-parmak XXXX-XXXX-...] [--sessiz] [--kurulu]
  python3 dogrula.py --dosya TEK_DOSYA --pub PUBKEY.hex     (tek dosyanin muhru)
Cikis kodu: 0 = tam dogrulandi, 1 = DEGISTIRILMIS/uyumsuz, 2 = muhursuz (imza yok)."""
import base64
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ckz_ed25519  # noqa: E402

MUH = b"CKZ-MUHUR/1"
MARK_RE = re.compile(rb"^\s*(#|//|<!--)\s*CKZ-MUHUR/1\b")
HDR_RE = re.compile(rb"^\s*(#|//|<!--)\s*CKZ-HDR/1\b")
ISARETLI = (".sh", ".py", ".java", ".md")


def parmak(pub):
    h = hashlib.sha256(pub).hexdigest()[:32].upper()
    return "-".join(h[i:i + 4] for i in range(0, 32, 4))


def govde_hash(b):
    return hashlib.sha256(b"".join(l for l in b.splitlines(keepends=True) if not MARK_RE.match(l))).digest()


def dogrula(kok, pin_parmak=None, sessiz=False):
    say = (lambda *a: None) if sessiz else print
    md = os.path.join(kok, "MUHUR")
    try:
        pub = bytes.fromhex(open(os.path.join(md, "PUBKEY.hex")).read().strip())
        sig = base64.b64decode(open(os.path.join(md, "MANIFEST.sig")).read().strip())
        man = open(os.path.join(md, "MANIFEST.txt"), "rb").read()
    except (OSError, ValueError):
        say("MUHUR: bu kopya M\u00dcH\u00dcRS\u00dcZ (yazar imzas\u0131 yok).")
        return 2
    fp = parmak(pub)
    say("Yazar anahtar\u0131 parmak izi: %s" % fp)
    sorun = []
    if pin_parmak and pin_parmak.replace(" ", "").upper() != fp:
        sorun.append("parmak izi beklenenle ayn\u0131 de\u011fil (beklenen %s)" % pin_parmak)
    if not ckz_ed25519.verify(pub, b"CKZ-MANIFEST/1\n" + man, sig):
        sorun.append("MANIFEST imzas\u0131 GE\u00c7ERS\u0130Z")
    else:
        kayitli = set()
        for satir in man.decode("utf-8").splitlines():
            try:
                h, boyut, rel = satir.split("  ", 2)
            except ValueError:
                sorun.append("bozuk manifest sat\u0131r\u0131")
                continue
            kayitli.add(rel)
            p = os.path.join(kok, rel)
            if not os.path.isfile(p):
                sorun.append("eksik dosya: " + rel)
                continue
            with open(p, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != h:
                    sorun.append("DE\u011e\u0130\u015eT\u0130R\u0130LM\u0130\u015e: " + rel)
        for root, dirs, files in os.walk(kok):
            dirs[:] = [d for d in dirs if d not in ("MUHUR", "__pycache__", ".git")]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), kok).replace(os.sep, "/")
                if rel not in kayitli and not rel.endswith((".pyc", ".class")):
                    sorun.append("manifest d\u0131\u015f\u0131 dosya: " + rel)
    # dosya bazli muhurler (tek dosya baska yere kopyalansa bile dogrulanabilir)
    for root, dirs, files in os.walk(kok):
        dirs[:] = [d for d in dirs if d not in ("MUHUR", "__pycache__", ".git")]
        for f in files:
            if not f.lower().endswith(ISARETLI):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, kok).replace(os.sep, "/")
            with open(p, "rb") as fh:
                ham = fh.read()
            satir = [l for l in ham.splitlines() if MARK_RE.match(l)]
            if not satir or not any(HDR_RE.match(l) for l in ham.splitlines()):
                sorun.append("m\u00fch\u00fcr/telif ba\u015fl\u0131\u011f\u0131 kald\u0131r\u0131lm\u0131\u015f: " + rel)
                continue
            try:
                s = base64.b64decode(satir[0].split(MUH)[1].strip().split()[0].replace(b"-->", b""))
            except Exception:
                sorun.append("bozuk m\u00fch\u00fcr: " + rel)
                continue
            if not ckz_ed25519.verify(pub, b"CKZ-FILE/1\n" + govde_hash(ham).hex().encode(), s):
                sorun.append("dosya m\u00fchr\u00fc GE\u00c7ERS\u0130Z (i\u00e7erik de\u011fi\u015fmi\u015f): " + rel)
    if sorun:
        say("M\u00dcH\u00dcR: DO\u011eRULANAMADI \u2014 bu kopya orijinal/de\u011fi\u015fmemi\u015f DE\u011e\u0130L:")
        for s in sorun[:30]:
            say("  - " + s)
        return 1
    if pin_parmak:
        say("M\u00dcH\u00dcR: DO\u011eRULANDI \u2714  (\u00a9 Av. Can KIZILYAR \u2014 parmak izi resm\u00ee de\u011fere e\u015fit, dosyalar de\u011fi\u015ftirilmemi\u015f)")
    else:
        say("M\u00dcH\u00dcR: imza tutarl\u0131, dosyalar de\u011fi\u015ftirilmemi\u015f. ANCAK yukar\u0131daki parmak izini yazar\u0131n RESM\u00ee sayfas\u0131ndaki de\u011ferle kar\u015f\u0131la\u015ft\u0131rmadan bunu yazar\u0131n s\u00fcr\u00fcm\u00fc saymay\u0131n (sahte paketler kendi anahtar\u0131yla imzalanabilir).")
    return 0


def dosya_kontrol(yol, pub_hex):
    """Tek bir dosyanin (baska yere kopyalanmis olsa bile) yazar muhruyle uyumunu denetler. --pub: genel anahtar (hex)."""
    pub = bytes.fromhex(pub_hex.strip())
    ham = open(yol, "rb").read()
    satir = [l for l in ham.splitlines() if MARK_RE.match(l)]
    if not satir:
        print("%s: M\u00dcH\u00dcR YOK (kald\u0131r\u0131lm\u0131\u015f ya da hi\u00e7 eklenmemi\u015f)." % yol)
        return 2
    try:
        s = base64.b64decode(satir[0].split(MUH)[1].strip().split()[0].replace(b"-->", b""))
    except Exception:
        print("%s: bozuk m\u00fchür." % yol)
        return 1
    if ckz_ed25519.verify(pub, b"CKZ-FILE/1\n" + govde_hash(ham).hex().encode(), s):
        print("%s: M\u00dcH\u00dcR GE\u00c7ERL\u0130 \u2014 dosya yazar\u0131n orijinali, de\u011fi\u015ftirilmemi\u015f (parmak izi %s)." % (yol, parmak(pub)))
        return 0
    print("%s: M\u00dcH\u00dcR GE\u00c7ERS\u0130Z \u2014 dosya sonradan DE\u011e\u0130\u015eT\u0130R\u0130LM\u0130\u015e." % yol)
    return 1


def kurulu_kontrol(kok):
    """Kurulu dosyalari (~/ue.py, ~/eimza/*) manifestteki orijinal ozetlerle karsilastirir."""
    home = os.path.expanduser("~")
    try:
        man = open(os.path.join(kok, "MUHUR", "MANIFEST.txt"), "rb").read().decode("utf-8")
    except OSError:
        print("Kurulu dosya kontrolu: manifest yok.")
        return 2
    ok = bozuk = 0
    for satir in man.splitlines():
        try:
            h, _, rel = satir.split("  ", 2)
        except ValueError:
            continue
        if not rel.startswith("bilesenler/"):
            continue
        hedef = os.path.join(home, rel[len("bilesenler/"):])
        if not os.path.isfile(hedef):
            continue
        with open(hedef, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() == h:
                ok += 1
            else:
                bozuk += 1
                print("  DE\u011e\u0130\u015eM\u0130\u015e kurulu dosya: ~/" + rel[len("bilesenler/"):])
    print("Kurulu dosyalar: %d de\u011fi\u015fmemi\u015f, %d de\u011fi\u015fmi\u015f." % (ok, bozuk))
    return 1 if bozuk else 0


if __name__ == "__main__":
    if "--dosya" in sys.argv and "--pub" in sys.argv:
        f = sys.argv[sys.argv.index("--dosya") + 1]
        pk = sys.argv[sys.argv.index("--pub") + 1]
        sys.exit(dosya_kontrol(f, open(pk).read() if os.path.isfile(pk) else pk))
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pin = None
    if "--pub-parmak" in sys.argv:
        pin = sys.argv[sys.argv.index("--pub-parmak") + 1]
        args = [a for a in args if a != pin]
    if not args:
        print(__doc__)
        sys.exit(64)
    rc = dogrula(args[0], pin, "--sessiz" in sys.argv)
    if "--kurulu" in sys.argv:
        rc = max(rc, kurulu_kontrol(args[0]))
    sys.exit(rc)
