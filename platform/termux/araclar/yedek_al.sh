#!/data/data/com.termux/files/usr/bin/bash
# UYAP / Termux TAM YEDEK: baska bir Android cihazda sifirdan ayni sistemi kurabilmek icin her seyi toplar.
#
#   bash yedek_al.sh [etiket] [--belgeler] [--deb] [--ek yol]...
#     etiket      dosya adina eklenir (or. v3-oncesi, v3-sonrasi)
#     --belgeler  /sdcard/Documents/UYAP_Belgelerim ve editorun otomatik kayitlari (.uki/yedekler) de dahil edilir
#                 (VARSAYILAN DEGIL: muvekkil belgeleri gizlidir)
#     --tarayici  Firefox/Chromium profilleri de dahil edilir (VARSAYILAN DEGIL: kayitli parolalar, cerezler, oturumlar)
#     --deb       Download'daki adalet-eimza-tray*.deb / .AppImage dosyalari da dahil edilir
#     --ek yol    ek dosya/klasor (HOME'a gore ya da mutlak); birden cok kez verilebilir
#
# Cikti: <Download>/termux-yedek/uyap-termux-yedek_<etiket>_<tarih>.zip   (+ .sha256)
# Icerik: HOME'daki yapi (ue.py, jars, eimza, ~/.termux, ~/.shortcuts, XFCE/X11 ayarlari, masaustu/mime kayitlari, ...),
#         paket listeleri (pkg/pip/npm), depo bilgisi, sistem bilgisi, editor ayarlari (.uki), ve zip'in icinde
#         geri_yukle.sh (yeni cihazda kurulum + bagimliliklari kuran betik).
# PIN'ler, e-imza ozel anahtarlari ve calisma zamani jetonlari YEDEKTE OLMAZ (anahtarlar zaten karttadir).
# Tarayici profilleri (kayitli parolalar!), SSH/GPG anahtarlari, muhur ozel anahtari (~/.ckz-muhur) ve belge
# otomatik kayitlari varsayilan olarak HARIC tutulur. Zip yalnizca sahibinin okuyabilecegi izinle (600) yazilir.
# !!! Yedegi "baglantiya sahip herkes" ile paylasmayin (Drive/Dropbox): kisiye ozel paylasin.
set -u
ETIKET="yedek"; BELGELER=0; DEB=0; TARAYICI=0; EKLER=()
first=1
while [ $# -gt 0 ]; do
  case "$1" in
    --belgeler) BELGELER=1 ;;
    --deb) DEB=1 ;;
    --tarayici) TARAYICI=1 ;;
    --ek) shift; [ $# -gt 0 ] && EKLER+=("$1") ;;
    -*) echo "Bilinmeyen secenek: $1"; exit 2 ;;
    *) if [ "$first" = "1" ]; then ETIKET="$1"; first=0; else EKLER+=("$1"); fi ;;
  esac
  shift
done
ETIKET="$(printf '%s' "$ETIKET" | tr -c 'A-Za-z0-9._-' '_')"

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TS="$(date +%Y%m%d-%H%M%S)"
WORK="$HOME/storage/downloads"; [ -d "$WORK" ] || WORK=/sdcard/Download
if [ -d "$WORK" ]; then OUTDIR="${YEDEK_DIR:-$WORK/termux-yedek}"
else OUTDIR="${YEDEK_DIR:-$HOME/termux-yedek}"; echo "(uyari) Download klasoru yok -> $OUTDIR . Onerilen: termux-setup-storage"; fi
mkdir -p "$OUTDIR" || { echo "Cikti klasoru olusturulamadi: $OUTDIR"; exit 1; }
OUT="$OUTDIR/uyap-termux-yedek_${ETIKET}_${TS}.zip"
command -v python3 >/dev/null 2>&1 || { echo "python3 gerekli: pkg install python"; exit 1; }

STG="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/yedek.XXXXXX")"
trap 'rm -rf "$STG"' EXIT
mkdir -p "$STG/manifest" "$STG/sistem" "$STG/downloads_uki"
ITEMS="$STG/items.txt"; : > "$ITEMS"     # satirlar: KAYNAK|ZIP-ICI-YOL
add() { [ -e "$1" ] || [ -L "$1" ] && printf '%s|%s\n' "$1" "$2" >> "$ITEMS"; }

echo "== Yedek: $OUT"
echo "== 1/4 sistem bilgisi ve paket listeleri"
{
  echo "yedek_tarihi: $(date '+%F %T')  etiket: $ETIKET"
  echo "HOME: $HOME   PREFIX: $PREFIX"
  echo "uname: $(uname -a)"
  for k in ro.product.manufacturer ro.product.model ro.build.version.release ro.product.cpu.abi; do
    v="$(getprop $k 2>/dev/null)"; [ -n "$v" ] && echo "$k: $v"
  done
  echo "--- termux-info"; termux-info 2>&1 | head -60
  echo "--- java"; ls "$PREFIX/lib/jvm" 2>/dev/null; java -version 2>&1 | head -3
  echo "--- python"; python3 --version 2>&1
} > "$STG/manifest/termux-info.txt" 2>&1
apt-mark showmanual 2>/dev/null | sort > "$STG/manifest/paketler_manuel.txt"
dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' 2>/dev/null | sort > "$STG/manifest/paketler_tumu.txt"
: > "$STG/manifest/repo_paketleri.txt"
for r in x11-repo tur-repo root-repo science-repo game-repo unstable-repo; do
  dpkg -s "$r" >/dev/null 2>&1 && echo "$r" >> "$STG/manifest/repo_paketleri.txt"
done
{ cat "$PREFIX/etc/apt/sources.list" 2>/dev/null; for f in "$PREFIX"/etc/apt/sources.list.d/*; do [ -f "$f" ] && { echo "# $f"; cat "$f"; }; done; } > "$STG/manifest/repolar.txt" 2>/dev/null
# repo paketleri ayri kurulur: manuel listeden cikar (geri_yukle once repolari kurar, sonra bunlari)
python3 -m pip list --not-required --format=freeze 2>/dev/null | grep -viE '^(pip|setuptools|wheel)==' > "$STG/manifest/pip.txt"
command -v npm >/dev/null 2>&1 && npm ls -g --depth=0 --parseable 2>/dev/null | tail -n +2 | xargs -n1 basename 2>/dev/null | grep -v '^npm$' > "$STG/manifest/npm_global.txt"
{ echo "termux ile ilgili Android uygulamalari (yedegin alindigi cihaz):"; pm list packages 2>/dev/null | grep -i termux || echo "(pm ile listelenemedi)"; } > "$STG/manifest/android_uygulamalar.txt" 2>&1
[ -d "$HOME/.shortcuts" ] && ls -la "$HOME/.shortcuts" > "$STG/manifest/kisayollar.txt" 2>&1

# sistem duzeyi dosyalar (bilgi/yedek amacli; geri yukleme bunlari otomatik yazmaz)
for f in "$PREFIX/etc/apt/sources.list" "$PREFIX/etc/motd" "$PREFIX/etc/bash.bashrc" "$PREFIX/etc/termux-login.sh"; do
  [ -f "$f" ] && cp -a "$f" "$STG/sistem/"
done
[ -d "$PREFIX/etc/apt/sources.list.d" ] && cp -a "$PREFIX/etc/apt/sources.list.d" "$STG/sistem/"
[ -d "$PREFIX/etc/profile.d" ] && cp -a "$PREFIX/etc/profile.d" "$STG/sistem/"
[ -d "$PREFIX/etc/termux" ] && cp -a "$PREFIX/etc/termux" "$STG/sistem/termux_etc"

echo "== 2/4 dosyalar toplaniyor"
# ---- HOME: bilinen ogeler
for it in ue.py uyap_baslat.sh AkiciUyap.java jars eimza \
          .bashrc .bash_profile .profile .zshrc .zprofile .inputrc .vimrc .gitconfig .tmux.conf .nanorc \
          .xinitrc .xsession .xprofile .Xresources .Xdefaults .fluxbox .vnc \
          .termux .shortcuts .config .local .themes .icons .fonts .java .uyap-editor .eimza Desktop; do
  add "$HOME/$it" "home/$it"
done
# ---- HOME: ust duzeydeki kucuk betikler (*.sh, *.py, *.java)
for f in "$HOME"/*.sh "$HOME"/*.py "$HOME"/*.java "$HOME"/*.yedek "$HOME"/ue.py.*; do
  [ -f "$f" ] && add "$f" "home/$(basename "$f")"
done
# ---- Download altindaki editor ayarlari (editor -Duser.home=Download oldugu icin .uki orada olusur)
for d in "$WORK"/.uki* "$WORK"/.java "$WORK"/.uyap* ; do
  [ -e "$d" ] && add "$d" "downloads_uki/$(basename "$d")"
done
# ---- istege bagli
[ "$BELGELER" = "1" ] && add /sdcard/Documents/UYAP_Belgelerim "belgeler"
if [ "$DEB" = "1" ]; then
  for f in "$WORK"/adalet-eimza-tray* ; do [ -f "$f" ] && add "$f" "deb/$(basename "$f")"; done
fi
for e in "${EKLER[@]:-}"; do
  [ -n "$e" ] || continue
  case "$e" in /*) src="$e" ;; *) src="$HOME/$e" ;; esac
  case "$src" in "$HOME"/*) add "$src" "home/${src#$HOME/}" ;; *) add "$src" "ek/$(basename "$src")" ;; esac
done

# ---- OKU.txt + geri yukleme betigi
cat > "$STG/OKU.txt" <<'OKU'
UYAP-TERMUX YEDEGI
==================
Yeni cihazda:
  1) Termux, Termux:X11, Termux:API (+Boot/Widget) uygulamalarini AYNI kaynaktan kurun (F-Droid veya GitHub).
  2) Termux:  pkg install -y unzip ; termux-setup-storage
  3) unzip -o <bu zip> geri_yukle.sh   ve   bash geri_yukle.sh <bu zip>
Ayrintilar geri_yukle.sh'in basindaki yorumlarda. Yedegin icerigi: manifest/dosya_listesi.txt
Gizlilik: PIN/ozel anahtar, tarayici profili (kayitli parolalar) ve belge otomatik kayitlari varsayilan olarak YOKTUR.
Editor ayarlari son acilan dosya adlarini icerebilir. Bu zip'i "baglantiya sahip herkes" ile PAYLASMAYIN.
OKU
cat > "$STG/geri_yukle.sh" <<'GERI_YUKLE_BITTI'
#!/data/data/com.termux/files/usr/bin/bash
# UYAP / Termux sistemini YENI bir Android cihazda geri kurar.
#
# ONCE (Android tarafi, elle):
#   1) Termux, Termux:X11, Termux:API (+ kullaniyorsaniz Termux:Boot, Termux:Widget/Shortcuts, Termux:Styling)
#      uygulamalarini AYNI kaynaktan kurun (hepsi F-Droid VEYA hepsi GitHub). Play Store surumleri UYUMSUZDUR.
#   2) Termux'u acin:   pkg install -y unzip
#                       termux-setup-storage        (izin penceresinde "Izin ver")
#   3) Yedek zip'ini telefona koyun (or. Download/termux-yedek/) ve:
#         cd ~ && unzip -o /sdcard/Download/termux-yedek/uyap-termux-yedek_XXX.zip geri_yukle.sh
#         bash geri_yukle.sh /sdcard/Download/termux-yedek/uyap-termux-yedek_XXX.zip
#
# Secenekler:  --paketleri-atla   (pkg/pip/npm kurulumunu yapma, yalnizca dosyalari geri koy)
#              --dosyalari-atla   (yalnizca paketleri kur)
#              --deneme           (hicbir sey degistirmeden ne yapilacagini yaz)
set -u
PAKET=1; DOSYA=1; DENEME=0; ZIP=""
for a in "$@"; do
  case "$a" in
    --paketleri-atla) PAKET=0 ;;
    --dosyalari-atla) DOSYA=0 ;;
    --deneme) DENEME=1 ;;
    -*) echo "Bilinmeyen secenek: $a"; exit 2 ;;
    *) ZIP="$a" ;;
  esac
done
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TS="$(date +%Y%m%d-%H%M%S)"
say()  { echo "$@"; }
run()  { if [ "$DENEME" = "1" ]; then echo "[deneme] $*"; else "$@"; fi; }
HATA="$HOME/geri_yukle_hatalar_$TS.txt"; : > "$HATA" 2>/dev/null

if [ -z "$ZIP" ]; then
  for d in "$PWD" "$HOME" "$HOME/storage/downloads/termux-yedek" "$HOME/storage/downloads" /sdcard/Download/termux-yedek /sdcard/Download; do
    f=$(ls -1t "$d"/uyap-termux-yedek*.zip 2>/dev/null | head -1)
    [ -n "$f" ] && { ZIP="$f"; break; }
  done
fi
[ -n "$ZIP" ] && [ -f "$ZIP" ] || { echo "Yedek zip'i bulunamadi. Kullanim: bash geri_yukle.sh /yol/uyap-termux-yedek_*.zip"; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "unzip yok: pkg install -y unzip"; exit 1; }
say "Yedek: $ZIP"

TMPD="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/geri.XXXXXX")"
trap 'rm -rf "$TMPD"' EXIT
say "Zip aciliyor ..."
unzip -q -o "$ZIP" -d "$TMPD" || { echo "Zip acilamadi"; exit 1; }
[ -d "$TMPD/manifest" ] || { echo "Bu zip bir UYAP-Termux yedegi gibi gorunmuyor."; exit 1; }
[ -f "$TMPD/manifest/termux-info.txt" ] && { say "--- yedegin alindigi sistem:"; head -12 "$TMPD/manifest/termux-info.txt"; say "---"; }

fail() { echo "$*" | tee -a "$HATA" >/dev/null; }

# ------------------------------------------------------------------ paketler
if [ "$PAKET" = "1" ]; then
  say "== 1/4 paket deposu ve paketler"
  run pkg update -y
  if [ -s "$TMPD/manifest/repo_paketleri.txt" ]; then
    while read -r r; do [ -n "$r" ] || continue
      say "  depo: $r"; run pkg install -y "$r" || fail "depo kurulamadi: $r"
    done < "$TMPD/manifest/repo_paketleri.txt"
    run pkg update -y
  fi
  if [ -s "$TMPD/manifest/paketler_manuel.txt" ]; then
    say "  Paketler kuruluyor (uzun surebilir) ..."
    LIST="$(grep -v '^$' "$TMPD/manifest/paketler_manuel.txt" | tr '\n' ' ')"
    if [ "$DENEME" = "1" ]; then echo "[deneme] pkg install -y $LIST"
    else
      pkg install -y $LIST >/dev/null 2>&1 || {
        say "  Toplu kurulum basarisiz; tek tek deneniyor ..."
        for p in $LIST; do
          dpkg -s "$p" >/dev/null 2>&1 && continue
          pkg install -y "$p" >/dev/null 2>&1 && say "   + $p" || { say "   ! $p kurulamadi"; fail "paket kurulamadi: $p"; }
        done
      }
    fi
  fi
  if [ -s "$TMPD/manifest/pip.txt" ] && command -v python3 >/dev/null 2>&1; then
    say "  pip paketleri ..."
    run python3 -m pip install -r "$TMPD/manifest/pip.txt" >/dev/null 2>&1 \
      || run python3 -m pip install --break-system-packages -r "$TMPD/manifest/pip.txt" >/dev/null 2>&1 \
      || fail "pip requirements tamamen kurulamadi: manifest/pip.txt"
  fi
  if [ -s "$TMPD/manifest/npm_global.txt" ] && command -v npm >/dev/null 2>&1; then
    say "  npm global paketleri ..."
    for p in $(cat "$TMPD/manifest/npm_global.txt"); do run npm install -g "$p" >/dev/null 2>&1 || fail "npm kurulamadi: $p"; done
  fi
fi

# ------------------------------------------------------------------ dosyalar
if [ "$DOSYA" = "1" ]; then
  say "== 2/4 dosyalar (HOME)"
  ESKI=""
  if [ -d "$TMPD/home" ]; then
    ESKI="$HOME/.geri_yukle_eski_$TS"
    while IFS= read -r -d '' src; do
      item="$(basename "$src")"
      if [ -e "$HOME/$item" ] || [ -L "$HOME/$item" ]; then
        run mkdir -p "$ESKI"; run mv "$HOME/$item" "$ESKI/$item"
      fi
      run cp -a "$src" "$HOME/$item"
    done < <(find "$TMPD/home" -mindepth 1 -maxdepth 1 -print0)
    [ -n "$ESKI" ] && [ -d "$ESKI" ] && say "  (mevcut dosyalar buraya tasindi: $ESKI)"
  fi
  # depolama: Download altindaki editor ayarlari (.uki vb.)
  WORK="$HOME/storage/downloads"; [ -d "$WORK" ] || WORK=/sdcard/Download
  if [ -d "$TMPD/downloads_uki" ] && [ -n "$(ls -A "$TMPD/downloads_uki" 2>/dev/null)" ]; then
    if [ -d "$WORK" ]; then say "  Editor ayarlari -> $WORK"; run cp -a "$TMPD/downloads_uki/." "$WORK/"
    else fail "Download klasoru yok (termux-setup-storage?): editor ayarlari (.uki) geri konmadi; zip icinde downloads_uki/ altinda duruyor"; fi
  fi
  if [ -d "$TMPD/belgeler" ]; then
    run mkdir -p /sdcard/Documents/UYAP_Belgelerim && run cp -a "$TMPD/belgeler/." /sdcard/Documents/UYAP_Belgelerim/ && say "  Belgeler geri konuldu."
  fi
  if [ -d "$TMPD/deb" ] && [ -d "$WORK" ]; then run cp -a "$TMPD/deb/." "$WORK/" && say "  Adalet paketi (deb/AppImage) Download'a konuldu."; fi
  if [ -d "$TMPD/ek" ]; then say "  --ek ile alinan dosyalar zip icinde 'ek/' altinda; elle yerlestirin."; fi

  say "== 3/4 yetkiler ve masaustu tumlesmesi"
  run chmod +x "$HOME"/*.sh "$HOME"/eimza/*.sh "$HOME"/eimza/*.py "$HOME"/.local/bin/* "$HOME"/.termux/boot/* "$HOME"/.shortcuts/* 2>/dev/null
  [ -d "$HOME/.local/share/mime" ] && command -v update-mime-database >/dev/null 2>&1 && run update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1
  [ -d "$HOME/.local/share/applications" ] && command -v update-desktop-database >/dev/null 2>&1 && run update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1
  if [ -d "$HOME/Desktop" ] && command -v gio >/dev/null 2>&1; then
    for d in "$HOME"/Desktop/*.desktop; do [ -f "$d" ] && run gio set "$d" metadata::trusted true 2>/dev/null; done
  fi
  # Termux ayarlarinin yeniden okunmasi
  command -v termux-reload-settings >/dev/null 2>&1 && run termux-reload-settings 2>/dev/null
  # e-imza / editor: yollar sabit ($HOME ayni) oldugu icin kayit dosyalari oldugu gibi gecerli; yine de yenile
  [ -f "$HOME/eimza/masaustu_kur.sh" ] && run bash "$HOME/eimza/masaustu_kur.sh" >/dev/null 2>&1
fi

# ------------------------------------------------------------------ Android tarafi
say "== 4/4 Android'de ELLE yapilacaklar"
cat <<'ANDROID'
  [ ] Termux:X11 uygulamasinin AYARLARINI (ekran cozunurlugu, klavye, "Prefer scancodes" vb.) elle girin
      (uygulama icinde; yedeklenemez). Ayrica bkz. manifest/termux-info.txt.
  [ ] Termux'a: Ayarlar > Uygulamalar > Termux > "Diger uygulamalarin uzerinde goster" izni (Android PIN penceresi icin)
  [ ] Termux, Termux:API ve Termux:Boot icin pil optimizasyonunu KAPATIN ("Kisitlama yok").
  [ ] Termux:Boot'u bir kez ACIN (yoksa telefon acilisinda calismaz). Termux:API'yi de bir kez acin.
  [ ] USB e-imza okuyucuyu takin: "Izin ver" (mumkunse "varsayilan olarak kullan") deyin.
  [ ] Chrome: UYAP Avukat Portal'da e-imza girisinde "yerel ag erisimi" izni sorarsa izin verin.
  [ ] Oturumu kapatip Termux'u yeniden acin; sonra:  bash ~/eimza/adalet_baslat.sh durum
ANDROID
if [ -s "$HATA" ]; then echo; echo "Bazi adimlar basarisiz oldu (bkz. $HATA):"; cat "$HATA"; else rm -f "$HATA"; echo; echo "Hata yok."; fi
echo "Bitti."
GERI_YUKLE_BITTI
chmod +x "$STG/geri_yukle.sh"
add "$STG/OKU.txt" "OKU.txt"
add "$STG/geri_yukle.sh" "geri_yukle.sh"
for x in manifest sistem; do add "$STG/$x" "$x"; done

echo "== 3/4 zip olusturuluyor"
umask 077
YEDEK_TARAYICI="$TARAYICI" YEDEK_BELGELER="$BELGELER" python3 - "$OUT" "$ITEMS" "$STG" <<'PYBUILD'
import os, sys, zipfile, fnmatch, stat, time
out, items_path, stg = sys.argv[1:4]
DIR_EXCL = {"__pycache__", ".cache", "Trash", ".git", "node_modules"}
FILE_EXCL = ["*.class", "*.pyc", "*.log", "*.log.gz", "*.pid", "*.lck", ".akici.hash", "bridge.json",
             "instance.properties", "starting.pid", "tani.txt", "*.tmp", "mimeinfo.cache",
             "eimza-termux*.zip", "*.zip"]
PATH_EXCL = ["home/.local/lib/*", "home/.local/share/Trash/*", "home/.eimza/*.lck/*",
             "home/.eimza/adalet.display", "home/.termux/x11/*.sock",
             "home/.uyap-editor/siniflar/*", "home/.config/pulse/*", "home/.local/share/recently-used.xbel",
             "home/.local/share/gvfs-metadata/*", "downloads_uki/.uki/logs/*", "downloads_uki/.uki/smartCardSessionHandler"]
# GIZLI: yalnizca acik secenekle alinir
GIZLI_TARAYICI = ["home/.config/mozilla/*", "home/.mozilla/*", "home/.config/chromium/*",
                  "home/.config/google-chrome/*", "home/.cache/*"]
GIZLI_BELGE = ["downloads_uki/.uki/yedekler/*"]
# ASLA: hicbir secenekle alinmaz
ASLA = ["home/.ckz-muhur/*", "home/.ssh/*", "home/.gnupg/*", "home/.config/gh/*", "home/.git-credentials",
        "home/.netrc", "home/.pki/*", "home/.config/uyap-termux/gizli*"]
if os.environ.get("YEDEK_TARAYICI") != "1": PATH_EXCL += GIZLI_TARAYICI
if os.environ.get("YEDEK_BELGELER") != "1": PATH_EXCL += GIZLI_BELGE
PATH_EXCL += ASLA
def excluded(arc, name):
    if any(fnmatch.fnmatch(name, p) for p in FILE_EXCL): return True
    if any(fnmatch.fnmatch(arc, p) for p in PATH_EXCL): return True
    return False
n_files = 0; n_bytes = 0; listing = []; seen = set()
def add_file(z, src, arc):
    global n_files, n_bytes
    if arc in seen: return
    seen.add(arc)
    try:
        st = os.lstat(src)
        if stat.S_ISLNK(st.st_mode):
            zi = zipfile.ZipInfo(arc, time.localtime(st.st_mtime)[:6]); zi.create_system = 3
            zi.external_attr = (0o120777 << 16)
            z.writestr(zi, os.readlink(src)); listing.append(arc + "  -> (symlink)"); n_files += 1; return
        if not stat.S_ISREG(st.st_mode): return
        z.write(src, arc, compress_type=zipfile.ZIP_DEFLATED)
        n_files += 1; n_bytes += st.st_size; listing.append("%s  %d" % (arc, st.st_size))
    except (OSError, ValueError) as e:
        print("  atlandi:", src, e, file=sys.stderr)
with zipfile.ZipFile(out + ".part", "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
    for line in open(items_path, encoding="utf-8"):
        line = line.rstrip("\n")
        if "|" not in line: continue
        src, arc = line.split("|", 1)
        if os.path.isdir(src) and not os.path.islink(src):
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d not in DIR_EXCL]
                rel = os.path.relpath(root, src)
                base = arc if rel == "." else arc + "/" + rel.replace(os.sep, "/")
                for d in list(dirs):                      # dizin symlink'lerini link olarak sakla
                    p = os.path.join(root, d)
                    if os.path.islink(p): dirs.remove(d); add_file(z, p, base + "/" + d)
                for f in files:
                    a = base + "/" + f
                    if excluded(a, f): continue
                    add_file(z, os.path.join(root, f), a)
        else:
            a = arc
            if excluded(a, os.path.basename(a)) and not a.endswith((".sh", ".py", ".txt")): continue
            add_file(z, src, a)
    z.writestr("manifest/dosya_listesi.txt", "\n".join(sorted(listing)) + "\n")
os.chmod(out + ".part", 0o600)
os.replace(out + ".part", out)
print("  %d dosya, %.1f MB (sikistirilmamis)" % (n_files, n_bytes / 1048576.0))
PYBUILD
rc=$?
[ $rc -eq 0 ] && [ -f "$OUT" ] || { echo "Zip olusturulamadi"; exit 1; }

echo "== 4/4 dogrulama"
( cd "$OUTDIR" && sha256sum "$(basename "$OUT")" > "$(basename "$OUT").sha256" 2>/dev/null )
python3 - "$OUT" <<'PYCHK'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); bad = z.testzip()
names = z.namelist()
print("  zip saglam." if bad is None else "  BOZUK dosya: %s" % bad)
for must in ("geri_yukle.sh", "manifest/termux-info.txt", "manifest/paketler_manuel.txt"):
    print("  %-32s %s" % (must, "var" if must in names else "YOK"))
home = sorted({n.split('/')[1] for n in names if n.startswith('home/') and n.count('/') >= 1 and len(n.split('/')) > 1 and n.split('/')[1]})
other = sorted({n.split('/')[0] for n in names if not n.startswith('home/')})
print("  home/ ogeleri:", ", ".join(home)[:400])
print("  diger:", ", ".join(other)[:300])
PYCHK
SZ="$(du -h "$OUT" | cut -f1)"
echo
echo "YEDEK HAZIR: $OUT  ($SZ)"
echo "Baska cihaza/bilgisayara kopyalayin (USB, Drive, bulut...). Geri yukleme: zip icindeki geri_yukle.sh (OKU.txt'ye bakin)."
echo "UYARI: bulutta 'baglantiya sahip herkes' paylasimi ACMAYIN; yedek kisisel ayarlarinizi icerir."
[ "$TARAYICI" = "1" ] && echo "UYARI: --tarayici ile alindi: zip KAYITLI PAROLALARINIZI icerir. Sifreli bir ortamda saklayin."
