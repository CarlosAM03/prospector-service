ARG PIP_VERSION=26.3
FROM python:3.11.18-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39 AS build
ARG PIP_VERSION
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements/constraints.txt requirements/constraints.txt
COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
RUN python -m pip install --no-cache-dir --only-binary=:all: "pip==${PIP_VERSION}" \
    && python -m pip wheel --no-cache-dir --wheel-dir /wheels -c requirements/constraints.txt .

FROM python:3.11.18-slim-bookworm@sha256:a83ba18aef0f865b1a4a611c2cf460fe446f2795673bbb9fe43be570439e3b39
ARG PIP_VERSION
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    HOST=0.0.0.0 PORT=8000 ENGINE_BROWSER=chromium ENGINE_HEADLESS=true \
    PROSPECTOR_CHROMIUM_SANDBOX=1
RUN --mount=type=bind,from=build,source=/wheels,target=/wheels \
    python -m pip install --no-cache-dir --only-binary=:all: "pip==${PIP_VERSION}" \
    && python -m pip install --no-cache-dir --no-index --no-deps /wheels/*.whl \
    && apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && python -m playwright install --with-deps chromium \
    && python -m pip uninstall --yes setuptools wheel \
    && python -m pip check \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 service \
    && install -d -m 0700 -o 10001 -g 10001 /var/lib/prospector /run/prospector-tmp \
    && chmod -R a+rX /opt/playwright
ENV METADATA_PATH=/var/lib/prospector/metadata.sqlite3 WORKER_TEMP_DIR=/dev/shm
USER 10001:10001
WORKDIR /home/service
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health/ready',timeout=2)"
CMD ["python", "-m", "prospector_service"]
