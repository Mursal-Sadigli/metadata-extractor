FROM node:20-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    libgomp1 \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY python-core/requirements-docker.txt ./python-core/requirements-docker.txt
COPY python-core/constraints-docker.txt ./python-core/constraints-docker.txt
# CPU torch — easyocr/ultralytics CUDA torch (~3GB) çəkməsin
RUN pip3 install --no-cache-dir --break-system-packages \
    -r python-core/requirements-docker.txt \
    -c python-core/constraints-docker.txt \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple

COPY backend/package.json backend/package-lock.json* ./backend/
RUN cd backend && npm install --omit=dev

COPY backend ./backend
COPY python-core ./python-core

WORKDIR /app/backend

ENV NODE_ENV=production
ENV PYTHONIOENCODING=utf-8
ENV PYTHON_BIN=python3
# Render RAM limiti (~512MB Free) — ağır ML söndürülür
ENV LIGHT_VISION=1
ENV LIGHT_OSINT=1
ENV LIGHT_FORENSICS=1
ENV SKIP_HEAVY_ENRICH=1
ENV YOLO_MODEL=yolov8n.pt
ENV YOLO_WORLD=0
ENV YOLO_TILED=0
ENV YOLO_MULTISCALE=0

EXPOSE 10000

CMD ["node", "server.js"]
