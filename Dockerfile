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
RUN pip3 install --no-cache-dir --break-system-packages torch --index-url https://download.pytorch.org/whl/cpu \
    && pip3 install --no-cache-dir --break-system-packages -r python-core/requirements-docker.txt

COPY backend/package.json backend/package-lock.json* ./backend/
RUN cd backend && npm install --omit=dev

COPY backend ./backend
COPY python-core ./python-core

WORKDIR /app/backend

ENV NODE_ENV=production
ENV PYTHONIOENCODING=utf-8
ENV PYTHON_BIN=python3

EXPOSE 10000

CMD ["node", "server.js"]
