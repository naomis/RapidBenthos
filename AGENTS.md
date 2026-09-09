# AGENTS.md — RapidBenthos

## Project Overview

Python pipeline for automated segmentation and multi-view classification of coral reef communities from photogrammetric reconstruction. Two main stages:
- **Part 1**: SAM segmentation → mask fusion → vectorization → hexgrid → Metashape linkage
- **Part 3**: Classification + community composition analysis (ReefCloud integration)

## Key Commands

### Local Development (uv only)
```bash
uv venv --python 3.10
source .venv/bin/activate
uv sync --extra gpu
```

### Docker (Recommended for GPU/Metashape)
```bash
docker compose up --build          # Run Part 1 pipeline
docker compose run test-gpu        # Verify GPU + imports
```

### Run Pipeline Scripts Directly
```bash
python Scripts/RapidBenthos_part1.py       # Part 1: segmentation + hexgrid
python Scripts/Rapid_benthos_part3.py      # Part 3: classification + analysis
python Scripts/test_environment.py         # Verify environment
```

## Configuration

- **config.yaml** — Central config (site, ortho, Metashape, SAM checkpoint paths)
- **.env** (required for Docker) — `DATA_PATH`, `PHOTOS_PATH`, `CHECKPOINT_PATH`, `OUTPUT_PATH`, `LOG_PATH`, `METASHAPE_LICENSE_KEY`, `CUDA_VISIBLE_DEVICES`, `PLOT_ID`
- Paths in config.yaml use container mounts: `/app/data`, `/app/photos`, `/app/checkpoints`, `/app/outputs`
- **data/label_set_M7_compatible.csv** — Classification label definitions

## Entry Points & Scripts

| Script | Purpose |
|--------|---------|
| `Scripts/RapidBenthos_part1.py` | Main Part 1 pipeline (SAM → hexgrid) |
| `Scripts/RapidBenthos_part1_Clean.py` | Windows-friendly Part 1 variant |
| `Scripts/RapidBenthos_part1_00_tuiles.py` | Tiled orthomosaic processing |
| `Scripts/RapidBenthos_part1_01_metashape.py` | Metashape integration utilities |
| `Scripts/Rapid_benthos_part3.py` | Part 3: classification + reporting |
| `Scripts/RB_fcn_part1.py` | Part 1 function library (filtering, hexgrid, coord transform) |
| `Scripts/RB_fcn_part3.py` | Part 3 function library (classification, cover %, plots) |
| `Scripts/test_environment.py` | Full env verification (PyTorch CUDA, GDAL, SAM, Metashape) |

## Environment Requirements

- **Python**: 3.10 (enforced in pyproject.toml)
- **CUDA**: 12.8 (Docker), variable locally
- **GPU**: Required for SAM (vit_h checkpoint ~2.5GB VRAM)
- **Metashape Pro**: License key required for 3D/camera linkage
- **Key deps**: torch<2.11 (cu128 index), segment-geospatial[all], geopandas, gdal, rasterio
- **System**: GDAL/PROJ/GEOS must be installed system-wide (apt: gdal-bin libgdal-dev libproj-dev libgeos-dev)

## Docker Specifics

- Base: `nvidia/cuda:12.8.1-cudnn9-devel-ubuntu22.04`
- Metashape installed from local wheels (`dist/` dir)
- Entrypoint (`entrypoint.sh`) handles license activation/deactivation lifecycle
- `PYTHONPATH=/app/Scripts:/app` set in compose
- Shared memory: 16GB (main), 4GB (test)

## Common Gotchas

1. **Metashape license** — Must set `METASHAPE_LICENSE_KEY` in `.env` (or `SKIP` for test mode). Entrypoint auto-deactivates on exit.
2. **tqdm + Metashape conflict** — Part 1 disables tqdm monitor thread (`monitor_interval=0`) and sets `TQDM_NCOLS=100` before imports.
3. **Windows paths in Part 3** — `Rapid_benthos_part3.py` contains hardcoded Windows paths; adapt for your environment.
4. **SAM checkpoint** — Expected at `/app/checkpoints/sam_vit_h_4b8939.pth` (configurable in config.yaml).
5. **GDAL/PROJ alignment** — uv pins gdal=3.9, proj=9.3, geos=3.12 for compatibility via pyproject.toml.

## Verification

```bash
# Quick env check (local)
source .venv/bin/activate && python Scripts/test_environment.py

# Docker env check
docker compose run test-gpu
```

## Project Structure

```
.
├── assets/                  # UI assets (icons, logos)
├── config.yaml              # Pipeline configuration
├── data/                    # Input data (label_set_M7_compatible.csv)
├── dist/                    # Metashape wheels + segment-geospatial wheel (gitignored)
├── docker-compose.yml       # GPU services (rapidbenthos, test-gpu)
├── Dockerfile               # CUDA 12.8 + Metashape + deps
├── entrypoint.sh            # License lifecycle manager
├── pyproject.toml           # Python deps (uv-managed)
├── uv.lock                  # Reproducible lockfile
└── Scripts/                 # All pipeline code
```

## Testing

No formal test suite. Verification is via `test_environment.py` which checks:
- Python version, paths
- PyTorch + CUDA + GPU tensor ops
- GDAL, rasterio, geopandas, numpy, shapely, pandas, opencv, scipy, Pillow
- SAM model loading (segment_anything, samgeo)
- Data directory + raster read + output write
- Metashape import + runtime