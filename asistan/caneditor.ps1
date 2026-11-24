# caneditor - CanEditor terminal arayuzu (PowerShell). EN: CanEditor CLI launcher.
$bat = Join-Path $PSScriptRoot "caneditor.bat"
& $bat @args
exit $LASTEXITCODE
