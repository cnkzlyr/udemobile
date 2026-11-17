#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ AVUKAT ASİSTANI — TEK GİRİŞ NOKTASI

    python3 asistan.py                  # yardım (bu ekran)
    python3 asistan.py calistir         # BİR KEZ: UETS'den indir + TickTick/Notion'a işle
    python3 asistan.py izle             # SÜREKLİ: her 30 dk UETS, her 2 saatte denetim (arka plan)
    python3 asistan.py denetim          # BİR KEZ: biçim/kimlik + bütünlük denetimi (mükerrer, yarım kalmış işler; UETS'ye girmez)
    python3 asistan.py rapor            # SALT OKUNUR: sorunlu görevler raporu (hiçbir şeyi değiştirmez)
    python3 asistan.py uyap-liste       # UYAP dosya listesi (dosyalar.xlsx): ÖNİZLEME + dosya defteri
    python3 asistan.py uyap-liste --guvenli  # ... yalnızca güvenli değişiklikler (kart kapatmaz; izleyici bunu kullanır)
    python3 asistan.py uyap-liste --uygula   # ... hepsini UYGULA (altında açık iş olmayan kartları da kapatır)
    python3 asistan.py tani             # 'calistir' + adım adım ekran görüntüsü/kayıt zip'i (sorun bildirmek için)
    python3 asistan.py takvim           # AJANDA takvimindeki duruşmaları TickTick'e işle (erteleme/iptal dahil)
    python3 asistan.py notlar           # ÖNİZLEME: görev/Notion sayfalarının sonuna 🧭 asistan notu (bilgi + eksikler)
    python3 asistan.py notlar --uygula  # ... yaz (sizin notlarınıza dokunmaz; --en-cok 5 ile önce birkaçını deneyin)
    python3 asistan.py catisma "AD SOYAD"    # bu kişi/kurum hangi dosyalarda, hangi rolde? (yeni müvekkil öncesi)
    python3 asistan.py catisma          # olası çıkar çatışmaları (aynı dosyada karşı karşıya müvekkiller)
    python3 asistan.py defter           # dosya defteri özeti (kaç dosya, durumlar, son liste)
    python3 asistan.py defter tasi "mysql+pymysql://..."   # defteri Plesk/MySQL'e taşı
    python3 asistan.py durum            # ayarlar tamam mı? (.env anahtarları, TickTick erişimi, son çalışma)
    python3 asistan.py panel            # dokunmatik kontrol paneli (Termux:X11 gerekir)
    python3 asistan.py test             # otomatik testler (gerçek hesaplara dokunmaz)

Bu dosya yalnızca yönlendirir; işi yapan modüller aynı klasördedir (README: "Dosyalar ne işe yarar").
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _python(*arglar):
    """Aynı Python ile proje klasöründe bir betik çalıştırır, çıkış kodunu döndürür."""
    return subprocess.call([sys.executable, *arglar], cwd=HERE)


def calistir(ek):
    return _python("main.py", *ek)


def izle(ek):
    return _python("izleyici.py", *ek)


def denetim(ek):
    return _python("izleyici.py", "--bir-kez", "--uets-yok", *ek)


def rapor(ek):
    kod = _python(os.path.join("araclar", "sentinel.py"), *ek)
    print("\n" + "─" * 60)
    _python("main.py", "--autocontrol")
    return kod


def _on_kontrol(notion=True):
    """İşe başlamadan internet ve anahtarlar: internet yoksa gelene kadar bekler (yarım iş başlamasın)."""
    import baglanti
    tamam, sorunlar = baglanti.on_kontrol(notion=notion)
    if not tamam:
        print("🛑 İşlem başlatılmadı: " + "; ".join(sorunlar))
    return tamam


def uyap_liste(ek):
    """UYAP'tan indirilen dosya listesi. Yol verilmezse İndirilenler'deki en yeni dosyalar*.xlsx kullanılır."""
    uygula = "--uygula" in ek or "--apply" in ek
    yollar = [a for a in ek if not a.startswith("--")]
    yol = yollar[0] if yollar else _en_yeni_uyap_listesi()
    guvenli = "--guvenli" in ek
    if not yol:
        print("❌ UYAP dosya listesi bulunamadı. UYAP Avukat Portalı > Dosya Sorgulama > Excel'e Aktar ile indirin\n"
              "   ya da yolunu verin:  python3 asistan.py uyap-liste /sdcard/Download/dosyalar.xlsx")
        return 1
    guvenli_on = "--guvenli" in ek
    print(f"📄 Kullanılan liste: {yol}\n   Mod: " + ("UYGULA (Notion/TickTick değişir, kapanan kartlar dahil)" if uygula else
          "GÜVENLİ (durum + yeni dosya + yeni kart; kart kapatılmaz)" if guvenli_on else
          "ÖNİZLEME (Notion/TickTick'e dokunulmaz; dosya defteri güncellenir)"))
    if not _on_kontrol():
        return 3
    sys.path.insert(0, HERE)
    from sync_uyap_excel import run_sync
    run_sync(yol, mod="tam" if uygula else ("guvenli" if guvenli else "onizleme"))
    return 0


def _en_yeni_uyap_listesi():
    import glob
    try:
        from config import CONFIG
        klasorler = list(CONFIG.get("DOWNLOAD_DIRS", []))
    except Exception:
        klasorler = []
    klasorler += ["/sdcard/Download", "/sdcard/Download/Quick Share", "/sdcard/Documents",
                  os.path.expanduser("~/Downloads"), os.path.expanduser("~/storage/downloads")]
    adaylar = []
    for k in klasorler:
        for desen in ("dosyalar*.xlsx", "Dosyalar*.xlsx", "dosya_listesi*.xlsx"):
            adaylar += glob.glob(os.path.join(k, desen))
    return max(set(adaylar), key=os.path.getmtime) if adaylar else None


def tani(ek):
    return _python("main.py", "--tani", *ek)


def panel(ek):
    return subprocess.call(["bash", os.path.join(HERE, "baslat_gui.sh"), *ek], cwd=HERE)


def test(ek):
    return _python("-m", "unittest", "discover", "-s", "tests", *ek)


def durum(ek):
    """Kurulumun sağlıklı olup olmadığını tek ekranda gösterir (gizli değerleri GÖSTERMEZ)."""
    from config import CONFIG, ENV_PATH
    print("🔐 Gizli ayarlar:", ENV_PATH, "✅" if os.path.exists(ENV_PATH) else "❌ YOK")
    for ad in ("TICKTICK_TOKEN", "NOTION_TOKEN", "UETS_TCKN", "UETS_PASSWORD", "GMAIL_USER", "GMAIL_APP_PASS",
               "TICKTICK_EMAIL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        print(f"   {'✅' if CONFIG.get(ad) else '❌'} {ad}")
    print(f"   {'✅' if os.environ.get('AJANDA_ICS_URL') else '❌'} AJANDA_ICS_URL (duruşmalar takvimden)")
    print(f"   {'✅' if os.environ.get('AVUKAT_ADI') else '➖'} AVUKAT_ADI (yoksa takvimden tahmin edilir)")
    try:
        import defter
        st = defter.istatistik()
        print(f"📚 Dosya defteri: {st['dosya']} dosya, {st['tebligat']} tebligat, {st['durusma']} duruşma "
              f"({'Plesk/uzak veritabanı' if os.environ.get('DEFTER_URL') else 'tablette: veri/defter.db'})")
    except Exception as e:
        print(f"📚 Dosya defteri: ❌ {e} (pip install sqlalchemy)")
    try:
        import requests
        r = requests.get(f"{CONFIG['TICKTICK_API_BASE']}/project",
                         headers={"Authorization": f"Bearer {CONFIG['TICKTICK_TOKEN']}"}, timeout=15)
        print(f"☑️ TickTick erişimi: {'✅ tamam' if r.status_code == 200 else f'❌ HTTP {r.status_code} (anahtar geçersiz/süresi dolmuş?)'}")
    except Exception as e:
        print(f"☑️ TickTick erişimi: ❌ {e}")
    print("📁 İndirme/arşiv klasörleri:")
    for d in CONFIG.get("DOWNLOAD_DIRS", []):
        print(f"   {'✅' if os.path.isdir(d) else '—'} {d}")
    log = os.path.join(HERE, "izleyici.log")
    if os.path.exists(log):
        import time
        print(f"🛰️ İzleyici son kayıt: {time.strftime('%d.%m.%Y %H:%M', time.localtime(os.path.getmtime(log)))} ({log})")
    else:
        print("🛰️ İzleyici henüz çalıştırılmamış (python3 asistan.py izle)")
    liste = _en_yeni_uyap_listesi()
    print(f"📄 En yeni UYAP dosya listesi: {liste or 'yok'}")
    import baglanti
    yarim = baglanti.yarim_kalanlar(en_az_dk=0)
    print(f"⏸️ Yarım kalmış/sonucu belirsiz yazma: {len(yarim)}" + (" (asistan denetim ile kontrol edin)" if yarim else " ✅"))
    for k in yarim[:5]:
        print(f"   • {k.get('zaman', '')} {k.get('islem', '')}: {(k.get('anahtar') or '')[:60]} [{k.get('durum')}]")
    return 0


def notlar(ek):
    """TickTick görevlerinin ve Notion dava sayfalarının sonuna 🧭 asistan notu (yardımcı bilgi + eksikler)."""
    uygula = "--uygula" in ek
    if not _on_kontrol(notion="--notion-yok" not in ek):
        return 3
    en_cok = None
    if "--en-cok" in ek:
        try:
            en_cok = int(ek[ek.index("--en-cok") + 1])
        except (IndexError, ValueError):
            print("Kullanım: asistan notlar --uygula --en-cok 5")
            return 2
    import asistan_notu
    asistan_notu.calistir(uygula=uygula, notion="--notion-yok" not in ek, hepsi="--hepsi" in ek, en_cok=en_cok)
    return 0


def takvim_komut(ek):
    if not _on_kontrol(notion=False):
        return 3
    import takvim
    takvim.esitle()
    return 0


def catisma(ek):
    import defter
    if ek:
        ad = " ".join(ek)
        sonuc = defter.ad_ara(ad)
        if not sonuc:
            print(f"🔎 '{ad}' dosya defterinde hiçbir dosyada geçmiyor. (Defter UYAP listesinden dolar: asistan uyap-liste)")
            return 0
        print(f"🔎 '{ad}' {len(sonuc)} kayıtta geçiyor:")
        for r in sonuc:
            kim = "MÜVEKKİLİMİZ" if r["muvekkil_mi"] else ("karşı/diğer taraf" if r["muvekkil_mi"] is False else "bilinmiyor")
            print(f"   • {r['birim']} {r['esas']} [{r['durum'] or '—'}] — {r['ad']} ({r['rol']}) → {kim}"
                  + (f"; dosyanın müvekkili: {r['muvekkil']}" if r.get("muvekkil") and not r["muvekkil_mi"] else ""))
        return 0
    c = defter.catismalar()
    if not c:
        print("✅ Olası çıkar çatışması bulunmadı (aynı dosyada karşı karşıya müvekkil yok).")
    for x in c:
        print(f"⚠️ {x['dosya']} [{x['durum'] or '—'}]\n     {'; '.join(x['a_taraf'])}\n  ⟷  {'; '.join(x['b_taraf'])}")
    return 0


def defter_komut(ek):
    import defter
    if ek[:1] == ["tasi"]:
        if len(ek) < 2:
            print('Kullanım: asistan defter tasi "mysql+pymysql://KULLANICI:SIFRE@SUNUCU:3306/VERITABANI?charset=utf8mb4"')
            return 2
        sayilar = defter.tasi(ek[1])
        print("✅ Taşındı:", ", ".join(f"{k}: {v}" for k, v in sayilar.items()))
        print("Şimdi .env dosyasına  DEFTER_URL=" + ek[1] + "  satırını ekleyin; sistem bundan sonra oraya yazar.")
        return 0
    st = defter.istatistik()
    url = os.environ.get("DEFTER_URL") or defter.varsayilan_url()
    print(f"📚 Dosya defteri: {url.split('@')[-1] if '@' in url else url}")
    print(f"   Dosya: {st['dosya']} (son listede {st['listede']}) · taraf: {st['taraf']} · müvekkili belli: {st['muvekkilli_dosya']}")
    print(f"   Tebligat: {st['tebligat']} · duruşma: {st['durusma']} · işlenen UYAP listesi: {st['aktarim']}")
    print("   Durumlar: " + ", ".join(f"{d}: {n}" for d, n in st["durumlar"][:10]))
    return 0


KOMUTLAR = {
    "calistir": calistir, "izle": izle, "denetim": denetim, "rapor": rapor, "uyap-liste": uyap_liste,
    "tani": tani, "durum": durum, "panel": panel, "test": test, "catisma": catisma, "defter": defter_komut, "takvim": takvim_komut,
    "notlar": notlar,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "yardim", "yardım"):
        print(__doc__)
        return 0
    komut, ek = sys.argv[1], sys.argv[2:]
    if komut not in KOMUTLAR:
        print(f"❌ Bilinmeyen komut: {komut}\n{__doc__}")
        return 2
    try:
        return KOMUTLAR[komut](ek) or 0
    except Exception as e:
        if not getattr(e, "baglanti_hatasi", False):
            raise
        # Bağlantı koptu (ör. Wi-Fi'den mobil veriye geçiş): yarım okumayla YAZMA yapılmadan durduruldu.
        print(f"\n📶 Bağlantı sorunu, işlem güvenle durduruldu: {e}\n"
              "   Okuma tamamlanmadan kart/görev açılmadı ya da silinmedi. İnternet gelince aynı komutu tekrar\n"
              "   çalıştırın: yapılmış adımlar atlanır, kalan adımlar tamamlanır.")
        return 3


if __name__ == "__main__":
    sys.exit(main())
