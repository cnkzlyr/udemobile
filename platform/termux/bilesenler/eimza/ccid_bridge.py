#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""
ccid_bridge.py - Rootsuz Android/Termux icin USB CCID akilli kart okuyucu koprusu.

Nasil calisir
-------------
Android, USB cihazini uygulamaya yalnizca "dosya tanimlayicisi (fd)" olarak verir.
`termux-usb -r -e bridge_run.sh <cihaz>` bu fd'yi bu programa arguman olarak gecirir.
Program libusb (libusb_wrap_sys_device) ile cihazi acar, CCID protokolunu konusur ve
127.0.0.1 uzerinde basit, satir tabanli (ve jeton korumali) bir TCP servisi sunar.
Java tarafindaki eimza.TermuxCcidProvider (javax.smartcardio TerminalFactory) bu servise baglanir.

Protokol (satir tabanli, UTF-8):
  AUTH <jeton>          -> OK
  INFO                  -> OK <okuyucu adi>
  STATUS                -> OK 1|0            (kart takili mi)
  CONNECT               -> OK <ATR hex> <T=0|T=1>   (kart zaten acik ise resetlemez)
  TRANSMIT <APDU hex>   -> OK <cevap hex>
  DISCONNECT 0|1        -> OK                (1 = karti kapat/resetle)
  Hata: ERR <KOD> <mesaj>   KOD: REMOVED | NO_CARD | USB | PROTO

Guvenlik: yalnizca 127.0.0.1'e baglanir; ilk satir rastgele jeton olmalidir (jeton ~/.eimza/bridge.json
icinde, dosya izni 600 - diger Android uygulamalari okuyamaz). APDU icerigi (PIN dahil) LOGLANMAZ.
"""
import argparse
import atexit
import ctypes
import json
import os
import secrets
import signal
import socketserver
import struct
import sys
import threading
import time

VERSION = "0.1"
DEBUG = os.environ.get("EIMZA_DEBUG", "") not in ("", "0")


def log(*a):
    print(time.strftime("%H:%M:%S"), "[eimza-kopru]", *a, file=sys.stderr, flush=True)


# ----------------------------------------------------------------------------------------
# Hatalar
# ----------------------------------------------------------------------------------------
class UsbError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


class UsbTimeout(UsbError):
    pass


class CcidError(Exception):
    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


class NoCard(CcidError):
    pass


class T1Error(CcidError):
    pass


# ----------------------------------------------------------------------------------------
# libusb (ctypes) - yalnizca basit imzali fonksiyonlar kullanilir (struct tanimi gerekmez)
# ----------------------------------------------------------------------------------------
class LibusbFd:
    LIBUSB_OPTION_NO_DEVICE_DISCOVERY = 2  # (eski adi WEAK_AUTHORITY, deger ayni)
    ERROR_TIMEOUT = -7
    ERROR_NO_DEVICE = -4

    def __init__(self, fd):
        self.lib = self._load()
        L = self.lib
        c = ctypes
        L.libusb_set_option.argtypes = [c.c_void_p, c.c_int]
        L.libusb_set_option.restype = c.c_int
        L.libusb_init.argtypes = [c.POINTER(c.c_void_p)]
        L.libusb_init.restype = c.c_int
        L.libusb_wrap_sys_device.argtypes = [c.c_void_p, c.c_ssize_t, c.POINTER(c.c_void_p)]
        L.libusb_wrap_sys_device.restype = c.c_int
        L.libusb_claim_interface.argtypes = [c.c_void_p, c.c_int]
        L.libusb_claim_interface.restype = c.c_int
        L.libusb_release_interface.argtypes = [c.c_void_p, c.c_int]
        L.libusb_release_interface.restype = c.c_int
        L.libusb_close.argtypes = [c.c_void_p]
        L.libusb_control_transfer.argtypes = [c.c_void_p, c.c_uint8, c.c_uint8, c.c_uint16, c.c_uint16,
                                              c.c_void_p, c.c_uint16, c.c_uint]
        L.libusb_control_transfer.restype = c.c_int
        L.libusb_bulk_transfer.argtypes = [c.c_void_p, c.c_uint8, c.c_void_p, c.c_int,
                                           c.POINTER(c.c_int), c.c_uint]
        L.libusb_bulk_transfer.restype = c.c_int
        L.libusb_error_name.argtypes = [c.c_int]
        L.libusb_error_name.restype = c.c_char_p
        # cihaz aramasi YAPMA (Android'de izin yok) - fd zaten elimizde
        self._chk(L.libusb_set_option(None, self.LIBUSB_OPTION_NO_DEVICE_DISCOVERY), "libusb_set_option")
        self.ctx = c.c_void_p()
        self._chk(L.libusb_init(c.byref(self.ctx)), "libusb_init")
        self.handle = c.c_void_p()
        self._chk(L.libusb_wrap_sys_device(self.ctx, fd, c.byref(self.handle)), "libusb_wrap_sys_device")
        self.claimed = None

    @staticmethod
    def _load():
        cands = []
        if os.environ.get("LIBUSB_PATH"):
            cands.append(os.environ["LIBUSB_PATH"])
        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        cands += [os.path.join(prefix, "lib", "libusb-1.0.so"), "libusb-1.0.so", "libusb-1.0.so.0",
                  "libusb-1.0.dylib"]
        last = None
        for n in cands:
            try:
                return ctypes.CDLL(n)
            except OSError as e:
                last = e
        raise UsbError("libusb bulunamadi (pkg install libusb): %s" % last)

    def _err(self, code, what):
        try:
            name = self.lib.libusb_error_name(code).decode()
        except Exception:
            name = str(code)
        return "%s: %s (%d)" % (what, name, code)

    def _chk(self, r, what):
        if r < 0:
            raise UsbError(self._err(r, what), r)
        return r

    def control_in(self, bm, req, value, index, length, timeout=3000):
        buf = (ctypes.c_ubyte * length)()
        r = self.lib.libusb_control_transfer(self.handle, bm, req, value, index, buf, length, timeout)
        self._chk(r, "control_transfer")
        return bytes(buf[:r])

    def claim(self, iface):
        self._chk(self.lib.libusb_claim_interface(self.handle, iface), "claim_interface")
        self.claimed = iface

    def bulk_out(self, ep, data, timeout=5000):
        buf = (ctypes.c_ubyte * max(len(data), 1)).from_buffer_copy(data if data else b"\0")
        n = ctypes.c_int(0)
        r = self.lib.libusb_bulk_transfer(self.handle, ep, buf, len(data), ctypes.byref(n), timeout)
        if r == self.ERROR_TIMEOUT:
            raise UsbTimeout("bulk_out zaman asimi", r)
        self._chk(r, "bulk_out")
        return n.value

    def bulk_in(self, ep, length, timeout=5000):
        buf = (ctypes.c_ubyte * length)()
        n = ctypes.c_int(0)
        r = self.lib.libusb_bulk_transfer(self.handle, ep, buf, length, ctypes.byref(n), timeout)
        if r == self.ERROR_TIMEOUT:
            if n.value > 0:            # kismi veri geldi: cagirana ver
                return bytes(buf[:n.value])
            raise UsbTimeout("bulk_in zaman asimi", r)
        self._chk(r, "bulk_in")
        return bytes(buf[:n.value])

    def close(self):
        try:
            if self.claimed is not None:
                self.lib.libusb_release_interface(self.handle, self.claimed)
            self.lib.libusb_close(self.handle)
        except Exception:
            pass


# ----------------------------------------------------------------------------------------
# USB tanimlayicilari / CCID sinif tanimlayicisi
# ----------------------------------------------------------------------------------------
def get_string(usb, idx):
    if not idx:
        return ""
    try:
        d = usb.control_in(0x80, 0x06, (3 << 8) | idx, 0x0409, 255)
        return d[2:d[0]].decode("utf-16-le", "replace").strip()
    except Exception:
        return ""


def find_ccid(cfg):
    """Yapilandirma tanimlayicisinda ilk CCID (sinif 0x0B) arayuzunu bul."""
    i = 0
    found = None
    cur = None
    while i + 2 <= len(cfg):
        ln, typ = cfg[i], cfg[i + 1]
        if ln < 2:
            break
        d = cfg[i:i + ln]
        if typ == 4:  # arayuz
            cur = None
            if d[5] == 0x0B and d[3] == 0 and found is None:
                cur = found = {"iface": d[2], "ep_out": None, "ep_in": None, "mps_out": 64, "mps_in": 64,
                               "ccid": None}
        elif typ == 0x21 and cur is not None and ln >= 54:
            cur["ccid"] = {
                "bcd": struct.unpack_from("<H", d, 2)[0],
                "max_slot": d[4],
                "voltage": d[5],
                "protocols": struct.unpack_from("<I", d, 6)[0],
                "max_ifsd": struct.unpack_from("<I", d, 28)[0],
                "features": struct.unpack_from("<I", d, 40)[0],
                "max_msg": struct.unpack_from("<I", d, 44)[0],
                "pin_support": d[52],
            }
        elif typ == 5 and cur is not None:
            addr, attr = d[2], d[3]
            mps = struct.unpack_from("<H", d, 4)[0] & 0x7FF
            if attr & 3 == 2:  # bulk
                if addr & 0x80:
                    cur["ep_in"], cur["mps_in"] = addr, mps
                else:
                    cur["ep_out"], cur["mps_out"] = addr, mps
        i += ln
    return found


# ----------------------------------------------------------------------------------------
# ATR ayristirma
# ----------------------------------------------------------------------------------------
class AtrInfo:
    def __init__(self, atr):
        self.atr = atr
        self.protos = []
        self.ta = {}
        self.tb = {}
        self.tc = {}
        if len(atr) < 2:
            self.proto = 0
            self.ifsc = 32
            return
        y, i, n = atr[1] >> 4, 2, 1
        while True:
            if y & 1:
                self.ta[n] = atr[i]; i += 1
            if y & 2:
                self.tb[n] = atr[i]; i += 1
            if y & 4:
                self.tc[n] = atr[i]; i += 1
            if y & 8:
                td = atr[i]; i += 1
                p = td & 0x0F
                if p not in self.protos:
                    self.protos.append(p)
                y, n = td >> 4, n + 1
            else:
                break
        self.proto = self.protos[0] if self.protos else 0
        # T=1 arayuz baytlari (i>=3): TA3=IFSC, TB3=BWI/CWI, TC3=EDC tipi
        ifsc = None
        for k in sorted(self.ta):
            if k >= 3:
                ifsc = self.ta[k]; break
        self.ifsc = ifsc if ifsc not in (None, 0, 0xFF) else 32
        self.bwi_cwi = next((self.tb[k] for k in sorted(self.tb) if k >= 3), 0x4D)
        tc3 = next((self.tc[k] for k in sorted(self.tc) if k >= 3), 0)
        self.crc = bool(tc3 & 1)


# ----------------------------------------------------------------------------------------
# CCID okuyucu
# ----------------------------------------------------------------------------------------
LEVEL_TPDU, LEVEL_SHORT, LEVEL_EXT = 0x10000, 0x20000, 0x40000


class CcidReader:
    def __init__(self, usb, info, name="CCID Reader", mode="auto"):
        self.usb = usb
        self.iface = info["iface"]
        self.ep_out, self.ep_in = info["ep_out"], info["ep_in"]
        self.mps_out = info["mps_out"]
        c = info["ccid"] or {}
        if not info["ccid"]:
            log("UYARI: CCID sinif tanimlayicisi okunamadi; varsayilan degerler kullaniliyor")
        self.features = c.get("features", LEVEL_TPDU | 0x02)
        self.max_msg = c.get("max_msg", 271) or 271
        self.max_ifsd = c.get("max_ifsd", 254) or 254
        self.voltage = c.get("voltage", 7) or 7
        self.name = name
        lvl = self.features & 0x70000
        if mode == "tpdu":
            lvl = LEVEL_TPDU
        elif mode == "apdu":
            lvl = lvl if lvl in (LEVEL_SHORT, LEVEL_EXT) else LEVEL_SHORT
        self.level = lvl or LEVEL_TPDU
        self.bufsz = max(self.max_msg, 271) + 16
        self.slot = 0
        self.seq = 0
        self.powered = False
        self.atr = b""
        self.atr_info = None
        self.t1 = None

    # -- temel mesajlasma ---------------------------------------------------------------
    def _send(self, mtype, data, rfu3):
        self.seq = (self.seq + 1) & 0xFF
        msg = struct.pack("<BIBB3s", mtype, len(data), self.slot, self.seq, rfu3) + data
        self.usb.bulk_out(self.ep_out, msg)
        if self.mps_out and len(msg) % self.mps_out == 0:
            self.usb.bulk_out(self.ep_out, b"")          # sifir uzunluklu paket (ZLP)
        return self.seq

    def _recv(self, seq, timeout_ms):
        while True:
            raw = self.usb.bulk_in(self.ep_in, self.bufsz, timeout_ms)
            if len(raw) < 10:
                raise CcidError("CCID: kisa cevap (%d bayt)" % len(raw))
            mt, ln, slot, sq, st, err, rfu = struct.unpack_from("<BIBBBBB", raw)
            data = raw[10:10 + ln]
            while len(data) < ln:                             # birden cok USB paketine bolunmus
                data += self.usb.bulk_in(self.ep_in, self.bufsz, timeout_ms)
            if sq != seq:                                     # eski/artik mesaj
                continue
            cmd = st >> 6
            if cmd == 2:                                      # zaman uzatimi: okuyucu hala calisiyor
                continue
            return mt, st, err, rfu, data

    def _cmd(self, mtype, data=b"", rfu3=b"\0\0\0", timeout_ms=60000, allow_nocard=False):
        seq = self._send(mtype, data, rfu3)
        mt, st, err, rfu, d = self._recv(seq, timeout_ms)
        icc = st & 3
        if icc == 2 and not allow_nocard:
            self.powered = False
            raise NoCard("kart yok/cikarildi")
        if (st >> 6) == 1:
            self.last_err = err
            raise CcidError("CCID komut hatasi (bError=0x%02X)" % err, err)
        return mt, st, err, rfu, d

    # -- kart durumu / guc ---------------------------------------------------------------
    def slot_status(self):
        """0=kart takili+aktif, 1=takili+pasif, 2=kart yok"""
        _, st, _, _, _ = self._cmd(0x65, allow_nocard=True, timeout_ms=5000)
        return st & 3

    def card_present(self):
        return self.slot_status() != 2

    def power_off(self):
        try:
            self._cmd(0x63, allow_nocard=True)
        except Exception as e:
            if DEBUG:
                log("power_off:", e)
        self.powered = False
        self.t1 = None

    def power_on(self):
        if self.features & 0x08:
            volts = [0]                                   # okuyucu voltaji kendi secer
        else:
            volts = [v for v, bit in ((1, 1), (2, 2), (3, 4)) if self.voltage & bit] or [0]
        last = None
        for v in volts:
            try:
                _, _, _, _, atr = self._cmd(0x62, b"", bytes([v, 0, 0]))
                self.atr = atr
                break
            except NoCard:
                raise
            except CcidError as e:
                last = e
        else:
            raise last or CcidError("ATR alinamadi")
        self.atr_info = AtrInfo(self.atr)
        self.powered = True
        self.t1 = None
        if self.level == LEVEL_TPDU:
            if self.atr_info.proto != 1:
                raise CcidError("TPDU seviyeli okuyucuda T=0 kart desteklenmiyor", "PROTO")
            self._maybe_set_params()
            self.t1 = T1(self, self.atr_info)
            self.t1.setup()
        return self.atr

    def _maybe_set_params(self):
        if self.features & (0x02 | 0x40):                 # okuyucu parametreleri kendisi ayarliyor
            return
        a = self.atr_info
        tc1 = a.tc.get(1, 0)
        params = bytes([0x11, 0x10 | (1 if a.crc else 0), 0 if tc1 == 0xFF else tc1,
                        a.bwi_cwi, 0x00, min(a.ifsc, 254), 0x00])
        try:
            self._cmd(0x61, params, bytes([1, 0, 0]))
        except Exception as e:
            log("SetParameters reddedildi (devam):", e)

    def connect(self):
        st = self.slot_status()
        if st == 2:
            raise NoCard("kart takili degil")
        if self.powered and st == 0:
            return self.atr, "T=%d" % (self.atr_info.proto if self.atr_info else 1)
        self.power_on()
        return self.atr, "T=%d" % self.atr_info.proto

    # -- APDU degisimi ----------------------------------------------------------------
    def xfr_block(self, data, bwi=0):
        _, _, _, _, d = self._cmd(0x6F, data, bytes([bwi, 0, 0]))
        return d

    def _xfr_apdu(self, apdu):
        maxd = self.max_msg - 10
        parts = [apdu[i:i + maxd] for i in range(0, len(apdu), maxd)] if len(apdu) > maxd else [apdu]
        data, chain = b"", 0
        for idx, part in enumerate(parts):
            if len(parts) == 1:
                lvl = 0
            elif idx == 0:
                lvl = 1
            elif idx == len(parts) - 1:
                lvl = 2
            else:
                lvl = 3
            _, _, _, rfu, d = self._cmd(0x6F, part, bytes([0]) + struct.pack("<H", lvl))
            if idx == len(parts) - 1:
                data, chain = data + d, rfu
        while chain in (1, 3, 0x10):
            _, _, _, rfu, d = self._cmd(0x6F, b"", bytes([0]) + struct.pack("<H", 0x10))
            data, chain = data + d, rfu
        return data

    def transmit(self, apdu):
        if not self.powered:
            raise NoCard("kart aktif degil")
        if self.level == LEVEL_TPDU:
            return self.t1.transmit(apdu)
        return self._xfr_apdu(apdu)


# ----------------------------------------------------------------------------------------
# T=1 (TPDU seviyeli okuyucular icin ana bilgisayar tarafi)
# ----------------------------------------------------------------------------------------
class T1:
    def __init__(self, reader, atr_info):
        self.r = reader
        self.ifsc = max(16, min(atr_info.ifsc, 254, reader.max_msg - 14))
        self.ns = 0          # bizim gonderdigimiz sonraki I-blok sirasi
        self.cns = 0         # karttan bekledigimiz I-blok sirasi
        self.crc = atr_info.crc
        if self.crc:
            raise CcidError("T=1 CRC (EDC) desteklenmiyor", "PROTO")

    @staticmethod
    def _lrc(b):
        x = 0
        for c in b:
            x ^= c
        return x

    def _block(self, pcb, inf=b""):
        h = bytes([0, pcb, len(inf)]) + inf
        return h + bytes([self._lrc(h)])

    @staticmethod
    def _parse(raw):
        if len(raw) < 4 or len(raw) != raw[2] + 4 or T1._lrc(raw[:-1]) != raw[-1]:
            raise T1Error("bozuk T=1 blogu")
        return raw[1], raw[3:3 + raw[2]]

    def setup(self):
        self.ns = self.cns = 0
        if self.r.features & 0x400:                       # IFSD'yi okuyucu yapiyor
            return
        want = min(254, self.r.max_ifsd)
        if want > 32:
            try:
                raw = self.r.xfr_block(self._block(0xC1, bytes([want])))
                pcb, inf = self._parse(raw)
                if pcb == 0xE1:
                    pass
            except Exception as e:
                log("IFSD pazarligi atlandi:", e)

    def _send_recv(self, blk, bwi=0):
        """Blok yolla; WTX/IFS S-bloklarini yut; ilk I veya R blogunu dondur."""
        errs = 0
        while True:
            try:
                raw = self.r.xfr_block(blk, bwi)
                pcb, inf = self._parse(raw)
            except NoCard:
                raise
            except (CcidError, UsbTimeout, T1Error):
                errs += 1
                if errs > 2:
                    raise T1Error("T=1: cevap alinamadi")
                blk = self._block(0x81 | (self.cns << 4))    # R-blok (EDC hatasi) iste
                bwi = 0
                continue
            if pcb & 0x80 == 0:
                return "I", pcb, inf
            if pcb & 0xC0 == 0x80:
                return "R", pcb, inf
            # S-blok
            if pcb == 0xC3:                                   # WTX istegi
                blk = self._block(0xE3, inf)
                bwi = inf[0] if inf else 1
                continue
            if pcb == 0xC1:                                   # kart IFS istiyor
                blk = self._block(0xE1, inf)
                continue
            if pcb == 0xC2:                                   # abort istegi
                blk = self._block(0xE2, inf)
                continue
            raise T1Error("beklenmeyen S-blok 0x%02X" % pcb)

    def transmit(self, apdu):
        chunks = [apdu[i:i + self.ifsc] for i in range(0, len(apdu), self.ifsc)] or [b""]
        kind = pcb = inf = None
        for idx, ch in enumerate(chunks):
            last = idx == len(chunks) - 1
            blk = self._block((self.ns << 6) | (0 if last else 0x20), ch)
            for attempt in range(3):
                kind, pcb, inf = self._send_recv(blk)
                if last:
                    if kind == "I":
                        break
                else:
                    if kind == "R" and (pcb & 0x0F) == 0 and ((pcb >> 4) & 1) == (self.ns ^ 1):
                        break
                if attempt == 2:
                    raise T1Error("T=1: blok kabul edilmedi")
            self.ns ^= 1
        out = b""
        while True:
            self.cns ^= 1
            out += inf
            if not (pcb & 0x20):
                return out
            kind, pcb, inf = self._send_recv(self._block(0x80 | (self.cns << 4)))
            if kind != "I":
                raise T1Error("T=1: I blok bekleniyordu")


# ----------------------------------------------------------------------------------------
# TCP koprusu
# ----------------------------------------------------------------------------------------
class Bridge(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, reader, token, port=0):
        super().__init__(("127.0.0.1", port), Handler)
        self.reader = reader
        self.token = token
        self.lock = threading.RLock()
        self.clients = 0
        self.idle_timer = None
        self.fatal = False

    def client_open(self):
        with self.lock:
            self.clients += 1
            if self.idle_timer:
                self.idle_timer.cancel()
                self.idle_timer = None

    def client_close(self):
        with self.lock:
            self.clients -= 1
            if self.clients <= 0:
                # son istemci gitti: PIN oturumunu kartta acik birakma
                self.idle_timer = threading.Timer(3.0, self._idle_off)
                self.idle_timer.daemon = True
                self.idle_timer.start()

    def _idle_off(self):
        with self.lock:
            if self.clients <= 0 and self.reader.powered:
                log("istemci yok -> kart kapatiliyor")
                self.reader.power_off()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        br = self.server
        self.request.settimeout(None)
        try:
            first = self.rfile.readline(200).decode("utf-8", "replace").strip()
        except Exception:
            return
        if not first.startswith("AUTH ") or not secrets.compare_digest(first[5:].strip(), br.token):
            self._w("ERR AUTH yetkisiz")
            return
        self._w("OK")
        br.client_open()
        try:
            while True:
                line = self.rfile.readline(1 << 18)
                if not line:
                    break
                line = line.decode("utf-8", "replace").strip()
                if not line:
                    continue
                if line == "QUIT":
                    break
                try:
                    with br.lock:
                        resp = self.dispatch(br.reader, line)
                except NoCard as e:
                    resp = "ERR REMOVED %s" % e
                except UsbError as e:
                    resp = "ERR USB %s" % e
                    if e.code == LibusbFd.ERROR_NO_DEVICE:
                        br.fatal = True
                except CcidError as e:
                    resp = "ERR %s %s" % (e.code if e.code == "PROTO" else "USB", e)
                except Exception as e:  # pragma: no cover
                    resp = "ERR USB %r" % (e,)
                self._w(resp)
                if br.fatal:
                    threading.Thread(target=br.shutdown, daemon=True).start()
                    break
        finally:
            br.client_close()

    def _w(self, s):
        try:
            self.wfile.write((s + "\n").encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    @staticmethod
    def dispatch(rd, line):
        op, _, arg = line.partition(" ")
        if op == "INFO":
            return "OK " + rd.name
        if op == "STATUS":
            return "OK " + ("1" if rd.card_present() else "0")
        if op == "CONNECT":
            atr, proto = rd.connect()
            log("kart baglandi: ATR=%s %s (seviye=%s)" % (atr.hex().upper(), proto, hex(rd.level)))
            return "OK %s %s" % (atr.hex().upper(), proto)
        if op == "TRANSMIT":
            apdu = bytes.fromhex(arg.strip())
            if DEBUG:
                log("APDU ->", len(apdu), "bayt")            # icerik (PIN) yazilmaz
            resp = rd.transmit(apdu)
            if DEBUG and len(resp) >= 2:
                log("APDU <-", len(resp), "bayt SW=%02X%02X" % (resp[-2], resp[-1]))
            return "OK " + resp.hex().upper()
        if op == "DISCONNECT":
            if arg.strip() == "1":
                rd.power_off()
            return "OK"
        return "ERR PROTO bilinmeyen komut"


# ----------------------------------------------------------------------------------------
# calistirma
# ----------------------------------------------------------------------------------------
def open_reader_from_fd(fd, mode):
    usb = LibusbFd(fd)
    try:
        dev = usb.control_in(0x80, 0x06, 0x0100, 0, 18)
        vid, pid = struct.unpack_from("<HH", dev, 8)
        prod = get_string(usb, dev[15])
        head = usb.control_in(0x80, 0x06, 0x0200, 0, 9)
        total = struct.unpack_from("<H", head, 2)[0]
        cfg = usb.control_in(0x80, 0x06, 0x0200, 0, total)
    except UsbError as e:
        raise SystemExit("USB tanimlayicilari okunamadi: %s" % e)
    info = find_ccid(cfg)
    if not info or info["ep_in"] is None or info["ep_out"] is None:
        raise SystemExit("Bu cihaz CCID (akilli kart okuyucu) degil: %04x:%04x %s" % (vid, pid, prod))
    usb.claim(info["iface"])
    name = ("%s %04X:%04X" % (prod or "USB CCID Reader", vid, pid))
    rd = CcidReader(usb, info, name, mode)
    log("okuyucu: %s  ozellik=0x%08X  seviye=%s  max_mesaj=%d" % (
        name, rd.features, {LEVEL_TPDU: "TPDU", LEVEL_SHORT: "kisa-APDU", LEVEL_EXT: "uzun-APDU"}[rd.level],
        rd.max_msg))
    return rd


def probe(fd, usb=None):
    """Tani: cihazin USB/CCID ozelliklerini ve (kart takiliysa) ATR'sini yazdirir. PIN'e dokunmaz."""
    usb = usb or LibusbFd(fd)
    P = lambda *a: print(*a, flush=True)
    dev = usb.control_in(0x80, 0x06, 0x0100, 0, 18)
    vid, pid = struct.unpack_from("<HH", dev, 8)
    P("== cihaz %04X:%04X  sinif=%02X  uretici=%r urun=%r seri=%r" % (
        vid, pid, dev[4], get_string(usb, dev[14]), get_string(usb, dev[15]), get_string(usb, dev[16])))
    head = usb.control_in(0x80, 0x06, 0x0200, 0, 9)
    cfg = usb.control_in(0x80, 0x06, 0x0200, 0, struct.unpack_from("<H", head, 2)[0])
    i = 0
    while i + 2 <= len(cfg):
        ln, typ = cfg[i], cfg[i + 1]
        if ln < 2:
            break
        d = cfg[i:i + ln]
        if typ == 4:
            P("  arayuz %d alt=%d sinif=%02X alt-sinif=%02X protokol=%02X uc-nokta=%d" % (d[2], d[3], d[5], d[6], d[7], d[4]))
        elif typ == 5:
            P("    uc nokta 0x%02X tip=%d maxpaket=%d" % (d[2], d[3] & 3, struct.unpack_from("<H", d, 4)[0]))
        elif typ == 0x21:
            P("    sinif tanimlayicisi (0x21) uzunluk=%d: %s" % (ln, d.hex()))
        i += ln
    info = find_ccid(cfg)
    if not info or info["ep_in"] is None or info["ep_out"] is None:
        P("SONUC: CCID arayuzu YOK (bu cihaz standart akilli kart okuyucu degil)")
        return
    c = info["ccid"] or {}
    f = c.get("features", 0)
    P("CCID: bcd=0x%04X ozellik=0x%08X seviye=%s max_mesaj=%s max_ifsd=%s protokoller=0x%X voltaj=0x%X pin=%s" % (
        c.get("bcd", 0), f, {0x10000: "TPDU", 0x20000: "kisa-APDU", 0x40000: "uzun-APDU"}.get(f & 0x70000, "?"),
        c.get("max_msg"), c.get("max_ifsd"), c.get("protocols", 0), c.get("voltage", 0), c.get("pin_support")))
    usb.claim(info["iface"])
    rd = CcidReader(usb, info, "probe", os.environ.get("EIMZA_MODE", "auto"))
    st = rd.slot_status()
    P("yuva durumu:", {0: "kart takili+aktif", 1: "kart takili", 2: "KART YOK"}[st])
    if st == 2:
        return
    try:
        atr, proto = rd.connect()
        a = rd.atr_info
        P("ATR:", atr.hex().upper(), " protokoller:", ["T=%d" % x for x in a.protos], "IFSC:", a.ifsc, "CRC:", a.crc)
        r = rd.transmit(bytes.fromhex("00A4000000"))      # MF sec (zararsiz)
        P("SELECT MF ->", r.hex().upper())
        P("SONUC: okuyucu+kart ISLEV GORUYOR")
    except Exception as e:
        P("SONUC: HATA:", repr(e))
    finally:
        rd.power_off()


def serve(reader, state_dir, port=0):
    os.makedirs(state_dir, exist_ok=True)
    try:
        os.chmod(state_dir, 0o700)
    except OSError:
        pass
    token = secrets.token_hex(16)
    br = Bridge(reader, token, port)
    path = os.path.join(state_dir, "bridge.json")
    tmp = path + ".tmp"
    fdw = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fdw, "w") as f:
        json.dump({"port": br.server_address[1], "token": token, "name": reader.name,
                   "pid": os.getpid()}, f)
    os.replace(tmp, path)

    def cleanup():
        try:
            os.remove(path)
        except OSError:
            pass
        try:
            reader.power_off()
        except Exception:
            pass

    stop_evt = threading.Event()

    def watchdog():
        """Cihaz cikarildiysa (USB hatasi) koprudan cik; eimza_izle.py yenisini baslatir."""
        fails = 0
        while not stop_evt.wait(2.0):
            if not br.lock.acquire(blocking=False):      # bir islem suruyor
                fails = 0
                continue
            try:
                reader.slot_status()
                fails = 0
            except UsbError as e:
                fails += 1
                log("USB kontrol hatasi (%d): %s" % (fails, e))
                if e.code == LibusbFd.ERROR_NO_DEVICE or fails >= 3:
                    log("USB cihaz koptu -> kopru kapaniyor")
                    threading.Thread(target=br.shutdown, daemon=True).start()
                    return
            except Exception:
                pass
            finally:
                br.lock.release()

    threading.Thread(target=watchdog, daemon=True).start()
    atexit.register(stop_evt.set)
    atexit.register(cleanup)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, lambda *_: threading.Thread(target=br.shutdown, daemon=True).start())
        except Exception:
            pass
    log("hazir: 127.0.0.1:%d (durum dizini %s)" % (br.server_address[1], state_dir))
    try:
        br.serve_forever(poll_interval=0.3)
    finally:
        cleanup()
        br.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fd", type=int, help="termux-usb'nin verdigi USB dosya tanimlayicisi")
    ap.add_argument("--state-dir", default=os.environ.get("EIMZA_DIR") or os.path.expanduser("~/.eimza"))
    ap.add_argument("--mode", choices=["auto", "tpdu", "apdu"], default=os.environ.get("EIMZA_MODE", "auto"),
                    help="degisim seviyesi (varsayilan: okuyucunun bildirdigi)")
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--probe", action="store_true", help="tani: cihaz/kart bilgisini yazdir ve cik")
    ap.add_argument("--sim", action="store_true",
                    help="donanimsiz deneme: sahte okuyucu+kart (editorun kopruye baglandigini gormek icin)")
    a = ap.parse_args()
    if a.sim:
        import selftest
        card = selftest.SimCard()
        usb = selftest.SimUsb(card=card)
        info = find_ccid(usb.control_in(0x80, 6, 0x0200, 0, 255))
        serve(CcidReader(usb, info, "Sim Reader (donanimsiz deneme) 00 00"), a.state_dir, a.port)
        return
    if a.fd is None:
        ap.error("--fd gerekli (bu program `termux-usb -r -e eimza/bridge_run.sh <cihaz>` ile baslatilir)")
    if a.probe:
        probe(a.fd)
        return
    rd = open_reader_from_fd(a.fd, a.mode)
    serve(rd, a.state_dir, a.port)


if __name__ == "__main__":
    main()
