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
COPY main.py .

RUN useradd -r -u 1000 appuser
USER 1000

# No HTTP server — this is a batch job.
# Exits 0 on success, non-zero on failure.
# Kubernetes retries according to backoffLimit in k8s/job.yaml.
CMD ["python", "main.py"]
