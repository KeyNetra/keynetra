FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY keynetra /app/keynetra
COPY contracts /app/contracts
COPY pyproject.toml /app/pyproject.toml
COPY README.md /app/README.md
RUN pip install --no-cache-dir /app
RUN chown -R appuser:appuser /app

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready', timeout=3)"

CMD ["keynetra", "serve", "--host", "0.0.0.0", "--port", "8080"]
