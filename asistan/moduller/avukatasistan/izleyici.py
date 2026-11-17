#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛰️ İZLEYİCİ (WATCHER): UETS + TickTick + Notion'u düzenli aralıklarla denetleyen tek arka plan süreci.

    python3 izleyici.py                     # varsayılan: UETS her 30 dk, denetim her 2 saatte bir
    python3 izleyici.py --uets-dk 15 --denetim-dk 60
    python3 izleyici.py --bir-kez           # tek tur çalış ve çık (deneme / zamanlayıcı için)
    python3 izleyici.py --tani              # her UETS turunda teşhis zip'i de üret

Her UETS turunda:
  1. UETS'ye giriş (oturum tarayıcıda canlı tutulur; her turda SMS kodu gerekmez), liste + eksik EYP'ler.
  2. Senkronizasyon: yeni tebligat -> TickTick görevi (esas nosuz olanlar dahil), Notion sütunları.
Her denetim turunda (biçimleri korur, BAŞLIKLARA DOKUNMAZ):
  3. TickTick sağlık denetimi: kimlik satırı eksik görevlere 🔖 KİMLİK (mahkeme/esas/barkod) eklenir, dava
     kartına (parent) bağlanmamış görevler bağlanır, etiketler, saat dilimi kayıkları, mükerrerler
     (kimliğe göre; kullanıcı başlığı korunarak) düzeltilir.
  4. Notion: kimliğinde esas nosu olup notunda Notion bağlantısı olmayan görevlere bağlantı eklenir.
  5. Sözleşme raporu (gatekeeper): sorunlu görevler Telegram'a özetlenir (yalnızca sorun varsa).
Bildirim: yeni görev açıldığında ve hata olduğunda Telegram (hata bildirimi saatte en fazla bir kez).
Aynı anda yalnızca bir izleyici çalışır (kilit dosyası). Termux'ta uyku kilidi (termux-wake-lock) alınır.
Kayıt: izleyici.log (5 MB'ta döner, 3 eski dosya tutulur).
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "izleyici.log")
KILIT = os.path.expanduser("~/.avukat_izleyici.lock")


class _Kayit:
    """Ekran çıktısını izleyici.log'a da yazar (zaman damgalı, 5 MB'ta döner)."""

    def __init__(self, asil):
        self.asil = asil
        self.bas = True

    def _dondur(self):
        try:
            if os.path.exists(LOG) and os.path.getsize(LOG) > 5 * 1024 * 1024:
                for i in (2, 1):
                    if os.path.exists(f"{LOG}.{i}"):
                        os.replace(f"{LOG}.{i}", f"{LOG}.{i + 1}")
                os.replace(LOG, f"{LOG}.1")
        except Exception:
            pass

    def write(self, s):
        try:
            self.asil.write(s)
        except Exception:
            pass
        if not s:
            return 0
        self._dondur()
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                for parca in s.splitlines(keepends=True):
                    f.write((datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ") if self.bas else "") + parca)
                    self.bas = parca.endswith("\n")
        except Exception:
            pass
        return len(s)

    def flush(self):
        try:
            self.asil.flush()
        except Exception:
            pass

    def __getattr__(self, ad):
        return getattr(self.asil, ad)


def kilit_al():
    """Tek örnek: ikinci izleyici açılırsa hemen çıkar."""
    import fcntl
    f = open(KILIT, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("⛔ Başka bir izleyici zaten çalışıyor (kilit: ~/.avukat_izleyici.lock). Çıkılıyor.")
        sys.exit(1)
    f.write(str(os.getpid()))
    f.flush()
    return f


_SON_HATA_BILDIRIMI = 0


def bildir(metin, hata=False):
    global _SON_HATA_BILDIRIMI
    if hata and time.time() - _SON_HATA_BILDIRIMI < 3600:
        return
    try:
        from main import send_telegram_alert
        send_telegram_alert(metin[:3500])
        if hata:
            _SON_HATA_BILDIRIMI = time.time()
    except Exception:
        pass


def uets_turu(durum, args):
    """UETS indir + senkronize et. Tarayıcı turlar arasında açık kalır (oturum korunur)."""
    from uets_downloader import setup_driver, login_and_download
    from main import run_synchronization
    import uets_tani
    if args.tani:
        uets_tani.etkinlestir()
    if durum.get("driver") is None:
        print("🌐 İzleyici tarayıcısı başlatılıyor...")
        durum["driver"] = setup_driver(headless=args.headless)
    try:
        csv_yolu = login_and_download(headless=args.headless, auto_sync=False, external_driver=durum["driver"])
    except Exception:
        # Tarayıcı çökmüş/oturum bozulmuş olabilir: bir sonraki tur temiz başlasın
        try:
            durum["driver"].quit()
        except Exception:
            pass
        durum["driver"] = None
        raise
    sonuc = run_synchronization(csv_path=csv_yolu if csv_yolu and os.path.exists(csv_yolu) else None) or {}
    if sonuc.get("yeni"):
        bildir(f"📨 UETS: {sonuc['yeni']} yeni tebligat görevi TickTick'e eklendi.")
    return sonuc


def uyap_listesi_kontrol():
    """İndirilenler'e YENİ bir UYAP dosya listesi (dosyalar*.xlsx) düştüyse kendiliğinden işler:
    deftere yazar, değişiklik özetini ve olası çatışmaları Telegram'a gönderir, Notion/TickTick'te yalnızca
    GÜVENLİ değişiklikleri uygular (durum güncelleme, yeni dosya, yeni kart). Kart kapatma onay ister:
    asistan uyap-liste --uygula. Aynı liste ikinci kez işlenmez."""
    from asistan import _en_yeni_uyap_listesi
    yol = _en_yeni_uyap_listesi()
    if not yol:
        return None
    import defter
    from sqlalchemy import select
    ozet = defter.dosya_ozeti(yol)
    with defter.motor().connect() as c:
        if c.execute(select(defter.aktarimlar.c.id).where(defter.aktarimlar.c.ozet == ozet)).first():
            return None
    print(f"\n📄 Yeni UYAP dosya listesi bulundu: {yol} (güvenli modda işleniyor)")
    from sync_uyap_excel import run_sync
    try:
        sonuc = run_sync(yol, mod="guvenli")
    except Exception:
        # Yarıda kaldı (ör. bağlantı koptu): liste "işlendi" sayılmasın, sonraki turda baştan işlensin.
        defter.aktarim_sil(ozet)
        raise
    if (sonuc or {}).get("eksik"):
        defter.aktarim_sil(ozet)
    bekleyen = (sonuc or {}).get("kart_bekleyen") or []
    if bekleyen:
        bildir("📁 Kapanan dosyalar var ama kartlarının altında açık iş duruyor (kart kapatılmadı):\n" +
               "\n".join(f"• {b['title']}" for b in bekleyen[:15]))
    return sonuc


def notion_baglantilari():
    """Kimliğinde esas nosu olup notunda Notion bağlantısı olmayan görevlere bağlantı ekler (başlığa dokunmaz)."""
    import kimlik
    from ticktick_sync import tum_aktif_gorevler, update_task_details
    from notion_sync import find_notion_case
    eklenen = 0
    for t in tum_aktif_gorevler(force=True):
        icerik = t.get("content") or ""
        k = kimlik.oku(icerik)
        if k.get("tur") not in ("TEBLİGAT", "DURUŞMA", "DOSYA") or not k.get("esas") or "notion" in icerik.lower():
            continue
        try:
            sayfa = find_notion_case(k["esas"], k.get("mahkeme", ""))
        except Exception:
            sayfa = None
        url = (sayfa or {}).get("url") if isinstance(sayfa, dict) else None
        if not url:
            continue
        satirlar = icerik.splitlines()
        satirlar.insert(1 if satirlar else 0, f"🔗 **Notion Dosyası:** {url}")
        update_task_details(t["id"], t.get("projectId") or t.get("_pid"), t.get("parentId"), content="\n".join(satirlar))
        eklenen += 1
        print(f"   🔗 Notion bağlantısı eklendi: {(t.get('title') or '')[:60]}")
    return eklenen


def sozlesme_raporu():
    """Gatekeeper kurallarına uymayan aktif görevlerin kısa özeti (yalnızca 'blok' düzeyindekiler)."""
    import gatekeeper as gk
    from ticktick_sync import tum_aktif_gorevler
    sorunlar = []
    for t in tum_aktif_gorevler():
        k = gk.infer_kind(t)
        if k == "diger":
            continue
        for kod, ciddiyet, mesaj in gk.check(t, k):
            if ciddiyet == "blok":
                sorunlar.append(f"{kod} {mesaj}: {(t.get('title') or '')[:50]}")
    return sorunlar


def denetim_turu():
    from ticktick_sync import audit_and_heal_all_tasks
    print("\n🛠️ Denetim turu: TickTick biçimleri, kimlik satırları, dava kartları, mükerrerler...")
    rapor = audit_and_heal_all_tasks() or {}
    # Yarım kalmış işler, dava kartı / Notion mükerrerleri, belirsiz yazmalar (bağlantı kopmasının izleri)
    import butunluk
    rapor["butunluk"] = butunluk.tam_denetim(bildir=bildir)
    # 🧭 Asistan notları: yalnızca kullanıcı bir kez "asistan notlar --uygula" çalıştırdıysa güncel tutulur
    import asistan_notu
    if os.path.exists(asistan_notu.DURUM):
        try:
            asistan_notu.calistir(uygula=True, sessiz=True)
        except Exception as e:
            if getattr(e, "baglanti_hatasi", False):
                raise
            print(f"   ⚠️ Asistan notları güncellenemedi: {e}")
    try:
        n = notion_baglantilari()
        print(f"   ↳ Notion bağlantısı eklenen görev: {n}")
    except Exception as e:
        print(f"   ⚠️ Notion denetimi yapılamadı: {e}")
    sorunlar = sozlesme_raporu()
    if sorunlar:
        print(f"   ⚠️ Sözleşmeye uymayan {len(sorunlar)} görev:")
        for s in sorunlar[:30]:
            print("      - " + s)
        bildir("🛰️ İzleyici denetimi: düzeltilemeyen görevler\n" + "\n".join(sorunlar[:15]))
    return rapor


def main():
    ap = argparse.ArgumentParser(description="UETS + TickTick + Notion izleyicisi")
    ap.add_argument("--uets-dk", type=int, default=30, help="UETS kontrol aralığı (dakika, varsayılan 30)")
    ap.add_argument("--denetim-dk", type=int, default=120, help="TickTick/Notion denetim aralığı (dakika, varsayılan 120)")
    ap.add_argument("--bir-kez", action="store_true", help="Bir tur çalış ve çık")
    ap.add_argument("--headless", action="store_true", help="Tarayıcıyı ekransız çalıştır")
    ap.add_argument("--tani", action="store_true", help="UETS turlarında teşhis zip'i üret")
    ap.add_argument("--uets-yok", action="store_true", help="Yalnızca denetim (UETS'ye bağlanma)")
    args = ap.parse_args()

    sys.stdout = _Kayit(sys.stdout)
    _kilit = kilit_al()  # noqa: F841  (süreç boyunca açık kalmalı)
    if shutil.which("termux-wake-lock"):
        subprocess.run(["termux-wake-lock"], check=False)
        print("🔋 Termux uyku kilidi alındı (ekran kapansa da izleyici çalışır).")
    print(f"🛰️ İZLEYİCİ BAŞLADI: UETS her {args.uets_dk} dk, denetim her {args.denetim_dk} dk. Kayıt: {LOG}")

    durum = {"driver": None}
    son_uets = son_denetim = 0.0
    import baglanti
    kesinti = False

    def _ag_sorunu(e):
        return baglanti.baglanti_hatasi_mi(e) or not baglanti.internet_var()

    try:
        while True:
            # ÖN KONTROL: internet yoksa hiçbir tur başlamaz (yarım iş olmasın); 2 dk'da bir bakılır.
            if not baglanti.internet_var():
                if not kesinti:
                    print(f"📶 {time.strftime('%H:%M')} İnternet yok: turlar bağlantı gelene kadar erteleniyor.")
                kesinti = True
                if args.bir_kez and not baglanti.bekle("izleyici"):
                    break
                if not args.bir_kez:
                    time.sleep(120)
                    continue
            if kesinti:
                print(f"✅ {time.strftime('%H:%M')} Bağlantı geri geldi: kaçırılan turlar ve bütünlük denetimi hemen yapılıyor.")
                son_denetim = 0.0
                kesinti = False
            simdi = time.time()
            if not args.uets_yok and simdi - son_uets >= args.uets_dk * 60:
                son_uets = simdi
                try:
                    uets_turu(durum, args)
                except Exception as e:
                    if _ag_sorunu(e):
                        print(f"📶 UETS turu bağlantı yüzünden yarıda kaldı; bağlantı gelince yeniden yapılacak: {e}")
                        son_uets, son_denetim, kesinti = 0.0, 0.0, True
                    else:
                        print(f"❌ UETS turu hatası: {e}\n{traceback.format_exc()}")
                        bildir(f"❌ İzleyici UETS hatası: {e}\nAyrıntı: izleyici.log (teşhis için: python3 main.py --tani)", hata=True)
            try:
                uyap_listesi_kontrol()
            except Exception as e:
                print(f"⚠️ UYAP listesi işlenemedi (sonraki turda yeniden denenecek): {e}")
                if _ag_sorunu(e):
                    son_denetim, kesinti = 0.0, True
            if simdi - durum.get("son_takvim", 0) >= args.uets_dk * 60 and os.environ.get("AJANDA_ICS_URL"):
                durum["son_takvim"] = simdi
                try:
                    import takvim
                    takvim.esitle(bildir=bildir)
                except Exception as e:
                    print(f"❌ Takvim eşitleme hatası: {e}")
                    if _ag_sorunu(e):
                        durum["son_takvim"] = 0   # geçici bağlantı sorunu: bağlantı gelince yeniden, bildirim yok
                        son_denetim, kesinti = 0.0, True
                    else:
                        bildir(f"❌ AJANDA takvimi okunamadı: {e}", hata=True)
            if not kesinti and simdi - son_denetim >= args.denetim_dk * 60:
                son_denetim = simdi
                try:
                    denetim_turu()
                except Exception as e:
                    if _ag_sorunu(e):
                        print(f"📶 Denetim turu bağlantı sorunu yüzünden ertelendi (hiçbir görev değiştirilmedi): {e}")
                        son_denetim, kesinti = 0.0, True
                    else:
                        print(f"❌ Denetim turu hatası: {e}\n{traceback.format_exc()}")
                        bildir(f"❌ İzleyici denetim hatası: {e}", hata=True)
            if kesinti and not args.bir_kez:
                time.sleep(60)
                continue
            if args.bir_kez:
                break
            # Bekleme: UETS oturumunu canlı tutmak için 3 dakikada bir hafif ziyaret
            hedef = min(son_uets + args.uets_dk * 60 if not args.uets_yok else float("inf"),
                        son_denetim + args.denetim_dk * 60)
            while time.time() < hedef:
                time.sleep(min(180, max(1, hedef - time.time())))
                if durum.get("driver") is not None and time.time() < hedef:
                    try:
                        from uets_downloader import PORTAL
                        durum["driver"].get(f"{PORTAL}/messages/1")
                    except Exception:
                        pass
    except KeyboardInterrupt:
        print("\n🛑 İzleyici durduruldu.")
    finally:
        if durum.get("driver") is not None:
            try:
                durum["driver"].quit()
            except Exception:
                pass
        if shutil.which("termux-wake-unlock"):
            subprocess.run(["termux-wake-unlock"], check=False)


if __name__ == "__main__":
    main()
