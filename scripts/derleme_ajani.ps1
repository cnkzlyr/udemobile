# CanEditor Derleme Ajanı — "GitHub Actions" benzeri, ama derleme SİZİN bilgisayarınızda yapılır.
#
# Zamanlanmış görev olarak birkaç dakikada bir çalışır (kurulum: scripts\derleme_ajani_kur.ps1):
#   1. origin/derleme-istek dalındaki istek.json'a bakar. Yeni bir istek yoksa hemen çıkar.
#   2. Varsa: depoyu origin/main'e eşitler ve scripts\windows_yayin.ps1'i izin verilen seçeneklerle çalıştırır
#      (Windows + WSL'de Linux + Android derlemesi, gh ile GitHub Release'e yükleme).
#   3. Günlüğü ve özeti origin/derleme-sonuc dalına push'lar (sonuc/<kimlik>.log, sonuc/<kimlik>.json).
#
# Güvenlik: yalnızca depodaki sabit derleme betiği çalışır; istek dosyası komut taşıyamaz, yalnız sürüm
# numarası ve aşağıdaki izinli bayraklar okunur. İstek gönderebilmek için depoya push yetkisi gerekir.
param([string]$Depo = "$HOME\caneditor-derleme")
$ErrorActionPreference = "Continue"
$Durum = "$HOME\.caneditor-ajan"
New-Item -ItemType Directory -Force $Durum | Out-Null
$Kilit = "$Durum\calisiyor.kilit"
if ((Test-Path $Kilit) -and ((Get-Date) - (Get-Item $Kilit).LastWriteTime).TotalHours -lt 4) { exit 0 }   # önceki derleme sürüyor
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")

function Gunluk($m) { Add-Content "$Durum\ajan.log" ("{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $m) }

# 1. İstek var mı?
git -C $Depo fetch --quiet --depth 1 origin derleme-istek 2>$null
if ($LASTEXITCODE -ne 0) { exit 0 }
$ham = git -C $Depo show FETCH_HEAD:istek.json 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ham) { exit 0 }
try { $istek = ($ham -join "`n") | ConvertFrom-Json } catch { Gunluk "istek.json okunamadı"; exit 0 }
$kimlik = [string]$istek.kimlik
if ($kimlik -notmatch '^[A-Za-z0-9._-]{1,64}$') { Gunluk "geçersiz kimlik"; exit 0 }
$son = if (Test-Path "$Durum\son_istek.txt") { (Get-Content "$Durum\son_istek.txt" -Raw).Trim() } else { "" }
if ($kimlik -eq $son) { exit 0 }
Set-Content "$Durum\son_istek.txt" $kimlik   # aynı istek ikinci kez çalışmasın (hata olsa da)
Set-Content $Kilit $kimlik

# 2. Derleme (izin listesi)
$surum = [string]$istek.surum
if ($surum -notmatch '^\d+\.\d+\.\d+$') { $surum = "" }
$bayraklar = @()
foreach ($b in @($istek.secenekler)) { if (@("Yeniden", "LinuxYok", "AndroidYok") -contains [string]$b) { $bayraklar += "-$b" } }
$surumArg = if ($surum) { "-Surum $surum" } else { "" }
Gunluk "istek $kimlik başladı (sürüm '$surum', seçenekler: $($bayraklar -join ' '))"
$bas = Get-Date
git -C $Depo fetch --quiet --depth 1 origin main
git -C $Depo reset --quiet --hard origin/main
$log = "$Durum\derleme-$kimlik.log"
# Komut .cmd dosyasından çalıştırılır: Windows PowerShell 5.1 tırnaklı argümanları yerel programlara bozuk geçirir;
# cmd yönlendirmesi de yerel stderr'in hata kaydına çevrilmesinden etkilenmez.
$cmdDosyasi = "$Durum\derle.cmd"
$satir = "@powershell -NoProfile -ExecutionPolicy Bypass -File `"$Depo\scripts\windows_yayin.ps1`" $surumArg $($bayraklar -join ' ') > `"$log`" 2>&1"
[IO.File]::WriteAllText($cmdDosyasi, "@chcp 65001 >nul`r`n$satir`r`n@exit /b %ERRORLEVEL%`r`n", (New-Object Text.UTF8Encoding $false))
cmd /c "`"$cmdDosyasi`""
$kod = $LASTEXITCODE
$sure = [math]::Round(((Get-Date) - $bas).TotalMinutes, 1)
Gunluk "istek $kimlik bitti: kod $kod, $sure dk"

# 3. Sonucu derleme-sonuc dalına push'la
$sonucDepo = "$Durum\sonuc-depo"
if (-not (Test-Path "$sonucDepo\.git")) {
    $url = (git -C $Depo remote get-url origin)
    git clone --quiet --depth 1 --branch derleme-sonuc $url $sonucDepo 2>$null
    if ($LASTEXITCODE -ne 0) {
        New-Item -ItemType Directory -Force $sonucDepo | Out-Null
        git -C $sonucDepo init --quiet
        git -C $sonucDepo remote add origin $url
        git -C $sonucDepo checkout --quiet --orphan derleme-sonuc
    }
} else {
    git -C $sonucDepo fetch --quiet --depth 1 origin derleme-sonuc
    git -C $sonucDepo reset --quiet --hard FETCH_HEAD
}
New-Item -ItemType Directory -Force "$sonucDepo\sonuc" | Out-Null
$satirlar = Get-Content $log -Encoding UTF8 -ErrorAction SilentlyContinue
# Günlük büyükse yalnız son 3000 satır (PyInstaller çok ayrıntılı yazar)
$satirlar | Select-Object -Last 3000 | Set-Content "$sonucDepo\sonuc\$kimlik.log" -Encoding UTF8
$tamam = ($satirlar | Select-String -SimpleMatch "TAMAM: https://github.com" | Select-Object -Last 1)
$uyarilar = @($satirlar | Select-String -SimpleMatch "UYARI:" | ForEach-Object { $_.Line.Trim() } | Select-Object -Unique)
$ozet = [ordered]@{ kimlik = $kimlik; surum = $surum; kod = $kod; basarili = [bool]$tamam; sure_dk = $sure
    bitis = (Get-Date -Format s); bilgisayar = $env:COMPUTERNAME; uyarilar = $uyarilar
    surum_adresi = if ($tamam) { ($tamam.Line -replace '.*TAMAM:\s*', '').Trim() } else { "" } }
[IO.File]::WriteAllText("$sonucDepo\sonuc\$kimlik.json", ($ozet | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding $false))
git -C $sonucDepo add -A
git -C $sonucDepo -c user.name="CanEditor Derleme Ajanı" -c user.email="ajan@caneditor.local" commit --quiet -m "derleme $kimlik: kod $kod"
git -C $sonucDepo push --quiet origin HEAD:derleme-sonuc
Remove-Item $Kilit -ErrorAction SilentlyContinue
