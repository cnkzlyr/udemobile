# -*- coding: utf-8 -*-
"""Android'de (CANASISTAN_ANDROID=1) HER Python sürecinde — yalnız sunucuda değil, alt görevlerde de (UETS,
TickTick, Notion, Telegram, nöbetçi) — bağımsız DNS çözücüyü (dns_cozucu) etkinleştirir.
Eskiden yama yalnız sunucu.py içinde kuruluyordu; görevler ayrı süreç olduğundan telefonda
"internet yok / ad çözülemedi" hatası veriyordu. Masaüstünde hiçbir şey yapmaz."""
import os

if os.environ.get("CANASISTAN_ANDROID") == "1":
    try:
        import dns_cozucu

        dns_cozucu.yama_kur()
    except Exception:  # noqa: BLE001 — başlangıç asla bozulmasın
        pass
