#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selenium WebDriver arayüzünü Chrome DevTools Protokolü (CDP) üzerinden taklit eden küçük sürücü.

Neden: Telefonda (Termux'suz CanEditor APK) Chrome/chromedriver yoktur; UETS indirme (uets_downloader.py)
Selenium bekler ve bu yüzden telefonda tamamen kapalıydı. CanEditor'un gizli WebView'ı DevTools soketini
açar ve asistan sunucusu bunu 127.0.0.1:9223'e köprüler (UYAP modülleri de bunu kullanır). Bu sınıf aynı
sayfayı Selenium'un uets_downloader'da kullanılan alt kümesiyle sürer:
  get, current_url, title, page_source, find_element(s), execute_script, execute_async_script,
  set_script_timeout, window_handles, switch_to.window, close, back, quit, get_cookies, get_log,
  save_screenshot, execute_cdp_cmd; öğe: click, clear, send_keys, text, get_attribute, is_displayed,
  is_enabled, find_element(s), tag_name.

Minimal Selenium-compatible driver backed by raw CDP (websocket-client), for Android WebView automation.
"""
from __future__ import annotations

import base64
import itertools
import json
import os
import threading
import time
import urllib.request

import websocket

CDP_PORT = int(os.environ.get("CANASISTAN_CDP_PORT", "9223"))

try:  # Selenium kuruluysa onun istisnalarını kullan (EC/WebDriverWait bunları yakalar)
    from selenium.common.exceptions import (JavascriptException, NoSuchElementException,
                                            StaleElementReferenceException, TimeoutException, WebDriverException)
except Exception:  # noqa: BLE001
    class WebDriverException(Exception):
        pass

    class NoSuchElementException(WebDriverException):
        pass

    class StaleElementReferenceException(WebDriverException):
        pass

    class TimeoutException(WebDriverException):
        pass

    class JavascriptException(WebDriverException):
        pass


# Selenium By sabitleri → JS bulucu
_BULUCU_JS = r"""
function(by, deger, kok) {
  kok = kok || document;
  if (by === 'css selector') return Array.from(kok.querySelectorAll(deger));
  if (by === 'tag name') return Array.from(kok.getElementsByTagName(deger));
  if (by === 'id') { const e = (kok.getElementById ? kok : document).getElementById(deger); return e ? [e] : []; }
  if (by === 'name') return Array.from(kok.querySelectorAll('[name="' + CSS.escape(deger) + '"]'));
  if (by === 'class name') return Array.from(kok.getElementsByClassName(deger));
  if (by === 'link text') return Array.from(kok.querySelectorAll('a')).filter(a => a.textContent.trim() === deger);
  if (by === 'partial link text') return Array.from(kok.querySelectorAll('a')).filter(a => a.textContent.includes(deger));
  if (by === 'xpath') {
    const r = document.evaluate(deger, kok, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null), out = [];
    for (let i = 0; i < r.snapshotLength; i++) out.push(r.snapshotItem(i));
    return out;
  }
  throw new Error('Desteklenmeyen bulucu: ' + by);
}
"""


class CdpOgesi:
    """Selenium WebElement benzeri: CDP RemoteObject kimliğini taşır."""

    def __init__(self, surucu: "CdpSurucu", object_id: str):
        self._s, self.id = surucu, object_id

    def _cagir(self, fonksiyon: str, *args):
        return self._s._fonksiyon_cagir(fonksiyon, [self, *args])

    # Selenium uyumlu yüzey
    @property
    def text(self) -> str:
        return self._cagir("function(e){return (e.innerText || e.textContent || '').trim();}") or ""

    @property
    def tag_name(self) -> str:
        return (self._cagir("function(e){return e.tagName;}") or "").lower()

    def get_attribute(self, ad: str):
        return self._cagir("function(e,a){ if (a in e && typeof e[a] !== 'function' && typeof e[a] !== 'object') return String(e[a]);"
                           " const v = e.getAttribute(a); return v === null ? null : v; }", ad)

    def get_property(self, ad: str):
        return self._cagir("function(e,a){return e[a];}", ad)

    def is_displayed(self) -> bool:
        return bool(self._cagir("function(e){const r=e.getBoundingClientRect(), s=getComputedStyle(e);"
                                " return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none';}"))

    def is_enabled(self) -> bool:
        return not bool(self._cagir("function(e){return !!e.disabled;}"))

    def click(self):
        self._cagir("function(e){e.scrollIntoView({block:'center'}); e.click();}")

    def clear(self):
        self._cagir(_DEGER_YAZ_JS, "")

    def send_keys(self, *metinler):
        ek = "".join(str(m) for m in metinler)
        # Selenium send_keys mevcut değerin sonuna yazar; Angular/Material alanları input olayını bekler
        self._cagir("function(e,v){" + _DEGER_YAZ_GOVDE.replace("__DEGER__", "(e.value || '') + v") + "}", ek)

    def submit(self):
        self._cagir("function(e){ (e.form || e.closest('form')).requestSubmit(); }")

    def find_elements(self, by="css selector", value=None):
        return self._s._bul(by, value, kok=self)

    def find_element(self, by="css selector", value=None):
        l = self.find_elements(by, value)
        if not l:
            raise NoSuchElementException(f"{by}={value}")
        return l[0]

    def __eq__(self, o):
        return isinstance(o, CdpOgesi) and o.id == self.id

    def __hash__(self):
        return hash(self.id)


_DEGER_YAZ_GOVDE = """
  e.focus();
  const proto = e instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const set = Object.getOwnPropertyDescriptor(proto, 'value');
  if (set && set.set) set.set.call(e, __DEGER__); else e.value = __DEGER__;
  e.dispatchEvent(new Event('input', {bubbles: true}));
  e.dispatchEvent(new Event('change', {bubbles: true}));
  e.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
"""
_DEGER_YAZ_JS = "function(e,v){" + _DEGER_YAZ_GOVDE.replace("__DEGER__", "v") + "}"


class _SwitchTo:
    def __init__(self, s):
        self._s = s

    def window(self, _handle):
        return None

    def default_content(self):
        return None

    @property
    def alert(self):
        raise NoSuchElementException("alert yok")


class CdpSurucu:
    """CanEditor gizli WebView'ını (127.0.0.1:9223) Selenium gibi süren sürücü."""

    def __init__(self, port: int = CDP_PORT, bekle_sn: float = 30.0):
        self.port = port
        self._sayac = itertools.count(1)
        self._kilit = threading.Lock()
        self._script_sn = 30.0
        self.switch_to = _SwitchTo(self)
        son_hata = None
        bitis = time.time() + bekle_sn
        while time.time() < bitis:
            try:
                sekmeler = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3).read())
                sayfalar = [t for t in sekmeler if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
                # UETS için ayrılmış gizli sayfa (about:blank#uets ya da uets.ptt.gov.tr) önce; UYAP oturumunu taşıyan
                # sayfa yalnızca başka gizli sayfa yoksa kullanılır (UETS girişi UYAP oturumunu düşürmesin).
                sayfalar.sort(key=lambda t: (0 if "uets" in (t.get("url") or "").lower() else
                                             2 if any(h in (t.get("url") or "") for h in ("uyap.gov.tr", "turkiye.gov.tr")) else 1))
                sayfa = sayfalar[0] if sayfalar else None
                if sayfa:
                    self._ws = websocket.create_connection(sayfa["webSocketDebuggerUrl"], timeout=60, suppress_origin=True)
                    break
            except Exception as e:  # noqa: BLE001
                son_hata = e
            time.sleep(1.0)
        else:
            raise WebDriverException(f"Gizli tarayıcıya (CDP {port}) bağlanılamadı: {son_hata}. CanEditor uygulamasını açın.")
        self._komut("Runtime.enable")
        self._komut("Page.enable")

    # ------------------------------------------------------------------ CDP çekirdeği
    def _komut(self, yontem: str, params: dict | None = None, zaman_asimi: float = 60.0) -> dict:
        with self._kilit:
            kimlik = next(self._sayac)
            self._ws.settimeout(zaman_asimi)
            self._ws.send(json.dumps({"id": kimlik, "method": yontem, "params": params or {}}))
            bitis = time.time() + zaman_asimi
            while time.time() < bitis:
                m = json.loads(self._ws.recv())
                if m.get("id") == kimlik:
                    if "error" in m:
                        raise WebDriverException(f"CDP {yontem}: {m['error'].get('message')}")
                    return m.get("result", {})
            raise TimeoutException(f"CDP {yontem} zaman aşımı")

    def execute_cdp_cmd(self, yontem: str, params: dict | None = None) -> dict:
        try:
            return self._komut(yontem, params)
        except WebDriverException:
            return {}

    def _deger(self, ro: dict):
        if ro.get("subtype") == "node" and ro.get("objectId"):
            return CdpOgesi(self, ro["objectId"])
        if ro.get("type") == "object" and ro.get("subtype") == "array" and ro.get("objectId"):
            return self._dizi(ro["objectId"])
        if "value" in ro:
            return ro["value"]
        if ro.get("type") == "undefined" or ro.get("subtype") == "null":
            return None
        if ro.get("objectId"):  # düz nesne → JSON ile al
            r = self._komut("Runtime.callFunctionOn", {"objectId": ro["objectId"], "functionDeclaration": "function(){return this;}",
                                                       "returnByValue": True})
            return r.get("result", {}).get("value")
        return None

    def _dizi(self, object_id: str) -> list:
        ozellikler = self._komut("Runtime.getProperties", {"objectId": object_id, "ownProperties": True}).get("result", [])
        ogeler = sorted(((int(p["name"]), p["value"]) for p in ozellikler if p.get("name", "").isdigit() and "value" in p),
                        key=lambda x: x[0])
        return [self._deger(v) for _, v in ogeler]

    def _arguman(self, a):
        if isinstance(a, CdpOgesi):
            return {"objectId": a.id}
        return {"value": a}

    def _fonksiyon_cagir(self, fonksiyon: str, args: list, bekle: bool = False, zaman_asimi: float | None = None):
        r = self._komut("Runtime.callFunctionOn", {
            "functionDeclaration": fonksiyon,
            "objectId": self._global_id(),
            "arguments": [self._arguman(a) for a in args],
            "awaitPromise": bekle, "returnByValue": False, "userGesture": True,
        }, zaman_asimi=zaman_asimi or self._script_sn + 5)
        if r.get("exceptionDetails"):
            ed = r["exceptionDetails"]
            msg = (ed.get("exception") or {}).get("description") or ed.get("text")
            if "Cannot find context" in str(msg) or "Could not find object" in str(msg):
                raise StaleElementReferenceException(str(msg))
            raise JavascriptException(str(msg)[:500])
        return self._deger(r.get("result", {}))

    def _global_id(self) -> str:
        # Gezinti sonrası bağlam değişir: global nesneyi her çağrıda tazele (ucuz)
        r = self._komut("Runtime.evaluate", {"expression": "window", "returnByValue": False})
        return r["result"]["objectId"]

    def _bul(self, by, value, kok: CdpOgesi | None = None) -> list:
        args = [by, value] + ([kok] if kok else [])
        sonuc = self._fonksiyon_cagir(_BULUCU_JS, args)
        return [x for x in (sonuc or []) if isinstance(x, CdpOgesi)]

    # ------------------------------------------------------------------ Selenium yüzeyi
    def get(self, url: str) -> None:
        self._komut("Page.navigate", {"url": url})
        bitis = time.time() + 45
        while time.time() < bitis:
            time.sleep(0.5)
            try:
                if self.execute_script("return document.readyState") == "complete":
                    return
            except WebDriverException:
                continue

    @property
    def current_url(self) -> str:
        return self.execute_script("return location.href") or ""

    @property
    def title(self) -> str:
        return self.execute_script("return document.title") or ""

    @property
    def page_source(self) -> str:
        return self.execute_script("return document.documentElement.outerHTML") or ""

    @property
    def window_handles(self) -> list[str]:
        return ["webview"]

    @property
    def current_window_handle(self) -> str:
        return "webview"

    def find_elements(self, by="css selector", value=None) -> list:
        return self._bul(by, value)

    def find_element(self, by="css selector", value=None):
        l = self._bul(by, value)
        if not l:
            raise NoSuchElementException(f"{by}={value}")
        return l[0]

    def execute_script(self, betik: str, *args):
        return self._fonksiyon_cagir("function(){" + betik + "\n}", list(args))

    def set_script_timeout(self, sn: float) -> None:
        self._script_sn = float(sn)

    def implicitly_wait(self, _sn) -> None:
        return None

    def set_page_load_timeout(self, _sn) -> None:
        return None

    def execute_async_script(self, betik: str, *args):
        # Selenium sözleşmesi: son argüman callback. Promise'e sarılır ve CDP awaitPromise ile beklenir.
        sarici = ("function(){ const args = Array.from(arguments); return new Promise((coz, red) => {"
                  " const t = setTimeout(() => red(new Error('script timeout')), " + str(int(self._script_sn * 1000)) + ");"
                  " args.push(v => { clearTimeout(t); coz(v); });"
                  " (function(){" + betik + "\n}).apply(null, args); }); }")
        r = self._komut("Runtime.callFunctionOn", {
            "functionDeclaration": sarici, "objectId": self._global_id(),
            "arguments": [self._arguman(a) for a in args], "awaitPromise": True, "returnByValue": True,
        }, zaman_asimi=self._script_sn + 10)
        if r.get("exceptionDetails"):
            raise JavascriptException(str(r["exceptionDetails"].get("text"))[:300])
        return r.get("result", {}).get("value")

    def back(self) -> None:
        self.execute_script("history.back()")
        time.sleep(1.5)

    def refresh(self) -> None:
        self._komut("Page.reload")
        time.sleep(2)

    def get_cookies(self) -> list[dict]:
        try:
            return self._komut("Network.getCookies").get("cookies", [])
        except WebDriverException:
            return []

    def get_log(self, _tur: str) -> list:
        return []

    def save_screenshot(self, yol: str) -> bool:
        try:
            veri = self._komut("Page.captureScreenshot", {"format": "png"}).get("data")
            with open(yol, "wb") as f:
                f.write(base64.b64decode(veri))
            return True
        except Exception:  # noqa: BLE001
            return False

    get_screenshot_as_file = save_screenshot

    def close(self) -> None:
        return None

    def quit(self) -> None:
        # Paylaşılan WebView kapatılmaz. UETS bitince gizli tarayıcı UYAP'a geri döner: UYAP oturum nabzı ve
        # nöbetçi UYAP sayfasını bulamazsa gereksiz yeniden giriş (= Mobil İmza isteği) yapardı.
        try:
            self._komut("Page.navigate", {"url": "https://avukat.uyap.gov.tr/"}, zaman_asimi=15)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001
            pass
