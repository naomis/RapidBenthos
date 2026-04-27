# ================================================================
# RapidBenthos — Dockerfile
# CUDA 12.1 · Ubuntu 22.04 · Python 3.10
# ================================================================

FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive

# ================================================================
# Variables d'environnement runtime
# ================================================================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_VISIBLE_DEVICES=0 \
    GDAL_DATA=/usr/share/gdal \
    PROJ_LIB=/usr/share/proj \
    OMP_NUM_THREADS=4 \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# ================================================================
# ÉTAPE 1 — Dépendances système
# ================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3.10-distutils \
    # GDAL / géospatial système
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    python3-gdal \
    # OpenGL — OBLIGATOIRE pour Metashape (même headless)
    libgl1-mesa-glx \
    libglu1-mesa \
    # Autres libs graphiques / système
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Outils
    git \
    wget \
    curl \
    htop \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Python3.10 par défaut
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python -m pip install --upgrade pip setuptools wheel

# ================================================================
# ÉTAPE 2 — PyTorch 2.2.2 + CUDA 12.1
# ================================================================
RUN pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

# ================================================================
# ÉTAPE 3 — Stack géospatial (versions épinglées)
# ================================================================
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    rasterio==1.3.9 \
    geopandas==0.14.4 \
    pyproj==3.6.1 \
    shapely==2.0.1 \
    fiona==1.9.5

# ================================================================
# ÉTAPE 4 — Data science
# ================================================================
RUN pip install --no-cache-dir \
    pandas==2.0.3 \
    scipy==1.12.0 \
    scikit-learn==1.3.0 \
    matplotlib==3.7.2 \
    tqdm==4.66.0 \
    multiprocess==0.70.15 \
    opencv-python-headless==4.8.0.76 \
    Pillow==10.0.0

# ================================================================
# ÉTAPE 5 — SAM
# ================================================================
RUN pip install --no-cache-dir \
    segment-anything-py==1.0 \
    segment-geospatial==0.11.4

# ── Réépingler les versions critiques écrasées par segment-geospatial ──
RUN pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

RUN pip install --no-cache-dir \
    rasterio==1.3.9 \
    pandas==2.0.3 \
    Pillow==10.0.0

# ================================================================
# ÉTAPE 6 — Metashape headless
# ================================================================
COPY wheels/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl /tmp/
RUN pip install --no-cache-dir /tmp/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl \
    && rm /tmp/*.whl

# ================================================================
# ÉTAPE 7 — Utils
# ================================================================
RUN pip install --no-cache-dir \
    pyyaml \
    python-dotenv \
    psutil \
    coloredlogs

# ================================================================
# ÉTAPE 8 — Vérification gdal_calc.py
# ================================================================
RUN which gdal_calc.py && chmod +x /usr/bin/gdal_calc.py || \
    (echo "ERREUR : gdal_calc.py introuvable" && exit 1)

# ================================================================
# ÉTAPE 9 — Structure des dossiers
# ================================================================
WORKDIR /app

RUN mkdir -p \
    /app/Scripts \
    /app/data \
    /app/outputs \
    /app/checkpoints \
    /app/logs \
    /app/photos

COPY Scripts/ /app/Scripts/

# ================================================================
# ÉTAPE 10 — Vérification finale du build
# ================================================================
RUN echo "=== Vérification des imports ===" && \
    python -c "import torch; print('torch         :', torch.__version__)" && \
    python -c "import torch; assert torch.__version__.startswith('2.2'), f'ERREUR: torch attendu 2.2.x, obtenu {torch.__version__}'" && \
    python -c "import torch; print('CUDA dispo    :', torch.cuda.is_available())" && \
    python -c "import samgeo; print('samgeo        : OK')" && \
    python -c "import geopandas; print('geopandas     :', geopandas.__version__)" && \
    python -c "from osgeo import gdal; print('GDAL          :', gdal.__version__)" && \
    python -c "import rasterio; print('rasterio      :', rasterio.__version__)" && \
    python -c "import pandas; print('pandas        :', pandas.__version__)" && \
    python -c "from PIL import Image; import PIL; print('Pillow        :', PIL.__version__)" && \
    python -c "import Metashape; print('Metashape     :', Metashape.app.version)" && \
    echo "=== Tout OK ==="

# ================================================================
# Commande par défaut
# ================================================================
CMD ["python", "/app/Scripts/RapidBenthos_part1.py"]