import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from RB_paths import get_venv_prefix, get_metashape_config, setup_dll_directories

setup_dll_directories()

prefix = get_venv_prefix()

os.environ["PATH"] = str(prefix / "Library" / "bin") + ";" + os.environ.get("PATH", "")
os.environ["GDAL_DATA"] = str(prefix / "Library" / "share" / "gdal")
os.environ["PROJ_LIB"] = str(prefix / "Library" / "share" / "proj")

# ============================================
# CONFIG — from environment variables
# ============================================
cfg = get_metashape_config()
MetashapeProject_path = cfg["project_path"]
Chunk_number = cfg["chunk_number"]
PhotoPath = cfg["photo_path"]
hexagrid_csv = cfg["hexagrid_csv"]
OutputPath = cfg["output_path"]

# Add scripts path for imports
sys.path.append(str(cfg["scripts_path"]))
from RB_fcn_part1 import camera_point_from_segment_centerPoint

# ============================================
# ÉTAPE 7 — Metashape
# ============================================
print("=" * 50)
print("ÉTAPE 7 — Liaison Metashape")
print("=" * 50)

camera_uv = camera_point_from_segment_centerPoint(
    MetashapeProject_path, Chunk_number, PhotoPath, OutputPath, hexagrid_csv
)

print("\n✅ Terminé")
print(f"   Points UV trouvés  : {len(camera_uv)}")
print(f"   Caméras uniques    : {camera_uv.camera_id.nunique()}")
print(f"   Segments uniques   : {camera_uv.SAM_centroid.nunique()}")
