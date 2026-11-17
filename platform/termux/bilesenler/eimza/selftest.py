#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""
selftest.py - Donanim olmadan kopruyu sinar: sahte CCID okuyucu + sahte T=1 kart.
Kullanim:  python3 selftest.py        (Termux'ta da, PC'de de calisir)

Sinananlar: CCID cerceveleme, ATR/ATR ayristirma, T=1 (zincirleme gonderme/alma, WTX, IFS),
kisa-APDU seviyeli okuyucu, TCP protokolu + jeton dogrulama, kart cikarma hatasi.
"""
import os
import socket
import struct
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ccid_bridge as cb

ATR_AKIS = bytes.fromhex("3B9F968131FE45806755454B41451261318073B3A18099")


def lrc(b):
    x = 0
    for c in b:
        x ^= c
    return x


class SimCard:
    """Basit T=1 kart + uygulama (APDU isleyici)."""

    def __init__(self, ifsc=254):
        self.ifsc = ifsc
        self.exp = 0          # karttan beklenen ana bilgisayar N(S)
        self.cns = 0
        self.rx = b""
        self.tx = []          # gonderilecek I-blok parcalari
        self.ifsd = 32
        self.pending_wtx = None
        self.present = True
        self.log = []

    def blk(self, pcb, inf=b""):
        h = bytes([0, pcb, len(inf)]) + inf
        return h + bytes([lrc(h)])

    def app(self, apdu):
        ins = apdu[1]
        if apdu[:2] == b"\x00\xa4":
            return b"\x90\x00"
        if apdu[:2] == b"\x80\x10":
            return bytes((i * 7) & 0xFF for i in range(300)) + b"\x90\x00"
        if apdu[:2] == b"\x80\x20":
            assert apdu[4] == 0
            lc = (apdu[5] << 8) | apdu[6]
            data = apdu[7:7 + lc]
            assert len(data) == lc, (len(data), lc)
            return (sum(data) & 0xFFFFFFFF).to_bytes(4, "big") + b"\x90\x00"
        if apdu[:2] == b"\x80\x30":
            return b"\x90\x00"
        return b"\x6d\x00"

    def _next_i(self):
        part, more = self.tx.pop(0)
        b = self.blk((self.cns << 6) | (0x20 if more else 0), part)
        self.cns ^= 1
        return b

    def _start_tx(self, resp):
        n = self.ifsd
        parts = [resp[i:i + n] for i in range(0, len(resp), n)] or [b""]
        self.tx = [(p, i < len(parts) - 1) for i, p in enumerate(parts)]

    def t1(self, raw):
        assert len(raw) == raw[2] + 4 and lrc(raw[:-1]) == raw[-1], "kotu LRC"
        pcb, inf = raw[1], raw[3:3 + raw[2]]
        if pcb & 0x80 == 0:                                    # I-blok
            self.rx += inf
            self.exp ^= 1
            if pcb & 0x20:
                return self.blk(0x80 | (self.exp << 4))
            apdu, self.rx = self.rx, b""
            resp = self.app(apdu)
            self._start_tx(resp)
            if apdu[:2] == b"\x80\x30":                        # WTX senaryosu
                return self.blk(0xC3, b"\x02")
            return self._next_i()
        if pcb & 0xC0 == 0x80:                                 # R-blok (onay)
            return self._next_i()
        if pcb == 0xC1:                                        # IFS istegi
            self.ifsd = inf[0]
            return self.blk(0xE1, inf)
        if pcb == 0xE3:                                        # WTX cevabi
            return self._next_i()
        raise AssertionError("beklenmeyen blok %02X" % pcb)


class SimUsb:
    """LibusbFd ile ayni arayuz; icinde sahte CCID okuyucu var."""

    def __init__(self, level=cb.LEVEL_TPDU, card=None, max_msg=271, mps=64, time_ext=True):
        self.level = level
        self.card = card
        self.max_msg = max_msg
        self.mps = mps
        self.q = []
        self.time_ext = time_ext
        self.powered = False
        self.apdu_buf = b""
        feats = 0x00000002 | 0x00000004 | 0x00000008 | 0x00000400 * 0 | level
        self.features = feats
        self.claimed = None
        self.dead = False

    # descriptor'lar
    def control_in(self, bm, req, value, index, length, timeout=3000):
        t = value >> 8
        if t == 1:
            d = bytes([18, 1, 0, 2, 0, 0, 0, 64]) + struct.pack("<HHH", 0x072F, 0x9000, 0x0100) + bytes([1, 2, 0, 1])
            return d[:length]
        if t == 2:
            cls = bytearray(54)
            cls[0], cls[1] = 54, 0x21
            struct.pack_into("<H", cls, 2, 0x0110)
            cls[5] = 7
            struct.pack_into("<I", cls, 6, 3)
            struct.pack_into("<I", cls, 28, 254)
            struct.pack_into("<I", cls, 40, self.features)
            struct.pack_into("<I", cls, 44, self.max_msg)
            iface = bytes([9, 4, 0, 0, 3, 0x0B, 0, 0, 0])
            eps = bytes([7, 5, 0x81, 2]) + struct.pack("<H", self.mps) + b"\0" + \
                bytes([7, 5, 0x02, 2]) + struct.pack("<H", self.mps) + b"\0" + \
                bytes([7, 5, 0x83, 3]) + struct.pack("<H", 8) + b"\x10"
            body = iface + bytes(cls) + eps
            total = 9 + len(body)
            cfg = bytes([9, 2]) + struct.pack("<H", total) + bytes([1, 1, 0, 0x80, 50]) + body
            return cfg[:length]
        if t == 3:
            s = "SimReader".encode("utf-16-le")
            return (bytes([2 + len(s), 3]) + s)[:length]
        raise cb.UsbError("control?")

    def claim(self, i):
        self.claimed = i

    def bulk_out(self, ep, data, timeout=5000):
        if self.dead:
            raise cb.UsbError("cihaz yok", -4)
        if not data:
            return 0
        mt, ln, slot, seq, r1, r2, r3 = struct.unpack_from("<BIBBBBB", data)
        body = data[10:10 + ln]
        self.q.extend(self._reply(mt, seq, r1, r2, r3, body))
        return len(data)

    def bulk_in(self, ep, length, timeout=5000):
        if not self.q:
            raise cb.UsbTimeout("bos", -7)
        return self.q.pop(0)

    def close(self):
        pass

    # okuyucu mantigi
    def _m(self, mt, seq, data=b"", status=0, err=0, rfu=0):
        return struct.pack("<BIBBBBB", mt, len(data), 0, seq, status, err, rfu) + data

    def _icc(self):
        if self.card is None or not self.card.present:
            return 2
        return 0 if self.powered else 1

    def _reply(self, mt, seq, r1, r2, r3, body):
        icc = self._icc()
        if mt == 0x65:
            return [self._m(0x81, seq, status=icc)]
        if mt == 0x62:
            if icc == 2:
                return [self._m(0x81, seq, status=2 | 0x40, err=0xFE)]
            self.powered = True
            self.card.exp = self.card.cns = 0
            self.card.rx = b""
            self.card.ifsd = 32
            return [self._m(0x80, seq, ATR_AKIS)]
        if mt == 0x63:
            self.powered = False
            return [self._m(0x81, seq, status=self._icc())]
        if mt == 0x61:
            return [self._m(0x82, seq, body, rfu=r1)]
        if mt == 0x6F:
            if icc == 2:
                return [self._m(0x80, seq, status=2 | 0x40, err=0xFE)]
            out = []
            if self.time_ext:
                out.append(self._m(0x80, seq, status=0x80 | icc, err=1))   # zaman uzatimi
            if self.level == cb.LEVEL_TPDU:
                out.append(self._m(0x80, seq, self.card.t1(body)))
            else:
                lvl = r2 | (r3 << 8)
                if lvl in (0, 1) and r2 in (0,):
                    self.apdu_buf = b""
                self.apdu_buf += body
                if lvl in (0, 2):
                    resp = self.card.app(self.apdu_buf)
                    self.apdu_buf = b""
                    out.append(self._m(0x80, seq, resp))
                else:
                    out.append(self._m(0x80, seq, b"", rfu=0x10))
            return out
        return [self._m(0x80, seq, status=0x40, err=0)]


# ----------------------------------------------------------------------------------------
def check(name, cond):
    print(("  ok   " if cond else "  HATA ") + name)
    if not cond:
        raise SystemExit(1)


def test_atr():
    a = cb.AtrInfo(ATR_AKIS)
    check("ATR: T=1, IFSC=254", a.proto == 1 and a.ifsc == 254 and not a.crc)


def test_t1(level_name, level):
    print("- sahte okuyucu:", level_name)
    card = SimCard()
    usb = SimUsb(level=level, card=card)
    cfg = usb.control_in(0x80, 6, 0x0200, 0, 255)
    info = cb.find_ccid(cfg)
    check("CCID arayuzu + uc noktalar bulundu", info and info["ep_in"] == 0x81 and info["ep_out"] == 0x02)
    rd = cb.CcidReader(usb, info, "Sim")
    check("okuyucu seviyesi", rd.level == level)
    atr, proto = rd.connect()
    check("ATR + protokol", atr == ATR_AKIS and proto == "T=1")
    atr2, _ = rd.connect()
    check("ikinci connect kart resetlemiyor", atr2 == atr and usb.powered)
    check("SELECT -> 9000", rd.transmit(bytes.fromhex("00A4040000")) == b"\x90\x00")
    r = rd.transmit(bytes.fromhex("8010000000"))
    check("302 baytlik cevap (zincirli alma)", len(r) == 302 and r[-2:] == b"\x90\x00" and r[5] == 35)
    data = bytes((i * 3) & 0xFF for i in range(300))
    apdu = bytes([0x80, 0x20, 0, 0, 0]) + struct.pack(">H", 300) + data
    r = rd.transmit(apdu)
    check("307 baytlik komut (zincirli gonderme) toplami dogru", r[:4] == sum(data).to_bytes(4, "big"))
    if level == cb.LEVEL_TPDU:
        r = rd.transmit(bytes.fromhex("8030000000"))
        check("WTX (bekleme uzatimi) sonrasi 9000", r == b"\x90\x00")
        r = rd.transmit(bytes.fromhex("8010000000"))
        check("WTX sonrasi T=1 sirasi bozulmadi", len(r) == 302)
    rd.power_off()
    check("power_off", not usb.powered)
    card.present = False
    try:
        rd.connect()
        check("kart yokken connect hata vermeli", False)
    except cb.NoCard:
        check("kart yokken NoCard", True)
    card.present = True


def test_tcp():
    print("- TCP koprusu")
    card = SimCard()
    usb = SimUsb(card=card)
    info = cb.find_ccid(usb.control_in(0x80, 6, 0x0200, 0, 255))
    rd = cb.CcidReader(usb, info, "Sim Reader 00 00")
    d = tempfile.mkdtemp()
    th = threading.Thread(target=cb.serve, args=(rd, d), daemon=True)
    th.start()
    for _ in range(50):
        if os.path.exists(os.path.join(d, "bridge.json")):
            break
        time.sleep(0.1)
    import json
    st = json.load(open(os.path.join(d, "bridge.json")))
    check("bridge.json izni 600", (os.stat(os.path.join(d, "bridge.json")).st_mode & 0o777) == 0o600)

    def conn(token):
        s = socket.create_connection(("127.0.0.1", st["port"]), 5)
        f = s.makefile("rw", encoding="utf-8", newline="\n")
        f.write("AUTH %s\n" % token)
        f.flush()
        return s, f

    s, f = conn("yanlis")
    check("yanlis jeton reddedildi", f.readline().startswith("ERR AUTH"))
    s.close()
    s, f = conn(st["token"])
    check("dogru jeton", f.readline().strip() == "OK")

    def call(l):
        f.write(l + "\n")
        f.flush()
        return f.readline().strip()

    check("INFO", call("INFO") == "OK Sim Reader 00 00")
    check("STATUS", call("STATUS") == "OK 1")
    r = call("CONNECT")
    check("CONNECT", r == "OK %s T=1" % ATR_AKIS.hex().upper())
    check("TRANSMIT", call("TRANSMIT 00A4040000") == "OK 9000")
    card.present = False
    check("kart cikarilinca STATUS 0", call("STATUS") == "OK 0")
    check("kart cikarilinca TRANSMIT -> ERR REMOVED", call("TRANSMIT 00A4040000").startswith("ERR REMOVED"))
    card.present = True
    check("tekrar CONNECT", call("CONNECT").startswith("OK "))
    f.close()
    s.close()
    time.sleep(3.6)
    check("son istemci gidince kart kapandi (PIN oturumu acik kalmaz)", not usb.powered)
    return d


def test_probe(capfn=None):
    print("- tani (--probe)")
    import io, contextlib
    card = SimCard()
    usb = SimUsb(card=card)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cb.probe(0, usb)
    out = buf.getvalue()
    check("probe: cihaz+CCID+ATR+SELECT satirlari", "CCID:" in out and "ATR:" in out and "ISLEV GORUYOR" in out)


def test_watchdog():
    print("- cihaz cikarilinca kopru kendiliginden kapanir (yeniden baglanma icin)")
    card = SimCard()
    usb = SimUsb(card=card)
    info = cb.find_ccid(usb.control_in(0x80, 6, 0x0200, 0, 255))
    rd = cb.CcidReader(usb, info, "Sim")
    d = tempfile.mkdtemp()
    done = threading.Event()

    def run():
        cb.serve(rd, d)
        done.set()

    threading.Thread(target=run, daemon=True).start()
    for _ in range(50):
        if os.path.exists(os.path.join(d, "bridge.json")):
            break
        time.sleep(0.1)
    check("kopru basladi", os.path.exists(os.path.join(d, "bridge.json")))
    usb.dead = True                                       # okuyucu sokuldu
    check("cihaz kopunca serve() sonlandi", done.wait(8))
    check("bridge.json silindi", not os.path.exists(os.path.join(d, "bridge.json")))


def main():
    print("eimza koprusu oz-sinama")
    test_atr()
    test_t1("TPDU (T=1 ana bilgisayarda)", cb.LEVEL_TPDU)
    test_t1("kisa-APDU (okuyucu T=1'i yapar)", cb.LEVEL_SHORT)
    test_tcp()
    test_probe()
    test_watchdog()
    print("HEPSI GECTI")


if __name__ == "__main__":
    main()
