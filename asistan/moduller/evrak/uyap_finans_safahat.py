# -*- coding: utf-8 -*-
"""
UYAP Finans, Safahat, İcra Hesap ve İşlemlerim Yöneticisi
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Bu modül:
1. Dava dosyalarının safahat kayıtlarını, harç/masraf detaylarını ve gider avansı bakiyelerini çeker.
2. İcra dosyalarının dosya kapak hesabını (asıl alacak, faiz, vekalet ücreti, harçlar, masraflar, 
   toplam alacak, yatan para, bakiye borç), borçlularını ve tahsilat/reddiyat dökümünü çeker.
3. Avukat sorgu bakiyesini kontrol ederek SADECE ücretsiz ve güvenli sorguları çalıştırır (kotayı zorlamaz).
4. Portal İşlemlerim kayıtlarını (yapılan talepler, gönderilen dilekçeler, durumlar) çeker.
5. Tüm verileri 'uyap_katalog.db' SQLite veritabanına kaydeder ve günceller.
"""

import os
import re
import sys
import json
import time
import sqlite3
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger("UyapFinansSafahat")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (FinansSafahat) %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
# v4.9.3: kök günlükçüye (Watcher) de iletilip her satır İKİ kez yazılıyordu: (FinansSafahat) + (Watcher)
logger.propagate = False

# Katalogla AYNI veritabanı: paketli uygulamada UYAP_VERI_DIZINI (eskiden modül klasörüne yazılıyor, sunucu
# kataloğu başka yerde okuduğunda hesaplar hiç görünmüyordu).
DB_PATH = os.path.join(os.environ.get("UYAP_VERI_DIZINI") or os.path.dirname(os.path.abspath(__file__)), "uyap_katalog.db")


def _fold(s) -> str:
    s = str(s or "").translate(str.maketrans("İIıŞşĞğÜüÖöÇçÂâÎîÛû", "iiissgguuooccaaiiuu"))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _sayi(v) -> float:
    """UYAP tutarları sayı, '1.234,56' ya da '1234.56 TL' olabilir."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    t = re.sub(r"[^0-9,.\-]", "", str(v))
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


# Kapak hesabı satırları UYAP'ta bazen Türkçe karakterli, bazen ASCII gelir ("Masraf Miktari"): katlanmış
# anahtar sözcüklerle eşlenir. Sıra önemli: ilk eşleşen alan kazanır.
_KAPAK_ALANLARI = [
    ("takip_kesinlesen_miktar", ("takipte kesinlesen", "takip miktari", "asil alacak")),
    ("toplam_faiz", ("faiz",)),
    ("vekalet_ucreti", ("vekalet",)),
    ("tahsil_harci", ("tahsil harci", "cezaevi harci")),
    ("masraf_miktari", ("masraf",)),
    ("yatan_para", ("yatan para", "tahsil edilen", "odenen")),
    ("bakiye_borc", ("bakiye", "kalan borc")),
    ("toplam_alacak", ("toplam alacak", "toplam borc", "genel toplam")),
]


def kapak_hesabi_coz(kalemler) -> dict:
    """dosya_hesap_bilgileri.ajx yanıtını alanlara ayırır (saf fonksiyon, test edilir)."""
    out = {k: 0.0 for k, _ in _KAPAK_ALANLARI}
    for item in kalemler if isinstance(kalemler, list) else []:
        if not isinstance(item, dict):
            continue
        ad = _fold(item.get("textAlan"))
        if not ad:
            continue
        for alan, anahtarlar in _KAPAK_ALANLARI:
            if any(a in ad for a in anahtarlar):
                if not out[alan]:
                    out[alan] = _sayi(item.get("degerAlan"))
                break
    if not out["toplam_alacak"]:
        out["toplam_alacak"] = round(sum(out[k] for k in ("takip_kesinlesen_miktar", "toplam_faiz", "vekalet_ucreti",
                                                          "masraf_miktari", "tahsil_harci")), 2)
    if not out["bakiye_borc"] and out["toplam_alacak"]:
        out["bakiye_borc"] = round(max(0.0, out["toplam_alacak"] - out["yatan_para"]), 2)
    return out


def _liste_tutar(item: dict) -> float:
    for k in ("miktar", "tutar", "tahsilatTutari", "reddiyatTutari", "harcTutari", "odenenMiktar", "toplamTutar", "net"):
        if isinstance(item, dict) and item.get(k) not in (None, ""):
            return _sayi(item.get(k))
    return 0.0


def _liste_ad(item: dict) -> str:
    for k in ("harcMasrafAdi", "tahsilatTuru", "reddiyatTuru", "harcTuru", "aciklama", "turu", "tur", "kalemAdi"):
        if isinstance(item, dict) and item.get(k):
            return str(item.get(k))
    return "Kalem"


def tahsilat_reddiyat_coz(res: dict) -> dict:
    """dosya_tahsilat_reddiyat_bilgileri_brd.ajx yanıtı -> toplamlar + kalem listeleri (saf fonksiyon).
    Dava dosyasında 'toplamKalan' kasada kalan (kullanılmamış) gider avansıdır = ARTAN AVANS."""
    res = res if isinstance(res, dict) else {}
    tl = res.get("tahsilatList") or []
    rl = res.get("reddiyatList") or []
    hl = res.get("harcList") or []
    tahsilat = _sayi(res.get("toplamTahsilat")) or round(sum(_liste_tutar(x) for x in tl), 2)
    reddiyat = _sayi(res.get("toplamreddiyat") or res.get("toplamReddiyat")) or round(sum(_liste_tutar(x) for x in rl), 2)
    harc = _sayi(res.get("toplamTahsilHarci")) or round(sum(_liste_tutar(x) for x in hl), 2)
    kalan = res.get("toplamKalan")
    kalan = _sayi(kalan) if kalan not in (None, "") else round(max(0.0, tahsilat - reddiyat - harc), 2)
    harclar: dict = {}
    for x in hl:
        ad = _liste_ad(x)
        harclar[ad] = round(harclar.get(ad, 0.0) + _liste_tutar(x), 2)
    return {
        "toplam_tahsilat": round(tahsilat, 2), "toplam_reddiyat": round(reddiyat, 2), "toplam_harc": round(harc, 2),
        "kalan_bakiye": round(kalan, 2), "haricen": _sayi(res.get("haricen")), "teminat": _sayi(res.get("toplamTeminat")),
        "is_icra": bool(res.get("isIcraMi")), "harc_kalemleri": [{"ad": k, "tutar": v} for k, v in harclar.items()],
        "tahsilat_list": tl, "reddiyat_list": rl, "harc_list": hl,
    }


def get_db_connection(db_path: str = DB_PATH, timeout: float = 60.0) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_finans_tables(db_path: str = DB_PATH):
    """Gerekli finans, safahat, icra hesap ve işlemlerim tablolarını oluşturur."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Safahat Tablosu
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dosya_safahat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dkey TEXT NOT NULL,
        birim TEXT,
        dosya_no TEXT,
        safahat_tarihi TEXT,
        safahat_tarihi_str TEXT,
        islem_yapan_birim TEXT,
        safahat_turu TEXT,
        aciklama TEXT,
        raw_json TEXT,
        kayit_tarihi TEXT,
        UNIQUE(dkey, safahat_tarihi_str, safahat_turu, aciklama) ON CONFLICT REPLACE
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_safahat_dkey ON dosya_safahat(dkey)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_safahat_tarih ON dosya_safahat(safahat_tarihi_str)")

    # 2. Dava Finans Tablosu (Gider Avansı, Harçlar, Masraflar)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dosya_finans (
        dkey TEXT PRIMARY KEY,
        birim TEXT,
        dosya_no TEXT,
        toplam_tahsilat REAL DEFAULT 0,
        toplam_reddiyat REAL DEFAULT 0,
        toplam_harc REAL DEFAULT 0,
        kalan_bakiye REAL DEFAULT 0,
        gider_avansi REAL DEFAULT 0,
        haricen REAL DEFAULT 0,
        tahsilat_list_json TEXT,
        reddiyat_list_json TEXT,
        harc_list_json TEXT,
        masraf_hesabi_json TEXT,
        son_guncelleme TEXT
    )
    """)

    # 3. İcra Kapak Hesabı ve Takip Bilgileri Tablosu
    cur.execute("""
    CREATE TABLE IF NOT EXISTS icra_hesap (
        dkey TEXT PRIMARY KEY,
        birim TEXT,
        dosya_no TEXT,
        takip_kesinlesen_miktar REAL DEFAULT 0,
        toplam_faiz REAL DEFAULT 0,
        vekalet_ucreti REAL DEFAULT 0,
        masraf_miktari REAL DEFAULT 0,
        tahsil_harci REAL DEFAULT 0,
        toplam_alacak REAL DEFAULT 0,
        yatan_para REAL DEFAULT 0,
        bakiye_borc REAL DEFAULT 0,
        kesinlesme_durumu TEXT,
        borclular_json TEXT,
        hesap_kalemleri_json TEXT,
        tahsilat_list_json TEXT,
        reddiyat_list_json TEXT,
        malvarligi_durumu TEXT,
        ozet_metin TEXT,
        son_guncelleme TEXT
    )
    """)

    # 4. Portal İşlemlerim Tablosu
    cur.execute("""
    CREATE TABLE IF NOT EXISTS portal_islemlerim (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        is_emir_no TEXT UNIQUE,
        is_emir_tarihi TEXT,
        birim_adi TEXT,
        dosya_no TEXT,
        islem_adi TEXT,
        isin_durumu TEXT,
        isin_sahibi TEXT,
        evrak_turu TEXT,
        raw_json TEXT,
        kayit_tarihi TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_islem_tarih ON portal_islemlerim(is_emir_tarihi)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_islem_durum ON portal_islemlerim(isin_durumu)")

    # Sonradan eklenen sütunlar (eski veritabanlarında yoksa eklenir)
    for tablo, sutun, tip in (("dosya_finans", "is_icra", "INTEGER DEFAULT 0"), ("dosya_finans", "teminat", "REAL DEFAULT 0"),
                              ("dosya_finans", "harc_kalemleri_json", "TEXT"), ("dosya_finans", "hata", "TEXT"),
                              ("icra_hesap", "hata", "TEXT")):
        try:
            cur.execute(f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tip}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


def _post_js(url: str, govde: dict) -> str:
    """UYAP'a sayfa içinden POST: oturum düşükse (HTML) {oturum:false}, UYAP hatasıysa {hata:...} döner."""
    return f"""
        (async () => {{
            try {{
                const resp = await fetch({json.dumps(url)}, {{
                    method: 'POST', headers: {{'Content-Type': 'application/json', 'Cache-Control': 'no-cache'}},
                    body: JSON.stringify({json.dumps(govde)})
                }});
                const txt = await resp.text();
                if (!resp.ok || /^\\s*</.test(txt)) return {{oturum: false, http: resp.status}};
                const d = JSON.parse(txt);
                if (d && !Array.isArray(d) && d.errorCode) return {{hata: String(d.error || d.errorCode)}};
                return d;
            }} catch(e) {{
                return {{hata: String(e)}};
            }}
        }})()
        """


def icra_mi(birim: str = "", dosya_tur: str = "") -> bool:
    """İcra DAİRESİ dosyası mı (İcra Hukuk Mahkemesi bir mahkemedir, kapak hesabı yoktur)."""
    b, t = _fold(birim), _fold(dosya_tur)
    if "icra dairesi" in b or "icra mudurlugu" in b or "iflas" in b:
        return True
    return "icra" in t and "mahkeme" not in b and "dava" not in t


class UyapFinansSafahatManager:
    """UYAP finans, safahat, icra kapak hesabı ve işlemlerim verilerini yönetir."""

    def __init__(self, bridge=None, db_path: str = DB_PATH):
        self.bridge = bridge
        self.db_path = db_path
        init_finans_tables(self.db_path)

    def _ensure_bridge(self):
        if not self.bridge:
            from uyap_indirici import UyapBrowserBridge
            self.bridge = UyapBrowserBridge(port=9223)
        return self.bridge

    def get_avukat_sorgu_bakiyesi(self) -> float:
        """Avukatın kalan sorgu bakiyesini kontrol eder (TL)."""
        bridge = self._ensure_bridge()
        try:
            res = bridge.eval_js("""
            (async () => {
                try {
                    const resp = await fetch('/avukatBakiyeSorgula.ajx', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({})
                    });
                    return await resp.json();
                } catch(e) {
                    return {error: String(e)};
                }
            })()
            """)
            if isinstance(res, list) and res:
                val = res[0].get("value", "0")
                return float(str(val).replace(",", "."))
        except Exception as e:
            logger.debug(f"Sorgu bakiyesi okunamadı: {e}")
        return 0.0

    def fetch_safahat(self, dosya_id: str, dkey: str, birim: str = "", dosya_no: str = "") -> list:
        """Dosyanın safahat geçmişini çeker ve veritabanına kaydeder."""
        bridge = self._ensure_bridge()
        clean_id = dosya_id.strip('"\'')
        js = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_safahat_bilgileri_brd.ajx', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{dosyaId: {json.dumps(clean_id)}}})
                }});
                return await resp.json();
            }} catch(e) {{
                return {{error: String(e)}};
            }}
        }})()
        """
        res = bridge.eval_js(js)
        if not isinstance(res, dict) or "safahatlar" not in res:
            return []

        safahatlar = res.get("safahatlar") or []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        saved = 0
        for s in safahatlar:
            s_tarih = s.get("safahatTarihi", "")
            s_tarih_str = s.get("safahatTarihiSTR", "")
            s_birim = s.get("islemYapanBirim", birim)
            s_tur = s.get("safahatTuruAciklama", "")
            s_aciklama = s.get("aciklama", "")
            raw = json.dumps(s, ensure_ascii=False)

            cur.execute("""
            INSERT OR REPLACE INTO dosya_safahat 
            (dkey, birim, dosya_no, safahat_tarihi, safahat_tarihi_str, islem_yapan_birim, safahat_turu, aciklama, raw_json, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dkey, birim, dosya_no, s_tarih, s_tarih_str, s_birim, s_tur, s_aciklama, raw, now_str))
            saved += 1

        conn.commit()
        conn.close()
        logger.info(f"[{dkey}] {saved} safahat kaydı kaydedildi.")
        return safahatlar

    def _istek(self, url: str, govde: dict):
        res = self._ensure_bridge().eval_js(_post_js(url, govde), timeout=45.0)
        if isinstance(res, dict) and res.get("oturum") is False:
            raise RuntimeError("UYAP oturumu kapalı")
        return res

    def fetch_finans(self, dosya_id: str, dkey: str, birim: str = "", dosya_no: str = "", is_icra: bool | None = None) -> dict:
        """Dosyanın tahsilat, reddiyat, harç kalemleri ve kasada kalan (artan) avansını UYAP'tan çeker."""
        clean_id = dosya_id.strip('"\'')
        res_tr = self._istek('/dosya_tahsilat_reddiyat_bilgileri_brd.ajx', {"dosyaId": clean_id})
        if isinstance(res_tr, dict) and res_tr.get("hata"):
            # Bazı dosya türlerinde dosyaTurKod zorunlu: icra 35 (İcra Dosyası), diğerleri 1 ile yeniden dene
            res_tr = self._istek('/dosya_tahsilat_reddiyat_bilgileri_brd.ajx',
                                 {"dosyaId": clean_id, "dosyaTurKod": 35 if is_icra else 1})
        hata = res_tr.get("hata") if isinstance(res_tr, dict) and res_tr.get("hata") else None
        res_hm = self._istek('/dosya_harc_masraf_hesabi.ajx', {"dosyaId": clean_id})
        if not isinstance(res_hm, dict) or res_hm.get("hata"):
            res_hm = {}
        coz = tahsilat_reddiyat_coz(res_tr if not hata else {})
        if is_icra is None:
            is_icra = coz["is_icra"]
        masraf_satirlar = res_hm.get("tahsilatSatirDVOList") or res_hm.get("masrafList") or []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection(self.db_path)
        conn.execute("""
        INSERT OR REPLACE INTO dosya_finans
        (dkey, birim, dosya_no, toplam_tahsilat, toplam_reddiyat, toplam_harc, kalan_bakiye, gider_avansi, haricen,
         tahsilat_list_json, reddiyat_list_json, harc_list_json, masraf_hesabi_json, son_guncelleme,
         is_icra, teminat, harc_kalemleri_json, hata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dkey, birim, dosya_no, coz["toplam_tahsilat"], coz["toplam_reddiyat"], coz["toplam_harc"],
            coz["kalan_bakiye"], 0.0 if is_icra else coz["kalan_bakiye"], coz["haricen"],
            json.dumps(coz["tahsilat_list"], ensure_ascii=False), json.dumps(coz["reddiyat_list"], ensure_ascii=False),
            json.dumps(coz["harc_list"], ensure_ascii=False), json.dumps(masraf_satirlar, ensure_ascii=False),
            now_str, 1 if is_icra else 0, coz["teminat"], json.dumps(coz["harc_kalemleri"], ensure_ascii=False), hata,
        ))
        conn.commit()
        conn.close()
        (logger.info if (coz['toplam_tahsilat'] or coz['toplam_reddiyat'] or coz['kalan_bakiye']) else logger.debug)(f"[{dkey}] Finans güncellendi: Tahsilat={coz['toplam_tahsilat']:.2f} TL, Reddiyat={coz['toplam_reddiyat']:.2f} TL, Kalan={coz['kalan_bakiye']:.2f} TL")
        return {
            "toplamTahsilat": coz["toplam_tahsilat"], "toplamReddiyat": coz["toplam_reddiyat"],
            "toplamHarc": coz["toplam_harc"], "kalanBakiye": coz["kalan_bakiye"],
            "tahsilatList": coz["tahsilat_list"], "reddiyatList": coz["reddiyat_list"], "harcList": coz["harc_list"],
            "harcKalemleri": coz["harc_kalemleri"], "masrafSatirlar": masraf_satirlar, "hata": hata,
        }

    def fetch_icra_hesap(self, dosya_id: str, dkey: str, birim: str = "", dosya_no: str = "") -> dict:
        """İcra dosyasının kapak hesabını, borçlu listesini ve finans dökümünü çeker."""
        bridge = self._ensure_bridge()
        clean_id = dosya_id.strip('"\'')

        # 1. Dosya Kapak Hesabı (/dosya_hesap_bilgileri.ajx)
        res_dh = self._istek('/dosya_hesap_bilgileri.ajx', {"dosyaId": clean_id})
        hesap_kalemleri = res_dh if isinstance(res_dh, list) else []
        k = kapak_hesabi_coz(hesap_kalemleri)
        takip_kesinlesen = k["takip_kesinlesen_miktar"]
        toplam_faiz = k["toplam_faiz"]
        vekalet_ucreti = k["vekalet_ucreti"]
        masraf_miktari = k["masraf_miktari"]
        tahsil_harci = k["tahsil_harci"]
        toplam_alacak = k["toplam_alacak"]
        yatan_para = k["yatan_para"]
        bakiye_borc = k["bakiye_borc"]

        # 2. Borçlular Listesi (/dosya_borclu_list.ajx)
        js_bl = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_borclu_list.ajx', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{dosyaId: {json.dumps(clean_id)}}})
                }});
                return await resp.json();
            }} catch(e) {{
                return {{error: String(e)}};
            }}
        }})()
        """
        res_bl = bridge.eval_js(js_bl)
        borclular = []
        if isinstance(res_bl, list):
            for b in res_bl:
                kdvo = b.get("kisiTumDVO") or {}
                borclular.append({
                    "ad_soyad": f"{kdvo.get('adi', '')} {kdvo.get('soyadi', '')}".strip() or kdvo.get("unvan", ""),
                    "tc": kdvo.get("tcKimlikNo", "") or kdvo.get("vergiNo", ""),
                    "id": b.get("kisiKurumId", "")
                })

        # 3. Kesinleşme Durumu Kontrolü (/dosya_icra_kesinlesme_bilgileri_brd.ajx)
        js_kd = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_icra_kesinlesme_bilgileri_brd.ajx', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{dosyaId: {json.dumps(clean_id)}}})
                }});
                return await resp.json();
            }} catch(e) {{
                return {{error: String(e)}};
            }}
        }})()
        """
        res_kd = bridge.eval_js(js_kd)
        kesinlesme_str = "Bilinmiyor"
        if isinstance(res_kd, dict):
            if res_kd.get("basarilimi") is True:
                kesinlesme_str = "Kesinleşti"
            else:
                sonuc = res_kd.get("islemSonucu", "")
                if sonuc == "A":
                    kesinlesme_str = "Tebligat / Kesinleşme Bekleniyor"
                elif sonuc == "B":
                    kesinlesme_str = "Borçlu Vekili / Takip Askıda"
                else:
                    kesinlesme_str = "Kesinleşmedi"

        # 4. Tahsilat / Reddiyat dökümü
        fin = self.fetch_finans(dosya_id, dkey, birim, dosya_no, is_icra=True)
        if not yatan_para and fin.get("toplamTahsilat"):
            yatan_para = fin["toplamTahsilat"]
            bakiye_borc = round(max(0.0, toplam_alacak - yatan_para), 2)

        # 5. Malvarlığı / Ücretsiz Sorgu Kontrolü
        # KULLANICI ŞARTI: Sorgu sınırlarına dikkat et, ücretsiz sorgu kullan sadece, olmuyorsa zorlama!
        malvarligi_durumu = "Kesinleşme olmadığından sorgu yapılmadı"
        if kesinlesme_str == "Kesinleşti":
            bakiye = self.get_avukat_sorgu_bakiyesi()
            if bakiye > 0:
                malvarligi_durumu = f"Ücretsiz/Yetkili Sorgu Uygun (Bakiye: {bakiye:.2f} TL)"
            else:
                malvarligi_durumu = "Sorgu Bakiyesi Yetersiz (Ücretsiz sınır)"

        # Özet metin oluştur
        ozet_metin = (
            f"İcra Takip Özeti: {birim} - {dosya_no}\n"
            f"• Takip Çıkışı (Asıl Alacak): {takip_kesinlesen:,.2f} TL\n"
            f"• Birikmiş Faiz: {toplam_faiz:,.2f} TL | Vekalet Ücreti: {vekalet_ucreti:,.2f} TL\n"
            f"• Masraf: {masraf_miktari:,.2f} TL | Tahsil Harcı: {tahsil_harci:,.2f} TL\n"
            f"• Toplam Alacak Tutarı: {toplam_alacak:,.2f} TL\n"
            f"• Yapılan Tahsilat (Yatan): {yatan_para:,.2f} TL\n"
            f"• Kalan Bakiye Borç: {bakiye_borc:,.2f} TL\n"
            f"• Takip Durumu: {kesinlesme_str} | Malvarlığı: {malvarligi_durumu}\n"
            f"• Borçlu(lar): {', '.join([b['ad_soyad'] for b in borclular]) if borclular else 'Kayıtlı borçlu yok'}"
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO icra_hesap
        (dkey, birim, dosya_no, takip_kesinlesen_miktar, toplam_faiz, vekalet_ucreti, masraf_miktari,
         tahsil_harci, toplam_alacak, yatan_para, bakiye_borc, kesinlesme_durumu, borclular_json,
         hesap_kalemleri_json, tahsilat_list_json, reddiyat_list_json, malvarligi_durumu, ozet_metin, son_guncelleme)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dkey, birim, dosya_no,
            takip_kesinlesen, toplam_faiz, vekalet_ucreti, masraf_miktari,
            tahsil_harci, toplam_alacak, yatan_para, bakiye_borc,
            kesinlesme_str, json.dumps(borclular, ensure_ascii=False),
            json.dumps(hesap_kalemleri, ensure_ascii=False),
            json.dumps(fin.get("tahsilatList", []), ensure_ascii=False),
            json.dumps(fin.get("reddiyatList", []), ensure_ascii=False),
            malvarligi_durumu, ozet_metin, now_str
        ))
        conn.commit()
        conn.close()

        logger.info(f"[{dkey}] İcra kapak hesabı güncellendi: Alacak={toplam_alacak:,.2f} TL, Kalan Borç={bakiye_borc:,.2f} TL")
        return {
            "takipKesinlesen": takip_kesinlesen,
            "toplamFaiz": toplam_faiz,
            "vekaletUcreti": vekalet_ucreti,
            "masrafMiktari": masraf_miktari,
            "tahsilHarci": tahsil_harci,
            "toplamAlacak": toplam_alacak,
            "yatanPara": yatan_para,
            "bakiyeBorc": bakiye_borc,
            "kesinlesmeDurumu": kesinlesme_str,
            "borclular": borclular,
            "malvarligiDurumu": malvarligi_durumu,
            "ozetMetin": ozet_metin
        }

    def hesaplari_tazele(self, limit: int = 10, en_eski_saat: float = 24.0, dkeyler: list | None = None,
                         durdur=None, ilerleme=None) -> dict:
        """Hesabı hiç çekilmemiş ya da en_eski_saat'ten eski dosyaların hesaplarını UYAP'tan çeker.
        Açık dosyalar ve icra dosyaları önce. Oturum düşerse durur (sonraki turda kaldığı yerden)."""
        conn = get_db_connection(self.db_path)
        try:
            esik = (datetime.now() - timedelta(hours=en_eski_saat)).strftime("%Y-%m-%d %H:%M:%S")
            if dkeyler:
                ph = ",".join("?" * len(dkeyler))
                rows = conn.execute(f"SELECT dkey, birim, dosya_no, dosya_tur, dosya_id, durum FROM dosya WHERE dkey IN ({ph})",
                                    list(dkeyler)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT d.dkey, d.birim, d.dosya_no, d.dosya_tur, d.dosya_id, d.durum FROM dosya d
                    LEFT JOIN dosya_finans f ON f.dkey = d.dkey
                    WHERE COALESCE(d.dosya_id,'') != '' AND (f.son_guncelleme IS NULL OR f.son_guncelleme < ?)
                    ORDER BY CASE WHEN d.durum='Açık' THEN 0 ELSE 1 END,
                             CASE WHEN d.birim LIKE '%İcra%' OR d.birim LIKE '%icra%' THEN 0 ELSE 1 END,
                             CASE WHEN f.son_guncelleme IS NULL THEN 0 ELSE 1 END, f.son_guncelleme
                    LIMIT ?""", (esik, max(1, int(limit)))).fetchall()
        except sqlite3.OperationalError:
            rows = []
        finally:
            conn.close()
        sonuc = {"denenen": len(rows), "basarili": 0, "hata": 0, "icra": 0}
        for i, r in enumerate(rows):
            if durdur and durdur():
                break
            if not r["dosya_id"]:
                continue
            ic = icra_mi(r["birim"], r["dosya_tur"])
            try:
                if ic:
                    self.fetch_icra_hesap(r["dosya_id"], r["dkey"], r["birim"], r["dosya_no"])
                    # Safahat: ödeme/icra emri tebliğleri, itirazlar, haciz ve sorgu işlemleri burada görünür;
                    # kesinleşme ve takipsizlik analizi (icra_analiz) buna dayanır.
                    try:
                        self.fetch_safahat(r["dosya_id"], r["dkey"], r["birim"], r["dosya_no"])
                    except Exception as e:  # noqa: BLE001
                        logger.warning("[%s] Safahat alınamadı: %s", r["dkey"], e)
                    sonuc["icra"] += 1
                else:
                    self.fetch_finans(r["dosya_id"], r["dkey"], r["birim"], r["dosya_no"], is_icra=False)
                sonuc["basarili"] += 1
            except RuntimeError as e:
                logger.warning("Hesap çekme durdu: %s", e)
                sonuc["hata"] += 1
                sonuc["oturum"] = False
                break
            except Exception as e:  # noqa: BLE001
                sonuc["hata"] += 1
                logger.warning("[%s] Hesap çekilemedi: %s", r["dkey"], e)
            if ilerleme:
                ilerleme(i + 1, len(rows))
        return sonuc

    def fetch_portal_islemlerim(self, days_back: int = 30) -> list:
        """Avukatın portal üzerindeki son işlemlerini çeker ve veritabanına kaydeder."""
        bridge = self._ensure_bridge()

        # TCKN config'den al
        cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".uyap_config.json"))
        tckn = ""
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    tckn = json.load(f).get("tc", "")
            except Exception:
                pass

        today = date.today()
        start_date = (today - timedelta(days=days_back)).strftime("%d.%m.%Y")
        end_date = today.strftime("%d.%m.%Y")

        js = f"""
        (async () => {{
            try {{
                const resp = await fetch('/uyap_islem_sorgula.ajx', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{
                        tcKimlikNo: {json.dumps(tckn)},
                        islemTuru: null,
                        isEmirNo: null,
                        baslangicTarihi: {json.dumps(start_date)},
                        bitisTarihi: {json.dumps(end_date)}
                    }})
                }});
                return await resp.json();
            }} catch(e) {{
                return {{error: String(e)}};
            }}
        }})()
        """
        res = bridge.eval_js(js)
        if not isinstance(res, list):
            logger.warning(f"İşlemlerim sorgusu başarısız veya boş: {res}")
            return []

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        saved = 0

        for item in res:
            emir_no = str(item.get("isEmirNo") or "")
            emir_tarihi = item.get("isEmirTarihi", "")
            birim_adi = item.get("birimAdi", "")
            dosya_no = item.get("dosyaNo", "")
            islem_adi = item.get("name", "")
            isin_durumu = item.get("isinDurumu", "")
            isin_sahibi = item.get("isinSahibi", "")
            evrak_turu = item.get("evrakTuru", "")
            raw = json.dumps(item, ensure_ascii=False)

            cur.execute("""
            INSERT OR REPLACE INTO portal_islemlerim
            (is_emir_no, is_emir_tarihi, birim_adi, dosya_no, islem_adi, isin_durumu, isin_sahibi, evrak_turu, raw_json, kayit_tarihi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (emir_no, emir_tarihi, birim_adi, dosya_no, islem_adi, isin_durumu, isin_sahibi, evrak_turu, raw, now_str))
            saved += 1

        conn.commit()
        conn.close()
        logger.info(f"Portal İşlemlerim: {saved} işlem kaydedildi/güncellendi.")
        return res




def _cli() -> int:
    """asistan görevi 'hesap-tara': UYAP hesaplarını (icra kapak, tahsilat/reddiyat, harç, artan avans) çeker.
    Görünür tarayıcı AÇMAZ: CanEditor'un gizli UYAP oturumunu (CDP 9223) kullanır."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dkey", action="append", default=[])
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--saat", type=float, default=0.0, help="Bu kadar saatten yeni hesapları atla (0: hepsini tazele)")
    a = ap.parse_args()
    os.environ.setdefault("CANASISTAN_GORUNMEZ", "1")
    import uyap_indirici as ui
    from uyap_watcher import _kayitli_pin
    bridge = ui.UyapBrowserBridge(port=ui.CDP_PORT)
    ok, msg = bridge.ensure_ready("uyap")
    if not ok:
        print(f"[!] UYAP tarayıcısına bağlanılamadı: {msg}", flush=True)
        return 2
    if not bridge.is_logged_in():
        print("[i] UYAP oturumu kapalı; arka planda giriş yapılıyor (e-İmza takılıysa e-İmza, değilse Mobil İmza)...", flush=True)
        ok, msg = bridge.akilli_oturum_ac(pin=_kayitli_pin(ui), status_cb=lambda m: print(m, flush=True), sure_siniri_s=900)
        if not ok:
            print(f"[!] UYAP oturumu açılamadı: {msg}", flush=True)
            return 3
    m = UyapFinansSafahatManager(bridge=bridge)
    d = m.hesaplari_tazele(limit=a.limit, en_eski_saat=a.saat, dkeyler=a.dkey or None,
                           ilerleme=lambda i, n: print(f"  ↳ {i}/{n} dosya", flush=True))
    print(f"[✓] {d['basarili']}/{d['denenen']} dosyanın hesabı çekildi ({d['icra']} icra, {d['hata']} hata).", flush=True)
    return 3 if d.get("oturum") is False else 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(_cli())
    init_finans_tables()
    print("UYAP Finans, Safahat, İcra Hesap tabloları başarıyla hazırlandı.")
