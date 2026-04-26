FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e .

# Copy source after deps so code changes don't bust the dep layer
COPY maestro ./maestro
COPY scripts ./scripts

# Non-root user — never run as root in prod
RUN useradd -m -u 1000 maestro && chown -R maestro:maestro /app
USER maestro

EXPOSE 8000

CMD ["uvicorn", "maestro.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
