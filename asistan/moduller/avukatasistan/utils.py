#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yardımcı Fonksiyonlar, Metin Temizleme ve Tarih Hesaplamaları
"""

import re
from datetime import datetime, timedelta
from config import CONFIG, TZ_TURKEY

def normalize_tr(s):
    if not s:
        return ""
    return str(s).replace("İ", "i").replace("I", "ı").lower()

def clean_text(text):
    if not text:
        return ""
    tr_map = {"ğ": "g", "ü": "u", "ş": "s", "ı": "i", "ö": "o", "ç": "c", "i": "i"}
    s = normalize_tr(text)
    for k, v in tr_map.items():
        s = s.replace(k, v)
    return re.sub(r"[^a-z0-9]", "", s)

def is_excluded(text):
    if not text:
        return False
    s = clean_text(text)
    for kw in CONFIG["EXCLUDED_KEYWORDS"]:
        if clean_text(kw) in s:
            return True
    return False

def resolve_client_tag(raw_name, is_cmk=False):
    if not raw_name:
        return ""
    clean = clean_text(raw_name)
    
    # 1. Şirket ve özel anahtar kelimeler (eklerden/unvanlardan bağımsız)
    for kw, target in CONFIG.get("COMPANY_KEYWORD_OVERRIDES", {}).items():
        if kw in clean:
            clean = target
            break
            
    # 2. Tam override eşleşmesi
    if clean in CONFIG.get("TAG_OVERRIDES", {}):
        clean = CONFIG["TAG_OVERRIDES"][clean]
        
    # 3. CMK kontrolü: is_cmk True ise veya bilinen CMK müvekkili ise
    cmk_list = CONFIG.get("CMK_CLIENTS", [])
    if is_cmk or clean in cmk_list or clean.startswith("cmk_") or any(c in clean for c in cmk_list):
        clean_base = clean.replace("cmk_", "")
        return f"#cmk_{clean_base}"
        
    return f"#{clean}"

def normalize_tags(tags, is_cmk=False, is_uets=None):
    """
    Göreve ait etiket listesini temizler, dönüştürür ve kurala uygun hale getirir:
    - Şirket unvanlarını (atmacamadencilik... -> erolatmaca) düzeltir.
    - CMK dosyalarında bare ismi kaldırır, 'cmk_' öneki verir ve 'cmk' ana etiketini garanti eder.
    - Tekrarları temizler.
    - is_uets True ise 'uets' etiketini ekler; is_uets False ise (Duruşma ve üst dava kartları) 'uets' etiketini ÇIKARIR.
    - is_uets None ise listede varsa korur, yoksa eklemez.
    """
    had_uets = any(t.replace("#", "").strip().lower() == "uets" for t in (tags or []))
    if not tags:
        return ["uets"] if is_uets is True else []
        
    new_tags = set()
    cmk_list = set(CONFIG.get("CMK_CLIENTS", []))
    has_cmk = is_cmk
    
    # Mevcut etiketlerde cmk veya cmk_ var mı kontrol et
    for t in tags:
        t_clean = t.replace("#", "").strip().lower()
        if t_clean == "cmk" or t_clean.startswith("cmk_") or t_clean in cmk_list:
            has_cmk = True
            
    for t in tags:
        t_clean = t.replace("#", "").strip().lower()
        if not t_clean:
            continue
            
        if t_clean == "uets":
            if is_uets is not False:
                new_tags.add("uets")
            continue
            
        if t_clean == "cmk":
            new_tags.add("cmk")
            continue
            
        # Şirket anahtar kelime eşleştirmesi (CMK müvekkili veya CMK etiketi ise şirket unvanıyla ezilmez)
        if not t_clean.startswith("cmk_") and t_clean not in cmk_list:
            for kw, target in CONFIG.get("COMPANY_KEYWORD_OVERRIDES", {}).items():
                if kw in t_clean:
                    t_clean = target
                    break
                
        if t_clean in CONFIG.get("TAG_OVERRIDES", {}):
            t_clean = CONFIG["TAG_OVERRIDES"][t_clean]
            
        # Eğer bu müvekkil bir CMK müvekkili ise veya dosya CMK ise
        if has_cmk and (t_clean in cmk_list or any(c in t_clean for c in cmk_list) or t_clean.startswith("cmk_")):
            base_name = t_clean.replace("cmk_", "")
            new_tags.add(f"cmk_{base_name}")
            new_tags.add("cmk")
        elif t_clean in cmk_list:
            new_tags.add(f"cmk_{t_clean}")
            new_tags.add("cmk")
        else:
            new_tags.add(t_clean)
            
    # Eğer herhangi bir cmk_ etiketi varsa 'cmk' garanti edilir ve bare isim varsa çıkarılır
    cmk_bases = set()
    for nt in list(new_tags):
        if nt.startswith("cmk_"):
            cmk_bases.add(nt.replace("cmk_", ""))
            new_tags.add("cmk")
            
    # Bare isimleri temizle (örn: ferhatakbas silinir, cmk_ferhatakbas kalır)
    for base in cmk_bases:
        if base in new_tags:
            new_tags.remove(base)
            
    # Üst etiketleri ekle (PARENT_TAG_MAP)
    for nt in list(new_tags):
        if nt in CONFIG.get("PARENT_TAG_MAP", {}):
            new_tags.add(CONFIG["PARENT_TAG_MAP"][nt])
            
    # UETS etiketi kontrolü (Duruşmalara ve dava kartlarına ASLA verilmez!)
    if is_uets is True:
        new_tags.add("uets")
    elif is_uets is False:
        new_tags.discard("uets")
    elif had_uets:
        new_tags.add("uets")
    
    return sorted(list(new_tags))

def get_required_parent_tags(tags):
    needed = []
    for t in tags:
        tl = t.lower()
        if tl.startswith("cmk_") and "cmk" not in needed:
            needed.append("cmk")
        if tl in CONFIG.get("PARENT_TAG_MAP", {}):
            p = CONFIG["PARENT_TAG_MAP"][tl]
            if p not in needed:
                needed.append(p)
    return needed

def determine_list(court, gonderen=""):
    m = normalize_tr(court)
    g = normalize_tr(gonderen)
    if "arabuluculuk" in m: return "ArabuluculukDosyaları"
    if "fikri ve sınai" in m or "fshm" in m: return "FikriSınaiHaklar"
    if "kira" in m: return "KİRA TAKİBİ"
    if "icra ceza" in m: return "İcraCezaHakimliği"
    if "icra müdürlüğü" in m or "icra dairesi" in m: return "İcraTakipleri"
    if "infaz" in m: return "AğırCezaMahkemesi"
    if "ağır" in m: return "ÇocukMahkemesi" if "çocuk" in m else "AğırCezaMahkemesi"
    if any(k in m for k in ["soruşturma", "hazırlık", "savcılığı", "savcilik", "bürosu"]): return "Soruşturmalar"
    if "asliye ceza" in m: return "AsliyeCezaMahkemesi"
    if "asliye hukuk" in m: return "AsliyeHukukMahkemesi"
    if "asliye ticaret" in m: return "AsliyeTicaretMahkemesi"
    if "çocuk" in m: return "ÇocukMahkemesi"
    if "aile" in m: return "AileMahkemesi"
    if "iş mahkemesi" in m or "is mahkemesi" in m: return "İşMahkemesi"
    if "sulh hukuk" in m: return "SulhHukukMahkemesi"
    if "icra hukuk" in m: return "İcraHukukMahkemesi"
    if "tüketici" in m: return "TüketiciMahkemesi"
    if "kadastro" in m: return "KadastroMahkemesi"
    if "bölge idare" in m or "bim" in m or "idari dava" in m: return "BİM_İdareDosyaları"
    if "bölge adliye" in m or "bam" in m: return "BAM-CezaDairesi" if "ceza" in m else "BAM_HukukDairesi"
    if "danıştay" in m: return "DanıştayDosyaları"
    if "vergi" in m: return "VergiMahkemesi"
    if "idare" in m: return "İdareMahkemesi"
    if "yargıtay" in m or "yargitay" in g:
        return "Yargıtay-CezaDairesi" if "ceza" in m else "Yargıtay-HukukDairesi"
    if "ceza dairesi" in m: return "Yargıtay-CezaDairesi"
    if "hukuk dairesi" in m: return "Yargıtay-HukukDairesi"
    return "Inbox"

def adjust_for_weekend(dt):
    """
    Sürenin son günü hafta sonuna (Cumartesi/Pazar) rastlarsa Pazartesi'ye uzatır (HMK m. 94, CMK m. 39, İİK m. 19).
    """
    weekday = dt.weekday()
    if weekday == 5: # Cumartesi -> Pazartesi
        return dt + timedelta(days=2)
    elif weekday == 6: # Pazar -> Pazartesi
        return dt + timedelta(days=1)
    return dt

def get_applicable_deadline_days(court, doc_type=""):
    """
    Merci türüne ve evrak mahiyetine göre uygulanacak yasal süreyi belirler:
    - İcra takipleri ve İcra Mahkemesi: 7 Gün (Ödeme emrine itiraz vb. İİK m. 62)
    - Ceza Mahkemeleri ve Soruşturmalar: 7 Gün (İtiraz süreleri CMK m. 268)
    - İdari Yargı: 30 Gün (İYUK m. 7, 45)
    - Hukuk Mahkemeleri: 14 Gün / 2 Hafta (HMK m. 127, 281, 345)
    """
    c = normalize_tr(court)
    
    # 1. İcra Daireleri & İcra Mahkemesi -> 7 Gün
    if any(k in c for k in ["icra", "kira"]):
        return 7
        
    # 2. Ceza Mahkemeleri ve Soruşturma Büroları -> 7 Gün
    if any(k in c for k in ["ceza", "soruşturma", "sorusturma", "hazırlık", "hazirlik", "savcılık", "savcilik"]):
        return 7
        
    # 3. İdari ve Vergi Yargısı -> 30 Gün
    if any(k in c for k in ["idare", "vergi", "danıştay", "danistay", "bim", "bölge idare"]):
        return 30
        
    # 4. Hukuk Mahkemeleri (Asliye Hukuk, Ticaret, İş, Aile, Sulh Hukuk vb.) -> 14 Gün (2 Hafta)
    return 14

def tt_iso(dt):
    """TickTick Open API tarih biçimi (yyyy-MM-dd'T'HH:mm:ssZ), saat diliminin GERÇEK ofsetiyle (Türkiye: +0300).
    Saat dilimi olmayan datetime Türkiye saati kabul edilir."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ_TURKEY)
    return dt.strftime("%Y-%m-%dT%H:%M:00%z")

def calculate_deadlines(gelis_dt, court="", doc_type=""):
    """
    Tebligat süre hesaplaması (Türkiye Saati UTC+3)
    gelis_dt: datetime nesnesi (UTC+3)
    court: Merci adı (mahkeme/daire türüne göre doğru süreyi otomatik seçer)
    """
    if gelis_dt.tzinfo is None:
        gelis_dt = gelis_dt.replace(tzinfo=TZ_TURKEY)
        
    # 1. Tebliğ Sayılma (5. Gün)
    teblig_dt = gelis_dt + timedelta(days=CONFIG["UETS_DELIVERY_DAYS"])
    
    # 2. Süreleri hesapla ve hafta sonu kuralını uygula (Mesai bitimi 17:00)
    d7_raw = teblig_dt + timedelta(days=CONFIG["UETS_SHORT_DEADLINE_DAYS"])
    d7_dt = adjust_for_weekend(d7_raw).replace(hour=CONFIG["DEADLINE_HOUR"], minute=0, second=0, microsecond=0)
    
    d14_raw = teblig_dt + timedelta(days=CONFIG["UETS_DEFAULT_DEADLINE_DAYS"])
    d14_dt = adjust_for_weekend(d14_raw).replace(hour=CONFIG["DEADLINE_HOUR"], minute=0, second=0, microsecond=0)
    
    d30_raw = teblig_dt + timedelta(days=30)
    d30_dt = adjust_for_weekend(d30_raw).replace(hour=CONFIG["DEADLINE_HOUR"], minute=0, second=0, microsecond=0)
    
    # Merciye göre uygulanacak öncelikli süreyi belirle
    app_days = get_applicable_deadline_days(court, doc_type)
    if app_days == 7:
        target_dt = d7_dt
        target_label = "7 Günlük Yasal Süre (İcra/Ceza)"
    elif app_days == 30:
        target_dt = d30_dt
        target_label = "30 Günlük Yasal Süre (İdari Yargı)"
    else:
        target_dt = d14_dt
        target_label = "14 Günlük / 2 Haftalık Yasal Süre (HMK)"
        
    return {
        "gelis_dt": gelis_dt,
        "teblig_dt": teblig_dt,
        "d7_dt": d7_dt,
        "d14_dt": d14_dt,
        "d30_dt": d30_dt,
        "target_dt": target_dt,
        "target_days": app_days,
        "target_label": target_label,
        "gelis_str": gelis_dt.strftime("%d.%m.%Y %H:%M"),
        "teblig_str": teblig_dt.strftime("%d.%m.%Y"),
        "d7_str": d7_dt.strftime("%d.%m.%Y"),
        "d14_str": d14_dt.strftime("%d.%m.%Y"),
        "d30_str": d30_dt.strftime("%d.%m.%Y"),
        "target_str": target_dt.strftime("%d.%m.%Y"),
        # TickTick saatleri mutlak an olarak okur: yerel (UTC+3) saat "+0000" ile yazılınca görevler 3 saat kayıyordu
        # (17:00 son gün 20:00, 09:30 duruşma 12:30 görünüyordu). Gerçek ofset yazılır: "+0300".
        "start_iso": tt_iso(gelis_dt),
        "due_iso": tt_iso(target_dt.replace(hour=CONFIG["DEADLINE_HOUR"], minute=0))
    }

def parse_hearing_datetime(hearing_date_str, hearing_time_str=""):
    """Duruşma gün ve saatini ayrıştırıp datetime ve ISO 8601 string üretir (TickTick Europe/Istanbul uyumlu)."""
    if not hearing_date_str:
        return None, None
    try:
        clean_date = hearing_date_str.strip().replace(".", "/")
        time_part = hearing_time_str.strip() if hearing_time_str else "09:00"
        dt_str = f"{clean_date} {time_part}"
        dt = datetime.strptime(dt_str, "%d/%m/%Y %H:%M")
        dt = dt.replace(tzinfo=TZ_TURKEY)
        iso_str = tt_iso(dt)
        return dt, iso_str
    except Exception:
        return None, None
