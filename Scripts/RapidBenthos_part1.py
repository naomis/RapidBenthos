"""
RapidBenthos — Part 1 : Segmentation SAM + Hexagrid
====================================================
Workflow :
  1. SAM passe fine  (128×128 points/side)
  2. SAM passe large (200×200 points/side)
  3. Fusion GDAL     (masque1 × masque2)
  4. Vectorisation   (.tif → .gpkg)
  5. Filtrage + Hexagrid
  6. Liaison Metashape (optionnel)

Config : /app/config.yaml  (chemin interne container)
Entrées : montées via volumes Docker (voir docker-compose.yml)
"""

# ================================================================
# SETUP ENVIRONNEMENT
# ================================================================
import os
import sys
import tqdm
# CUDA
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
# Monkey-patch : force tqdm à écrire sur stderr avec TTY simulé
_original_init = tqdm.tqdm.__init__

def _patched_init(self, *args, **kwargs):
    kwargs.setdefault('file', sys.stderr)
    kwargs.setdefault('dynamic_ncols', True)
    # Force l'affichage même si isatty() = False
    if not sys.stderr.isatty():
        kwargs.setdefault('ncols', 100)
    _original_init(self, *args, **kwargs)

tqdm.tqdm.__init__ = _patched_init
# ================================================================
# IMPORTS
# ================================================================
import torch
import yaml
import numpy as np
import cv2
from datetime import datetime
from osgeo import gdal
import geopandas as gpd
import pandas as pd
from samgeo import SamGeo
from PIL import Image, ImageFile

Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Import des fonctions RapidBenthos
sys.path.insert(0, os.path.dirname(__file__))
from RB_fcn_part1 import Filter_segments, hexagrid

try:
    import Metashape
    METASHAPE_OK = True
    print(f"✅ Metashape OK : {Metashape.app.version}")
except Exception as e:
    METASHAPE_OK = False
    print(f"⚠️  Metashape non disponible : {e}")

# ================================================================
# VÉRIFICATION GPU
# ================================================================
print(f"\n🎮 GPU       : {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   Device    : {torch.cuda.get_device_name(0)}")
    print(f"   VRAM      : {round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)} Go")

# ================================================================
# LECTURE CONFIG
# ================================================================
config_path = os.environ.get("CONFIG_PATH", "/app/config.yaml")
with open(config_path, "r") as f:
    cfg = yaml.safe_load(f)

ortho      = cfg["site"]["ortho"]
out_folder = cfg["site"]["out_folder"]
plot_id    = cfg["site"]["plot_id"]

MetashapeProject_path = cfg["metashape"]["project_path"]
Chunk_number          = cfg["metashape"]["chunk_number"]
PhotoPath             = cfg["metashape"]["photo_path"]

checkpoint  = cfg["sam"]["checkpoint"]
model_type  = cfg["sam"]["model_type"]

os.makedirs(out_folder, exist_ok=True)

ts = datetime.now().strftime('%Y-%m-%d')

print(f"\n📋 Site      : {plot_id}")
print(f"   Ortho     : {ortho}")
print(f"   Output    : {out_folder}")
print(f"   SAM model : {model_type}")

# ================================================================
# ÉTAPE 1 — SAM passe fine (petits objets)
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 1/6 — SAM passe fine (128×128)...")
print("="*50)

sam = SamGeo(
    model_type=model_type,
    checkpoint=checkpoint,
    device='cuda:0',
    sam_kwargs={
        'points_per_side': 128,
        'points_per_batch': 16,
        'pred_iou_thresh': 0.88,
        'stability_score_thresh': 0.94,
        'stability_score_offset': 1.0,
        'box_nms_thresh': 0.35,
        'crop_n_layers': 0,
        'crop_nms_thresh': 0.9,
        'crop_n_points_downscale_factor': 1,
        'min_mask_region_area': 1600,
    }
)

mask_1 = os.path.join(out_folder, f'{plot_id}_{ts}_mask1.tif')
sam.generate(
    ortho, mask_1,
    batch=True,
    foreground=False,
    mask_multiplier=255,
    erosion_kernel=(3, 3),
    bound=100
)
print(f"✅ Passe fine terminée → {mask_1}")

# ================================================================
# ÉTAPE 2 — SAM passe large (grands objets)
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 2/6 — SAM passe large (200×200)...")
print("="*50)

sam = SamGeo(
    model_type=model_type,
    checkpoint=checkpoint,
    device='cuda:0',
    sam_kwargs={
        'points_per_side': 200,
        'points_per_batch': 8,
        'pred_iou_thresh': 0.88,
        'stability_score_thresh': 0.94,
        'stability_score_offset': 1.0,
        'box_nms_thresh': 0.35,
        'crop_n_layers': 0,
        'crop_nms_thresh': 0.9,
        'crop_n_points_downscale_factor': 1,
        'min_mask_region_area': 1600,
    }
)

mask_2 = os.path.join(out_folder, f'{plot_id}_{ts}_mask2.tif')
sam.generate(
    ortho, mask_2,
    batch=True,
    foreground=False,
    mask_multiplier=255,
    erosion_kernel=(3, 3),
    bound=200
)
print(f"✅ Passe large terminée → {mask_2}")

# ================================================================
# ÉTAPE 3 — Fusion GDAL (masque1 × masque2)
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 3/6 — Fusion des deux masques...")
print("="*50)

Combined_seg_tif = os.path.join(out_folder, f'{plot_id}_{ts}_combined.tif')

# ⚠️ gdal_calc.py : chemin auto-détecté (Linux/Docker)
#    Pas de chemin Windows hardcodé ici !
import shutil
gdal_calc_bin = shutil.which("gdal_calc.py")
if gdal_calc_bin is None:
    # Fallback : chercher dans les osgeo_utils du Python courant
    import glob
    candidates = glob.glob(
        os.path.join(os.path.dirname(sys.executable),
                     "**", "gdal_calc.py"),
        recursive=True
    )
    if candidates:
        gdal_calc_bin = candidates[0]
    else:
        raise FileNotFoundError(
            "gdal_calc.py introuvable. "
            "Vérifier l'installation de python3-gdal ou gdal-bin."
        )

print(f"   gdal_calc.py : {gdal_calc_bin}")

gdal_calc_cmd = (
    f'python "{gdal_calc_bin}" '
    f'-A "{mask_1}" -B "{mask_2}" '
    f'--outfile="{Combined_seg_tif}" '
    f'--calc="A*B" --type=Float32 --hideNoData'
)
ret = os.system(gdal_calc_cmd)
if ret != 0:
    raise RuntimeError(f"gdal_calc.py a échoué (code {ret})")
print(f"✅ Fusion terminée → {Combined_seg_tif}")

# ================================================================
# ÉTAPE 4 — Vectorisation (raster → polygones)
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 4/6 — Vectorisation en polygones...")
print("="*50)

Combined_seg_gpkg = os.path.join(out_folder, f'{plot_id}_{ts}_combined.gpkg')
sam.tiff_to_gpkg(Combined_seg_tif, Combined_seg_gpkg, simplify_tolerance=None)
print(f"✅ Vectorisation terminée → {Combined_seg_gpkg}")

# ================================================================
# ÉTAPE 5 — Filtrage segments
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 5/6 — Filtrage segments...")
print("="*50)

SEG_shp = os.path.join(out_folder, f'{plot_id}_{ts}_SEG.shp')
PTS_shp = os.path.join(out_folder, f'{plot_id}_{ts}_PTS.shp')
PTS_csv = os.path.join(out_folder, f'{plot_id}_{ts}_PTS.csv')

segments_df_filtered, segments_pts_df = Filter_segments(
    Combined_seg_gpkg, SEG_shp, PTS_shp, PTS_csv
)
print("✅ Filtrage terminé")

# ================================================================
# ÉTAPE 6 — Grille hexagonale
# ================================================================
print("\n" + "="*50)
print("ÉTAPE 6/6 — Grille hexagonale...")
print("="*50)

full_grid    = os.path.join(out_folder, f'{plot_id}_{ts}_grid_full.shp')
clip_grid    = os.path.join(out_folder, f'{plot_id}_{ts}_grid_clip.shp')
hexagrid_seg = os.path.join(out_folder, f'{plot_id}_{ts}_hex_seg.shp')
hexagrid_pts = os.path.join(out_folder, f'{plot_id}_{ts}_hex_pts.shp')
hexagrid_csv = os.path.join(out_folder, f'{plot_id}_{ts}_hex_pts.csv')

hexagird_union_shp, hexagrid_union_pts = hexagrid(
    ortho, 0.05,
    full_grid, SEG_shp,
    clip_grid, hexagrid_seg,
    hexagrid_pts, hexagrid_csv
)
print("✅ Hexagrid terminé")

# ================================================================
# ÉTAPE 7 — Liaison Metashape (optionnelle)
# ================================================================
if METASHAPE_OK:
    print("\n" + "="*50)
    print("ÉTAPE 7/7 — Liaison Metashape...")
    print("="*50)
    try:
        from RB_fcn_part1 import camera_point_from_segment_centerPoint
        OutputPath = os.path.join(out_folder, plot_id + '_{}.csv')
        camera_uv = camera_point_from_segment_centerPoint(
            MetashapeProject_path,
            Chunk_number,
            PhotoPath,
            OutputPath,
            hexagrid_csv
        )
        print("✅ Metashape terminé")
    except Exception as e:
        print(f"⚠️  Erreur Metashape : {e}")
else:
    print("\n⚠️  ÉTAPE 7 ignorée — Metashape non disponible")
    print("   → Les résultats de segmentation sont complets !")

# ================================================================
# RÉSUMÉ FINAL
# ================================================================
gdf = gpd.read_file(SEG_shp)

print("\n" + "="*50)
print("🎉 RAPIDBENTHOS PART 1 TERMINÉ !")
print("="*50)
print(f"\n📁 Résultats dans : {out_folder}")
print(f"   🖼️  mask1        : {os.path.basename(mask_1)}")
print(f"   🖼️  mask2        : {os.path.basename(mask_2)}")
print(f"   🖼️  combined     : {os.path.basename(Combined_seg_tif)}")
print(f"   📐  polygones    : {os.path.basename(Combined_seg_gpkg)}")
print(f"   📐  SEG filtré   : {os.path.basename(SEG_shp)}")
print(f"   📊  hexagrid CSV : {os.path.basename(hexagrid_csv)}")
print(f"\n📊 Polygones détectés  : {len(gdf)}")
print(f"   Surface moyenne    : {gdf.geometry.area.mean():.4f} m²")
print(f"\n💡 Ouvre {Combined_seg_gpkg} dans QGIS !")