# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
WORKDIR /build
COPY . .
RUN pip install maturin && maturin build -m core/rust_engine/Cargo.toml

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /build/target/wheels/forzium_engine-*.whl /tmp/
RUN pip install /tmp/forzium_engine-*.whl && \
    pip install fastapi httpx
COPY . /app
EXPOSE 8000
CMD ["python", "run_server.py"]