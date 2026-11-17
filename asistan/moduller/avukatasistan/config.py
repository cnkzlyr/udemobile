#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ AVUKAT BULUT OTOMASYONU - TERMUX SÜRÜMÜ
Yapılandırma ve Sabitler
"""

import os
from datetime import timezone, timedelta

# Türkiye Saati (UTC+3)
TZ_TURKEY = timezone(timedelta(hours=3))

# ---------------------------------------------------------------------------
# GİZLİ BİLGİLER (.env): API anahtarları, şifreler ve UETS girişi artık KODDA DEĞİL.
# Proje klasöründeki .env dosyasından (git'e girmez, izin 600) ya da ortam değişkenlerinden okunur.
# .env yoksa bir kereliğe mahsus, bilgilerin kodda durduğu son sürümden (git geçmişi) taşınır; böylece
# güncelleme sonrası sistem çalışmaya devam eder. Bu anahtarlar git geçmişinde kaldığı için YENİLENMELİDİR.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(_HERE, ".env")
_GIZLI_ANAHTARLAR = ["TICKTICK_TOKEN", "NOTION_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
                     "GMAIL_USER", "GMAIL_APP_PASS", "UETS_TCKN", "UETS_PASSWORD", "TICKTICK_EMAIL"]
_ESKI_SURUM = "3a448c39969afbbc34a0f3f1b9011b8020bdab3d"  # bilgilerin config.py'de durduğu son commit


def _env_tasi():
    """Eski config.py'deki (git geçmişi) gizli değerleri .env dosyasına bir kez taşır."""
    if os.path.exists(ENV_PATH) or os.environ.get("AVUKAT_ENV_TASIMA") == "0":
        return
    import re
    import subprocess
    try:
        eski = subprocess.run(["git", "-C", _HERE, "show", f"{_ESKI_SURUM}:config.py"],
                              capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return
    if not eski:
        return
    degerler = {}
    for k in _GIZLI_ANAHTARLAR:
        m = re.search(r'"%s":\s*(?:os\.environ\.get\("%s",\s*)?"([^"]*)"' % (k, k), eski)
        if m and m.group(1):
            degerler[k] = m.group(1)
    try:
        eski_mail = subprocess.run(["git", "-C", _HERE, "show", f"{_ESKI_SURUM}:mail_sender.py"],
                                   capture_output=True, text=True, timeout=10).stdout
        m = re.search(r'TICKTICK_EMAIL\s*=\s*"([^"]+)"', eski_mail or "")
        if m:
            degerler["TICKTICK_EMAIL"] = m.group(1)
    except Exception:
        pass
    if not degerler:
        return
    try:
        fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# Avukat Asistanı gizli ayarları (git'e girmez). Değerleri yeniledikçe buradan değiştirin.\n")
            for k, v in degerler.items():
                f.write(f"{k}={v}\n")
        print(f"🔐 Gizli ayarlar koddan {ENV_PATH} dosyasına taşındı. Lütfen anahtarları yenileyin (README: Güvenlik).")
    except FileExistsError:
        pass
    except Exception as e:
        print(f"⚠️ .env oluşturulamadı: {e}")


def _env_yukle():
    """.env satırlarını (ANAHTAR=değer) ortam değişkenlerine yükler; ortamda zaten olan değerler önceliklidir."""
    _env_tasi()
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for satir in f:
                satir = satir.strip()
                if not satir or satir.startswith("#") or "=" not in satir:
                    continue
                k, v = satir.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_env_yukle()


def _gizli(ad, varsayilan=""):
    return os.environ.get(ad, varsayilan)

def _detect_uets_archive_dir():
    if os.path.exists("/sdcard/Download"):
        p = "/sdcard/Download/UETS_Arsivi"
    else:
        p = os.path.join(os.path.expanduser("~/Downloads"), "UETS_Arsivi")
    os.makedirs(p, exist_ok=True)
    return p

def _detect_download_dirs():
    candidates = [
        # UETS Sürekli Arşiv Klasörü (Tüm EYP ve CSV'ler burada toplanır)
        _detect_uets_archive_dir(),
        # Android (Tablet / Telefon)
        "/sdcard/Download",
        "/storage/emulated/0/Download",
        os.path.expanduser("~/storage/downloads"),
        # Mac & Linux & Windows varsayılan
        os.path.expanduser("~/Downloads"),
    ]
    # Windows kullanıcı ve OneDrive yolları
    user_prof = os.environ.get("USERPROFILE")
    if user_prof:
        candidates.append(os.path.join(user_prof, "Downloads"))
        candidates.append(os.path.join(user_prof, "OneDrive", "Downloads"))

    seen_real = set()
    found = []
    for c in candidates:
        if c and os.path.exists(c):
            try:
                rp = os.path.realpath(c)
            except Exception:
                rp = c
            if rp not in seen_real:
                seen_real.add(rp)
                found.append(c)

    if not found:
        found.append(os.path.expanduser("~/Downloads"))
    return found

def _detect_evrak_output_dir():
    p = os.path.join(_detect_uets_archive_dir(), "Tebligat_Evraklari")
    os.makedirs(p, exist_ok=True)
    return p

CONFIG = {
    "UETS_ARCHIVE_DIR": _detect_uets_archive_dir(),
    # API Anahtarları
    "NOTION_TOKEN": _gizli("NOTION_TOKEN"),
    "TICKTICK_TOKEN": _gizli("TICKTICK_TOKEN"),
    "NOTION_DB_DOSYALAR": "3bfff3541194803aa052dd2c41e4d94a",
    
    # API Adresleri
    "TICKTICK_API_BASE": os.environ.get("TICKTICK_API_BASE", "https://api.ticktick.com/open/v1"),
    "NOTION_API_BASE": "https://api.notion.com/v1",
    
    # Süre ve Tarih Kuralları
    "UETS_DELIVERY_DAYS": 5,           # 5. gün tebliğ sayılma
    "UETS_DEFAULT_DEADLINE_DAYS": 14,  # 14 günlük yasal süre
    "UETS_SHORT_DEADLINE_DAYS": 7,     # 7 günlük yasal süre
    "DEADLINE_HOUR": 17,               # Son gün saat 17:00
    "MAX_SCAN_DAYS": 30,               # En fazla 30 gün geriye dönük tarama
    
    # Dizinler (Otomatik Algılama: Android Tablet/Telefon, Windows PC, MacBook, Linux)
    "DOWNLOAD_DIRS": _detect_download_dirs(),
    "EVRAK_OUTPUT_DIR": _detect_evrak_output_dir(),
    
    # Telegram Bot Bilgileri
    "TELEGRAM_BOT_TOKEN": _gizli("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID": _gizli("TELEGRAM_CHAT_ID"),

    # Gmail UETS Doğrulama (OTP) IMAP Ayarları
    "GMAIL_USER": _gizli("GMAIL_USER"),
    "TICKTICK_EMAIL": _gizli("TICKTICK_EMAIL"),  # TickTick'e e-postayla görev ekleme adresi (todo+...@mail.ticktick.com)
    "GMAIL_APP_PASS": _gizli("GMAIL_APP_PASS"),
    "GMAIL_UETS_LABEL": '"UETS Giris&Ayc- Kodu"',  # 'UETS Giriş Kodu' etiketi (RFC 3501 UTF-7)

    # UETS Giriş Bilgileri
    "UETS_TCKN": _gizli("UETS_TCKN"),
    "UETS_PASSWORD": _gizli("UETS_PASSWORD"),

    # EYP bu kadar saat indirilemezse tebligat görevi eksiz açılır (yasal süre kaçmasın). -1: hiç açma.
    "EYP_BEKLEME_SAAT": float(_gizli("EYP_BEKLEME_SAAT", "6")),

    # Kara Liste: Takip Dışı Müvekkil ve Dosyalar
    "EXCLUDED_KEYWORDS": [
        "gulsen hakverdi", "casmoni", "seferihisar", "menderes baydar", "baydar",
        "emre oral", "kemal barlak", "hakan cap", "irfan ozturk", "maral",
        "ali yildiz", "metin urgun", "vefa celik", "huseyin yigit", "metin yigit", "nimet koca"
    ],

    # Etiket Eşleştirmeleri
    "TAG_OVERRIDES": {
        "adkpazarlamamagazacilikyapisanayiticaretanonimsirketi": "agkirikkale",
        "adkpazarlama": "agkirikkale",
        "ramazanemreayelan": "cmk_ramazanemreayelan",
        "sudenazyildirim": "cmk_sudenazyildirim",
        "osmancolak": "cmk_osmancolak",
        "mehmetkorkmaz": "cmk_mehmetkorkmaz",
        "naturelltdsti": "naturel",
        "naturel": "naturel",
        "cevatalpaslan": "osmancevatalpaslan",
        "ademtasdemir": "kiyasettintasdemir",
        "adilsengul": "ekremaktas",
        "servetalpaslanmuhendislikanonimsirketi": "servetalpaslan",
        "alimiratozyolcu": "necmettinozyolcu",
        "kaleraydemiryoluinsaatmuhendisliksanayiveticaretanonimsirketi": "kaleray",
        "atmacamadencilikinsaattaahhutnakliyepetrolsanayiveticaretlimited": "erolatmaca",
        "edibecelik": "yasincelikmirascilari",
        "canselcecenbilal": "yasincelikmirascilari"
    },

    # Şirket ve Özel Anahtar Kelime Eşleştirmeleri (Eklerden ve unvanlardan bağımsız)
    "COMPANY_KEYWORD_OVERRIDES": {
        "atmaca": "erolatmaca",
        "nextpoint": "zekicoban",
        "kaleray": "kaleray",
        "naturel": "naturel",
        "servetalpaslan": "servetalpaslan",
        "adkpazarlama": "agkirikkale",
        "agkirikkale": "agkirikkale",
        "cetin": "cetinler"
    },

    # Bilinen CMK Müvekkilleri (Otomatik #cmk_ öneki ve #cmk etiketi alır)
    "CMK_CLIENTS": [
        "ramazanemreayelan", "sudenazyildirim", "osmancolak", "mehmetkorkmaz",
        "ferhatakbas", "ardadogan", "kubilayolpak", "dursunaltuntas", "haydarkumlu"
    ],

    # Üst Etiket (Parent Tag) Haritası
    "PARENT_TAG_MAP": {
        "cankizilyar": "aile", "gulerkizilyar": "aile", "larenecekizilyar": "aile",
        "hanefiege": "beykem", "mustafaege": "beykem",
        "denizbank": "finans", "garanti": "finans", "qnb": "finans", "vakifbank": "finans",
        "demetsanmak": "tevkil", "mustafakartal": "tevkil", "sezaisanmak": "tevkil",
        "bunyamintoykan": "ramazanzengin",
        "aydincoban": "zekicoban",
        "huseyinozmen": "aliozmen"
    }
}

PROJECT_IDS = {
    "TüketiciMahkemesi": "66a0ec5eebad360000000949",
    "DanıştayDosyaları": "695fb0278f087d4e8df73f3e",
    "BİM_İdareDosyaları": "695fb0278f087d4e8df73f55",
    "VergiMahkemesi": "695fb0278f087d4e8df73f60",
    "İdareMahkemesi": "695fb0278f087d4e8df73f66",
    "AileMahkemesi": "695fb0278f087d4e8df73f8c",
    "AsliyeHukukMahkemesi": "695fb0278f087d4e8df73fd3",
    "AsliyeTicaretMahkemesi": "695fb0278f087d4e8df740e4",
    "BAM_HukukDairesi": "695fb0278f087d4e8df74159",
    "İşMahkemesi": "695fb0278f087d4e8df741c7",
    "KadastroMahkemesi": "695fb0278f087d4e8df74263",
    "SulhHukukMahkemesi": "695fb0278f087d4e8df74274",
    "Yargıtay-HukukDairesi": "695fb0278f087d4e8df742bc",
    "İcraHukukMahkemesi": "695fb0278f087d4e8df742c4",
    "İcraTakipleri": "695fb0278f087d4e8df74333",
    "KİRA TAKİBİ": "695fb0278f087d4e8df74357",
    "Soruşturmalar": "695fb0278f087d4e8df743aa",
    "AğırCezaMahkemesi": "695fb0278f087d4e8df743e0",
    "AsliyeCezaMahkemesi": "695fb0278f087d4e8df74542",
    "BAM-CezaDairesi": "695fb0278f087d4e8df746b8",
    "ÇocukMahkemesi": "695fb0278f087d4e8df74720",
    "İcraCezaHakimliği": "695fb0278f087d4e8df74727",
    "Yargıtay-CezaDairesi": "695fb0278f087d4e8df7472d",
    "FikriSınaiHaklar": "inbox",
    "ArabuluculukDosyaları": "inbox",
    "Inbox": "inbox"
}
