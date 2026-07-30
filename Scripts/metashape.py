import os, sys

# ============================================
# FIX DLLs
# ============================================
_dll = os.path.join(os.path.dirname(sys.executable), 'Library', 'bin')
if hasattr(os, 'add_dll_directory') and os.path.exists(_dll):
    os.add_dll_directory(_dll)
os.environ['PATH'] = _dll + ';' + os.environ.get('PATH', '')
os.environ['GDAL_DATA'] = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'gdal')
os.environ['PROJ_LIB']  = os.path.join(os.path.dirname(sys.executable), 'Library', 'share', 'proj')

for p in [
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\lib",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Lib\site-packages\torch\bin",
    r"C:\Users\CMBU\AppData\Local\miniconda3\envs\RapidBenthos\Library\bin",
]:
    if os.path.exists(p):
        os.add_dll_directory(p)

# ============================================
# CONFIG — modifier ici selon le site
# ============================================
MetashapeProject_path = r"\\CREO34-NAS\creo\241275_ENVIR_EXXONMOBIL_MOZAMBIQUE\DATA\PSM\PROCESS\Test_for_RapidBenthos\R1_0326.psx"
Chunk_number          = 0
PhotoPath             = r"\\CREO34-NAS\creo\241275_ENVIR_EXXONMOBIL_MOZAMBIQUE\DATA\PSM\PROCESS\Data\R1"

# CSV hexagrid déjà produit par les étapes 1-6
hexagrid_csv = r"\\Creo34-nas\creo\CTI_Detourgage-automatise\recap desktop\RapidBenthos_Data\outputs\R1_Reoriented\R1_EPSG32737_reoriented_1mm\R1_1mm2026-06-22_hex_pts.csv"

# Dossier de sortie — le {} sera remplacé par le timestamp
out_folder   = r"\\Creo34-nas\creo\CTI_Detourgage-automatise\recap desktop\RapidBenthos_Data\outputs\R1_Reoriented\R1_EPSG32737_reoriented_1mm"
OutputPath   = os.path.join(out_folder, "R1_reoriented1mm.csv")


# ============================================
# IMPORT fonction depuis RB_fcn_part1
# ============================================
sys.path.append(r"C:\Users\Public\Desktop\RapidBenthos")
from RB_fcn_part1 import camera_point_from_segment_centerPoint

# ============================================
# ÉTAPE 7 — Metashape
# ============================================
print("=" * 50)
print("ÉTAPE 7 — Liaison Metashape")
print("=" * 50)

camera_uv = camera_point_from_segment_centerPoint(
    MetashapeProject_path,
    Chunk_number,
    PhotoPath,
    OutputPath,
    hexagrid_csv
)

print("\n✅ Terminé")
print(f"   Points UV trouvés  : {len(camera_uv)}")
print(f"   Caméras uniques    : {camera_uv.camera_id.nunique()}")
print(f"   Segments uniques   : {camera_uv.SAM_centroid.nunique()}")