# CanEditor Derleme Ajanı kurulumu — bir kez çalıştırın (normal Terminal):
#   Set-ExecutionPolicy -Scope Process Bypass -Force; .\scripts\derleme_ajani_kur.ps1
# Windows "Görev Zamanlayıcı"ya oturum açıkken her 3 dakikada bir derleme_ajani.ps1'i çalıştıran bir görev ekler.
# Kaldırmak için:  Unregister-ScheduledTask -TaskName "CanEditor Derleme Ajani" -Confirm:$false
$Depo = Split-Path -Parent $PSScriptRoot
$Ajan = "$Depo\scripts\derleme_ajani.ps1"
if (-not (Test-Path $Ajan)) { throw "derleme_ajani.ps1 bulunamadı: $Ajan" }
# conhost --headless: görev her çalıştığında ekranda konsol penceresi yanıp sönmesin (Windows 11)
$eylem = New-ScheduledTaskAction -Execute "conhost.exe" -Argument "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Ajan`" -Depo `"$Depo`""
$tetik = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 3) -RepetitionDuration (New-TimeSpan -Days 3650)
$ayar = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4)
Register-ScheduledTask -TaskName "CanEditor Derleme Ajani" -Action $eylem -Trigger $tetik -Settings $ayar -Description "CanEditor: derleme-istek dalındaki isteği derleyip yayınlar" -Force | Out-Null
Write-Host "Kuruldu: 'CanEditor Derleme Ajani' her 3 dakikada bir istek kontrol eder (bilgisayar açık ve oturum açıkken)." -ForegroundColor Green
Write-Host "Günlük: $HOME\.caneditor-ajan\ajan.log"
Start-ScheduledTask -TaskName "CanEditor Derleme Ajani"   # ilk denetim hemen
