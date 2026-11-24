#!/usr/bin/env bash
# ================================================================
#  UYAP Evrak Yöneticisi & Hukuk Asistanı (Linux / macOS Başlatıcı)
#  © 2026 Av. Can KIZILYAR — Tüm hakları saklıdır.
# ================================================================
cd "$(dirname "$0")"
exec python3 baslat.py "$@"
