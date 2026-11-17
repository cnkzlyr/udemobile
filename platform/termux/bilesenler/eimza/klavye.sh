#!/data/data/com.termux/files/usr/bin/bash
# Fiziksel klavye ayari (Termux:X11): Turkce Q duzeni + Ctrl/Alt/AltGr kisayollarinin calismasi.
#
# Sorun: Termux:X11 varsayilan olarak harfleri Android'in duzeninden "metin" olarak gonderir, Ctrl/Alt basiliyken ise
# ham tarama kodu (scancode) gonderir ve X sunucusu onu kendi (varsayilan: ABD) duzeniyle cozer. Iki yol karisinca
# Ctrl+A gibi kisayollar ve Turkce harfler tutarsiz olur. Cozum: tum tuslari tarama kodu olarak gonder
# ("Prefer scancodes") ve X'in duzenini Turkce yap (setxkbmap tr). Boylece klavye bilgisayardaki gibi davranir:
#   Ctrl+A/C/V/X/Z/S, Alt+Tab, AltGr+Q = @, AltGr+E = €, ğ ü ş ı ö ç dogrudan.
#
#   bash klavye.sh            tercih + uygula (Termux:X11 acikken)
#   bash klavye.sh uygula     yalnizca X duzeni (setxkbmap + XFCE ayari)
#   bash klavye.sh tercih     yalnizca Termux:X11 tercihleri (uygulama on planda/arka planda acik olmali)
#   bash klavye.sh xfce-xml   XFCE oturumu baslamadan once klavye duzeni ayar dosyasini yazar
#   bash klavye.sh durum
# Dokunmatik ekran (Termux:X11 "Touchscreen input mode"):
#   dokunmatik (varsayilan) = parmagin altina tiklar; surukleyerek metin secer/tasir; uzun basma = sag tik
#   touchpad = dizustu dokunmatik yuzeyi gibi (imleci parmakla kaydirirsiniz)    dogrudan = ham dokunma olaylari
# Ekran klavyesi: kaydirarak yazma ve yazma onerileri acik kalir (enforceCharBasedInput=false).
# Fare/dokunmatik yuzey baglaninca bunlar bu ayardan etkilenmez: bilgisayardaki gibi calisir.
# Ayarlar: ~/.config/uyap-termux/ayarlar.ini
#   [klavye] duzen=tr  varyant=(bos=Q, f=F)  tarama_kodlari=evet  dokunma=dokunmatik|touchpad|dogrudan
set -u
AYAR="${XDG_CONFIG_HOME:-$HOME/.config}/uyap-termux/ayarlar.ini"
export DISPLAY="${DISPLAY:-:0}"

ayar() { python3 - "$AYAR" "$1" <<'PY' 2>/dev/null || printf '%s' "$2"
import configparser, sys
c = configparser.ConfigParser(inline_comment_prefixes=(";",)); c.read(sys.argv[1], encoding="utf-8")
v = c.get("klavye", sys.argv[2], fallback=None)
sys.exit(1) if v is None else print(v.strip(), end="")
PY
}
DUZEN="$(ayar duzen tr)"; [ -n "$DUZEN" ] || DUZEN="tr"
VARYANT="$(ayar varyant '')"
TARAMA="$(ayar tarama_kodlari evet)"
case "$TARAMA" in evet|e|true|1|acik) TARAMA=true ;; *) TARAMA=false ;; esac
DOKUNMA="$(ayar dokunma dokunmatik)"
case "$DOKUNMA" in touchpad|trackpad) DOKUNMA_KOD=1 ;; dogrudan|direct) DOKUNMA_KOD=3 ;; *) DOKUNMA="dokunmatik"; DOKUNMA_KOD=2 ;; esac

tercih() {
  if ! command -v termux-x11-preference >/dev/null 2>&1; then
    echo "termux-x11-preference yok (termux-x11-nightly paketi?)"; return 1
  fi
  # Uygulama acik degilse arac sonsuza dek bekler: zaman asimi sart
  if timeout 15 termux-x11-preference "preferScancodes"="$TARAMA" "hardwareKbdScancodesWorkaround"="true" \
        "dexMetaKeyCapture"="true" "touchMode"="$DOKUNMA_KOD" "enforceCharBasedInput"="false" \
        "displayResolutionMode"="native" >/dev/null 2>&1; then
    echo "Termux:X11: tarama kodlari=$TARAMA, dokunma=$DOKUNMA, oneriler/kaydirarak yazma=acik, cozunurluk=yerel"
  else
    echo "Termux:X11 tercihleri yazilamadi (uygulama acik mi?). Elle: Termux:X11 > Ayarlar > Klavye > 'Prefer scancodes when possible'"
    return 1
  fi
}

xfce_xml() {
  local d="${XDG_CONFIG_HOME:-$HOME/.config}/xfce4/xfconf/xfce-perchannel-xml"
  mkdir -p "$d"
  cat > "$d/keyboard-layout.xml" <<EOT
<?xml version="1.0" encoding="UTF-8"?>

<channel name="keyboard-layout" version="1.0">
  <property name="Default" type="empty">
    <property name="XkbDisable" type="bool" value="false"/>
    <property name="XkbLayout" type="string" value="$DUZEN"/>
    <property name="XkbVariant" type="string" value="$VARYANT"/>
    <property name="XkbOptions" type="empty">
      <property name="Group" type="string" value=""/>
    </property>
  </property>
</channel>
EOT
}

uygula() {
  xfce_xml
  if command -v xfconf-query >/dev/null 2>&1 && pgrep -f xfconfd >/dev/null 2>&1; then
    xfconf-query -c keyboard-layout -p /Default/XkbDisable -n -t bool -s false 2>/dev/null
    xfconf-query -c keyboard-layout -p /Default/XkbLayout -n -t string -s "$DUZEN" 2>/dev/null
    xfconf-query -c keyboard-layout -p /Default/XkbVariant -n -t string -s "$VARYANT" 2>/dev/null
  fi
  if ! command -v setxkbmap >/dev/null 2>&1; then
    echo "setxkbmap yok: pkg install xorg-setxkbmap xorg-xkbcomp"; return 1
  fi
  local v=(); [ -n "$VARYANT" ] && v=(-variant "$VARYANT")
  setxkbmap -layout "$DUZEN" "${v[@]}" -option "" 2>/dev/null || { echo "setxkbmap basarisiz (X ekrani $DISPLAY acik mi?)"; return 1; }
  # Bazi X sunucularinda setxkbmap 0 doner ama duzen degismez: gercek tus haritasindan dogrula
  if ! duzen_dogru && command -v xkbcomp >/dev/null 2>&1; then
    setxkbmap -layout "$DUZEN" "${v[@]}" -option "" -print 2>/dev/null | xkbcomp -w 0 - "$DISPLAY" >/dev/null 2>&1
  fi
  if duzen_dogru; then
    echo "X klavye duzeni: $DUZEN${VARYANT:+ ($VARYANT)}"
  else
    echo "UYARI: X klavye duzeni $DUZEN olarak uygulanamadi (setxkbmap -query: $(setxkbmap -query 2>/dev/null | awk '/layout/{print $2}'))."
    echo "       Elle: XFCE > Ayarlar > Klavye > Duzen > 'Sistem varsayilanini kullan' kapali, Turkce ekle."
    return 1
  fi
}

# Sunucudaki gercek tus haritasinda duzenin sembol dosyasi var mi (or. "pc+tr+inet(evdev)")
duzen_dogru() {
  command -v xkbcomp >/dev/null 2>&1 || { setxkbmap -query 2>/dev/null | grep -q "layout: *$DUZEN"; return; }
  xkbcomp "$DISPLAY" - 2>/dev/null | grep -m1 '^xkb_symbols' | grep -q "+$DUZEN"
}

durum() {
  echo "ayar: duzen=$DUZEN varyant=${VARYANT:-Q} tarama_kodlari=$TARAMA dokunma=$DOKUNMA"
  command -v setxkbmap >/dev/null 2>&1 && setxkbmap -query 2>/dev/null | sed 's/^/  X: /'
  command -v termux-x11-preference >/dev/null 2>&1 && timeout 10 termux-x11-preference list 2>/dev/null \
    | grep -E '"(preferScancodes|hardwareKbdScancodesWorkaround|dexMetaKeyCapture|touchMode|enforceCharBasedInput|displayResolutionMode)"' | sed 's/^/  Termux:X11: /'
}

case "${1:-hepsi}" in
  hepsi) tercih; uygula ;;
  uygula) uygula ;;
  tercih) tercih ;;
  xfce-xml) xfce_xml ;;
  durum) durum ;;
  *) echo "kullanim: klavye.sh [uygula|tercih|xfce-xml|durum]"; exit 2 ;;
esac
