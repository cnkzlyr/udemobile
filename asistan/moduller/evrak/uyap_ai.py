# -*- coding: utf-8 -*-
"""
UYAP Gemini Yapay Zeka Entegratörü (gemini-2.5-flash)
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Bu modül:
1. Google'ın en güncel ve en verimli modeli olan 'gemini-2.5-flash' ile çalışır.
2. Dava ve icra dosyalarını özetler, dosya konusunu, tarafların taleplerini ve hukuki durumu çıkarır.
3. Duruşma zaptı metinlerindeki ara kararları, kesin süreleri ve yapılacak işleri ayrıştırır.
4. ÇIKTI ÖNBELLEĞİ (ai_cache): Üretilen tüm analizler SHA-256 anahtarı ile SQLite'a kaydedilir.
   Aynı dosya veya metin tekrar görüntülendiğinde API çağrısı yapılmaz, SIFIR (0) token harcanır!
5. API Anahtarı: Ortam değişkeni (GEMINI_API_KEY), .uyap_config.json veya watcher_config.json üzerinden okunur.
"""

import os
import sys
import json
import hashlib
import sqlite3
import logging
import requests
from datetime import datetime

logger = logging.getLogger("UyapAI")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] (GeminiAI) %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "uyap_katalog.db"))
DEFAULT_MODEL = "gemini-2.5-flash"


def init_ai_table(db_path: str = DB_PATH):
    """ai_cache tablosunu oluşturur."""
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS ai_cache (
        hash_key TEXT PRIMARY KEY,
        prompt_type TEXT,
        model TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        response_text TEXT,
        created_at TEXT
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_cache_type ON ai_cache(prompt_type)")
    conn.commit()
    conn.close()


class UyapGeminiClient:
    """Gemini API istemcisi - Yerel önbellekleme ile minimum token tüketimi."""

    def __init__(self, api_key: str = None, model: str = DEFAULT_MODEL, db_path: str = DB_PATH):
        self.db_path = db_path
        self.model = model
        self.api_key = api_key or self._resolve_api_key()
        init_ai_table(self.db_path)

    def _resolve_api_key(self) -> str:
        """API anahtarını env veya config dosyalarından arar."""
        # 1. Environment variable
        key = os.environ.get("GEMINI_API_KEY")
        if key:
            return key.strip()

        # 2. .uyap_config.json
        cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".uyap_config.json"))
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("gemini_api_key"):
                        return data["gemini_api_key"].strip()
            except Exception:
                pass

        # 3. watcher_config.json
        wcfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "watcher_config.json"))
        if os.path.exists(wcfg_path):
            try:
                with open(wcfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("gemini_api_key"):
                        return data["gemini_api_key"].strip()
            except Exception:
                pass

        return ""

    def save_api_key(self, api_key: str):
        """API anahtarını yapılandırma dosyasına kaydeder."""
        self.api_key = api_key.strip()
        cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".uyap_config.json"))
        data = {}
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["gemini_api_key"] = self.api_key
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("Gemini API anahtarı .uyap_config.json dosyasına kaydedildi.")

    def _get_cache(self, hash_key: str) -> str:
        """Veritabanında kayıtlı önbellek varsa metni döndürür."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=20.0)
            cur = conn.cursor()
            cur.execute("SELECT response_text FROM ai_cache WHERE hash_key = ?", (hash_key,))
            row = cur.fetchone()
            conn.close()
            if row:
                return row[0]
        except Exception as e:
            logger.debug(f"Önbellek okuma hatası: {e}")
        return ""

    def _set_cache(self, hash_key: str, prompt_type: str, response_text: str, in_tok: int = 0, out_tok: int = 0):
        """Üretilen yanıtı önbelleğe kaydeder."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=20.0)
            cur = conn.cursor()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("""
            INSERT OR REPLACE INTO ai_cache (hash_key, prompt_type, model, input_tokens, output_tokens, response_text, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (hash_key, prompt_type, self.model, in_tok, out_tok, response_text, now_str))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug(f"Önbellek yazma hatası: {e}")

    def generate(self, prompt: str, system_instruction: str = "", prompt_type: str = "GENEL", force_refresh: bool = False) -> str:
        """Gemini API çağrısı yapar. Önbellekte varsa doğrudan döndürür (0 token harcar)."""
        # Hash hesapla
        hash_input = f"{self.model}:{prompt_type}:{system_instruction}:{prompt}".encode("utf-8")
        hash_key = hashlib.sha256(hash_input).hexdigest()

        if not force_refresh:
            cached = self._get_cache(hash_key)
            if cached:
                logger.info(f"⚡ Önbellekten getirildi ({prompt_type}) - 0 token harcandı!")
                return cached

        if not self.api_key:
            return "HATA: Gemini API anahtarı bulunamadı! Lütfen ayarlardan veya .uyap_config.json içerisine 'gemini_api_key' tanımlayın."

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        contents = []
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"SİSTEM TALİMATI:\n{system_instruction}"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Anlaşıldı. Belirtilen rol ve kurallara uygun olarak Türkçe analiz sunacağım."}]
            })

        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 2048,
            }
        }

        try:
            logger.info(f"Gemini API çağrılıyor ({self.model} - {prompt_type})...")
            resp = requests.post(url, headers=headers, json=payload, timeout=45)
            if resp.status_code != 200:
                err_msg = f"API Hatası ({resp.status_code}): {resp.text}"
                logger.error(err_msg)
                # Fallback to gemini-1.5-flash if 2.5-flash model not found
                if resp.status_code == 404 and "gemini-2.5-flash" in self.model:
                    logger.info("gemini-2.5-flash bulunamadı, gemini-1.5-flash deneniyor...")
                    self.model = "gemini-1.5-flash"
                    return self.generate(prompt, system_instruction, prompt_type, force_refresh)
                return err_msg

            data = resp.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return "Model yanıt üretmedi."

            parts = candidates[0].get("content", {}).get("parts", [])
            output_text = "".join(p.get("text", "") for p in parts).strip()

            usage = data.get("usageMetadata", {})
            in_tok = usage.get("promptTokenCount", 0)
            out_tok = usage.get("candidatesTokenCount", 0)

            # Önbelleğe kaydet
            self._set_cache(hash_key, prompt_type, output_text, in_tok, out_tok)
            logger.info(f"✓ Gemini yanıtı alındı ve önbelleğe kaydedildi. ({in_tok} in / {out_tok} out token)")
            return output_text

        except Exception as e:
            err_msg = f"Gemini Bağlantı Hatası: {e}"
            logger.error(err_msg)
            return err_msg

    def summarize_dava_dosyasi(self, dkey: str, dosya_info: dict, evraklar: list = None, safahat: list = None, finans: dict = None, force_refresh: bool = False) -> str:
        """Dava dosyasını kapsamlı bir şekilde özetler."""
        system_instruction = (
            "Sen Türk Hukukunda uzman, tecrübeli bir avukat asistanısın. "
            "Sana verilen dava dosyası bilgileri, son evraklar, safahat geçmişi ve mali durumu "
            "inceleyerek avukatın hızlıca kavrayabileceği net, profesyonel bir yönetici özeti hazırla. "
            "Markdown formatında şu başlıkları kullan:\n"
            "### 📌 Dosya Konusu ve Özeti\n"
            "### ⚖️ Taraflar ve Talepler\n"
            "### 🔄 Son Aşamalar ve Safahat Durumu\n"
            "### 💰 Masraf ve Bakiye Durumu\n"
            "### 🎯 Sıradaki İşlemler ve Tavsiyeler"
        )

        prompt = f"AŞAĞIDAKİ DAVA DOSYASINI ANALİZ ET VE ÖZETLE:\n\n"
        prompt += f"Birim: {dosya_info.get('birimAdi') or dosya_info.get('birim')}\n"
        prompt += f"Dosya No: {dosya_info.get('dosyaNo')}\n"
        prompt += f"Tür: {dosya_info.get('dosyaTur')}\n"
        prompt += f"Durum: {dosya_info.get('dosyaDurum')}\n"
        prompt += f"Açılış Tarihi: {dosya_info.get('dosyaAcilisTarihi')}\n"

        if evraklar:
            prompt += f"\nSON EVRAKLAR ({len(evraklar)} adet):\n"
            for ev in evraklar[:10]:
                prompt += f"- {ev.get('tarih', '')} | {ev.get('tur', '')} | {ev.get('aciklama', '')}\n"

        if safahat:
            prompt += f"\nSAFAHAT GEÇMİŞİ ({len(safahat)} adet):\n"
            for s in safahat[:10]:
                prompt += f"- {s.get('safahatTarihiSTR', '')} | {s.get('safahatTuruAciklama', '')}: {s.get('aciklama', '')}\n"

        if finans:
            prompt += f"\nFİNANSAL DURUM:\n"
            prompt += f"- Yatırılan Toplam: {finans.get('toplamTahsilat', 0):,.2f} TL\n"
            prompt += f"- Harcanan Masraf/Reddiyat: {finans.get('toplamReddiyat', 0):,.2f} TL\n"
            prompt += f"- Kalan Gider Avansı Bakiyesi: {finans.get('kalanBakiye', 0):,.2f} TL\n"

        return self.generate(prompt, system_instruction=system_instruction, prompt_type=f"DAVA_OZET_{dkey}", force_refresh=force_refresh)

    def summarize_icra_dosyasi(self, dkey: str, dosya_info: dict, icra_info: dict, force_refresh: bool = False) -> str:
        """İcra dosyasının kapak hesabını ve takip stratejisini analiz eder."""
        system_instruction = (
            "Sen icra ve iflas hukuku alanında uzman bir avukat danışmanısın. "
            "Sana verilen icra dosyası kapak hesabı, borçlular ve takip durumunu analiz ederek "
            "alacaklı/borçlu vekili açısından finansal tabloyu ve atılması gereken hukuki adımları özetle. "
            "Markdown formatında şu başlıkları kullan:\n"
            "### 📌 İcra Takip Kartı\n"
            "### 📊 Alacak, Masraf ve Tahsilat Tablosu\n"
            "### 🔍 Kesinleşme ve Malvarlığı Durumu\n"
            "### 🚀 Sıradaki Haciz ve Takip İşlemleri"
        )

        prompt = f"AŞAĞIDAKİ İCRA DOSYASINI ANALİZ ET:\n\n"
        prompt += f"Birim: {dosya_info.get('birimAdi') or dosya_info.get('birim')}\n"
        prompt += f"Dosya No: {dosya_info.get('dosyaNo')}\n"
        prompt += f"Takip Çıkışı (Asıl Alacak): {icra_info.get('takipKesinlesen', 0):,.2f} TL\n"
        prompt += f"Birikmiş Faiz: {icra_info.get('toplamFaiz', 0):,.2f} TL\n"
        prompt += f"Vekalet Ücreti: {icra_info.get('vekaletUcreti', 0):,.2f} TL\n"
        prompt += f"Masraflar: {icra_info.get('masrafMiktari', 0):,.2f} TL\n"
        prompt += f"Tahsil Harcı: {icra_info.get('tahsilHarci', 0):,.2f} TL\n"
        prompt += f"Toplam Alacak: {icra_info.get('toplamAlacak', 0):,.2f} TL\n"
        prompt += f"Yatan/Tahsil Edilen Para: {icra_info.get('yatanPara', 0):,.2f} TL\n"
        prompt += f"Kalan Bakiye Borç: {icra_info.get('bakiyeBorc', 0):,.2f} TL\n"
        prompt += f"Takip Kesinleşme Durumu: {icra_info.get('kesinlesmeDurumu', 'Bilinmiyor')}\n"
        prompt += f"Malvarlığı Durumu: {icra_info.get('malvarligiDurumu', '')}\n"

        borclular = icra_info.get("borclular") or []
        if borclular:
            prompt += f"Borçlular: {', '.join([b.get('ad_soyad', '') for b in borclular])}\n"

        return self.generate(prompt, system_instruction=system_instruction, prompt_type=f"ICRA_OZET_{dkey}", force_refresh=force_refresh)

    def extract_deadlines_from_zabit(self, zabit_metni: str, dkey: str = "", force_refresh: bool = False) -> str:
        """Duruşma tutanağından ara kararları, kesin süreleri ve yapılacak işleri çıkarır."""
        system_instruction = (
            "Sen Türk yargı kararlarını ve duruşma tutanaklarını inceleyen uzman bir hukuk asistanısın. "
            "Aşağıda verilen duruşma zaptı metninden 'Gereği Düşünüldü' (G.D.) ve ara karar maddelerini tek tek incele. "
            "Özellikle taraf vekillerine verilen KESİN SÜRELER, haftalık/günlük süreler (bilirkişi itirazı, beyan, delil avansı vb.) "
            "ve bir sonraki duruşma gününü yapılandırılmış JSON formatında çıkar.\n"
            "JSON Formatı:\n"
            "[\n"
            "  {\n"
            "    \"gorev\": \"Görev veya Ara Karar Tanımı\",\n"
            "    \"kime\": \"Davacı Vekili / Davalı Vekili / Bilirkişi\",\n"
            "    \"sure\": \"2 hafta kesin süre / 10 gün / bir sonraki celseye kadar\",\n"
            "    \"sonuc_ihtari\": \"Kesin süre uyarısı var mı (Vazgeçmiş sayılacağı vb.)\",\n"
            "    \"oncelik\": \"ACIL / YUKSEK / NORMAL\"\n"
            "  }\n"
            "]\n"
            "Yalnızca geçerli JSON dizisi döndür, başka açıklama yazma."
        )

        return self.generate(zabit_metni, system_instruction=system_instruction, prompt_type=f"ZABIT_ANALIZ_{dkey}", force_refresh=force_refresh)


if __name__ == "__main__":
    init_ai_table()
    client = UyapGeminiClient()
    print("Gemini AI Entegratörü hazır.")
    print(f"Aktif Model: {client.model}")
    print(f"API Anahtarı Durumu: {'Tanımlı' if client.api_key else 'Tanımlı Değil (Ayarlardan girilebilir)'}")
