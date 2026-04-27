import sys, os, logging
from pathlib import Path

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("test")

# ================================================================
# PATHS
# ================================================================
DATA_PATH = Path("/app/data")
CHECKPOINT_PATH = Path("/app/checkpoints")
OUTPUT_PATH = Path("/app/outputs")

SAM_CKPT_FILE = os.environ.get("SAM_CHECKPOINT_FILE", "sam_vit_h_4b8939.pth")
PLOT_ID = os.environ.get("PLOT_ID", "SITE")

results = []

def check(name, fn):
    try:
        msg = fn()
        log.info(f"  [PASS] {name} : {msg or 'OK'}")
        results.append((name, True, msg or "OK"))
    except Exception as e:
        log.error(f"  [FAIL] {name} : {e}")
        results.append((name, False, str(e)))

# ================================================================
# HEADER
# ================================================================
log.info("")
log.info("=" * 60)
log.info(f"  Test environnement RapidBenthos — Site : {PLOT_ID}")
log.info("=" * 60)
log.info("")

# ================================================================
# GROUPE 1 — PYTHON + SYSTEME
# ================================================================
log.info("--- Groupe 1 : Python + système ---")

check("Python version",
      lambda: f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

check("DATA_PATH",
      lambda: str(DATA_PATH))

check("CHECKPOINT_PATH",
      lambda: str(CHECKPOINT_PATH))

check("OUTPUT_PATH",
      lambda: str(OUTPUT_PATH))

# ================================================================
# GROUPE 2 — PYTORCH + CUDA
# ================================================================
log.info("\n--- Groupe 2 : PyTorch + CUDA ---")

def test_torch():
    import torch
    return f"torch {torch.__version__}"
check("PyTorch import", test_torch)

def test_cuda():
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA non disponible")
    name = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    return f"{name} — {vram:.1f} Go VRAM — CUDA {torch.version.cuda}"
check("CUDA + GPU", test_cuda)

def test_tensor():
    import torch
    x = torch.ones(256, 256).cuda()
    val = x.sum().item()
    del x
    torch.cuda.empty_cache()
    return f"GPU OK (sum={val})"
check("Tensor GPU", test_tensor)

# ================================================================
# GROUPE 3 — GEOSPATIAL STACK
# ================================================================
log.info("\n--- Groupe 3 : Geo stack ---")

check("GDAL", lambda: __import__("osgeo.gdal").__version__)
check("rasterio", lambda: __import__("rasterio").__version__)
check("geopandas", lambda: __import__("geopandas").__version__)
check("numpy", lambda: __import__("numpy").__version__)
check("shapely", lambda: __import__("shapely").__version__)
check("pandas", lambda: __import__("pandas").__version__)
check("opencv", lambda: __import__("cv2").__version__)
check("scipy", lambda: __import__("scipy").__version__)
check("Pillow", lambda: __import__("PIL").__version__)

# ================================================================
# GROUPE 4 — SAM
# ================================================================
log.info("\n--- Groupe 4 : SAM ---")

check("segment_anything",
      lambda: "OK" if __import__("segment_anything") else "FAIL")

check("samgeo",
      lambda: "OK" if __import__("samgeo") else "FAIL")

def test_sam():
    import torch
    from segment_anything import sam_model_registry

    ckpt = CHECKPOINT_PATH / SAM_CKPT_FILE
    if not ckpt.exists():
        avail = list(CHECKPOINT_PATH.glob("*.pth"))
        if not avail:
            raise FileNotFoundError("Aucun checkpoint SAM")
        ckpt = avail[0]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_type = "vit_h" if "vit_h" in ckpt.name else "vit_l" if "vit_l" in ckpt.name else "vit_b"

    sam = sam_model_registry[model_type](checkpoint=str(ckpt))
    sam.to(device)

    del sam
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return f"SAM {model_type} OK ({ckpt.name})"

check("Chargement SAM GPU", test_sam)

# ================================================================
# GROUPE 5 — DONNEES
# ================================================================
log.info("\n--- Groupe 5 : Données ---")

def test_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError("DATA_PATH introuvable")
    tifs = list(DATA_PATH.glob("*.tif"))
    return f"{len(tifs)} fichiers .tif"
check("Dossier DATA", test_data)

def test_raster():
    import rasterio
    tifs = list(DATA_PATH.glob("*.tif"))
    if not tifs:
        return "Pas de tif"
    with rasterio.open(str(tifs[0])) as src:
        return f"{tifs[0].name} {src.width}x{src.height}"
check("Lecture raster", test_raster)

def test_output():
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    f = OUTPUT_PATH / "_test.txt"
    f.write_text("OK")
    f.unlink()
    return "WRITE OK"
check("OUTPUT write", test_output)

# ================================================================
# GROUPE 6 — METASHAPE (NOUVEAU)
# ================================================================
log.info("\n--- Groupe 6 : Metashape ---")

def test_metashape_import():
    try:
        import Metashape
        return f"Metashape {Metashape.app.version}"
    except Exception as e:
        raise RuntimeError(f"Metashape import failed: {e}")

check("Metashape import", test_metashape_import)

def test_metashape_runtime():
    import Metashape

    app = Metashape.app
    version = app.version

    # test léger API
    doc = Metashape.Document()
    doc.clear()

    return f"Runtime OK (version={version})"

check("Metashape runtime", test_metashape_runtime)

# ================================================================
# RESUME FINAL
# ================================================================
log.info("")
log.info("=" * 60)

passed = [r for r in results if r[1]]
failed = [r for r in results if not r[1]]

log.info(f"RESULTATS : {len(passed)} passes / {len(failed)} echecs")
log.info("=" * 60)

for name, ok, msg in results:
    log.info(f"[{'PASS' if ok else 'FAIL'}] {name}")

if failed:
    log.error(f"{len(failed)} erreurs détectées")
    sys.exit(1)
else:
    log.info("Tous les tests OK — prêt pipeline 🚀")
    sys.exit(0)