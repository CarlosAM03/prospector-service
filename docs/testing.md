# Validación reproducible

Validación local del 21 de octubre de 2026, sobre la base Service
`0494f2b385e38c6a83202290a13fab33e345c7c4` y el código de esta rama.
Python Windows 3.13.4; Ruff 0.17.1; pytest 9.1.1; FastAPI 0.156.8;
Pydantic 2.14.1; Playwright 1.61.0; openpyxl 3.1.5.
Las versiones transitivas usadas están en requirements/constraints.txt.

## Gates locales ejecutados

| Comando desde Service | Resultado |
|---|---|
| `python -m compileall -q src` | PASS, código de salida 0 |
| `python -m ruff check .` | PASS, All checks passed |
| `python -m ruff format --check .` | PASS, 32 archivos |
| `python -m pytest -q` | PASS, 94 pruebas: 81 unit/API, 7 contract, 5 integration, 1 browser |
| `python -m pytest -q packages/prospector_export/tests` | PASS, 103 pruebas, paquete sin cambios |
| `python -m build` | PASS, wheel y sdist 0.1.0.dev0 |
| `python scripts/installed_smoke.py --wheelhouse <wheelhouse> --work-dir <temporal-aislado>` | PASS, INSTALLED_SERVICE_ENGINE_EXPORT_SMOKE_PASS |
| `docker build -t prospector-service:foundation .` | PASS, base Python 3.11.14 fijada por digest |
| `python scripts/container_smoke.py --image prospector-service:foundation` | PASS, CONTAINER_ASGI_BROWSER_HEALTH_SMOKE_PASS (no Maps) |

El primer compile en la ruta física larga encontró MAX_PATH de Windows. Se repitió
correctamente mediante una junction exclusiva hacia Service, bajo
`%TEMP%/prospector-service-01a15e71/source`. Venv, browsers, wheelhouse y temporales
se mantuvieron bajo ese directorio de validación exclusivo, sin usar P: o Q:.
No se comparten caches o instalaciones con Engine. Para reproducir en Windows,
usar un checkout corto o una junction verificada exclusivamente hacia Service.

La suite emite una advertencia de deprecación Starlette TestClient/httpx; no se oculta
ni afecta el resultado. No se añadió httpx2 sin validar compatibilidad del cliente.

## Qué acredita cada prueba

- Unit/API: EnginePort controlado e inyectado; autenticación, admisión, cola llena,
  duplicados, errores, resultados, callbacks/retries y apagado cooperativo. No es
  evidencia de scraping ni de una llamada al Engine real.
- Contract: YAML de autoridad copiado sin cambios y hash SHA256 verificable; envelopes,
  schemas, estados y diferencias explícitas en [contracts.md](contracts.md).
- Integration: paquete Engine instalado desde el commit fijado; fachada/pipeline
  reales con adquisición controlada sólo dentro de un test, preflight público real,
  mapping y exportación instalada. No se presenta el fixture como Google Maps real.
- Browser: BrowserRuntime público real, Chromium local, set_content y cierre;
  no navegación a servicios externos. Readiness usa esta misma estrategia al arrancar.
- Installed smoke: venv nuevo; instalación offline de todos los wheels con --no-index;
  proceso Python -I desde un directorio externo al source; verifica que Service,
  Engine y export se importan desde sys.prefix, preflight Engine, CSV/XLSX y health.
  El venv temporal se elimina al terminar. Preparar wheelhouse puede requerir red:
  `python -m pip wheel -c requirements/constraints.txt --wheel-dir .validation/wheels ".[dev]"`.
- Container smoke: proceso ASGI con Engine/export y Chromium instalados, UID 10001,
  puerto loopback efímero, ready/live 200, request sin clave 401 y docker stop en
  finally. Usa claves ficticias; no admite Jobs ni hace scraping. El contenedor
  efímero se elimina con --rm. Docker requiere acceso legítimo al daemon local.

No se ejecutó E2E Platform→Service→Google Maps, callback hacia Backend real ni carga
productiva. El registry y los eventos siguen en memoria sin TTL ni recuperación.

## CI remoto

[Service CI](https://github.com/CarlosAM03/prospector-service/actions/workflows/service-ci.yml)
ejecuta quality; unit and contract en Python 3.11/3.13; integration/browser en
Ubuntu y Windows 3.11/3.13; package/installed smoke; docker-build/container smoke.
El estado definitivo se comprueba en los checks del PR y del commit correspondiente.
Service CI se ejecuta en todos los PRs a main: los checks obligatorios no pueden
filtrarse por paths, porque un PR sólo del exportador quedaría bloqueado sin ellos.
No hay continue-on-error, Maps live ni secretos productivos. El workflow exportador
existente permanece intacto y filtra sus propios paths.

Engine se consume desde el baseline publicado
`70f6081688db5c5bc5ea612f5fabd5724aab0b20`; su validación remota precedente está en
[Engine CI](https://github.com/CarlosAM03/prospector-engine/actions/runs/39608150150).
Este cierre no reconfigura ni vuelve a publicar Engine.
