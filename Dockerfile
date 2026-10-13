FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY models/ models/
COPY scripts/download_model.py scripts/download_model.py
RUN python scripts/download_model.py
COPY --from=frontend /build/dist frontend/dist
ENV YOLO_CONFIG_DIR=/app/data/yolo MPLCONFIGDIR=/app/data/matplotlib
EXPOSE 8000
CMD ["uvicorn","backend.app.main:app","--host","0.0.0.0","--port","8000"]
