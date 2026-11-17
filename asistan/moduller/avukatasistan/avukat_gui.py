#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚖️ AVUKAT ASİSTANI - CANLI KONTROL PANELİ & X11 GUI
Tebligat takibi, UETS canlı indirme, TickTick & Notion senkronizasyonu
ve anlık müdahale yönetim merkezi.
"""

import os
import sys
import threading
import queue
import time
import subprocess
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Proje dizinini ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import CONFIG, PROJECT_IDS
from utils import clean_text, determine_list
from csv_parser import parse_csv_file, find_latest_tebligat_csv
from eyp_parser import scan_all_eyp_files, parse_eyp_file
from notion_sync import fetch_notion_cases, find_notion_case
from state_manager import load_state, get_barcode_state, update_barcode_state
from ticktick_sync import (
    get_completed_tasks_live,
    get_project_tasks_live,
    extract_barcode_from_text,
    extract_esas_from_text,
    find_existing_tebligat_in_completed,
    find_existing_tebligat_in_active,
    find_or_create_parent_task,
    create_or_update_uets_subtask,
    audit_and_heal_all_tasks,
    clean_and_merge_duplicates
)
from autocontrol import inspect_all_tebligatlar

# -----------------------------------------------------------------------------
# RENK VE TEMA PALETİ (Modern Dark / Catppuccin Mocha)
# -----------------------------------------------------------------------------
C_BG = "#1e1e2e"          # Ana arka plan
C_PANEL = "#181825"       # Panel arka plan
C_CARD = "#252538"        # Kart arka plan
C_BORDER = "#313244"      # Kenarlık
C_TEXT = "#cdd6f4"        # Ana metin
C_MUTED = "#a6adc8"       # İkincil metin
C_ACCENT = "#89b4fa"      # Mavi vurgu
C_SUCCESS = "#a6e3a1"     # Yeşil başarı
C_WARNING = "#f9e2af"     # Sarı uyarı
C_DANGER = "#f38ba8"      # Kırmızı hata
C_SELECT = "#3b4261"      # Tablo seçim

class TextRedirector:
    """Konsol çıktılarını GUI log penceresine yönlendirir."""
    def __init__(self, text_widget, log_queue):
        self.text_widget = text_widget
        self.log_queue = log_queue

    def write(self, str_val):
        self.log_queue.put(str_val)

    def flush(self):
        pass

class AvukatGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("⚖️ Avukat Asistanı - Tebligat & Dosya Masası")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)
        self.root.configure(bg=C_BG)

        self.log_queue = queue.Queue()
        self.inspections_data = []
        self.is_busy = False

        self.setup_styles()
        self.create_widgets()

        # Log akışını başlat
        self.root.after(100, self.process_log_queue)

        # İlk veri yükleme
        self.root.after(300, self.refresh_data_async)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Genel Frame & Label
        style.configure(".", background=C_BG, foreground=C_TEXT, font=("Segoe UI", 9))
        style.configure("TFrame", background=C_BG)
        style.configure("Panel.TFrame", background=C_PANEL)
        style.configure("Card.TFrame", background=C_CARD, relief="flat")

        # Butonlar
        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=6, background=C_CARD, foreground=C_TEXT, borderwidth=1)
        style.map("TButton",
                  background=[("active", C_BORDER), ("disabled", C_PANEL)],
                  foreground=[("disabled", "#6c7086")])

        style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#2b5c92", foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", "#3b75b8")])

        style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#2d6a4f", foreground="#ffffff")
        style.map("Success.TButton", background=[("active", "#40916c")])

        style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#8c2f39", foreground="#ffffff")
        style.map("Danger.TButton", background=[("active", "#b23a48")])

        # Treeview (Tablo)
        style.configure("Treeview",
                        background=C_CARD,
                        foreground=C_TEXT,
                        fieldbackground=C_CARD,
                        rowheight=26,
                        font=("Segoe UI", 9),
                        borderwidth=0)
        style.map("Treeview",
                  background=[("selected", C_SELECT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading",
                        background=C_PANEL,
                        foreground=C_ACCENT,
                        font=("Segoe UI", 9, "bold"),
                        padding=5)
        style.map("Treeview.Heading", background=[("active", C_BORDER)])

    def create_widgets(self):
        # 1. ÜST BAŞLIK & DURUM ROZETLERİ
        header_frame = tk.Frame(self.root, bg=C_PANEL, height=50)
        header_frame.pack(fill="x", side="top", padx=0, pady=0)

        title_lbl = tk.Label(header_frame, text="⚖️ AVUKAT ASİSTANI - CANLI KONTROL MERKEZİ",
                             bg=C_PANEL, fg=C_ACCENT, font=("Segoe UI", 12, "bold"))
        title_lbl.pack(side="left", padx=15, pady=10)

        # Durum rozetleri
        self.badge_tt = tk.Label(header_frame, text="TickTick: ●", bg=C_CARD, fg=C_SUCCESS, font=("Segoe UI", 9, "bold"), padx=8, pady=3)
        self.badge_tt.pack(side="right", padx=6, pady=10)

        self.badge_notion = tk.Label(header_frame, text="Notion: ●", bg=C_CARD, fg=C_SUCCESS, font=("Segoe UI", 9, "bold"), padx=8, pady=3)
        self.badge_notion.pack(side="right", padx=6, pady=10)

        self.badge_gmail = tk.Label(header_frame, text="Gmail OTP: ●", bg=C_CARD, fg=C_SUCCESS, font=("Segoe UI", 9, "bold"), padx=8, pady=3)
        self.badge_gmail.pack(side="right", padx=6, pady=10)

        self.badge_uets = tk.Label(header_frame, text="UETS Portal: ●", bg=C_CARD, fg=C_ACCENT, font=("Segoe UI", 9, "bold"), padx=8, pady=3)
        self.badge_uets.pack(side="right", padx=6, pady=10)

        # 2. ÖZET İSTATİSTİK KARTLARI
        stats_frame = tk.Frame(self.root, bg=C_BG)
        stats_frame.pack(fill="x", padx=12, pady=8)

        self.card_total = self.create_stat_card(stats_frame, "Toplam Tebligat", "0", C_TEXT)
        self.card_synced = self.create_stat_card(stats_frame, "Tam Senkronize (Aktif)", "0", C_SUCCESS)
        self.card_pending = self.create_stat_card(stats_frame, "Ek Yükleme Bekleyen", "0", C_WARNING)
        self.card_completed = self.create_stat_card(stats_frame, "Kapatılmış / Tamam", "0", C_MUTED)
        self.card_missing = self.create_stat_card(stats_frame, "TickTick'te Eksik", "0", C_DANGER)

        # 3. İŞLEM BUTONLARI (TOOLBAR)
        toolbar = tk.Frame(self.root, bg=C_PANEL, height=45)
        toolbar.pack(fill="x", padx=12, pady=4)

        btn_uets = ttk.Button(toolbar, text="🌐 UETS Taze İndir & Senkronize Et", style="Primary.TButton", command=self.action_download_and_sync)
        btn_uets.pack(side="left", padx=4, pady=6)

        btn_force = ttk.Button(toolbar, text="⚡ Seçiliyi TickTick'e Ekle / Yenile", style="Success.TButton", command=self.action_force_sync_selected)
        btn_force.pack(side="left", padx=4, pady=6)

        btn_eyp = ttk.Button(toolbar, text="📦 Eksik EYP'leri İndir", command=self.action_download_missing_eyp)
        btn_eyp.pack(side="left", padx=4, pady=6)

        btn_dedup = ttk.Button(toolbar, text="🧹 Mükerrer Temizle & Onar", command=self.action_clean_duplicates)
        btn_dedup.pack(side="left", padx=4, pady=6)

        btn_excel = ttk.Button(toolbar, text="📑 UYAP Excel (dosyalar.xlsx)", command=self.action_sync_excel)
        btn_excel.pack(side="left", padx=4, pady=6)

        btn_refresh = ttk.Button(toolbar, text="🔄 Yenile (F5)", command=self.refresh_data_async)
        btn_refresh.pack(side="right", padx=4, pady=6)

        # Arama ve Filtreleme Kutusu
        filter_lbl = tk.Label(toolbar, text="🔍 Filtre:", bg=C_PANEL, fg=C_MUTED)
        filter_lbl.pack(side="right", padx=(10, 2), pady=6)
        self.search_var = tk.StringVar()
        if hasattr(self.search_var, "trace_add"):
            self.search_var.trace_add("write", lambda *args: self.filter_table())
        else:
            self.search_var.trace("w", lambda *args: self.filter_table())
        search_entry = tk.Entry(toolbar, textvariable=self.search_var, bg=C_CARD, fg=C_TEXT, insertbackground=C_TEXT, width=18, relief="flat")
        search_entry.pack(side="right", padx=4, pady=6)

        # 4. TEBLİGAT LİSTESİ TABLOSU
        table_frame = tk.Frame(self.root, bg=C_BG)
        table_frame.pack(fill="both", expand=True, padx=12, pady=4)

        columns = ("no", "gelis", "court", "esas", "barcode", "sure", "client", "tt_status", "eyp_status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("no", text="#")
        self.tree.heading("gelis", text="Geliş Tarihi")
        self.tree.heading("court", text="Merci / Mahkeme")
        self.tree.heading("esas", text="Esas No")
        self.tree.heading("barcode", text="Barkod No")
        self.tree.heading("sure", text="Yasal Süre (Son Gün)")
        self.tree.heading("client", text="Müvekkil")
        self.tree.heading("tt_status", text="TickTick Durumu")
        self.tree.heading("eyp_status", text="EYP / Ek")

        self.tree.column("no", width=35, anchor="center")
        self.tree.column("gelis", width=95, anchor="center")
        self.tree.column("court", width=260, anchor="w")
        self.tree.column("esas", width=95, anchor="center")
        self.tree.column("barcode", width=125, anchor="center")
        self.tree.column("sure", width=135, anchor="center")
        self.tree.column("client", width=110, anchor="w")
        self.tree.column("tt_status", width=140, anchor="w")
        self.tree.column("eyp_status", width=85, anchor="center")

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")

        # Renk Etiketleri (Row Tags)
        self.tree.tag_configure("green", foreground="#a6e3a1")
        self.tree.tag_configure("yellow", foreground="#f9e2af")
        self.tree.tag_configure("orange", foreground="#fab387")
        self.tree.tag_configure("red", foreground="#f38ba8", font=("Segoe UI", 9, "bold"))
        self.tree.tag_configure("gray", foreground="#6c7086")

        # Çift Tıklama & Sağ Tık Menüsü
        self.tree.bind("<Double-1>", self.on_double_click_row)
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.root.bind("<F5>", lambda e: self.refresh_data_async())

        self.context_menu = tk.Menu(self.root, tearoff=0, bg=C_CARD, fg=C_TEXT, activebackground=C_SELECT)
        self.context_menu.add_command(label="⚡ TickTick'e Ekle / Yeniden Senkronize Et", command=self.action_force_sync_selected)
        self.context_menu.add_command(label="🔍 Detayları Görüntüle", command=self.on_double_click_row)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📋 Barkod Kopyala", command=self.copy_selected_barcode)
        self.context_menu.add_command(label="🔗 Notion Kartını Aç", command=self.open_selected_notion)
        self.context_menu.add_command(label="📂 Evrak Klasörünü Aç", command=self.open_selected_folder)

        # 5. ALT PANEL: CANLI LOG KONSOLU
        log_panel = tk.Frame(self.root, bg=C_PANEL, height=150)
        log_panel.pack(fill="x", side="bottom", padx=12, pady=(2, 8))

        log_header = tk.Frame(log_panel, bg=C_PANEL)
        log_header.pack(fill="x", padx=6, pady=(4, 2))
        tk.Label(log_header, text="📋 Canlı İşlem ve Otokontrol Konsolu", bg=C_PANEL, fg=C_MUTED, font=("Segoe UI", 8, "bold")).pack(side="left")

        btn_clear_log = tk.Button(log_header, text="Temizle", bg=C_CARD, fg=C_MUTED, font=("Segoe UI", 8), relief="flat", command=self.clear_logs)
        btn_clear_log.pack(side="right")

        self.log_text = scrolledtext.ScrolledText(log_panel, height=6, bg="#11111b", fg="#bac2de",
                                                  insertbackground="#bac2de", font=("Consolas", 8), relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def create_stat_card(self, parent, title, val, color):
        f = tk.Frame(parent, bg=C_CARD, padx=12, pady=6)
        f.pack(side="left", fill="both", expand=True, padx=4)

        t_lbl = tk.Label(f, text=title, bg=C_CARD, fg=C_MUTED, font=("Segoe UI", 8))
        t_lbl.pack(anchor="w")

        v_lbl = tk.Label(f, text=val, bg=C_CARD, fg=color, font=("Segoe UI", 14, "bold"))
        v_lbl.pack(anchor="w")
        return v_lbl

    def log(self, msg):
        self.log_queue.put(str(msg) + "\n")

    def clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def process_log_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.insert(tk.END, msg)
            self.log_text.see(tk.END)
        self.root.after(100, self.process_log_queue)

    # -------------------------------------------------------------------------
    # TABLO VE VERİ YÖNETİMİ
    # -------------------------------------------------------------------------
    def refresh_data_async(self):
        if self.is_busy:
            return
        self.is_busy = True
        self.log("🔄 Tebligatlar, TickTick ve Notion verileri taranıyor...")

        def worker():
            try:
                data = inspect_all_tebligatlar()
                self.root.after(0, lambda: self.update_table(data))
            except Exception as e:
                self.log(f"⚠️ Veri tarama hatası: {e}")
            finally:
                self.is_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def update_table(self, data):
        self.inspections_data = data
        self.filter_table()

        # İstatistik Kartlarını Güncelle
        total = len(data)
        synced = sum(1 for d in data if d["status_code"] == "SYNCED")
        pending = sum(1 for d in data if d["status_code"] == "PENDING_ATTACHMENT")
        completed = sum(1 for d in data if d["status_code"] == "COMPLETED")
        missing = sum(1 for d in data if "MISSING" in d["status_code"])

        self.card_total.config(text=str(total))
        self.card_synced.config(text=str(synced))
        self.card_pending.config(text=str(pending))
        self.card_completed.config(text=str(completed))
        self.card_missing.config(text=str(missing))

        self.log(f"✅ Güncelleme tamamlandı: {total} tebligat incelendi ({synced} aktif/tam, {missing} eksik).")

    def filter_table(self):
        query = clean_text(self.search_var.get().lower())
        for row in self.tree.get_children():
            self.tree.delete(row)

        for d in self.inspections_data:
            match_str = clean_text(f"{d['court']} {d['esas_no']} {d['barcode']} {d['status_desc']}").lower()
            if query and query not in match_str:
                continue

            g_date = d["gelis_str"][:10] if d["gelis_str"] else "-"
            eyp_icon = "📦 Var" if d["has_local_eyp"] else "❌ Yok"
            client_name = d["notion_case"].get("client_name") if d["notion_case"] else "-"

            tag = d["status_color"]
            self.tree.insert("", "end", iid=str(d["idx"]), values=(
                d["idx"],
                g_date,
                d["court"],
                d["esas_no"],
                d["barcode"],
                d["target_str"],
                client_name,
                d["status_desc"],
                eyp_icon
            ), tags=(tag,))

    def get_selected_item(self):
        selected = self.tree.selection()
        if not selected:
            return None
        idx = int(selected[0])
        for d in self.inspections_data:
            if d["idx"] == idx:
                return d
        return None

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def copy_selected_barcode(self):
        item = self.get_selected_item()
        if item and item.get("barcode"):
            self.root.clipboard_clear()
            self.root.clipboard_append(item["barcode"])
            self.log(f"📋 Barkod panoya kopyalandı: {item['barcode']}")

    def open_selected_notion(self):
        item = self.get_selected_item()
        if item and item.get("notion_case") and item["notion_case"].get("url"):
            webbrowser.open(item["notion_case"]["url"])
        else:
            messagebox.showinfo("Notion", "Bu tebligat için bağlı bir Notion kartı bulunamadı.")

    def open_selected_folder(self):
        out_dir = CONFIG.get("EVRAK_OUTPUT_DIR") or CONFIG.get("UETS_ARCHIVE_DIR")
        if out_dir and os.path.exists(out_dir):
            subprocess.run(["xdg-open", out_dir], check=False)
        else:
            messagebox.showinfo("Dizin", f"Evrak dizini bulunamadı: {out_dir}")

    # -------------------------------------------------------------------------
    # AKSİYONLAR VE BUTONLAR
    # -------------------------------------------------------------------------
    def action_download_and_sync(self):
        if self.is_busy:
            self.log("⏳ Arka planda bir işlem devam ediyor, lütfen tamamlanmasını bekleyin...")
            return
        self.is_busy = True
        self.log("\n" + "="*60)
        self.log("🌐 UETS OTOMATİK İNDİRME VE SENKRONİZASYON BAŞLATILIYOR...")
        self.log("="*60)

        def worker():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            redirector = TextRedirector(self.log_text, self.log_queue)
            sys.stdout = redirector
            sys.stderr = redirector
            try:
                from uets_downloader import login_and_download
                dl_csv = login_and_download(headless=True, auto_sync=True)
                self.log(f"\n🎉 UETS İşlemi tamamlandı: {dl_csv}")
            except Exception as e:
                self.log(f"\n⚠️ UETS indirme hatası: {e}")
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                self.is_busy = False
                self.root.after(500, self.refresh_data_async)

        threading.Thread(target=worker, daemon=True).start()

    def action_force_sync_selected(self):
        item = self.get_selected_item()
        if not item:
            messagebox.showwarning("Seçim Gerekli", "Lütfen işlem yapmak istediğiniz tebligat satırını seçin.")
            return

        court = item["court"]
        esas_no = item["esas_no"]
        barcode = item["barcode"]
        raw_item = item["raw_item"]

        self.log(f"\n⚡ Seçili tebligat TickTick'e zorla aktarılıyor: {court} [{esas_no}] (Barkod: {barcode})...")

        def worker():
            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log_text, self.log_queue)
            try:
                list_name = item["list_name"]
                pid = item["project_id"]
                n_url = item["notion_case"].get("url", "") if item.get("notion_case") else ""
                c_tag = item["notion_case"].get("client_tag", "") if item.get("notion_case") else ""
                is_cmk = item["notion_case"].get("is_cmk", False) if item.get("notion_case") else False

                parent_res = find_or_create_parent_task(court, esas_no, pid, c_tag, n_url)
                parent_id = parent_res[0] if isinstance(parent_res, (tuple, list)) else parent_res

                # Eğer arşivde EYP varsa evraklarını ayıkla
                if item.get("local_eyp_path"):
                    full_eyp = parse_eyp_file(item["local_eyp_path"], extract_files=True)
                    if full_eyp:
                        raw_item["documents"] = full_eyp.get("documents", [])
                        raw_item["extracted_paths"] = full_eyp.get("extracted_paths", [])

                res = create_or_update_uets_subtask(
                    raw_item, pid, parent_id,
                    client_tag=c_tag, notion_url=n_url,
                    list_name=list_name, is_cmk=is_cmk, force=True
                )
                self.log(f"✅ Sonuç: {res}")
            except Exception as e:
                self.log(f"⚠️ Zorla ekleme hatası: {e}")
            finally:
                sys.stdout = old_stdout
                self.root.after(500, self.refresh_data_async)

        threading.Thread(target=worker, daemon=True).start()

    def action_download_missing_eyp(self):
        missing_count = sum(1 for d in self.inspections_data if "MISSING" in d["status_code"] or not d["has_local_eyp"])
        if missing_count == 0:
            messagebox.showinfo("Tamam", "Eksik EYP paketi bulunmuyor, tüm dosyalar arşivde mevcut!")
            return

        if not messagebox.askyesno("EYP İndirme", f"{missing_count} adet eksik tebligat tespit edildi. UETS'ye bağlanıp indirmek istiyor musunuz?"):
            return

        self.action_download_and_sync()

    def action_clean_duplicates(self):
        self.log("\n🧹 TickTick mükerrer kontrolü ve sağlık denetimi başlatılıyor...")

        def worker():
            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log_text, self.log_queue)
            try:
                res = audit_and_heal_all_tasks()
                self.log(f"✅ Sağlık Denetimi Bitti: {res}")
            except Exception as e:
                self.log(f"⚠️ Temizlik hatası: {e}")
            finally:
                sys.stdout = old_stdout
                self.root.after(500, self.refresh_data_async)

        threading.Thread(target=worker, daemon=True).start()

    def action_sync_excel(self):
        self.log("\n📑 UYAP Excel (dosyalar.xlsx) senkronizasyonu başlatılıyor...")

        def worker():
            old_stdout = sys.stdout
            sys.stdout = TextRedirector(self.log_text, self.log_queue)
            try:
                from sync_uyap_excel import run_sync
                run_sync(apply=True)
                self.log("✅ Excel senkronizasyonu tamamlandı.")
            except Exception as e:
                self.log(f"⚠️ Excel senkronizasyon hatası: {e}")
            finally:
                sys.stdout = old_stdout
                self.root.after(500, self.refresh_data_async)

        threading.Thread(target=worker, daemon=True).start()

    def on_double_click_row(self, event=None):
        item = self.get_selected_item()
        if not item:
            return

        # Detay Penceresi Aç
        win = tk.Toplevel(self.root)
        win.title(f"📨 Tebligat Detayı: {item['court']} [{item['esas_no']}]")
        win.geometry("640x540")
        win.configure(bg=C_PANEL)
        win.transient(self.root)

        txt = scrolledtext.ScrolledText(win, bg=C_CARD, fg=C_TEXT, font=("Segoe UI", 10), padx=10, pady=10)
        txt.pack(fill="both", expand=True, padx=12, pady=12)

        dl = item["deadlines"]
        info_str = f"🏛️ MERCİ: {item['court']}\n"
        info_str += f"📌 ESAS NO: {item['esas_no']}\n"
        info_str += f"🏷️ BARKOD: {item['barcode']}\n"
        info_str += f"📅 GELİŞ TARİHİ: {item['gelis_str']}\n"
        info_str += f"⏳ YASAL SÜRE (SON GÜN): {item['target_str']} (17:00)\n"
        info_str += f"  ↳ Tebliğ Sayılma: {dl.get('teblig_str', '-')}\n"
        info_str += f"  ↳ 7 Günlük Süre: {dl.get('d7_str', '-')}\n"
        info_str += f"  ↳ 14 Günlük Süre: {dl.get('d14_str', '-')}\n\n"

        info_str += f"📊 DURUM: {item['status_desc']}\n"
        info_str += f"📦 YEREL EYP: {'Mevcut (' + item['local_eyp_path'] + ')' if item['has_local_eyp'] else 'Eksik / Henüz İndirilmedi'}\n\n"

        if item.get("notion_case"):
            nc = item["notion_case"]
            info_str += f"🔗 NOTION DOSYASI: {nc.get('client_name')} ({nc.get('client_tag')})\n"
            info_str += f"   URL: {nc.get('url')}\n\n"
        else:
            info_str += "ℹ️ Notion Dosyası: Eşleşmedi (Genel merci listesinde).\n\n"

        txt.insert("1.0", info_str)
        txt.configure(state="disabled")

        btn_box = tk.Frame(win, bg=C_PANEL)
        btn_box.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(btn_box, text="⚡ TickTick'e Zorla Ekle", style="Success.TButton",
                   command=lambda: [win.destroy(), self.action_force_sync_selected()]).pack(side="left", padx=4)
        ttk.Button(btn_box, text="Kapat", command=win.destroy).pack(side="right", padx=4)

def main():
    print("⚖️  Avukat Asistanı Arayüzü açılıyor...")
    root = tk.Tk()
    app = AvukatGuiApp(root)
    print("✅ Grafiksel arayüz penceresi aktif. (Pencereyi kapatana kadar çalışacaktır)")
    root.mainloop()

if __name__ == "__main__":
    main()
