"""
RapidBenthos Desktop UI
Interface graphique pour le pipeline RapidBenthos
Thème clair professionnel — identité visuelle CREOCEAN
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import threading
import os
import sys
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageTk

# ─── PALETTE — Thème clair professionnel (identité CREOCEAN) ──────────────────
BG         = "#f4f6f9"   # fond général (gris très clair)
BG2        = "#ffffff"   # panneaux / cartes
BG3        = "#eef1f6"   # champs de saisie / zones secondaires
HEADER_BG  = "#ffffff"   # header
ACCENT     = "#2f5d8a"   # bleu CREOCEAN (logo)
ACCENT2    = "#6b5b95"   # mauve/violet (logo)
ACCENT3    = "#a4607a"   # rosé secondaire (logo)
TEXT       = "#1c2230"   # texte principal (presque noir)
TEXT_DIM   = "#6b7280"   # texte secondaire
BORDER     = "#d7dce4"
SUCCESS    = "#1f9d55"
WARNING    = "#b8860b"
ERROR      = "#c0392b"
CONSOLE_BG = "#1c2230"   # la console reste sombre (lisibilité logs type terminal)
CONSOLE_FG = "#d7e3f0"
FONT_MAIN  = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI Semibold", 11)
FONT_HEAD  = ("Segoe UI Bold", 13)
FONT_MONO  = ("Consolas", 9)

# ─── CHEMINS ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "rb_config.json")
LOGO_PATH   = os.path.join(BASE_DIR, "creo.png")   # logo header (avec texte)
ICON_PATH   = os.path.join(BASE_DIR, "rapidbenthos_icon.ico")   # icône fenêtre/taskbar

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ─── WIDGETS UTILITAIRES ──────────────────────────────────────────────────────

class FileRow(tk.Frame):
    """Ligne : label + entry + bouton parcourir"""
    def __init__(self, parent, label, mode="file", exts=None, config_key=None, cfg=None, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        self.mode       = mode
        self.exts       = exts or []
        self.config_key = config_key
        self.cfg        = cfg or {}

        tk.Label(self, text=label, bg=BG2, fg=TEXT_DIM, font=FONT_MAIN,
                 width=28, anchor="w").pack(side="left", padx=(0, 8))

        self.var = tk.StringVar(value=self.cfg.get(config_key, "") if config_key else "")
        entry = tk.Entry(self, textvariable=self.var, bg=BG3, fg=TEXT,
                         insertbackground=ACCENT, relief="flat",
                         font=FONT_MAIN, bd=0, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT)
        entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))

        btn = tk.Button(self, text="…", bg=BG3, fg=ACCENT, font=("Segoe UI", 10, "bold"),
                        relief="flat", cursor="hand2", width=3,
                        activebackground=ACCENT, activeforeground="#ffffff",
                        command=self._browse)
        btn.pack(side="left")

    def _browse(self):
        if self.mode == "file":
            ftypes = [("Tous les fichiers", "*.*")]
            if self.exts:
                ftypes = [(f"Fichiers {e}", f"*{e}") for e in self.exts] + ftypes
            path = filedialog.askopenfilename(filetypes=ftypes)
        elif self.mode == "files":
            ftypes = [("Tous les fichiers", "*.*")]
            if self.exts:
                ftypes = [(f"Fichiers {e}", f"*{e}") for e in self.exts] + ftypes
            path = filedialog.askopenfilenames(filetypes=ftypes)
            path = ";".join(path) if path else ""
        else:
            path = filedialog.askdirectory()
        if path:
            self.var.set(path)

    def get(self):
        return self.var.get().strip()

    def set(self, v):
        self.var.set(v)


class ParamRow(tk.Frame):
    """Ligne : label + entry simple (valeur texte)"""
    def __init__(self, parent, label, default="", config_key=None, cfg=None, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        tk.Label(self, text=label, bg=BG2, fg=TEXT_DIM, font=FONT_MAIN,
                 width=28, anchor="w").pack(side="left", padx=(0, 8))
        self.var = tk.StringVar(value=cfg.get(config_key, default) if (cfg and config_key) else default)
        entry = tk.Entry(self, textvariable=self.var, bg=BG3, fg=TEXT,
                         insertbackground=ACCENT, relief="flat",
                         font=FONT_MAIN, bd=0, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT)
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.config_key = config_key

    def get(self):
        return self.var.get().strip()

    def set(self, v):
        self.var.set(v)


class SectionLabel(tk.Frame):
    """Titre de section avec petite barre verticale colorée (look pro / dashboard)"""
    def __init__(self, parent, text, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        bar = tk.Frame(self, bg=ACCENT, width=3)
        bar.pack(side="left", fill="y", padx=(0, 8))
        tk.Label(self, text=text, bg=BG2, fg=ACCENT,
                 font=FONT_TITLE, anchor="w").pack(side="left", pady=2)


class Divider(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BORDER, height=1, **kwargs)


class RunButton(tk.Button):
    def __init__(self, parent, text, command, **kwargs):
        super().__init__(parent, text=text, command=command,
                         bg=ACCENT, fg="#ffffff", font=("Segoe UI Bold", 10),
                         relief="flat", cursor="hand2", padx=22, pady=9,
                         activebackground=ACCENT2, activeforeground="#ffffff",
                         bd=0, **kwargs)
        self.bind("<Enter>", lambda e: self.config(bg=ACCENT2))
        self.bind("<Leave>", lambda e: self.config(bg=ACCENT))


class Console(tk.Frame):
    """Zone de logs avec barre de progression et bouton Stop (reste en thème sombre type terminal)"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CONSOLE_BG, **kwargs)
        self._proc = None

        header = tk.Frame(self, bg="#151a24", pady=6)
        header.pack(fill="x")
        tk.Label(header, text="  ▶  Console", bg="#151a24", fg="#9fb3c8",
                 font=FONT_TITLE).pack(side="left")

        # Bouton Effacer
        tk.Button(header, text="Effacer", bg="#151a24", fg="#9fb3c8",
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self.clear).pack(side="right", padx=8)

        # Bouton Stop
        self.stop_btn = tk.Button(
            header, text="⏹ Stop", bg="#151a24", fg=ERROR,
            font=("Segoe UI Semibold", 9), relief="flat", cursor="hand2",
            padx=8, state="disabled",
            activebackground=ERROR, activeforeground="#ffffff",
            command=self.stop
        )
        self.stop_btn.pack(side="right", padx=4)

        self.text = scrolledtext.ScrolledText(
            self, bg="#11151d", fg=CONSOLE_FG, font=FONT_MONO,
            relief="flat", bd=0, state="disabled",
            selectbackground=ACCENT2, wrap="word"
        )
        self.text.pack(fill="both", expand=True)

        self.text.tag_config("info",    foreground=CONSOLE_FG)
        self.text.tag_config("success", foreground="#4ade80")
        self.text.tag_config("warning", foreground="#fbbf24")
        self.text.tag_config("error",   foreground="#f87171")
        self.text.tag_config("accent",  foreground="#8aa6c9")
        self.text.tag_config("dim",     foreground="#5b6678")

        # Barre de progression
        self.progress_frame = tk.Frame(self, bg=CONSOLE_BG)
        self.progress_frame.pack(fill="x", pady=(4, 0))
        self.progress_label = tk.Label(self.progress_frame, text="", bg=CONSOLE_BG,
                                       fg="#5b6678", font=("Segoe UI", 9))
        self.progress_label.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(self.progress_frame, mode="indeterminate",
                                        length=200, style="Console.Horizontal.TProgressbar")
        self.progress.pack(side="right", padx=6, pady=2)

    def set_process(self, proc):
        """Enregistre le processus en cours et active le bouton Stop"""
        self._proc = proc
        self.stop_btn.config(state="normal", bg=ERROR, fg="#ffffff")

    def stop(self):
        """Arrête le processus en cours"""
        if self._proc and self._proc.poll() is None:
            try:
                if sys.platform == "win32":
                    self._proc.terminate()
                else:
                    import signal
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                try:
                    self._proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
            except Exception as e:
                self.log(f"Erreur lors de l'arrêt : {e}", "error")
            self.log("⏹ Traitement arrêté par l'utilisateur.", "warning")
            self.stop_progress()
        self._proc = None
        self.stop_btn.config(state="disabled", bg="#151a24", fg=ERROR)

    def log(self, msg, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.configure(state="normal")
        self.text.insert("end", f"[{ts}] ", "dim")
        self.text.insert("end", msg + "\n", tag)
        self.text.configure(state="disabled")
        self.text.see("end")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def start_progress(self, label="Traitement en cours…"):
        self.progress_label.config(text=label)
        self.progress.start(12)

    def stop_progress(self):
        self.progress.stop()
        self.progress_label.config(text="")


# ─── TABS ─────────────────────────────────────────────────────────────────────

def scrollable_frame(parent):
    """Retourne (outer_frame, inner_frame) avec scrollbar verticale"""
    outer = tk.Frame(parent, bg=BG2)
    canvas = tk.Canvas(outer, bg=BG2, highlightthickness=0, bd=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG2)
    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    canvas.bind_all("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
    return outer, inner


# ─── TAB 1 : Part 1 — Orthomosaïque ──────────────────────────────────────────

class Tab1(tk.Frame):
    """Part 1 — Orthomosaïque unique (SAM + Metashape intégré)"""
    def __init__(self, parent, console, cfg):
        super().__init__(parent, bg=BG2)
        self.console = console
        self.cfg     = cfg
        self._build()

    def _build(self):
        outer, f = scrollable_frame(self)
        outer.pack(fill="both", expand=True)
        pad = {"fill": "x", "padx": 16}
        pad_std = {**pad, "pady": 3}

        SectionLabel(f, "📥  Entrées").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.ortho = FileRow(f, "Orthomosaïque (.tif)", mode="file",
                             exts=[".tif", ".tiff"], config_key="ortho", cfg=self.cfg)
        self.ortho.pack(**pad_std)

        self.out_dir = FileRow(f, "Dossier de sortie", mode="dir",
                               config_key="out_dir", cfg=self.cfg)
        self.out_dir.pack(**pad_std)

        self.plot_id = ParamRow(f, "Identifiant du site (plot_id)",
                                default="SITE_01", config_key="plot_id", cfg=self.cfg)
        self.plot_id.pack(**pad_std)

        SectionLabel(f, "🤖  Modèle SAM").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.sam_ckpt = FileRow(f, "Checkpoint SAM (.pth)", mode="file",
                                exts=[".pth"], config_key="sam_ckpt", cfg=self.cfg)
        self.sam_ckpt.pack(**pad_std)

        self.sam_model = ParamRow(f, "Type de modèle", default="vit_h",
                                  config_key="sam_model", cfg=self.cfg)
        self.sam_model.pack(**pad_std)

        SectionLabel(f, "📐  Paramètres SAM").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.pts_fine = ParamRow(f, "Points/side — passe fine", default="64",
                                 config_key="pts_fine", cfg=self.cfg)
        self.pts_fine.pack(**pad_std)
        self.pts_large = ParamRow(f, "Points/side — passe large", default="32",
                                  config_key="pts_large", cfg=self.cfg)
        self.pts_large.pack(**pad_std)
        self.min_area = ParamRow(f, "Surface min. masque (px²)", default="1600",
                                 config_key="min_area", cfg=self.cfg)
        self.min_area.pack(**pad_std)
        self.hex_size = ParamRow(f, "Taille hexagonale (m)", default="0.05",
                                 config_key="hex_size", cfg=self.cfg)
        self.hex_size.pack(**pad_std)

        SectionLabel(f, "🗺️  Metashape").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.ms_project = FileRow(f, "Projet Metashape (.psx)", mode="file",
                                  exts=[".psx"], config_key="ms_project", cfg=self.cfg)
        self.ms_project.pack(**pad_std)
        self.ms_chunk = ParamRow(f, "Numéro de chunk", default="0",
                                 config_key="ms_chunk", cfg=self.cfg)
        self.ms_chunk.pack(**pad_std)
        self.ms_photos = FileRow(f, "Dossier des photos", mode="dir",
                                 config_key="ms_photos", cfg=self.cfg)
        self.ms_photos.pack(**pad_std)

        info = tk.Frame(f, bg=BG3, padx=12, pady=10)
        info.pack(**pad, pady=(10, 4))
        tk.Label(info,
                 text="ℹ️  L'étape Metashape (liaison UV) est exécutée automatiquement à la fin de Part 1 si un projet .psx est renseigné.",
                 bg=BG3, fg=TEXT_DIM, font=("Segoe UI", 9), wraplength=550, justify="left").pack()

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(fill="x", padx=16, pady=(20, 16))
        RunButton(btn_frame, "▶  Lancer Part 1", self._run).pack(side="left")
        tk.Button(btn_frame, text="💾 Sauver config", command=self._save,
                  bg=BG3, fg=TEXT_DIM, font=FONT_MAIN, relief="flat",
                  cursor="hand2", padx=14, pady=8, bd=0).pack(side="left", padx=10)

    def _save(self):
        self.cfg.update(self._collect())
        save_config(self.cfg)
        self.console.log("Configuration sauvegardée.", "success")

    def _collect(self):
        return {
            "ortho":      self.ortho.get(),
            "out_dir":    self.out_dir.get(),
            "plot_id":    self.plot_id.get(),
            "sam_ckpt":   self.sam_ckpt.get(),
            "sam_model":  self.sam_model.get(),
            "pts_fine":   self.pts_fine.get(),
            "pts_large":  self.pts_large.get(),
            "min_area":   self.min_area.get(),
            "hex_size":   self.hex_size.get(),
            "ms_project": self.ms_project.get(),
            "ms_chunk":   self.ms_chunk.get(),
            "ms_photos":  self.ms_photos.get(),
        }

    def _run(self):
        p = self._collect()
        errors = []
        if not p["ortho"] or not os.path.exists(p["ortho"]):
            errors.append("Orthomosaïque introuvable")
        if not p["out_dir"]:
            errors.append("Dossier de sortie requis")
        if not p["sam_ckpt"] or not os.path.exists(p["sam_ckpt"]):
            errors.append("Checkpoint SAM introuvable")
        if errors:
            messagebox.showerror("Champs manquants", "\n".join(errors))
            return
        self._save()
        self.console.log("=== Démarrage Part 1 ===", "accent")
        self.console.log(f"Site     : {p['plot_id']}", "info")
        self.console.log(f"Ortho    : {p['ortho']}", "info")
        self.console.log(f"Sortie   : {p['out_dir']}", "info")
        self.console.start_progress("Part 1 en cours…")
        script = _generate_part1_script(p)
        _run_script_async(script, self.console)


# ─── TAB 2 : Part 3 — Post-traitement ────────────────────────────────────────

class Tab2(tk.Frame):
    """Part 3 — Post-traitement & résultats"""
    def __init__(self, parent, console, cfg):
        super().__init__(parent, bg=BG2)
        self.console = console
        self.cfg     = cfg
        self._build()

    def _build(self):
        outer, f = scrollable_frame(self)
        outer.pack(fill="both", expand=True)
        pad = {"fill": "x", "padx": 16}
        pad_std = {**pad, "pady": 3}

        SectionLabel(f, "📥  Entrées Part 3").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.rb_csv = FileRow(f, "CSV centroïdes RB (hex_pts.csv)", mode="file",
                              exts=[".csv"], config_key="p3_rb_csv", cfg=self.cfg)
        self.rb_csv.pack(**pad_std)
        self.rc_csv = FileRow(f, "CSV ReefCloud (dense_inference)", mode="file",
                              exts=[".csv"], config_key="p3_rc_csv", cfg=self.cfg)
        self.rc_csv.pack(**pad_std)
        self.label_f = FileRow(f, "Fichier labels (.csv)", mode="file",
                               exts=[".csv"], config_key="p3_label", cfg=self.cfg)
        self.label_f.pack(**pad_std)
        self.poly_shp = FileRow(f, "Polygones segmentés (.shp)", mode="file",
                                exts=[".shp"], config_key="p3_poly", cfg=self.cfg)
        self.poly_shp.pack(**pad_std)

        SectionLabel(f, "📤  Sorties Part 3").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.out_seg = FileRow(f, "Segments classifiés (.shp)", mode="file",
                               exts=[".shp"], config_key="p3_out_seg", cfg=self.cfg)
        self.out_seg.pack(**pad_std)
        self.out_csv2 = FileRow(f, "Résultat classif. (.csv)", mode="file",
                                exts=[".csv"], config_key="p3_out_csv", cfg=self.cfg)
        self.out_csv2.pack(**pad_std)
        self.out_pct = FileRow(f, "Pourcentage couverture (.csv)", mode="file",
                               exts=[".csv"], config_key="p3_out_pct", cfg=self.cfg)
        self.out_pct.pack(**pad_std)
        self.out_fig2 = FileRow(f, "Graphique communauté (.png)", mode="file",
                                exts=[".png"], config_key="p3_out_fig", cfg=self.cfg)
        self.out_fig2.pack(**pad_std)
        self.out_col = FileRow(f, "Segments colonies (.shp)", mode="file",
                               exts=[".shp"], config_key="p3_out_col", cfg=self.cfg)
        self.out_col.pack(**pad_std)

        SectionLabel(f, "🔧  Ordre des classes").pack(**pad, pady=(14, 3))
        Divider(f).pack(**pad_std)

        self.class_order = ParamRow(f, "Ordre (séparé par virgules)",
            default="Acropora Corymbose (ACO),Acropora,Branching_non_acropora,Massive,Foliose,Encrusting,Columnar,Fire_Coral,Fungiidae,Soft_Coral,Sponge,Algae,Abiotic_substrate,Mobile_Biota,Markers,Unidentifiable",
            config_key="p3_class_order", cfg=self.cfg)
        self.class_order.pack(**pad_std)

        btn_frame = tk.Frame(f, bg=BG2)
        btn_frame.pack(fill="x", padx=16, pady=(20, 16))
        RunButton(btn_frame, "▶  Lancer Part 3", self._run).pack(side="left")
        tk.Button(btn_frame, text="💾 Sauver config", command=self._save,
                  bg=BG3, fg=TEXT_DIM, font=FONT_MAIN, relief="flat",
                  cursor="hand2", padx=14, pady=8, bd=0).pack(side="left", padx=10)

    def _save(self):
        self.cfg.update(self._collect())
        save_config(self.cfg)
        self.console.log("Configuration sauvegardée.", "success")

    def _collect(self):
        return {
            "p3_rb_csv":      self.rb_csv.get(),
            "p3_rc_csv":      self.rc_csv.get(),
            "p3_label":       self.label_f.get(),
            "p3_poly":        self.poly_shp.get(),
            "p3_out_seg":     self.out_seg.get(),
            "p3_out_csv":     self.out_csv2.get(),
            "p3_out_pct":     self.out_pct.get(),
            "p3_out_fig":     self.out_fig2.get(),
            "p3_out_col":     self.out_col.get(),
            "p3_class_order": self.class_order.get(),
        }

    def _run(self):
        p = self._collect()
        errors = []
        for k, label in [("p3_rb_csv", "CSV centroïdes"), ("p3_rc_csv", "CSV ReefCloud"),
                         ("p3_label", "Labels"), ("p3_poly", "Polygones")]:
            if not p[k] or not os.path.exists(p[k]):
                errors.append(f"{label} introuvable")
        for k, label in [("p3_out_seg", "Shp sortie"), ("p3_out_csv", "CSV sortie"),
                         ("p3_out_pct", "Percent Cover"), ("p3_out_fig", "Figure"),
                         ("p3_out_col", "Colonies")]:
            if not p[k]:
                errors.append(f"Chemin de sortie requis : {label}")
        if errors:
            messagebox.showerror("Champs manquants", "\n".join(errors))
            return
        self._save()
        self.console.log("=== Démarrage Part 3 ===", "accent")
        self.console.start_progress("Post-traitement…")
        script = _generate_part3_script(p)
        _run_script_async(script, self.console)


# ─── GÉNÉRATEURS DE SCRIPTS ───────────────────────────────────────────────────

def _generate_part1_script(p):
    return f'''
import os, sys, torch

# ── Patch DLLs Windows ──
_dll = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
if hasattr(os, 'add_dll_directory') and os.path.exists(_dll):
    os.add_dll_directory(_dll)
os.environ['PATH'] = _dll + ';' + os.environ.get('PATH', '')
os.environ['GDAL_DATA'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'gdal')
os.environ['PROJ_LIB']  = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'proj')
for _p in [
    os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'torch', 'lib'),
    os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'torch', 'bin'),
    os.path.join(os.path.dirname(sys.executable), 'Library', 'bin'),
]:
    if os.path.exists(_p) and hasattr(os, 'add_dll_directory'):
        os.add_dll_directory(_p)

# ── Détection automatique GPU ──
if torch.cuda.is_available():
    device = "cuda:0"
    print(f"GPU détecté : {{torch.cuda.get_device_name(0)}}")
    print(f"VRAM       : {{round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)}} Go")
else:
    device = "cpu"
    print("Aucun GPU CUDA disponible — utilisation du CPU")

# ── Metashape (optionnel) ──
try:
    import Metashape
    METASHAPE_OK = True
    print(f"Metashape OK : {{Metashape.app.version}}")
except Exception as _e:
    METASHAPE_OK = False
    print(f"Metashape non disponible : {{_e}}")

from samgeo import SamGeo
import geopandas as gpd
from osgeo import gdal
from datetime import datetime
from RB_fcn_part1 import Filter_segments, hexagrid
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

ortho      = r"{p["ortho"]}"
out_folder = r"{p["out_dir"]}"
plot_id    = "{p["plot_id"]}"
os.makedirs(out_folder, exist_ok=True)
ts = datetime.now().strftime('%Y-%m-%d')

print("=" * 50)
print(f"Site    : {{plot_id}}")
print(f"Ortho   : {{ortho}}")
print(f"Outputs : {{out_folder}}")
print("=" * 50)

sam_kwargs_base = dict(
    points_per_batch=128,
    pred_iou_thresh=0.88,
    stability_score_thresh=0.94,
    stability_score_offset=1.0,
    box_nms_thresh=0.35,
    crop_n_layers=0,
    crop_nms_thresh=0.9,
    crop_n_points_downscale_factor=1,
    min_mask_region_area={p["min_area"]},
)

# ── ÉTAPE 1 — SAM passe fine ──
print("\\n ÉTAPE 1/6 — SAM passe fine (points_per_side={p["pts_fine"]})...")
sam = SamGeo(
    model_type="{p["sam_model"]}",
    checkpoint=r"{p["sam_ckpt"]}",
    device=device,
    sam_kwargs=dict(sam_kwargs_base, points_per_side={p["pts_fine"]})
)
mask_1 = os.path.join(out_folder, f'{{plot_id}}{{ts}}_mask1.tif')
sam.generate(ortho, mask_1, batch=True, foreground=False,
             mask_multiplier=255, erosion_kernel=(3, 3), bound=100)
print(f"✅ Passe fine terminée → {{mask_1}}")

# ── ÉTAPE 2 — SAM passe large ──
print("\\n ÉTAPE 2/6 — SAM passe large (points_per_side={p["pts_large"]})...")
sam = SamGeo(
    model_type="{p["sam_model"]}",
    checkpoint=r"{p["sam_ckpt"]}",
    device=device,
    sam_kwargs=dict(sam_kwargs_base, points_per_side={p["pts_large"]})
)
mask_2 = os.path.join(out_folder, f'{{plot_id}}{{ts}}_mask2.tif')
sam.generate(ortho, mask_2, batch=True, foreground=False,
             mask_multiplier=255, erosion_kernel=(3, 3), bound=200)
print(f"✅ Passe large terminée → {{mask_2}}")

# ── ÉTAPE 3 — Fusion GDAL ──
print("\\n ÉTAPE 3/6 — Fusion des deux masques...")
combined = os.path.join(out_folder, f'{{plot_id}}{{ts}}_combined.tif')
gdal_utils = os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'osgeo_utils')
os.system(f'python {{os.path.join(gdal_utils,"gdal_calc.py")}} -A {{mask_1}} -B {{mask_2}} --outfile={{combined}} --calc="A*B" --type=Float32 --hideNoData')
print(f"✅ Fusion terminée → {{combined}}")

# ── ÉTAPE 4 — Vectorisation ──
print("\\n ÉTAPE 4/6 — Vectorisation en polygones...")
combined_gpkg = os.path.join(out_folder, f'{{plot_id}}{{ts}}_combined.gpkg')
sam.tiff_to_gpkg(combined, combined_gpkg, simplify_tolerance=None)
print(f"✅ Vectorisation terminée → {{combined_gpkg}}")

# ── ÉTAPE 5 — Filtrage ──
print("\\n ÉTAPE 5/6 — Filtrage segments...")
SEG_shp = os.path.join(out_folder, f'{{plot_id}}{{ts}}_SEG.shp')
PTS_shp = os.path.join(out_folder, f'{{plot_id}}{{ts}}_PTS.shp')
PTS_csv = os.path.join(out_folder, f'{{plot_id}}{{ts}}_PTS.csv')
Filter_segments(combined_gpkg, SEG_shp, PTS_shp, PTS_csv)
print("✅ Filtrage terminé")

# ── ÉTAPE 6 — Hexagrid ──
print("\\n ÉTAPE 6/6 — Grille hexagonale...")
hexagrid_csv = os.path.join(out_folder, f'{{plot_id}}{{ts}}_hex_pts.csv')
hexagrid(ortho, {p["hex_size"]},
    os.path.join(out_folder, f'{{plot_id}}{{ts}}_grid_full.shp'), SEG_shp,
    os.path.join(out_folder, f'{{plot_id}}{{ts}}_grid_clip.shp'),
    os.path.join(out_folder, f'{{plot_id}}{{ts}}_hex_seg.shp'),
    os.path.join(out_folder, f'{{plot_id}}{{ts}}_hex_pts.shp'),
    hexagrid_csv)
print("✅ Hexagrid terminé")

# ── ÉTAPE 7 — Metashape (si disponible et configuré) ──
ms_project = r"{p["ms_project"]}"
ms_photos  = r"{p["ms_photos"]}"
ms_chunk   = {p["ms_chunk"]}

if METASHAPE_OK and ms_project and os.path.exists(ms_project):
    print("\\n ÉTAPE 7/7 — Liaison Metashape (UV projection)...")
    try:
        from RB_fcn_part1 import camera_point_from_segment_centerPoint
        OutputPath = os.path.join(out_folder, plot_id + '_{{ts}}_camera_UV.csv')
        camera_point_from_segment_centerPoint(
            ms_project, ms_chunk, ms_photos, OutputPath, hexagrid_csv)
        print(f"✅ Metashape terminé → {{OutputPath}}")
    except Exception as _e:
        print(f"⚠️ Erreur Metashape : {{_e}}")
elif ms_project and not os.path.exists(ms_project):
    print("\\n⚠️ Projet Metashape introuvable — étape 7 ignorée")
else:
    print("\\n⚠️ Étape 7 ignorée (Metashape non configuré ou non disponible)")

# ── RÉSUMÉ ──
print("\\n" + "=" * 50)
print("🎉 RAPIDBENTHOS PART 1 TERMINÉ !")
print("=" * 50)
gdf = gpd.read_file(SEG_shp)
print(f"\\n📊 Polygones détectés  : {{len(gdf)}}")
print(f"   Surface moyenne     : {{gdf.geometry.area.mean():.4f}} m²")
print(f"   Hexagrid CSV        : {{hexagrid_csv}}")
print(f"\\n💡 Ouvre {{combined_gpkg}} dans QGIS !")
print("DONE")
'''


def _generate_part3_script(p):
    class_order = [c.strip() for c in p["p3_class_order"].split(",")]
    return f'''
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from RB_fcn_part3 import Select_class_ReefCloud_pts, format_percent_cover, stack_catplot, ColonyLevel_Segments
import matplotlib.pyplot as plt

RB_centroid_csv         = r"{p["p3_rb_csv"]}"
RC_csv                  = r"{p["p3_rc_csv"]}"
label_file              = r"{p["p3_label"]}"
polygon_file            = r"{p["p3_poly"]}"
label_polygon_seg       = r"{p["p3_out_seg"]}"
label_poygon_csv        = r"{p["p3_out_csv"]}"
PercentCover            = r"{p["p3_out_pct"]}"
out_fig                 = r"{p["p3_out_fig"]}"
ColonyLevelSegments_shp = r"{p["p3_out_col"]}"

if __name__ == '__main__':
    print("ÉTAPE 1 — Classification segments...")
    gdf = Select_class_ReefCloud_pts(RB_centroid_csv, RC_csv, label_file,
                                     polygon_file, label_polygon_seg, label_poygon_csv)
    print(f"  {{len(gdf)}} segments classifiés")

    print("ÉTAPE 2 — Calcul percent cover...")
    df_morpho, palette = format_percent_cover(label_polygon_seg, label_file)
    df_morpho.to_csv(PercentCover)
    df_morpho['Morphology'] = df_morpho['Morphology'].replace({{'Columnar (CAAB 11 290915)': 'Columnar'}})

    print("ÉTAPE 3 — Graphique composition...")
    Class_order = {class_order}
    plt.figure(figsize=(6, 3), dpi=600)
    stack_catplot(x='Morphology', y='Percent_cover', cat='treatment', stack='label_set',
                  data=df_morpho, palette=palette, out_fig=out_fig, order=Class_order)

    print("ÉTAPE 4 — Segments colonie...")
    ColonyLevel_Segments(label_polygon_seg, ColonyLevelSegments_shp)

    print("DONE Part 3 !")
    print(f"  Segments : {{label_polygon_seg}}")
    print(f"  Cover    : {{PercentCover}}")
    print(f"  Figure   : {{out_fig}}")
    print(f"  Colonies : {{ColonyLevelSegments_shp}}")
'''


# ─── EXÉCUTION ASYNC ──────────────────────────────────────────────────────────

def _run_script_async(script_code, console):
    """Écrit le script dans un fichier tmp puis l'exécute dans un thread"""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False,
                                     mode="w", encoding="utf-8",
                                     dir=BASE_DIR)
    tmp.write(script_code)
    tmp.close()

    def _worker():
        try:
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True

            proc = subprocess.Popen(
                [sys.executable, tmp.name],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=BASE_DIR,
                **kwargs
            )
            console.set_process(proc)

            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                if proc.poll() is not None and proc.returncode not in (0, None):
                    break
                tag = "info"
                low = line.lower()
                if any(k in low for k in ["done", "ok", "terminé", "terminee", "succès", "🎉"]):
                    tag = "success"
                elif any(k in low for k in ["erreur", "error", "fail"]):
                    tag = "error"
                elif any(k in low for k in ["skip", "ignore", "warning", "⚠"]):
                    tag = "warning"
                elif line.startswith("===") or "étape" in low or "step" in low:
                    tag = "accent"
                console.log(line, tag)

            proc.wait()
            if proc.returncode == 0:
                console.log("✅ Traitement terminé avec succès.", "success")
            elif proc.returncode in (1, -1, -15, -9):
                pass  # Arrêt volontaire — déjà loggé par console.stop()
            else:
                console.log(f"⚠ Code de retour : {proc.returncode}", "error")

        except Exception as e:
            console.log(f"Erreur d'exécution : {e}", "error")
        finally:
            console.stop_progress()
            console.stop_btn.config(state="disabled", bg="#151a24", fg=ERROR)
            console._proc = None
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


# ─── FENÊTRE PRINCIPALE ───────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RapidBenthos — Interface de traitement | CREOCEAN")
        self.configure(bg=BG)
        self.geometry("1040x800")
        self.minsize(900, 640)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._set_window_icon()
        self._style()
        self.cfg = load_config()
        self._build()

    def _set_window_icon(self):
        try:
            if sys.platform == "win32" and os.path.exists(ICON_PATH):
                self.iconbitmap(ICON_PATH)
        except Exception as e:
            print(f"Icône non chargée : {e}")

    def _on_close(self):
        if hasattr(self, 'console') and self.console._proc and self.console._proc.poll() is None:
            if messagebox.askyesno("Traitement en cours",
                                   "Un traitement est en cours.\nVoulez-vous l'arrêter et quitter ?"):
                self.console.stop()
                self.destroy()
        else:
            self.destroy()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook",     background=BG,  borderwidth=0)
        style.configure("TNotebook.Tab", background=BG,  foreground=TEXT_DIM,
                         font=FONT_TITLE, padding=[18, 10], borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG2), ("active", BG3)],
                  foreground=[("selected", ACCENT), ("active", TEXT)])
        style.configure("TScrollbar", background=BG3, troughcolor=BG,
                         bordercolor=BG, arrowcolor=TEXT_DIM)
        style.configure("Horizontal.TProgressbar",
                         troughcolor=BG3, background=ACCENT,
                         bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT2)
        style.configure("Console.Horizontal.TProgressbar",
                         troughcolor="#151a24", background=ACCENT,
                         bordercolor="#151a24", lightcolor=ACCENT, darkcolor=ACCENT2)

    def _build(self):
        # ── Header ──
        header = tk.Frame(self, bg=HEADER_BG, pady=0)
        header.pack(fill="x")

        # Bandeau dégradé fin bleu→mauve en haut (simulé par segments de couleur, look pro)
        band = tk.Frame(header, bg=BG, height=4)
        band.pack(fill="x")
        seg_colors = [ACCENT, "#4d6f9b", "#5a6aa0", ACCENT2, ACCENT3]
        for c in seg_colors:
            tk.Frame(band, bg=c).pack(side="left", fill="both", expand=True)

        title_frame = tk.Frame(header, bg=HEADER_BG, pady=14, padx=24)
        title_frame.pack(fill="x")

        # ── Logo CREOCEAN (à droite du header, visible sur fond clair) ──
        self.logo_tk = None
        self.console_warn_logo = False
        try:
            if os.path.exists(LOGO_PATH):
                logo_img = Image.open(LOGO_PATH).convert("RGBA")
                logo_img.thumbnail((170, 60), Image.LANCZOS)
                self.logo_tk = ImageTk.PhotoImage(logo_img)
                tk.Label(title_frame, image=self.logo_tk, bg=HEADER_BG).pack(side="right", padx=(0, 4))
            else:
                self.console_warn_logo = True
        except Exception as e:
            print(f"Logo non chargé ({LOGO_PATH}) : {e}")

        title_text = tk.Frame(title_frame, bg=HEADER_BG)
        title_text.pack(side="left")
        tk.Label(title_text, text="RapidBenthos", bg=HEADER_BG, fg=TEXT,
                 font=("Segoe UI Bold", 22)).pack(side="left")
        badge = tk.Label(title_text, text=" v2.2 ", bg=ACCENT, fg="#ffffff",
                 font=("Segoe UI Bold", 8), padx=2, pady=1)
        badge.pack(side="left", padx=(10, 0), pady=(6, 0))
        sub = tk.Label(header, text="Pipeline de traitement benthique — analyse automatisée d'orthomosaïques coralliennes",
                 bg=HEADER_BG, fg=TEXT_DIM, font=("Segoe UI", 11))
        sub.pack(anchor="w", padx=24, pady=(0, 14))

        Divider(self).pack(fill="x")

        # ── PanedWindow ──
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                              sashwidth=4, sashrelief="flat", sashpad=0, handlesize=0)
        pane.pack(fill="both", expand=True)

        nb_frame = tk.Frame(pane, bg=BG2)
        pane.add(nb_frame, width=580, minsize=420)

        self.nb = ttk.Notebook(nb_frame)
        self.nb.pack(fill="both", expand=True)

        console_frame = tk.Frame(pane, bg=CONSOLE_BG)
        pane.add(console_frame, width=420, minsize=320)

        self.console = Console(console_frame)
        self.console.pack(fill="both", expand=True)

        # ── 2 onglets uniquement ──
        self.tab1 = Tab1(self.nb, self.console, self.cfg)
        self.tab2 = Tab2(self.nb, self.console, self.cfg)

        self.nb.add(self.tab1, text="  Part 1 — Orthomosaïque  ")
        self.nb.add(self.tab2, text="  Part 3 — Résultats  ")

        # ── Status bar ──
        status = tk.Frame(self, bg=BG2, pady=6)
        status.pack(fill="x", side="bottom")
        Divider(status).pack(fill="x", side="top")
        tk.Label(status, text="  RapidBenthos Desktop UI  —  CREOCEAN · Environnement & océanographie",
                 bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="left", pady=(4,0))
        tk.Label(status, text="Python " + sys.version.split()[0] + "  ",
                 bg=BG2, fg=TEXT_DIM, font=("Segoe UI", 8)).pack(side="right", pady=(4,0))

        # ── Welcome ──
        self.console.log("Bienvenue dans RapidBenthos Desktop UI  v2.2", "accent")
        self.console.log("Part 1 : SAM + Metashape (étape 7) intégrés en un seul lancement.", "info")
        self.console.log("GPU détecté automatiquement — aucune sélection manuelle requise.", "info")
        self.console.log("Utilisez ⏹ Stop pour interrompre à tout moment.", "dim")
        if self.console_warn_logo:
            self.console.log(f"⚠️ Logo introuvable : {LOGO_PATH} (placez creo.png à côté du script)", "warning")


if __name__ == "__main__":
    app = App()
    app.mainloop()