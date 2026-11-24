<#
================================================================
 UYAP UDF E-İmza & Mobil İmza Evrensel İmzalatıcı (PowerShell)
 © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.
================================================================
#>
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
python "$ScriptDir\uyap_imzala.py" @args
