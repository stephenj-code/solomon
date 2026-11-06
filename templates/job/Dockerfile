# Stage 1: build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: runtime — production image
FROM python:3.12-slim AS runtime
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

# Stage 3: test (CI only — never pushed to GHCR)
FROM runtime AS test
USER root
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ./tests/
COPY pytest.ini .
RUN pytest tests/ -v
