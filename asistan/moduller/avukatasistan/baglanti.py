# -*- coding: utf-8 -*-
"""Bağlantı dayanıklılığı: ön kontrol, kopunca bekleyip KALDIĞI YERDEN devam, belirsiz yazmaların doğrulanması,
işlem günlüğü.

Neden: Wi-Fi'den mobil veriye geçişte istekler yarıda kalır. Eskiden okuma başarısız olunca liste "boş" sayılıyor
(kopya kart/görev riski), yanıtı kaybolan bir "oluştur" isteği tekrar gönderilince aynı görev iki kez açılabiliyordu.

Kurallar:
  * OKUMA başarısızsa asla "boş" sayılmaz: kısa yeniden denemeler, sonra internet gelene kadar bekleme
    (BAGLANTI_BEKLEME_SN, varsayılan 15 dk), sonra aynı istek tekrar. Yine olmazsa BaglantiHatasi: yazma yapılmaz.
  * GÜNCELLEME/TAMAMLAMA (aynı isteği iki kez göndermek zararsız): bekle + tekrar gönder.
  * OLUŞTURMA (iki kez gönderilirse kopya oluşur): yanıt kaybolursa önce "oluşmuş mu?" diye bakılır, oluşmamışsa
    bir kez daha gönderilir.
  * Her yazma veri/islem_gunlugu.jsonl dosyasına yazılır; yarıda kalanlar bütünlük denetiminde raporlanır.
"""
import json
import os
import time
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
GUNLUK = os.path.join(HERE, "veri", "islem_gunlugu.jsonl")


class BaglantiHatasi(RuntimeError):
    """İnternet/servis, yeniden denemeler ve bekleme süresine rağmen yanıt vermedi. Yazma yapılmadan durulur;
    aynı komut yeniden çalıştırıldığında yapılmış adımlar atlanır."""
    baglanti_hatasi = True


def baglanti_hatasi_mi(e):
    return bool(getattr(e, "baglanti_hatasi", False))


def kisa_beklemeler():
    """Hızlı yeniden denemeler (sn). TICKTICK_YENIDEN_DENEME=0 ile kapatılır (testler)."""
    try:
        n = int(os.environ.get("TICKTICK_YENIDEN_DENEME", "4"))
    except ValueError:
        n = 4
    return [3, 6, 12, 24, 30, 30][:max(0, n)]


def uzun_bekleme_sn():
    """Kısa denemeler tutmazsa internetin geri gelmesi için beklenen en uzun süre (sn)."""
    try:
        return max(0, int(os.environ.get("BAGLANTI_BEKLEME_SN", "900")))
    except ValueError:
        return 900


def _uyu(sn):
    time.sleep(sn)


# ----------------------------------------------------------------------------------------------- erişilebilirlik
def erisilebilir_mi(url, timeout=6):
    """Sunucuya ulaşılabiliyor mu (yanıtın kodu önemsiz: 401 de 'ulaşıldı' demektir)."""
    u = urlparse(url)
    if not u.scheme:
        return False
    try:
        requests.get(f"{u.scheme}://{u.netloc}/", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def _hedefler():
    try:
        from config import CONFIG
        return [CONFIG.get("TICKTICK_API_BASE") or "https://api.ticktick.com/open/v1",
                CONFIG.get("NOTION_API_BASE") or "https://api.notion.com/v1"]
    except Exception:
        return ["https://api.ticktick.com/open/v1"]


def internet_var(hedef=None):
    hedefler = [hedef] if hedef else _hedefler()[:1]
    return all(erisilebilir_mi(h) for h in hedefler)


def bekle(neden="", hedef=None, en_cok_sn=None):
    """İnternet (hedef sunucu) geri gelene kadar bekler. Geldiyse True, süre dolduysa False.
    İşlem bu sırada olduğu yerde bekler; bağlantı gelince AYNI noktadan devam eder."""
    en_cok = uzun_bekleme_sn() if en_cok_sn is None else en_cok_sn
    if en_cok <= 0:
        return False
    bas = time.time()
    adim = 5
    print(f"   📶 Bağlantı yok{(' (' + neden + ')') if neden else ''}: en çok {en_cok // 60} dk bekleniyor; "
          f"gelince kaldığı yerden devam edilecek...", flush=True)
    while time.time() - bas < en_cok:
        _uyu(min(adim, max(1, en_cok - (time.time() - bas))))
        if internet_var(hedef):
            print(f"   ✅ Bağlantı geri geldi ({time.time() - bas:.0f} sn sonra), devam ediliyor.", flush=True)
            return True
        adim = min(adim * 2, 30)
    print(f"   ❌ {en_cok // 60} dk içinde bağlantı gelmedi.", flush=True)
    return False


def _hata_metni(e):
    s = str(e)
    if "NameResolution" in s or "resolve" in s:
        return "internet yok / ad çözülemedi"
    if "abort" in s.lower() or "reset" in s.lower():
        return "bağlantı koptu"
    if "timed out" in s.lower() or "Timeout" in type(e).__name__:
        return "zaman aşımı"
    return type(e).__name__


# ----------------------------------------------------------------------------------------------- 429 (istek sınırı)
# v4.9.3: TickTick "HTTP 429 Too Many Requests" verince eskiden HER süreç (UETS, TickTick düzeni, otokontrol) kendi
# başına 3-6-12-24 sn deneyip her denemeyi günlüğe yazıyordu: yüzlerce "okunamadı (HTTP 429)" satırı, sınır hiç
# açılmıyordu. Artık sınır tüm süreçlerce paylaşılan bir dosyada tutulur (sunucu adı -> "şu zamana kadar bekle");
# her süreç istekten önce bu süreyi sessizce bekler, günlüğe yalnız BİR satır yazılır.
# EN: shared cross-process rate-limit cooldown per host (file based), honours Retry-After.
def _sinir_dosyasi():
    d = os.environ.get("UYAP_VERI_DIZINI") or os.path.join(HERE, "veri")
    return os.path.join(d, "istek_siniri.json")


def _sinir_oku():
    try:
        with open(_sinir_dosyasi(), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def sinir_kalan(url):
    """Bu sunucu için paylaşılan 429 bekleme süresinden kalan saniye (0 = serbest)."""
    host = urlparse(url).netloc
    try:
        return max(0.0, float(_sinir_oku().get(host, 0)) - time.time())
    except (TypeError, ValueError):
        return 0.0


def sinir_koy(url, sn):
    host = urlparse(url).netloc
    v = _sinir_oku()
    v[host] = max(float(v.get(host) or 0), time.time() + sn)
    try:
        os.makedirs(os.path.dirname(_sinir_dosyasi()), exist_ok=True)
        gecici = _sinir_dosyasi() + f".{os.getpid()}.tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            json.dump(v, f)
        os.replace(gecici, _sinir_dosyasi())
    except OSError:
        pass


def _retry_after(r, varsayilan):
    try:
        return max(5, min(600, int(float(r.headers.get("Retry-After") or varsayilan))))
    except (TypeError, ValueError):
        return varsayilan


def oku(method, url, headers, json_body=None, timeout=15, ne="veri", hata_sinifi=BaglantiHatasi,
        kabul=(200, 404), yetki_mesaji=""):
    """Dayanıklı OKUMA. Kabul edilen kodlardan biriyle yanıt döner; olmazsa hata_sinifi fırlatır (boş SAYMAZ).
    Sıra: kısa yeniden denemeler -> internet gelene kadar bekleme -> bir tur daha kısa deneme.
    429 (istek sınırı): paylaşılan bekleme süresi konur ve SESSİZCE beklenir (en çok 3 kez); internet yok sayılmaz."""
    son = ""
    sinir_deneme = 0
    for tur in range(2):
        beklemeler = kisa_beklemeler()
        deneme = 0
        while deneme <= len(beklemeler):
            kalan = sinir_kalan(url)
            if kalan > 0 and beklemeler:
                _uyu(kalan)
            try:
                r = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
                if r.status_code in kabul:
                    return r
                if r.status_code == 429:
                    sinir_deneme += 1
                    if sinir_deneme > 3 or not beklemeler:
                        raise hata_sinifi(f"{ne}: sunucu istek sınırında (HTTP 429); birazdan kendiliğinden yeniden denenecek")
                    sn = _retry_after(r, 60 * sinir_deneme)
                    sinir_koy(url, sn)
                    if sinir_deneme == 1:
                        print(f"   ⏳ {ne}: istek sınırı (HTTP 429) — {sn} sn beklenip devam edilecek.", flush=True)
                    continue          # deneme sayacı artmaz; döngü başında paylaşılan süre beklenir
                if r.status_code in (401, 403):
                    raise hata_sinifi(yetki_mesaji or f"{ne}: erişim reddedildi (HTTP {r.status_code}), anahtarı kontrol edin")
                son = f"HTTP {r.status_code}"
            except requests.RequestException as e:
                son = _hata_metni(e)
            if deneme < len(beklemeler):
                # Yalnız ilk denemede yazılır (eskiden her denemede bir satır: günlük okunmaz hale geliyordu)
                if deneme == 0:
                    print(f"   📶 {ne} okunamadı ({son}); kısa aralıklarla yeniden deneniyor...", flush=True)
                _uyu(beklemeler[deneme])
            deneme += 1
        if tur == 0 and not bekle(ne, hedef=url):
            break
    raise hata_sinifi(f"{ne} okunamadı ({son}). İnternet gelince aynı komutu yeniden çalıştırın; "
                      f"yapılmış işler tekrar yapılmaz, kopya açılmaz.")


def yaz(method, url, headers, json_body=None, timeout=12, ne="kayıt", olusturma=False, dogrula=None, anahtar=""):
    """Dayanıklı YAZMA. Döner: (yanıt ya da None, dogrulanan_kayit ya da None).
    - Ağ hatası/5xx/429: bağlantı beklenir; güncellemede istek tekrar gönderilir.
    - Oluşturmada (olusturma=True) yanıt kaybolduysa önce dogrula() ile "zaten oluşmuş mu?" bakılır:
      oluşmuşsa o kayıt döner (kopya AÇILMAZ), oluşmamışsa istek BİR kez daha gönderilir.
    HTTP 4xx (400, 401...) yeniden denenmez: isteğin kendisi hatalıdır."""
    gunluk_yaz({"islem": ne, "anahtar": anahtar, "durum": "basladi", "olusturma": olusturma})
    son = ""
    for deneme in range(3):
        belirsiz = False
        try:
            r = requests.request(method, url, headers=headers, json=json_body, timeout=timeout)
            if r.status_code < 500 and r.status_code != 429:
                gunluk_yaz({"islem": ne, "anahtar": anahtar, "durum": "tamam" if r.status_code == 200 else f"http_{r.status_code}",
                            "id": _id(r)})
                return r, None
            son = f"HTTP {r.status_code}"
            belirsiz = r.status_code >= 500        # sunucu hatası: kayıt oluşmuş olabilir
        except requests.RequestException as e:
            son = _hata_metni(e)
            belirsiz = not isinstance(e, requests.ConnectionError) or "abort" in str(e).lower() or "reset" in str(e).lower()
        print(f"   📶 {ne} gönderilemedi ({son}).", flush=True)
        if not internet_var(url):
            if not bekle(ne, hedef=url):
                break
        else:
            _uyu(kisa_beklemeler()[0] if kisa_beklemeler() else 0)
        if olusturma and belirsiz and dogrula:
            try:
                var = dogrula()
            except Exception as e:
                print(f"   ⚠️ '{ne}' oluşmuş mu kontrol edilemedi ({e}); kopya riski nedeniyle tekrar gönderilmedi.")
                gunluk_yaz({"islem": ne, "anahtar": anahtar, "durum": "belirsiz"})
                return None, None
            if var:
                print(f"   ↪️ Yanıt kaybolmuştu ama '{ne}' zaten oluşmuş; tekrar açılmadı.", flush=True)
                gunluk_yaz({"islem": ne, "anahtar": anahtar, "durum": "dogrulandi", "id": (var or {}).get("id")})
                return None, var
    gunluk_yaz({"islem": ne, "anahtar": anahtar, "durum": "basarisiz", "hata": son})
    return None, None


def _id(r):
    try:
        return (r.json() or {}).get("id") if r.content else None
    except ValueError:
        return None


# ----------------------------------------------------------------------------------------------- işlem günlüğü
def gunluk_yaz(kayit):
    """Her yazmayı satır satır kaydeder (müvekkil verisi içerebilir: veri/ git'e girmez)."""
    if os.environ.get("ISLEM_GUNLUGU", "1") == "0":
        return
    try:
        os.makedirs(os.path.dirname(GUNLUK), exist_ok=True)
        kayit = dict(kayit, zaman=time.strftime("%Y-%m-%d %H:%M:%S"), pid=os.getpid())
        with open(GUNLUK, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        if os.path.getsize(GUNLUK) > 5 * 1024 * 1024:       # 5 MB'ı geçince son yarısı kalır
            with open(GUNLUK, encoding="utf-8") as f:
                satirlar = f.readlines()
            with open(GUNLUK, "w", encoding="utf-8") as f:
                f.writelines(satirlar[len(satirlar) // 2:])
    except Exception:
        pass


def yarim_kalanlar(en_az_dk=10):
    """Başlayıp sonuçlanmamış (süreç kapandı/telefon kapandı) ya da belirsiz kalan yazmalar.
    Döner: [{"islem", "anahtar", "durum", "zaman"}], en eski önce."""
    if not os.path.exists(GUNLUK):
        return []
    acik = {}
    try:
        with open(GUNLUK, encoding="utf-8") as f:
            for satir in f:
                try:
                    k = json.loads(satir)
                except ValueError:
                    continue
                anahtar = (k.get("pid"), k.get("islem"), k.get("anahtar"))
                if k.get("durum") == "basladi":
                    acik[anahtar] = k
                elif k.get("durum") in ("belirsiz", "basarisiz"):
                    acik[anahtar] = k
                elif k.get("durum") in ("tamam", "dogrulandi", "denetlendi") or str(k.get("durum", "")).startswith("http_"):
                    acik.pop(anahtar, None)
                    if k.get("durum") == "denetlendi":
                        for a in [a for a in acik if a[1:] == anahtar[1:]]:
                            acik.pop(a, None)
    except OSError:
        return []
    sinir = time.time() - en_az_dk * 60
    sonuc = []
    for k in acik.values():
        try:
            t = time.mktime(time.strptime(k.get("zaman", ""), "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            t = 0
        if t <= sinir:
            sonuc.append(k)
    return sorted(sonuc, key=lambda k: k.get("zaman", ""))


def yarim_kalan_isaretle(kayit):
    gunluk_yaz({"islem": kayit.get("islem"), "anahtar": kayit.get("anahtar"), "durum": "denetlendi", "pid": kayit.get("pid")})


# ----------------------------------------------------------------------------------------------- ön kontrol
def on_kontrol(ticktick=True, notion=True, bekle_sn=None, sessiz=False):
    """İşe başlamadan: internet var mı (yoksa bekler), anahtarlar geçerli mi? Döner: (tamam_mi, sorunlar).
    Anahtar hatası beklemekle düzelmez: hemen bildirilir."""
    from config import CONFIG
    sorunlar = []
    hedefler = []
    if ticktick:
        hedefler.append(("TickTick", f"{CONFIG['TICKTICK_API_BASE']}/project",
                         {"Authorization": f"Bearer {CONFIG.get('TICKTICK_TOKEN', '')}"}, "TICKTICK_TOKEN"))
    if notion and CONFIG.get("NOTION_TOKEN"):
        hedefler.append(("Notion", f"{CONFIG.get('NOTION_API_BASE') or 'https://api.notion.com/v1'}/users/me",
                         {"Authorization": f"Bearer {CONFIG['NOTION_TOKEN']}", "Notion-Version": "2022-06-28"},
                         "NOTION_TOKEN"))
    for ad, url, h, anahtar_adi in hedefler:
        if not erisilebilir_mi(url):
            if not bekle(f"{ad} ön kontrol", hedef=url, en_cok_sn=bekle_sn):
                sorunlar.append(f"{ad}: internet/sunucu yok")
                continue
        try:
            r = requests.get(url, headers=h, timeout=12)
            if r.status_code in (401, 403):
                sorunlar.append(f"{ad}: anahtar geçersiz ya da süresi dolmuş ({anahtar_adi}, HTTP {r.status_code})")
            elif r.status_code >= 500:
                sorunlar.append(f"{ad}: sunucu hatası (HTTP {r.status_code}), biraz sonra tekrar deneyin")
        except requests.RequestException as e:
            sorunlar.append(f"{ad}: {_hata_metni(e)}")
    if not sessiz:
        if sorunlar:
            print("🚦 Ön kontrol: ❌ " + "; ".join(sorunlar))
        else:
            print("🚦 Ön kontrol: ✅ internet ve " + " + ".join(a for a, *_ in hedefler) + " erişimi tamam")
    return (not sorunlar), sorunlar
