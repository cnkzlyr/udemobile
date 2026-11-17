#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP KÖPRÜSÜ: Kullanıcının kendi, giriş yapılmış Chromium oturumuna uzaktan hata ayıklama
portuyla (CDP) bağlanır. İstekler sayfanın kendi oturumuyla (same-origin fetch) gönderilir.
- Salt okunur kural: kaydet/sil/gönder/imzala gibi uç noktalar engellenir.
- Makul hız sınırı: istekler arasında en az MIN_INTERVAL saniye.
- Gizlenme/izleri saklama YOKTUR; oturum kullanıcıya aittir.
"""
import os, re, json, time, threading, subprocess, urllib.request, base64

BASE = "https://avukat.uyap.gov.tr"
CHROMIUM = "/data/data/com.termux/files/usr/bin/chromium-browser"
CHROMEDRIVER = "/data/data/com.termux/files/usr/bin/chromedriver"
DEFAULT_PROFILE = os.path.expanduser("~/.uyap_crawler_profile")
MIN_INTERVAL = 0.6

ALLOW = re.compile(r"(sorgula|list|get|bilgi|ayrinti|search|durusma|safahat|evrak|taraf|hesap|menu|login|bakiye|duyuru|bildirim|parametre|turleri|birim|mahkeme|tahsilat|harc|view_document)", re.I)
DENY = re.compile(r"(kaydet|sil(?!ahat)|gonder(?!ilecek)|imza|ekle|guncelle|iptal|update|delete|save|send|olustur|yukle|upload|feragat|vazgec|cikis|logout|kapat|talep|odemeyap|odeme_yap)", re.I)
KNOWN_READ = set()  # discovery tarafından, kullanıcının gezdiği okuma uç noktalarıyla doldurulur


class BridgeError(Exception):
    pass


def is_safe_path(path: str) -> bool:
    path = path.split("?")[0]
    if path in KNOWN_READ:
        return True
    return bool(ALLOW.search(path)) and not DENY.search(path)


SPY_JS = r"""
(function(){
 if(window.__UYAP_SPY__) return; window.__UYAP_SPY__=true; window.__UYAP_Q__=[]; window.__UYAP_BRIDGE_SILENT__=false;
 function rec(e){ if(window.__UYAP_Q__.length>500) window.__UYAP_Q__.shift(); window.__UYAP_Q__.push(e); }
 function parse(t){ try{return JSON.parse(t);}catch(_){ return t && t.length>3000 ? t.slice(0,3000) : t; } }
 const of=window.fetch;
 window.fetch=function(a,o){
   const silent=window.__UYAP_BRIDGE_SILENT__===true; o=o||{};
   const url=typeof a==='string'?a:(a&&a.url)||''; const method=(o.method||(a&&a.method)||'GET').toUpperCase();
   const body=o.body; const p=of.apply(this,arguments);
   if(!silent){ p.then(r=>{ const c=r.clone(); c.text().then(t=>rec({url:url,method:method,requestPayload:body?parse(String(body)):null,status:r.status,responseBody:parse(t),ts:Date.now(),page:location.href})).catch(()=>{}); }).catch(()=>{}); }
   return p; };
 const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
 XMLHttpRequest.prototype.open=function(m,u){ this._m=m; this._u=u; return oo.apply(this,arguments); };
 XMLHttpRequest.prototype.send=function(b){ const x=this; x.addEventListener('load',function(){
     rec({url:x._u,method:(x._m||'GET').toUpperCase(),requestPayload:b?parse(String(b)):null,status:x.status,
          responseBody:(x.responseType===''||x.responseType==='text')?parse(x.responseText):null,ts:Date.now(),page:location.href}); });
   return os.apply(this,arguments); };
})();
"""

CALL_JS = r"""
const [path, body, method, done] = arguments;
window.__UYAP_BRIDGE_SILENT__ = true;
let p;
try {
  p = fetch(path, {method: method, credentials: 'same-origin',
     headers: {'Content-Type':'application/json','Accept':'application/json, text/plain, */*'},
     body: method === 'GET' ? undefined : body});
} finally { window.__UYAP_BRIDGE_SILENT__ = false; }
p.then(async r => { const t = await r.text(); done({status: r.status, text: t, url: r.url}); })
 .catch(e => done({error: String(e)}));
"""

BIN_JS = r"""
const [path, done] = arguments;
window.__UYAP_BRIDGE_SILENT__ = true;
let p;
try { p = fetch(path, {credentials:'same-origin'}); } finally { window.__UYAP_BRIDGE_SILENT__ = false; }
p.then(async r => { const b = await r.blob(); const fr = new FileReader();
  fr.onloadend = () => done({status: r.status, ctype: r.headers.get('content-type')||'', disp: r.headers.get('content-disposition')||'', b64: String(fr.result).split(',')[1]||''});
  fr.readAsDataURL(b); }).catch(e => done({error: String(e)}));
"""

STATIC_JS = r"""
const done = arguments[arguments.length-1];
window.__UYAP_BRIDGE_SILENT__ = true;
(async () => {
  const urls = [...new Set(performance.getEntriesByType('resource').map(r => r.name)
     .filter(u => /\.js(\?|$)/.test(u) && u.startsWith(location.origin)))];
  const out = new Set();
  for (const u of urls.slice(0, 60)) {
    try { const t = await (await fetch(u, {credentials:'same-origin'})).text();
      (t.match(/["'`]\/?[A-Za-z0-9_\-\/]{3,80}\.(?:ajx|uyap)["'`]/g) || []).forEach(m => out.add(m.slice(1, -1)));
    } catch (e) {}
    await new Promise(r => setTimeout(r, 200));
  }
  window.__UYAP_BRIDGE_SILENT__ = false;
  done([...out]);
})();
"""

CLICK_JS = r"""
const name = arguments[0];
const els = [...document.querySelectorAll('a,li,span,button,[role=menuitem]')].filter(e => {
  const t = (e.childElementCount === 0 ? e.textContent : e.firstChild && e.firstChild.nodeType === 3 ? e.firstChild.textContent : '') || '';
  return t.trim() === name; });
if (!els.length) return false;
const el = els[0]; (el.closest('a,button,li') || el).click(); return true;
"""


class UyapBridge:
    def __init__(self, port=9222, profile=DEFAULT_PROFILE):
        self.port = port
        self.profile = profile
        self.driver = None
        self.lock = threading.RLock()
        self._last = 0.0
        self._login = (0.0, False)
        self.home_url = None
        self.calls = 0

    # ---------- tarayıcı ----------
    def debugger_alive(self) -> bool:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=1.5).read()
            return True
        except Exception:
            return False

    def launch(self, url=BASE):
        """Chromium'u uzaktan hata ayıklama portuyla açar (zaten açıksa dokunmaz)."""
        if self.debugger_alive():
            return True
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        env.setdefault("TMPDIR", "/data/data/com.termux/files/usr/tmp")
        cmd = [CHROMIUM, f"--remote-debugging-port={self.port}", "--remote-allow-origins=*",
               f"--user-data-dir={self.profile}", "--no-first-run", "--no-sandbox",
               "--disable-dev-shm-usage", url]
        subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(40):
            if self.debugger_alive():
                return True
            time.sleep(0.5)
        raise BridgeError("Chromium hata ayıklama portu açılamadı")

    def attach(self):
        with self.lock:
            if self.driver:
                return True
            if not self.debugger_alive():
                raise BridgeError("Tarayıcı bağlantı modunda değil. 'Tarayıcıyı Aç' ile başlatın.")
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            o = Options()
            o.debugger_address = f"127.0.0.1:{self.port}"
            svc = Service(executable_path=CHROMEDRIVER) if os.path.exists(CHROMEDRIVER) else None
            self.driver = webdriver.Chrome(service=svc, options=o) if svc else webdriver.Chrome(options=o)
            self.driver.set_script_timeout(90)
            try:
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": SPY_JS})
            except Exception:
                pass
            self._select_uyap_tab()
            self._inject_spy()
            return True

    def detach(self):
        with self.lock:
            try:
                if self.driver:
                    self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def _select_uyap_tab(self):
        d = self.driver
        try:
            if "avukat.uyap.gov.tr" in d.current_url:
                return
        except Exception:
            pass
        for h in d.window_handles:
            d.switch_to.window(h)
            if "avukat.uyap.gov.tr" in d.current_url:
                return

    def _inject_spy(self):
        try:
            self.driver.execute_script(SPY_JS)
        except Exception:
            pass

    def _ensure(self):
        if not self.driver:
            self.attach()
        try:
            self.driver.current_url
        except Exception:
            self.driver = None
            self.attach()
        self._select_uyap_tab()

    # ---------- durum ----------
    def current_url(self) -> str:
        try:
            with self.lock:
                return self.driver.current_url if self.driver else ""
        except Exception:
            return ""

    def logged_in(self, max_age=15) -> bool:
        if time.time() - self._login[0] < max_age:
            return self._login[1]
        ok = False
        try:
            with self.lock:
                self._ensure()
                url = self.driver.current_url
                if "avukat.uyap.gov.tr" in url and not re.search(r"giris|login", url, re.I):
                    r = self._fetch("/kullaniciLoginMi.ajx", None, "GET")
                    ok = r.get("status") == 200 and r.get("text", "").strip().lower() == "true"
                    if ok and not self.home_url:
                        self.home_url = url
        except Exception:
            ok = False
        self._login = (time.time(), ok)
        return ok

    def status(self) -> dict:
        alive = self.debugger_alive()
        return {"browserAlive": alive, "attached": bool(self.driver), "url": self.current_url(),
                "loggedIn": self.logged_in() if alive else False, "port": self.port, "calls": self.calls}

    # ---------- çağrı ----------
    def _throttle(self):
        wait = self._last + MIN_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def _fetch(self, path, body, method):
        return self.driver.execute_async_script(CALL_JS, path, body, method)

    def call(self, path: str, payload=None, method="POST"):
        """Salt okunur uç noktayı sayfa oturumuyla çağırır; JSON döner."""
        if not is_safe_path(path):
            raise BridgeError(f"Güvenlik kuralı: '{path}' salt-okunur listede değil, engellendi.")
        body = json.dumps(payload if payload is not None else {}, ensure_ascii=False)
        with self.lock:
            self._ensure()
            self._throttle()
            r = self._fetch(path, body, method)
            self.calls += 1
        if r.get("error"):
            raise BridgeError(r["error"])
        text = r.get("text", "")
        if r.get("status") != 200:
            raise BridgeError(f"HTTP {r.get('status')} {path}")
        if text.lstrip().startswith("<"):
            self._login = (0.0, False)
            raise BridgeError("Oturum geçersiz veya süresi dolmuş (giriş sayfası döndü)")
        try:
            return json.loads(text)
        except Exception:
            return text

    def fetch_binary(self, path: str):
        """Evrak gibi ikili içeriği indirir: (bytes, content_type, content_disposition)."""
        if not is_safe_path(path):
            raise BridgeError("Güvenlik kuralı: bu yol indirilemez")
        with self.lock:
            self._ensure()
            self._throttle()
            r = self.driver.execute_async_script(BIN_JS, path)
            self.calls += 1
        if r.get("error") or r.get("status") != 200:
            raise BridgeError(r.get("error") or f"HTTP {r.get('status')}")
        return base64.b64decode(r.get("b64", "")), r.get("ctype", ""), r.get("disp", "")

    # ---------- keşif yardımcıları ----------
    def poll_traffic(self) -> list:
        """Uygulamanın kendi XHR/fetch trafiğini toplar (pasif dinleme)."""
        try:
            with self.lock:
                if not self.driver:
                    return []
                self._select_uyap_tab()
                self._inject_spy()
                return self.driver.execute_script(
                    "var q=window.__UYAP_Q__||[]; window.__UYAP_Q__=[]; return q;") or []
        except Exception:
            return []

    def scan_static_refs(self) -> list:
        with self.lock:
            self._ensure()
            return self.driver.execute_async_script(STATIC_JS) or []

    def click_menu(self, name: str) -> bool:
        with self.lock:
            self._ensure()
            return bool(self.driver.execute_script(CLICK_JS, name))

    def go_home(self):
        if self.home_url:
            with self.lock:
                self._ensure()
                if self.driver.current_url != self.home_url:
                    self.driver.get(self.home_url)