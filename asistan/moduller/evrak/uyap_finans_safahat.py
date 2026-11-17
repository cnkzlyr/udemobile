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

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "uyap_katalog.db"))


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

    conn.commit()
    conn.close()


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

    def fetch_finans(self, dosya_id: str, dkey: str, birim: str = "", dosya_no: str = "") -> dict:
        """Dava dosyasının tahsilat, reddiyat, harç ve masraf hesaplarını çeker."""
        bridge = self._ensure_bridge()
        clean_id = dosya_id.strip('"\'')

        # 1. Tahsilat / Reddiyat / Harç Listeleri
        js_tr = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_tahsilat_reddiyat_bilgileri_brd.ajx', {{
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
        res_tr = bridge.eval_js(js_tr)
        if not isinstance(res_tr, dict):
            res_tr = {}

        # 2. Dosya Harç Masraf Hesabı (Ayrıntılı masraf kalemleri)
        js_hm = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_harc_masraf_hesabi.ajx', {{
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
        res_hm = bridge.eval_js(js_hm)
        if not isinstance(res_hm, dict):
            res_hm = {}

        toplam_tahsilat = float(res_tr.get("toplamTahsilat") or 0)
        toplam_reddiyat = float(res_tr.get("toplamreddiyat") or 0)
        kalan_bakiye = float(res_tr.get("toplamKalan") or 0)
        toplam_harc = float(res_tr.get("toplamTahsilHarci") or 0)
        haricen = float(res_tr.get("haricen") or 0)

        tahsilat_list = res_tr.get("tahsilatList") or []
        reddiyat_list = res_tr.get("reddiyatList") or []
        harc_list = res_tr.get("harcList") or []
        masraf_satirlar = res_hm.get("tahsilatSatirDVOList") or []

        # Harç toplamı yoksa harcList üzerinden topla
        if toplam_harc == 0 and harc_list:
            toplam_harc = sum(float(item.get("miktar") or 0) for item in harc_list)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO dosya_finans
        (dkey, birim, dosya_no, toplam_tahsilat, toplam_reddiyat, toplam_harc, kalan_bakiye, gider_avansi, haricen,
         tahsilat_list_json, reddiyat_list_json, harc_list_json, masraf_hesabi_json, son_guncelleme)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dkey, birim, dosya_no,
            toplam_tahsilat, toplam_reddiyat, toplam_harc, kalan_bakiye, kalan_bakiye, haricen,
            json.dumps(tahsilat_list, ensure_ascii=False),
            json.dumps(reddiyat_list, ensure_ascii=False),
            json.dumps(harc_list, ensure_ascii=False),
            json.dumps(masraf_satirlar, ensure_ascii=False),
            now_str
        ))
        conn.commit()
        conn.close()

        logger.info(f"[{dkey}] Finans güncellendi: Tahsilat={toplam_tahsilat:.2f} TL, Reddiyat={toplam_reddiyat:.2f} TL, Kalan={kalan_bakiye:.2f} TL")
        return {
            "toplamTahsilat": toplam_tahsilat,
            "toplamReddiyat": toplam_reddiyat,
            "toplamHarc": toplam_harc,
            "kalanBakiye": kalan_bakiye,
            "tahsilatList": tahsilat_list,
            "reddiyatList": reddiyat_list,
            "harcList": harc_list,
            "masrafSatirlar": masraf_satirlar
        }

    def fetch_icra_hesap(self, dosya_id: str, dkey: str, birim: str = "", dosya_no: str = "") -> dict:
        """İcra dosyasının kapak hesabını, borçlu listesini ve finans dökümünü çeker."""
        bridge = self._ensure_bridge()
        clean_id = dosya_id.strip('"\'')

        # 1. Dosya Kapak Hesabı (/dosya_hesap_bilgileri.ajx)
        js_dh = f"""
        (async () => {{
            try {{
                const resp = await fetch('/dosya_hesap_bilgileri.ajx', {{
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
        res_dh = bridge.eval_js(js_dh)
        hesap_kalemleri = res_dh if isinstance(res_dh, list) else []

        # Parse hesap kalemleri
        hesap_map = {}
        for item in hesap_kalemleri:
            txt = (item.get("textAlan") or "").strip()
            deg = float(item.get("degerAlan") or 0)
            hesap_map[txt] = deg

        takip_kesinlesen = hesap_map.get("Takipte Kesinlesen Miktar", 0.0)
        toplam_faiz = hesap_map.get("Toplam Faiz Miktari", 0.0)
        vekalet_ucreti = hesap_map.get("Vekalet Ücreti", 0.0)
        masraf_miktari = hesap_map.get("Masraf Miktari", 0.0)
        tahsil_harci = hesap_map.get("Tahsil Harcı", 0.0)
        toplam_alacak = hesap_map.get("Toplam Alacak", 0.0)
        yatan_para = hesap_map.get("Yatan Para", 0.0)
        bakiye_borc = hesap_map.get("Bakiye Borç Miktari", 0.0)

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
        fin = self.fetch_finans(dosya_id, dkey, birim, dosya_no)

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


if __name__ == "__main__":
    init_finans_tables()
    print("UYAP Finans, Safahat, İcra Hesap tabloları başarıyla hazırlandı.")
