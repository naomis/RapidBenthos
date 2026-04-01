"""
etape7_metashape_fix2.py
Fix CRS : convertit les centroides UTM 32737 en WGS84 lat/lon
avant de chercher dans v_Trans (qui est en WGS84 géographique)
À lancer via : Metashape → Tools → Run Script
"""

import Metashape
import pandas as pd
import numpy as np
from tqdm import tqdm
from time import time
import sys

sys.path.append(r"C:\Users\Public\Desktop\RapidBenthos")
from RB_fcn_part1 import timestamp, convert_time, CameraStats, Point3D

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MetashapeProject_path = r"\\Creo34-nas\CREO\241275_ENVIR_EXXONMOBIL_MOZAMBIQUE\DATA\PSM\PROCESS\M7_0326.psx"
Chunk_number          = 0
PhotoPath = r"\\Creo34-nas\CREO\241275_ENVIR_EXXONMOBIL_MOZAMBIQUE\DATA\PSM\RAW\M7"
hexagrid_csv = r"C:\Users\Public\Desktop\RapidBenthos\M7\tuiles_resultats\hex_pts_31tuiles_uid.csv"
OutputPath   = r"C:\Users\Public\Desktop\RapidBenthos\M7\tuiles_resultats\M7_31tuiles_uid_{}_camera_UV.csv"
# ───────────────────────────────────────────────────────────────────────────────

print("=" * 60)
print("ETAPE 7 — Extraction UV caméras (fix CRS UTM→WGS84)")
print("=" * 60)

# Ouvrir le projet
doc = Metashape.Document()
doc.open(MetashapeProject_path)
chunk = doc.chunks[Chunk_number]
T   = chunk.transform.matrix
crs = chunk.crs
ts  = timestamp()
save_path = OutputPath.format(ts)

# Afficher le CRS du chunk pour confirmer
print(f"\nCRS du chunk : {crs.name}")
print(f"  (attendu : WGS84 géographique ou similaire)\n")

# Charger les centroides CSV (en UTM 32737)
RB_centroid = pd.read_csv(hexagrid_csv)
print(f"Centroides CSV chargés : {len(RB_centroid)} points (UTM 32737)")
print(f"  X range UTM : {RB_centroid.center_point_x.min():.1f} → {RB_centroid.center_point_x.max():.1f}")
print(f"  Y range UTM : {RB_centroid.center_point_y.min():.1f} → {RB_centroid.center_point_y.max():.1f}")

# Convertir les centroides UTM 32737 → WGS84 via Metashape
# On utilise le CRS source UTM32737 et on projette vers le CRS du chunk (WGS84)
utm_crs = Metashape.CoordinateSystem("EPSG::32737")

print("\nConversion UTM 32737 → CRS chunk (WGS84)...")
cx_wgs = []
cy_wgs = []
for _, row in RB_centroid.iterrows():
    pt_utm = Metashape.Vector((row.center_point_x, row.center_point_y, row.average_z))
    pt_wgs = Metashape.CoordinateSystem.transform(pt_utm, utm_crs, crs)
    cx_wgs.append(pt_wgs.x)
    cy_wgs.append(pt_wgs.y)

RB_centroid['cx_wgs'] = cx_wgs
RB_centroid['cy_wgs'] = cy_wgs

print(f"  X range WGS84 : {RB_centroid.cx_wgs.min():.6f} → {RB_centroid.cx_wgs.max():.6f}")
print(f"  Y range WGS84 : {RB_centroid.cy_wgs.min():.6f} → {RB_centroid.cy_wgs.max():.6f}")

# Charger le modèle 3D
print("\nChargement du modèle 3D...")
tic = time()
model   = chunk.models[0]
v_Trans = []
for V in model.vertices:
    transform_vertices = chunk.crs.project(T.mulp(V.coord))
    v_Trans.append(transform_vertices)
v_Trans = np.asarray(v_Trans)
print(f"  {len(v_Trans)} vertices chargés en {convert_time(time()-tic)}")
print(f"  X range modèle : {v_Trans[:,0].min():.6f} → {v_Trans[:,0].max():.6f}")
print(f"  Y range modèle : {v_Trans[:,1].min():.6f} → {v_Trans[:,1].max():.6f}")

# Vérification overlap
print("\n--- VÉRIFICATION OVERLAP ---")
csv_x_min, csv_x_max = RB_centroid.cx_wgs.min(), RB_centroid.cx_wgs.max()
csv_y_min, csv_y_max = RB_centroid.cy_wgs.min(), RB_centroid.cy_wgs.max()
mod_x_min, mod_x_max = v_Trans[:,0].min(), v_Trans[:,0].max()
mod_y_min, mod_y_max = v_Trans[:,1].min(), v_Trans[:,1].max()

x_overlap = (csv_x_min <= mod_x_max) and (csv_x_max >= mod_x_min)
y_overlap = (csv_y_min <= mod_y_max) and (csv_y_max >= mod_y_min)
print(f"  Overlap X : {'✅ OUI' if x_overlap else '❌ NON'}")
print(f"  Overlap Y : {'✅ OUI' if y_overlap else '❌ NON'}")

if not x_overlap or not y_overlap:
    print("\n  ⚠ AUCUN OVERLAP ! Vérifier le CRS du chunk dans Metashape.")
    print("  → Dans Metashape : Chunk → Settings → Coordinate System")
    sys.exit(1)

# Estimer eps adaptatif
from scipy.spatial import KDTree
sample_idx = np.random.choice(len(v_Trans), min(2000, len(v_Trans)), replace=False)
sample_pts = v_Trans[sample_idx, :2]
tree = KDTree(sample_pts)
dists, _ = tree.query(sample_pts, k=2)
mean_spacing = dists[:, 1].mean()
print(f"\n  Espacement moyen vertices : {mean_spacing:.6f}° ({mean_spacing * 111000:.2f} m environ)")
eps_auto = max(mean_spacing * 3, 0.00005)  # minimum ~5m en degrés
print(f"  eps automatique           : {eps_auto:.6f}°")

# Test point 0
x0, y0 = RB_centroid.cx_wgs.iloc[0], RB_centroid.cy_wgs.iloc[0]
print(f"\n--- TEST POINT 0 : lon={x0:.6f}, lat={y0:.6f} ---")
for test_eps in [eps_auto, eps_auto*2, eps_auto*4, eps_auto*8]:
    xi = np.where(np.logical_and(v_Trans[:,0] > x0 - test_eps, v_Trans[:,0] < x0 + test_eps))
    yi = np.where(np.logical_and(v_Trans[:,1] > y0 - test_eps, v_Trans[:,1] < y0 + test_eps))
    found = len(v_Trans[np.intersect1d(xi, yi)])
    print(f"  eps={test_eps:.6f}° → {found} vertices")

# ─── EXTRACTION UV ─────────────────────────────────────────────────────────────
print("\n--- EXTRACTION UV ---")

# Caméras
cams    = []
for cam in chunk.cameras:
    try:
        chunk.crs.project(T.mulp(cam.center))
        cams.append(cam)
    except:
        continue
print(f"  {len(cams)} caméras chargées\n")

Empty_centroid = []
out_df_list    = []

for index, row in tqdm(RB_centroid.iterrows(), total=RB_centroid.shape[0]):
    samID = row.segment_un
    cx, cy = row.cx_wgs, row.cy_wgs

    # Chercher vertices proches
    verts = []
    for eps in [eps_auto, eps_auto*2, eps_auto*4, eps_auto*8]:
        xi = np.where(np.logical_and(v_Trans[:,0] > cx - eps, v_Trans[:,0] < cx + eps))
        yi = np.where(np.logical_and(v_Trans[:,1] > cy - eps, v_Trans[:,1] < cy + eps))
        verts = v_Trans[np.intersect1d(xi, yi)]
        if len(verts) > 0:
            break

    if len(verts) == 0:
        Empty_centroid.append(samID)
        continue

    # Vertex Z max
    xy_max_z = list(max(verts, key=lambda x: x[2])[:])
    X, Y, Z  = xy_max_z
    p_int    = T.inv().mulp(crs.unproject(Metashape.Vector((X, Y, Z))))

    for camera in chunk.cameras:
        try:
            if not camera.project(p_int):
                continue
            u   = camera.project(p_int).x
            v_px = camera.project(p_int).y
            if (u < 0 or u > camera.sensor.width or
                    v_px < 0 or v_px > camera.sensor.height):
                continue

            est_coord = crs.project(T.mulp(camera.center))
            s1 = Point3D(X, Y, Z)
            s2 = Point3D(est_coord.x, est_coord.y, est_coord.z)

            out_df_list.append({
                'camera_id'               : camera.label,
                'U'                       : u,
                'V'                       : v_px,
                'dis_3D'                  : s1.distance(s2),
                'dis_2D'                  : s1.distance_2D(s2),
                'camera_path'             : camera.photo.path,
                'camera_rotation'         : CameraStats(camera).estimated_rotation,
                'SAM_ID'                  : samID,
                'cam_enable'              : camera.enabled,
                'camera_center_coordinate': s2,
            })
        except:
            continue

# ─── RÉSULTATS ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"RÉSULTATS :")
print(f"  Points UV trouvés       : {len(out_df_list)}")
print(f"  Centroides sans vertex  : {len(Empty_centroid)} / {len(RB_centroid)}")

if len(out_df_list) > 0:
    out_df = pd.DataFrame(out_df_list)
    out_df.to_csv(save_path, index=False)
    print(f"  ✅ Fichier sauvegardé   : {save_path}")
    print(f"  Caméras uniques         : {out_df.camera_id.nunique()}")
    print(f"  Segments uniques        : {out_df.SAM_ID.nunique()}")
else:
    print("  ⚠ Toujours 0 points.")
    print("  → Vérifier le CRS du chunk via :")
    print("     Metashape → Chunk → Settings → Coordinate System")

print("=" * 60)