# Satyapan – one container: React website + FastAPI backend on port 7860 (Hugging Face Spaces / Render / any Docker host)
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PORT=7860
# libgl/glib for OpenCV + RapidOCR
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY . .
COPY --from=web /web/dist frontend/dist
# build the synthetic dataset and run the AI pipeline once (~5–10 min, same seed as the demo video)
RUN python -m data.generator.seed --seed 42 && chmod -R a+rwX /app
WORKDIR /app/backend
EXPOSE 7860
# every start clears officer actions so the demo begins clean
CMD ["sh", "-c", "python ../data/reset_demo.py; uvicorn serve:web --host 0.0.0.0 --port ${PORT}"]
