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

    def upload_file(self, local_path: Path | str, remote_folder_path: str = "") -> dict:
        """Dosyayı doğrudan Google Drive'daki ilgili klasör yoluna yükler."""
        p = Path(local_path)
        if not p.exists() or p.stat().st_size == 0:
            return {"status": "error", "message": "Dosya bulunamadı veya boş"}

        # 1. Öncelik: Eğer bilgisayarda yerel Google Drive sürücüsü bağlıysa (G:\Drive'ım)
        if self.local_drive_dir and self.local_drive_dir.exists():
            try:
                target = self.local_drive_dir / remote_folder_path / p.name
                target.parent.mkdir(parents=True, exist_ok=True)
                import shutil
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
                    "content": content_b64
                }
                resp = requests.post(self.webhook_url, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info("[Drive Cloud] Dosya doğrudan Google Drive'a yüklendi: %s", p.name)
                    return data
                else:
                    logger.error("[Drive Cloud] Yükleme hatası (%d): %s", resp.status_code, resp.text)
            except Exception as e:
                logger.error("[Drive Cloud] Bağlantı hatası: %s", e)

        return {"status": "skipped", "message": "Drive hedefi yapılandırılmamış"}


GOOGLE_APPS_SCRIPT_TEMPLATE = """
// ===========================================================================
// UYAP Google Drive Webhook Betiği (script.google.com)
// Bu kodu Google Drive'ınızda "Yeni > Diğer > Google Apps Script" açıp yapıştırın.
// Ardından "Dağıt (Deploy) > Yeni Dağıtım > Web Uygulaması" seçip URL'yi alın.
// ===========================================================================
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var rootFolderName = "UYAP_Arsiv";
    var rootFolders = DriveApp.getFoldersByName(rootFolderName);
    var root = rootFolders.hasNext() ? rootFolders.next() : DriveApp.createFolder(rootFolderName);
    
    // Klasör hiyerarşisini bul veya oluştur
    var folder = root;
    if (data.folder_path) {
      var parts = data.folder_path.replace(/\\\\/g, "/").split("/");
      for (var i = 0; i < parts.length; i++) {
        var part = parts[i].trim();
        if (!part) continue;
        var sub = folder.getFoldersByName(part);
        folder = sub.hasNext() ? sub.next() : folder.createFolder(part);
      }
    }
    
    // Dosyayı oluştur
    var decoded = Utilities.base64Decode(data.content);
    var blob = Utilities.newBlob(decoded, "application/pdf", data.filename);
    var file = folder.createFile(blob);
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      filename: data.filename,
      fileId: file.getId(),
      url: file.getUrl()
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
"""
