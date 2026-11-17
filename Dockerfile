# FLARE demo image: one container, one port, one URL.
#
# Stage 1 builds the React console; stage 2 runs the FastAPI process that
# serves both /api/* and the built UI (backend/app/static_site.py). No second
# service, no CORS, no reverse proxy to configure.

FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY --from=ui /ui/dist frontend/dist

# Render/Railway/Fly/Cloud Run inject PORT; 8080 is the local default.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]
