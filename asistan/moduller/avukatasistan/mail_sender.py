#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TickTick E-posta ile Görev ve Ek (Attachment) Gönderici Modülü
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from config import CONFIG

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_USER = CONFIG.get("GMAIL_USER") or ""
SMTP_PASS = (CONFIG.get("GMAIL_APP_PASS") or "").replace(" ", "").strip()
TICKTICK_EMAIL = CONFIG.get("TICKTICK_EMAIL") or ""

def send_task_via_email(subject, body, attachment_paths=None):
    """
    TickTick'e e-posta yoluyla görev ve orijinal dosya ekleri (PDF, UDF vb.) gönderir.
    """
    if not (SMTP_USER and SMTP_PASS and TICKTICK_EMAIL):
        print("⚠️ E-posta ile görev gönderilemedi: .env içinde GMAIL_USER, GMAIL_APP_PASS ve TICKTICK_EMAIL olmalı.")
        return False
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = TICKTICK_EMAIL
    msg["Subject"] = subject
    
    # Gövde metni
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    # Dosya ekleri
    attached_count = 0
    if attachment_paths:
        for fpath in attachment_paths:
            if not fpath or not os.path.exists(fpath):
                continue
            fname = os.path.basename(fpath)
            try:
                with open(fpath, "rb") as f:
                    part = MIMEApplication(f.read(), Name=fname)
                # Türkçe karakterli dosya adları RFC 2231 ile kodlanır (aksi halde ek adı bozuluyordu)
                part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", fname))
                msg.attach(part)
                attached_count += 1
            except Exception as e:
                print(f"⚠️ Dosya eklenemedi ({fname}): {e}")
                
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, TICKTICK_EMAIL, msg.as_string())
        print(f"   ✉️ TickTick'e E-posta Gönderildi: {subject} ({attached_count} dosya eklendi)")
        return True
    except Exception as e:
        print(f"⚠️ SMTP E-posta gönderim hatası: {e}")
        return False
