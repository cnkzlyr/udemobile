#!/bin/bash
# ⚖️ AVUKAT ASİSTANI - TELEFON TERMUX OTOMATİK KURULUM VE YAPILANDIRICI
set -e

echo "=================================================="
echo "⚖️  Avukat Asistanı - Telefon Termux Kurulumu"
echo "=================================================="

# 1. Depolama İzni Kontrolü
if [ ! -d "$HOME/storage" ]; then
    echo "📁 Depolama izni isteniyor (Download klasörüne erişim için)..."
    echo "⚠️  Lütfen telefon ekranında çıkan izne 'İZİN VER / ALLOW' deyin."
    termux-setup-storage
    sleep 3
else
    echo "✅ Depolama izni mevcut."
fi

# 2. Temel Paketlerin Kurulumu
echo "📦 Gerekli Termux paketleri kontrol ediliyor (python, curl, x11-repo, chromium)..."
pkg update -y || true
command -v python >/dev/null 2>&1 || pkg install -y python || true
command -v curl >/dev/null 2>&1 || pkg install -y curl || true
pkg install -y x11-repo || true
command -v chromium-browser >/dev/null 2>&1 || pkg install -y chromium || true
command -v git >/dev/null 2>&1 || pkg install -y git || true

# 3. Python Kütüphaneleri
# Not: Termux'ta "pip install --upgrade pip" YASAKTIR (python-pip paketini bozar); pip güncellenmez.
echo "🐍 Python kütüphaneleri yükleniyor..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt || echo "⚠️ Bazı paketler kurulamadı; aşağıdaki kontrol eksikleri gösterir."
else
    pip install requests pypdf selenium openpyxl || true
fi
# Dosya defteri (SQLAlchemy): saf Python paketi, bağımlılıksız kurulur. Normal kurulum Android'de derlenemeyen
# 'greenlet' eklentisini de çeker; bu sistem onu kullanmaz.
python3 -c "import sqlalchemy" 2>/dev/null || pip install --no-deps "sqlalchemy>=2.0,<2.1" typing-extensions || true
echo "🔎 Kurulum kontrolü:"
for m in requests pypdf selenium openpyxl sqlalchemy; do
    if python3 -c "import $m" 2>/dev/null; then echo "   ✅ $m"; else echo "   ❌ $m  (elle: pip install $m)"; fi
done

# 4. State (Hafıza) Dosyası Aktarımı
if [ -f ".avukat_asistan_state.json" ] && [ ! -f "$HOME/.avukat_asistan_state.json" ]; then
    cp .avukat_asistan_state.json "$HOME/.avukat_asistan_state.json"
    echo "✅ İşlem geçmişi ve hafıza (~/.avukat_asistan_state.json) aktarıldı."
elif [ -f ".avukat_asistan_state.json" ]; then
    echo "ℹ️  Mevcut hafıza dosyası korundu."
fi

# 5. tebligat.sh Komut Dosyası
cat << 'EOF' > "$HOME/tebligat.sh"
#!/bin/bash
# ⚖️ Avukat Bulut Otomasyonu - Hızlı Çalıştırıcı
cd /data/data/com.termux/files/home/avukatasistan
python3 asistan.py "$@"
EOF
chmod +x "$HOME/tebligat.sh"
echo "✅ ~/tebligat.sh oluşturuldu."

# 6. Global 'tebligat' Komutu Yapılandırması
mkdir -p "$HOME/.local/bin"
cat << 'EOF' > "$HOME/.local/bin/tebligat"
#!/bin/bash
exec /data/data/com.termux/files/home/tebligat.sh "$@"
EOF
chmod +x "$HOME/.local/bin/tebligat"

# 'asistan' komutu: python3 ~/avukatasistan/asistan.py ile aynı (her klasörden çalışır)
cat << 'EOF' > "$HOME/.local/bin/asistan"
#!/bin/bash
cd /data/data/com.termux/files/home/avukatasistan && exec python3 asistan.py "$@"
EOF
chmod +x "$HOME/.local/bin/asistan"

# PATH Ayarı (~/.bashrc)
if ! grep -q '\.local/bin' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "✅ ~/.bashrc içerisine PATH eklendi."
fi

echo ""
echo "=================================================="
echo "🎉 Kurulum Başarıyla Tamamlandı!"
echo "=================================================="
echo "Yeni bir Termux oturumu açın ya da 'source ~/.bashrc' yazın, sonra:"
echo "  asistan             -> komut listesi"
echo "  asistan calistir    -> bir kez: UETS indir + TickTick/Notion'a işle"
echo "  asistan izle        -> sürekli: 30 dk'da bir kontrol + düzenli denetim"
echo "  asistan durum       -> ayarlar tamam mı?"
echo "=================================================="
