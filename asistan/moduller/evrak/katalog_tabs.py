# -*- coding: utf-8 -*-
"""
UYAP Evrak Kataloğu Gelişmiş GUI Sekmeleri (Tabs)
(c) 2026 Av. Can KIZILYAR - Tüm hakları saklıdır.

Bu modül:
1. Dava Finans & Safahat Sekmesi (Harçlar, Masraflar, Kalan Gider Avansı, Safahat Zaman Çizelgesi)
2. İcra Dosya Hesabı Sekmesi (Kapak Hesabı: Asıl Alacak, Faiz, Masraf, Tahsil Harcı, Kalan Borç, Borçlular)
3. Süreler & Görevler Sekmesi (Yasal süreler, duruşma ara kararları, kesin süre geri sayımı)
4. Portal İşlemlerim Sekmesi (UYAP Portal işlem ve talep akışı)
5. Gemini AI Analiz Sekmesi (gemini-2.5-flash ile dosya özetleri ve zapt analizi, önbellek korumalı)
6. Notion & TickTick Entegrasyon Sekmesi (Dışa aktarma ve senkronizasyon kontrolleri)
"""

import os
import sys
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date
from pathlib import Path

import gui_ekler as ge
from uyap_finans_safahat import UyapFinansSafahatManager, get_db_connection
from uyap_sure_analiz import UyapSureAnalizManager
from uyap_ai import UyapGeminiClient
from uyap_entegrasyon import export_all_integrations


class KatalogTabsManager:
    """Katalog GUI sekmelerini oluşturan ve yöneten sınıf."""

    def __init__(self, app, notebook: ttk.Notebook):
        self.app = app
        self.notebook = notebook
        self.finans_mgr = UyapFinansSafahatManager(bridge=app.bridge)
        self.sure_mgr = UyapSureAnalizManager()
        self.ai_client = UyapGeminiClient()

        # Sekmeleri kur
        self.tab_finans = ttk.Frame(notebook, padding=6)
        self.tab_icra = ttk.Frame(notebook, padding=6)
        self.tab_sure = ttk.Frame(notebook, padding=6)
        self.tab_islem = ttk.Frame(notebook, padding=6)
        self.tab_ai = ttk.Frame(notebook, padding=6)
        self.tab_ent = ttk.Frame(notebook, padding=6)

        notebook.add(self.tab_finans, text="⚖️ Finans & Safahat")
        notebook.add(self.tab_icra, text="📊 İcra Kapak Hesabı")
        notebook.add(self.tab_sure, text="⏳ Süreler & Görevler")
        notebook.add(self.tab_islem, text="⚡ İşlemlerim")
        notebook.add(self.tab_ai, text="🤖 Gemini AI Analiz")
        notebook.add(self.tab_ent, text="🔗 Notion & TickTick")

        self._build_finans_tab()
        self._build_icra_tab()
        self._build_sure_tab()
        self._build_islem_tab()
        self._build_ai_tab()
        self._build_ent_tab()

    # -------------------------------------------------------------------------
    # 1. DAVA FİNANS & SAFAHAT SEKMESİ
    # -------------------------------------------------------------------------
    def _build_finans_tab(self):
        f = self.tab_finans

        # Üst Araç Çubuğu
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        ttk.Label(top, text="Dosya Seç:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.cb_finans_dosya = ttk.Combobox(top, width=45, state="readonly")
        self.cb_finans_dosya.pack(side="left", padx=(0, 8))
        self.cb_finans_dosya.bind("<<ComboboxSelected>>", lambda e: self.load_finans_for_selected())

        btn_fetch = ttk.Button(top, text="🔄 UYAP'tan Bilgileri Çek", command=self.on_fetch_finans_live, style="Vurgu.TButton")
        btn_fetch.pack(side="left", padx=2)
        ge.Ipucu(btn_fetch, "Seçili dosyanın UYAP'taki güncel harç, masraf, tahsilat ve safahat kayıtlarını canlı sorgular.")

        btn_refresh = ttk.Button(top, text="⚡ Listeyi Yenile", command=self.refresh_finans_combo)
        btn_refresh.pack(side="left", padx=2)

        # Kartlar Şeridi
        cards = ttk.Frame(f)
        cards.pack(fill="x", pady=(0, 6))

        def make_card(parent, title, val_lbl_attr, bg_col, fg_col):
            cf = tk.Frame(parent, bg=bg_col, padx=12, pady=6, highlightbackground="#cbd5e1", highlightthickness=1)
            cf.pack(side="left", fill="x", expand=True, padx=3)
            tk.Label(cf, text=title, bg=bg_col, fg="#475569", font=("Segoe UI", 8)).pack(anchor="w")
            lbl = tk.Label(cf, text="0.00 TL", bg=bg_col, fg=fg_col, font=("Segoe UI", 12, "bold"))
            lbl.pack(anchor="w")
            setattr(self, val_lbl_attr, lbl)

        make_card(cards, "Yatırılan Toplam", "lbl_fin_tahsilat", "#f8fafc", "#0f172a")
        make_card(cards, "Harcanan Masraf / Reddiyat", "lbl_fin_reddiyat", "#fef2f2", "#b91c1c")
        make_card(cards, "Toplam Harç Tutarı", "lbl_fin_harc", "#f0fdf4", "#15803d")
        make_card(cards, "Kalan Gider Avansı Bakiyesi", "lbl_fin_bakiye", "#e0f2fe", "#0369a1")

        # Orta Bölünmüş Alan: Sol (Harç/Masraf) | Sağ (Safahat)
        split = ttk.PanedWindow(f, orient="horizontal")
        split.pack(fill="both", expand=True)

        # Sol: Harç ve Masraf Dökümü
        lf_hm = ttk.LabelFrame(split, text="💰 Harç ve Masraf Hareketleri", padding=4)
        split.add(lf_hm, weight=1)

        cols_hm = ("tarih", "tur", "miktar", "odeyen")
        self.tree_hm = ttk.Treeview(lf_hm, columns=cols_hm, show="headings")
        self.tree_hm.heading("tarih", text="Tarih")
        self.tree_hm.heading("tur", text="İşlem / Masraf Türü")
        self.tree_hm.heading("miktar", text="Tutar (TL)")
        self.tree_hm.heading("odeyen", text="Ödeyen / Açıklama")
        self.tree_hm.column("tarih", width=80)
        self.tree_hm.column("tur", width=140)
        self.tree_hm.column("miktar", width=85, anchor="e")
        self.tree_hm.column("odeyen", width=160)

        sb_hm = ttk.Scrollbar(lf_hm, orient="vertical", command=self.tree_hm.yview)
        self.tree_hm.configure(yscrollcommand=sb_hm.set)
        self.tree_hm.pack(side="left", fill="both", expand=True)
        sb_hm.pack(side="right", fill="y")

        # Sağ: Safahat Geçmişi
        lf_saf = ttk.LabelFrame(split, text="📜 Safahat Geçmişi (Dava Aşamaları)", padding=4)
        split.add(lf_saf, weight=1)

        cols_s = ("tarih", "birim", "tur", "aciklama")
        self.tree_saf = ttk.Treeview(lf_saf, columns=cols_s, show="headings")
        self.tree_saf.heading("tarih", text="Tarih")
        self.tree_saf.heading("birim", text="İşlem Birimi")
        self.tree_saf.heading("tur", text="Safahat Türü")
        self.tree_saf.heading("aciklama", text="Açıklama")
        self.tree_saf.column("tarih", width=85)
        self.tree_saf.column("birim", width=140)
        self.tree_saf.column("tur", width=130)
        self.tree_saf.column("aciklama", width=200)

        sb_s = ttk.Scrollbar(lf_saf, orient="vertical", command=self.tree_saf.yview)
        self.tree_saf.configure(yscrollcommand=sb_s.set)
        self.tree_saf.pack(side="left", fill="both", expand=True)
        sb_s.pack(side="right", fill="y")

    def refresh_finans_combo(self):
        """Dava dosyalarını combobox'a doldurur."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT dkey, birim, dosya_no, dosya_id FROM dosya WHERE durum LIKE '%Açık%' ORDER BY birim ASC")
        rows = cur.fetchall()
        conn.close()

        self._finans_dosyalar = {f"{r['birim']} - {r['dosya_no']}": (r['dkey'], r['dosya_id'], r['birim'], r['dosya_no']) for r in rows}
        vals = list(self._finans_dosyalar.keys())
        self.cb_finans_dosya["values"] = vals
        if vals and not self.cb_finans_dosya.get():
            self.cb_finans_dosya.set(vals[0])
            self.load_finans_for_selected()

    def load_finans_for_selected(self):
        """Seçili dosyanın veritabanındaki finans ve safahat kayıtlarını gösterir."""
        secilen = self.cb_finans_dosya.get()
        if not secilen or secilen not in getattr(self, "_finans_dosyalar", {}):
            return
        dkey, dosya_id, birim, dosya_no = self._finans_dosyalar[secilen]

        conn = get_db_connection()
        cur = conn.cursor()

        # Finans
        cur.execute("SELECT toplam_tahsilat, toplam_reddiyat, toplam_harc, kalan_bakiye, tahsilat_list_json, reddiyat_list_json, harc_list_json FROM dosya_finans WHERE dkey = ?", (dkey,))
        fin = cur.fetchone()

        if fin:
            self.lbl_fin_tahsilat.config(text=f"{fin['toplam_tahsilat']:,.2f} TL")
            self.lbl_fin_reddiyat.config(text=f"{fin['toplam_reddiyat']:,.2f} TL")
            self.lbl_fin_harc.config(text=f"{fin['toplam_harc']:,.2f} TL")
            self.lbl_fin_bakiye.config(text=f"{fin['kalan_bakiye']:,.2f} TL")

            # Tabloyu temizle ve doldur
            for item in self.tree_hm.get_children():
                self.tree_hm.delete(item)

            harclar = json.loads(fin["harc_list_json"] or "[]")
            for h in harclar:
                self.tree_hm.insert("", "end", values=(
                    h.get("tahsilatTarihi", "")[:10],
                    h.get("tahsilatTuru", "Harç"),
                    f"{float(h.get('miktar', 0)):,.2f}",
                    h.get("odeyenKisi", "")
                ))
            tahsilatlar = json.loads(fin["tahsilat_list_json"] or "[]")
            for t in tahsilatlar:
                self.tree_hm.insert("", "end", values=(
                    t.get("tahsilatTarihi", "")[:10],
                    t.get("tahsilatTuru", "Masraf Avansı"),
                    f"{float(t.get('tahsilatTutari', 0)):,.2f}",
                    t.get("odeyenKisi", "")
                ))
        else:
            self.lbl_fin_tahsilat.config(text="0.00 TL")
            self.lbl_fin_reddiyat.config(text="0.00 TL")
            self.lbl_fin_harc.config(text="0.00 TL")
            self.lbl_fin_bakiye.config(text="0.00 TL")
            for item in self.tree_hm.get_children():
                self.tree_hm.delete(item)

        # Safahat
        cur.execute("SELECT safahat_tarihi_str, islem_yapan_birim, safahat_turu, aciklama FROM dosya_safahat WHERE dkey = ? ORDER BY safahat_tarihi DESC", (dkey,))
        safs = cur.fetchall()
        for item in self.tree_saf.get_children():
            self.tree_saf.delete(item)
        for s in safs:
            self.tree_saf.insert("", "end", values=(s[0], s[1], s[2], s[3]))

        conn.close()

    def on_fetch_finans_live(self):
        """Seçili dosya için UYAP'tan canlı sorgu atar."""
        secilen = self.cb_finans_dosya.get()
        if not secilen or secilen not in getattr(self, "_finans_dosyalar", {}):
            messagebox.showinfo("Bilgi", "Lütfen önce listeden bir dosya seçin.")
            return
        dkey, dosya_id, birim, dosya_no = self._finans_dosyalar[secilen]

        if not dosya_id:
            messagebox.showwarning("Hata", "Dosya ID bulunamadı.")
            return

        ge.bildirim(self.app.root, f"UYAP'tan çekiliyor: {dosya_no}...", renk="#1e3a5f")
        try:
            self.finans_mgr.bridge = self.app.bridge
            self.finans_mgr.fetch_finans(dosya_id, dkey, birim, dosya_no)
            self.finans_mgr.fetch_safahat(dosya_id, dkey, birim, dosya_no)
            self.load_finans_for_selected()
            ge.bildirim(self.app.root, "Finans ve safahat bilgileri başarıyla güncellendi!", renk="#15803d")
        except Exception as e:
            messagebox.showerror("Hata", f"UYAP sorgu hatası: {e}")

    # -------------------------------------------------------------------------
    # 2. İCRA DOSYA HESABI SEKMESİ
    # -------------------------------------------------------------------------
    def _build_icra_tab(self):
        f = self.tab_icra

        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        ttk.Label(top, text="İcra Dosyası:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 4))
        self.cb_icra_dosya = ttk.Combobox(top, width=45, state="readonly")
        self.cb_icra_dosya.pack(side="left", padx=(0, 8))
        self.cb_icra_dosya.bind("<<ComboboxSelected>>", lambda e: self.load_icra_for_selected())

        btn_fetch = ttk.Button(top, text="🔄 UYAP'tan Kapak Hesabı Çek", command=self.on_fetch_icra_live, style="Vurgu.TButton")
        btn_fetch.pack(side="left", padx=2)
        ge.Ipucu(btn_fetch, "Dosya kapak hesabı, borçlular ve güvenli/ücretsiz sorgu durumunu UYAP'tan çeker.")

        btn_refresh = ttk.Button(top, text="⚡ Listeyi Yenile", command=self.refresh_icra_combo)
        btn_refresh.pack(side="left", padx=2)

        # Kartlar
        cards = ttk.Frame(f)
        cards.pack(fill="x", pady=(0, 6))

        def make_icra_card(parent, title, attr, bg_col, fg_col):
            cf = tk.Frame(parent, bg=bg_col, padx=10, pady=6, highlightbackground="#cbd5e1", highlightthickness=1)
            cf.pack(side="left", fill="x", expand=True, padx=2)
            tk.Label(cf, text=title, bg=bg_col, fg="#475569", font=("Segoe UI", 8)).pack(anchor="w")
            lbl = tk.Label(cf, text="0.00 TL", bg=bg_col, fg=fg_col, font=("Segoe UI", 11, "bold"))
            lbl.pack(anchor="w")
            setattr(self, attr, lbl)

        make_icra_card(cards, "Asıl Alacak (Takip)", "lbl_icra_asil", "#f8fafc", "#0f172a")
        make_icra_card(cards, "Faiz + Vekalet Ücreti", "lbl_icra_faiz", "#f8fafc", "#0f172a")
        make_icra_card(cards, "Harç & Masraflar", "lbl_icra_masraf", "#f8fafc", "#0f172a")
        make_icra_card(cards, "Toplam Alacak", "lbl_icra_toplam", "#f0fdf4", "#15803d")
        make_icra_card(cards, "Yatan / Tahsilat", "lbl_icra_yatan", "#e0f2fe", "#0369a1")
        make_icra_card(cards, "Kalan Borç Tutarı", "lbl_icra_kalan", "#fee2e2", "#b91c1c")

        # Bilgi Şeridi
        info_bar = ttk.Frame(f, padding=(4, 2))
        info_bar.pack(fill="x", pady=(0, 4))
        self.lbl_icra_kesinlesme = ttk.Label(info_bar, text="Durum: Bilinmiyor", style="Badge.Warn.TLabel")
        self.lbl_icra_kesinlesme.pack(side="left", padx=(0, 8))
        self.lbl_icra_malvarligi = ttk.Label(info_bar, text="Malvarlığı: Ücretsiz sorgu modu devrede", style="Badge.Count.TLabel")
        self.lbl_icra_malvarligi.pack(side="left")

        # Orta Bölünmüş Alan: Sol (Borçlular & Özet) | Sağ (Hesap Kalemleri)
        split = ttk.PanedWindow(f, orient="horizontal")
        split.pack(fill="both", expand=True)

        # Sol: Borçlular ve Özet Metin
        lf_left = ttk.LabelFrame(split, text="👤 Borçlu Bilgisi & Takip Notu", padding=4)
        split.add(lf_left, weight=1)

        self.txt_icra_ozet = tk.Text(lf_left, font=("Segoe UI", 9), wrap="word", padx=6, pady=6)
        sb_io = ttk.Scrollbar(lf_left, orient="vertical", command=self.txt_icra_ozet.yview)
        self.txt_icra_ozet.configure(yscrollcommand=sb_io.set)
        self.txt_icra_ozet.pack(side="left", fill="both", expand=True)
        sb_io.pack(side="right", fill="y")

        # Sağ: Kapak Hesabı Detayları
        lf_right = ttk.LabelFrame(split, text="📑 Kapak Hesabı Kalemleri", padding=4)
        split.add(lf_right, weight=1)

        cols_hk = ("kalem", "tutar")
        self.tree_icra_kalem = ttk.Treeview(lf_right, columns=cols_hk, show="headings")
        self.tree_icra_kalem.heading("kalem", text="Hesap Kalemi")
        self.tree_icra_kalem.heading("tutar", text="Tutar (TL)")
        self.tree_icra_kalem.column("kalem", width=220)
        self.tree_icra_kalem.column("tutar", width=120, anchor="e")

        sb_ik = ttk.Scrollbar(lf_right, orient="vertical", command=self.tree_icra_kalem.yview)
        self.tree_icra_kalem.configure(yscrollcommand=sb_ik.set)
        self.tree_icra_kalem.pack(side="left", fill="both", expand=True)
        sb_ik.pack(side="right", fill="y")

    def refresh_icra_combo(self):
        """İcra dosyalarını doldurur."""
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT dkey, birim, dosya_no, dosya_id FROM dosya WHERE (birim LIKE '%İcra%' OR birim LIKE '%Icra%' OR dosya_tur LIKE '%İcra%') AND durum LIKE '%Açık%' ORDER BY birim ASC")
        rows = cur.fetchall()
        conn.close()

        self._icra_dosyalar = {f"{r['birim']} - {r['dosya_no']}": (r['dkey'], r['dosya_id'], r['birim'], r['dosya_no']) for r in rows}
        vals = list(self._icra_dosyalar.keys())
        self.cb_icra_dosya["values"] = vals
        if vals and not self.cb_icra_dosya.get():
            self.cb_icra_dosya.set(vals[0])
            self.load_icra_for_selected()

    def load_icra_for_selected(self):
        secilen = self.cb_icra_dosya.get()
        if not secilen or secilen not in getattr(self, "_icra_dosyalar", {}):
            return
        dkey, dosya_id, birim, dosya_no = self._icra_dosyalar[secilen]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT takip_kesinlesen_miktar, toplam_faiz, vekalet_ucreti, masraf_miktari,
               tahsil_harci, toplam_alacak, yatan_para, bakiye_borc, kesinlesme_durumu,
               malvarligi_durumu, hesap_kalemleri_json, ozet_metin
        FROM icra_hesap WHERE dkey = ?
        """, (dkey,))
        row = cur.fetchone()
        conn.close()

        if row:
            self.lbl_icra_asil.config(text=f"{row['takip_kesinlesen_miktar']:,.2f} TL")
            self.lbl_icra_faiz.config(text=f"{(row['toplam_faiz'] + row['vekalet_ucreti']):,.2f} TL")
            self.lbl_icra_masraf.config(text=f"{(row['masraf_miktari'] + row['tahsil_harci']):,.2f} TL")
            self.lbl_icra_toplam.config(text=f"{row['toplam_alacak']:,.2f} TL")
            self.lbl_icra_yatan.config(text=f"{row['yatan_para']:,.2f} TL")
            self.lbl_icra_kalan.config(text=f"{row['bakiye_borc']:,.2f} TL")

            k_durum = row["kesinlesme_durumu"] or "Bilinmiyor"
            self.lbl_icra_kesinlesme.config(text=f"Takip Durumu: {k_durum}")
            self.lbl_icra_malvarligi.config(text=f"Malvarlığı: {row['malvarligi_durumu'] or ''}")

            self.txt_icra_ozet.delete("1.0", "end")
            self.txt_icra_ozet.insert("1.0", row["ozet_metin"] or "")

            for item in self.tree_icra_kalem.get_children():
                self.tree_icra_kalem.delete(item)

            kalemler = json.loads(row["hesap_kalemleri_json"] or "[]")
            for k in kalemler:
                self.tree_icra_kalem.insert("", "end", values=(
                    k.get("textAlan", ""),
                    f"{float(k.get('degerAlan') or 0):,.2f}" if k.get("degerAlan") is not None else "-"
                ))
        else:
            self.lbl_icra_asil.config(text="0.00 TL")
            self.lbl_icra_faiz.config(text="0.00 TL")
            self.lbl_icra_masraf.config(text="0.00 TL")
            self.lbl_icra_toplam.config(text="0.00 TL")
            self.lbl_icra_yatan.config(text="0.00 TL")
            self.lbl_icra_kalan.config(text="0.00 TL")
            self.txt_icra_ozet.delete("1.0", "end")
            self.txt_icra_ozet.insert("1.0", "Bu dosya için henüz kapak hesabı çekilmemiş. Yukarıdaki 'UYAP'tan Kapak Hesabı Çek' butonuna basabilirsiniz.")
            for item in self.tree_icra_kalem.get_children():
                self.tree_icra_kalem.delete(item)

    def on_fetch_icra_live(self):
        secilen = self.cb_icra_dosya.get()
        if not secilen or secilen not in getattr(self, "_icra_dosyalar", {}):
            messagebox.showinfo("Bilgi", "Lütfen önce bir icra dosyası seçin.")
            return
        dkey, dosya_id, birim, dosya_no = self._icra_dosyalar[secilen]

        ge.bildirim(self.app.root, f"İcra kapak hesabı sorgulanıyor: {dosya_no}...", renk="#1e3a5f")
        try:
            self.finans_mgr.bridge = self.app.bridge
            self.finans_mgr.fetch_icra_hesap(dosya_id, dkey, birim, dosya_no)
            self.load_icra_for_selected()
            ge.bildirim(self.app.root, "İcra hesabı ve takip kartı başarıyla güncellendi!", renk="#15803d")
        except Exception as e:
            messagebox.showerror("Hata", f"İcra hesabı sorgu hatası: {e}")

    # -------------------------------------------------------------------------
    # 3. SÜRELER & GÖREVLER SEKMESİ
    # -------------------------------------------------------------------------
    def _build_sure_tab(self):
        f = self.tab_sure

        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        btn_scan = ttk.Button(top, text="🔄 Süre & Duruşmaları Tara", command=self.on_scan_sureler, style="Vurgu.TButton")
        btn_scan.pack(side="left", padx=(0, 6))
        ge.Ipucu(btn_scan, "Tebligat sürelerini, duruşma tarihlerini ve duruşma zaptı ara kararlarındaki kesin süreleri tarar.")

        btn_alert = ttk.Button(top, text="📢 Telegram'a Alarm Gönder", command=self.on_send_telegram_alert)
        btn_alert.pack(side="left", padx=2)
        ge.Ipucu(btn_alert, "Son 3 gün kalan kritik duruşma ve süreleri Telegram üzerinden anlık bildirir.")

        self.lbl_sure_count = ttk.Label(top, text="Görev Sayısı: -", font=("Segoe UI", 9, "bold"))
        self.lbl_sure_count.pack(side="right")

        cols = ("oncelik", "kalan", "son_tarih", "baslik", "birim", "dosya_no", "aciklama")
        self.tree_sure = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        self.tree_sure.heading("oncelik", text="Öncelik")
        self.tree_sure.heading("kalan", text="Kalan Gün")
        self.tree_sure.heading("son_tarih", text="Son Tarih")
        self.tree_sure.heading("baslik", text="Görev / Süre Tanımı")
        self.tree_sure.heading("birim", text="Mahkeme / Birim")
        self.tree_sure.heading("dosya_no", text="Dosya No")
        self.tree_sure.heading("aciklama", text="Açıklama / Detay")

        self.tree_sure.column("oncelik", width=75, anchor="center")
        self.tree_sure.column("kalan", width=75, anchor="center")
        self.tree_sure.column("son_tarih", width=85, anchor="center")
        self.tree_sure.column("baslik", width=220)
        self.tree_sure.column("birim", width=160)
        self.tree_sure.column("dosya_no", width=85)
        self.tree_sure.column("aciklama", width=280)

        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree_sure.yview)
        self.tree_sure.configure(yscrollcommand=sb.set)
        self.tree_sure.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree_sure.tag_configure("acil", background="#fee2e2", foreground="#b91c1c")
        self.tree_sure.tag_configure("yuksek", background="#fef3c7", foreground="#b45309")
        self.tree_sure.tag_configure("normal", background="#ffffff")

        self.load_sureler()

    def load_sureler(self):
        for item in self.tree_sure.get_children():
            self.tree_sure.delete(item)

        rows = self.sure_mgr.get_yaklasan_gorevler(limit=100, sadece_bekleyen=True)
        self.lbl_sure_count.config(text=f"Bekleyen Görev: {len(rows)} adet")

        for r in rows:
            kalan = r.get("kalan_gun", 0)
            tag = "normal"
            if kalan <= 1:
                tag = "acil"
            elif kalan <= 3:
                tag = "yuksek"

            kalan_str = f"🔴 {kalan} Gün" if kalan <= 1 else (f"🟡 {kalan} Gün" if kalan <= 3 else f"{kalan} Gün")

            self.tree_sure.insert("", "end", tags=(tag,), values=(
                r.get("oncelik", "NORMAL"),
                kalan_str,
                r.get("son_tarih", ""),
                r.get("gorev_baslik", ""),
                r.get("birim", ""),
                r.get("dosya_no", ""),
                r.get("aciklama", "")
            ))

    def on_scan_sureler(self):
        ge.bildirim(self.app.root, "Canlı duruşmalar ve yasal süreler taranıyor...", renk="#1e3a5f")
        try:
            self.sure_mgr.scan_all(bridge=self.app.bridge)
            self.load_sureler()
            ge.bildirim(self.app.root, "Süre ve görev analizi tamamlandı!", renk="#15803d")
        except Exception as e:
            messagebox.showerror("Hata", f"Süre tarama hatası: {e}")

    def on_send_telegram_alert(self):
        msg = self.sure_mgr.build_telegram_alert_message(max_days=3)
        if not msg:
            messagebox.showinfo("Bilgi", "Önümüzdeki 3 gün içinde kritik süre veya duruşma bulunamadı.")
            return

        from uyap_watcher import TelegramClient, load_config
        cfg = load_config()
        tg = TelegramClient(cfg.get("telegram_token", ""), cfg.get("telegram_chat_id", ""))
        if not tg.is_configured:
            messagebox.showwarning("Telegram Yapılandırılmamış", "Lütfen önce 'watcher_config.json' içine Telegram token ve chat_id giriniz.")
            return

        if tg.send_message(msg):
            ge.bildirim(self.app.root, "Telegram alarmı başarıyla gönderildi!", renk="#15803d")
        else:
            messagebox.showerror("Hata", "Telegram mesajı gönderilemedi.")

    # -------------------------------------------------------------------------
    # 4. PORTAL İŞLEMLERİM SEKMESİ
    # -------------------------------------------------------------------------
    def _build_islem_tab(self):
        f = self.tab_islem

        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        btn_fetch = ttk.Button(top, text="🔄 UYAP'tan İşlemlerimi Güncelle", command=self.on_fetch_islemlerim, style="Vurgu.TButton")
        btn_fetch.pack(side="left", padx=(0, 6))
        ge.Ipucu(btn_fetch, "Son 30 gün içinde UYAP Avukat Portalından gönderdiğiniz tüm dilekçe, talep ve evrak kayıtlarını çeker.")

        self.lbl_islem_count = ttk.Label(top, text="Toplam İşlem: -", font=("Segoe UI", 9, "bold"))
        self.lbl_islem_count.pack(side="right")

        cols = ("tarih", "birim", "dosya_no", "islem_adi", "durum", "sahibi", "evrak_turu")
        self.tree_islem = ttk.Treeview(f, columns=cols, show="headings")
        self.tree_islem.heading("tarih", text="İşlem Tarihi")
        self.tree_islem.heading("birim", text="Mahkeme / Birim")
        self.tree_islem.heading("dosya_no", text="Dosya No")
        self.tree_islem.heading("islem_adi", text="İşlem / Talep Adı")
        self.tree_islem.heading("durum", text="İşin Durumu")
        self.tree_islem.heading("sahibi", text="İşin Sahibi")
        self.tree_islem.heading("evrak_turu", text="Evrak Türü Kodu")

        self.tree_islem.column("tarih", width=125)
        self.tree_islem.column("birim", width=180)
        self.tree_islem.column("dosya_no", width=85)
        self.tree_islem.column("islem_adi", width=240)
        self.tree_islem.column("durum", width=110, anchor="center")
        self.tree_islem.column("sahibi", width=95, anchor="center")
        self.tree_islem.column("evrak_turu", width=130)

        sb = ttk.Scrollbar(f, orient="vertical", command=self.tree_islem.yview)
        self.tree_islem.configure(yscrollcommand=sb.set)
        self.tree_islem.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.load_islemlerim()

    def load_islemlerim(self):
        for item in self.tree_islem.get_children():
            self.tree_islem.delete(item)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT is_emir_tarihi, birim_adi, dosya_no, islem_adi, isin_durumu, isin_sahibi, evrak_turu FROM portal_islemlerim ORDER BY is_emir_tarihi DESC LIMIT 200")
        rows = cur.fetchall()
        conn.close()

        self.lbl_islem_count.config(text=f"Kayıtlı İşlem: {len(rows)} adet")
        for r in rows:
            self.tree_islem.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4], r[5], r[6]))

    def on_fetch_islemlerim(self):
        ge.bildirim(self.app.root, "UYAP Portal İşlemlerim sorgulanıyor...", renk="#1e3a5f")
        try:
            self.finans_mgr.bridge = self.app.bridge
            islemler = self.finans_mgr.fetch_portal_islemlerim(days_back=30)
            self.load_islemlerim()
            ge.bildirim(self.app.root, f"{len(islemler)} adet işlem başarıyla güncellendi!", renk="#15803d")
        except Exception as e:
            messagebox.showerror("Hata", f"İşlemlerim sorgu hatası: {e}")

    # -------------------------------------------------------------------------
    # 5. GEMINI YAPAY ZEKA ANALİZ SEKMESİ
    # -------------------------------------------------------------------------
    def _build_ai_tab(self):
        f = self.tab_ai

        # Üst Ayar Şeridi
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))

        ttk.Label(top, text="Gemini API Anahtarı:").pack(side="left", padx=(0, 4))
        self.ent_ai_key = ttk.Entry(top, width=32, show="*")
        self.ent_ai_key.pack(side="left", padx=(0, 4))
        if self.ai_client.api_key:
            self.ent_ai_key.insert(0, self.ai_client.api_key)

        btn_save_key = ttk.Button(top, text="💾 Kaydet", command=self.on_save_ai_key)
        btn_save_key.pack(side="left", padx=(0, 8))

        ttk.Label(top, text="Model:").pack(side="left", padx=(4, 2))
        self.cb_ai_model = ttk.Combobox(top, values=["gemini-2.5-flash", "gemini-1.5-flash"], width=16, state="readonly")
        self.cb_ai_model.set("gemini-2.5-flash")
        self.cb_ai_model.pack(side="left", padx=(0, 8))

        lbl_cache_badge = ttk.Label(top, text="⚡ Önbellek Korumalı (0 Token)", style="Badge.Ok.TLabel")
        lbl_cache_badge.pack(side="right")
        ge.Ipucu(lbl_cache_badge, "Aynı dosya veya zapt bir kez analiz edildikten sonra SQLite'a kaydedilir ve tekrar token harcamaz!")

        # Aksiyon Butonları
        actions = ttk.Frame(f)
        actions.pack(fill="x", pady=(0, 6))

        btn_sum_dava = ttk.Button(actions, text="📄 Seçili Dava Dosyasını Özetle", command=self.on_ai_summarize_dava, style="Vurgu.TButton")
        btn_sum_dava.pack(side="left", padx=(0, 4))

        btn_sum_icra = ttk.Button(actions, text="📊 İcra Takip Analizi", command=self.on_ai_summarize_icra)
        btn_sum_icra.pack(side="left", padx=4)

        btn_zabit = ttk.Button(actions, text="⚖️ Duruşma Zaptı Ara Kararları Ayrıştır", command=self.on_ai_analyze_zabit)
        btn_zabit.pack(side="left", padx=4)

        self.var_force_refresh = tk.BooleanVar(value=False)
        cb_force = ttk.Checkbutton(actions, text="Yeniden Oluştur (Önbelleği Geç - Token Harcar)", variable=self.var_force_refresh)
        cb_force.pack(side="right")

        # Çıktı Alanı
        lf_out = ttk.LabelFrame(f, text="🧠 Gemini Hukuki Analiz Raporu", padding=6)
        lf_out.pack(fill="both", expand=True)

        self.txt_ai_output = tk.Text(lf_out, font=("Segoe UI", 10), wrap="word", padx=8, pady=8)
        sb_ai = ttk.Scrollbar(lf_out, orient="vertical", command=self.txt_ai_output.yview)
        self.txt_ai_output.configure(yscrollcommand=sb_ai.set)
        self.txt_ai_output.pack(side="left", fill="both", expand=True)
        sb_ai.pack(side="right", fill="y")

    def on_save_ai_key(self):
        key = self.ent_ai_key.get().strip()
        if not key:
            messagebox.showwarning("Uyarı", "Lütfen geçerli bir API anahtarı girin.")
            return
        self.ai_client.save_api_key(key)
        ge.bildirim(self.app.root, "Gemini API anahtarı başarıyla kaydedildi!", renk="#15803d")

    def on_ai_summarize_dava(self):
        secili = self.app.tree.selection()
        if not secili:
            messagebox.showinfo("Bilgi", "Lütfen önce 'Evrak Kataloğu' sekmesinden bir evrak veya dosya seçin.")
            return

        row_id = self.app.tree.set(secili[0], "id") if "id" in self.app.tree["columns"] else None
        item = self.app.tree.item(secili[0])
        vals = item.get("values", [])
        birim = vals[1] if len(vals) > 1 else ""
        dosya_no = vals[2] if len(vals) > 2 else ""
        dkey = f"{birim}-{dosya_no}"

        dosya_info = {"birimAdi": birim, "dosyaNo": dosya_no, "dosyaTur": "Dava Dosyası", "dosyaDurum": "Açık"}

        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", f"⏳ Gemini AI ({self.cb_ai_model.get()}) dosyayı inceliyor, lütfen bekleyin...\n")
        self.app.root.update_idletasks()

        self.ai_client.model = self.cb_ai_model.get()
        out = self.ai_client.summarize_dava_dosyasi(dkey, dosya_info, force_refresh=self.var_force_refresh.get())
        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", out)

    def on_ai_summarize_icra(self):
        secilen = getattr(self, "cb_icra_dosya", None) and self.cb_icra_dosya.get()
        if not secilen or secilen not in getattr(self, "_icra_dosyalar", {}):
            messagebox.showinfo("Bilgi", "Lütfen 'İcra Kapak Hesabı' sekmesinde bir icra dosyası seçin.")
            return
        dkey, dosya_id, birim, dosya_no = self._icra_dosyalar[secilen]

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM icra_hesap WHERE dkey = ?", (dkey,))
        row = cur.fetchone()
        conn.close()

        if not row:
            messagebox.showinfo("Bilgi", "Önce bu icra dosyasının kapak hesabını çekmelisiniz.")
            return

        dosya_info = {"birimAdi": birim, "dosyaNo": dosya_no}
        icra_info = dict(row)
        icra_info["takipKesinlesen"] = row["takip_kesinlesen_miktar"]
        icra_info["toplamFaiz"] = row["toplam_faiz"]
        icra_info["vekaletUcreti"] = row["vekalet_ucreti"]
        icra_info["masrafMiktari"] = row["masraf_miktari"]
        icra_info["tahsilHarci"] = row["tahsil_harci"]
        icra_info["toplamAlacak"] = row["toplam_alacak"]
        icra_info["yatanPara"] = row["yatan_para"]
        icra_info["bakiyeBorc"] = row["bakiye_borc"]
        icra_info["kesinlesmeDurumu"] = row["kesinlesme_durumu"]
        icra_info["malvarligiDurumu"] = row["malvarligi_durumu"]
        icra_info["borclular"] = json.loads(row["borclular_json"] or "[]")

        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", f"⏳ Gemini AI ({self.cb_ai_model.get()}) icra takibini analiz ediyor...\n")
        self.app.root.update_idletasks()

        self.ai_client.model = self.cb_ai_model.get()
        out = self.ai_client.summarize_icra_dosyasi(dkey, dosya_info, icra_info, force_refresh=self.var_force_refresh.get())
        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", out)

    def on_ai_analyze_zabit(self):
        secili = self.app.tree.selection()
        if not secili:
            messagebox.showinfo("Bilgi", "Lütfen 'Evrak Kataloğu'ndan bir duruşma zaptı seçin.")
            return

        item = self.app.tree.item(secili[0])
        vals = item.get("values", [])
        birim = vals[1] if len(vals) > 1 else ""
        dosya_no = vals[2] if len(vals) > 2 else ""
        dkey = f"{birim}-{dosya_no}"

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT pdf_path, path FROM evrak WHERE dkey = ? AND (tur LIKE '%Duruşma%' OR tur LIKE '%Zapt%') ORDER BY tarih DESC LIMIT 1", (dkey,))
        row = cur.fetchone()
        conn.close()

        if not row or not (row[0] or row[1]):
            messagebox.showinfo("Bilgi", "Bu dosyaya ait indirilmiş duruşma zaptı bulunamadı.")
            return

        fpath = row[0] or row[1]
        text = ""
        if fpath.lower().endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(fpath)
                for p in reader.pages[:4]:
                    text += (p.extract_text() or "") + "\n"
            except Exception as e:
                messagebox.showerror("Hata", f"PDF okunamadı: {e}")
                return

        if not text:
            messagebox.showwarning("Uyarı", "Duruşma zaptından metin çıkarılamadı.")
            return

        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", f"⏳ Gemini AI duruşma tutanağındaki ara kararları ve kesin süreleri çıkarıyor...\n")
        self.app.root.update_idletasks()

        self.ai_client.model = self.cb_ai_model.get()
        out = self.ai_client.extract_deadlines_from_zabit(text, dkey=dkey, force_refresh=self.var_force_refresh.get())
        self.txt_ai_output.delete("1.0", "end")
        self.txt_ai_output.insert("1.0", out)

    # -------------------------------------------------------------------------
    # 6. NOTION & TICKTICK ENTEGRASYON SEKMESİ
    # -------------------------------------------------------------------------
    def _build_ent_tab(self):
        f = self.tab_ent

        # Başlık ve Açıklama
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))

        ttk.Label(top, text="🚀 Hukuk Bürosu Bulut Entegrasyonu (TickTick & Notion)", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(top, text="Duruşmalarınızı, yasal sürelerinizi ve açık portföyünüzü tek tıkla TickTick ve Notion'a aktarın.", foreground="#64748b").pack(anchor="w")

        # Butonlar
        btn_box = ttk.Frame(f)
        btn_box.pack(fill="x", pady=(4, 10))

        btn_all = ttk.Button(btn_box, text="⚡ Tüm Dosyaları Üret / Güncelle", command=self.on_export_all_integrations, style="Vurgu.TButton")
        btn_all.pack(side="left", padx=(0, 6))

        btn_folder = ttk.Button(btn_box, text="📂 Çıktı Klasörünü Aç", command=lambda: ge.klasorde_goster(os.path.join(os.path.dirname(__file__), "ticktick_uyap_gorevler.csv")))
        btn_folder.pack(side="left", padx=4)

        # Kartlar Şeridi
        cards = ttk.Frame(f)
        cards.pack(fill="x", pady=(0, 8))

        def make_ent_card(parent, title, desc, file_name, icon):
            cf = tk.Frame(parent, bg="#ffffff", padx=12, pady=10, highlightbackground="#cbd5e1", highlightthickness=1)
            cf.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(cf, text=f"{icon} {title}", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(anchor="w")
            tk.Label(cf, text=desc, font=("Segoe UI", 8), bg="#ffffff", fg="#475569", wraplength=260, justify="left").pack(anchor="w", pady=(2, 6))
            tk.Label(cf, text=f"Dosya: {file_name}", font=("Consolas", 8), bg="#f8fafc", fg="#0284c7", padx=4, pady=2).pack(anchor="w")

        make_ent_card(cards, "TickTick Görevler", "3 Proje (Duruşmalar, Yasal Süreler, İcra). TickTick'e sürükle-bırak.", "ticktick_uyap_gorevler.csv", "✅")
        make_ent_card(cards, "iCalendar (.ics)", "TickTick, Google Takvim veya Apple Takvim'e abone olun.", "ticktick_uyap_takvim.ics", "📅")
        make_ent_card(cards, "Notion Portföyü", "Derdest dava ve icra dosyaları, mali bakiyeler ve duruşma günleri.", "notion_uyap_dosya_portfoyu.csv", "📑")

        # Rehber Metni
        lf_guide = ttk.LabelFrame(f, text="📘 Entegrasyon Yöntemleri ve Tavsiyeler", padding=6)
        lf_guide.pack(fill="both", expand=True)

        txt_guide = tk.Text(lf_guide, font=("Segoe UI", 9), wrap="word", padx=8, pady=8)
        sb_g = ttk.Scrollbar(lf_guide, orient="vertical", command=txt_guide.yview)
        txt_guide.configure(yscrollcommand=sb_g.set)
        txt_guide.pack(side="left", fill="both", expand=True)
        sb_g.pack(side="right", fill="y")

        guide_content = (
            "📌 TICKTICK ENTEGRASYON YÖNTEMİ:\n"
            "1. 'ticktick_uyap_gorevler.csv' dosyasını TickTick masaüstü veya web uygulamasında Ayarlar -> İçe Aktar bölümünden yükleyin.\n"
            "2. Görevleriniz otomatik olarak 3 ayrı klasöre ayrılır:\n"
            "   • UYAP - Duruşmalar: Duruşma saati, salon ve mahkeme bilgisiyle birlikte öncelikli olarak takvime işlenir.\n"
            "   • UYAP - Yasal Süreler & Ara Kararlar: İstinaf, bilirkişi itirazı ve kesin süreler yüksek öncelikle eklenir.\n"
            "   • UYAP - İcra Takip: Haciz ve kesinleşme takip işleri eklenir.\n"
            "3. 'ticktick_uyap_takvim.ics' dosyasını doğrudan Google Takvim veya Outlook'a URL veya dosya olarak bağlayabilirsiniz.\n\n"
            "📌 NOTION ENTEGRASYON YÖNTEMİ:\n"
            "1. Notion'da yeni bir sayfa açıp 'Import' -> 'CSV' seçeneği ile 'notion_uyap_dosya_portfoyu.csv' dosyasını seçin.\n"
            "2. Tüm derdest dava ve icra dosyalarınız; mahkeme adı, esas no, son duruşma tarihi, kalan gider avansı bakiyesi "
            "ve bekleyen görev sayısı ile eksiksiz bir Notion Veritabanına dönüşür!\n"
            "3. Dilerseniz Gemini AI sekmesinden oluşturduğunuz dosya özetlerini Notion kartlarının içerisine yapıştırabilirsiniz."
        )
        txt_guide.insert("1.0", guide_content)
        txt_guide.config(state="disabled")

    def on_export_all_integrations(self):
        try:
            res = export_all_integrations()
            ge.bildirim(self.app.root, "TickTick ve Notion dosyaları başarıyla üretildi!", renk="#15803d")
            messagebox.showinfo("Başarılı", f"Entegrasyon dosyaları hazırlandı:\n\n• {res['ticktick_csv']}\n• {res['ticktick_ics']}\n• {res['notion_csv']}")
        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarım hatası: {e}")
