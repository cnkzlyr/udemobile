#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Notion & TickTick Canlı Entegrasyon + Otomatik UYAP Senkronizasyon Köprüsü
=========================================================================
Yalnızca Python standart kütüphanesiyle çalışır (masaüstü ve Termux'suz Android'de).
  * Gizli anahtarlar (NOTION_TOKEN, TICKTICK_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    UETS_TCKN, UETS_PASSWORD) yalnızca yerel avukatasistan/.env dosyasında (chmod 600)
    saklanır; asla git deposuna yazılmaz ve API yanıtlarında maskelenir.
  * Notion: "Tüm Dosyalar Düzenli" veritabanını sorgular, dava sayfalarına not ekler,
    "📨 Son Tebligat" ve "📅 Sıradaki Duruşma" alanlarını günceller.
  * TickTick: Projeleri ve aktif görevleri listeler, mahkeme türüne göre doğru listeye
    yasal süreli görev ekler ve görev tamamlar.
  * Otomatik Aktarım: UYAP'a düşen yeni evrak/tebligat/duruşma tek tıkla ya da nöbetçi
    taramasından otomatik olarak Notion + TickTick + Telegram'a aktarılır.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
TICKTICK_API = "https://api.ticktick.com/open/v1"
VARSAYILAN_NOTION_DB = "3bfff3541194803aa052dd2c41e4d94a"

GIZLI_ALANLAR = (
    "NOTION_TOKEN",
    "NOTION_DB_DOSYALAR",
    "TICKTICK_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "UETS_TCKN",
    "UETS_PASSWORD",
    "TICKTICK_EMAIL",
    "GMAIL_USER",
    "GMAIL_APP_PASS",
    "OZET_API_KEY",
)

# Önbellek (5 dk)
_NOTION_CACHE: tuple[float, list[dict]] = (0.0, [])
_TT_PROJ_CACHE: tuple[float, list[dict]] = (0.0, [])


def _fold(s: str) -> str:
    tr = str.maketrans({
        "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
        "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
    })
    return re.sub(r"\s+", " ", str(s or "").translate(tr).lower()).strip()


def _maskele(v: str) -> str:
    v = str(v or "").strip()
    if not v:
        return ""
    if len(v) <= 8:
        return "•" * len(v)
    return v[:4] + "••••" + v[-4:]


def env_dosyasi(avukat_dir: Path) -> Path:
    return avukat_dir / ".env"


def env_oku(avukat_dir: Path) -> dict[str, str]:
    degerler: dict[str, str] = {}
    p = env_dosyasi(avukat_dir)
    if p.is_file():
        for satir in p.read_text(encoding="utf-8", errors="replace").splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#") or "=" not in satir:
                continue
            k, v = satir.split("=", 1)
            degerler[k.strip()] = v.strip().strip('"').strip("'")
    for k in GIZLI_ALANLAR:
        if not degerler.get(k) and os.environ.get(k):
            degerler[k] = os.environ[k].strip()
    degerler.setdefault("NOTION_DB_DOSYALAR", VARSAYILAN_NOTION_DB)
    return degerler


def ayar_ozeti(avukat_dir: Path) -> dict:
    e = env_oku(avukat_dir)
    return {
        "notion_bagli": bool(e.get("NOTION_TOKEN")),
        "notion_token": _maskele(e.get("NOTION_TOKEN", "")),
        "notion_db": e.get("NOTION_DB_DOSYALAR") or VARSAYILAN_NOTION_DB,
        "ticktick_bagli": bool(e.get("TICKTICK_TOKEN")),
        "ticktick_token": _maskele(e.get("TICKTICK_TOKEN", "")),
        "telegram_bagli": bool(e.get("TELEGRAM_BOT_TOKEN") and e.get("TELEGRAM_CHAT_ID")),
        "telegram_chat_id": e.get("TELEGRAM_CHAT_ID", ""),
        "uets_bagli": bool(e.get("UETS_TCKN") and e.get("UETS_PASSWORD")),
        "gmail_bagli": bool(e.get("GMAIL_USER") and e.get("GMAIL_APP_PASS")),
        "gmail_user": e.get("GMAIL_USER", ""),
        "ticktick_email": e.get("TICKTICK_EMAIL", ""),
        "ek_gonderim_hazir": bool(e.get("GMAIL_USER") and e.get("GMAIL_APP_PASS") and e.get("TICKTICK_EMAIL")),
        "uets_tckn": _maskele(e.get("UETS_TCKN", "")),
        "otomatik_senkron": e.get("UYAP_OTO_SENKRON", "1") != "0",
        # Dosya konusu özetleri: anahtar varsa yapay zekâ, yoksa evraklardan çıkarımsal özet (dosya_ozet.py)
        "ozet_bagli": bool(e.get("OZET_API_KEY")),
        "ozet_api_key": _maskele(e.get("OZET_API_KEY", "")),
        "ozet_saglayici": e.get("OZET_SAGLAYICI", "anthropic"),
        "ozet_model": e.get("OZET_MODEL", ""),
    }


def ayar_kaydet(avukat_dir: Path, girdi: dict) -> dict:
    global _NOTION_CACHE, _TT_PROJ_CACHE
    avukat_dir.mkdir(parents=True, exist_ok=True)
    mevcut = env_oku(avukat_dir)
    esleme = {
        "notion_token": "NOTION_TOKEN",
        "notion_db": "NOTION_DB_DOSYALAR",
        "ticktick_token": "TICKTICK_TOKEN",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
        "telegram_chat_id": "TELEGRAM_CHAT_ID",
        "uets_tckn": "UETS_TCKN",
        "uets_password": "UETS_PASSWORD",
        # UETS giriş kodu (OTP) Gmail'den otomatik okunur (uets_downloader.find_latest_otp_code)
        "gmail_user": "GMAIL_USER",
        "gmail_app_pass": "GMAIL_APP_PASS",
        # v4.9.3: TickTick'e DOSYA (EYP ekleri) ancak e-postayla eklenebiliyor; adres arayüzde hiç sorulmuyordu,
        # ekler "E-posta ile görev gönderilemedi" uyarısıyla TickTick'e hiç gitmiyordu.
        "ticktick_email": "TICKTICK_EMAIL",
        "ozet_api_key": "OZET_API_KEY",
        "ozet_saglayici": "OZET_SAGLAYICI",
        "ozet_model": "OZET_MODEL",
    }
    for json_k, env_k in esleme.items():
        if json_k in girdi and str(girdi[json_k] or "").strip():
            val = str(girdi[json_k]).strip()
            if "••••" not in val:
                mevcut[env_k] = val
                os.environ[env_k] = val
    if "otomatik_senkron" in girdi:
        mevcut["UYAP_OTO_SENKRON"] = "1" if girdi["otomatik_senkron"] else "0"

    satirlar = ["# CanEditor Hukuk Asistanı gizli ayarları (git'e eklenmez, yerel cihazda saklanır)"]
    for k, v in sorted(mevcut.items()):
        if v:
            satirlar.append(f"{k}={v}")
    p = env_dosyasi(avukat_dir)
    tmp = p.with_suffix(".env.tmp")
    tmp.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    _NOTION_CACHE = (0.0, [])
    _TT_PROJ_CACHE = (0.0, [])
    return ayar_ozeti(avukat_dir)


def _http_json(method: str, url: str, headers: dict, body: dict | None = None, timeout: int = 20) -> dict | list:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ham = r.read().decode("utf-8", errors="replace").strip()
            return json.loads(ham) if ham else {}
    except urllib.error.HTTPError as e:
        detay = ""
        try:
            detay = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {detay or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Bağlantı hatası: {e.reason}") from e


# ---------------------------------------------------------------------------
# NOTION
# ---------------------------------------------------------------------------

def _notion_headers(avukat_dir: Path) -> tuple[dict, str]:
    e = env_oku(avukat_dir)
    tok = e.get("NOTION_TOKEN", "").strip()
    if not tok:
        raise ValueError("Notion API anahtarı tanımlı değil (Entegrasyonlar sekmesinden girin).")
    db_id = (e.get("NOTION_DB_DOSYALAR") or VARSAYILAN_NOTION_DB).strip()
    return {
        "Authorization": f"Bearer {tok}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }, db_id


def _prop_text(prop: dict) -> str:
    if not isinstance(prop, dict):
        return ""
    t = prop.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in prop.get("title") or [])
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop.get("rich_text") or [])
    if t == "formula":
        f = prop.get("formula") or {}
        return str(f.get("string") or f.get("number") or "")
    if t == "select":
        return (prop.get("select") or {}).get("name") or ""
    if t == "date":
        return (prop.get("date") or {}).get("start") or ""
    if t == "rollup":
        arr = (prop.get("rollup") or {}).get("array") or []
        parcalar = [_prop_text(x) for x in arr]
        return ", ".join(p for p in parcalar if p)
    return ""


def notion_dosyalar(avukat_dir: Path, q: str = "", limit: int = 100, yenile: bool = False) -> dict:
    global _NOTION_CACHE
    headers, db_id = _notion_headers(avukat_dir)
    if yenile or not _NOTION_CACHE[1] or (time.time() - _NOTION_CACHE[0] > 300):
        dosyalar: list[dict] = []
        cursor = None
        for _ in range(10):  # en çok 1000 kayıt
            payload: dict = {"page_size": 100, "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}]}
            if cursor:
                payload["start_cursor"] = cursor
            veri = _http_json("POST", f"{NOTION_API}/databases/{db_id}/query", headers, payload)
            for page in veri.get("results") or []:
                props = page.get("properties") or {}
                baslik = _prop_text(props.get("NOTION DOSYA"))
                mahkeme = _prop_text(props.get("MAHKEME/BİRİM"))
                esas = _prop_text(props.get("DOSYA NO"))
                if (not mahkeme or not esas) and " - " in baslik:
                    p = baslik.split(" - ")
                    mahkeme = mahkeme or p[0].strip()
                    esas = esas or p[-1].strip()
                durum = _prop_text(props.get("DURUM"))
                muvekkil = _prop_text(props.get("Müvekkil Adı"))
                konu = _prop_text(props.get("DOSYA KONUSU"))
                son_tebligat = _prop_text(props.get("📨 Son Tebligat"))
                durusma = _prop_text(props.get("📅 Sıradaki Duruşma"))
                dosyalar.append({
                    "page_id": page.get("id", ""),
                    "url": page.get("url", ""),
                    "baslik": baslik or f"{mahkeme} - {esas}".strip(" -"),
                    "mahkeme": mahkeme,
                    "esas_no": esas,
                    "durum": durum,
                    "muvekkil": muvekkil,
                    "konu": konu,
                    "son_tebligat": son_tebligat,
                    "durusma": durusma,
                    "son_duzenleme": page.get("last_edited_time", ""),
                })
            if not veri.get("has_more"):
                break
            cursor = veri.get("next_cursor")
        _NOTION_CACHE = (time.time(), dosyalar)

    tum = _NOTION_CACHE[1]
    kf = _fold(q)
    if kf:
        kelimeler = kf.split()
        sonuc = [d for d in tum if all(w in _fold(f"{d['baslik']} {d['mahkeme']} {d['esas_no']} {d['muvekkil']} {d['konu']} {d['durum']}") for w in kelimeler)]
    else:
        sonuc = tum
    return {"toplam": len(tum), "dosyalar": sonuc[:max(1, min(limit, 300))]}


def notion_sayfa_bul(avukat_dir: Path, esas_no: str, mahkeme: str = "") -> dict | None:
    if not esas_no:
        return None
    tum = notion_dosyalar(avukat_dir, limit=300)["dosyalar"]
    temiz_esas = esas_no.strip()
    eslesen = [d for d in tum if temiz_esas in (d["esas_no"] or "") or temiz_esas in (d["baslik"] or "")]
    if not eslesen:
        return None
    if len(eslesen) == 1 or not mahkeme:
        return eslesen[0]
    mf = _fold(mahkeme)
    for d in eslesen:
        df = _fold(d["mahkeme"])
        if df and (df in mf or mf in df):
            return d
    return eslesen[0]


def notion_not_ekle(avukat_dir: Path, page_id: str, baslik: str, metin: str,
                    son_tebligat: str = "", durusma_iso: str = "") -> dict:
    """Notion dava sayfasına zaman damgalı not bloğu ekler ve isteğe bağlı sütunları günceller."""
    headers, _ = _notion_headers(avukat_dir)
    zaman = time.strftime("%d.%m.%Y %H:%M")
    blok = {
        "children": [
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "icon": {"type": "emoji", "emoji": "⚖️"},
                    "rich_text": [
                        {"type": "text", "text": {"content": f"[{zaman}] {baslik}\n"}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": (metin or "")[:1800]}},
                    ],
                },
            }
        ]
    }
    _http_json("PATCH", f"{NOTION_API}/blocks/{page_id}/children", headers, blok)

    props: dict = {}
    if son_tebligat:
        props["📨 Son Tebligat"] = {"rich_text": [{"text": {"content": son_tebligat[:200]}}]}
    if durusma_iso and re.match(r"^\d{4}-\d{2}-\d{2}", durusma_iso):
        props["📅 Sıradaki Duruşma"] = {"date": {"start": durusma_iso[:19]}}
    if props:
        try:
            _http_json("PATCH", f"{NOTION_API}/pages/{page_id}", headers, {"properties": props})
        except RuntimeError:
            pass  # veritabanı sütunu yeniden adlandırıldıysa not yine de eklenmiş olur
    return {"ok": True, "page_id": page_id, "zaman": zaman}


# ---------------------------------------------------------------------------
# TICKTICK
# ---------------------------------------------------------------------------

def _tt_headers(avukat_dir: Path) -> dict:
    e = env_oku(avukat_dir)
    tok = e.get("TICKTICK_TOKEN", "").strip()
    if not tok:
        raise ValueError("TickTick API anahtarı tanımlı değil (Entegrasyonlar sekmesinden girin).")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def ticktick_projeler(avukat_dir: Path, yenile: bool = False) -> list[dict]:
    global _TT_PROJ_CACHE
    if not yenile and _TT_PROJ_CACHE[1] and (time.time() - _TT_PROJ_CACHE[0] < 300):
        return _TT_PROJ_CACHE[1]
    headers = _tt_headers(avukat_dir)
    ham = _http_json("GET", f"{TICKTICK_API}/project", headers)
    projeler = [{"id": p["id"], "ad": p.get("name", ""), "renk": p.get("color", ""), "kapali": bool(p.get("closed"))}
                for p in (ham if isinstance(ham, list) else []) if not p.get("closed")]
    _TT_PROJ_CACHE = (time.time(), projeler)
    return projeler


def _mahkeme_proje_id(projeler: list[dict], mahkeme: str) -> str:
    """Mahkeme adına en uygun TickTick proje ID'sini bulur."""
    mf = _fold(mahkeme)
    kurallar = [
        ("agir ceza", "agirceza"), ("asliye ceza", "asliyeceza"), ("cocuk", "cocuk"),
        ("icra ceza", "icraceza"), ("icra hukuk", "icrahukuk"), ("icra", "icratakip"),
        ("sorusturma", "sorusturma"), ("savcilik", "sorusturma"),
        ("asliye ticaret", "asliyeticaret"), ("asliye hukuk", "asliyehukuk"),
        ("sulh hukuk", "sulhhukuk"), ("is mahkeme", "ismahkeme"), ("aile", "aile"),
        ("tuketici", "tuketici"), ("kadastro", "kadastro"), ("vergi", "vergi"),
        ("idare", "idare"), ("danistay", "danistay"), ("yargitay", "yargitay"),
        ("arabuluculuk", "arabuluculuk"), ("anayasa", "aym"),
    ]
    for anahtar, hedef in kurallar:
        if anahtar in mf:
            for p in projeler:
                if hedef in _fold(p["ad"]).replace(" ", "").replace("-", ""):
                    return p["id"]
    return projeler[0]["id"] if projeler else "inbox"


def ticktick_gorevler(avukat_dir: Path, project_id: str = "", limit: int = 80) -> dict:
    headers = _tt_headers(avukat_dir)
    projeler = ticktick_projeler(avukat_dir)
    proje_map = {p["id"]: p["ad"] for p in projeler}
    hedef_ids = [project_id] if project_id else [p["id"] for p in projeler[:12]]
    gorevler: list[dict] = []
    for pid in hedef_ids:
        try:
            veri = _http_json("GET", f"{TICKTICK_API}/project/{pid}/data", headers, timeout=12)
            for t in (veri.get("tasks") or []) if isinstance(veri, dict) else []:
                if t.get("status", 0) != 0:
                    continue
                gorevler.append({
                    "id": t.get("id", ""),
                    "project_id": t.get("projectId", pid),
                    "proje": proje_map.get(t.get("projectId", pid), pid),
                    "baslik": t.get("title", ""),
                    "icerik": (t.get("content") or "")[:400],
                    "son_tarih": t.get("dueDate", ""),
                    "oncelik": int(t.get("priority") or 0),
                    "etiketler": t.get("tags") or [],
                })
        except RuntimeError:
            continue
    gorevler.sort(key=lambda x: (x["son_tarih"] or "9999", -x["oncelik"]))
    return {"projeler": projeler, "gorevler": gorevler[:limit]}


def ticktick_gorev_ekle(avukat_dir: Path, baslik: str, icerik: str = "",
                        project_id: str = "", mahkeme: str = "",
                        son_tarih_iso: str = "", oncelik: int = 3, etiketler: list[str] | None = None) -> dict:
    if not (baslik or "").strip():
        raise ValueError("Görev başlığı boş olamaz.")
    headers = _tt_headers(avukat_dir)
    if not project_id:
        project_id = _mahkeme_proje_id(ticktick_projeler(avukat_dir), mahkeme)
    payload: dict = {
        "title": baslik.strip()[:250],
        "content": (icerik or "").strip()[:3000],
        "projectId": project_id,
        "priority": int(oncelik or 0),
        "timeZone": "Europe/Istanbul",
    }
    if etiketler:
        payload["tags"] = [str(x).strip().lstrip("#") for x in etiketler if str(x).strip()]
    if son_tarih_iso:
        # YYYY-MM-DD -> TickTick ISO 8601
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?", son_tarih_iso.strip())
        if m:
            saat = m.group(2) or "17:00"
            payload["dueDate"] = f"{m.group(1)}T{saat}:00+0300"
            payload["isAllDay"] = False
    yanit = _http_json("POST", f"{TICKTICK_API}/task", headers, payload)
    return {"ok": True, "gorev": yanit, "project_id": project_id}


def ticktick_tamamla(avukat_dir: Path, project_id: str, task_id: str) -> dict:
    if not project_id or not task_id:
        raise ValueError("project_id ve task_id gerekli.")
    headers = _tt_headers(avukat_dir)
    _http_json("POST", f"{TICKTICK_API}/project/{project_id}/task/{task_id}/complete", headers, {})
    return {"ok": True, "task_id": task_id}


# ---------------------------------------------------------------------------
# OTOMATİK UYAP → NOTION + TICKTICK AKTARIMI
# ---------------------------------------------------------------------------

def telegram_gonder(avukat_dir: Path, metin: str) -> dict:
    """Kayıtlı bot ile Telegram mesajı gönderir (HTML biçimli). Yanıt: {"ok": bool, "hata": str}."""
    e = env_oku(avukat_dir)
    tok, chat = e.get("TELEGRAM_BOT_TOKEN", ""), e.get("TELEGRAM_CHAT_ID", "")
    if not (tok and chat):
        return {"ok": False, "hata": "Telegram bot token ve chat ID girilmemiş."}
    try:
        r = _http_json("POST", f"https://api.telegram.org/bot{tok}/sendMessage", {"Content-Type": "application/json"},
                       {"chat_id": chat, "text": metin[:4000], "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=15)
        if isinstance(r, dict) and r.get("ok"):
            return {"ok": True, "hata": ""}
        return {"ok": False, "hata": str((r or {}).get("description") if isinstance(r, dict) else r)[:300]}
    except Exception as ex:  # noqa: BLE001
        # Token URL içinde: hata mesajında sızmasın
        return {"ok": False, "hata": str(ex).replace(tok, "••••")[:300]}


def baglanti_testi(avukat_dir: Path) -> dict:
    """Kayıtlı tüm servisleri gerçekten dener; her biri için {"durum": "ok"|"hata"|"yok", "mesaj": ...}."""
    e = env_oku(avukat_dir)
    sonuc: dict = {}
    if e.get("NOTION_TOKEN"):
        try:
            r = notion_dosyalar(avukat_dir, limit=1, yenile=True)
            sonuc["notion"] = {"durum": "ok", "mesaj": f"{r.get('toplam', len(r.get('dosyalar', [])))} kayıt erişilebilir"}
        except Exception as ex:  # noqa: BLE001
            sonuc["notion"] = {"durum": "hata", "mesaj": str(ex)[:200]}
    else:
        sonuc["notion"] = {"durum": "yok", "mesaj": "Token girilmemiş"}
    if e.get("TICKTICK_TOKEN"):
        try:
            pr = ticktick_projeler(avukat_dir, yenile=True)
            sonuc["ticktick"] = {"durum": "ok", "mesaj": f"{len(pr)} liste"}
        except Exception as ex:  # noqa: BLE001
            sonuc["ticktick"] = {"durum": "hata", "mesaj": str(ex)[:200]}
    else:
        sonuc["ticktick"] = {"durum": "yok", "mesaj": "Token girilmemiş"}
    if e.get("TELEGRAM_BOT_TOKEN") and e.get("TELEGRAM_CHAT_ID"):
        r = telegram_gonder(avukat_dir, "🔔 <b>CanEditor</b> bağlantı testi: Telegram bildirimleri çalışıyor.")
        sonuc["telegram"] = {"durum": "ok" if r["ok"] else "hata", "mesaj": "Test mesajı gönderildi" if r["ok"] else r["hata"]}
    else:
        sonuc["telegram"] = {"durum": "yok", "mesaj": "Bot token / chat ID girilmemiş"}
    return sonuc


def _yasal_son_gun_iso(merci: str, teblig_mi: bool = False) -> str:
    mf = _fold(merci)
    gun = 7 if any(k in mf for k in ("icra", "ceza", "sorusturma", "savcilik", "kira")) else (
        30 if any(k in mf for k in ("idare", "vergi", "danistay", "bim")) else 14
    )
    bas = dt.date.today() + dt.timedelta(days=5 if teblig_mi else 0)
    hedef = bas + dt.timedelta(days=gun)
    if hedef.weekday() == 5:
        hedef += dt.timedelta(days=2)
    elif hedef.weekday() == 6:
        hedef += dt.timedelta(days=1)
    return hedef.isoformat()


def uyap_otomatik_aktar(avukat_dir: Path, birim: str, dosya_no: str, tur: str,
                        aciklama: str = "", tarih: str = "", muvekkil: str = "") -> dict:
    """Bir UYAP evrakını / tebligatını hem Notion dava sayfasına hem TickTick'e aktarır."""
    sonuc = {"notion": None, "ticktick": None, "telegram": None, "hatalar": []}
    e = env_oku(avukat_dir)
    teblig_mi = any(k in _fold(f"{tur} {aciklama}") for k in ("tebligat", "uets", "mazbata"))
    son_gun = _yasal_son_gun_iso(birim, teblig_mi=teblig_mi)
    ozet_baslik = f"📄 {tur or 'UYAP Evrakı'} — {birim} {dosya_no}".strip()
    detay = "\n".join(filter(None, [
        f"Mahkeme/Birim: {birim}" if birim else "",
        f"Dosya No: {dosya_no}" if dosya_no else "",
        f"Müvekkil: {muvekkil}" if muvekkil else "",
        f"Evrak Türü: {tur}" if tur else "",
        f"Tarih: {tarih}" if tarih else "",
        f"Açıklama: {aciklama}" if aciklama else "",
        f"Tahmini Yasal Son Gün: {son_gun} 17:00",
    ]))

    if e.get("NOTION_TOKEN"):
        try:
            sayfa = notion_sayfa_bul(avukat_dir, dosya_no, birim)
            if sayfa:
                sonuc["notion"] = notion_not_ekle(
                    avukat_dir,
                    sayfa["page_id"],
                    ozet_baslik,
                    detay,
                    son_tebligat=f"{son_gun} · {tur}" if teblig_mi else "",
                )
                sonuc["notion"]["url"] = sayfa.get("url", "")
            else:
                sonuc["hatalar"].append(f"Notion'da '{dosya_no}' ile eşleşen dava sayfası bulunamadı.")
        except Exception as ex:
            sonuc["hatalar"].append(f"Notion: {ex}")

    if e.get("TICKTICK_TOKEN"):
        etiket = ["uyap", "tebligat" if teblig_mi else "evrak"]
        try:
            # Standart yol: dosya kartının altına kimlik satırlı görev; aynı evrak için (aktif / tamamlanan /
            # yapılmayacak) görev varsa yenisi AÇILMAZ.
            import sys as _sys
            if str(avukat_dir) not in _sys.path:
                _sys.path.insert(0, str(avukat_dir))
            for _k in ("TICKTICK_TOKEN", "NOTION_TOKEN"):
                if e.get(_k):
                    os.environ.setdefault(_k, e[_k])
            import ticktick_sync as _ts  # type: ignore
            sonuc["ticktick"] = _ts.uyap_evrak_gorevi(birim, dosya_no, tur, aciklama=aciklama, tarih=tarih,
                                                      son_gun_iso=son_gun, oncelik=5 if teblig_mi else 3,
                                                      etiketler=etiket, detay=detay)
        except Exception as ex:  # noqa: BLE001
            sonuc["hatalar"].append(f"TickTick: {str(ex)[:200]}")

    # Belgede "Notion + TickTick + Telegram" yazıyordu ama Telegram'a hiç gönderilmiyordu
    if e.get("TELEGRAM_BOT_TOKEN") and e.get("TELEGRAM_CHAT_ID"):
        import html as _html
        tg = telegram_gonder(avukat_dir, f"<b>{_html.escape(ozet_baslik)}</b>\n{_html.escape(detay)}")
        sonuc["telegram"] = tg
        if not tg.get("ok"):
            sonuc["hatalar"].append(f"Telegram: {tg.get('hata')}")

    return sonuc
