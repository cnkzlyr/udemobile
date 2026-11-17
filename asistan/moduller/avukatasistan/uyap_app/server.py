#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UYAP Mobil sunucusu: gerçek UYAP köprüsü + harita + tutanak analizi + web arayüzü."""
import os, json, mimetypes, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import uyap_bridge as ub
from uyap_bridge import UyapBridge, BridgeError
from discovery import DiscoveryStore, Explorer
from uyap_service import UyapService
from intel import IntelEngine

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")

bridge = UyapBridge()
store = DiscoveryStore()
explorer = Explorer(bridge, store)
service = UyapService(bridge)
intel = IntelEngine(service)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, ctype="application/json; charset=utf-8", status=200, extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    do_POST = lambda self: self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = u.path
        if p.startswith("/api/"):
            try:
                return self.api(p, q)
            except BridgeError as e:
                msg = str(e)
                return self._send({"error": msg, "needLogin": "Oturum" in msg or "bağlantı" in msg}, status=503)
            except Exception as e:
                return self._send({"error": f"{type(e).__name__}: {e}"}, status=500)
        f = os.path.join(STATIC, "index.html" if p in ("/", "") else p.lstrip("/"))
        if os.path.isfile(f) and os.path.abspath(f).startswith(STATIC):
            return self._send(open(f, "rb").read(), mimetypes.guess_type(f)[0] or "application/octet-stream")
        self._send({"error": "yok"}, status=404)

    def api(self, p, q):
        # --- bağlantı ---
        if p == "/api/bridge/status":
            return self._send(dict(bridge.status(), explore=explorer.auto_explore))
        if p == "/api/bridge/launch":
            bridge.launch()
            return self._send({"ok": True})
        if p == "/api/bridge/attach":
            bridge.attach()
            if not explorer.is_alive():
                explorer.start()
            return self._send(bridge.status())
        # --- veri ---
        if p == "/api/user":
            return self._send(service.user())
        if p == "/api/stats":
            return self._send(service.stats())
        if p == "/api/cases":
            data, cached = service.cases()
            return self._send({"cached": cached, "items": data})
        if p.startswith("/api/cases/"):
            return self._send(service.case_detail(urllib.parse.unquote(p[11:])))
        if p == "/api/hearings":
            data, cached = service.hearings(int(q.get("back", 0)), int(q.get("fwd", 30)))
            return self._send({"cached": cached, "items": data})
        if p == "/api/notifications":
            data, cached = service.notifications()
            return self._send({"cached": cached, "items": data})
        if p.startswith("/api/document/"):
            data, ctype, disp = service.document(urllib.parse.unquote(p[14:]), q.get("dosyaId", ""))
            ext = "udf" if data[:2] == b"PK" else "pdf" if data[:4] == b"%PDF" else "bin"
            ct = "application/pdf" if ext == "pdf" else "application/octet-stream"
            return self._send(data, ct, extra={"Content-Disposition": f'inline; filename="evrak.{ext}"'})
        # --- harita ---
        if p == "/api/discovery":
            return self._send(dict(store.summary(), endpoints=store.list(), log=explorer.log, explore=explorer.auto_explore))
        if p == "/api/discovery/explore":
            explorer.auto_explore = q.get("on", "1") == "1"
            return self._send({"explore": explorer.auto_explore})
        if p == "/api/discovery/export":
            return self._send(store.markdown(), "text/markdown; charset=utf-8")
        # --- tutanak analizi ---
        if p == "/api/intel":
            return self._send({"running": intel.state["running"], "progress": intel.state["progress"], "items": intel.state["items"]})
        if p == "/api/intel/start":
            return self._send({"started": intel.start(int(q.get("days", 30)))})
        if p == "/api/intel/toggle":
            return self._send({"ok": intel.toggle(q.get("dosyaId", ""), q.get("todo", ""))})
        if p == "/api/intel/proposals":
            return self._send(intel.proposals())
        self._send({"error": "bilinmeyen uç nokta"}, status=404)


def main(port=8080, host="127.0.0.1"):
    ub.KNOWN_READ.update(e["path"] for e in store.endpoints.values() if "blueprint" in e.get("sources", []) and ub.ALLOW.search(e["path"]))
    if bridge.debugger_alive():
        try:
            bridge.attach()
            explorer.start()
        except Exception as e:
            print("Otomatik bağlanılamadı:", e)
    print(f"⚖️  UYAP Mobil: http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser()
    a.add_argument("--port", type=int, default=8080)
    a.add_argument("--host", default="127.0.0.1")
    x = a.parse_args()
    main(x.port, x.host)
