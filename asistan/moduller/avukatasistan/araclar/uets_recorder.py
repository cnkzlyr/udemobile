#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🕵️ UETS EYLEM KAYDEDİCİ & DOM DEDEKTİFİ (UETS ACTION RECORDER)
Bu script, UETS portalında yaptığınız işlemleri (tıklamalar, butonlar, linkler,
CSS/XPath seçicileri ve indirilen dosyaları) anlık olarak kaydeder.
Ayrıca Downloads klasörüne düşen doğrulama kodlarını (.eml) anında ekrana basar.
"""

import os
import sys
import time
import json
import glob
import re
import email
from email import policy
from datetime import datetime

# Proje dizinlerini dahil et
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # proje kökü
from config import _detect_download_dirs

def get_target_download_dir():
    dirs = _detect_download_dirs()
    for d in dirs:
        if os.path.exists(d):
            return d
    return os.path.expanduser("~/Downloads")

def check_latest_otp_code(download_dirs):
    """İndirilenler klasöründeki en güncel .eml dosyasından UETS doğrulama kodunu okur."""
    eml_files = []
    for d in download_dirs:
        if os.path.exists(d):
            eml_files.extend(glob.glob(os.path.join(d, "**", "*.eml"), recursive=True))
            eml_files.extend(glob.glob(os.path.join(d, "*.eml")))
            
    if not eml_files:
        return None
        
    eml_files = list(set(eml_files))
    eml_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest_eml = eml_files[0]
    
    # Son 10 dakika içinde mi gelmiş?
    if time.time() - os.path.getmtime(latest_eml) > 600:
        return None
        
    try:
        with open(latest_eml, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)
        body = msg.get_body(preferencelist=("html", "plain"))
        if body:
            content = body.get_content()
            m = re.search(r"Sayin [^,]+,\s*(\d{6})\s*kodunu", content, re.IGNORECASE) or \
                re.search(r"\b(\d{6})\b\s*kodunu", content, re.IGNORECASE) or \
                re.search(r"(?:Doğrulama Kodu)[^\d]*(\d{6})", content, re.IGNORECASE)
            if m:
                return m.group(1), os.path.basename(latest_eml)
    except Exception:
        pass
    return None

INJECTION_JS = """
if (!window.__recorder_attached) {
    window.__recorder_attached = true;
    window.__recorded_events = [];

    function getXPath(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return `//*[@id="${el.id}"]`;
        let sameTagSiblings = 0;
        let index = 1;
        let sib = el.previousElementSibling;
        while (sib) {
            if (sib.tagName === el.tagName) index++;
            sib = sib.previousElementSibling;
        }
        const parentPath = el.parentElement ? getXPath(el.parentElement) : '';
        return `${parentPath}/${el.tagName.toLowerCase()}[${index}]`;
    }

    function getCssSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return `#${el.id}`;
        let tag = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c && !c.includes(':') && !c.includes('/')).join('.');
            if (classes) return `${tag}.${classes}`;
        }
        return tag;
    }

    document.addEventListener('click', function(e) {
        let target = e.target;
        if (!target) return;
        
        // Eğer tıklanan eleman bir ikon veya span ise en yakın buton veya linki de yakala
        let clickableParent = target.closest('button, a, tr, [role="button"]');
        
        let el = clickableParent || target;

        let eventData = {
            type: 'click',
            time: new Date().toLocaleTimeString(),
            url: window.location.href,
            tagName: el.tagName,
            id: el.id || '',
            className: typeof el.className === 'string' ? el.className : '',
            innerText: (el.innerText || '').slice(0, 120).trim(),
            href: el.href || el.getAttribute('href') || '',
            title: el.title || el.getAttribute('title') || '',
            name: el.name || el.getAttribute('name') || '',
            role: el.getAttribute('role') || '',
            xpath: getXPath(el),
            cssSelector: getCssSelector(el),
            outerHTML: (el.outerHTML || '').slice(0, 250)
        };
        
        window.__recorded_events.push(eventData);
    }, true);
}
"""

def run_recorder():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    dl_dir = get_target_download_dir()
    all_dl_dirs = _detect_download_dirs()

    print("\n" + "="*70)
    print("🕵️  UETS EYLEM KAYDEDİCİ & DOM DEDEKTİFİ BAŞLATILIYOR")
    print("="*70)
    print(f"📁 Taranan İndirme Klasörü: {dl_dir}")
    print("💡 Talimat:")
    print("   1. Açılan tarayıcı penceresinden UETS'ye giriş yapın.")
    print("   2. (E-posta ile kod gelirse sistem Downloads klasöründen yakalayacaktır).")
    print("   3. Gelen Kutusuna gidin, 'Tebligatlar CSV' dışa aktar butonuna basın.")
    print("   4. Son 10 tebligatın EYP paketlerini indirin.")
    print("   5. İşiniz bittiğinde BU TERMİNALDE Enter'a basın (veya Ctrl+C yapın).")
    print("="*70 + "\n")

    chrome_options = Options()
    prefs = {
        "download.default_directory": dl_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    user_data_dir = os.path.expanduser("~/.uets_browser_profile")
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1600,1000")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    termux_chromium = "/data/data/com.termux/files/usr/bin/chromium-browser"
    termux_driver = "/data/data/com.termux/files/usr/bin/chromedriver"

    service = None
    if os.path.exists(termux_chromium):
        chrome_options.binary_location = termux_chromium
    if os.path.exists(termux_driver):
        service = Service(executable_path=termux_driver)

    if service:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    # Başlangıç dosyaları listesi (yeni inenleri tespit etmek için)
    initial_files = set(glob.glob(os.path.join(dl_dir, "*")))
    last_known_otp = None
    all_recorded_events = []
    downloaded_files_log = []

    try:
        driver.get("https://portal.etebligat.gov.tr")
        print("🌐 UETS Portalı Açıldı (https://portal.etebligat.gov.tr)")
        print("👀 Tıklamalarınız anlık olarak izleniyor ve kaydediliyor...\n")

        last_url = driver.current_url

        while True:
            # 1. URL Değişimi Kontrolü
            try:
                cur_url = driver.current_url
                if cur_url != last_url:
                    last_url = cur_url
                    print(f"\n📍 [SAYFA DEĞİŞTİ]: {cur_url}")
            except Exception:
                pass

            # 2. JavaScript Dinleyicisini Enjekte Et
            try:
                driver.execute_script(INJECTION_JS)
                # Olayları Çek
                events = driver.execute_script("""
                    if (!window.__recorded_events) return [];
                    const ev = window.__recorded_events;
                    window.__recorded_events = [];
                    return ev;
                """)
                for ev in events:
                    all_recorded_events.append(ev)
                    print(f"🖱️  [TIKLAMA {len(all_recorded_events)}]: <{ev['tagName']}> \"{ev['innerText']}\"")
                    if ev['id']:
                        print(f"   ↳ ID: #{ev['id']}")
                    if ev['className']:
                        print(f"   ↳ Sınıf: .{ev['className']}")
                    print(f"   ↳ CSS: {ev['cssSelector']}")
                    print(f"   ↳ XPath: {ev['xpath']}")
                    if ev['href']:
                        print(f"   ↳ Link: {ev['href']}")
                    print("-" * 50)
            except Exception:
                pass

            # 3. İndirilen Yeni Dosyaları İzle
            current_files = set(glob.glob(os.path.join(dl_dir, "*")))
            new_files = current_files - initial_files
            for nf in new_files:
                if not nf.endswith(".crdownload") and not nf.endswith(".tmp"):
                    initial_files.add(nf)
                    bname = os.path.basename(nf)
                    sz = os.path.getsize(nf) if os.path.exists(nf) else 0
                    print(f"📥 [YENİ DOSYA İNDİRİLDİ]: {bname} ({sz / 1024:.1f} KB)")
                    downloaded_files_log.append({
                        "file": bname,
                        "path": nf,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "last_click_event": len(all_recorded_events)
                    })

            # 4. Doğrulama Kodu (.eml) Kontrolü
            otp_res = check_latest_otp_code(all_dl_dirs)
            if otp_res:
                code, eml_name = otp_res
                if code != last_known_otp:
                    last_known_otp = code
                    print("\n" + "🔥"*25)
                    print(f"🔑 [UETS DOĞRULAMA KODU BULUNDU]: {code}")
                    print(f"📄 Kaynak E-Posta: {eml_name}")
                    print("🔥"*25 + "\n")

            time.sleep(0.5)

    except (KeyboardInterrupt, Exception) as e:
        print(f"\n🛑 Kayıt oturumu sonlandırılıyor... ({e})")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    # Raporları Kaydet
    output_json = os.path.join(os.path.dirname(__file__), "uets_kayit_raporu.json")
    output_txt = os.path.join(os.path.dirname(__file__), "uets_kayit_raporu.txt")

    report_data = {
        "recorded_at": datetime.now().isoformat(),
        "total_clicks": len(all_recorded_events),
        "downloaded_files": downloaded_files_log,
        "clicks": all_recorded_events
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("="*70 + "\n")
        f.write("📋 UETS KAYIT ÖZET RAPORU\n")
        f.write("="*70 + "\n\n")
        f.write(f"Toplam Tıklama: {len(all_recorded_events)}\n")
        f.write(f"İndirilen Dosyalar ({len(downloaded_files_log)} adet):\n")
        for df in downloaded_files_log:
            f.write(f"  - [{df['time']}] {df['file']} (Tıklama #{df['last_click_event']} sonrası)\n")
        f.write("\n" + "="*70 + "\n")
        f.write("TIKLANAN ELEMANLAR VE SEÇİCİLER:\n")
        f.write("="*70 + "\n")
        for i, c in enumerate(all_recorded_events, 1):
            f.write(f"\n[{i}] {c['time']} - <{c['tagName']}> \"{c['innerText']}\"\n")
            f.write(f"    URL: {c['url']}\n")
            if c['id']: f.write(f"    ID: #{c['id']}\n")
            f.write(f"    CSS: {c['cssSelector']}\n")
            f.write(f"    XPath: {c['xpath']}\n")
            if c['href']: f.write(f"    Href: {c['href']}\n")
            f.write(f"    HTML: {c['outerHTML'][:120]}...\n")

    print("\n" + "="*70)
    print("🎉 KAYIT BAŞARIYLA TAMAMLANDI!")
    print(f"📊 Toplam Tıklama Sayısı: {len(all_recorded_events)}")
    print(f"📥 İndirilen Dosya Sayısı: {len(downloaded_files_log)}")
    print(f"📄 JSON Raporu: {output_json}")
    print(f"📄 Okunabilir Özet Rapor: {output_txt}")
    print("="*70)
    print("👉 Şimdi bu raporu bana gönderin veya dosyayı okuyalım, scripti kusursuz yapalım!")

if __name__ == "__main__":
    run_recorder()
