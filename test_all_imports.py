#!/usr/bin/env python
"""
Comprehensive import test for RapidBenthos.
Run: python test_all_imports.py
"""

import sys
import importlib
from pathlib import Path

# ================================================================
# INVENTORY OF ALL IMPORTS FROM CODEBASE
# ================================================================

# Standard library
STDLIB_IMPORTS = [
    "os",
    "sys",
    "json",
    "math",
    "datetime",
    "warnings",
    "logging",
    "subprocess",
    "threading",
    "tempfile",
    "shutil",
    "glob",
    "pathlib",
    "functools",
    "time",
    "signal",
    "multiprocessing",
]

# Third-party packages (from pyproject.toml + code analysis)
# Note: Some are optional or Docker-only
THIRD_PARTY_IMPORTS = [
    # Core scientific
    ("numpy", "numpy"),
    ("pandas", "pandas"),
    ("scipy", "scipy"),
    ("sklearn", "scikit-learn"),  # imports as sklearn
    # Visualization
    ("matplotlib", "matplotlib"),
    ("matplotlib.pyplot", "matplotlib.pyplot"),
    ("matplotlib.colors", "matplotlib.colors"),
    ("matplotlib.gridspec", "matplotlib.gridspec"),
    # Geospatial
    ("geopandas", "geopandas"),
    ("rasterio", "rasterio"),
    ("shapely", "shapely"),
    ("shapely.geometry", "shapely.geometry"),
    ("pyproj", "pyproj"),
    ("fiona", "fiona"),
    ("osgeo.gdal", "osgeo.gdal"),  # GDAL Python bindings (system dep)
    # Computer vision / ML
    ("torch", "torch"),
    ("torchvision", "torchvision"),
    ("cv2", "opencv-python-headless"),
    ("PIL", "Pillow"),
    ("PIL.Image", "PIL.Image"),
    ("PIL.ImageFile", "PIL.ImageFile"),
    ("PIL.ImageTk", "PIL.ImageTk"),
    # SAM
    ("segment_anything", "segment-anything-py"),
    ("samgeo", "segment-geospatial"),
    # Progress / UI
    ("tqdm", "tqdm"),
    ("tkinter", "tkinter"),
    ("tkinter.ttk", "tkinter.ttk"),
    ("tkinter.filedialog", "tkinter.filedialog"),
    ("tkinter.messagebox", "tkinter.messagebox"),
    ("tkinter.scrolledtext", "tkinter.scrolledtext"),
    # Config
    ("yaml", "PyYAML"),
    ("dotenv", "python-dotenv"),
    # Parallel
    ("multiprocess", "multiprocess"),
    # Optional (Docker-only or not in base env)
    # ("dask", "dask"),
    # ("dask_geopandas", "dask-geopandas"),
    # ("Metashape", "Metashape"),  # Requires license + Docker
    # ("psutil", "psutil"),
    # ("coloredlogs", "coloredlogs"),
]

# Local modules
LOCAL_IMPORTS = [
    "RB_fcn_part1",
    "RB_fcn_part3",
]

# ================================================================
# TEST FUNCTIONS
# ================================================================


def test_import(name, import_fn):
    """Test a single import."""
    try:
        import_fn()
        return True, None
    except Exception as e:
        return False, str(e)


def run_tests():
    print("=" * 60)
    print("RapidBenthos — Import Verification")
    print("=" * 60)

    results = {"pass": [], "fail": []}

    # Standard library
    print("\n--- Standard Library ---")
    for mod in STDLIB_IMPORTS:
        ok, err = test_import(mod, lambda m=mod: __import__(m))
        status = "✅" if ok else "❌"
        print(f"  {status} {mod}" + (f" — {err}" if err else ""))
        (results["pass"] if ok else results["fail"]).append(mod)

    # Third-party
    print("\n--- Third-Party Packages ---")
    for import_name, pkg_name in THIRD_PARTY_IMPORTS:
        ok, err = test_import(import_name, lambda m=import_name: __import__(m))
        status = "✅" if ok else "❌"
        print(f"  {status} {import_name} ({pkg_name})" + (f" — {err}" if err else ""))
        (results["pass"] if ok else results["fail"]).append(import_name)

    # Local modules
    print("\n--- Local Modules ---")
    scripts_dir = Path(__file__).parent / "Scripts"
    sys.path.insert(0, str(scripts_dir))

    for mod in LOCAL_IMPORTS:
        ok, err = test_import(mod, lambda m=mod: __import__(m))
        status = "✅" if ok else "❌"
        print(f"  {status} {mod}" + (f" — {err}" if err else ""))
        (results["pass"] if ok else results["fail"]).append(mod)

    # Specific function imports from local modules
    print("\n--- Local Functions ---")
    local_funcs = [
        ("RB_fcn_part1.Filter_segments", "from RB_fcn_part1 import Filter_segments"),
        ("RB_fcn_part1.hexagrid", "from RB_fcn_part1 import hexagrid"),
        (
            "RB_fcn_part1.camera_point_from_segment_centerPoint",
            "from RB_fcn_part1 import camera_point_from_segment_centerPoint",
        ),
        (
            "RB_fcn_part3.Select_class_ReefCloud_pts",
            "from RB_fcn_part3 import Select_class_ReefCloud_pts",
        ),
        (
            "RB_fcn_part3.format_percent_cover",
            "from RB_fcn_part3 import format_percent_cover",
        ),
        ("RB_fcn_part3.stack_catplot", "from RB_fcn_part3 import stack_catplot"),
        ("RB_fcn_part3.rgb_to_hex", "from RB_fcn_part3 import rgb_to_hex"),
        (
            "RB_fcn_part3.ColonyLevel_Segments",
            "from RB_fcn_part3 import ColonyLevel_Segments",
        ),
    ]

    for name, import_stmt in local_funcs:
        ok, err = test_import(name, lambda s=import_stmt: exec(s))
        status = "✅" if ok else "❌"
        print(f"  {status} {name}" + (f" — {err}" if err else ""))
        (results["pass"] if ok else results["fail"]).append(name)

    # Summary
    print("\n" + "=" * 60)
    print(f"PASSED: {len(results['pass'])}")
    print(f"FAILED: {len(results['fail'])}")
    print("=" * 60)

    if results["fail"]:
        print("\nFailed imports:")
        for f in results["fail"]:
            print(f"  - {f}")
        return 1
    else:
        print("\n✅ All imports successful!")
        return 0


if __name__ == "__main__":
    sys.exit(run_tests())
