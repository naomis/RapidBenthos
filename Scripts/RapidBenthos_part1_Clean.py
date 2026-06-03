import os, sys
_dll = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
if hasattr(os, 'add_dll_directory') and os.path.exists(_dll):
    os.add_dll_directory(_dll)
os.environ['PATH'] = _dll + ';' + os.environ.get('PATH', '')
os.environ['GDAL_DATA'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'gdal')
os.environ['PROJ_LIB'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'proj')
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
import os, sys
_dll = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
if hasattr(os, 'add_dll_directory') and os.path.exists(_dll):
    os.add_dll_directory(_dll)
os.environ['PATH'] = _dll + ';' + os.environ.get('PATH', '')
os.environ['GDAL_DATA'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'gdal')
os.environ['PROJ_LIB'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'proj')
# ============================================
# FIX DLLs 
# ============================================
import os
for p in [
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\lib",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\bin",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Library\bin",
]:
    if os.path.exists(p):
        os.add_dll_directory(p)

# ============================================
# IMPORTS
# ============================================
import torch
print("GPU :", torch.cuda.is_available())
import sys
try:
    import Metashape
    METASHAPE_OK = True
    print("Metashape OK :", Metashape.app.version)
except Exception as e:
    METASHAPE_OK = False
    print("Metashape non disponible :", e)
from samgeo import SamGeo
import geopandas as gpd
import pandas as pd
from osgeo import gdal
import numpy as np
import cv2
from datetime import datetime
from RB_fcn_part1 import Filter_segments, hexagrid
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

def timestamp():
    return datetime.now().strftime('%Y-%m-%d')
ts = timestamp()

# ============================================
# ENTRÉES
# ============================================
ortho      = r"C:\Users\CMBU\Desktop\RapidBenthos_Data\M7\M7_0326.tif"
out_folder = r"C:\Users\CMBU\Desktop\RapidBenthos\M7 V2" 
plot_id    = "m7"

MetashapeProject_path = r"C:\Users\CMBU\Desktop\RapidBenthos_Data\M7\M7_0326.psx"
Chunk_number = 0
PhotoPath    = r"C:\Users\CMBU\Desktop\RapidBenthos_Data\M7\M7_imgs"

os.makedirs(out_folder, exist_ok=True)
print("=" * 50)
print("Site    :", plot_id)
print("Ortho   :", ortho)
print("Outputs :", out_folder)
print("=" * 50)

# ============================================
# VÉRIFICATION GPU
# ============================================
import torch
print("GPU :", torch.cuda.is_available())
print("Device :", torch.cuda.get_device_name(0))
print("VRAM :", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1), "Go")

# ============================================
# ÉTAPE 1 — SAM passe fine (petits objets)
# ============================================
print("\n ÉTAPE 1/6 — SAM passe fine (128x128)...")

sam = SamGeo(
    model_type="vit_l",
    checkpoint= r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_l_0b3195.pth",
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

mask_1 = os.path.join(out_folder, f'{plot_id}{ts}_mask1.tif')
sam.generate(
    ortho, mask_1,
    batch=True,
    foreground=False,
    mask_multiplier=255,
    erosion_kernel=(3, 3),
    bound=100
)
print("✅ Passe fine terminée →", mask_1)

# ============================================
# ÉTAPE 2 — SAM passe large (grands objets)
# ============================================
print("\n ÉTAPE 2/6 — SAM passe large (200x200)...")

sam = SamGeo(
    model_type="vit_l",
    checkpoint= r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_l_0b3195.pth",
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

mask_2 = os.path.join(out_folder, f'{plot_id}{ts}_mask2.tif')
sam.generate(
    ortho, mask_2,
    batch=True,
    foreground=False,
    mask_multiplier=255,
    erosion_kernel=(3, 3),
    bound=200
)
print("✅ Passe large terminée →", mask_2)

# ============================================
# ÉTAPE 3 — Fusion GDAL (A × B)
# ============================================
print("\n ÉTAPE 3/6 — Fusion des deux masques...")

dir_path = r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\osgeo_utils"
Combined_seg_tif = os.path.join(out_folder, f'{plot_id}{ts}_combined.tif')

gdal_calc_str = 'python {0} -A {1} -B {2} --outfile={3} --calc="A*B" --type=Float32 --hideNoData'
gdal_calc_process = gdal_calc_str.format(
    os.path.join(dir_path, "gdal_calc.py"),
    mask_1, mask_2, Combined_seg_tif
)
os.system(gdal_calc_process)
print("✅ Fusion terminée →", Combined_seg_tif)

# ============================================
# ÉTAPE 4 — Vectorisation (raster → polygones)
# ============================================
print("\n ÉTAPE 4/6 — Vectorisation en polygones...")

Combined_seg_gpkg = os.path.join(out_folder, f'{plot_id}{ts}_combined.gpkg')
sam.tiff_to_gpkg(Combined_seg_tif, Combined_seg_gpkg, simplify_tolerance=None)
print("✅ Vectorisation terminée →", Combined_seg_gpkg)

# ============================================
# ÉTAPE 5 — Filtrage + Hexagrid
# ============================================
print("\n ÉTAPE 5/6 — Filtrage segments...")

SEG_shp = os.path.join(out_folder, f'{plot_id}{ts}_SEG.shp')
PTS_shp = os.path.join(out_folder, f'{plot_id}{ts}_PTS.shp')
PTS_csv = os.path.join(out_folder, f'{plot_id}{ts}_PTS.csv')

segments_df_filtered, segments_pts_df = Filter_segments(
    Combined_seg_gpkg, SEG_shp, PTS_shp, PTS_csv)
print("✅ Filtrage terminé")

print("\n ÉTAPE 6/6 — Grille hexagonale...")

full_grid    = os.path.join(out_folder, f'{plot_id}{ts}_grid_full.shp')
clip_grid    = os.path.join(out_folder, f'{plot_id}{ts}_grid_clip.shp')
hexagrid_seg = os.path.join(out_folder, f'{plot_id}{ts}_hex_seg.shp')
hexagrid_pts = os.path.join(out_folder, f'{plot_id}{ts}_hex_pts.shp')
hexagrid_csv = os.path.join(out_folder, f'{plot_id}{ts}_hex_pts.csv')

hexagird_union_shp, hexagrid_union_pts = hexagrid(
    ortho, 0.05,
    full_grid, SEG_shp,
    clip_grid, hexagrid_seg,
    hexagrid_pts, hexagrid_csv
)
print("✅ Hexagrid terminé")

# ============================================
# ÉTAPE 7 — Metashape 
# ============================================
if METASHAPE_OK:
    print("\n ÉTAPE 7/7 — Liaison Metashape...")
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
        print("⚠️ Erreur Metashape :", e)
else:
    print("\n⚠️ ÉTAPE 7 ignorée — Metashape non disponible")
    print("→ Les résultats de segmentation sont quand même complets !")

# ============================================
# RÉSUMÉ FINAL
# ============================================
print("\n" + "=" * 50)
print("🎉 RAPIDBENTHOS PART 1 TERMINÉ !")
print("=" * 50)
print(f"\n📁 Résultats dans : {out_folder}")
print(f"   🖼️  mask1        : {os.path.basename(mask_1)}")
print(f"   🖼️  mask2        : {os.path.basename(mask_2)}")
print(f"   🖼️  combined     : {os.path.basename(Combined_seg_tif)}")
print(f"   📐  polygones    : {os.path.basename(Combined_seg_gpkg)}")
print(f"   📐  SEG filtré   : {os.path.basename(SEG_shp)}")
print(f"   📊  hexagrid CSV : {os.path.basename(hexagrid_csv)}")

gdf = gpd.read_file(SEG_shp)
print(f"\n📊 Polygones détectés : {len(gdf)}")
print(f"   Surface moyenne   : {gdf.geometry.area.mean():.4f} m²")
print(f"\n💡 Ouvre {Combined_seg_gpkg} dans QGIS !")

