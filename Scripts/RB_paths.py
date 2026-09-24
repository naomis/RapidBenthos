"""
Dynamic path resolution for RapidBenthos.
Replaces hardcoded Windows/miniconda paths with environment-aware detection.
"""

import os
import shutil
import sys
from pathlib import Path


def get_venv_prefix() -> Path:
    """Get the current environment prefix."""
    return Path(sys.prefix)


def get_torch_lib_paths() -> list[Path]:
    """Get torch library paths for DLL loading (Windows)."""
    prefix = get_venv_prefix()
    paths = [
        prefix / "Lib" / "site-packages" / "torch" / "lib",
        prefix / "Lib" / "site-packages" / "torch" / "bin",
        prefix / "Library" / "bin",
    ]
    return [p for p in paths if p.exists()]


def get_osgeo_utils_path() -> Path | None:
    """Find osgeo_utils (gdal_calc.py) location."""
    gdal_calc = shutil.which("gdal_calc.py")
    if gdal_calc:
        return Path(gdal_calc).parent
    prefix = get_venv_prefix()
    candidates = list(prefix.glob("**/osgeo_utils"))
    if candidates:
        return candidates[0]
    candidates = list(prefix.glob("**/gdal_calc.py"))
    if candidates:
        return candidates[0].parent
    return None


def get_gdal_calc_path() -> Path:
    """Get gdal_calc.py path, raising if not found."""
    gdal_calc = shutil.which("gdal_calc.py")
    if gdal_calc:
        return Path(gdal_calc)
    prefix = get_venv_prefix()
    candidates = list(prefix.glob("**/gdal_calc.py"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError("gdal_calc.py not found. Install gdal-bin or python3-gdal.")


def get_sam_checkpoint(model_type: str = "vit_h") -> Path:
    """Get SAM checkpoint path from config or default cache location."""
    env_checkpoint = os.environ.get("SAM_CHECKPOINT")
    if env_checkpoint and Path(env_checkpoint).exists():
        return Path(env_checkpoint)

    # Check project checkpoints directory first (Docker mount)
    project_checkpoints = get_checkpoint_root()
    checkpoints = {
        "vit_h": "sam_vit_h_4b8939.pth",
        "vit_l": "sam_vit_l_0b3195.pth",
        "vit_b": "sam_vit_b_01ec64.pth",
    }
    project_ckpt = project_checkpoints / checkpoints.get(
        model_type, "sam_vit_h_4b8939.pth"
    )
    if project_ckpt.exists():
        return project_ckpt

    # Fall back to torch hub cache
    cache_dir = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    cache_dir.mkdir(parents=True, exist_ok=True)
    default = cache_dir / checkpoints.get(model_type, "sam_vit_h_4b8939.pth")
    if default.exists():
        return default

    # Return the expected path (caller should handle download if missing)
    return default


def setup_dll_directories() -> None:
    """Add necessary DLL directories for Windows (torch, GDAL, etc.)."""
    if sys.platform != "win32":
        return
    for p in get_torch_lib_paths():
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(p))
    osgeo4w = Path(r"C:\OSGeo4W\bin")
    if osgeo4w.exists() and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(osgeo4w))


def get_data_root() -> Path:
    """Get data root from environment or default."""
    env = os.environ.get("DATA_PATH")
    if env:
        return Path(env)
    return Path("/app/data")


def get_photos_root() -> Path:
    """Get photos root from environment or default."""
    env = os.environ.get("PHOTOS_PATH")
    if env:
        return Path(env)
    return Path("/app/photos")


def get_output_root() -> Path:
    """Get output root from environment or default."""
    env = os.environ.get("OUTPUT_PATH")
    if env:
        return Path(env)
    return Path("/app/outputs")


def get_checkpoint_root() -> Path:
    """Get checkpoint root from environment or default."""
    env = os.environ.get("CHECKPOINT_PATH")
    if env:
        return Path(env)
    return Path("/app/checkpoints")


def get_log_root() -> Path:
    """Get log root from environment or default."""
    env = os.environ.get("LOG_PATH")
    if env:
        return Path(env)
    return Path("/app/logs")


def get_part3_inputs() -> dict:
    """Get Part 3 input paths from environment variables."""
    data_root = get_data_root()
    output_root = get_output_root()

    return {
        "rb_centroid_csv": Path(
            os.environ.get(
                "RB_CENTROID_CSV", data_root / "outputs" / "M7_reoriented5mm.csv"
            )
        ),
        "rc_csv": Path(
            os.environ.get(
                "RC_CSV",
                output_root / "dense_inference" / "SAM_points" / "M7_reoriented5mm.csv",
            )
        ),
        "label_file": Path(
            os.environ.get("LABEL_FILE", data_root / "label_set_M7_compatible.csv")
        ),
        "polygon_file": Path(
            os.environ.get("POLYGON_FILE", data_root / "outputs" / "M7_hex_seg.shp")
        ),
        "label_polygon_seg": Path(
            os.environ.get("LABEL_POLYGON_SEG", output_root / "M7_labeled_segments.shp")
        ),
        "label_polygon_csv": Path(
            os.environ.get("LABEL_POLYGON_CSV", output_root / "M7_labeled_segments.csv")
        ),
        "percent_cover": Path(
            os.environ.get("PERCENT_COVER", output_root / "M7_percent_cover.csv")
        ),
        "out_fig": Path(
            os.environ.get("OUT_FIG", output_root / "M7_community_composition.png")
        ),
        "colony_segments_shp": Path(
            os.environ.get(
                "COLONY_SEGMENTS_SHP", output_root / "M7_colony_segments.shp"
            )
        ),
    }


def get_metashape_config() -> dict:
    """Get Metashape configuration from environment variables."""
    data_root = get_data_root()
    output_root = get_output_root()

    return {
        "project_path": Path(
            os.environ.get(
                "METASHAPE_PROJECT_PATH", data_root / "metashape" / "project.psx"
            )
        ),
        "chunk_number": int(os.environ.get("METASHAPE_CHUNK_NUMBER", "0")),
        "photo_path": Path(
            os.environ.get("METASHAPE_PHOTO_PATH", data_root / "photos")
        ),
        "hexagrid_csv": Path(
            os.environ.get("HEXAGRID_CSV", output_root / "hex_pts.csv")
        ),
        "output_path": Path(
            os.environ.get(
                "METASHAPE_OUTPUT_PATH", output_root / "metashape_output.csv"
            )
        ),
        "scripts_path": Path(
            os.environ.get("RAPIDBENTHOS_SCRIPTS", Path(__file__).parent)
        ),
    }
