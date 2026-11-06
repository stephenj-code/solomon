# Stage 1: build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
# Preserve app/ as a package so "from app.xxx import" works
COPY app/ ./app/

RUN useradd -r -u 1000 appuser
USER 1000

EXPOSE 8000
# Gunicorn + UvicornWorker: multiple processes for a stateless API.
# 2 workers is a safe default for Jetson's RAM.
# Override via GUNICORN_WORKERS in k8s/deployment.yaml if needed.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120"]
