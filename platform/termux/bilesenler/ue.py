#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
"""UYAP Doküman / Şablon Editörü başlatıcısı (Termux + Termux:X11, Linux masaüstü).

  python3 ue.py [belge.udf|sablon.usf ...]   editörü açar (açıksa belgeyi açık editörde açar)
  python3 ue.py --oku belge.udf              belgenin düz metnini panoya kopyalar
  python3 ue.py --doc belge.udf              belgeyi Word'ün açabildiği .doc (HTML) olarak dışa aktarır
  python3 ue.py --tani                       Java/jar/ayar/e-imza durumunu yazar (sorun giderme)
  python3 ue.py --panel                      Kontrol Merkezi (durum + ayarlar penceresi)
  python3 ue.py --derle                      Java bileşenlerini derler ve çıkar (kurulum doğrulaması)
  python3 ue.py --surum

Ayarlar: ~/.config/uyap-termux/ayarlar.ini  (yoksa varsayılanlarla oluşturulur; 'uyap ayarlar' ile düzenlenir)
Ortam değişkenleri: UYAP_TEMA, UYAP_OLCEK, UYAP_TEK_ORNEK=0, UYAP_AYRINTI=1, UYAP_JAVA, EIMZA_DIR
"""
import configparser
import glob
import hashlib
import html
import os
import shutil
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile

SURUM = "2.0.0"
CKZ_KIMLIK = "[UYAP-Termux Pro] © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır." + "⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
TERMUX = "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux")
AYRINTI = os.environ.get("UYAP_AYRINTI") == "1"

JARS_DIR = os.environ.get("UYAP_JARS") or os.path.join(BASE_DIR, "jars")
JAVA_SRC = os.path.join(BASE_DIR, "java")                     # ~/java/uyaptermux/*.java (kurulumda kopyalanır)
EIMZA_SRC = os.path.join(BASE_DIR, "eimza", "TermuxCcidProvider.java")
DURUM_DIR = os.environ.get("UYAP_INSTANCE_DIR") or os.path.join(HOME, ".uyap-editor")
DERLEME_DIR = os.path.join(DURUM_DIR, "siniflar")
EIMZA_DIR = os.environ.get("EIMZA_DIR") or os.path.join(HOME, ".eimza")
AYAR_DOSYASI = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "uyap-termux", "ayarlar.ini")

FLATLAF_URL = "https://repo1.maven.org/maven2/com/formdev/flatlaf/3.4.1/flatlaf-3.4.1.jar"
FLATLAF_SHA256 = "8b4bbd34727f80e74555b2be3d8dcb994434654986c64f4298162247a9d35ffc"
UYAP_ANA_SINIF = "tr/com/havelsan/uyap/system/editor/common/WPAppManager.class"

VARSAYILAN_AYARLAR = {
    "arayuz": {
        "tema": "acik",            # acik | koyu | macos-acik | macos-koyu | sistem
        "olcek": "1.2",            # 1.0 - 3.0 ya da otomatik (ekran DPI'sına göre)
        "vurgu": "",               # #RRGGBB, boş = temanın rengi
        "dokunmatik": "hayir",     # evet: kalın kaydırma çubukları, geniş menüler (parmakla kullanım)
    },
    "kaydirma": {
        "akici": "evet",
        "adim": "75",              # bir tekerlek çentiğinde piksel
        "sure": "0.11",            # yumuşatma süresi (sn); büyük = daha yağlı
        "hz": "0",                 # 0 = ekranın yenileme hızı
    },
    "java": {
        "yol": "",                 # boş = otomatik (11 > 17 > 21)
        "bellek": "otomatik",      # MB ya da otomatik (RAM'in ~%40'ı, 768-4096 arası)
        "surum_taklidi": "evet",   # JDK 15+ ile editörün "6-14 arası" kontrolünü açılışta geçer
        "ek_parametreler": "",     # ek JVM parametreleri, ör. -Dsun.java2d.xrender=false
    },
    "eimza": {
        "aktif": "evet",
    },
    "klavye": {
        "duzen": "tr",             # X11 klavye düzeni (setxkbmap): tr, us, de ...
        "varyant": "",             # boş = Türkçe Q, f = Türkçe F
        "tarama_kodlari": "evet",  # Termux:X11 "Prefer scancodes": Ctrl/Alt kısayolları + Türkçe düzen X'te
        "alt_menu": "hayir",       # hayir: tek başına Alt, editörün kısayol harflerini (KeyTips) açmaz
        "dokunma": "dokunmatik",   # dokunmatik (dokunulan yere tıklar, sürükleyip seçer) | touchpad | dogrudan
    },
    "belgeler": {
        "kayit_klasoru": "",       # boş = Termux'ta /sdcard/Documents/UYAP_Belgelerim
    },
}


def bilgi(msg):
    print("[BİLGİ] " + msg)


def uyari(msg):
    print("[UYARI] " + msg)


def ayrinti(msg):
    if AYRINTI:
        print("[AYRINTI] " + msg)


# --------------------------------------------------------------------------- ayarlar
def ayarlari_yukle(yol=AYAR_DOSYASI):
    # ';' satır içi yorum olabilir ('#' olamaz: vurgu = #RRGGBB)
    c = configparser.ConfigParser(inline_comment_prefixes=(";",))
    c.read_dict(VARSAYILAN_AYARLAR)
    if os.path.exists(yol):
        try:
            c.read(yol, encoding="utf-8")
        except configparser.Error as e:
            uyari("Ayar dosyası okunamadı (%s); varsayılanlar kullanılıyor: %s" % (e, yol))
    else:
        try:
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "w", encoding="utf-8") as f:
                f.write("# UYAP-Termux ayarları. Değişiklikler editörün bir sonraki açılışında geçerli olur.\n"
                        "# Düzenlemek için: uyap ayarlar   (ya da bu dosyayı elle düzenleyin)\n\n")
                c.write(f)
        except OSError:
            pass
    # ortam değişkenleri ayarları ezer
    for env, (bol, ad) in {"UYAP_TEMA": ("arayuz", "tema"), "UYAP_OLCEK": ("arayuz", "olcek"),
                           "UYAP_JAVA": ("java", "yol"), "UYAP_BELLEK": ("java", "bellek")}.items():
        if os.environ.get(env):
            c[bol][ad] = os.environ[env]
    return c


def evet(deger):
    return str(deger).strip().lower() in ("1", "evet", "e", "true", "yes", "on", "acik", "açık")


# --------------------------------------------------------------------------- dosya argümanları
def dosya_argumanlari(argv):
    """file:// URI'lerini çözer, mutlak yola çevirir, olmayanları atlar (çift tıklama: uyap-editor %F)."""
    from urllib.parse import unquote, urlparse
    sonuc = []
    for a in argv:
        if not a or a.startswith("--"):
            continue
        if a.startswith("file://"):
            a = unquote(urlparse(a).path)
        p = os.path.abspath(os.path.expanduser(a))
        if os.path.isfile(p):
            sonuc.append(p)
        else:
            uyari("Dosya bulunamadı, atlandı: %s" % a)
    return sonuc


# --------------------------------------------------------------------------- tek örnek
def _ornek_bilgisi():
    try:
        d = {}
        with open(os.path.join(DURUM_DIR, "instance.properties"), "r", encoding="utf-8") as f:
            for satir in f:
                if "=" in satir:
                    k, v = satir.strip().split("=", 1)
                    d[k] = v
        os.kill(int(d["pid"]), 0)
        return d
    except Exception:
        return None


def ornege_gonder(bilgi_, komut):
    with socket.create_connection(("127.0.0.1", int(bilgi_["port"])), 3) as sk:
        sk.settimeout(20)
        sk.sendall((bilgi_["token"] + "\t" + komut + "\n").encode("utf-8"))
        return sk.makefile("r", encoding="utf-8").readline().strip()


def ornege_yonlendir(dosyalar):
    """Editör açıksa belgeleri onda açar ve True döner. Art arda çift tıklamada açılmakta olan örneği bekler."""
    baslangic = os.path.join(DURUM_DIR, "starting.pid")
    bekle_sn = 0
    try:
        with open(baslangic) as f:
            bpid = int(f.read().strip())
        os.kill(bpid, 0)
        if bpid != os.getpid() and time.time() - os.path.getmtime(baslangic) < 180:
            bekle_sn = 120
    except Exception:
        pass
    bitis = time.time() + bekle_sn
    while True:
        b = _ornek_bilgisi()
        if b:
            break
        if time.time() >= bitis:
            return False
        time.sleep(0.5)
    try:
        for k in ["OPEN\t" + p for p in dosyalar] or ["NEW"]:
            if ornege_gonder(b, k) != "OK":
                return False
        return True
    except Exception as e:
        uyari("Açık editöre iletilemedi (%s); yeni pencere açılacak." % e)
        return False


# --------------------------------------------------------------------------- glibc JDK (ör. JDK 14.0.2)
def elf_yorumlayici(yol):
    """ELF dosyasının PT_INTERP (dinamik bağlayıcı) yolu; ELF değilse ya da okunamazsa ''.
    patchelf yorumlayıcıyı genellikle dosyanın sonlarına taşır: başlıktaki ofsete gidilerek okunur."""
    import struct
    try:
        with open(os.path.realpath(yol), "rb") as f:
            b = f.read(64)
            if len(b) < 64 or b[:4] != b"\x7fELF" or b[4] != 2:     # yalnızca 64 bit
                return ""
            end = "<" if b[5] == 1 else ">"
            phoff, = struct.unpack_from(end + "Q", b, 0x20)
            phentsize, phnum = struct.unpack_from(end + "HH", b, 0x36)
            f.seek(phoff)
            ph = f.read(phentsize * phnum)
            for i in range(phnum):
                o = i * phentsize
                if o + 56 > len(ph):
                    break
                p_type, = struct.unpack_from(end + "I", ph, o)
                if p_type == 3:                                      # PT_INTERP
                    off, = struct.unpack_from(end + "Q", ph, o + 8)
                    size, = struct.unpack_from(end + "Q", ph, o + 32)
                    if size > 4096:
                        return ""
                    f.seek(off)
                    return f.read(size).rstrip(b"\0").decode("utf-8", "ignore")
    except (OSError, struct.error):
        return ""
    return ""


def glibc_jdk(java):
    """'glibc' = Termux glibc bağlayıcısına yamalı (çalışır), 'yamasiz' = /lib/ld-linux (Termux'ta çalışmaz), '' = bionic."""
    yorum = elf_yorumlayici(java)
    if "/glibc/" in yorum:
        return "glibc"
    if TERMUX and yorum.startswith("/lib"):
        return "yamasiz"
    return ""


def java_on_ek(java):
    """glibc JDK 14 hazır CDS arşivini 64K sayfa için üretmiş; Android çekirdeği 4K → arşivi kapat."""
    return ["-Xshare:off"] if java and glibc_jdk(java) == "glibc" else []


def java_ortami(java):
    """glibc JDK'lar, Termux'un her sürece eklediği bionic LD_PRELOAD (termux-exec) ile çöker: temizlenir.
    (grun kullanılmaz: Java'yı bağlayıcı üzerinden başlatınca JAVA_HOME'u bulamaz ve boşluklu argümanları böler.)"""
    env = dict(os.environ)
    if java and glibc_jdk(java):
        env.pop("LD_PRELOAD", None)
        env.pop("LD_LIBRARY_PATH", None)
        fc = os.path.join(PREFIX, "etc", "fonts", "fonts.conf")
        if os.path.isfile(fc):
            env.setdefault("FONTCONFIG_FILE", fc)
    return env


# --------------------------------------------------------------------------- Java bulma
def _jdk_surumu(java):
    if glibc_jdk(java) == "yamasiz":
        return 0
    try:
        out = subprocess.run([java] + java_on_ek(java) + ["-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=java_ortami(java), timeout=30).stdout.decode("utf-8", "ignore")
    except Exception:
        return 0
    import re
    m = re.search(r'version "(\d+)(?:\.(\d+))?', out)
    if not m:
        return 0
    ana = int(m.group(1))
    return int(m.group(2) or 0) if ana == 1 else ana


def jdk_adaylari():
    """Bilinen JDK yolları: Termux (openjdk-11 tur-repo, 17/21 ana depo) ve Linux."""
    adaylar = []
    jvm = os.path.join(PREFIX, "lib", "jvm")
    for kalip in ("java-11-openjdk", "openjdk-11", "jdk-14*", "java-17-openjdk", "openjdk-17",
                  "java-21-openjdk", "openjdk-21", "*"):
        adaylar += sorted(glob.glob(os.path.join(jvm, kalip, "bin", "java")))
    adaylar += [os.path.join(PREFIX, "opt", "openjdk-11", "bin", "java"), os.path.join(PREFIX, "opt", "openjdk", "bin", "java")]
    # Elle kurulmuş JDK'lar (ör. jdk-14.0.2 arşivi açılmış): ~/, ~/java, ~/jdk, $PREFIX/opt, $PREFIX/share altında
    for kok in (HOME, os.path.join(HOME, "java"), os.path.join(HOME, "jdk"), os.path.join(PREFIX, "opt"),
                os.path.join(PREFIX, "share")):
        for kalip in ("*jdk*", "*jre*", "zulu*", "java-*"):
            adaylar += sorted(glob.glob(os.path.join(kok, kalip, "bin", "java")))
            adaylar += sorted(glob.glob(os.path.join(kok, kalip, "*", "bin", "java")))
    adaylar += sorted(glob.glob("/usr/lib/jvm/*/bin/java"))
    w = shutil.which("java")
    if w and os.path.realpath(w) != "/system/bin/java":
        adaylar.append(w)
    goruldu, sonuc = set(), []
    for a in adaylar:
        r = os.path.realpath(a)
        if os.path.isfile(r) and os.access(r, os.X_OK) and r not in goruldu and not r.startswith("/system/"):
            goruldu.add(r)
            sonuc.append(a)
    return sonuc


def java_bul(ayar_yolu=""):
    """(java, surum) döner. Tercih: ayar > 11 > 12-14 > 17 > 21 > diğer (UYAP Java 11 ile sınanmıştır)."""
    if ayar_yolu:
        if os.path.isfile(ayar_yolu):
            return ayar_yolu, _jdk_surumu(ayar_yolu)
        uyari("Ayarlardaki Java bulunamadı: %s (otomatik aranıyor)" % ayar_yolu)
    adaylar = [(a, _jdk_surumu(a)) for a in jdk_adaylari()]
    adaylar = [(a, s) for a, s in adaylar if s >= 8]

    def puan(x):
        s = x[1]
        return (0 if s == 11 else 1 if 12 <= s <= 14 else 2 if s == 17 else 3 if s == 21 else 4, s)
    adaylar.sort(key=puan)
    return adaylar[0] if adaylar else (None, 0)


def javac_bul(java):
    """Aynı JDK'nın javac'ı; çalıştırılamıyorsa (yamasız glibc) Termux'un kendi JDK'sının javac'ı.
    Başlatıcı --release 11 ile derlendiği için hangi javac olduğu fark etmez."""
    def calisir(p):
        return os.path.isfile(p) and glibc_jdk(p) != "yamasiz"
    for ad in ("javac", "javac.default"):
        p = os.path.join(os.path.dirname(java), ad)
        if calisir(p):
            return p
    for aday in jdk_adaylari():
        if not glibc_jdk(aday):
            p = os.path.join(os.path.dirname(aday), "javac")
            if calisir(p):
                return p
    w = shutil.which("javac")
    return w if w and calisir(w) else None


# --------------------------------------------------------------------------- jar'lar
def jar_listesi():
    if not os.path.isdir(JARS_DIR):
        return []
    return sorted(glob.glob(os.path.join(JARS_DIR, "*.jar")))


def editor_jar_var_mi(jars):
    for j in jars:
        try:
            with zipfile.ZipFile(j) as z:
                if UYAP_ANA_SINIF in z.namelist():
                    return True
        except (zipfile.BadZipFile, OSError):
            continue
    return False


def dosya_sha256(yol):
    h = hashlib.sha256()
    with open(yol, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def flatlaf_hazirla():
    """FlatLaf'ı Maven Central'dan indirir ve SHA-256 ile doğrular (bozuk/sahte jar classpath'e girmez)."""
    hedef = os.path.join(JARS_DIR, "flatlaf.jar")
    if os.path.exists(hedef):
        return True
    import urllib.request
    gecici = hedef + ".indiriliyor"
    try:
        os.makedirs(JARS_DIR, exist_ok=True)
        bilgi("Modern arayüz motoru (FlatLaf 3.4.1) indiriliyor ...")
        urllib.request.urlretrieve(FLATLAF_URL, gecici)
        if dosya_sha256(gecici) != FLATLAF_SHA256:
            os.remove(gecici)
            uyari("FlatLaf özeti uyuşmadı; dosya silindi. Standart görünüm kullanılacak.")
            return False
        os.replace(gecici, hedef)
        return True
    except Exception as e:
        try:
            os.remove(gecici)
        except OSError:
            pass
        uyari("FlatLaf indirilemedi, standart görünüm kullanılacak: %s" % e)
        return False


# --------------------------------------------------------------------------- derleme
def java_kaynaklari(eimza):
    kaynaklar = sorted(glob.glob(os.path.join(JAVA_SRC, "uyaptermux", "*.java")))
    if eimza and os.path.isfile(EIMZA_SRC):
        kaynaklar.append(EIMZA_SRC)
    return kaynaklar


def baslaticiyi_derle(java, cp, eimza):
    """Başlatıcıyı ~/.uyap-editor/siniflar'a derler. Kaynaklar + JDK değişmediyse derlemeyi atlar.
    Dönüş: (hazir, eimza_hazir)"""
    kaynaklar = java_kaynaklari(eimza)
    if not any(k.endswith("Baslatici.java") for k in kaynaklar):
        uyari("Başlatıcı kaynakları yok (%s); editör düz modda açılacak." % JAVA_SRC)
        return False, False
    h = hashlib.sha256(os.path.realpath(java).encode())
    for k in kaynaklar:
        h.update(k.encode())
        with open(k, "rb") as f:
            h.update(f.read())
    ozet = h.hexdigest()
    ozet_dosyasi = os.path.join(DERLEME_DIR, ".ozet")
    try:
        with open(ozet_dosyasi) as f:
            if f.read().strip() == ozet and os.path.isfile(os.path.join(DERLEME_DIR, "uyaptermux", "Baslatici.class")):
                ayrinti("Java bileşenleri güncel, derleme atlandı.")
                return True, eimza and os.path.isfile(os.path.join(DERLEME_DIR, "eimza", "TermuxCcidProvider.class"))
    except OSError:
        pass
    javac = javac_bul(java)
    if not javac:
        uyari("javac bulunamadı (JDK yerine yalnızca JRE kurulu?): editör düz modda açılacak.")
        return False, False
    shutil.rmtree(DERLEME_DIR, ignore_errors=True)
    os.makedirs(DERLEME_DIR, exist_ok=True)
    bilgi("Başlatıcı derleniyor (ilk açılışta bir kez) ...")

    def derle(dosyalar):
        r = subprocess.run([javac, "--release", "11", "-encoding", "UTF-8", "-nowarn", "-d", DERLEME_DIR, "-cp", cp] + dosyalar,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=java_ortami(javac))
        if r.returncode != 0:
            uyari("Derleme hatası:\n" + r.stderr.decode("utf-8", "ignore")[-2000:])
        return r.returncode == 0

    eimza_hazir = False
    if eimza and os.path.isfile(EIMZA_SRC):
        eimza_hazir = derle([EIMZA_SRC])
        if not eimza_hazir:
            uyari("E-imza sağlayıcısı derlenemedi: e-imza kapalı.")
    if not derle([k for k in kaynaklar if k != EIMZA_SRC]):
        return False, False
    with open(ozet_dosyasi, "w") as f:
        f.write(ozet if (eimza_hazir or not eimza) else "")
    return True, eimza_hazir


# --------------------------------------------------------------------------- bellek
def bellek_mb(ayar):
    if str(ayar).isdigit():
        return max(256, int(ayar))
    try:
        with open("/proc/meminfo") as f:
            for satir in f:
                if satir.startswith("MemTotal:"):
                    toplam = int(satir.split()[1]) // 1024
                    return max(768, min(4096, int(toplam * 0.4)))
    except (OSError, ValueError):
        pass
    return 1536


# --------------------------------------------------------------------------- UDF araçları
def udf_metni(udf_yolu):
    """UDF'nin düz metni: content.xml içindeki <content> CDATA havuzu (paragraflar \\n ile ayrılır)."""
    with zipfile.ZipFile(udf_yolu) as z:
        adlar = z.namelist()
        ad = "content.xml" if "content.xml" in adlar else next((n for n in adlar if n.endswith(".xml")), None)
        if ad is None:
            raise ValueError("UDF içinde content.xml yok")
        veri = z.read(ad)
    if not veri.strip():
        return ""
    kok = ET.fromstring(veri)
    icerik = kok.find("content")
    if icerik is not None and icerik.text:
        return icerik.text
    return "\n".join(e.text.strip() for e in kok.iter() if e.text and e.text.strip())


def panoya_kopyala(metin):
    veri = metin.encode("utf-8")
    for komut in (["termux-clipboard-set"], ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"]):
        if shutil.which(komut[0]):
            try:
                subprocess.run(komut, input=veri, check=True, timeout=15)
                return komut[0]
            except Exception:
                continue
    return None


def udf_oku_ve_kopyala(yol):
    try:
        metin = udf_metni(yol)
    except Exception as e:
        print("[HATA] UDF okunamadı: %s" % e)
        return 1
    arac = panoya_kopyala(metin)
    print("[BAŞARILI] Metin panoya kopyalandı (%s)." % arac if arac else "[BİLGİ] Pano aracı yok; metin aşağıda:")
    print("-" * 50)
    print(metin if not arac else metin[:400] + ("\n... [devamı panoda]" if len(metin) > 400 else ""))
    return 0


def udf_to_doc(yol):
    try:
        metin = udf_metni(yol)
    except Exception as e:
        print("[HATA] UDF okunamadı: %s" % e)
        return 1
    hedef = os.path.splitext(yol)[0] + "_Disari_Aktarilan.doc"
    paragraflar = "".join("<p>%s</p>" % (html.escape(p) if p.strip() else "&nbsp;") for p in metin.split("\n"))
    with open(hedef, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'><style>body{font-family:'Times New Roman',serif;font-size:12pt}"
                "p{margin:0 0 6pt 0;line-height:1.5}</style></head><body>%s</body></html>" % paragraflar)
    print("[BAŞARILI] DOC kaydedildi: %s" % hedef)
    return 0


# --------------------------------------------------------------------------- çalışma klasörü
def calisma_klasoru():
    for d in (os.path.join(HOME, "storage", "downloads"), "/sdcard/Download", HOME):
        if os.path.isdir(d) and os.access(d, os.W_OK):
            return d
    return HOME


def belge_klasoru(ayarlar):
    k = ayarlar["belgeler"].get("kayit_klasoru", "").strip()
    if not k and TERMUX:
        k = "/sdcard/Documents/UYAP_Belgelerim"
    if k:
        try:
            os.makedirs(os.path.expanduser(k), exist_ok=True)
        except OSError:
            pass
    return k


# --------------------------------------------------------------------------- ölçek
def xft_dpi():
    """X sunucusunun Xft.dpi değeri (xrdb), yoksa None."""
    try:
        out = subprocess.run(["xrdb", "-query"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5).stdout.decode()
        for satir in out.splitlines():
            if satir.startswith("Xft.dpi:"):
                return float(satir.split(":", 1)[1])
    except Exception:
        pass
    return None


def olcek_degeri(ayar, dpi=None):
    """Tüm pencerenin ölçeği (sun.java2d.uiScale). 'otomatik' = Xft.dpi/96, 0.25'lik adımlarla, 1.0-3.0."""
    a = str(ayar).strip().lower().replace(",", ".")
    if a and a != "otomatik":
        try:
            return "%g" % max(0.75, min(3.0, float(a)))
        except ValueError:
            pass
    if dpi is None:
        dpi = xft_dpi()
    if not dpi:
        return "1"
    return "%g" % max(1.0, min(3.0, round(dpi / 96.0 * 4) / 4.0))


# --------------------------------------------------------------------------- komut
def komut_olustur(java, java_surum, cp, ayarlar, hazir, eimza_hazir, dosyalar, work_dir):
    a = ayarlar
    komut = [java] + java_on_ek(java) + [
        "-Duser.home=%s" % work_dir,
        "-Duser.dir=%s" % work_dir,
        "-Xms256M",
        "-Xmx%dM" % bellek_mb(a["java"]["bellek"]),
        "-XX:+UseSerialGC" if TERMUX else "-XX:+UseG1GC",
        "-Dfile.encoding=UTF-8",
        "-Dsun.java2d.uiScale=%s" % olcek_degeri(a["arayuz"]["olcek"]),
        "-Dawt.useSystemAAFontSettings=on",
        "-Dswing.aatext=true",
        "-Dswing.volatileImageBufferEnabled=true",
    ]
    if java_surum >= 9:
        komut += java_modul_izinleri()
    # Ek JVM parametreleri: ayarlar.ini [java] ek_parametreler ya da UYAP_JAVA_OPTS (boşlukla ayrılmış)
    import shlex
    komut += shlex.split(a["java"].get("ek_parametreler", "")) + shlex.split(os.environ.get("UYAP_JAVA_OPTS", ""))
    if hazir:
        komut += [
            "-Duyap.tema=%s" % a["arayuz"]["tema"],
            "-Duyap.olcek=%s" % a["arayuz"]["olcek"],
            "-Duyap.vurgu=%s" % a["arayuz"]["vurgu"],
            "-Duyap.dokunmatik=%s" % str(evet(a["arayuz"]["dokunmatik"])).lower(),
            "-Duyap.kaydirma=%s" % str(evet(a["kaydirma"]["akici"])).lower(),
            "-Duyap.kaydirma.adim=%s" % a["kaydirma"]["adim"],
            "-Duyap.kaydirma.sure=%s" % a["kaydirma"]["sure"],
            "-Duyap.hz=%s" % a["kaydirma"]["hz"],
            "-Duyap.java.taklit=%s" % str(evet(a["java"]["surum_taklidi"])).lower(),
            "-Duyap.alt.menu=%s" % str(evet(a["klavye"]["alt_menu"])).lower(),
        ]
        if os.name != "nt" and os.environ.get("UYAP_TEK_ORNEK", "1") != "0":
            komut.append("-Duyap.instance.dir=%s" % DURUM_DIR)
        if eimza_hazir:
            komut.append("-Deimza.dir=%s" % EIMZA_DIR)
        komut += ["-cp", cp, "uyaptermux.Baslatici"] + dosyalar
    else:
        komut += ["-cp", cp, "tr.com.havelsan.uyap.system.editor.common.WPAppManager", "getNewWPInstance"]
        if dosyalar:
            komut += ["EDITOR_TYPE_TEMPLATE" if dosyalar[0].lower().endswith(".usf") else "EDITOR_TYPE_DOCUMENT", dosyalar[0]]
        else:
            komut.append("EDITOR_TYPE_DOCUMENT")
    return komut


# UYAP Java 8 için yazılmış; Java 9+ modül sistemi dahili sınıflara erişimi engeller. Editör jar'larında başvurulan
# dahili paketler (jar taramasıyla bulundu). Eksik izin → örn. seçili metin hiç çizilmiyordu:
# "IllegalAccessError: ... cannot access class sun.swing.SwingUtilities2 ... does not export sun.swing".
MODUL_IZINLERI = {
    "java.base": ["java.util", "java.lang", "java.lang.reflect", "java.text", "java.io", "java.net",
                  "sun.security.util", "sun.security.x509", "sun.security.action", "sun.security.provider",
                  "sun.reflect.generics.reflectiveObjects"],
    "java.desktop": ["java.awt", "java.awt.font", "java.awt.image", "java.awt.event", "javax.swing",
                     "javax.swing.text", "javax.swing.plaf.basic", "sun.swing", "sun.awt", "sun.awt.X11",
                     "sun.awt.image", "sun.awt.datatransfer", "sun.awt.dnd", "sun.awt.im", "sun.font",
                     "sun.java2d", "sun.java2d.loops", "sun.java2d.pipe", "sun.java2d.opengl", "sun.print",
                     "com.sun.java.swing.plaf.gtk"],
    "jdk.crypto.cryptoki": ["sun.security.pkcs11.wrapper"],
}


def java_modul_izinleri():
    return ["--add-opens=%s/%s=ALL-UNNAMED" % (m, p) for m, ps in MODUL_IZINLERI.items() for p in ps]


def tani(ayarlar):
    print("UYAP-Termux başlatıcı %s" % SURUM)
    print("Termux: %s   PREFIX: %s" % ("evet" if TERMUX else "hayır", PREFIX))
    print("Ayar dosyası: %s" % AYAR_DOSYASI)
    for b in ayarlar.sections():
        print("  [%s] %s" % (b, ", ".join("%s=%s" % kv for kv in ayarlar[b].items())))
    print("JDK adayları:")
    for a in jdk_adaylari():
        g = glibc_jdk(a)
        ek = {"glibc": "  (glibc)", "yamasiz": "  (glibc, YAMASIZ: uyap jdk14 kur)"}.get(g, "")
        print("  %-60s Java %s%s" % (a, _jdk_surumu(a), ek))
    java, s = java_bul(ayarlar["java"]["yol"].strip())
    print("Seçilen Java: %s (%s)" % (java, s))
    print("javac: %s" % (javac_bul(java) if java else "-"))
    jars = jar_listesi()
    print("Jar klasörü: %s (%d jar, editör %s)" % (JARS_DIR, len(jars), "VAR" if editor_jar_var_mi(jars) else "YOK"))
    print("Bellek sınırı: %d MB" % bellek_mb(ayarlar["java"]["bellek"]))
    print("Başlatıcı kaynakları: %s" % ("var" if java_kaynaklari(False) else "YOK"))
    print("Açık editör: %s" % ("var (pid %s)" % _ornek_bilgisi()["pid"] if _ornek_bilgisi() else "yok"))
    bj = os.path.join(EIMZA_DIR, "bridge.json")
    print("E-imza köprüsü: %s" % ("hazır" if os.path.exists(bj) else "bağlı okuyucu yok"))
    return 0


def kontrol_merkezi(ayarlar):
    java, java_surum = java_bul(ayarlar["java"]["yol"].strip())
    if not java:
        print("[KRİTİK HATA] Java bulunamadı (pkg install openjdk-21).")
        return 3
    flatlaf_hazirla()
    jars = jar_listesi()
    hazir, _ = baslaticiyi_derle(java, os.pathsep.join(jars), evet(ayarlar["eimza"]["aktif"]) and os.name != "nt")
    if not hazir:
        return 4
    flatlaf = [j for j in jars if os.path.basename(j) == "flatlaf.jar"]
    return subprocess.call(env=java_ortami(java), args=[java] + java_on_ek(java) + ["-Xmx256M", "-XX:+UseSerialGC", "-Dawt.useSystemAAFontSettings=on", "-Dsun.java2d.uiScale=1",
                            "-cp", os.pathsep.join([DERLEME_DIR] + flatlaf), "uyaptermux.KontrolMerkezi"])


def main(argv):
    print(CKZ_KIMLIK)
    ayarlar = ayarlari_yukle()
    if argv and argv[0] in ("-h", "--yardim", "--help"):
        print(__doc__)
        return 0
    if argv and argv[0] == "--surum":
        print(SURUM)
        return 0
    if argv and argv[0] == "--tani":
        return tani(ayarlar)
    if argv and argv[0] == "--derle":
        java, _ = java_bul(ayarlar["java"]["yol"].strip())
        if not java:
            print("[HATA] Java bulunamadı.")
            return 3
        flatlaf_hazirla()
        hazir, eimza_hazir = baslaticiyi_derle(java, os.pathsep.join(jar_listesi()), evet(ayarlar["eimza"]["aktif"]))
        print("başlatıcı: %s, e-imza sağlayıcısı: %s" % ("hazır" if hazir else "HATA", "hazır" if eimza_hazir else "yok"))
        return 0 if hazir else 4
    if argv and argv[0] == "--panel":
        return kontrol_merkezi(ayarlar)
    if len(argv) > 1 and argv[0] == "--oku":
        return udf_oku_ve_kopyala(argv[1])
    if len(argv) > 1 and argv[0] == "--doc":
        return udf_to_doc(argv[1])

    dosyalar = dosya_argumanlari(argv)

    tek_ornek = os.name != "nt" and os.environ.get("UYAP_TEK_ORNEK", "1") != "0"
    if tek_ornek:
        if ornege_yonlendir(dosyalar):
            bilgi("Belge zaten açık olan UYAP Editör'de açıldı.")
            return 0
        os.makedirs(DURUM_DIR, exist_ok=True)
        baslangic = os.path.join(DURUM_DIR, "starting.pid")
        with open(baslangic, "w") as f:
            f.write(str(os.getpid()))
        import atexit
        atexit.register(lambda: os.path.exists(baslangic) and os.remove(baslangic))

    jars = jar_listesi()
    if not editor_jar_var_mi(jars):
        print("[HATA] UYAP Editör jar'ları bulunamadı: %s" % JARS_DIR)
        print("       Kurulum:  bash ~/uyap-termux/kur.sh   ya da   uyap kur-editor /sdcard/Download/uyapeditor_*_amd64.zip")
        return 2

    java, java_surum = java_bul(ayarlar["java"]["yol"].strip())
    if not java:
        print("[KRİTİK HATA] Kullanılabilir Java bulunamadı.")
        print("  Termux:  pkg install openjdk-21   (ya da tur-repo'dan openjdk-11)")
        print("  Android'in /system/bin/java'sı UYAP'ı çalıştıramaz.")
        return 3
    ayrinti("Java: %s (%d)" % (java, java_surum))

    flatlaf_hazirla()
    jars = jar_listesi()
    eimza_iste = evet(ayarlar["eimza"]["aktif"]) and os.name != "nt"
    cp_derleme = os.pathsep.join(jars)
    hazir, eimza_hazir = baslaticiyi_derle(java, cp_derleme, eimza_iste)
    if eimza_iste and hazir and not eimza_hazir:
        uyari("E-imza sağlayıcısı hazır değil: e-imza kapalı.")
    cp = os.pathsep.join(([DERLEME_DIR] if hazir else []) + jars)

    work_dir = calisma_klasoru()
    belge_klasoru(ayarlar)
    os.chdir(work_dir)
    komut = komut_olustur(java, java_surum, cp, ayarlar, hazir, eimza_hazir, dosyalar, work_dir)
    bilgi("UYAP Editör başlatılıyor (Java %d%s%s) ..." % (java_surum, " glibc" if glibc_jdk(java) else "",
                                                          ", e-imza açık" if eimza_hazir else ""))
    ayrinti("Komut: " + " ".join(komut))
    try:
        return subprocess.call(komut, env=java_ortami(java))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
