#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP HARİTALAMA MOTORU: uygulamanın gerçek trafiğini dinler, JS dosyalarındaki uç nokta adlarını
ve menü ağacını toplar, kullanıcının gezdiği sayfaları haritaya işler. Salt okunur çalışır.
"""
import os, re, json, time, threading, urllib.parse
from datetime import datetime

import uyap_bridge as ub

HERE = os.path.dirname(os.path.abspath(__file__))
MAP_PATH = os.path.join(HERE, "uyap_map_live.json")
BLUEPRINT = os.path.join(os.path.dirname(HERE), "uyap_api_blueprint.json")
STATIC_EXT = re.compile(r"\.(js|css|woff2?|ttf|png|jpe?g|gif|svg|ico|map)(\?.*)?$", re.I)
RISKY_MENU = re.compile(r"(sil|kaydet|gönder|gonder|imza|onayla|iptal|çıkış|cikis|ödeme|odeme|feragat|vazgeç|talep|başvuru|basvuru|açılış|acilis|ekle)", re.I)


def schema(x, depth=0):
    if depth > 4:
        return "..."
    if isinstance(x, dict):
        return {k: schema(v, depth + 1) for k, v in list(x.items())[:60]}
    if isinstance(x, list):
        return [schema(x[0], depth + 1)] if x else []
    return type(x).__name__


def trim(x, n=3):
    if isinstance(x, list):
        return [trim(i, n) for i in x[:n]]
    if isinstance(x, dict):
        return {k: trim(v, n) for k, v in x.items()}
    if isinstance(x, str) and len(x) > 200:
        return x[:200] + "…"
    return x


class DiscoveryStore:
    def __init__(self):
        self.lock = threading.RLock()
        self.endpoints = {}   # "METHOD path" -> kayıt
        self.static_refs = {}  # path -> {"called": bool}
        self.menu = []
        self.menu_pages = {}  # menuAdi -> {url, endpoints, ts}
        self._dirty = False
        self._load()

    def _load(self):
        if os.path.exists(MAP_PATH):
            try:
                d = json.load(open(MAP_PATH, encoding="utf-8"))
                self.endpoints = d.get("endpoints", {})
                self.static_refs = d.get("static_refs", {})
                self.menu = d.get("menu", [])
                self.menu_pages = d.get("menu_pages", {})
            except Exception:
                pass
        if not self.endpoints and os.path.exists(BLUEPRINT):
            try:
                bp = json.load(open(BLUEPRINT, encoding="utf-8"))
                for ep in bp.get("all_endpoints", []):
                    key = f"{ep['method']} {ep['path']}"
                    self.endpoints[key] = {
                        "key": key, "method": ep["method"], "path": ep["path"], "host": "",
                        "hits": ep.get("hit_count", 1), "first_seen": ep.get("first_seen", ""),
                        "last_seen": ep.get("first_seen", ""), "sources": ["blueprint"], "isNew": False,
                        "payload_sample": ep.get("request_payload_sample"),
                        "response_schema": schema(ep.get("response_sample")),
                        "response_sample": trim(ep.get("response_sample")), "pages": []}
            except Exception:
                pass
        for e in self.endpoints.values():
            if e["method"] in ("POST", "GET") and ub.is_safe_path(e["path"]) and e.get("hits"):
                ub.KNOWN_READ.add(e["path"]) if "blueprint" in e.get("sources", []) and ub.ALLOW.search(e["path"]) else None

    def save(self, force=False):
        with self.lock:
            if not (self._dirty or force):
                return
            d = {"endpoints": self.endpoints, "static_refs": self.static_refs, "menu": self.menu,
                 "menu_pages": self.menu_pages, "saved": datetime.now().isoformat()}
            tmp = MAP_PATH + ".tmp"
            json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
            os.replace(tmp, MAP_PATH)
            self._dirty = False

    def record(self, e: dict, source="app"):
        """Yakalanan bir isteği haritaya işler. Yeni uç noktaysa True döner."""
        url = e.get("url") or ""
        if not url or STATIC_EXT.search(url):
            return None
        u = urllib.parse.urlparse(url)
        path = u.path or url
        host = u.netloc if u.netloc and "avukat.uyap.gov.tr" not in u.netloc else ""
        method = (e.get("method") or "GET").upper()
        if not re.search(r"\.(ajx|uyap)$|/api/|/portal/|\.do$", path):
            return None
        key = f"{method} {path}"
        now = datetime.now().isoformat(timespec="seconds")
        resp = e.get("responseBody")
        with self.lock:
            new = key not in self.endpoints
            rec = self.endpoints.setdefault(key, {
                "key": key, "method": method, "path": path, "host": host, "hits": 0, "first_seen": now,
                "sources": [], "isNew": True, "payload_sample": None, "response_schema": None,
                "response_sample": None, "pages": []})
            rec["hits"] += 1
            rec["last_seen"] = now
            rec["status"] = e.get("status")
            if source not in rec["sources"]:
                rec["sources"].append(source)
            pl = e.get("requestPayload")
            if pl is not None and not rec.get("payload_sample"):
                rec["payload_sample"] = trim(pl)
            if resp is not None and not rec.get("response_schema"):
                rec["response_schema"] = schema(resp)
                rec["response_sample"] = trim(resp)
            pg = e.get("page")
            if pg and pg not in rec["pages"] and len(rec["pages"]) < 8:
                rec["pages"].append(pg)
            if path in self.static_refs:
                self.static_refs[path]["called"] = True
            self._dirty = True
            return key if new else None

    def add_static(self, refs):
        with self.lock:
            for r in refs:
                p = r if r.startswith("/") else "/" + r
                self.static_refs.setdefault(p, {"called": any(k.endswith(" " + p) for k in self.endpoints)})
            self._dirty = True

    def set_menu(self, tree):
        with self.lock:
            self.menu = tree
            self._dirty = True

    def flat_menu(self):
        out = []

        def walk(items):
            for m in items or []:
                if not isinstance(m, dict):
                    continue
                if m.get("menuAdi"):
                    out.append({"adi": m["menuAdi"], "page": m.get("pageName") or m.get("menuLink") or ""})
                walk(m.get("altMenuList"))
        walk(self.menu)
        return out

    def summary(self):
        with self.lock:
            unexplored = [p for p, v in self.static_refs.items() if not v.get("called")]
            return {"endpointCount": len(self.endpoints),
                    "newEndpoints": [k for k, v in self.endpoints.items() if v.get("isNew")],
                    "staticRefs": len(self.static_refs), "unexplored": sorted(unexplored)[:300],
                    "menuItems": len(self.flat_menu()), "menuPages": self.menu_pages}

    def list(self):
        with self.lock:
            return [{k: v for k, v in e.items() if k not in ("response_sample",)} for e in
                    sorted(self.endpoints.values(), key=lambda x: (-x.get("isNew", False), x["path"]))]

    def markdown(self):
        s = self.summary()
        L = ["# UYAP Canlı Harita", f"_Güncelleme: {datetime.now():%d.%m.%Y %H:%M}_", "",
             f"- Uç nokta: **{s['endpointCount']}** (yeni keşfedilen: **{len(s['newEndpoints'])}**)",
             f"- JS içinde adı geçen: **{s['staticRefs']}** (henüz çağrılmamış: **{len(s['unexplored'])}**)", "",
             "## Menü → Sayfa → Uç Noktalar"]
        for m, v in s["menuPages"].items():
            L.append(f"- **{m}** → `{v.get('url','')}`: " + ", ".join(f"`{x}`" for x in v.get("endpoints", [])))
        L += ["", "## Uç Noktalar", "| Metot | Yol | İstek | Kaynak |", "|---|---|---|---|"]
        for e in self.list():
            L.append(f"| {e['method']} | `{e['path']}` | {e['hits']} | {','.join(e['sources'])}{' 🆕' if e.get('isNew') else ''} |")
        L += ["", "## Haritada olup çağrılmamışlar"] + [f"- `{p}`" for p in s["unexplored"]]
        return "\n".join(L)


class Explorer(threading.Thread):
    """Arka planda: pasif trafik dinleme, oturumu açık tutan hafif yoklama, isteğe bağlı menü gezme."""
    def __init__(self, bridge, store):
        super().__init__(daemon=True)
        self.bridge, self.store = bridge, store
        self.auto_explore = False
        self.log = []
        self._static_done = False
        self._last_explore = 0
        self._last_keepalive = 0
        self.visited = set(self.store.menu_pages.keys())

    def say(self, m):
        self.log = (self.log + [f"{datetime.now():%H:%M:%S} {m}"])[-60:]

    def drain(self, source="app"):
        keys = []
        for e in self.bridge.poll_traffic():
            k = self.store.record(e, source)
            if k:
                keys.append(k)
                self.say(f"🆕 Yeni uç nokta: {k}")
        return keys

    def run(self):
        while True:
            try:
                if self.bridge.driver:
                    self.drain()
                    if self.bridge.logged_in():
                        now = time.time()
                        if now - self._last_keepalive > 240:
                            self._last_keepalive = now  # logged_in() zaten hafif bir yoklama yapar
                        if self.auto_explore and now - self._last_explore > 20:
                            self._last_explore = now
                            self.step()
                self.store.save()
            except Exception as ex:
                self.say(f"hata: {ex}")
            time.sleep(3)

    def step(self):
        b, s = self.bridge, self.store
        if not self._static_done:
            refs = b.scan_static_refs()
            s.add_static(refs)
            self._static_done = True
            self.say(f"JS taraması: {len(refs)} uç nokta adı bulundu")
            return
        if not s.menu:
            tree = b.call("/menuListesiGetir.ajx", {})
            s.set_menu(tree if isinstance(tree, list) else [])
            self.say(f"Menü ağacı alındı: {len(s.flat_menu())} öğe")
            return
        for m in s.flat_menu():
            if m["adi"] in self.visited or RISKY_MENU.search(m["adi"]):
                continue
            self.visited.add(m["adi"])
            self.drain()
            if b.click_menu(m["adi"]):
                time.sleep(4)
                keys = self.drain("explore")
                s.menu_pages[m["adi"]] = {"url": b.current_url(), "endpoints": keys, "ts": time.time()}
                self.say(f"Menü gezildi: {m['adi']} ({len(keys)} yeni)")
                b.go_home()
            else:
                s.menu_pages[m["adi"]] = {"url": "", "endpoints": [], "ts": time.time(), "note": "tıklanamadı"}
            s._dirty = True
            return
        self.say("Tüm güvenli menüler gezildi.")
        self.auto_explore = False
