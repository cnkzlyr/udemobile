#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır. / All rights reserved.
r"""
UYAP Doğrudan Google Drive Bulut Entegratörü
===========================================
Bilgisayarınız kapalıyken bile telefonunuzdan (Android / Termux), laptopunuzdan
veya herhangi bir cihazdan indirilen evrakları doğrudan Google Drive'a yükler.

Özellikler:
  1. Aracısız Yükleme: Telefondan indirilen dosya doğrudan Google Drive API veya
     Google Apps Script Webhook üzerinden buluta aktarılır.
  2. Otomatik Klasör Oluşturma: Drive içinde 'UYAP_Arsiv/DAVA_EVRAKLARI/...'
     klasör yapısını bulutta kendisi hiyerarşik olarak açar.
  3. Yerel & Bulut Hibrit Desteği: Bilgisayardayken G:\ sürücüsünü, telefondayken
     doğrudan internet üzerinden Drive API'sini kullanır.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("uyap.gdrive")


class GoogleDriveCloudClient:
    """Doğrudan Google Drive bulut yükleyicisi."""

    def __init__(self, webhook_url: str = "", local_drive_dir: str = ""):
        self.webhook_url = webhook_url.strip()
        self.local_drive_dir = Path(local_drive_dir) if local_drive_dir else None

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url or (self.local_drive_dir and self.local_drive_dir.exists()))

    @staticmethod
    def temiz_yol(remote_folder_path: str) -> str:
        """Yolun başındaki "UYAP_Arsiv" parçalarını atar. v4.10.2: bazı modüller yolu "UYAP_Arsiv/..." diye
        veriyordu; betik bunu kökün ALTINA ikinci bir UYAP_Arsiv olarak açıyor, iç içe klasörler ve çift kopyalar
        oluşuyordu. EN: strip leading root segments so nested UYAP_Arsiv folders are never created."""
        parca = [x.strip() for x in str(remote_folder_path or "").replace("\\", "/").split("/") if x.strip()]
        while parca and parca[0] == "UYAP_Arsiv":
            parca.pop(0)
        return "/".join(parca)

    def _post(self, govde: dict, timeout: int = 90) -> dict:
        import requests
        r = requests.post(self.webhook_url, json=govde, timeout=timeout)
        try:
            return r.json()
        except ValueError:
            return {"status": "error", "message": f"Apps Script JSON döndürmedi (HTTP {r.status_code})"}

    def betik_surumu(self) -> int:
        """Webhook betiğinin sürümü (0 = eski/ulaşılamıyor). v3 ve üstü üzerine yazma + sabit kök destekler."""
        if not self.webhook_url:
            return 0
        try:
            return int(self._post({"action": "ping"}, timeout=30).get("surum") or 1)
        except Exception:  # noqa: BLE001
            return 0

    def ic_ice_duzelt(self, azami_tur: int = 40) -> dict:
        """Drive'daki iç içe UYAP_Arsiv/UYAP_Arsiv/... klasörlerini köke birleştirir (betik v3)."""
        toplam = {"tasinan": 0, "kopya_cope": 0, "birlesen_klasor": 0, "bitti": False}
        for _ in range(azami_tur):
            r = self._post({"action": "ic_ice_duzelt"}, timeout=120)
            if r.get("status") != "ok":
                toplam["hata"] = r.get("message") or str(r)
                break
            for k in ("tasinan", "kopya_cope", "birlesen_klasor"):
                toplam[k] += int(r.get(k) or 0)
            if r.get("bitti"):
                toplam["bitti"] = True
                break
        return toplam

    def upload_file(self, local_path: Path | str, remote_folder_path: str = "", uzerine_yaz: bool = False) -> dict:
        """Dosyayı Google Drive'daki ilgili klasör yoluna yükler.
        uzerine_yaz=True: aynı klasördeki aynı adlı dosya(lar) çöpe taşınıp yenisi yazılır (onarılan PDF eskisinin
        YERİNE geçer; betik v3 gerekir). EN: upload; with uzerine_yaz the same-name file is replaced."""
        p = Path(local_path)
        if not p.exists() or p.stat().st_size == 0:
            return {"status": "error", "message": "Dosya bulunamadı veya boş"}
        remote_folder_path = self.temiz_yol(remote_folder_path)

        # 1. Öncelik: Eğer bilgisayarda yerel Google Drive sürücüsü bağlıysa (G:\Drive'ım)
        if self.local_drive_dir and self.local_drive_dir.exists():
            try:
                # Seçilen Drive klasörü kök sayılır (davranış değişmez); yalnız baştaki UYAP_Arsiv tekrarları atıldı
                target = self.local_drive_dir / remote_folder_path / p.name
                target.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                if target.exists() and not uzerine_yaz and target.stat().st_size == p.stat().st_size:
                    return {"status": "success", "mode": "local_drive", "path": str(target), "mevcut": True}
                shutil.copy2(p, target)
                logger.info("[Drive] Yerel Drive sürücüsüne kopyalandı: %s", target.name)
                return {"status": "success", "mode": "local_drive", "path": str(target)}
            except Exception as e:
                logger.warning("[Drive] Yerel sürücüye yazılamadı, bulut API denenecek: %s", e)

        # 2. Öncelik: Telefondan / dışarıdan doğrudan Google Cloud Webhook üzerinden yükleme
        if self.webhook_url:
            try:
                import requests
                content_b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
                payload = {
                    "filename": p.name,
                    "folder_path": remote_folder_path.replace("\\", "/"),
                    "content": content_b64,
                    "uzerine_yaz": bool(uzerine_yaz),
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=60)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        data = {"status": "error", "message": "Apps Script JSON döndürmedi (erişim 'Herkes' mi?)"}
                    if data.get("status") == "success":
                        logger.info("[Drive Cloud] %s: %s", "Zaten Drive'da" if data.get("mevcut") else "Drive'a yüklendi", p.name)
                    else:
                        logger.error("[Drive Cloud] Apps Script hatası: %s", data.get("message") or data)
                    return data
                else:
                    logger.error("[Drive Cloud] Yükleme hatası (%d): %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("[Drive Cloud] Bağlantı hatası: %s", e)

        return {"status": "skipped", "message": "Drive hedefi yapılandırılmamış"}


def _betik_oku() -> str:
    """Apps Script betiğinin tek kaynağı: asistan/drive_webhook.gs (arayüzdeki şablonla aynı, sürüm 3)."""
    for p in (Path(__file__).resolve().parents[2] / "drive_webhook.gs", Path(__file__).resolve().parent / "drive_webhook.gs"):
        if p.is_file():
            return p.read_text(encoding="utf-8")
    return "// drive_webhook.gs bulunamadı"


GOOGLE_APPS_SCRIPT_TEMPLATE = _betik_oku()
