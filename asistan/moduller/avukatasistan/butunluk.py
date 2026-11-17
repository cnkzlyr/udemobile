# -*- coding: utf-8 -*-
"""Bütünlük denetimi: yarım kalan işlemlerden (bağlantı kopması, telefonun kapanması, Termux'un kapatılması)
doğabilecek bozuklukları ve mükerrerleri bulur, güvenli olanları düzeltir, kalanları raporlar.

    asistan denetim          # elle
    izleyici                 # her denetim turunda ve bağlantı kopup geri geldikten sonra kendiliğinden
    uyap-liste --uygula / calistir / takvim  # iş bitince

Ne yapar:
  1. Tebligat mükerrerleri (kimlik/barkod)        -> birleştirir (alt görevi olan kopya silinmez)
  2. Duruşma mükerrerleri (aynı esas + aynı gün)   -> birleştirir
  3. Dava kartı mükerrerleri (aynı mahkeme + esas) -> notlar/etiketler ana karta taşınır, BOŞ kopya silinir;
                                                      alt görevi olan kopyalar silinmez, raporlanır
  4. Notion'da aynı başlıkta birden çok dosya sayfası -> yalnızca raporlanır (Notion'da silme yapılmaz)
  5. Yarım kalan yazmalar (işlem günlüğü)          -> durumu kontrol edilip raporlanır
Okuma tam yapılamazsa (bağlantı) HİÇBİR şey silinmez/değiştirilmez.
"""
import re

import baglanti
import kimlik

_ESAS_RE = re.compile(r"(\d{4}/\d+)")


def _kart_anahtari(t):
    """Dava kartının (mahkeme, esas) anahtarı; kart değilse None. Kullanıcının yeniden adlandırdığı başlıktan
    bilgi okunmaz (yalnızca kimlik satırından)."""
    from ticktick_sync import is_case_card
    from utils import clean_text
    if t.get("status", 0) != 0 or t.get("parentId"):
        return None
    k = kimlik.oku(t.get("content") or "")
    if k:
        if k.get("tur") != "DOSYA" or not k.get("esas"):
            return None
        return clean_text(k.get("mahkeme", "")), k["esas"]
    baslik = (t.get("title") or "").strip()
    if not is_case_card(t):
        return None
    # Yalnızca "<Mahkeme/Daire> [-] YYYY/NNN Esas" biçimindeki başlıklar (kullanıcının serbest başlıkları değil)
    m = re.match(r"^(.*?)\s*-?\s*(\d{4}/\d+)\s+Esas\b", baslik)
    if not m or not re.search(r"Mahkemesi|Dairesi|İcra|Başkanlığı|Yargıtay|Danıştay|Bölge", m.group(1)):
        return None
    return clean_text(m.group(1).rstrip(" -")), m.group(2)


_KART_KALIP = ("⚖️ **Dava Dosyası**", "📁 **Dava Dosya Takip Kartı**", "- **Merci:**", "- **Dosya:**", "**Mahkeme:**",
               "**Esas No:**")


def kart_mukerrerlerini_birlestir(gorevler):
    """Aynı mahkeme + esas için birden çok AKTİF ana dava kartı. Ana kart: alt görevi en çok olan, eşitse en eski.
    Kopyanın etiketleri ve farklı not satırları ana karta taşınır; ALT GÖREVİ OLMAYAN kopya silinir.
    Döner: (birlesen_grup, silinen, elle_bakilacak[liste])."""
    import requests
    from config import CONFIG
    from ticktick_sync import tt_post, get_ticktick_headers
    gruplar = {}
    for t in gorevler:
        if (t.get("projectId") or t.get("_pid") or "").startswith("inbox"):
            continue
        a = _kart_anahtari(t)
        if a:
            gruplar.setdefault(a, []).append(t)
    birlesen = silinen = 0
    elle = []
    for (mahkeme, esas), liste in gruplar.items():
        if len(liste) < 2:
            continue
        liste.sort(key=lambda x: (-len(x.get("childIds") or []), x.get("createdTime") or "9999"))
        ana, kopyalar = liste[0], liste[1:]
        icerik = ana.get("content") or ""
        etiketler = list(ana.get("tags") or [])
        mevcut = {l.strip() for l in icerik.splitlines() if l.strip()}
        ek = []
        for c in kopyalar:
            for tg in c.get("tags") or []:
                if tg not in etiketler:
                    etiketler.append(tg)
            for l in (c.get("content") or "").splitlines():
                l2 = l.strip()
                if l2 and l2 not in mevcut and not kimlik.var_mi(l2) and not l2.startswith(_KART_KALIP) \
                        and not (l2.startswith(("👤 **Müvekkil:**", "**Müvekkil:**")) and any(x.startswith(("👤 **Müvekkil:**", "**Müvekkil:**")) for x in mevcut)):
                    ek.append(l2)
                    mevcut.add(l2)
        if ek or etiketler != list(ana.get("tags") or []):
            if ek:
                icerik += "\n\n📌 **BİRLEŞTİRİLEN NOTLAR (mükerrer dava kartından):**\n" + "\n".join(ek)
            tt_post(f"{CONFIG['TICKTICK_API_BASE']}/task/{ana['id']}",
                    {"id": ana["id"], "projectId": ana.get("projectId"), "content": icerik, "tags": etiketler,
                     **({"items": ana["items"]} if ana.get("items") else {})}, what="dava kartı birleştirme")
        for c in kopyalar:
            if c.get("childIds"):
                elle.append(f"{c.get('title') or ''} (alt görevli kopya; asıl kart: {ana.get('title') or ''})")
                print(f"   🛡️ Mükerrer kart silinmedi (alt görevleri var, elle taşıyın): {(c.get('title') or '')[:60]}")
                continue
            try:
                r = requests.delete(f"{CONFIG['TICKTICK_API_BASE']}/project/{c.get('projectId')}/task/{c['id']}",
                                    headers=get_ticktick_headers(), timeout=8)
                if r.status_code == 200:
                    silinen += 1
            except Exception as e:
                print(f"   ⚠️ Silinemedi ({c['id']}): {e}")
        birlesen += 1
        print(f"   🔗 Dava kartı birleştirildi: {esas} -> \"{(ana.get('title') or '')[:60]}\" ({len(kopyalar)} kopya)")
    return birlesen, silinen, elle


def notion_mukerrerleri(sayfalar=None):
    """Notion Dosyalar veritabanında aynı başlıklı sayfalar. Yalnızca rapor (silme yok). Döner: [(başlık, adet)]."""
    from utils import clean_text
    if sayfalar is None:
        from sync_uyap_excel import fetch_all_notion_pages
        sayfalar = fetch_all_notion_pages()
    sayac = {}
    for p in sayfalar:
        b = clean_text(p.get("title") or "")
        if b:
            sayac.setdefault(b, []).append(p.get("title"))
    return sorted((v[0], len(v)) for v in sayac.values() if len(v) > 1)


def yarim_islemler(gorevler, en_az_dk=10):
    """İşlem günlüğünde sonuçlanmamış yazmalar. Görev oluşturma ise TickTick'te o başlıkla görev var mı bakılır.
    Döner: [metin]. Bakılan kayıtlar 'denetlendi' işaretlenir (bir kez raporlanır)."""
    basliklar = {}
    for t in gorevler:
        basliklar[(t.get("title") or "").strip()] = basliklar.get((t.get("title") or "").strip(), 0) + 1
    rapor = []
    for k in baglanti.yarim_kalanlar(en_az_dk=en_az_dk):
        anahtar = (k.get("anahtar") or "").strip()
        durum = k.get("durum")
        if "TickTick" in (k.get("islem") or "") and k.get("olusturma"):
            n = basliklar.get(anahtar, 0)
            sonuc = "oluşmamış (bir sonraki çalışmada yeniden açılır)" if n == 0 else \
                    "oluşmuş" if n == 1 else f"{n} kopya! (mükerrer denetimi birleştirir)"
        else:
            sonuc = "sonraki çalışmada yeniden denenir" if durum != "belirsiz" else "sonucu belirsiz, kontrol edin"
        rapor.append(f"{k.get('zaman', '')} {k.get('islem', '')}: {anahtar[:70]} -> {sonuc}")
        baglanti.yarim_kalan_isaretle(k)
    return rapor


def tam_denetim(bildir=None, notion=True):
    """Hepsini çalıştırır. Okuma tam yapılamazsa BaglantiHatasi yükselir ve hiçbir şey silinmez.
    Döner: rapor sözlüğü."""
    from ticktick_sync import tum_aktif_gorevler, clean_and_merge_duplicates
    print("\n🧪 Bütünlük denetimi (yarım kalmış işler, mükerrerler, bozukluklar)...")
    rapor = {}
    gorevler = tum_aktif_gorevler(force=True)          # okunamazsa hata: aşağıda hiçbir şey yapılmaz
    rapor["yarim"] = yarim_islemler(gorevler)
    rapor["tebligat"] = clean_and_merge_duplicates()          # tebligat + duruşma mükerrerleri
    rapor["kart_birlesen"], rapor["kart_silinen"], rapor["kart_elle"] = kart_mukerrerlerini_birlestir(tum_aktif_gorevler(force=True))
    if notion:
        try:
            rapor["notion_mukerrer"] = notion_mukerrerleri()
        except Exception as e:
            if baglanti.baglanti_hatasi_mi(e):
                raise
            rapor["notion_mukerrer"] = []
            print(f"   ⚠️ Notion mükerrer kontrolü yapılamadı: {e}")
    satirlar = []
    if rapor["yarim"]:
        satirlar.append("⏸️ Yarım kalmış işlemler:\n" + "\n".join("• " + x for x in rapor["yarim"][:15]))
    if rapor["kart_birlesen"]:
        satirlar.append(f"🔗 {rapor['kart_birlesen']} mükerrer dava kartı birleştirildi ({rapor['kart_silinen']} boş kopya silindi)")
    if rapor["kart_elle"]:
        satirlar.append("🛡️ Elle bakılacak mükerrer kartlar (alt görevli):\n" + "\n".join("• " + x for x in rapor["kart_elle"][:10]))
    if rapor.get("notion_mukerrer"):
        satirlar.append("📄 Notion'da aynı başlıklı dosya sayfaları (silinmedi, kontrol edin):\n" +
                        "\n".join(f"• {b} ({n} adet)" for b, n in rapor["notion_mukerrer"][:15]))
    for s in satirlar:
        print("   " + s.replace("\n", "\n   "))
    if not satirlar:
        print("   ✅ Bozukluk/mükerrer bulunmadı.")
    if satirlar and bildir:
        metin = "🧪 Bütünlük denetimi\n" + "\n\n".join(satirlar)
        try:
            import defter
            import hashlib
            yeni = defter.uyari_yeni_mi("butunluk:" + hashlib.sha1(metin.encode("utf-8")).hexdigest(), metin)
        except Exception:
            yeni = True
        if yeni:
            bildir(metin)
    return rapor
