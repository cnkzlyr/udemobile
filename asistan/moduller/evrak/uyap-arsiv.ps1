<#
================================================================
 UYAP Dosya Arşivleyici & Drive Senkronizasyonu (PowerShell)
 © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.
================================================================
#>
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
python "$ScriptDir\dosya_arsivle.py" @args
