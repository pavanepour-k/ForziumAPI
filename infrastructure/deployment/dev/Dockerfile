# syntax=docker/dockerfile:1.7-labs

##############################################
# Builder image: compiles the Rust extension #
##############################################
FROM rust:1.77-slim-bullseye AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        pkg-config \
        libssl-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml README.md requirements.txt ./
COPY core ./core
COPY forzium ./forzium
COPY interfaces ./interfaces
COPY plugins ./plugins
COPY infrastructure ./infrastructure

RUN pip install --upgrade pip \
    && pip install maturin==1.7.4

RUN maturin build --release --strip --out dist

##############################################
# Runtime image: installs wheel + application #
##############################################
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/usr/local/bin:${PATH}" \
    PYTHONPATH="/srv/forzium"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/forzium

COPY --from=builder /build/dist/forzium_engine-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/forzium_engine-*.whl

COPY infrastructure/deployment/dev/runtime-requirements.txt ./runtime-requirements.txt
RUN pip install --no-cache-dir -r runtime-requirements.txt

COPY forzium ./forzium
COPY interfaces ./interfaces
COPY core ./core
COPY infrastructure ./infrastructure
COPY plugins ./plugins
COPY main.py ./main.py

ENV FORZIUM_HOST=0.0.0.0 \
    FORZIUM_PORT=8000 \
    FORZIUM_ENV=dev

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "forzium.cli", "run"]