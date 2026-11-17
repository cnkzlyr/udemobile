#!/data/data/com.termux/files/usr/bin/bash
# CKZ-HDR/1 | © 2026 Av. Can KIZILYAR⁠​‌​​​​‌‌​‌​​‌​‌‌​‌​‌‌​‌​​​‌​‌‌​‌​​‌‌​​‌​​​‌‌​​​​​​‌‌​​‌​​​‌‌​‌‌​​​‌​‌‌​‌​‌​​​​‌‌​‌​​‌​‌‌⁠ | Tüm hakları saklıdır.
# CKZ-HDR/1 | Yazılı izin olmadan çoğaltılamaz, değiştirilemez, dağıtılamaz; bu bildirim kaldırılamaz. Bkz. LICENSE.txt
# CKZ-MUHUR/1 MUHURSUZ
# UYAP-Termux Kurulum Paketi — ana kurulum betigi.
#   bash kur.sh [--kabul] [--hafif] [--deneme] [--yine-de] [--yazitipleri]
#               [--editor-zip YOL] [--adalet-deb YOL] [--parmak XXXX-XXXX-...] [--paket-atla] [--yalniz-editor]
#   --kabul        lisansi okudugunuzu ve kabul ettiginizi onaylar (soru sormaz)
#   --hafif        XFCE yerine hafif fluxbox masaustu
#   --deneme       hicbir sey degistirmeden adimlari yazar
#   --yine-de      muhur dogrulamasi BASARISIZ/YOK olsa da devam eder (yazar onayi olmadan; kendi sorumlulugunuzdadir)
#   --editor-zip   resmi UYAP Editor zip'ini (uyapeditor_*_amd64.zip) elle verin (otomatik indirme calismazsa)
#   --adalet-deb   resmi adalet-eimza-tray*.deb dosyasini elle verin
#   --parmak       yazarin resmi sayfasinda yayimlanan anahtar parmak izi (dogrulamayi sabitler)
#   --yazitipleri  PDF'te birebir Times New Roman icin Microsoft cekirdek yazi tiplerini de kurar
#   --yalniz-editor yalnizca UYAP Editor jar'larini kurar/gunceller (uyap kur-editor bunu kullanir)
set -u
KOK="$(cd "$(dirname "$0")" && pwd)"
. "$KOK/bilesenler/eimza/marka.sh" 2>/dev/null || { echo "marka.sh eksik: paket bozuk."; exit 1; }

KABUL=0; HAFIF=0; DENEME=0; YINEDE=0; EDITOR_ZIP=""; ADALET_DEB=""; PARMAK="${CKZ_PARMAK:-}"; PAKETATLA=0
YAZITIPI=0; YALNIZ_EDITOR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --kabul) KABUL=1 ;; --hafif) HAFIF=1 ;; --deneme) DENEME=1 ;; --yine-de) YINEDE=1 ;; --paket-atla) PAKETATLA=1 ;;
    --yazitipleri) YAZITIPI=1 ;; --yalniz-editor) YALNIZ_EDITOR=1 ;;
    --editor-zip) shift; EDITOR_ZIP="${1:-}" ;;
    --adalet-deb) shift; ADALET_DEB="${1:-}" ;;
    --parmak) shift; PARMAK="${1:-}" ;;
    -h|--help) sed -n '/^# UYAP-Termux Kurulum/,/^set -u/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "Bilinmeyen secenek: $1"; exit 2 ;;
  esac
  shift
done
run() { if [ "$DENEME" = "1" ]; then echo "[deneme] $*"; else "$@"; fi; }
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
HATA="$HOME/uyap-termux-kurulum-hatalar.txt"; : > "$HATA" 2>/dev/null
if [ -t 1 ]; then R_K=$'\e[1;31m'; R_Y=$'\e[1;32m'; R_M=$'\e[1;36m'; R_B=$'\e[1m'; R_N=$'\e[0m'; else R_K=""; R_Y=""; R_M=""; R_B=""; R_N=""; fi
fail() { echo "  ${R_K}✖${R_N} $*"; echo "$*" >> "$HATA"; }
iyi()  { echo "  ${R_Y}✔${R_N} $*"; }
ADIM_SAYI=7
if [ -t 1 ]; then CURL_I="--progress-bar"; else CURL_I="-sS"; fi
adim() { printf '\n%s[%s/%s]%s %s%s%s\n' "$R_M" "$1" "$ADIM_SAYI" "$R_N" "$R_B" "$2" "$R_N"; }

ckz_banner
echo
if [ "$YALNIZ_EDITOR" = "1" ]; then KABUL=1; PAKETATLA=1; fi

# ---------------------------------------------------------------- 0) ortam
if [ "$DENEME" != "1" ] && [ ! -d /data/data/com.termux ] && [ -z "${UYAP_TEST_ORTAMI:-}" ]; then
  echo "Bu paket yalnizca Android'deki Termux (F-Droid/GitHub surumu) icindir."; exit 1
fi
case "$(uname -m)" in aarch64|arm64) ;; *) echo "(uyari) Islemci $(uname -m): paket arm64 icin hazirlandi." ;; esac
[ "$KABUL" = "1" ] || { [ -t 0 ] || { echo "Etkilesimli degil: lisansi kabul ediyorsaniz --kabul ekleyin."; exit 1; }; }

# ---------------------------------------------------------------- 1) lisans
adim 1 "Lisans"
sed -n '1,28p' "$KOK/LICENSE.txt"
echo "   ... (tamami: $KOK/LICENSE.txt ; ucuncu taraf bilesenler: NOTICE.txt)"
if [ "$YALNIZ_EDITOR" = "1" ]; then :; elif [ "$KABUL" != "1" ]; then
  printf '\nLisansi okudum ve kabul ediyorum (evet/hayir): '; read -r c
  case "$c" in evet|EVET|Evet|e|E) ;; *) echo "Kurulum iptal edildi."; exit 1 ;; esac
fi

# ---------------------------------------------------------------- 2) temel paketler + muhur
adim 2 "Temel paketler ve mühür doğrulaması"
# Yeni kurulmus Termux'ta paketlerin cogu eskidir; yalnizca birkac paket kurmak (or. python) libcurl'u yukseltip
# openssl'i eski birakabilir ve curl "cannot locate symbol SSL_..." ile bozulur. Bu yuzden ONCE tam yukseltme.
tam_yukselt() {
  echo "   Tüm Termux paketleri güncelleniyor (yarım güncelleme curl/pkg'yi bozar) ..."
  run pkg update -y || true
  run env DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confdef \
      -o Dpkg::Options::=--force-confold full-upgrade
}
curl_saglam() { curl --version >/dev/null 2>&1; }
if [ "$PAKETATLA" != "1" ]; then
  tam_yukselt || fail "paket guncellemesi tamamlanamadi (elle: yes | pkg upgrade)"
  run env DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold \
      install python unzip zip curl tar dpkg || fail "temel paketler kurulamadi"
  if [ "$DENEME" != "1" ] && ! curl_saglam; then
    echo "   curl bozuk (kütüphane uyumsuzluğu); onarılıyor ..."
    run env DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold install --reinstall openssl libcurl curl || true
    tam_yukselt || true
    curl_saglam || { echo "  ${R_K}✖${R_N} curl hâlâ çalışmıyor. Önce elle:  yes | pkg upgrade   sonra kur.sh'i yeniden çalıştırın."; exit 4; }
  fi
fi
command -v python3 >/dev/null 2>&1 || { echo "python3 yok."; [ "$DENEME" = "1" ] || exit 1; }
if [ "$YALNIZ_EDITOR" = "1" ]; then :; elif command -v python3 >/dev/null 2>&1; then
  pin=(); [ -n "$PARMAK" ] && pin=(--pub-parmak "$PARMAK")
  python3 "$KOK/tools/dogrula.py" "$KOK" "${pin[@]}"; rc=$?
  [ $rc -eq 0 ] && echo "   Yukaridaki parmak izini yazarin RESMI sayfasindaki degerle karsilastirin."
  if [ $rc -eq 0 ] && [ -z "$PARMAK" ]; then
    if [ "$KABUL" != "1" ]; then
      printf '   Parmak izi resmi sayfadaki degerle AYNI mi? (evet/hayir): '; read -r c
      case "$c" in evet|EVET|Evet|e|E) ;; *) echo "   Kurulum durduruldu."; exit 3 ;; esac
    else
      echo "   (uyari) --parmak verilmedi: parmak izi elle dogrulanmadi."
    fi
  fi
  if [ $rc -eq 2 ] && [ -d "$KOK/.git" ]; then
    echo
    echo "   Bu bir GELISTIRME kopyasi (git deposu): dosyalar henuz yazar muhruyle imzalanmamis."
    echo "   Resmi surum icin yayimlanan muhurlu zip'i kullanin; kendi derlemenizi kuruyorsaniz: --yine-de"
  fi
  if [ $rc -ne 0 ]; then
    echo
    echo "   !!! Bu kopya yazar (Av. Can KIZILYAR) tarafindan dogrulanamadi. Degistirilmis/sahte olabilir."
    if [ "$YINEDE" != "1" ]; then echo "   Kurulum durduruldu. Resmi kaynaktan tekrar indirin. (Bilincli devam: --yine-de)"; [ "$DENEME" = "1" ] || exit 3; fi
    echo "   --yine-de: devam ediliyor; bu kurulum 'ONAYSIZ' olarak isaretlenecek."
    ONAYSIZ=1
  fi
fi
ONAYSIZ="${ONAYSIZ:-0}"

# ---------------------------------------------------------------- 3) depolar ve paketler
adim 3 "Depolar ve paketler (uzun sürebilir)"
# openjdk-21: Adalet E-Imza (zorunlu) ve UYAP Editor (baslatici surum kontrolunu gecer). openjdk-11 (tur-repo)
# varsa editor onu tercih eder; yoksa kurulum bu yuzden basarisiz sayilmaz.
PAKETLER="python libusb termux-api openjdk-21 openjdk-21-x xorg-server-xvfb termux-x11-nightly dialog fontconfig-utils ttf-dejavu xorg-setxkbmap xorg-xkbcomp"
ISTEGE_BAGLI="openjdk-11"
if [ "$HAFIF" = "1" ]; then PAKETLER="$PAKETLER fluxbox xterm"; else PAKETLER="$PAKETLER xfce4 xfce4-terminal thunar"; fi
if [ "$PAKETATLA" != "1" ]; then
  run pkg install -y x11-repo tur-repo || fail "x11-repo/tur-repo kurulamadi"
  run pkg update -y
  for p in $PAKETLER; do
    if [ "$DENEME" = "1" ]; then echo "[deneme] pkg install -y $p"; continue; fi
    dpkg -s "$p" >/dev/null 2>&1 && continue
    if pkg install -y "$p" >/dev/null 2>&1; then iyi "$p"; else fail "paket kurulamadi: $p"; fi
  done
  KRITIK_EKSIK=""
  for p in python openjdk-21 termux-x11-nightly; do
    [ "$DENEME" = "1" ] && break
    dpkg -s "$p" >/dev/null 2>&1 || KRITIK_EKSIK="$KRITIK_EKSIK $p"
  done
  if [ -n "$KRITIK_EKSIK" ]; then
    echo
    echo "  ${R_K}✖ Kritik paketler kurulamadı:${R_N}$KRITIK_EKSIK"
    echo "    Muhtemel nedenler: yarım kalmış güncelleme ya da erişilemeyen yansı (mirror)."
    echo "    Çözüm:  yes | pkg upgrade   (gerekirse: termux-change-repo)   sonra:  bash $KOK/kur.sh --yine-de"
    exit 5
  fi
  for p in $ISTEGE_BAGLI; do
    [ "$DENEME" = "1" ] && { echo "[deneme] pkg install -y $p (istege bagli)"; continue; }
    dpkg -s "$p" >/dev/null 2>&1 && continue
    if pkg install -y "$p" >/dev/null 2>&1; then iyi "$p (istege bagli)"; else echo "  - $p kurulamadi (istege bagli; Java 21 kullanilacak)"; fi
  done
fi

# ---------------------------------------------------------------- 4) resmi UYAP Editor
T="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/uyapkur.XXXXXX")"; trap 'rm -rf "$T"' EXIT
adim 4 "UYAP Doküman Editörü (T.C. Adalet Bakanlığı) — resmî kaynaktan indirilir, pakete dahil DEĞİLDİR"
editor_indir() {
  if [ -z "$EDITOR_ZIP" ] && [ -f "$HOME/jars/editor_lib.jar" ]; then iyi "jar'lar zaten mevcut: ~/jars"; return 0; fi
  local zip="$EDITOR_ZIP"
  if [ -z "$zip" ]; then
    local sayfa url
    sayfa="$(curl -fsSL --max-time 40 https://uyap.gov.tr/UYAP-Editor 2>/dev/null)" || { fail "uyap.gov.tr sayfasina ulasilamadi"; return 1; }
    # Sayfadaki baglanti protokolsuz ve tirnaksiz olabilir: href=//rayp.adalet.gov.tr/.../uyapeditor_5.4.20_amd64.zip
    url="$(printf '%s' "$sayfa" | grep -oE '(https?:)?//rayp\.adalet\.gov\.tr/[A-Za-z0-9_./-]*uyapeditor_[0-9.]+_amd64\.zip' \
           | sed -E 's#^(https?:)?//#https://#' | sort -t_ -k2 -V | tail -1)"
    [ -n "$url" ] || { fail "resmi sayfada Pardus/Debian paketi baglantisi bulunamadi (sayfa degismis olabilir)"; return 1; }
    echo "   indiriliyor: $url"
    curl -fL $CURL_I --max-time 1200 -o "$T/editor.zip" "$url" || { fail "editor indirilemedi"; return 1; }
    zip="$T/editor.zip"
  fi
  echo "   sha256: $(sha256sum "$zip" | cut -d' ' -f1)"
  mkdir -p "$T/ed" && unzip -q -o "$zip" -d "$T/ed" || { fail "editor zip'i acilamadi"; return 1; }
  while IFS= read -r -d '' d; do
    case "$(basename "$d")" in *cups*) continue ;; esac
    dpkg-deb --fsys-tarfile "$d" | tar -x -C "$T/ed" --wildcards '*.jar' 2>/dev/null
  done < <(find "$T/ed" -name '*.deb' -print0 2>/dev/null)
  python3 - "$T/ed" "$HOME/jars" <<'PY'
import os, shutil, sys, zipfile
kok, hedef = sys.argv[1:3]
ana = None
for r, _, fs in os.walk(kok):
    for f in fs:
        if f.endswith(".jar"):
            try:
                with zipfile.ZipFile(os.path.join(r, f)) as z:
                    if "tr/com/havelsan/uyap/system/editor/common/WPAppManager.class" in z.namelist():
                        ana = r
            except zipfile.BadZipFile:
                pass
if not ana:
    print("   HATA: paketin icinde editor JAR'i (WPAppManager) bulunamadi"); sys.exit(1)
os.makedirs(hedef, exist_ok=True)
n = 0
for f in sorted(os.listdir(ana)):
    if f.endswith(".jar"):
        shutil.copy2(os.path.join(ana, f), os.path.join(hedef, f)); n += 1; print("   ->", f)
print("   %d jar ~/jars altina kopyalandi." % n)
PY
}
if [ "$DENEME" = "1" ]; then echo "[deneme] editor_indir"; else editor_indir || echo "   (Editor otomatik kurulamadi. Elle: uyap kur-editor /yol/uyapeditor_*_amd64.zip)"; fi
if [ "$YALNIZ_EDITOR" = "1" ]; then
  if [ -s "$HATA" ]; then cat "$HATA"; exit 1; fi
  rm -f "$HATA"; echo "Editor jar'lari guncellendi. Editoru yeniden acin."; exit 0
fi

# ---------------------------------------------------------------- 5) bilesenler
adim 5 "UYAP-Termux bileşenleri"
if [ "$DENEME" != "1" ]; then
  [ -f "$HOME/ue.py" ] && cp -a "$HOME/ue.py" "$HOME/ue.py.onceki" 2>/dev/null
  cp -a "$KOK/bilesenler/ue.py" "$HOME/ue.py"
  rm -rf "$HOME/java"; cp -a "$KOK/bilesenler/java" "$HOME/java"
  mkdir -p "$HOME/eimza"; cp -a "$KOK/bilesenler/eimza/." "$HOME/eimza/"
  cp -a "$KOK/araclar/yedek_al.sh" "$HOME/yedek_al.sh"
  chmod +x "$HOME"/eimza/*.sh "$HOME"/eimza/*.py "$HOME/yedek_al.sh" 2>/dev/null
  # eski v3 artiklari (yerini ~/java ve 'uyap' komutu aldi)
  rm -f "$HOME/AkiciUyap.java" "$HOME/AkiciUyap.class" "$HOME/.akici.hash" "$HOME"/eimza/TermuxCcidProvider*.class 2>/dev/null
  if command -v javac >/dev/null 2>&1 && bash "$HOME/eimza/agent-src/derle.sh" >/dev/null 2>&1; then iyi "eimza-agent.jar kaynaktan derlendi"
  elif [ -f "$HOME/eimza/eimza-agent.jar" ]; then echo "  - eimza-agent.jar derlenemedi; mevcut kopya kullaniliyor"
  else fail "eimza-agent.jar derlenemedi (javac yok?): pkg install openjdk-21 ; bash ~/eimza/agent-src/derle.sh"; fi
  if python3 "$HOME/ue.py" --derle >/dev/null 2>&1; then iyi "editor baslaticisi derlendi"
  else fail "editor baslaticisi derlenemedi: python3 ~/ue.py --derle"; fi
  rm -rf "$HOME/.ckz-kurulum"; mkdir -p "$HOME/.ckz-kurulum"; cp -a "$KOK/." "$HOME/.ckz-kurulum/"
  # 'uyap' komutu, git pull ile güncellenen bu kopyadaki kur.sh'i kullansın
  mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/uyap-termux"
  [ -d "$KOK/.git" ] && printf '%s\n' "$KOK" > "${XDG_CONFIG_HOME:-$HOME/.config}/uyap-termux/kaynak_dizini"
  mkdir -p "$HOME/.ckz-durum"; rm -f "$HOME/.ckz-durum/ONAYSIZ"
  [ "$ONAYSIZ" = "1" ] && echo "ONAYSIZ kurulum: yazar muhru dogrulanamadi ($(date '+%F %T'))" > "$HOME/.ckz-durum/ONAYSIZ"
  { ckz_satir; echo "kurulum: $(date '+%F %T')  surum: $CKZ_SURUM"; } > "$HOME/.ckz-durum/KURULUM.txt"
  echo "   ue.py, eimza/ ve mühür kopyası (~/.ckz-kurulum) yerleştirildi."
else echo "[deneme] bilesenler -> ~/ue.py, ~/eimza/"; fi

# ---------------------------------------------------------------- 6) Adalet E-Imza
adim 6 "Adalet E-İmza (T.C. Adalet Bakanlığı) — resmî kaynaktan"
adalet_indir() {
  [ -z "$ADALET_DEB" ] && [ -f "$HOME/eimza/adalet/eimza-tray.jar" ] && { echo "   zaten kurulu"; return 0; }
  local deb="$ADALET_DEB"
  [ -n "$deb" ] || deb="$(ls -1 "$HOME"/storage/downloads/adalet-eimza-tray*.deb /sdcard/Download/adalet-eimza-tray*.deb 2>/dev/null | sort -V | tail -1)"
  if [ -z "$deb" ]; then
    local json url
    json="$(curl -fsSL --max-time 30 https://cdn.uyap.gov.tr/framework/public/latest.json 2>/dev/null)" || json=""
    url="$(printf '%s' "$json" | python3 -c '
import sys, json, re
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
c = []
def w(x):
    if isinstance(x, dict): [w(v) for v in x.values()]
    elif isinstance(x, list): [w(v) for v in x]
    elif isinstance(x, str) and re.search(r"\.deb($|\?)", x): c.append(x)
w(d)
c.sort(key=lambda s: ("amd64" not in s, "linux" not in s.lower()))
if c:
    u = c[0]
    print(u if u.startswith("http") else "https://cdn.uyap.gov.tr" + (u if u.startswith("/") else "/" + u))
' 2>/dev/null)"
    if [ -n "$url" ]; then
      echo "   indiriliyor: $url"; curl -fL $CURL_I --max-time 900 -o "$T/adalet.deb" "$url" && deb="$T/adalet.deb" || fail "adalet .deb indirilemedi"
    fi
  fi
  if [ -z "$deb" ]; then
    fail "Adalet E-Imza paketi bulunamadi. https://eimza.adalet.gov.tr adresinden Linux (.deb) surumunu Download klasorune indirip: bash ~/eimza/adalet_kur.sh"
    return 1
  fi
  bash "$HOME/eimza/adalet_kur.sh" "$deb"
}
if [ "$DENEME" = "1" ]; then echo "[deneme] adalet_indir"; else adalet_indir || true; fi

# ---------------------------------------------------------------- 7) entegrasyon
adim 7 "Otomatik başlatma, masaüstü, dosya ilişkilendirme ve yazı tipleri"
if [ "$DENEME" != "1" ]; then
  bash "$HOME/eimza/kur.sh"
  mkdir -p "$HOME/.local/bin" "$HOME/.shortcuts"
  printf '#!/data/data/com.termux/files/usr/bin/bash\nMASAUSTU=%s exec bash "$HOME/eimza/xfce_baslat.sh"\n' "$([ "$HAFIF" = 1 ] && echo fluxbox || echo xfce)" > "$HOME/.local/bin/uyap-masaustu"
  chmod +x "$HOME/.local/bin/uyap-masaustu"; cp "$HOME/.local/bin/uyap-masaustu" "$HOME/.shortcuts/UYAP-Masaustu" 2>/dev/null
  printf '#!/data/data/com.termux/files/usr/bin/bash\nexec "$HOME/.local/bin/uyap"\n' > "$HOME/.shortcuts/UYAP-Menu"; chmod +x "$HOME/.shortcuts/UYAP-Menu"
  # v3'ten kalan eski kisayol (Termux:Widget) yeni masaustu baslaticisina yonlendirilir
  [ -f "$HOME/.shortcuts/uyap_baslat.sh" ] && cp "$HOME/.local/bin/uyap-masaustu" "$HOME/.shortcuts/uyap_baslat.sh"
  if [ "$YAZITIPI" = "1" ]; then "$HOME/.local/bin/uyap" yazitipi || fail "yazi tipleri kurulamadi (sonra: uyap yazitipi)"; fi
else echo "[deneme] bash ~/eimza/kur.sh ; uyap-masaustu kisayolu"; fi

echo
ckz_banner
[ "$ONAYSIZ" = "1" ] && echo "!!! ONAYSIZ KURULUM: bu kopya yazar mühürüyle doğrulanamadı."
if [ -s "$HATA" ]; then echo "Bazı adımlar tamamlanamadı ($HATA):"; cat "$HATA"; else rm -f "$HATA"; echo "Hata yok."; fi
cat <<'SON'

SIRADAKI ADIMLAR
  1) Android: Termux, Termux:X11 ve Termux:API için pil optimizasyonunu KAPATIN; Termux'a
     "diğer uygulamaların üzerinde göster" izni verin. Termux:API'yi bir kez açın.
  2) Menü:       uyap                 (durum, masaüstü, editör, ayarlar, yedek, tanı)
     Masaüstü:   uyap masaustu        (Termux:X11 açılır; ".udf" dosyalarına çift tıklayın)
     Panel:      uyap panel           (grafik Kontrol Merkezi: durum kartları + ayarlar)
  3) E-imza okuyucusunu OTG ile takın; "İzin ver" deyin (mümkünse "varsayılan olarak kullan").
  4) Tarayıcıdan UYAP Avukat Portal → e-imza ile giriş (Termux arka planda açık kalsın).
  5) PDF'te birebir Times New Roman için:   uyap yazitipi
  6) Telif ve mühür bilgisi:   uyap hakkinda
SON
