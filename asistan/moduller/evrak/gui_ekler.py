#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UYAP Evrak Yöneticisi — arayüz yardımcıları: ipuçları, bildirimler (animasyonlu), kullanım kılavuzu,
araç menüsü komutları ve günlük paketleme.
Copyright (c) 2026 Av. Can KIZILYAR. Tüm hakları saklıdır.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk

UYGULAMA_ADI = "UYAP Evrak Yöneticisi"
SURUM = "3.2.0"
IMZA = "© 2026 Av. Can KIZILYAR — Tüm hakları saklıdır."

RENK = {
    "lacivert": "#0f2744", "lacivert2": "#1e3a5f", "acik": "#f8fafc",
    "kart_bg": "#ffffff", "kart_border": "#e2e8f0",
    "yesil": "#10b981", "kirmizi": "#ef4444", "gri": "#64748b",
    "vurgu": "#2563eb", "mavi": "#0284c7", "mor": "#8b5cf6", "sari": "#f59e0b",
    "badge_yesil_bg": "#dcfce7", "badge_yesil_fg": "#15803d",
    "badge_sari_bg": "#fef3c7", "badge_sari_fg": "#b45309",
    "badge_kirmizi_bg": "#fee2e2", "badge_kirmizi_fg": "#b91c1c",
    "badge_mavi_bg": "#e0f2fe", "badge_mavi_fg": "#0284c7",
    "badge_mor_bg": "#f3e8ff", "badge_mor_fg": "#7e22ce",
    "badge_gri_bg": "#f1f5f9", "badge_gri_fg": "#334155",
}


# ---------------------------------------------------------------------------
# Görünüm ve Modern Stil
# ---------------------------------------------------------------------------
def stil_uygula(root: tk.Tk):
    st = ttk.Style(root)
    for th in (("vista", "clam") if os.name == "nt" else ("clam",)):
        try:
            st.theme_use(th)
            break
        except tk.TclError:
            continue
    f = ("Segoe UI", 9) if os.name == "nt" else ("DejaVu Sans", 9)
    st.configure("Treeview", rowheight=26, font=f)
    st.configure("Treeview.Heading", font=(f[0], 9, "bold"))
    st.configure("Baslik.TFrame", background=RENK["lacivert"])
    st.configure("Baslik.TLabel", background=RENK["lacivert"], foreground="white", font=(f[0], 12, "bold"))
    st.configure("Imza.TLabel", background=RENK["lacivert"], foreground="#94a3b8", font=(f[0], 8))
    st.configure("Vurgu.TButton", font=(f[0], 9, "bold"))
    st.configure("Watcher.TButton", font=(f[0], 9, "bold"))
    st.configure("Action.TButton", font=(f[0], 9))
    st.configure("Ayrinti.TLabelframe.Label", font=(f[0], 9, "bold"))
    st.configure("Ipucu.TLabel", foreground=RENK["gri"])

    # Modern Durum Rozetleri (Badges)
    st.configure("Badge.Ok.TLabel", background="#dcfce7", foreground="#15803d", font=(f[0], 8, "bold"), padding=(8, 3))
    st.configure("Badge.Warn.TLabel", background="#fef3c7", foreground="#b45309", font=(f[0], 8, "bold"), padding=(8, 3))
    st.configure("Badge.Err.TLabel", background="#fee2e2", foreground="#b91c1c", font=(f[0], 8, "bold"), padding=(8, 3))
    st.configure("Badge.Drive.TLabel", background="#e0f2fe", foreground="#0284c7", font=(f[0], 8, "bold"), padding=(8, 3))
    st.configure("Badge.Watcher.TLabel", background="#f3e8ff", foreground="#7e22ce", font=(f[0], 8, "bold"), padding=(8, 3))
    st.configure("Badge.Count.TLabel", background="#f1f5f9", foreground="#475569", font=(f[0], 8, "bold"), padding=(6, 2))
    st.configure("Badge.Metric.TLabel", background="#ffffff", foreground="#0f172a", font=(f[0], 9, "bold"), padding=(8, 4))

    # Kart Stilleri
    st.configure("Card.TLabelframe", background="#ffffff")
    st.configure("Card.TLabelframe.Label", font=(f[0], 9, "bold"), foreground=RENK["lacivert2"])

    root.option_add("*Listbox.font", f)
    root.option_add("*Text.font", ("Consolas", 9))
    root.option_add("*Listbox.background", "#ffffff")
    root.option_add("*Listbox.selectBackground", "#e0edff")
    root.option_add("*Listbox.selectForeground", "#0f172a")


# ---------------------------------------------------------------------------
# Katlanabilir Kart Bileşeni (Collapsible Card)
# ---------------------------------------------------------------------------
class CollapsibleCard(ttk.Frame):
    """Modern, katlanabilir ve sağında rozet taşıyan filtre kartı."""

    def __init__(self, master, title: str = "Filtre", icon: str = "📁", collapsed: bool = False, on_toggle=None, **kw):
        super().__init__(master, **kw)
        self.collapsed = collapsed
        self.on_toggle = on_toggle

        # Başlık Çubuğu
        self.hdr = ttk.Frame(self, cursor="hand2")
        self.hdr.pack(fill="x", pady=(3, 1))

        self.btn_toggle = ttk.Label(self.hdr, text="▼" if not collapsed else "►", width=2,
                                    font=("Segoe UI", 9, "bold"), foreground=RENK["lacivert2"])
        self.btn_toggle.pack(side="left")

        self.lbl_title = ttk.Label(self.hdr, text=f"{icon}  {title}", font=("Segoe UI", 9, "bold"),
                                   foreground=RENK["lacivert2"])
        self.lbl_title.pack(side="left", padx=2)

        self.lbl_badge = ttk.Label(self.hdr, text="Tümü", style="Badge.Count.TLabel")
        self.lbl_badge.pack(side="right", padx=(0, 2))

        # Gövde Çerçevesi
        self.body = ttk.Frame(self, padding=(2, 2, 2, 4))
        if not collapsed:
            self.body.pack(fill="both", expand=True)

        for w in (self.hdr, self.btn_toggle, self.lbl_title):
            w.bind("<Button-1>", lambda e: self.toggle())

    def toggle(self):
        self.collapsed = not self.collapsed
        if self.collapsed:
            self.body.pack_forget()
            self.btn_toggle.config(text="►")
        else:
            self.body.pack(fill="both", expand=True)
            self.btn_toggle.config(text="▼")
        if self.on_toggle:
            self.on_toggle(self.collapsed)

    def set_badge(self, text: str, style: str = "Badge.Count.TLabel"):
        self.lbl_badge.config(text=text, style=style)


class Ipucu:
    """Fare üzerine gelince açıklama gösteren ve ekran sınırlarına duyarlı kutu."""

    def __init__(self, widget, metin: str, gecikme: int = 400):
        self.w, self.metin, self.gecikme = widget, metin, gecikme
        self.tip = None
        self._id = None
        widget.bind("<Enter>", self._planla, add="+")
        widget.bind("<Leave>", self._kapat, add="+")
        widget.bind("<ButtonPress>", self._kapat, add="+")

    def _planla(self, _e=None):
        self._id = self.w.after(self.gecikme, self._goster)

    def _goster(self):
        if self.tip:
            return
        self.tip = tk.Toplevel(self.w)
        self.tip.wm_overrideredirect(True)
        try:
            self.tip.attributes("-topmost", True)
        except Exception:
            pass

        lbl = tk.Label(self.tip, text=self.metin, justify="left", background="#0f172a", foreground="#f8fafc",
                       relief="flat", borderwidth=1, wraplength=420, padx=10, pady=6, font=("Segoe UI", 8))
        lbl.pack()
        self.tip.update_idletasks()
        tw, th = self.tip.winfo_reqwidth(), self.tip.winfo_reqheight()

        x = self.w.winfo_rootx() + 10
        y = self.w.winfo_rooty() + self.w.winfo_height() + 4

        # Ekran taşma kontrolü
        sw = self.w.winfo_screenwidth()
        sh = self.w.winfo_screenheight()
        if x + tw > sw - 12:
            x = max(10, sw - tw - 12)
        if y + th > sh - 12:
            y = max(10, self.w.winfo_rooty() - th - 4)

        self.tip.wm_geometry(f"+{x}+{y}")

    def _kapat(self, _e=None):
        if self._id:
            self.w.after_cancel(self._id)
            self._id = None
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


def bildirim(root: tk.Tk, metin: str, renk: str = "#1e3a5f", sure: int = 3500, baslik: str | None = None):
    """Sağ altta yumuşak kayma ve şeffaflık (slide-up + fade) animasyonlu modern bildirim kartı."""
    try:
        t = tk.Toplevel(root)
        t.wm_overrideredirect(True)
        try:
            t.attributes("-topmost", True)
            t.attributes("-alpha", 0.0)
        except tk.TclError:
            pass

        # Kart İçeriği
        cf = tk.Frame(t, background=renk, borderwidth=1, relief="solid")
        cf.pack(fill="both", expand=True)

        top_f = tk.Frame(cf, background=renk)
        top_f.pack(fill="x", padx=12, pady=(8, 2))
        
        b_lbl = tk.Label(top_f, text=baslik or "UYAP Bildirimi", background=renk, foreground="#ffffff",
                         font=("Segoe UI", 9, "bold"))
        b_lbl.pack(side="left")

        def dismiss():
            try:
                t.destroy()
            except Exception:
                pass

        btn_x = tk.Label(top_f, text="✕", background=renk, foreground="#cbd5e1", font=("Segoe UI", 8, "bold"),
                         cursor="hand2")
        btn_x.pack(side="right")
        btn_x.bind("<Button-1>", lambda e: dismiss())

        msg_lbl = tk.Label(cf, text=metin, background=renk, foreground="#f8fafc", padx=12, pady=6,
                           wraplength=380, justify="left", font=("Segoe UI", 9))
        msg_lbl.pack(fill="both")

        root.update_idletasks()
        w, h = t.winfo_reqwidth(), t.winfo_reqheight()
        target_x = root.winfo_rootx() + root.winfo_width() - w - 24
        target_y = root.winfo_rooty() + root.winfo_height() - h - 24
        start_y = target_y + 35
        t.wm_geometry(f"{w}x{h}+{max(target_x, 0)}+{max(start_y, 0)}")

        # Kayma ve belirme animasyonu (Slide up + Fade in)
        steps = 6
        step_ms = 22

        def slide_in(i):
            if not t.winfo_exists():
                return
            curr_y = int(start_y - (start_y - target_y) * (i / steps))
            alpha = min(0.96, (i / steps))
            try:
                t.wm_geometry(f"{w}x{h}+{max(target_x, 0)}+{max(curr_y, 0)}")
                t.attributes("-alpha", alpha)
            except Exception:
                return
            if i < steps:
                t.after(step_ms, slide_in, i + 1)
            else:
                t.after(sure, start_fade_out)

        def start_fade_out():
            fade_out(0.96)

        def fade_out(a):
            if not t.winfo_exists():
                return
            try:
                if a > 0.08:
                    t.attributes("-alpha", a)
                    t.after(step_ms, fade_out, a - 0.12)
                else:
                    t.destroy()
            except Exception:
                pass

        slide_in(1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Kullanım kılavuzu
# ---------------------------------------------------------------------------
KILAVUZ = """UYAP EVRAK YÖNETİCİSİ — KULLANIM KILAVUZU
{imza}

1) BAŞLARKEN
   • "Bağlan / Giriş": Tarayıcı arka planda (görünmeden) açılır. UYAP oturumu yoksa e-İmza (PIN yalnızca
     bellekte tutulur) veya Mobil İmza ile giriş yapılır. Oturum indirme sırasında düşerse program aynı
     yöntemle yeniden girer ve AYNI evrakı tekrar dener; yarım/bozuk dosya veya HTML hata sayfası asla
     kaydedilmez, hiçbir evrak atlanmaz.
   • "UYAP'ı Tara": Dosyalarınızdaki tüm evrak ve eklerin LİSTESİNİ kataloğa yazar (indirme yapmaz).
     Günlük kullanımda "Evet: yalnızca AÇIK dosyaları güncelle" yeterlidir. Katalog kalıcıdır; programı
     kapatıp açınca yeniden taranmaz.

2) ASIL EVRAK ve EK NEDİR?
   UYAP'ta her evrakın (ör. "Talimat Üst Yazısı") altında ekleri olabilir (ör. "İfade Tutanağı.tif",
   "gelen_eyp_gönderisi.eyp"). Listede ekler "↳ EK03: …" diye girintili gösterilir.
   Örnek:  2025-07-10  Talimat Üst Yazısı                      (Asıl)
              ↳ EK01: Talimat Dosyasının Emniyetten İadesi     (Ek)
              ↳ EK02: 2025070416582311037.tif                  (Ek)
   • "Yalnız asıl evrak": eklerin hiçbiri gelmez (hızlı, az sayıda).
   • "Yalnız ekler": sadece ekler.
   • Evrak türü listesi ekleri AİT OLDUKLARI ASIL EVRAKIN türüyle süzer. Örn. "Genel Karar/Müzekkere"yi
     kırmızı (hariç) yaparsanız o müzekkerelere eklenmiş yüz binlerce dosya sureti de hariç kalır.
   • "Eklerde ait olduğu evrakın kategorisine bak": kategori listesini de aynı mantıkla çalıştırır.
     Örn. "Karar" yeşil + bu kutu işaretli = kararlar ve kararların ekleri.
   • "Aynı dosyada aynı adlı ekleri bir kez al (tahmini)": Aynı dosyada adı aynı olan eklerden ilkini alır.
     Çok yer kazandırır ama TAHMİNDİR: adı aynı, içeriği farklı ekler de elenebilir.
   • Diskte ekler asıl evrakın adıyla başlar, böylece yan yana durur:
       2025-07-10_Talimat Üst Yazısı_no68987.udf
       2025-07-10_Talimat Üst Yazısı_no68987__EK01_İfade Tutanağı.tif  (+ aynı adla .pdf)

3) FİLTRELER
   • Listeler: 1. tık = getir (yeşil ✔), 2. tık = hariç tut (kırmızı ✖), 3. tık = kaldır.
     Aynı listede hem getirip hem hariç tutabilirsiniz. Sayılar diğer filtrelere göre güncellenir.
     "Sırala: A→Z / Sayı" ile alfabetik ya da sayıya göre sıralayın.
   • Metin kutuları Türkçe harf duyarsızdır (çağlar = CAGLAR). Başına "-" koyduğunuz kelime hariç tutulur,
     tırnak içi tek ifade sayılır:   sungur -ahmet      "ağır ceza" -"sulh ceza"
   • İçerik araması yalnızca indirilmiş (veya önizlenmiş) evrakların metninde çalışır.
   • "Dosya biçimi (uzantı)": UYAP, indirilmeden önce asıl evrakların biçimini bildirmez; bu yüzden
     indirilmemiş asıl evraklar "Henüz bilinmiyor" görünür (büyük çoğunluğu .udf'dir). Eklerde biçim adından
     anlaşılıyorsa (…tif, …pdf, …eyp) baştan gösterilir. İndirilince gerçek biçim yazılır.
   • Filtreleriniz kapanışta kaydedilir, açılışta aynen gelir.

4) MÜKERRER (TEKRAR) KONTROLÜ
   • İstinaf / birleşen / talimat dosyalarında tekrar görünen aynı evrak katalogda TEK kayıttır.
   • Başka evrakın ekinde tekrar gelen aynı belge indirilince içerik özetiyle tanınır ve ikinci kez
     diske yazılmaz ("Mükerrer"). Adı benzersiz dosya adı olan ekler indirmeden önce elenir.
   • İndirme durumu listesinde "Mükerrer"i kırmızı yaparak bunları gizleyin.
   • Klasörden dosya silerseniz program açılışta bunu fark eder ve o evrakları "İndirilmedi"ye alır.

5) GÖRÜNTÜLEYİCİ ve ÖNBELLEK
   • Bir evraka çift tıklayın: indirilmişse PDF'i (yoksa kendisi) açılır. İndirilmemişse UYAP'tan hemen
     önbelleğe alınır, PDF'e çevrilir ve açılır; "Durum" sütununda "önbellekte" yazar. Sonra indirilirse
     yeniden çekilmez, önbellekten taşınır.
   • Alttaki ayrıntı panelinde seçili evrakın bilgileri ve ekleri görünür; ekine çift tıklayarak açabilirsiniz.

6) PDF DÖNÜŞÜMÜ (otomatik)
   • .udf → Havelsan UYAP Editör motoruyla PDF (yazı tipleri gömülü, Türkçe karakterler korunur).
     Her dosya grubunun indirmesi bitince arka planda yapılır; indirmeyi bekletmez.
   • .tif/.tiff (çok sayfalı) → A4 PDF (yatay sayfalar yatay A4).  .jpg/.png → A4 PDF.
   • .docx/.doc/.rtf/.odt → Word (yoksa LibreOffice) ile PDF.
   • PDF her zaman kaynağın yanına AYNI ADLA yazılır; var olanın üzerine yazılmaz.
   • Windows'ta dosyalara sağ tık > "PDF'e dönüştür (UYAP)" (Araçlar menüsünden kurulur). Windows 11'de
     "Daha fazla seçenek göster" altındadır; çoklu seçimde tek pencerede sırayla dönüştürür.
     Ayrıca sağ tık > Gönder > "PDF'e dönüştür (UYAP)".

7) GÜNLÜKLER (LOG)
   • Ekrandaki günlüğün yanında, bağlantı/oturum/deneme ayrıntılarının tamamı loglar/katalog.log dosyasına
     sürekli yazılır (5 MB'ta yeni dosyaya geçer, son 10 dosya tutulur).
   • Yardım > "Günlükleri paketle" Masaüstüne zip oluşturur; destek için bu dosyayı gönderebilirsiniz.
     (PIN ve şifre hiçbir günlüğe yazılmaz.)

8) DİĞER ARAÇLAR (Araçlar menüsü)
   İşlemlerim indirme, duruşma takvimi (.ics), tebligat ve süre analizi, evrak zenginleştirme,
   toplu PDF dönüştürme, UYAP tarayıcısını görünür açma, sağ tık menüsünü kurma/kaldırma.

9) KISAYOLLAR
   Ctrl+F: taraf aramasına git · F5: sonuçları yenile · Ctrl+B / ☰: filtre panelini gizle/göster
   Enter / çift tık: seçili evrakı aç · Ctrl+O: klasörde göster · Ctrl+D: seçilileri indir
"""


def kilavuz_penceresi(root: tk.Tk):
    w = tk.Toplevel(root)
    w.title(f"{UYGULAMA_ADI} — Kullanım kılavuzu")
    w.geometry("860x640")
    txt = tk.Text(w, wrap="word", padx=14, pady=10, font=("Segoe UI", 10))
    sb = ttk.Scrollbar(w, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    txt.pack(fill="both", expand=True)
    txt.insert("1.0", KILAVUZ.format(imza=IMZA))
    txt.configure(state="disabled")


def hakkinda(root: tk.Tk):
    from tkinter import messagebox
    messagebox.showinfo(
        "Hakkında",
        f"{UYGULAMA_ADI} {SURUM}\n\nUYAP Avukat Portal için evrak kataloğu, filtreli toplu indirme, "
        f"görüntüleyici ve PDF dönüştürücü.\n\nGeliştiren: Av. Can KIZILYAR\n{IMZA}\n\n"
        "Bu yazılım UYAP'ın resmi bir ürünü değildir. UDF dönüştürme için Havelsan UYAP Editör "
        "kütüphaneleri kullanıcının kendi kurulumundan kullanılır.", parent=root)


# ---------------------------------------------------------------------------
# Araç komutları
# ---------------------------------------------------------------------------
def konsol_exe() -> str:
    """Paketlenmiş uygulamada konsol araçları için ayrı (konsollu) çalıştırılabilir dosya."""
    exe = Path(sys.executable)
    k = exe.with_name("UYAPEvrakKonsol" + exe.suffix)
    return str(k if k.exists() else exe)


def _uygulama_komutu(*args) -> list[str]:
    if getattr(sys, "frozen", False):
        return [konsol_exe(), *args]
    return [sys.executable, str(Path(__file__).resolve().parent / "uyap_indirici.py"), *args]


def konsolda_calistir(args: list[str], cwd: Path | None = None):
    """Etkileşimli komut satırı araçlarını ayrı bir konsol penceresinde başlatır."""
    cmd = args
    if os.name == "nt":
        subprocess.Popen(cmd, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        import shlex
        script = " ".join(shlex.quote(c) for c in cmd)
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{script}"'])
    else:
        for term in (["x-terminal-emulator", "-e"], ["gnome-terminal", "--"], ["konsole", "-e"], ["xterm", "-e"]):
            try:
                subprocess.Popen(term + cmd, cwd=cwd)
                return
            except OSError:
                continue
        subprocess.Popen(cmd, cwd=cwd)


def arac_komutlari() -> dict:
    py = sys.executable
    here = Path(__file__).resolve().parent

    def script(name, *a):
        if getattr(sys, "frozen", False):
            return [konsol_exe(), f"--{name}", *a]
        return [py, str(here / f"{name}.py"), *a]
    return {
        "islemlerim_1yil": _uygulama_komutu("--cli", "--mode", "islemlerim"),
        "durusma_takvimi": _uygulama_komutu("--cli", "--mode", "durusmalar"),
        "tebligat": script("tebligat_yoneticisi"),
        "zenginlestir": script("enrich_and_rename_documents"),
        "tarayici": _uygulama_komutu("--browser-only"),
    }


def islemlerim_tarih(start: str, end: str) -> list[str]:
    return _uygulama_komutu("--cli", "--mode", "islemlerim", "--start-date", start, "--end-date", end)


def gunlukleri_paketle(log_dirs: list[Path], extra_files: list[Path]) -> Path:
    masaustu = Path.home() / "Desktop"
    if not masaustu.exists():
        masaustu = Path.home()
    out = masaustu / f"uyap_gunlukler_{dt.datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for d in log_dirs:
            if d.exists():
                for f in d.glob("*"):
                    if f.is_file():
                        z.write(f, f"loglar/{f.name}")
        for f in extra_files:
            if f.exists() and f.is_file():
                z.write(f, f.name)
        z.writestr("BILGI.txt", f"{UYGULAMA_ADI} {SURUM}\n{dt.datetime.now()}\nPython {sys.version}\n{sys.platform}\n")
    return out


def dosya_ac(path: str):
    if os.name == "nt":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def klasorde_goster(path: str):
    p = Path(path)
    if os.name == "nt" and p.exists() and p.is_file():
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        dosya_ac(str(p.parent if p.is_file() else p))
