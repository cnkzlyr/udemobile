# CanEditor - TEK KOMUTLA tüm paketleri derle ve GitHub Release'e yükle (GitHub Actions gerekmez)
# Kullanım (Yönetici Terminal, depo kökünde):  .\scripts\windows_yayin.ps1
#
# Üretir:  Windows   CanEditor_<sürüm>_x64-setup.exe, CanEditor_<sürüm>_x64_en-US.msi
#          Linux     .deb, .rpm, .AppImage           (WSL Ubuntu içinde: scripts/linux_derle.sh)
#          Android   CanEditor-v<sürüm>.apk (+latest), UYAP-Editor-v<sürüm>.apk (+latest)
#          Web       CanEditor-Portable-Web-GUI-v<sürüm>.zip
# macOS paketi Apple donanımı/aracı olmadan üretilemez (Windows'ta mümkün değil).
#
# Betik yeniden çalıştırılabilir: kurulu araçları atlar; WSL ilk kez kurulursa bilgisayarı yeniden
# başlatmanızı ister, sonra aynı komutu tekrar çalıştırırsınız.
# Not: Windows PowerShell yerel komutların stderr çıktısını hata sanabildiği için ErrorActionPreference
#      'Continue' tutulur; her yerel komutun çıkış kodu Calistir ile ayrıca denetlenir.
param([string]$Surum = "4.0.1", [switch]$LinuxYok, [switch]$AndroidYok, [switch]$Yeniden)
# -Yeniden: daha önce derlenmiş paketler olsa da her şeyi baştan derler
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$Kok = Split-Path -Parent $PSScriptRoot
Set-Location $Kok
$Distro = "Ubuntu-24.04"
$Uyarilar = @()

function Adim($m) { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Uyar($m) { Write-Host "   UYARI: $m" -ForegroundColor Yellow; $script:Uyarilar += $m }
function YoluYenile {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:USERPROFILE\.cargo\bin"
    if ($env:JAVA_HOME) { $env:Path = "$env:JAVA_HOME\bin;$env:Path" }
}
function Calistir {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE -ne 0) { throw "Komut başarısız ($LASTEXITCODE): $($args -join ' ')" }
}
function Kur($Id, $Komut) {
    if (Get-Command $Komut -ErrorAction SilentlyContinue) { return }
    Write-Host "   kuruluyor: $Id"
    winget install --id $Id -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    YoluYenile
}

# ---------------------------------------------------------------------------------------------
Adim "1/7 WSL (Linux paketleri ve Android çalışma ortamları için)"
if (-not $LinuxYok) {
    wsl --status 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   WSL kuruluyor..."
        wsl --install --no-distribution
        Write-Host ""
        Write-Host "WSL kuruldu. BİLGİSAYARI YENİDEN BAŞLATIN, sonra aynı komutu tekrar çalıştırın:" -ForegroundColor Yellow
        Write-Host "   cd `"$Kok`"; .\scripts\windows_yayin.ps1" -ForegroundColor Yellow
        exit 0
    }
    $kurulu = (wsl -l -q 2>$null) -replace "`0", "" | Where-Object { $_.Trim() -eq $Distro }
    if (-not $kurulu) {
        Write-Host "   $Distro kuruluyor (kullanıcı adı sorulmaz; derleme root ile yapılır)..."
        wsl --install -d $Distro --no-launch
        $exe = Get-Command "ubuntu2404.exe" -ErrorAction SilentlyContinue
        if ($exe) { & $exe.Source install --root | Out-Null }
        else { wsl -d $Distro -u root -- true }
    }
    wsl -d $Distro -u root -- true
    if ($LASTEXITCODE -ne 0) { Uyar "WSL $Distro başlatılamadı: Linux paketleri ve Android çalışma ortamları atlanacak."; $LinuxYok = $true }
}

# ---------------------------------------------------------------------------------------------
Adim "2/7 Windows araçları (yalnızca eksik olanlar kurulur)"
Kur "Git.Git" "git"
Kur "OpenJS.NodeJS.LTS" "node"
Kur "GitHub.cli" "gh"
Kur "Rustlang.Rustup" "rustup"
python -c "import sys, tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {   # "python" Microsoft Store kısayolu olabilir
    Write-Host "   kuruluyor: Python.Python.3.12"
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
    YoluYenile
}
if (-not (Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-21*")) {
    Write-Host "   kuruluyor: EclipseAdoptium.Temurin.21.JDK"
    winget install --id EclipseAdoptium.Temurin.21.JDK -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
}
if (-not (Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-17*")) {
    Write-Host "   kuruluyor: EclipseAdoptium.Temurin.17.JDK (Android sınıfları için)"
    winget install --id EclipseAdoptium.Temurin.17.JDK -e --accept-source-agreements --accept-package-agreements --silent | Out-Null
}
if (-not (Test-Path "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC")) {
    Write-Host "   kuruluyor: Visual Studio C++ derleme araçları (Rust için gerekli, ~10 dk)"
    winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-source-agreements --accept-package-agreements --silent `
        --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" | Out-Null
}
$jdk = Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-21*" | Select-Object -First 1
if (-not $jdk) { throw "JDK 21 bulunamadı (Eclipse Adoptium)" }
$env:JAVA_HOME = $jdk.FullName
YoluYenile
Calistir rustup default stable

Adim "3/7 GitHub girişi (tarayıcı açılırsa onaylayın)"
gh auth status 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Calistir gh auth login --hostname github.com --git-protocol https --web }

# ---------------------------------------------------------------------------------------------
Adim "4/7 Linux paketleri + Android çalışma ortamları (WSL içinde, ~30-40 dk)"
$linuxDamga = "dist-linux\caneditor-commit.txt"
$linuxHazir = (Test-Path $linuxDamga) -and (((Get-Content $linuxDamga -Raw) -join "").Trim() -eq ((git rev-parse HEAD) -join "").Trim()) -and
    (Get-ChildItem "dist-linux\*${Surum}*" -ErrorAction SilentlyContinue).Count -ge 2 -and
    (Test-Path "build\eimza\jre-arm64.zip") -and (Test-Path "build\asistan-android\asistan-rt-arm64.zip") -and (Test-Path "build\uyapmobil\rt-arm64.zip")
if ($linuxHazir -and -not $Yeniden) { Write-Host "   Linux paketleri ve Android çalışma ortamları zaten hazır (yeniden derlemek için -Yeniden)." }
elseif (-not $LinuxYok) {
    $wk = ((wsl -d $Distro -u root -- wslpath -a ($Kok.Replace('\', '/'))) -join "").Trim()
    $androidBayrak = if ($AndroidYok) { "--android-yok" } else { "" }
    $bash = @"
set -e
export DEBIAN_FRONTEND=noninteractive
command -v rsync >/dev/null || (apt-get update -qq && apt-get install -y -qq rsync >/dev/null)
mkdir -p /root/caneditor
rsync -a --delete --exclude node_modules --exclude src-tauri/target --exclude build --exclude release --exclude dist-linux --exclude .git --exclude src-tauri/sidecar --exclude 'src-tauri/tarayici-*' --exclude 'src-tauri/eimza/jre*' '$wk/' /root/caneditor/
cd /root/caneditor
find . -name '*.sh' -exec sed -i 's/\r$//' {} +
hata=0
bash scripts/linux_derle.sh $androidBayrak || hata=`$?
# Yarıda kalsa bile hazırlanabilenler Windows tarafına taşınır
mkdir -p '$wk/dist-linux' '$wk/build'
cp -f dist-linux/* '$wk/dist-linux/' 2>/dev/null || true
for d in eimza asistan-android uyapmobil; do [ -d build/`$d ] && rm -rf '$wk/build/'`$d && cp -r build/`$d '$wk/build/'; done
exit `$hata
"@
    # Komutlar LF satır sonlu dosyaya yazılıp WSL'de çalıştırılır (wsl.exe çok satırlı argümanı bozabilir)
    New-Item -ItemType Directory -Force build | Out-Null
    [IO.File]::WriteAllText("$Kok\build\wsl_derle.sh", $bash.Replace("`r", ""), (New-Object Text.UTF8Encoding $false))
    wsl -d $Distro -u root -- bash "$wk/build/wsl_derle.sh"
    if ($LASTEXITCODE -eq 3) { Uyar "Linux paketleri hazır; Android çalışma ortamlarından biri hazırlanamadı (yukarıdaki UYARI satırlarına bakın)." }
    elseif ($LASTEXITCODE -ne 0) { Uyar "Linux derlemesi başarısız oldu (yukarıdaki hatalara bakın); Windows paketleriyle devam ediliyor." }
    if ($LASTEXITCODE -eq 0) { Set-Content -Path $linuxDamga -Value ((git rev-parse HEAD) -join "").Trim() -Encoding ASCII }
}

# ---------------------------------------------------------------------------------------------
Adim "5/7 Windows: gömülü Java + Hukuk Asistanı sunucusu + görünmez Chrome + kurulum dosyaları"
$winExe = "src-tauri\target\release\bundle\nsis\CanEditor_${Surum}_x64-setup.exe"
# Yalnızca AYNI kaynak koddan (aynı commit) derlenmişse atlanır: eski kodla paket yayınlanmasın
$Commit = ((git rev-parse HEAD) -join "").Trim()
$winDamga = "src-tauri\target\release\bundle\caneditor-commit.txt"
$winGuncel = (Test-Path $winExe) -and (Test-Path $winDamga) -and (((Get-Content $winDamga -Raw) -join "").Trim() -eq $Commit)
if ($winGuncel -and -not $Yeniden) {
    Write-Host "   Windows kurulum dosyaları zaten derlenmiş (yeniden derlemek için -Yeniden)."
} else {
Calistir python -m pip install --upgrade pip
Calistir python -m pip install -r asistan/requirements.txt pyinstaller
Calistir python scripts/masaustu_hazirla.py --java-home $env:JAVA_HOME
Calistir python scripts/win_ajan_derle.py
# npm.ps1 kabuğu Windows PowerShell 5.1'de "Dizin, dizi sınırlarının dışındaydı" hatası verir: .cmd kullanılır
Calistir npm.cmd install
Push-Location frontend
Calistir npm.cmd install
Calistir npm.cmd run build
Pop-Location
npx.cmd tauri build
if ($LASTEXITCODE -ne 0) {
    # Windows 11 24H2'de VBScript kapalıysa MSI (WiX) derlenemez: yalnız .exe kurulumuyla devam
    Uyar "MSI derlenemedi (VBScript kapalı olabilir); yalnız .exe kurulum dosyası yayınlanacak."
    Calistir npx.cmd tauri build --bundles nsis
}
if (Test-Path $winExe) { Set-Content -Path $winDamga -Value $Commit -Encoding ASCII }
}

# ---------------------------------------------------------------------------------------------
Adim "6/7 Android APK + taşınabilir web zip"
New-Item -ItemType Directory -Force release | Out-Null   # seyrek klonda release/ indirilmez
if (-not $AndroidYok) {
    $sdk = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { "$env:LOCALAPPDATA\Android\Sdk" }
    if (-not (Get-ChildItem "$sdk\build-tools" -Directory -ErrorAction SilentlyContinue)) {
        Write-Host "   Android SDK komut satırı araçları kuruluyor (dl.google.com)..."
        New-Item -ItemType Directory -Force "$sdk\cmdline-tools" | Out-Null
        $zip = "$env:TEMP\android-cmdline-tools.zip"
        Invoke-WebRequest "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" -OutFile $zip
        Remove-Item -Recurse -Force "$sdk\cmdline-tools\latest", "$sdk\cmdline-tools\cmdline-tools" -ErrorAction SilentlyContinue
        Expand-Archive $zip "$sdk\cmdline-tools" -Force
        Rename-Item "$sdk\cmdline-tools\cmdline-tools" "latest"
        $sm = "$sdk\cmdline-tools\latest\bin\sdkmanager.bat"
        ("y`n" * 40) | & $sm --sdk_root="$sdk" --licenses | Out-Null
        & $sm --sdk_root="$sdk" "build-tools;35.0.0" "platforms;android-34" | Out-Null
    }
    $env:ANDROID_HOME = $sdk
    # JDK 21 javac'ı eski D8'i çökertir (isimsiz MethodParameters): Android sınıfları JDK 17 ile derlenir
    $jdk17 = Get-ChildItem "$env:ProgramFiles\Eclipse Adoptium" -Directory -ErrorAction SilentlyContinue | Where-Object Name -like "jdk-17*" | Select-Object -First 1
    if ($jdk17) { $env:CANEDITOR_ANDROID_JDK = $jdk17.FullName } else { Uyar "JDK 17 bulunamadı; APK derlemesi D8 hatası verebilir." }
    # Önceki APK'ları imzalayan anahtar: bu kullanıcı, depo kökü ya da bilgisayardaki diğer kullanıcı klasörleri
    $ks = @("$env:USERPROFILE\.android-sdk\debug.keystore", "$Kok\debug.keystore") +
          @(Get-ChildItem "$env:SystemDrive\Users\*\.android-sdk\debug.keystore" -ErrorAction SilentlyContinue | ForEach-Object FullName) |
          Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    if ($ks) {
        $env:ANDROID_KEYSTORE = $ks
        Write-Host "   imza anahtarı: $ks"
    } else {
        Uyar "Önceki APK'ları imzalayan anahtar (debug.keystore) bulunamadı: APK YENİ anahtarla imzalanacak; telefonda eski sürümü kaldırıp kurmak gerekir. Anahtarınızı %USERPROFILE%\.android-sdk\debug.keystore konumuna kopyalayıp betiği yeniden çalıştırabilirsiniz."
    }
    if (-not (Test-Path "build\asistan-android\asistan-rt-arm64.zip")) {
        $env:CANEDITOR_ASISTAN_ANDROID = "0"
        Uyar "Android asistan çalışma ortamı yok (WSL adımı çalışmadı): APK'da asistan sunucusu olmayacak."
    }
}
python scripts/pack_release.py
if ($LASTEXITCODE -ne 0) { Uyar "pack_release.py hata kodu döndü ($LASTEXITCODE); üretilebilen dosyalar yine de yüklenecek." }
# Yeni oluşturulan imza anahtarını kalıcı yere yedekle: sonraki APK'lar aynı anahtarla imzalanır (güncelleme olarak kurulur)
$kalici = "$env:USERPROFILE\.android-sdk\debug.keystore"
if ((Test-Path "$Kok\debug.keystore") -and -not (Test-Path $kalici)) {
    New-Item -ItemType Directory -Force (Split-Path $kalici) | Out-Null
    Copy-Item "$Kok\debug.keystore" $kalici
    Write-Host "   imza anahtarı yedeklendi: $kalici (bunu kaybetmeyin)"
}

# ---------------------------------------------------------------------------------------------
Adim "7/7 GitHub Release v$Surum"
$dosyalar = @()
$dosyalar += Get-ChildItem "src-tauri\target\release\bundle\nsis\*_${Surum}_*setup.exe" -ErrorAction SilentlyContinue
$dosyalar += Get-ChildItem "src-tauri\target\release\bundle\msi\*_${Surum}_*.msi" -ErrorAction SilentlyContinue
$dosyalar += Get-ChildItem "dist-linux\*${Surum}*" -ErrorAction SilentlyContinue
foreach ($ad in @("CanEditor-Portable-Web-GUI-v$Surum.zip", "CanEditor-v$Surum.apk", "UYAP-Editor-v$Surum.apk")) {
    if (Test-Path "release\$ad") { $dosyalar += Get-Item "release\$ad" }
}
foreach ($cift in @(@("CanEditor-v$Surum.apk", "CanEditor-latest.apk"), @("UYAP-Editor-v$Surum.apk", "UYAP-Editor-latest.apk"))) {
    if (Test-Path "release\$($cift[0])") {
        Copy-Item "release\$($cift[0])" "$env:TEMP\$($cift[1])" -Force
        $dosyalar += Get-Item "$env:TEMP\$($cift[1])"
    }
}
if (-not ($dosyalar | Where-Object Name -like "*.exe")) { throw "Windows kurulum dosyası üretilmedi" }
Write-Host "   Yüklenecek dosyalar:"
$dosyalar | ForEach-Object { Write-Host ("     " + $_.Name + "  (" + [math]::Round($_.Length / 1MB) + " MB)") }
$notlar = @"
CanEditor v$Surum — Editör + Hukuk Asistanı tek uygulamada.

Kurulum paketleri her şeyi içinde taşır: Python, Java, görünmez Chrome ve sürücüsüz e-imza altyapısı.
- Yasal süre hesabı, A4 PDF birleştirici, ajanda, UYAP evrak arama, UETS/UYAP görevleri (Asistan menüsü, Ctrl+K)
- UYAP oturumu: e-imza kartı takılıysa e-imza; değilse ya da bağlantı koparsa bağlanana kadar Mobil İmza
- Android: asistan Termux gerektirmez

Windows: CanEditor_${Surum}_x64-setup.exe veya .msi (SmartScreen uyarısında: Ek bilgi, ardından Yine de çalıştır)
Linux: sudo apt install ./CanEditor_${Surum}_amd64.deb  ·  sudo dnf install ./CanEditor-${Surum}-1.x86_64.rpm  ·  AppImage: chmod +x
Android: CanEditor-v$Surum.apk (Bilinmeyen kaynaklar iznini verin)
macOS: bu sürümde paket yok (Apple donanımında derlenmesi gerekir).
"@
# Notlar dosyayla verilir: Windows PowerShell 5.1 tırnaklı argümanları yerel programlara bozuk geçirir
$notDosyasi = "$env:TEMP\caneditor-surum-notlari.md"
[IO.File]::WriteAllText($notDosyasi, $notlar, (New-Object Text.UTF8Encoding $false))
$yollar = [string[]]($dosyalar | ForEach-Object { $_.FullName })
gh release view "v$Surum" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    gh release upload "v$Surum" $yollar --clobber
} else {
    gh release create "v$Surum" $yollar --target main --title "CanEditor v$Surum" --notes-file $notDosyasi
}
if ($LASTEXITCODE -ne 0) { throw "GitHub Release oluşturulamadı / dosyalar yüklenemedi" }
Write-Host ""
if ($Uyarilar.Count) { Write-Host "Uyarılar:" -ForegroundColor Yellow; $Uyarilar | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow } }
Write-Host "TAMAM: https://github.com/cnkzlyr/udemobile/releases/tag/v$Surum" -ForegroundColor Green
