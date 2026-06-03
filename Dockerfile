# ================================================================
# RapidBenthos — Dockerfile
# CUDA 12.1 · Ubuntu 22.04 · Python 3.10
# ================================================================

FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive


# ================================================================
# Runtime environment variables
# ================================================================
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CUDA_VISIBLE_DEVICES=0 \
    GDAL_DATA=/usr/share/gdal \
    PROJ_LIB=/usr/share/proj \
    OMP_NUM_THREADS=8 \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# ================================================================
# STEP 1 — System dependencies
# ================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Python
    python3.10 \
    python3.10-dev \
    python3-pip \
    python3.10-distutils \
    # GDAL / geospatial system
    gdal-bin \
    libgdal-dev \
    libproj-dev \
    libgeos-dev \
    python3-gdal \
    # OpenGL
    libgl1-mesa-glx \
    libglu1-mesa \
    # Other graphical / system libs
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Tools
    git \
    wget \
    curl \
    htop \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Python3.10 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    python -m pip install --upgrade pip setuptools wheel

# ================================================================
# STEP 2 — PyTorch 2.2.2 + CUDA 12.1
# ================================================================
RUN pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

# ================================================================
# STEP 3 — Geospatial stack (pinned versions)
# ================================================================
RUN pip install --no-cache-dir \
    numpy==1.26.4 \
    rasterio==1.3.9 \
    geopandas==0.14.4 \
    pyproj==3.6.1 \
    shapely==2.0.1 \
    fiona==1.9.5

# ================================================================
# STEP 4 — Data science
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
# STEP 5 — SAM
# ================================================================
RUN pip install --no-cache-dir \
    segment-anything-py==1.0 \
    segment-geospatial==0.11.4

# ── Re-pin critical versions overwritten by segment-geospatial ──
RUN pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

RUN pip install --no-cache-dir \
    rasterio==1.3.9 \
    pandas==2.0.3 \
    Pillow==10.0.0
# ================================================================
# STEP 5b — Fix tqdm/Metashape thread conflict
# Le monitor thread de tqdm 4.x cause un crash fatal (none_dealloc)
# quand Metashape itère sur des objets C++ en Python 3.10
# Solution : désactiver le monitor thread au niveau du package
# ================================================================

#RUN pip install --no-cache-dir "tqdm==4.66.0" && \
#    python -c "
#import tqdm
# Patch permanent dans le package installé
#import tqdm._monitor as _mon
#_mon.TRMonitor = type('TRMonitor', (), {
#    '__init__': lambda self, *a, **k: None,
 #   'exit': lambda self: None,
  #  'start': lambda self: None,
#})
#print('tqdm monitor patch OK')"

# ================================================================
# STEP 6 — Metashape headless
# ================================================================
COPY wheels/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl /tmp/
RUN pip install --no-cache-dir /tmp/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl \
    && rm /tmp/*.whl
# ================================================================
# STEP 6b — Metashape binaire complet (pour activation CLI)
# ================================================================
COPY wheels/metashape-pro_2_3_0_amd64.tar.gz /tmp/

RUN tar -xzf /tmp/metashape-pro_2_3_0_amd64.tar.gz -C /opt/ \
    && mv /opt/metashape-pro /opt/metashape \
    && rm /tmp/metashape-pro_2_3_0_amd64.tar.gz

# Wrapper propre (PAS de symlink)
RUN echo '#!/bin/bash\n/opt/metashape/metashape.sh "$@"' > /usr/local/bin/metashape \
    && chmod +x /usr/local/bin/metashape
# ================================================================
# STEP 7 — Utilities
# ================================================================
RUN pip install --no-cache-dir \
    pyyaml \
    python-dotenv \
    psutil \
    coloredlogs

# ================================================================
# STEP 8 — Verify gdal_calc.py
# ================================================================
RUN which gdal_calc.py && chmod +x /usr/bin/gdal_calc.py || \
    (echo "ERROR: gdal_calc.py not found" && exit 1)

# ================================================================
# STEP 9 — Directory structure
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
# STEP 10 — Final build verification
# ================================================================
RUN echo "=== Import verification ===" && \
    python -c "import torch; print('torch         :', torch.__version__)" && \
    python -c "import torch; assert torch.__version__.startswith('2.2'), f'ERROR: expected torch 2.2.x, got {torch.__version__}'" && \
    python -c "import torch; print('CUDA available :', torch.cuda.is_available())" && \
    python -c "import samgeo; print('samgeo        : OK')" && \
    python -c "import geopandas; print('geopandas     :', geopandas.__version__)" && \
    python -c "from osgeo import gdal; print('GDAL          :', gdal.__version__)" && \
    python -c "import rasterio; print('rasterio      :', rasterio.__version__)" && \
    python -c "import pandas; print('pandas        :', pandas.__version__)" && \
    python -c "from PIL import Image; import PIL; print('Pillow        :', PIL.__version__)" && \
    python -c "import Metashape; print('Metashape     :', Metashape.app.version)" && \
    echo "=== All OK ==="
# ================================================================
# STEP 11 — Entrypoint
# ================================================================
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "/app/Scripts/RapidBenthos_part1.py"]