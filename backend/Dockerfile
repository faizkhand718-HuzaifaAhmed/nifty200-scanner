# Multi-stage build: keeps the final image small and free of build tools.
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim AS runtime

# Runs as a non-root user - never run the app as root in production.
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app

COPY --from=builder /root/.local /home/appuser/.local
COPY app ./app
COPY config ./config

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Liveness probe hits /health (never the database - see app/core/health.py's
# module docstring for why liveness and readiness are deliberately separate).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)" || exit 1

# Do NOT bake DATABASE_URL, SECRET_KEY, or any broker credential into this
# image or a .env file copied into it - every secret is supplied at
# container-start time via environment variables (see .env.example and
# deploy/DEPLOYMENT.md's Secret management section).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
