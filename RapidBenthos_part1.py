# RapidBenthos_part1.py — version corrigee
import sys
sys.path.append(r"C:\Program Files\Agisoft\Metashape Pro\python")

import os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from functools import reduce
from tqdm import tqdm
import rasterio
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None
from RB_fcn_part1 import Filter_segments, camera_point_from_segment_centerPoint, hexagrid
from datetime import datetime

def timestamp():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

from samgeo import SamGeo
ImageFile.LOAD_TRUNCATED_IMAGES = True
os.environ['CUDA_VISIBLE_DEVICES'] = '0'

ts = timestamp()

# ============================================================
# CONFIG
# ============================================================
ortho      = r"C:\Users\CMBU\Desktop\testing data\Smash\M7_test_small_1mm.tif"
out_folder = r"C:\Users\Public\Desktop\RapidBenthos\M7\M7_test_small_0.4mm.tif"
plot_id    = "M7"
os.makedirs(out_folder, exist_ok=True)

print(f"Plot ID : {plot_id}")
print(f"Timestamp : {ts}")

# ============================================================
# NOMS DE FICHIERS UNIQUES
# ============================================================
mask_1           = os.path.join(out_folder, f'{plot_id}_{ts}_mask1.tif')
mask_2           = os.path.join(out_folder, f'{plot_id}_{ts}_mask2.tif')
combined_tif     = os.path.join(out_folder, f'{plot_id}_{ts}_combined.tif')
combined_gpkg    = os.path.join(out_folder, f'{plot_id}_{ts}_combined.gpkg')
SEG_shp          = os.path.join(out_folder, f'{plot_id}_{ts}_SEG.shp')
PTS_shp          = os.path.join(out_folder, f'{plot_id}_{ts}_PTS.shp')
PTS_csv          = os.path.join(out_folder, f'{plot_id}_{ts}_PTS.csv')
full_grid_shp    = os.path.join(out_folder, f'{plot_id}_{ts}_grid_full.shp')
clip_grid_shp    = os.path.join(out_folder, f'{plot_id}_{ts}_grid_clip.shp')
hex_seg_shp      = os.path.join(out_folder, f'{plot_id}_{ts}_hex_seg.shp')
hex_pts_shp      = os.path.join(out_folder, f'{plot_id}_{ts}_hex_pts.shp')
hex_pts_csv      = os.path.join(out_folder, f'{plot_id}_{ts}_hex_pts.csv')
camera_uv_output = os.path.join(out_folder, f'{plot_id}_{{}}' + '_camera_UV.csv')

# ============================================================
# SAM PASSE FINE
# ============================================================
print("\n-> SAM passe fine (128x128)...")
sam_kwargs = {
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
sam = SamGeo(
    model_type="vit_h",
    checkpoint=r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_h_4b8939.pth",
    device='cuda:0',
    sam_kwargs=sam_kwargs,
)
sam.generate(ortho, mask_1, batch=True, foreground=False,
             mask_multiplier=255, erosion_kernel=(3, 3), bound=100)
print("-> SAM passe fine OK")

# ============================================================
# SAM PASSE LARGE
# ============================================================
print("\n-> SAM passe large (200x200)...")
sam_kwargs['points_per_side'] = 200
sam_kwargs['points_per_batch'] = 8
sam = SamGeo(
    model_type="vit_h",
    checkpoint=r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_h_4b8939.pth",
    device='cuda:0',
    sam_kwargs=sam_kwargs,
)
sam.generate(ortho, mask_2, batch=True, foreground=False,
             mask_multiplier=255, erosion_kernel=(3, 3), bound=200)
print("-> SAM passe large OK")

# ============================================================
# FUSION GDAL
# ============================================================
print("\n-> Fusion des masques...")
dir_path = r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\osgeo_utils"
gdal_calc_str = 'python {0} -A {1} -B {2} --outfile={3} --calc="A*B" --type=Float32 --hideNoData'
os.system(gdal_calc_str.format(
    os.path.join(dir_path, "gdal_calc.py"),
    mask_1, mask_2, combined_tif
))
print("-> Fusion OK")

# ============================================================
# VECTORISATION
# ============================================================
print("\n-> Vectorisation...")
sam.tiff_to_gpkg(combined_tif, combined_gpkg, simplify_tolerance=None)
print("-> Vectorisation OK")

# ============================================================
# FILTRAGE SEGMENTS
# ============================================================
print("\n-> Filtrage segments...")
segments_df_filtered, segments_pts_df = Filter_segments(
    combined_gpkg, SEG_shp, PTS_shp, PTS_csv)
print(f"-> Filtrage OK : {len(segments_df_filtered)} segments")

# ============================================================
# FIX CRS
# ============================================================
print("\n-> Fix CRS...")
import rasterio
with rasterio.open(ortho) as src:
    crs_ortho = src.crs

seg = gpd.read_file(SEG_shp)
if seg.crs is None:
    seg = seg.set_crs(crs_ortho)
    seg.to_file(SEG_shp)
    print(f"  CRS applique : {crs_ortho}")
else:
    print(f"  CRS deja defini : {seg.crs}")

# ============================================================
# HEXAGRID
# ============================================================
print("\n-> Hexagrid...")
hexagrid_shp, hexagrid_pts = hexagrid(
    ortho, 0.05,
    full_grid_shp, SEG_shp,
    clip_grid_shp, hex_seg_shp,
    hex_pts_shp, hex_pts_csv
)
print(f"-> Hexagrid OK : {len(hexagrid_pts)} points")

# ============================================================
# ETAPE 7 — METASHAPE
# ============================================================
# print("\n-> Etape 7 Metashape...")
# MetashapeProject_path = r"C:\Users\CMBU\Desktop\testing data\M7_0326.psx"
# Chunk_number = 0
# PhotoPath = r"C:\Users\CMBU\Desktop\testing data\M7"

# camera_uv = camera_point_from_segment_centerPoint(
#     MetashapeProject_path, Chunk_number, PhotoPath,
#     camera_uv_output, hex_pts_csv
# )
# print("-> Etape 7 OK")
# print(f"\nFICHIERS CREES dans : {out_folder}")
# print(f"  mask1     : {os.path.basename(mask_1)}")
# print(f"  mask2     : {os.path.basename(mask_2)}")
# print(f"  combined  : {os.path.basename(combined_tif)}")
# print(f"  SEG       : {os.path.basename(SEG_shp)}")
# print(f"  hex_pts   : {os.path.basename(hex_pts_csv)}")