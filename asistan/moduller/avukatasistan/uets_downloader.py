#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 UETS OTOMATİK İNDİRİCİ (SELENIUM BOT - NİHAİ SÜRÜM)
UETS (Ulusal Elektronik Tebligat Sistemi - ptt.etebligat.gov.tr) portalına bağlanır,
doğrulama kodunu (.eml) otomatik yakalar/doldurur, gelen kutusundaki tebligatlar CSV'sini
ve son N adet tebligatın .eyp paketlerini kusursuz şekilde İndirilenler klasörüne indirir.
"""

import os
import sys
import time
import glob
import re
import base64
import email
from email import policy
import email.utils
import datetime
import imaplib
import argparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG, PROJECT_IDS, _detect_download_dirs
import uets_tani as tani

# Portal adresi (testlerde sahte sunucuya yönlendirmek için ortam değişkeniyle değiştirilebilir)
PORTAL = os.environ.get("UETS_PORTAL_URL", "https://ptt.etebligat.gov.tr").rstrip("/")

def download_blob_via_js(driver, blob_url, target_path):
    """
    Tarayıcıdaki bir blob: URL'sini JavaScript FileReader ile Base64'e çevirip diske doğrudan yazar.
    Chrome'un indirme yöneticisi veya ağ hatası olsa bile %100 çalışır!
    """
    js = """
    var blobUrl = arguments[0];
    var callback = arguments[1];
    fetch(blobUrl)
        .then(response => response.blob())
        .then(blob => {
            var reader = new FileReader();
            reader.onloadend = function() {
                callback(reader.result);
            };
            reader.readAsDataURL(blob);
        })
        .catch(err => callback(null));
    """
    try:
        base64_data = driver.execute_async_script(js, blob_url)
        if base64_data and "," in base64_data:
            b64_content = base64_data.split(",")[1]
            file_bytes = base64.b64decode(b64_content)
            with open(target_path, "wb") as f:
                f.write(file_bytes)
            print(f"      💾 Blob doğrudan diske kaydedildi: {os.path.basename(target_path)} ({len(file_bytes)} bayt)")
            return True
    except Exception as e:
        print(f"   ⚠️ Blob JS indirme hatası: {e}")
    return False

def get_target_download_dir():
    dirs = _detect_download_dirs()
    for d in dirs:
        if os.path.exists(d):
            return d
    fallback = os.path.expanduser("~/Downloads")
    os.makedirs(fallback, exist_ok=True)
    return fallback

def get_latest_gmail_msg_id():
    """Giriş yapılmadan önce mevcut son e-posta ID'sini tespit eder."""
    gmail_user = CONFIG.get("GMAIL_USER")
    gmail_pass = CONFIG.get("GMAIL_APP_PASS")
    if not gmail_user or not gmail_pass:
        return 0
    clean_pass = str(gmail_pass).replace(" ", "").strip()
    label_name = CONFIG.get("GMAIL_UETS_LABEL", '"UETS Giris&Ayc- Kodu"')
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)
        mail.login(gmail_user, clean_pass)
        status, _ = mail.select(label_name)
        if status != "OK":
            mail.select("INBOX")
        _, data = mail.search(None, "ALL")
        mail.logout()
        ids = data[0].split()
        return int(ids[-1]) if ids else 0
    except Exception:
        return 0

def fetch_otp_from_gmail(since_msg_id=0, max_age_seconds=120):
    """
    Gmail IMAP üzerinden 'UETS Giriş Kodu' etiketindeki veya gelen kutusundaki
    yeni UETS doğrulama e-postasını okuyup 6 haneli kodu çeker.
    Eğer since_msg_id verilmişse, sadece bu ID'den daha sonra gelen e-postaları kabul eder.
    """
    gmail_user = CONFIG.get("GMAIL_USER")
    gmail_pass = CONFIG.get("GMAIL_APP_PASS")
    if not gmail_user or not gmail_pass:
        return None
    
    clean_pass = str(gmail_pass).replace(" ", "").strip()
    label_name = CONFIG.get("GMAIL_UETS_LABEL", '"UETS Giris&Ayc- Kodu"')

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=12)
        mail.login(gmail_user, clean_pass)
        
        status, _ = mail.select(label_name)
        if status != "OK":
            status, _ = mail.select("INBOX")
        
        if status != "OK":
            mail.logout()
            return None

        status, data = mail.search(None, "ALL")
        if status != "OK" or not data[0]:
            mail.logout()
            return None

        msg_ids = data[0].split()
        if not msg_ids:
            mail.logout()
            return None

        # En son e-postalardan geriye doğru tara
        for msg_id in reversed(msg_ids[-5:]):
            mid_int = int(msg_id)
            if since_msg_id > 0 and mid_int <= since_msg_id:
                continue

            res, msg_data = mail.fetch(msg_id, "(RFC822)")
            if res != "OK" or not msg_data:
                continue
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email, policy=policy.default)
            
            # Tarih tazelik kontrolü
            try:
                date_str = msg.get("date")
                if date_str:
                    msg_dt = email.utils.parsedate_to_datetime(date_str)
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    age = (now_utc - msg_dt.astimezone(datetime.timezone.utc)).total_seconds()
                    if age > max_age_seconds:
                        continue
            except Exception:
                pass

            body = msg.get_body(preferencelist=("plain", "html"))
            if body:
                content = body.get_content()
                m = re.search(r"Sayin [^,]+,\s*(\d{6})\s*kodunu", content, re.IGNORECASE) or \
                    re.search(r"\b(\d{6})\b\s*kodunu", content, re.IGNORECASE) or \
                    re.search(r"(?:Doğrulama Kodu)[^\d]*(\d{6})", content, re.IGNORECASE)
                if m:
                    code = m.group(1)
                    mail.logout()
                    return code, f"Gmail ('{label_name.strip('\"')}') - {msg.get('date', '')}"
        mail.logout()
    except Exception:
        pass
    return None

def find_latest_otp_code(since_msg_id=0, wait_seconds=3, poll_timeout=50):
    """
    UETS Doğrulama Kodunu canlı olarak Gmail IMAP üzerinden yakalar;
    bulamazsa İndirilenler klasöründeki yeni .eml dosyalarını kontrol eder.
    """
    if wait_seconds > 0:
        print(f"⏳ Kodun Gmail'e ulaşması için {wait_seconds} sn bekleniyor...")
        time.sleep(wait_seconds)

    print("📬 Gmail ('UETS Giriş Kodu' etiketi) taranıyor...")
    start_t = time.time()
    while time.time() - start_t < poll_timeout:
        res = fetch_otp_from_gmail(since_msg_id=since_msg_id, max_age_seconds=180)
        if res:
            return res
        time.sleep(2.5)

    # İkincil kontrol: İndirilenler klasörüne düşen yeni .eml dosyaları
    dirs = _detect_download_dirs()
    eml_files = []
    for d in dirs:
        if os.path.exists(d):
            eml_files.extend(glob.glob(os.path.join(d, "**", "*.eml"), recursive=True))
            eml_files.extend(glob.glob(os.path.join(d, "*.eml")))

    if eml_files:
        eml_files = list(set(eml_files))
        eml_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        latest_eml = eml_files[0]
        if time.time() - os.path.getmtime(latest_eml) <= 180:
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
                        return m.group(1), f"Yerel Dosya ({os.path.basename(latest_eml)})"
            except Exception:
                pass

    return None

def setup_driver(headless=False, user_data_dir=None):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service

    # Termux / Android ortamında GUI (X11) yoksa zorunlu headless çalış
    is_termux = os.path.exists("/data/data/com.termux")
    has_display = bool(os.environ.get("DISPLAY"))
    if is_termux and not has_display:
        headless = True

    chrome_options = Options()
    tani.chrome_secenekleri(chrome_options)
    dl_dir = os.path.normpath(os.path.abspath(get_target_download_dir()))
    os.makedirs(dl_dir, exist_ok=True)

    prefs = {
        "download.default_directory": dl_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": False,
        "safebrowsing.disable_download_protection": True,
        "profile.default_content_settings.popups": 0,
        "profile.default_content_setting_values.automatic_downloads": 1,
        "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
        "plugins.always_open_pdf_externally": True
    }
    chrome_options.add_experimental_option("prefs", prefs)

    if not user_data_dir:
        user_data_dir = os.path.normpath(os.path.abspath(os.path.expanduser("~/.uets_browser_profile")))
    os.makedirs(user_data_dir, exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    if headless:
        chrome_options.add_argument("--headless=new")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1600,1000")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-features=InsecureDownloadWarnings")

    termux_chromium = os.environ.get("UETS_CHROME_BIN", "/data/data/com.termux/files/usr/bin/chromium-browser")
    termux_driver = os.environ.get("UETS_CHROMEDRIVER", "/data/data/com.termux/files/usr/bin/chromedriver")

    service = None
    if os.path.exists(termux_chromium):
        chrome_options.binary_location = termux_chromium
    if os.path.exists(termux_driver):
        service = Service(executable_path=termux_driver)

    if service:
        driver = webdriver.Chrome(service=service, options=chrome_options)
    else:
        driver = webdriver.Chrome(options=chrome_options)

    # Browser ve Page seviyesinde CDP indirme izni
    for cmd in ["Browser.setDownloadBehavior", "Page.setDownloadBehavior"]:
        try:
            driver.execute_cdp_cmd(cmd, {
                "behavior": "allow",
                "downloadPath": dl_dir,
                "eventsEnabled": True
            })
        except Exception:
            try:
                driver.execute_cdp_cmd(cmd, {
                    "behavior": "allow",
                    "downloadPath": dl_dir
                })
            except Exception:
                pass

    return driver

def wait_for_file_download(download_dir, before_files, start_time=None, timeout=30, extension=None):
    """
    İndirme klasörüne yeni bir dosyanın düşmesini veya var olan dosyanın güncellenmesini
    ve .crdownload/.tmp gibi geçici dosyaların tamamlanmasını güvenle bekler.
    """
    if start_time is None:
        start_time = time.time()
    time.sleep(1)
    while time.time() - start_time < timeout:
        in_progress = glob.glob(os.path.join(download_dir, "*.crdownload")) + \
                      glob.glob(os.path.join(download_dir, "*.part")) + \
                      glob.glob(os.path.join(download_dir, "*.tmp"))
        
        current_files = set(os.listdir(download_dir))
        # 1. Yeni eklenen dosyalar
        candidates = set(current_files - before_files)
        
        # 2. Üzerine yazılan / start_time'dan hemen önce veya sonra değiştirilen dosyalar
        for f in current_files:
            fp = os.path.join(download_dir, f)
            if os.path.isfile(fp):
                try:
                    if os.path.getmtime(fp) >= (start_time - 1.5):
                        candidates.add(f)
                except Exception:
                    pass

        completed = [f for f in candidates if not (f.endswith(".crdownload") or f.endswith(".tmp") or f.endswith(".part"))]
        
        if extension:
            completed = [f for f in completed if f.lower().endswith(extension.lower())]

        if completed and not in_progress:
            time.sleep(0.5)
            completed.sort(key=lambda x: os.path.getmtime(os.path.join(download_dir, x)), reverse=True)
            return completed[0]

        time.sleep(1)
    return None

def wait_for_downloads(download_dir, timeout=60):
    start_time = time.time()
    time.sleep(1)
    while time.time() - start_time < timeout:
        in_progress = glob.glob(os.path.join(download_dir, "*.crdownload")) + \
                      glob.glob(os.path.join(download_dir, "*.part")) + \
                      glob.glob(os.path.join(download_dir, "*.tmp"))
        if not in_progress:
            return True
        time.sleep(1)
    return False

def check_missing_tebligatlar_in_ticktick(csv_items, limit=None):
    """
    İndirilen CSV'deki tebligatları TickTick (aktif, tamamlanmış, yapılmayacak) ile karşılaştırır.
    Yalnızca TickTick'te bulunmayan veya eki eksik olan tebligatları (row_idx, item) listesi olarak döndürür.
    """
    from ticktick_sync import find_existing_tebligat_in_completed, find_existing_tebligat_in_active
    from utils import determine_list
    from state_manager import get_barcode_state

    items_to_check = csv_items[:limit] if (limit and limit > 0) else csv_items
    missing = []

    print(f"\n🔍 [AKILLI KONTROL]: İndirilen CSV'deki {len(items_to_check)} adet tebligat TickTick ile doğrulanıyor...")
    for idx, item in enumerate(items_to_check):
        barcode = item.get("barcode")
        court = item.get("court", "")
        esas_no = item.get("esas_no", "")
        deadlines = item.get("deadlines")

        # 1. Tamamlanmış veya yapılmayacak mı? (Tarih ve barkod doğrulamalı)
        comp = find_existing_tebligat_in_completed(barcode, esas_no, court, deadlines=deadlines)
        if comp:
            lbl = "Tamamlandı" if comp.get("status") == 2 else "Yapılmayacak"
            print(f"   🛡️ [{idx+1}/{len(items_to_check)}] {court} [{esas_no}] (Barkod: {barcode}) -> TickTick'te '{lbl}'.")
            continue

        # 2. State cache kontrolü
        b_state = get_barcode_state(barcode) if barcode else {}
        if b_state and b_state.get("task_id"):
            tid = b_state["task_id"]
            pid = b_state.get("project_id", "inbox")
            try:
                r = requests.get(f"{CONFIG['TICKTICK_API_BASE']}/project/{pid}/task/{tid}", headers={"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}"}, timeout=4)
                if r.status_code == 200:
                    t_obj = r.json()
                    if t_obj.get("status", 0) != 0:
                        lbl = "Tamamlandı" if t_obj.get("status") == 2 else "Yapılmayacak"
                        print(f"   🛡️ [{idx+1}/{len(items_to_check)}] {court} [{esas_no}] (Barkod: {barcode}) -> TickTick'te '{lbl}' (Cache).")
                        continue
            except Exception:
                pass

        # 3. Aktif görevlerde var mı ve eki eklenmiş mi?
        list_name = determine_list(court, gonderen=item.get("gonderen", ""))
        pid = PROJECT_IDS.get(list_name) or PROJECT_IDS["Inbox"]
        act, _ = find_existing_tebligat_in_active(barcode, esas_no, court, pid, deadlines=deadlines)
        if act:
            from ticktick_sync import gercek_ek_var
            has_att = gercek_ek_var(act, barcode)
            if has_att:
                print(f"   🛡️ [{idx+1}/{len(items_to_check)}] {court} [{esas_no}] (Barkod: {barcode}) -> TickTick'te mevcut ve eki tam.")
                continue
            else:
                print(f"   📎 [{idx+1}/{len(items_to_check)}] {court} [{esas_no}] (Barkod: {barcode}) -> TickTick'te var ama EYP eki eksik! (İndirilecek)")
                missing.append((idx, item))
                continue

        print(f"   ⭐ [{idx+1}/{len(items_to_check)}] {court} [{esas_no}] (Barkod: {barcode}) -> TickTick'te YENİ/EKSİK! (İndirilecek)")
        missing.append((idx, item))

    return missing

def ensure_messages_table(driver, timeout=25):
    """
    UETS Gelen Kutusu (messages/1) sayfasına dönmeyi ve tablonun
    satırlarıyla birlikte yüklenmesini %100 garanti eder.
    Detay ekranları, modallar, route geçişleri veya dashboard sapmalarını
    kusursuzca telafi eder.
    """
    from selenium.webdriver.common.by import By

    # A. Birden fazla sekme/pencere açıldıysa ana pencere dışındakileri kapat
    if len(driver.window_handles) > 1:
        main_win = driver.window_handles[0]
        for w in driver.window_handles[1:]:
            try:
                driver.switch_to.window(w)
                driver.close()
            except Exception:
                pass
        driver.switch_to.window(main_win)

    # B. Eğer detay ekranındaysak (viewmessages veya URL'de detail varsa)
    cur_url = driver.current_url.lower()
    if "viewmessages" in cur_url or "detail" in cur_url:
        # 1. Kapat veya Geri butonuna tıkla
        close_selectors = [
            "//button[contains(@class, 'btn-secondary') and (contains(., 'Kapat') or contains(., 'Geri'))]",
            "//button[contains(., 'Kapat') or contains(., 'Geri') or contains(., 'Vazgeç')]",
            "//a[contains(@class, 'btn-secondary') and (contains(., 'Kapat') or contains(., 'Geri'))]",
            "//a[contains(., 'Kapat') or contains(., 'Geri')]",
            "//button[@aria-label='Close' or contains(@class, 'close')]",
            "//a[contains(@href, 'messages/1') or contains(@href, '/messages/1')]",
            "//span[contains(text(), 'Gelen')]/ancestor::a"
        ]
        clicked = False
        for xpath in close_selectors:
            btns = driver.find_elements(By.XPATH, xpath)
            for b in btns:
                if b.is_displayed():
                    try:
                        driver.execute_script("arguments[0].click();", b)
                        clicked = True
                        break
                    except Exception:
                        pass
            if clicked:
                break

        time.sleep(1.2)

        # 2. Hala detaydaysa browser back (geri) yap
        if "viewmessages" in driver.current_url.lower() or "detail" in driver.current_url.lower():
            try:
                driver.back()
                time.sleep(1.5)
            except Exception:
                pass

        # 3. Hala dönmediyse doğrudan messages/1 sayfasına git
        if "viewmessages" in driver.current_url.lower() or "detail" in driver.current_url.lower() or "messages" not in driver.current_url.lower():
            driver.get(f"{PORTAL}/messages/1")
            driver._page_size_expanded = False
            time.sleep(2)

    # C. Eğer dashboard'a yönlendiyse Gelen Tebligatlar'a geç
    if "dashboard" in driver.current_url.lower():
        print("   📍 Dashboard algılandı, Gelen Tebligatlar menüsüne yönlendiriliyor...")
        driver._page_size_expanded = False
        menu_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'messages/1')] | //span[contains(text(), 'Gelen')]/ancestor::a")
        if menu_links:
            driver.execute_script("arguments[0].click();", menu_links[0])
        else:
            driver.get(f"{PORTAL}/messages/1")
        time.sleep(2)

    # D. Tablonun Angular tarafından satırlarıyla yüklenmesini bekle
    start_t = time.time()
    while time.time() - start_t < timeout:
        if "dashboard" in driver.current_url.lower():
            menu_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'messages/1')] | //span[contains(text(), 'Gelen')]/ancestor::a")
            if menu_links:
                driver.execute_script("arguments[0].click();", menu_links[0])
            else:
                driver.get(f"{PORTAL}/messages/1")
            time.sleep(2)

        rows = driver.find_elements(By.CSS_SELECTOR, "mat-table mat-row, table.mat-table tbody tr")
        if rows and len(rows) > 0:
            time.sleep(0.5)
            return rows
        time.sleep(1)

    # Son çare: Sayfayı bir kez taze aç
    print("   ⚠️ Tablo satırları beklenenden uzun sürdü, sayfa taze yükleniyor...")
    tani.adim(driver, "tablo-gelmedi-yenilemeden-once")
    driver.get(f"{PORTAL}/messages/1")
    time.sleep(4)
    rows = driver.find_elements(By.CSS_SELECTOR, "mat-table mat-row, table.mat-table tbody tr")
    tani.adim(driver, "tablo-yenilemeden-sonra", ek={"satir": len(rows)})
    return rows

def find_matching_row_with_pagination(driver, b_code, m_esas, max_pages=5):
    """
    UETS tablosunda ilgili satırı Barkod veya Esas No ile arar.
    Mevcut sayfada bulamazsa sonraki sayfaya geçer (mat-paginator-navigation-next).
    Gerekirse ilk sayfaya geri döner.
    """
    from selenium.webdriver.common.by import By

    # Öncelikle sayfa boyutunu 50 veya 100 yapmayı dene (tek sayfada daha çok satır çıksın)
    try:
        page_size_selects = driver.find_elements(By.CSS_SELECTOR, "mat-paginator mat-select, .mat-paginator-page-size-select")
        if page_size_selects and not getattr(driver, "_page_size_expanded", False):
            driver.execute_script("arguments[0].click();", page_size_selects[0])
            time.sleep(0.8)
            options = driver.find_elements(By.CSS_SELECTOR, "mat-option")
            best_opt = None
            max_val = 0
            for opt in options:
                txt = opt.text.strip()
                if txt.isdigit() and int(txt) > max_val:
                    max_val = int(txt)
                    best_opt = opt
            if best_opt:
                driver.execute_script("arguments[0].click();", best_opt)
                time.sleep(1.5)
                driver._page_size_expanded = True
    except Exception:
        pass

    # Sayfaları tara
    for page_num in range(1, max_pages + 1):
        cur_rows = driver.find_elements(By.CSS_SELECTOR, "mat-table mat-row, table.mat-table tbody tr")
        if not cur_rows:
            time.sleep(1)
            cur_rows = driver.find_elements(By.CSS_SELECTOR, "mat-table mat-row, table.mat-table tbody tr")

        for r in cur_rows:
            try:
                row_full = (r.get_attribute("textContent") or "") + " " + (r.get_attribute("innerHTML") or "") + " " + (r.text or "")
                if b_code and str(b_code) in row_full:
                    return r
                if m_esas and str(m_esas) in row_full:
                    return r
            except Exception:
                pass

        # Sonraki sayfa butonuna bak
        next_btns = driver.find_elements(By.CSS_SELECTOR, "button.mat-paginator-navigation-next, button[aria-label*='Next'], button[aria-label*='Sonraki']")
        can_go_next = False
        if next_btns:
            btn = next_btns[0]
            is_disabled = btn.get_attribute("disabled") is not None or "mat-button-disabled" in (btn.get_attribute("class") or "")
            if not is_disabled and btn.is_displayed():
                can_go_next = True
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)

        if not can_go_next:
            break

    # Bulunamadıysa ilk sayfaya geri dönmeyi dene
    try:
        first_btns = driver.find_elements(By.CSS_SELECTOR, "button.mat-paginator-navigation-first, button[aria-label*='First'], button[aria-label*='İlk']")
        if first_btns and first_btns[0].is_enabled():
            driver.execute_script("arguments[0].click();", first_btns[0])
            time.sleep(1.5)
    except Exception:
        pass

    return None

def login_and_download(headless=False, count=None, auto_sync=True, external_driver=None):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    dl_dir = get_target_download_dir()
    print("\n" + "="*70)
    print("🤖  UETS OTOMATİK İNDİRME MOTORU (NİHAİ SÜRÜM)")
    print("="*70)
    print(f"📁 İndirme Klasörü: {dl_dir}")

    tani.basla()
    driver = None
    driver_created = False
    if external_driver is not None:
        driver = external_driver
    else:
        print("🌐 Tarayıcı başlatılıyor...")
        driver = setup_driver(headless=headless)
        driver_created = True

    wait = WebDriverWait(driver, 30)

    try:
        start_url = f"{PORTAL}/messages/1"
        print(f"🔗 UETS Portalına gidiliyor: {start_url}")
        driver.get(start_url)
        time.sleep(3)
        tani.adim(driver, "acilis")

        # 1. OTURUM VE DOĞRULAMA KONTROLÜ
        current_url = driver.current_url.lower()
        if "login" in current_url:
            print("\n🔑 Oturum açma ekranı algılandı...")
            login_deadline = time.time() + 180
            credentials_submitted = False
            otp_entered = False
            baseline_msg_id = 0

            uets_tckn = CONFIG.get("UETS_TCKN", "")
            uets_pass = CONFIG.get("UETS_PASSWORD", "")
            tani.gizle(uets_tckn); tani.gizle(uets_pass)
            tani.adim(driver, "giris-ekrani")

            while time.time() < login_deadline:
                current_url = driver.current_url.lower()
                if "messages" in current_url or "dashboard" in current_url:
                    print("✅ Giriş başarılı!")
                    tani.adim(driver, "giris-basarili")
                    break

                # 1.A: TCKN ve Şifre formu (eğer m-sms-code henüz yoksa ve input[name='password'] varsa)
                pass_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
                sms_blocks = driver.find_elements(By.CSS_SELECTOR, "m-sms-code")

                if pass_inputs and not sms_blocks and not credentials_submitted:
                    tckn_inputs = driver.find_elements(By.CSS_SELECTOR, "input[name='ext_id'], input[placeholder*='T.C.'], input[placeholder*='UETS Adresi'], #mat-input-0")
                    if tckn_inputs and uets_tckn and uets_pass:
                        try:
                            # Giriş butonuna basmadan hemen önce referans son Gmail ID'sini al
                            baseline_msg_id = get_latest_gmail_msg_id()
                            print(f"📝 TCKN ({uets_tckn[:4]}***) ve Şifre otomatik giriliyor (Referans E-posta ID: {baseline_msg_id})...")
                            
                            tckn_inputs[0].clear()
                            tckn_inputs[0].send_keys(uets_tckn)
                            time.sleep(0.5)

                            pass_inputs[0].clear()
                            pass_inputs[0].send_keys(uets_pass)
                            time.sleep(0.5)

                            login_btn = driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], button.btn-primary")
                            if not login_btn:
                                login_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Giriş')]")

                            if login_btn:
                                print("🚀 'Giriş' butonuna tıklandı, OTP ekranı bekleniyor...")
                                driver.execute_script("arguments[0].click();", login_btn[0])
                                credentials_submitted = True
                                tani.adim(driver, "kimlik-gonderildi")
                                time.sleep(3)
                        except Exception as cred_err:
                            print(f"⚠️ Bilgiler girilirken hata oluştu: {cred_err}")

                # 1.B: SMS / E-posta Doğrulama Kodu (OTP) Ekranı kontrolü
                if sms_blocks and not otp_entered:
                    print("\n📬 Doğrulama kodu (OTP) ekranı algılandı!")
                    tani.adim(driver, "otp-ekrani")
                    print("⏳ UETS güvenlik kodu e-postadan (Gmail) alınıyor...")
                    otp_info = find_latest_otp_code(since_msg_id=baseline_msg_id, wait_seconds=3, poll_timeout=50)
                    if otp_info:
                        code, source = otp_info
                        tani.gizle(code)
                        print(f"🔥 Doğrulama Kodu Alındı: {code} [{source}]")
                        try:
                            c_inputs = sms_blocks[0].find_elements(By.TAG_NAME, "input")
                            if not c_inputs:
                                c_inputs = driver.find_elements(By.CSS_SELECTOR, "m-sms-code input, .mat-input-element")
                            
                            if c_inputs:
                                c_inputs[0].clear()
                                c_inputs[0].send_keys(code)
                                time.sleep(1)
                                
                                devam_btns = sms_blocks[0].find_elements(By.CSS_SELECTOR, "button.btn-brand, button.btn-primary")
                                if not devam_btns:
                                    devam_btns = driver.find_elements(By.XPATH, "//m-sms-code//button[contains(., 'Devam')] | //button[contains(., 'Devam')]")
                                
                                if devam_btns:
                                    driver.execute_script("arguments[0].click();", devam_btns[0])
                                    print("✅ 'Devam' butonuna tıklandı, portala giriliyor...")
                                    otp_entered = True
                                    tani.adim(driver, "otp-girildi")
                                    time.sleep(5)
                        except Exception as input_err:
                            print(f"⚠️ Kodu girerken hata: {input_err}")
                    else:
                        print("⏳ Kod henüz gelmedi, bekleniyor (manuel de girebilirsiniz)...")

                time.sleep(2)
        else:
            print("✨ Aktif UETS oturumu algılandı! Portala doğrudan erişiliyor...")

        # Gelen kutusu tablosunun hazır olmasını sağla
        print("⏳ Gelen Tebligat listesi bekleniyor...")
        ensure_messages_table(driver, timeout=20)
        tani.adim(driver, "gelen-kutusu")
        tani.kaynaklari_topla(driver)

        # ---------------------------------------------------------------------
        # 2. ADIM: CSV İNDİRME (YALNIZCA YENİ İNDİRİLECEK CSV KULLANILACAK)
        # ---------------------------------------------------------------------
        print("\n📊 [ADIM 1]: Tebligatlar CSV Dosyası İndiriliyor...")
        
        # KURAL: Mevcut/eski CSV'leri tamamen temizle (Mevcut CSV ASLA kullanılmayacak)
        print("   🧹 Mevcut eski CSV dosyaları temizleniyor...")
        for d in CONFIG["DOWNLOAD_DIRS"]:
            if os.path.exists(d):
                for old_csv in glob.glob(os.path.join(d, "*tebligat*.csv")) + glob.glob(os.path.join(d, "*Tebligat*.csv")):
                    try:
                        os.remove(old_csv)
                        print(f"      🗑️ Eski CSV silindi: {os.path.basename(old_csv)}")
                    except Exception as e:
                        print(f"      ⚠️ Silinemedi: {old_csv} ({e})")

        downloaded_csv_path = None
        # A) ÖNCE DOĞRUDAN API: tam liste (yalnızca ekrandaki 10 satır değil), indirme yöneticisine bağımlı değil.
        api_sess = None
        api_id_by_barcode = {}
        api_id_by_konu = {}   # barkodu olmayanlar (ör. noter AZİLNAME) için konu satırıyla eşleme
        try:
            from uets_api import tarayicidan_token, _oturum, mesajlari_listele, csv_yaz, barkod_bul, UetsApiHatasi
            token = tarayicidan_token(driver)
            if token:
                try:
                    u_agent = driver.execute_script('return navigator.userAgent;')
                except Exception:
                    u_agent = None
                from uets_api import TarayiciOturumu
                adet = int(CONFIG.get("UETS_LISTE_ADEDI", 200))
                mesajlar = None
                # 1) Python'dan doğrudan, 2) olmazsa tarayıcının içinden (portalın kendi çerez/kökeniyle)
                for api_sess in (_oturum(token, u_agent), TarayiciOturumu(driver, token)):
                    try:
                        mesajlar = mesajlari_listele(api_sess, en_fazla=adet,
                                                     en_eski_gun=int(CONFIG.get("MAX_SCAN_DAYS", 30)) + 30)
                        tani.olay(f"API listesi {type(api_sess).__name__} ile alındı: {len(mesajlar)} kayıt")
                        break
                    except Exception as yol_err:
                        print(f"   ⚠️ UETS API ({type(api_sess).__name__}) liste hatası: {yol_err}")
                        tani.hata(driver, f"api-liste-{type(api_sess).__name__}", yol_err)
                if mesajlar is None:
                    raise UetsApiHatasi("iki yoldan da liste alınamadı")
                csv_target = os.path.join(dl_dir, "tebligatlar.csv")
                csv_yaz(mesajlar, csv_target)
                downloaded_csv_path = csv_target
                for m in mesajlar:
                    b = barkod_bul(m.get("subject"))
                    if b and m.get("id") and b not in api_id_by_barcode:
                        api_id_by_barcode[b] = m["id"]
                    konu = (m.get("subject") or "").strip()
                    if konu and m.get("id") and konu not in api_id_by_konu:
                        api_id_by_konu[konu] = m["id"]
                print(f"   📥 CSV UETS API'den oluşturuldu: {len(mesajlar)} tebligat -> {csv_target}")
            else:
                print("   ⚠️ Tarayıcı oturumunda UETS erişim anahtarı bulunamadı; portal düğmeleri denenecek.")
                tani.adim(driver, "token-yok")
        except Exception as api_err:
            api_sess = None
            print(f"   ⚠️ UETS API ile liste alınamadı ({api_err}); portal düğmeleri denenecek.")
            tani.hata(driver, "api-liste", api_err)

        # B) YEDEK: portaldaki İNDİR > CSV İndir (yalnızca ekrandaki sayfa)
        if not downloaded_csv_path:
          try:
            before_files = set(os.listdir(dl_dir))

            # 1. "İNDİR" butonunu tıkla (button.btn-grey.btn-sm.dropdown-toggle.edit-toggle)
            tani.adim(driver, "csv-dugme-oncesi")
            indir_btns = driver.find_elements(By.XPATH, "//button[contains(@class, 'dropdown-toggle') and contains(., 'İndir')] | //button[contains(@class, 'edit-toggle')]")
            if not indir_btns:
                indir_btns = driver.find_elements(By.CSS_SELECTOR, "button.dropdown-toggle.edit-toggle")

            if indir_btns:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", indir_btns[0])
                driver.execute_script("arguments[0].click();", indir_btns[0])
                time.sleep(1)

                # 2. Dropdown menüdeki "CSV İndir" linkine tıkla
                csv_links = driver.find_elements(By.XPATH, "//a[contains(., 'CSV İndir')] | //span[contains(text(), 'CSV İndir')]/parent::a")
                if csv_links:
                    start_csv_t = time.time()
                    # Portal CSV'yi geçici <a href="blob:..."> ile indirip bağlantıyı HEMEN siliyor; tıklamadan önce
                    # bağlantının tıklanmasını yakalayıp blob adresini saklarız (sayfadan aramak hiçbir şey bulmuyordu).
                    driver.execute_script("""
                        if (!window.__blobYakala) { window.__blobYakala = true; window.__sonBlob = null;
                          const asil = HTMLAnchorElement.prototype.click;
                          HTMLAnchorElement.prototype.click = function () {
                            if (this.href && this.href.startsWith('blob:')) window.__sonBlob = this.href;
                            return asil.apply(this, arguments); }; }
                        window.__sonBlob = null;""")
                    driver.execute_script("arguments[0].click();", csv_links[0])
                    print("   ✅ 'CSV İndir' butonuna tıklandı.")
                    tani.adim(driver, "csv-tiklandi")
                    time.sleep(1.5)

                    # Sayfada oluşan blob linkini kontrol et (Chrome engellerse doğrudan JS ile çek)
                    blob_saved = False
                    yakalanan = driver.execute_script("return window.__sonBlob;")
                    if yakalanan:
                        csv_target = os.path.join(dl_dir, "tebligatlar.csv")
                        if download_blob_via_js(driver, yakalanan, csv_target):
                            blob_saved = True
                            downloaded_csv_path = csv_target
                    blob_anchors = [] if blob_saved else driver.find_elements(By.CSS_SELECTOR, "a[href^='blob:']")
                    if blob_anchors:
                        for ba in blob_anchors:
                            b_url = ba.get_attribute("href")
                            if b_url and "blob:" in b_url:
                                csv_target = os.path.join(dl_dir, "tebligatlar.csv")
                                if download_blob_via_js(driver, b_url, csv_target):
                                    blob_saved = True
                                    downloaded_csv_path = csv_target
                                    break

                    if not blob_saved:
                        csv_file = wait_for_file_download(dl_dir, before_files, start_time=start_csv_t, timeout=25, extension=".csv")
                        if csv_file:
                            downloaded_csv_path = os.path.join(dl_dir, csv_file)
                            print(f"   📥 CSV başarıyla indirildi: {csv_file}")
                        else:
                            print("   ⚠️ CSV indirme beklemesi tamamlandı.")
                    else:
                        print("   📥 CSV verisi doğrudan belleğe çekilerek diske kaydedildi.")
                else:
                    print("   ⚠️ 'CSV İndir' linki menüde bulunamadı.")
            else:
                print("   ⚠️ 'İNDİR' menü butonu bulunamadı.")
          except Exception as csv_err:
            print(f"   ⚠️ CSV indirme sırasında hata: {csv_err}")

        # Kural: Yeni CSV indirilemediyse eski CSV'yi KULLANMA, işlemi durdur!
        if not downloaded_csv_path or not os.path.exists(downloaded_csv_path):
            tani.adim(driver, "csv-yok")
            raise RuntimeError("❌ UETS portalından yeni CSV indirilemedi! Güvenlik gereği mevcut/eski CSV kullanılmayacaktır.")

        print(f"   ✅ Yeni indirilen taze CSV doğrulandı: {downloaded_csv_path}")

        # ---------------------------------------------------------------------
        # 3. ADIM: İNDİRİLEN YENİ CSV'YE GÖRE TICKTICK'İ KONTROL ET VE EKSİK EYP'LERİ İNDİR
        # ---------------------------------------------------------------------
        try:
            from csv_parser import parse_csv_file
            from eyp_parser import scan_all_eyp_files, parse_eyp_file

            csv_items = parse_csv_file(downloaded_csv_path)

            missing_rows = check_missing_tebligatlar_in_ticktick(csv_items, limit=count)

            if not missing_rows:
                print(f"\n✨ [SONUÇ]: Son tebligatların tümü TickTick'te zaten mevcut ve eksiksiz!")
                print("🚀 İndirilecek yeni EYP paketi bulunmuyor.")
            else:
                print(f"\n📦 [ADIM 2]: Tespit edilen {len(missing_rows)} adet eksik tebligatın EYP paketi sırayla inceleniyor/indiriliyor...")
                downloaded_eyp = 0

                # Mevcut yerel EYP dosyalarını önbelleğe al
                local_eyp_paths = scan_all_eyp_files()
                local_eyp_cache = {}
                for ep in local_eyp_paths:
                    try:
                        p_info = parse_eyp_file(ep, extract_files=False)
                        if p_info:
                            b = p_info.get("barcode")
                            if b:
                                local_eyp_cache[b] = ep
                    except Exception:
                        pass

                for m_pos, (target_idx, item) in enumerate(missing_rows):
                    b_code = item.get("barcode")
                    m_court = item.get("court", "")
                    m_esas = item.get("esas_no", "")
                    print(f"\n📥 [{m_pos+1}/{len(missing_rows)}] İşleniyor: {m_court} [{m_esas}] (Barkod: {b_code})...")

                    # 1. Önce bu EYP paketi yerel diskte zaten var mı kontrol et (Yalnızca benzersiz barkod ile!)
                    already_local = None
                    if b_code and b_code in local_eyp_cache:
                        already_local = local_eyp_cache[b_code]

                    if already_local and os.path.exists(already_local):
                        print(f"   ↳ 💾 EYP paketi yerel diskte zaten mevcut: {os.path.basename(already_local)} (İndirme atlandı)")
                        downloaded_eyp += 1
                        continue

                    # 1.5 Doğrudan API ile indir (mesaj kimliği listeden biliniyor; ekran gezintisi gerekmez)
                    mesaj_id = api_id_by_barcode.get(b_code) if b_code else api_id_by_konu.get((item.get("konu_raw") or "").strip())
                    if mesaj_id and os.path.exists(os.path.join(dl_dir, f"{mesaj_id}.eyp")):
                        print(f"   ↳ 💾 EYP paketi yerel diskte zaten mevcut: {mesaj_id}.eyp (İndirme atlandı)")
                        downloaded_eyp += 1
                        continue
                    if api_sess is not None and mesaj_id:
                        from uets_api import eyp_indir, _oturum as _yeni_oturum, TarayiciOturumu as _TO
                        yol = None
                        for eyp_sess in (api_sess, _TO(driver, token)):
                            try:
                                yol = eyp_indir(eyp_sess, mesaj_id, dl_dir)
                                break
                            except Exception as api_eyp_err:
                                print(f"   ↳ ⚠️ API ({type(eyp_sess).__name__}) ile EYP indirilemedi: {api_eyp_err}")
                                tani.hata(driver, f"api-eyp-{type(eyp_sess).__name__}", api_eyp_err)
                        if yol:
                            local_eyp_cache[b_code] = yol
                            downloaded_eyp += 1
                            print(f"   ↳ 📥 EYP UETS API'den indirildi: {os.path.basename(yol)}")
                            continue
                    if mesaj_id:
                        # Tabloda aramak yerine detay sayfasını doğrudan aç (portal yolu: /messages/1/viewMessages/<id>)
                        print("   ↳ Detay sayfası doğrudan açılıyor...")
                        driver.get(f"{PORTAL}/messages/1/viewMessages/{mesaj_id}")
                        time.sleep(3)
                        tani.adim(driver, f"detay-dogrudan-{b_code}")

                    # 2. Gelen kutusu tablosuna dönmeyi ve satırların hazır olmasını %100 garanti et
                    if not mesaj_id:
                        ensure_messages_table(driver, timeout=20)
                        tani.adim(driver, f"satir-aranacak-{b_code or m_esas}")

                    if mesaj_id:
                        row_href = ""
                        doc_uuid = mesaj_id
                    else:
                        # 3. İlgili satırı bul: Çok sayfalı arama (Sayfalama ve Boyut desteği ile)
                        matched_row = find_matching_row_with_pagination(driver, b_code, m_esas, max_pages=5)
                        # (Eski "sıradaki satırı al" son çaresi kaldırıldı: barkod doğrulamadan YANLIŞ tebligatın EYP'sini indirebiliyordu.)

                        if not matched_row:
                            print(f"   ⚠️ Satır tablonun hiçbir sayfasında bulunamadı, atlanıyor.")
                            tani.adim(driver, f"satir-bulunamadi-{b_code or m_esas}")
                            continue

                        # 4. Satırdaki "Görüntüle" linkini bul (a.view-btn)
                        view_btns = matched_row.find_elements(By.CSS_SELECTOR, "a.view-btn, a[href*='viewmessages'], a[href*='messages']")
                        if not view_btns:
                            view_btns = matched_row.find_elements(By.XPATH, ".//a[contains(@class, 'view-btn') or contains(., 'Görüntüle')] | .//button[contains(., 'Görüntüle')]")

                        if not view_btns:
                            print(f"   ⚠️ Görüntüle butonu bulunamadı, satır atlanıyor.")
                            continue

                        row_href = view_btns[0].get_attribute("href") or ""
                        doc_uuid = row_href.split("/")[-1] if "/" in row_href else (b_code or f"tebligat_{target_idx+1}")

                        # Görüntüle'ye tıkla
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", view_btns[0])
                        driver.execute_script("arguments[0].click();", view_btns[0])

                        # Sekme kontrolü (eğer yeni sekme açıldıysa ona odaklan)
                        if len(driver.window_handles) > 1:
                            driver.switch_to.window(driver.window_handles[-1])
                    tani.adim(driver, f"detay-{b_code or m_esas}")

                    # 5. Detay penceresindeki "EYP Paketini İndir" butonunu bekle ve tıkla
                    eyp_btn = None
                    try:
                        eyp_btn = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-danger') and contains(., 'EYP')] | //button[contains(., 'EYP Paketini İndir')] | //button[contains(., 'EYP')]"))
                        )
                    except Exception:
                        if row_href and ("http" in row_href or "/" in row_href):
                            try:
                                driver.get(row_href)
                                eyp_btn = WebDriverWait(driver, 12).until(
                                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-danger') and contains(., 'EYP')] | //button[contains(., 'EYP Paketini İndir')] | //button[contains(., 'EYP')]"))
                                )
                            except Exception:
                                pass

                    if not eyp_btn:
                        print(f"   ⚠️ Detay sayfası veya EYP butonu yüklenemedi.")
                        tani.adim(driver, f"eyp-dugmesi-yok-{b_code or m_esas}")
                        ensure_messages_table(driver)
                        continue

                    before_eyp_files = set(os.listdir(dl_dir))
                    start_eyp_t = time.time()
                    driver.execute_script("arguments[0].click();", eyp_btn)
                    print(f"   ↳ 'EYP Paketini İndir' tıklandı...")
                    tani.adim(driver, f"eyp-tiklandi-{b_code or m_esas}")

                    time.sleep(1.5)
                    eyp_blob_saved = False
                    saved_eyp_file = None

                    # A. Doğrudan UETS API üzerinden indirmeyi dene (Hızlı, Garantili & Zaman Aşımına Karşı Korunaklı)
                    if doc_uuid:
                        try:
                            token = driver.execute_script('return localStorage.getItem("accessToken") || sessionStorage.getItem("accessToken");')
                            if token:
                                cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                                api_url = f"https://api.etebligat.gov.tr/v1/messages/{doc_uuid}/_download"
                                u_agent = driver.execute_script('return navigator.userAgent;')
                                api_resp = requests.get(api_url, headers={'Authorization': f'Bearer {token}', 'User-Agent': u_agent}, cookies=cookies, timeout=20)
                                if api_resp.status_code == 200 and len(api_resp.content) > 100:
                                    target_name = f"{doc_uuid}.eyp"
                                    eyp_target = os.path.join(dl_dir, target_name)
                                    with open(eyp_target, "wb") as f:
                                        f.write(api_resp.content)
                                    eyp_blob_saved = True
                                    saved_eyp_file = eyp_target
                                    print(f"   ↳ 📥 EYP Paketi UETS API üzerinden başarıyla indirildi ({len(api_resp.content)} byte)")
                        except Exception:
                            pass

                    blob_anchors = driver.find_elements(By.CSS_SELECTOR, "a[href^='blob:']")
                    if not eyp_blob_saved and blob_anchors:
                        for ba in blob_anchors:
                            b_url = ba.get_attribute("href")
                            b_name = ba.get_attribute("download") or f"{doc_uuid}.eyp"
                            if not b_name.endswith(".eyp"):
                                b_name += ".eyp"
                            eyp_target = os.path.join(dl_dir, b_name)
                            if download_blob_via_js(driver, b_url, eyp_target):
                                eyp_blob_saved = True
                                saved_eyp_file = eyp_target
                                break

                    if not eyp_blob_saved:
                        new_eyp = wait_for_file_download(dl_dir, before_eyp_files, start_time=start_eyp_t, timeout=45, extension=".eyp")
                        if not new_eyp:
                            new_eyp = wait_for_file_download(dl_dir, before_eyp_files, start_time=start_eyp_t, timeout=10)

                        if new_eyp:
                            saved_eyp_file = os.path.join(dl_dir, new_eyp)
                            print(f"   ↳ 📥 EYP Paketi İndirildi: {new_eyp}")
                            downloaded_eyp += 1
                        else:
                            print(f"   ↳ ⚠️ EYP indirme zaman aşımına uğradı.")
                    else:
                        print(f"   ↳ 📥 EYP Paketi doğrudan kaydedildi.")
                        downloaded_eyp += 1

                    if saved_eyp_file and os.path.exists(saved_eyp_file):
                        if b_code:
                            local_eyp_cache[b_code] = saved_eyp_file

                    tani.olay(f"EYP sonucu {b_code}: {saved_eyp_file}")
                    # 6. Bir sonraki tebligat için Gelen Tebligatlar listesine dönmeyi garanti et
                    ensure_messages_table(driver)

                print(f"\n🎉 Toplam {downloaded_eyp} adet eksik EYP paketi başarıyla hazırlandı/indirildi!")
        except Exception as eyp_err:
            print(f"⚠️ EYP paketleri indirilirken genel hata: {eyp_err}")
            tani.hata(driver, "eyp-genel", eyp_err)

        # ---------------------------------------------------------------------
        # 4. ADIM: AVUKAT ASİSTANI SENKRONİZASYONUNU ÇALIŞTIR
        # ---------------------------------------------------------------------
        if auto_sync:
            print("\n" + "="*70)
            print("🚀 [ADIM 3]: Avukat Asistanı Senkronizasyonu Başlatılıyor...")
            print("="*70)
            from main import run_synchronization
            run_synchronization(csv_path=downloaded_csv_path)

        return downloaded_csv_path

    except Exception as genel_hata:
        tani.hata(driver, "genel", genel_hata)
        raise
    finally:
        tani.bitir(driver)
        if driver_created:
            try:
                driver.quit()
                print("🔒 Tarayıcı güvenli şekilde kapatıldı.")
            except Exception:
                pass

    return downloaded_csv_path

def run_daemon_mode(interval_minutes=15, headless=False, count=None, auto_sync=True):
    """
    Termux'u sürekli UETS'ye bağlı tutar, oturumun kopmasını engeller
    ve her N dakikada bir yeni tebligatları otomatik kontrol eder.
    """
    print("\n" + "="*70)
    print(f"🔄  UETS CANLI İZLEME & OTURUM KORUYUCU (HER {interval_minutes} DAKİKADA BİR)")
    print("="*70)
    print("💡 Termux arka planda UETS oturumunu canlı tutacak ve tebligatları indirecektir.")
    print("Çıkmak için bu ekranda Ctrl+C tuşlarına basabilirsiniz.\n")

    driver = setup_driver(headless=headless)
    try:
        while True:
            try:
                login_and_download(headless=headless, count=count, auto_sync=auto_sync, external_driver=driver)
            except Exception as loop_err:
                print(f"⚠️ Bu tarama döngüsünde hata oluştu: {loop_err}")

            print(f"\n💤 Bir sonraki kontrole kadar {interval_minutes} dakika bekleniyor (Oturum pinglenerek korunacak)...")
            
            # Belirtilen dakika boyunca her 3 dakikada bir hafif ping yaparak oturumun zaman aşımına düşmesini engelle
            wait_end = time.time() + (interval_minutes * 60)
            while time.time() < wait_end:
                sleep_chunk = min(180, max(1, wait_end - time.time()))
                time.sleep(sleep_chunk)
                if time.time() < wait_end:
                    try:
                        driver.get(f"{PORTAL}/messages/1")
                    except Exception:
                        pass
    except KeyboardInterrupt:
        print("\n🛑 Canlı izleme modu sonlandırıldı.")
    finally:
        try:
            driver.quit()
            print("🔒 Tarayıcı güvenli şekilde kapatıldı.")
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="UETS Otomatik Tebligat ve EYP İndirici (Selenium)")
    parser.add_argument("--count", "-c", type=int, default=None, help="İndirilecek son tebligat sayısı (varsayılan: tümü)")
    parser.add_argument("--headless", action="store_true", help="Tarayıcıyı başsız (ekransız) modda çalıştır")
    parser.add_argument("--no-sync", action="store_true", help="İndirme sonrasında senkronizasyonu otomatik çalıştırma")
    parser.add_argument("--tani", action="store_true", help="Teşhis: her adımda ekran görüntüsü, DOM, ağ ve konsol kaydı alıp zip'e paketler")
    parser.add_argument("--watch", "-w", type=int, nargs="?", const=5, default=None, help="Termux'u sürekli UETS'ye bağlı tutup her N dakikada bir kontrol et (varsayılan: 15)")
    args = parser.parse_args()
    if args.tani:
        tani.etkinlestir()

    if args.watch:
        run_daemon_mode(interval_minutes=args.watch, headless=args.headless, count=args.count, auto_sync=not args.no_sync)
    else:
        login_and_download(headless=args.headless, count=args.count, auto_sync=not args.no_sync)

if __name__ == "__main__":
    main()
