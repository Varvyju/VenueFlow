# ────────────────── Build stage ──────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ────────────────── Runtime stage ────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root
RUN useradd --create-home appuser
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

USER appuser

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

# Cloud Run sends PORT env var; uvicorn reads it
CMD ["python", "-m", "uvicorn", "main:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--workers", "2", "--log-level", "info"]
