FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements/constraints.txt requirements/constraints.txt
COPY pyproject.toml README.md MANIFEST.in ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels -c requirements/constraints.txt .

FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    HOST=0.0.0.0 PORT=8000 ENGINE_BROWSER=chromium ENGINE_HEADLESS=true
COPY --from=build /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --no-deps /wheels/*.whl \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/* /wheels \
    && useradd --create-home --uid 10001 service \
    && chmod -R a+rX /opt/playwright
USER 10001:10001
WORKDIR /home/service
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8000')+'/health/live',timeout=2)"
CMD ["python", "-m", "prospector_service"]
