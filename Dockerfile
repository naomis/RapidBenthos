# ================================================================
# RapidBenthos — Dockerfile
# CUDA 12.8 · Ubuntu 22.04 · Python 3.10
# ================================================================

FROM nvidia/cuda:12.8.1-cudnn9-devel-ubuntu22.04

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
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512 \
    GDAL_CACHEMAX=4096 \
    GDAL_NUM_THREADS=ALL_CPUS

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
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# ================================================================
# STEP 2 — Install uv
# ================================================================
COPY --from=ghcr.io/astral/uv:latest /uv /usr/local/bin/uv

# ================================================================
# STEP 3 — Install Python dependencies via uv
# ================================================================
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --extra gpu --frozen --no-dev --compile-bytecode

# ================================================================
# STEP 4 — Metashape headless
# ================================================================
COPY wheels/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl /tmp/
RUN pip install --no-cache-dir /tmp/metashape-2.3.0-cp39.cp310.cp311.cp312.cp313-abi3-linux_x86_64.whl \
    && rm /tmp/*.whl

# ================================================================
# STEP 4b — Metashape binaire complet (pour activation CLI)
# ================================================================
COPY wheels/metashape-pro_2_3_0_amd64.tar.gz /tmp/

RUN tar -xzf /tmp/metashape-pro_2_3_0_amd64.tar.gz -C /opt/ \
    && mv /opt/metashape-pro /opt/metashape \
    && rm /tmp/metashape-pro_2_3_0_amd64.tar.gz

# Wrapper propre (PAS de symlink)
RUN echo '#!/bin/bash\n/opt/metashape/metashape.sh "$@"' > /usr/local/bin/metashape \
    && chmod +x /usr/local/bin/metashape

# ================================================================
# STEP 5 — Utilities
# ================================================================
RUN uv pip install --no-cache-dir \
    pyyaml \
    python-dotenv \
    psutil \
    coloredlogs

# STEP 5b — Dask pour parallélisation GeoPandas
RUN uv pip install --no-cache-dir \
    dask==2024.2.0 \
    dask-geopandas==0.3.1

# ================================================================
# STEP 6 — Verify gdal_calc.py
# ================================================================
RUN which gdal_calc.py && chmod +x /usr/bin/gdal_calc.py || \
    (echo "ERROR: gdal_calc.py not found" && exit 1)

# ================================================================
# STEP 7 — Directory structure
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
# STEP 8 — Final build verification
# ================================================================
RUN echo "=== Import verification ===" && \
    python -c "import torch; print('torch         :', torch.__version__)" && \
    python -c "import torch; assert '+cu128' in torch.__version__, f'ERROR: expected torch CUDA 12.8, got {torch.__version__}'" && \
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
# STEP 9 — Entrypoint
# ================================================================
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "/app/Scripts/RapidBenthos_part1.py"]