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

RUN useradd -r -u 1000 appuser
USER 1000

EXPOSE 8000
# Single uvicorn process — not gunicorn.
# The LangGraph graph is a compiled in-memory object. Multiple workers would
# each hold a separate graph instance. Use one process; asyncio handles
# concurrent requests within it.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 3: test (CI only — never pushed to GHCR)
FROM runtime AS test
USER root
ENV LITELLM_API_KEY=sk-test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests/ ./tests/
COPY pytest.ini .
RUN pytest tests/ -v
