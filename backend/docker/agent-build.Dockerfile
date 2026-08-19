FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages --no-cache-dir \
    "fastapi>=0.116,<1.0" \
    "uvicorn>=0.35,<1.0" \
    "pydantic>=2.11,<3.0" \
    "pytest>=8.4,<10.0" \
    "pytest-cov>=6.2,<8.0" \
    "httpx>=0.28,<1.0"

# Prime npm's content-addressable cache. The runtime container can then install
# approved dependencies while running with --network none.
RUN mkdir -p /opt/npm-cache \
    && npm cache add --cache /opt/npm-cache vue@3.5.18 \
    && npm cache add --cache /opt/npm-cache vite@7.3.6 \
    && npm cache add --cache /opt/npm-cache @vitejs/plugin-vue@6.0.1 \
    && npm cache add --cache /opt/npm-cache vitest@3.2.4 \
    && npm cache add --cache /opt/npm-cache @vue/test-utils@2.4.6 \
    && npm cache add --cache /opt/npm-cache jsdom@26.1.0 \
    && chmod -R a-w /opt/npm-cache

ENV npm_config_cache=/opt/npm-cache \
    npm_config_prefer_offline=true \
    PYTHONUNBUFFERED=1

WORKDIR /workspace
