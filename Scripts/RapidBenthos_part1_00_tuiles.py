# RapidBenthos_M7_tuiles.py
# Ordre optimise pour maximiser la diversite geographique rapidement

import os, sys
import warnings
warnings.filterwarnings("ignore")
import logging
logging.getLogger("samgeo").setLevel(logging.ERROR)

for p in [
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\lib",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\bin",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Library\bin",
]:
    if os.path.exists(p): os.add_dll_directory(p)

import torch
import geopandas as gpd
import pandas as pd
from osgeo import gdal
from datetime import datetime
from samgeo import SamGeo
from RB_fcn_part1 import Filter_segments, hexagrid
from PIL import Image, ImageFile
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

 

PHASE_1_diversite = [
    1,           # Haut
    14, 16,      # Rangee 1
    22, 29,      # Rangee 2
    33, 40,      # Rangee 3
    46, 54,      # Centre
    57, 65,      # Rangee 5
    66, 76,      # Rangee 6
    80, 87,      # Rangee 7-8
    93, 97, 108, # Bas
]

PHASE_2_reste = [
    2, 3, 12, 13, 15, 23, 24, 25, 26, 27, 28, 30,
    34, 35, 36, 37, 38, 39, 41, 42, 44, 47, 48, 49,
    50, 51, 52, 53, 55, 56, 58, 59, 60, 61, 62, 63,
    64, 67, 68, 69, 70, 71, 72, 73, 74, 75, 79, 81,
    82, 83, 84, 85, 94, 95, 96, 105, 106, 107,
]

tuiles_recif = PHASE_1_diversite + PHASE_2_reste

tuiles_dir  = r"\\Creo34-nas\CREO\241275_ENVIR_EXXONMOBIL_MOZAMBIQUE\DATA\PSM\PRODUCTS\ORTHO_0326\M7 tuiles"
out_base    = r"C:\Users\Public\Desktop\RapidBenthos\M7\tuiles_resultats"
os.makedirs(out_base, exist_ok=True)
progress_file = os.path.join(out_base, "progression.txt")

print("=" * 55)
print("PLAN : DIVERSITE GEOGRAPHIQUE D'ABORD")
print("=" * 55)
print(f"Phase 1 : {len(PHASE_1_diversite)} tuiles -> {PHASE_1_diversite}")
print(f"Phase 2 : {len(PHASE_2_reste)} tuiles")
deja = [n for n in tuiles_recif if os.path.exists(os.path.join(out_base, f"tuile_{n}", "DONE.txt"))]
print(f"Deja traitees : {len(deja)} — {deja}")
print("=" * 55)

for num in tuiles_recif:

    tuile_name = f"M7 tuiles.{num}.tif"
    ortho      = os.path.join(tuiles_dir, tuile_name)
    out_folder = os.path.join(out_base, f"tuile_{num}")
    plot_id    = f"M7_t{num}"
    done_flag  = os.path.join(out_folder, "DONE.txt")

    if os.path.exists(done_flag):
        phase = "P1" if num in PHASE_1_diversite else "P2"
        print(f"SKIP [{phase}] Tuile {num} — deja traitee")
        continue

    os.makedirs(out_folder, exist_ok=True)
    ts    = datetime.now().strftime('%Y-%m-%d')
    phase = "PHASE 1 - DIVERSITE" if num in PHASE_1_diversite else "PHASE 2 - RESTE"

    print(f"\n{'='*55}")
    print(f"[{phase}] TUILE {num} — {tuile_name}")
    print(f"Debut : {datetime.now()}")
    print(f"{'='*55}")

    try:
        print("  -> SAM passe fine (128x128)...")
        sam = SamGeo(
            model_type="vit_h",
            checkpoint=r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_h_4b8939.pth",
            device='cuda:0',
            sam_kwargs={
                'points_per_side': 128, 'points_per_batch': 16,
                'pred_iou_thresh': 0.88, 'stability_score_thresh': 0.94,
                'stability_score_offset': 1.0, 'box_nms_thresh': 0.35,
                'crop_n_layers': 0, 'crop_nms_thresh': 0.9,
                'crop_n_points_downscale_factor': 1, 'min_mask_region_area': 1600,
            }
        )
        mask_1 = os.path.join(out_folder, f'{plot_id}{ts}_mask1.tif')
        sam.generate(ortho, mask_1, batch=True, foreground=False,
                     mask_multiplier=255, erosion_kernel=(3,3), bound=100)
        print("  -> SAM passe fine OK")

        print("  -> SAM passe large (200x200)...")
        sam = SamGeo(
            model_type="vit_h",
            checkpoint=r"C:\Users\CMBU\.cache\torch\hub\checkpoints\sam_vit_h_4b8939.pth",
            device='cuda:0',
            sam_kwargs={
                'points_per_side': 200, 'points_per_batch': 8,
                'pred_iou_thresh': 0.88, 'stability_score_thresh': 0.94,
                'stability_score_offset': 1.0, 'box_nms_thresh': 0.35,
                'crop_n_layers': 0, 'crop_nms_thresh': 0.9,
                'crop_n_points_downscale_factor': 1, 'min_mask_region_area': 1600,
            }
        )
        mask_2 = os.path.join(out_folder, f'{plot_id}{ts}_mask2.tif')
        sam.generate(ortho, mask_2, batch=True, foreground=False,
                     mask_multiplier=255, erosion_kernel=(3,3), bound=200)
        print("  -> SAM passe large OK")

        print("  -> Fusion des masques...")
        dir_path = r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\osgeo_utils"
        combined = os.path.join(out_folder, f'{plot_id}{ts}_combined.tif')
        os.system(f'python {os.path.join(dir_path,"gdal_calc.py")} -A {mask_1} -B {mask_2} --outfile={combined} --calc="A*B" --type=Float32 --hideNoData')
        print("  -> Fusion OK")

        print("  -> Vectorisation...")
        combined_gpkg = os.path.join(out_folder, f'{plot_id}{ts}_combined.gpkg')
        sam.tiff_to_gpkg(combined, combined_gpkg, simplify_tolerance=None)
        print("  -> Vectorisation OK")

        print("  -> Filtrage segments...")
        SEG_shp = os.path.join(out_folder, f'{plot_id}{ts}_SEG.shp')
        PTS_shp = os.path.join(out_folder, f'{plot_id}{ts}_PTS.shp')
        PTS_csv = os.path.join(out_folder, f'{plot_id}{ts}_PTS.csv')
        Filter_segments(combined_gpkg, SEG_shp, PTS_shp, PTS_csv)
        print("  -> Filtrage OK")

        print("  -> Hexagrid...")
        hexagrid_csv = os.path.join(out_folder, f'{plot_id}{ts}_hex_pts.csv')
        hexagrid(ortho, 0.05,
                 os.path.join(out_folder, f'{plot_id}{ts}_grid_full.shp'), SEG_shp,
                 os.path.join(out_folder, f'{plot_id}{ts}_grid_clip.shp'),
                 os.path.join(out_folder, f'{plot_id}{ts}_hex_seg.shp'),
                 os.path.join(out_folder, f'{plot_id}{ts}_hex_pts.shp'),
                 hexagrid_csv)
        print("  -> Hexagrid OK")

        with open(done_flag, 'w', encoding='utf-8') as f:
            f.write(f"Terminee le {datetime.now()}\n")
        with open(progress_file, 'a', encoding='utf-8') as f:
            f.write(f"OK Tuile {num} [{phase}] - {datetime.now()}\n")

        print(f"TUILE {num} TERMINEE !")

        if num == PHASE_1_diversite[-1]:
            print("\n" + "="*55)
            print("*** PHASE 1 TERMINEE ! ***")
            print("-> MAINTENANT : fusionner hex_pts.csv")
            print("-> Lancer Etape 7 Metashape")
            print("-> Verifier cameras uniques (objectif : >50)")
            print("-> Lancer inference_from_csv.py")
            print("-> Continuer Phase 2 sur ce PC en parallele")
            print("="*55 + "\n")

    except Exception as e:
        print(f"ERREUR Tuile {num} : {e}")
        with open(progress_file, 'a', encoding='utf-8') as f:
            f.write(f"ERREUR Tuile {num} : {e} - {datetime.now()}\n")
        continue

print("\nTOUTES LES TUILES TERMINEES !")