FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" --uid 10001 keynetra

COPY requirements.lock requirements.lock
RUN pip install --upgrade pip && pip install -r requirements.lock

COPY alembic.ini alembic.ini
COPY alembic alembic
COPY keynetra keynetra
COPY contracts contracts
COPY pyproject.toml pyproject.toml
COPY README.md README.md

RUN pip install . && chown -R keynetra:keynetra /app

USER keynetra

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"

CMD ["keynetra", "serve", "--host", "0.0.0.0", "--port", "8000"]
