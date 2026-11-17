#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================================
⚖️ UYAP AVUKAT PORTALI - REVERSE ENGINEERING & API KEŞİF MOTORU (FAZ 1)
========================================================================================
Bu betik, "avukat.uyap.gov.tr" Angular SPA mimarisini analiz eder.
Kullanıcının e-İmza veya Mobil İmza ile oturum açmasının ardından sol menüleri ve
sayfaları otomatik/etkileşimli olarak tarar; arka planda tetiklenen tüm XHR/Fetch
isteklerini (endpoint, HTTP metodu, header, payload, response JSON şeması) yakalar.

Elde edilen verileri iki formatta kaydeder:
  1. uyap_api_blueprint.json (Faz 2 FastAPI modelleri ve PWA için makine okunabilir şema)
  2. API_DOCS.md            (İnsan tarafından okunabilir detaylı API dokümantasyonu)

Çift Motor (Dual-Engine) Desteği:
  - Termux (Android) Ortamı: Doğal Selenium 4.x + Chromium/ChromeDriver + CDP motoru
  - Masaüstü (Mac/Linux/Win): Playwright (Async Python) motoru veya Selenium
========================================================================================
"""

import os
import sys
import json
import time
import re
import argparse
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional

# Terminal renkleri
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def log_info(msg: str):
    print(f"{Colors.BLUE}[BİLGİ]{Colors.ENDC} {time.strftime('%H:%M:%S')} - {msg}", flush=True)

def log_success(msg: str):
    print(f"{Colors.GREEN}[BAŞARILI]{Colors.ENDC} {time.strftime('%H:%M:%S')} - {msg}", flush=True)

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[UYARI]{Colors.ENDC} {time.strftime('%H:%M:%S')} - {msg}", flush=True)

def log_error(msg: str):
    print(f"{Colors.RED}[HATA]{Colors.ENDC} {time.strftime('%H:%M:%S')} - {msg}", flush=True)

def log_api(method: str, url: str, status: Optional[int] = None):
    st_text = f" -> {status}" if status else ""
    color = Colors.GREEN if status and status < 400 else Colors.YELLOW
    print(f"  {Colors.BOLD}{color}[API İSTEĞİ]{Colors.ENDC} {method.upper()} {url}{st_text}", flush=True)


# ======================================================================================
# 1. VERİ MASKESİ VE ŞEMA ÇIKARICI YARDIMCILARI
# ======================================================================================

def mask_sensitive_value(key: str, value: Any) -> Any:
    """Kişisel veri güvenliği için gerçek TC Kimlik, token ve hassas verileri maskeler."""
    if not isinstance(value, str):
        return value
    key_lower = key.lower()
    auth_words = ["token", "bearer", "jwt", "authorization", "auth-token", "authtoken", "cookie", "session"]
    if any(k in key_lower for k in auth_words) and "author" not in key_lower:
        if len(value) > 20:
            return value[:10] + "...[MASKED_TOKEN]..." + value[-5:]
        return "[MASKED_TOKEN]"
    if any(k in key_lower for k in ["tckn", "tc_kimlik", "kimlikno", "tcno", "tc_no"]):
        return "11111111111"
    if any(k in key_lower for k in ["iban"]):
        return "TR000000000000000000000000"
    if any(k in key_lower for k in ["telefon", "phone", "gsm"]):
        return "05000000000"
    if any(k in key_lower for k in ["sifre", "password", "pin", "parola"]):
        return "******"
    # 11 haneli TCKN deseni kontrolü
    if re.fullmatch(r"\d{11}", value):
        return "11111111111"
    return value

def sanitize_json(data: Any) -> Any:
    """Veri yapısındaki hassas bilgileri özyinelemeli (recursive) olarak maskeler."""
    if isinstance(data, dict):
        return {k: sanitize_json(mask_sensitive_value(k, v)) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json(v) for v in data[:5]]  # Çok uzun dizilerden ilk 5 örneği al
    return data

def infer_schema(data: Any) -> Any:
    """Verilen JSON verisinden TypeScript / OpenAPI uyumlu veri şemasını çıkarır."""
    if isinstance(data, dict):
        schema = {}
        for k, v in data.items():
            schema[k] = infer_schema(v)
        return {"_type": "object", "_properties": schema}
    elif isinstance(data, list):
        if not data:
            return {"_type": "array", "_items": "any"}
        item_schemas = [infer_schema(x) for x in data[:3]]
        return {"_type": "array", "_items": item_schemas[0] if item_schemas else "any"}
    elif isinstance(data, bool):
        return "boolean"
    elif isinstance(data, int):
        return "integer"
    elif isinstance(data, float):
        return "number"
    elif isinstance(data, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}", data):
            return "string (date/time)"
        if re.match(r"^[0-9a-fA-F-]{36}$", data):
            return "string (uuid)"
        return "string"
    elif data is None:
        return "null"
    return type(data).__name__


# ======================================================================================
# 2. XHR / FETCH İÇİN SAYFA İÇİ ENJEKSİYON CASUS KODU (INJECTABLE JS SPY)
# ======================================================================================

INJECTED_JS_SPY = r"""
(function() {
    if (window.__UYAP_API_SPY_ACTIVE__) return;
    window.__UYAP_API_SPY_ACTIVE__ = true;
    window.__UYAP_CAPTURED_REQUESTS__ = [];
    window.__UYAP_CURRENT_MENU__ = "Giriş / Başlangıç";

    function recordRequest(entry) {
        entry.id = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
        entry.menuContext = window.__UYAP_CURRENT_MENU__;
        window.__UYAP_CAPTURED_REQUESTS__.push(entry);
    }

    // 1. window.fetch müdahalesi
    const origFetch = window.fetch;
    window.fetch = async function(...args) {
        let url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
        let opts = args[1] || {};
        let method = (opts.method || (args[0] && args[0].method) || 'GET').toUpperCase();
        let headers = opts.headers || (args[0] && args[0].headers) || {};
        let body = opts.body;

        let entry = {
            type: 'fetch',
            url: url,
            method: method,
            requestHeaders: headers,
            requestPayload: null,
            status: 0,
            responseBody: null,
            timestamp: new Date().toISOString()
        };

        if (body) {
            try {
                entry.requestPayload = typeof body === 'string' ? JSON.parse(body) : body;
            } catch(e) {
                entry.requestPayload = String(body);
            }
        }

        try {
            const resp = await origFetch.apply(this, args);
            entry.status = resp.status;
            const clone = resp.clone();
            clone.text().then(txt => {
                try {
                    entry.responseBody = JSON.parse(txt);
                } catch(e) {
                    entry.responseBody = txt.length > 2000 ? txt.substr(0, 2000) + '...[TRUNCATED]' : txt;
                }
                recordRequest(entry);
            }).catch(e => {
                recordRequest(entry);
            });
            return resp;
        } catch(err) {
            entry.error = err.toString();
            recordRequest(entry);
            throw err;
        }
    };

    // 2. XMLHttpRequest müdahalesi
    const origOpen = XMLHttpRequest.prototype.open;
    const origSend = XMLHttpRequest.prototype.send;
    const origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._method = method;
        this._url = url;
        this._reqHeaders = {};
        return origOpen.apply(this, [method, url, ...rest]);
    };

    XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
        if (!this._reqHeaders) this._reqHeaders = {};
        this._reqHeaders[header] = value;
        return origSetHeader.apply(this, [header, value]);
    };

    XMLHttpRequest.prototype.send = function(body) {
        this._payload = body;
        this.addEventListener('load', function() {
            let parsedPayload = null;
            if (this._payload) {
                try {
                    parsedPayload = JSON.parse(this._payload);
                } catch(e) {
                    parsedPayload = String(this._payload);
                }
            }

            let parsedResp = null;
            try {
                parsedResp = JSON.parse(this.responseText);
            } catch(e) {
                parsedResp = this.responseText && this.responseText.length > 2000 
                    ? this.responseText.substr(0, 2000) + '...[TRUNCATED]' 
                    : this.responseText;
            }

            let entry = {
                type: 'xhr',
                url: this._url,
                method: (this._method || 'GET').toUpperCase(),
                requestHeaders: this._reqHeaders || {},
                requestPayload: parsedPayload,
                status: this.status,
                responseBody: parsedResp,
                timestamp: new Date().toISOString()
            };
            recordRequest(entry);
        });
        return origSend.apply(this, arguments);
    };
})();
"""


# ======================================================================================
# 3. YAKALANAN VERİLERİ ANALİZ EDEN BLUEPRINT MOTORU
# ======================================================================================

class BlueprintBuilder:
    """Yakalana ham HTTP isteklerini hiyerarşik endpoint sözlüğüne ve API dokümanına çevirir."""

    def __init__(self, base_url: str = "https://avukat.uyap.gov.tr"):
        self.base_url = base_url
        self.endpoints: Dict[str, Dict[str, Any]] = {}
        self.raw_records: List[Dict[str, Any]] = []
        self.detected_auth_headers: set = set()
        self.detected_cookies: set = set()

    def add_call(self, record: Dict[str, Any]):
        """Yeni bir XHR/Fetch isteğini sözlüğe ekler ve şemasını günceller."""
        url = record.get("url", "")
        if not url:
            return

        # Statik kaynakları filtrele (.js, .css, .woff, .png, .svg vb.)
        if re.search(r"\.(js|css|woff2?|ttf|png|jpe?g|gif|svg|ico)(\?.*)?$", url, re.I):
            return

        # Tam URL ve path ayrımı
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path or url
        method = (record.get("method") or "GET").upper()
        status = record.get("status", 0)

        # UYAP API endpoint belirteci
        endpoint_key = f"{method} {path}"

        headers = record.get("requestHeaders") or {}
        if isinstance(headers, dict):
            for hk in headers.keys():
                hk_lower = hk.lower()
                if "auth" in hk_lower or "bearer" in hk_lower or "token" in hk_lower or "jwt" in hk_lower:
                    self.detected_auth_headers.add(hk)
                if "cookie" in hk_lower or "session" in hk_lower:
                    self.detected_auth_headers.add(hk)
                if "csrf" in hk_lower or "xsrf" in hk_lower:
                    self.detected_auth_headers.add(hk)

        # Query parametreleri
        query_dict = urllib.parse.parse_qs(parsed_url.query) if parsed_url.query else {}

        # Payload & Response
        payload = record.get("requestPayload")
        response_body = record.get("responseBody")

        # Maskeleme
        sanitized_payload = sanitize_json(payload)
        sanitized_response = sanitize_json(response_body)

        # Kategori tahmini
        category = self._guess_category(path, record.get("menuContext", ""))

        if endpoint_key not in self.endpoints:
            self.endpoints[endpoint_key] = {
                "method": method,
                "path": path,
                "full_url": url,
                "category": category,
                "menu_context": record.get("menuContext", "Genel"),
                "query_params": query_dict,
                "request_headers_sample": sanitize_json(headers),
                "request_payload_sample": sanitized_payload,
                "request_schema": infer_schema(sanitized_payload) if sanitized_payload else None,
                "response_sample": sanitized_response,
                "response_schema": infer_schema(sanitized_response) if sanitized_response else None,
                "status_codes": [status] if status else [],
                "hit_count": 1,
                "first_seen": record.get("timestamp", datetime.now().isoformat())
            }
        else:
            ep = self.endpoints[endpoint_key]
            ep["hit_count"] += 1
            if status and status not in ep["status_codes"]:
                ep["status_codes"].append(status)
            if not ep["request_payload_sample"] and sanitized_payload:
                ep["request_payload_sample"] = sanitized_payload
                ep["request_schema"] = infer_schema(sanitized_payload)
            if not ep["response_sample"] and sanitized_response:
                ep["response_sample"] = sanitized_response
                ep["response_schema"] = infer_schema(sanitized_response)

        self.raw_records.append(record)

    def _guess_category(self, path: str, menu_context: str) -> str:
        ctx_lower = (menu_context or "").lower()
        path_lower = path.lower()

        if any(w in ctx_lower or w in path_lower for w in ["dava", "dosya", "case", "esas"]):
            return "Dava Dosyaları ve Dosya Sorgulama"
        if any(w in ctx_lower or w in path_lower for w in ["durusma", "duruşma", "hearing", "celse", "takvim"]):
            return "Duruşma Takvimi ve Celseler"
        if any(w in ctx_lower or w in path_lower for w in ["tebligat", "uets", "evrak", "document", "belge"]):
            return "Evrak ve Tebligat İşlemleri"
        if any(w in ctx_lower or w in path_lower for w in ["safahat", "tarihce", "log"]):
            return "Dosya Safahatı"
        if any(w in ctx_lower or w in path_lower for w in ["icra", "takip"]):
            return "İcra Takip İşlemleri"
        if any(w in ctx_lower or w in path_lower for w in ["auth", "login", "kullanici", "user", "me", "profil"]):
            return "Kimlik Doğrulama ve Kullanıcı Profili"
        if any(w in ctx_lower or w in path_lower for w in ["kasa", "harc", "harç", "makbuz", "odeme"]):
            return "Kasa ve Harç İşlemleri"
        return "Diğer Servisler"

    def export_blueprint_json(self, output_path: str):
        """Hiyerarşik OpenAPI/Blueprint JSON dosyasını oluşturur."""
        categorized: Dict[str, List[Dict[str, Any]]] = {}
        for ep in self.endpoints.values():
            cat = ep["category"]
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(ep)

        blueprint = {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "base_url": self.base_url,
                "total_unique_endpoints": len(self.endpoints),
                "total_requests_captured": len(self.raw_records),
                "auth_patterns": {
                    "detected_headers": sorted(list(self.detected_auth_headers)),
                    "detected_cookies": sorted(list(self.detected_cookies))
                }
            },
            "categories": categorized,
            "all_endpoints": list(self.endpoints.values())
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(blueprint, f, ensure_ascii=False, indent=2)
        log_success(f"Blueprint JSON dosyası kaydedildi: {output_path}")

    def export_api_docs_md(self, output_path: str):
        """İnsan tarafından okunabilir şık Markdown dokümantasyonu üretir."""
        categorized: Dict[str, List[Dict[str, Any]]] = {}
        for ep in self.endpoints.values():
            cat = ep["category"]
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(ep)

        md = []
        md.append("# ⚖️ UYAP Avukat Portalı - Keşfedilen API Uç Noktaları Dokümantasyonu")
        md.append(f"> **Oluşturulma Tarihi:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        md.append(f"> **Toplam Keşfedilen Endpoint:** {len(self.endpoints)}")
        md.append(f"> **Toplam İncelenen İstek:** {len(self.raw_records)}")
        md.append("")
        md.append("---")
        md.append("")
        md.append("## 📌 1. Kimlik Doğrulama & Oturum Mimarisi")
        md.append("UYAP Avukat Portalı SPA mimarisi, kimlik doğrulama sonrasında tarayıcı oturumuna ait aşağıdaki anahtar başlıkları kullanır:")
        md.append("")
        if self.detected_auth_headers:
            for h in sorted(self.detected_auth_headers):
                md.append(f"- **Header:** `{h}`")
        else:
            md.append("- Standart Bearer Token / Cookie tabanlı oturum anahtarları.")
        md.append("")
        md.append("---")
        md.append("")
        md.append("## 📑 2. Kategoriye Göre API Haritası")
        md.append("")

        for cat_name, ep_list in sorted(categorized.items()):
            md.append(f"### 📂 {cat_name}")
            md.append("")
            md.append("| Metot | Endpoint / Yol | Tetikleyen Menü | Durum Kodları | Çağrı Sayısı |")
            md.append("| :--- | :--- | :--- | :---: | :---: |")
            for ep in ep_list:
                status_str = ", ".join(map(str, ep["status_codes"])) or "200"
                md.append(f"| **`{ep['method']}`** | `{ep['path']}` | {ep['menu_context']} | {status_str} | {ep['hit_count']} |")
            md.append("")

            # Detaylı endpoint incelemeleri
            for ep in ep_list:
                md.append(f"#### 🔍 `{ep['method']} {ep['path']}`")
                md.append(f"- **Tetikleyen Menü / Bölüm:** `{ep['menu_context']}`")
                md.append(f"- **Hedef URL:** `{ep['full_url']}`")
                if ep["status_codes"]:
                    md.append(f"- **Dönen HTTP Kodları:** `{ep['status_codes']}`")
                md.append("")

                # Query Params
                if ep.get("query_params"):
                    md.append("**Query Parametreleri:**")
                    md.append("```json")
                    md.append(json.dumps(ep["query_params"], ensure_ascii=False, indent=2))
                    md.append("```")
                    md.append("")

                # Request Payload
                if ep.get("request_payload_sample"):
                    md.append("**Örnek İstek Gövdesi (Payload):**")
                    md.append("```json")
                    md.append(json.dumps(ep["request_payload_sample"], ensure_ascii=False, indent=2))
                    md.append("```")
                    md.append("")

                # Response Schema
                if ep.get("response_schema"):
                    md.append("**Yanıt Şeması (Inferred Schema):**")
                    md.append("```json")
                    md.append(json.dumps(ep["response_schema"], ensure_ascii=False, indent=2))
                    md.append("```")
                    md.append("")

                # Response Sample
                if ep.get("response_sample"):
                    md.append("**Örnek Yanıt (Response Sample - Maskelenmiş):**")
                    md.append("```json")
                    md.append(json.dumps(ep["response_sample"], ensure_ascii=False, indent=2))
                    md.append("```")
                    md.append("")

                md.append("---")
                md.append("")

        md.append("## 🚀 3. Faz 2: FastAPI & İstemci Geliştirme Notları")
        md.append("1. Keşfedilen endpoint'ler Pydantic veri modellerine (`schemas.py`) aktarılacak.")
        md.append("2. Oturum köprüsü (Cookie/Token forwarding) ile mobil uyumlu PWA arayüzü kurulacak.")
        md.append("")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        log_success(f"Markdown API dokümantasyonu kaydedildi: {output_path}")


# ======================================================================================
# 4. MOTOR 1: SELENIUM + CHROMEDRIVER + CDP (TERMUX DOĞAL MOTORU)
# ======================================================================================

def run_selenium_crawler(args, blueprint: BlueprintBuilder):
    """Termux Android ortamında veya Selenium yüklü sistemlerde çalışan motor."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError:
        log_error("Selenium kütüphanesi bulunamadı! 'pip install selenium' çalıştırın.")
        return False

    log_info("Selenium 4.x + CDP Keşif Motoru başlatılıyor...")

    chrome_options = Options()
    termux_chromium = "/data/data/com.termux/files/usr/bin/chromium-browser"
    termux_driver = "/data/data/com.termux/files/usr/bin/chromedriver"

    if os.path.exists(termux_chromium):
        chrome_options.binary_location = termux_chromium
        log_info(f"Termux Chromium bulundu: {termux_chromium}")

    user_data_dir = os.path.abspath(os.path.expanduser(args.profile_dir))
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    log_info(f"Tarayıcı profili: {user_data_dir}")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1400,900")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    if args.headless:
        chrome_options.add_argument("--headless=new")

    # CDP Performans ve Network loglarını etkinleştir
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL', 'browser': 'ALL'})

    service = None
    if os.path.exists(termux_driver):
        service = Service(executable_path=termux_driver)

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options) if service else webdriver.Chrome(options=chrome_options)
    except Exception as e:
        log_error(f"Chromium başlatılamadı: {e}")
        return False

    try:
        # CDP Network dinlemeyi aktif et
        driver.execute_cdp_cmd("Network.enable", {})

        # Sayfa her yüklendiğinde JavaScript API casusunu otomatik enjekte et
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": INJECTED_JS_SPY
        })

        log_info(f"UYAP Avukat Portalı açılıyor: {args.url}")
        driver.get(args.url)

        # 1. Oturum Giriş Bekleme Döngüsü
        print("\n" + "="*70)
        print(f"{Colors.BOLD}{Colors.YELLOW}👉 LÜTFEN E-İMZA, MOBİL İMZA VEYA E-DEVLET İLE GİRİŞ YAPIN.{Colors.ENDC}")
        print("Sistem, giriş tamamlanıp ana portal ekranı açılana kadar beklemektedir...")
        print("="*70 + "\n")

        login_success = False
        start_wait = time.time()
        timeout = args.timeout
        last_heartbeat = 0

        while time.time() - start_wait < timeout:
            try:
                current_url = driver.current_url
                page_title = driver.title
            except Exception:
                current_url = ""
                page_title = ""

            now = time.time()
            if now - last_heartbeat >= 10:
                elapsed = int(now - start_wait)
                log_info(f"⏳ Giriş bekleniyor... ({elapsed}/{timeout} sn) - URL: {current_url[:60]}")
                last_heartbeat = now

            # Giriş sayfası kontrolü (giris veya login sayfası kesinlikle dashboard DEĞİLDİR)
            is_login_page = any(k in current_url.lower() for k in ["giris", "login", "signin"])

            is_dashboard = False
            has_dashboard_element = False

            if not is_login_page:
                is_dashboard = (
                    ("avukat.uyap.gov.tr" in current_url and "#/" in current_url and "giris" not in current_url.lower()) or
                    ("avukat.uyap.gov.tr/main" in current_url) or
                    ("avukat.uyap.gov.tr/portal" in current_url) or
                    ("dava" in current_url.lower())
                )

                try:
                    found = driver.execute_script("""
                        const bodyText = (document.body && document.body.innerText) || '';
                        const hasKeywords = bodyText.includes('Güvenli Çıkış') || 
                                            bodyText.includes('Çıkış Yap') ||
                                            bodyText.includes('Dava Dosyalarım') ||
                                            bodyText.includes('Duruşma Takvimi') ||
                                            bodyText.includes('Tebligat İşlemleri') ||
                                            bodyText.includes('Dosya Sorgulama');
                        const hasLogoutBtn = !!(document.querySelector('button[title*="Çıkış"]') || document.querySelector('a[href*="logout"]'));
                        return hasKeywords || hasLogoutBtn;
                    """)
                    if found:
                        has_dashboard_element = True
                except Exception:
                    pass

            if is_dashboard or has_dashboard_element:
                login_success = True
                log_success(f"🎉 Giriş başarıyla algılandı! Mevcut URL: {current_url}")
                log_info(f"Sayfa Başlığı: {page_title}")
                break

            time.sleep(2)

        if not login_success:
            log_warn("Zaman aşımı süresi doldu ancak oturum tespit edilemedi.")
            proceed = True
            if sys.stdin.isatty():
                try:
                    import select
                    print(f"{Colors.YELLOW}👉 10 saniye içinde 'H' yazılmazsa mevcut ekran taranmaya başlanacaktır (Devam: E / İptal: H): {Colors.ENDC}", end="", flush=True)
                    rlist, _, _ = select.select([sys.stdin], [], [], 10)
                    if rlist:
                        ans = sys.stdin.readline().strip().lower()
                        if ans in ['h', 'hayir', 'hayır', 'n', 'no']:
                            proceed = False
                    else:
                        print("\n[BİLGİ] Zaman aşımı: Mevcut sayfa taranmaya başlanıyor...")
                except Exception:
                    pass

            if not proceed:
                log_info("Kullanıcı tarafından iptal edildi.")
                driver.quit()
                return False

        # Sayfaya JS casusunu canlı olarak da bas
        try:
            driver.execute_script(INJECTED_JS_SPY)
        except Exception:
            pass

        # 2. Menü Keşfi ve Gezinme Motoru
        time.sleep(3)
        poll_and_collect_selenium_logs(driver, blueprint)

        if args.auto_crawl:
            log_info("Sol menü elemanları taranıyor ve otomatik tıklanıyor...")
            perform_selenium_menu_crawl(driver, blueprint)

        # 3. Etkileşimli (Serbest Gezinme) Modu
        if args.interactive and sys.stdin.isatty():
            print("\n" + "="*70)
            print(f"{Colors.BOLD}{Colors.CYAN}🎯 ETKİLEŞİMLİ KEŞİF MODU AKTİF!{Colors.ENDC}")
            print("Tarayıcı üzerinden istediğiniz dosyalara, duruşmalara veya menülere tıklayabilirsiniz.")
            print("Tüm API istekleri canlı olarak dinlenmektedir.")
            print("Keşfi tamamlayıp rapor üretmek için terminalde [ENTER] tuşuna basın.")
            print("="*70 + "\n")

            try:
                import select
                while True:
                    poll_and_collect_selenium_logs(driver, blueprint)
                    if sys.stdin in select.select([sys.stdin], [], [], 1.5)[0]:
                        line = sys.stdin.readline()
                        break
            except Exception:
                try:
                    poll_and_collect_selenium_logs(driver, blueprint)
                    input(f"{Colors.BOLD}Keşfi bitirmek için [ENTER] tuşuna basın...{Colors.ENDC}")
                    poll_and_collect_selenium_logs(driver, blueprint)
                except (EOFError, KeyboardInterrupt):
                    pass
        elif not sys.stdin.isatty():
            log_info("Non-interactive mod: Bekleme süresi sonlandırılıyor...")
            time.sleep(2)
            poll_and_collect_selenium_logs(driver, blueprint)

        # Son logları da topla
        poll_and_collect_selenium_logs(driver, blueprint)
        log_success(f"Keşif tamamlandı! Toplam yakalanan istek sayısı: {len(blueprint.raw_records)}")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return True

def poll_and_collect_selenium_logs(driver, blueprint: BlueprintBuilder):
    """Hem window.__UYAP_CAPTURED_REQUESTS__ hem de CDP get_log üzerinden API çağrılarını çeker."""
    try:
        # 1. Enjekte edilen JavaScript casusundan kayıtları al
        captured = driver.execute_script("return window.__UYAP_CAPTURED_REQUESTS__.splice(0, window.__UYAP_CAPTURED_REQUESTS__.length);")
        if captured:
            for item in captured:
                blueprint.add_call(item)
                log_api(item.get("method", "GET"), item.get("url", ""), item.get("status"))
    except Exception:
        pass

    # 2. CDP Performance loglarını tara
    try:
        logs = driver.get_log('performance')
        for entry in logs:
            try:
                msg = json.loads(entry['message'])['message']
                method = msg.get('method')

                if method == 'Network.responseReceived':
                    resp = msg['params']['response']
                    url = resp.get('url', '')
                    mime = resp.get('mimeType', '')
                    # Sadece JSON / XHR API isteklerine odaklan
                    if 'application/json' in mime or '/api/' in url or '/service/' in url or '/rest/' in url:
                        req_id = msg['params']['requestId']
                        body_txt = None
                        try:
                            cdp_res = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': req_id})
                            body_txt = cdp_res.get('body')
                            parsed_body = json.loads(body_txt)
                        except Exception:
                            parsed_body = body_txt

                        record = {
                            "type": "cdp",
                            "url": url,
                            "method": resp.get("requestHeaders", {}).get(":method", "GET"),
                            "requestHeaders": resp.get("requestHeaders", {}),
                            "requestPayload": None,
                            "status": resp.get("status", 200),
                            "responseBody": parsed_body,
                            "timestamp": datetime.now().isoformat(),
                            "menuContext": "CDP Yakalama"
                        }
                        blueprint.add_call(record)
                        log_api(record["method"], url, record["status"])
            except Exception:
                continue
    except Exception:
        pass

def perform_selenium_menu_crawl(driver, blueprint: BlueprintBuilder):
    """Angular menüsünü tarayıp ana başlıklara kontrollü tıklar."""
    try:
        from selenium.webdriver.common.by import By
    except ImportError:
        return

    # Olası Angular menü seçicileri
    menu_selectors = [
        "nav a", ".sidebar a", ".menu a", "app-sidebar a", "app-menu a", 
        "mat-sidenav a", "p-panelmenu a", ".mat-list-item", ".menu-item",
        "nav button", ".sidebar button", ".nav-link"
    ]

    found_elements = []
    for sel in menu_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                try:
                    txt = el.text.strip()
                    if txt and len(txt) > 2 and el.is_displayed():
                        found_elements.append((txt, el))
                except Exception:
                    continue
        except Exception:
            continue

    # Tekil menü başlıkları
    seen_texts = set()
    targets = []
    for txt, el in found_elements:
        if txt not in seen_texts:
            seen_texts.add(txt)
            targets.append((txt, el))

    log_info(f"Tespit edilen aktif menü başlığı sayısı: {len(targets)}")

    for txt, el in targets[:15]: # İlk 15 ana menüyü gez
        try:
            log_info(f"Menüye tıklanıyor: '{txt}'")
            driver.execute_script("window.__UYAP_CURRENT_MENU__ = arguments[0];", txt)
            try:
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el)
                time.sleep(0.5)
            except Exception:
                pass

            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)

            time.sleep(2.5) # Angular yüklenmesi ve API yanıtı için bekle
            poll_and_collect_selenium_logs(driver, blueprint)
        except Exception as e:
            continue


# ======================================================================================
# 5. MOTOR 2: PLAYWRIGHT (ASYNC PYTHON - MASAÜSTÜ MOTORU)
# ======================================================================================

async def run_playwright_crawler(args, blueprint: BlueprintBuilder):
    """Masaüstü (MacBook, Linux, Windows) için Playwright tabanlı asenkron motor."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log_error("Playwright kütüphanesi bulunamadı! 'pip install playwright && playwright install chromium' çalıştırın.")
        return False

    log_info("Playwright Keşif Motoru başlatılıyor...")
    user_data_dir = os.path.abspath(os.path.expanduser(args.profile_dir))
    os.makedirs(user_data_dir, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=args.headless,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        current_menu_name = ["Giriş / Başlangıç"]

        # Network dinleyicisi
        async def handle_response(response):
            try:
                req = response.request
                url = req.url
                # Statik varlıkları ele
                if re.search(r"\.(js|css|woff2?|ttf|png|jpe?g|gif|svg|ico)(\?.*)?$", url, re.I):
                    return

                # XHR, Fetch veya JSON istekleri
                if req.resource_type in ["xhr", "fetch"] or "json" in response.headers.get("content-type", ""):
                    method = req.method
                    headers = await req.all_headers()
                    post_data = req.post_data

                    parsed_payload = None
                    if post_data:
                        try:
                            parsed_payload = json.loads(post_data)
                        except Exception:
                            parsed_payload = post_data

                    parsed_response = None
                    try:
                        parsed_response = await response.json()
                    except Exception:
                        try:
                            txt = await response.text()
                            parsed_response = txt[:2000] if len(txt) > 2000 else txt
                        except Exception:
                            pass

                    record = {
                        "type": "playwright",
                        "url": url,
                        "method": method,
                        "requestHeaders": headers,
                        "requestPayload": parsed_payload,
                        "status": response.status,
                        "responseBody": parsed_response,
                        "timestamp": datetime.now().isoformat(),
                        "menuContext": current_menu_name[0]
                    }
                    blueprint.add_call(record)
                    log_api(method, url, response.status)
            except Exception:
                pass

        page.on("response", handle_response)

        log_info(f"UYAP Avukat Portalı açılıyor: {args.url}")
        await page.goto(args.url)

        print("\n" + "="*70)
        print(f"{Colors.BOLD}{Colors.YELLOW}👉 LÜTFEN E-İMZA, MOBİL İMZA VEYA E-DEVLET İLE GİRİŞ YAPIN.{Colors.ENDC}")
        print("Sistem, giriş tamamlanıp ana portal ekranı açılana kadar beklemektedir...")
        print("="*70 + "\n")

        # Oturum kontrol döngüsü
        start_wait = time.time()
        login_success = False

        while time.time() - start_wait < args.timeout:
            url = page.url
            if ("avukat.uyap.gov.tr" in url and "#" in url) or ("avukat.uyap.gov.tr/main" in url):
                login_success = True
                log_success(f"Giriş başarıyla algılandı! Mevcut URL: {url}")
                break
            await page.wait_for_timeout(2000)

        if not login_success:
            log_warn("Zaman aşımı süresi doldu ancak oturum tespit edilemedi.")

        # Menü Gezinme
        if args.auto_crawl:
            log_info("Sol menü elemanları taranıyor...")
            menu_selectors = ["nav a", ".sidebar a", "app-sidebar a", ".menu a", "p-panelmenu a"]
            for sel in menu_selectors:
                try:
                    elements = await page.query_selector_all(sel)
                    for el in elements[:15]:
                        try:
                            txt = (await el.inner_text()).strip()
                            if txt and len(txt) > 2:
                                current_menu_name[0] = txt
                                log_info(f"Menüye tıklanıyor: '{txt}'")
                                await el.click(timeout=3000)
                                await page.wait_for_timeout(2500)
                        except Exception:
                            continue
                except Exception:
                    continue

        if args.interactive:
            print("\n" + "="*70)
            print(f"{Colors.BOLD}{Colors.CYAN}🎯 ETKİLEŞİMLİ KEŞİF MODU AKTİF!{Colors.ENDC}")
            print("Tarayıcıda dilediğiniz gibi gezinin. Tamamlayınca terminalde [ENTER] tuşuna basın.")
            print("="*70 + "\n")
            try:
                import asyncio
                # Enter bekle
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, input, "Keşfi bitirmek için [ENTER] tuşuna basın...")
            except Exception:
                await page.wait_for_timeout(10000)

        await context.close()
        return True


# ======================================================================================
# 6. ANA YÖNETİCİ & ÇALIŞTIRICI
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(
        description="⚖️ UYAP Avukat Portalı - Reverse Engineering & API Keşif Motoru (Faz 1)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--engine",
        choices=["auto", "selenium", "playwright"],
        default="auto",
        help="Kullanılacak tarayıcı motoru (auto: ortama göre otomatik seçer)"
    )
    parser.add_argument(
        "--url",
        default="https://avukat.uyap.gov.tr",
        help="Başlangıç adresi (varsayılan: https://avukat.uyap.gov.tr)"
    )
    parser.add_argument(
        "--profile-dir",
        default="~/.uyap_crawler_profile",
        help="Oturum çerezlerinin saklanacağı tarayıcı profil dizini"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Giriş yapılması için beklenecek maksimum saniye (varsayılan: 300 sn)"
    )
    parser.add_argument(
        "--auto-crawl",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Giriş yapıldıktan sonra menüleri otomatik tıkla"
    )
    parser.add_argument(
        "--interactive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Otomatik tarama sonrası kullanıcının serbestçe gezinmesine izin ver"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Tarayıcıyı başlıksız (ekransız) modda aç"
    )
    parser.add_argument(
        "--output-json",
        default="uyap_api_blueprint.json",
        help="Çıktı JSON blueprint dosya yolu"
    )
    parser.add_argument(
        "--output-docs",
        default="API_DOCS.md",
        help="Çıktı Markdown dokümantasyon dosya yolu"
    )

    args = parser.parse_args()

    print("\n" + "="*75)
    print(f"{Colors.BOLD}{Colors.HEADER}⚖️  UYAP AVUKAT PORTALI - API KEŞİF & TRAFİK YAKALAMA MOTORU (FAZ 1){Colors.ENDC}")
    print("="*75)
    log_info(f"Hedef Portal: {args.url}")
    log_info(f"Blueprint Çıktısı: {args.output_json}")
    log_info(f"Doküman Çıktısı: {args.output_docs}")

    # Motor seçimi
    engine = args.engine
    if engine == "auto":
        # Termux kontrolü
        is_termux = os.path.exists("/data/data/com.termux") or "TERMUX_VERSION" in os.environ
        if is_termux:
            log_info("Termux Android ortamı algılandı -> Selenium + Chromium + CDP motoru seçildi.")
            engine = "selenium"
        else:
            try:
                import playwright
                log_info("Playwright algılandı -> Playwright motoru seçildi.")
                engine = "playwright"
            except ImportError:
                log_info("Playwright bulunamadı -> Selenium motoru seçildi.")
                engine = "selenium"

    blueprint = BlueprintBuilder(base_url=args.url)

    success = False
    if engine == "selenium":
        success = run_selenium_crawler(args, blueprint)
    elif engine == "playwright":
        import asyncio
        success = asyncio.run(run_playwright_crawler(args, blueprint))

    # Sonuçları kaydet
    if len(blueprint.endpoints) > 0 or len(blueprint.raw_records) > 0:
        print("\n" + "="*75)
        log_info("Raporlar ve veri şemaları dosyaya yazılıyor...")
        blueprint.export_blueprint_json(args.output_json)
        blueprint.export_api_docs_md(args.output_docs)
        print("="*75)
        log_success("✅ FAZ 1 BAŞARIYLA TAMAMLANDI!")
        print(f"👉 JSON Şeması: {os.path.abspath(args.output_json)}")
        print(f"👉 API Dokümanı: {os.path.abspath(args.output_docs)}")
        print("="*75 + "\n")
    else:
        log_warn("Hiçbir API çağrısı yakalanamadı. Lütfen oturum açıldığından ve sayfanın yüklendiğinden emin olun.")

if __name__ == "__main__":
    main()
