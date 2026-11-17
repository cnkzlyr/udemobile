#!/data/data/com.termux/files/usr/bin/bash
# JDK 14.0.2 (AdoptOpenJDK, aarch64, glibc) kurulumu: UYAP Editor'u ve e-imzayi "kendi" Java surumuyle calistirmak icin.
#
#   bash jdk14_kur.sh                 kur (varsa ~/.jdk-14.0.2'yi kullanir, yoksa indirir) + editoru buna gecir
#   bash jdk14_kur.sh --arsiv YOL     indirmeden, elinizdeki OpenJDK14U-jdk_aarch64_linux_hotspot_14.0.2_12.tar.gz ile
#   bash jdk14_kur.sh dene            yalnizca calisiyor mu bak (java -version + AWT)
#   bash jdk14_kur.sh birak           editoru tekrar Termux'un Java 21'ine gecir (JDK dosyalari silinmez)
#
# Neden boyle: Termux Android'in C kutuphanesini (bionic) kullanir; resmi Linux JDK'lari glibc ister.
#  1) Termux'un glibc deposundan glibc + X11/yazi tipi kutuphanelerinin glibc surumleri kurulur.
#  2) JDK'nin calistirilabilir dosyalari patchelf ile Termux glibc baglayicisina yonlendirilir.
#  3) Baslatici (ue.py) bu JDK'yi Termux'un her surece ekledigi LD_PRELOAD'u (termux-exec, bionic) TEMIZLEYEREK
#     calistirir; aksi halde glibc sureci acilista coker. 'grun' kullanilmaz: Java'yi baglayici uzerinden
#     baslatinca kendi klasorunu (JAVA_HOME) bulamiyor.
# Arsiv yalnizca resmi AdoptOpenJDK surumunden indirilir ve SHA-256 ile dogrulanir.
set -u
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
JDK="${UYAP_JDK14:-$HOME/.jdk-14.0.2}"
URL="https://github.com/AdoptOpenJDK/openjdk14-binaries/releases/download/jdk-14.0.2%2B12/OpenJDK14U-jdk_aarch64_linux_hotspot_14.0.2_12.tar.gz"
SHA256="ee87e9f03b1fbe6f328429b78fe1a9f44900026d220c90dfd747fe0bcd62d904"
GLIBC_LD="$PREFIX/glibc/lib/ld-linux-aarch64.so.1"
AYAR="${XDG_CONFIG_HOME:-$HOME/.config}/uyap-termux/ayarlar.ini"
GLIBC_PAKETLER="glibc glibc-runner zlib-glibc gcc-libs-glibc libx11-glibc libxext-glibc libxrender-glibc libxtst-glibc libxi-glibc libxau-glibc libxdmcp-glibc libxcb-glibc freetype-glibc fontconfig-glibc libpng-glibc libexpat-glibc alsa-lib-glibc"

say() { printf '%s\n' "$*"; }
hata() { printf 'HATA: %s\n' "$*" >&2; exit 1; }

ayar_yaz() { python3 - "$AYAR" "$1" "$2" "$3" <<'PY'
import configparser, os, sys
yol, bol, ad, deger = sys.argv[1:5]
c = configparser.ConfigParser(inline_comment_prefixes=(";",)); c.read(yol, encoding="utf-8")
if not c.has_section(bol): c.add_section(bol)
c.set(bol, ad, deger)
os.makedirs(os.path.dirname(yol), exist_ok=True)
with open(yol, "w", encoding="utf-8") as f:
    f.write("# UYAP-Termux ayarları. Değişiklikler editörün bir sonraki açılışında geçerli olur.\n\n"); c.write(f)
PY
}

calistir() {  # glibc JDK'yi LD_PRELOAD olmadan calistir. -Xshare:off: JDK 14'un hazir CDS arsivi 64K sayfa
  # bekliyor, Android cekirdegi 4K: "Unable to map CDS archive" (zararsiz ama gurultulu) -> kapat
  local java="$1"; shift
  env -u LD_PRELOAD -u LD_LIBRARY_PATH FONTCONFIG_FILE="$PREFIX/etc/fonts/fonts.conf" "$java" -Xshare:off "$@"
}

bashrc_temizle() {
  # Elle eklenmis PATH/LD_LIBRARY_PATH satirlari tum kabugu bozar (javac/java glibc'ye gider ve coker)
  local rc="$HOME/.bashrc"
  [ -f "$rc" ] || return 0
  if grep -qE 'jdk-14\.0\.2|glibc/lib' "$rc"; then
    cp -a "$rc" "$rc.jdk14-yedek"
    sed -i -E '/jdk-14\.0\.2\/bin/d; /glibc\/lib/d; /alias java14=/d' "$rc"
    say "  ~/.bashrc'deki JDK 14 PATH/LD_LIBRARY_PATH satirlari kaldirildi (yedek: ~/.bashrc.jdk14-yedek)."
    say "  Bu oturum icin:  export PATH=\"\${PATH//\$HOME\/.jdk-14.0.2\/bin:/}\"; unset LD_LIBRARY_PATH"
  fi
}

paketler() {
  say "== glibc paketleri"
  dpkg -s glibc-repo >/dev/null 2>&1 || pkg install -y glibc-repo || hata "glibc-repo kurulamadi"
  pkg update -y >/dev/null 2>&1
  local eksik=""
  for p in $GLIBC_PAKETLER patchelf; do dpkg -s "$p" >/dev/null 2>&1 || eksik="$eksik $p"; done
  if [ -n "$eksik" ]; then
    # shellcheck disable=SC2086
    pkg install -y $eksik || hata "glibc paketleri kurulamadi:$eksik"
  fi
  [ -f "$GLIBC_LD" ] || hata "glibc baglayicisi yok: $GLIBC_LD"
}

arsiv_ac() {
  local arsiv="$1"
  say "== SHA-256 dogrulaniyor"
  [ "$(sha256sum "$arsiv" | cut -d' ' -f1)" = "$SHA256" ] || hata "ozet uyusmadi: $arsiv resmi AdoptOpenJDK 14.0.2+12 aarch64 arsivi degil"
  say "  dogru ($SHA256)"
  rm -rf "$JDK.yeni"; mkdir -p "$JDK.yeni"
  tar -xzf "$arsiv" -C "$JDK.yeni" --strip-components=1 || hata "arsiv acilamadi"
  if [ -d "$JDK" ]; then rm -rf "$JDK.eski"; mv "$JDK" "$JDK.eski"; fi
  mv "$JDK.yeni" "$JDK"
  say "  $JDK kuruldu"
}

jdk_hazirla() {
  local arsiv="${1:-}"
  if [ -n "$arsiv" ]; then arsiv_ac "$arsiv"
  elif [ ! -x "$JDK/bin/java" ] || [ ! -f "$JDK/release" ]; then
    say "== JDK 14.0.2 indiriliyor (~200 MB, resmi AdoptOpenJDK)"
    local t; t="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/jdk14.XXXXXX")"
    curl -fL --progress-bar --max-time 3600 -o "$t/jdk14.tar.gz" "$URL" || { rm -rf "$t"; hata "indirilemedi"; }
    arsiv_ac "$t/jdk14.tar.gz"; rm -rf "$t"
  else
    say "== mevcut JDK kullaniliyor: $JDK ($(grep -o 'JAVA_VERSION="[^"]*"' "$JDK/release"))"
  fi
  grep -q 'JAVA_VERSION="14' "$JDK/release" 2>/dev/null || hata "$JDK bir JDK 14 degil"
  say "== calistirilabilir dosyalar Termux glibc baglayicisina yonlendiriliyor"
  local n=0 f
  for f in "$JDK"/bin/* "$JDK"/lib/jspawnhelper "$JDK"/lib/jexec; do
    [ -f "$f" ] && [ -x "$f" ] || continue
    head -c 4 "$f" | grep -q 'ELF' || continue
    patchelf --set-interpreter "$GLIBC_LD" "$f" 2>/dev/null && n=$((n + 1))
  done
  say "  $n dosya"
  # yazi tipleri: fontconfig bulamazsa Java'nin kendi klasorune bak (DejaVu + varsa Microsoft)
  mkdir -p "$JDK/lib/fonts"
  for f in "$PREFIX"/share/fonts/TTF/*.ttf "$HOME"/.fonts/*/*.[Tt][Tt][Ff] "$HOME"/.fonts/*.[Tt][Tt][Ff]; do
    [ -f "$f" ] && ln -sf "$f" "$JDK/lib/fonts/$(basename "$f")"
  done
}

dene() {
  say "== deneme"
  local v
  v="$(calistir "$JDK/bin/java" -version 2>&1)"
  printf '%s\n' "$v" | sed 's/^/  /'
  printf '%s' "$v" | grep -q 'version "14.0.2"' || return 1
  # AWT kutuphaneleri (X11) yukleniyor mu: gorunmez modda font + grafik ortamini baslat
  if calistir "$JDK/bin/java" -Djava.awt.headless=true -XshowSettings:properties -version 2>&1 | grep -q 'java.home'; then
    say "  JVM ayarlari okunuyor: tamam"
  fi
  local d; d="$(mktemp -d)"
  cat > "$d/A.java" <<'J'
public class A { public static void main(String[] a) throws Exception {
  java.awt.GraphicsEnvironment g = java.awt.GraphicsEnvironment.getLocalGraphicsEnvironment();
  System.out.println("AWT tamam: " + g.getAvailableFontFamilyNames().length + " yazi tipi, ekran=" + (g.isHeadless() ? "yok" : "var"));
} }
J
  local awt; awt="$(calistir "$JDK/bin/java" "$d/A.java" 2>&1 | tail -1)"
  rm -rf "$d"
  say "  $awt"
  case "$awt" in "AWT tamam"*) return 0 ;; *) say "  (AWT/X11 kutuphaneleri yuklenemedi)"; return 1 ;; esac
}

case "${1:-kur}" in
  kur|--arsiv)
    arsiv=""; [ "${1:-}" = "--arsiv" ] && arsiv="${2:-}"; [ "${2:-}" = "--arsiv" ] && arsiv="${3:-}"
    [ -n "$arsiv" ] && [ ! -f "$arsiv" ] && hata "arsiv bulunamadi: $arsiv"
    bashrc_temizle
    paketler
    jdk_hazirla "$arsiv"
    if dene; then
      ayar_yaz java yol "$JDK/bin/java"
      say ""
      say "JDK 14.0.2 hazir; UYAP Editor bundan sonra bununla acilir ($AYAR: [java] yol)."
      say "Geri almak icin: uyap jdk14 birak"
    else
      hata "JDK 14 calismadi. Editor Java 21 ile calismaya devam eder. Rapor: uyap tani"
    fi ;;
  dene) dene ;;
  birak) ayar_yaz java yol ""; say "Editor tekrar otomatik secilen Java ile acilacak (JDK dosyalari $JDK altinda duruyor)." ;;
  *) sed -n '2,8p' "$0"; exit 2 ;;
esac
