# Prospector Service — 0.1.0.dev0

Aplicación FastAPI real para la integración inicial de Prospector Engine con Platform.
Acepta Jobs autenticados, ejecuta el Engine independiente fuera del event loop y envía
callbacks contractuales. Reutiliza prospector-export para generar CSV/XLSX en Python.

**SINGLE PROCESS · SINGLE WORKER · NON-DURABLE QUEUE · DEVELOPMENT / INITIAL INTEGRATION.**
No es una release estable ni una integración productiva habilitada de Platform.

---

## Frontera y estado

```text
Flutter -> NestJS Platform -> FastAPI -> bounded queue -> single Engine thread
                                   -> callbacks -> NestJS Platform
                                   -> export_results -> prospector-export
```

NestJS conserva JWT, RBAC, tenant, autorización del Job y persistencia SaaS. Service no
administra usuarios, no consulta PostgreSQL y no implementa scraping/normalización
paralelos. Engine se invoca mediante su API Python pública, sin HTTP ni copia de código.

- Engine 0.1.0.dev0: repositorio oficial, commit exacto
  `70f6081688db5c5bc5ea612f5fabd5724aab0b20`, publicado en main con CI verde y protección.
- Procedencia histórica del Engine: CLI v1.0.0,
  `bd50cf7cbba76ccd75517d06037662dff4797b05`; no se importa CLI.
- Export 0.1.0: API pública de [packages/prospector_export](packages/prospector_export/README.md).
  Dependencia reproducible desde commit Service `0494f2b385e38c6a83202290a13fab33e345c7c4`,
  subdirectorio del paquete. Su implementación local permanece intacta.
- El Backend inspeccionado aún devuelve 503 para iniciar Jobs/callbacks/exportación.
  Este bootstrap no activa su adaptador ni modifica Backend/Flutter.

## Instalación y ejecución

Python >=3.11; Git accesible para instalar dependencias fijadas por SHA. Desde este
repositorio, preferiblemente en una ruta corta en Windows:

```powershell
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -c requirements/constraints.txt -e ".[dev]"
# Sólo runtime Chromium opt-in, en un cache propio del Service:
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/.cache/browsers"
python -m playwright install chromium
# Establecer las variables de .env.example en el entorno (no se carga automáticamente).
python -m prospector_service
```

Linux usa `.venv/bin/activate` y, para Chromium, `playwright install --with-deps chromium`.
La instalación puede requerir red; las pruebas offline no usan Maps ni Backend real.
El entorno del Service no se comparte con Engine. Las referencias Git son inmutables,
no main flotante ni rutas personales. Para desarrollo del exportador puede instalarse
`pip install -e packages/prospector_export` por separado; no es necesario para ejecutar Service.

`python -m prospector_service` / `prospector-service` fija un único worker ASGI.
No usar múltiples procesos, reload en despliegue o réplicas para compartir este registry.

## Configuración

[.env.example](.env.example) contiene todas las variables consumidas y ningún secreto real.
`Settings.from_env()` valida tipos. Claves vacías o configuración incompleta cierran la
aceptación y readiness; liveness sigue disponible.

| Variables | Uso |
|---|---|
| APP_ENV, HOST, PORT, LOG_LEVEL | Modo, bind ASGI y logging |
| INTERNAL_API_KEY | X-API-Key entrante; comparación constante; no JWT |
| PLATFORM_CALLBACK_ORIGIN, CALLBACK_API_KEY | Destino Platform único y credencial saliente |
| ALLOW_LOCAL_CALLBACKS | Localhost sólo con opt-in explícito, prohibido en production |
| ENGINE_BROWSER, ENGINE_HEADLESS | msedge baseline; chromium explícito; sin fallback |
| ENGINE_WORKER_CONCURRENCY | Sólo 1 en esta implementación |
| QUEUE_CAPACITY, MAX_REGISTERED_JOBS | Cola pendiente (16) y registry total (100) |
| MAX_REQUEST_BYTES, MAX_RESULT_BYTES | 64 KiB por request; 1 MiB de resultados por Job |
| CALLBACK_TIMEOUT, CALLBACK_MAX_ATTEMPTS, CALLBACK_BACKOFF | Reintentos iniciales acotados |
| SHUTDOWN_GRACE_SECONDS | Drenado antes de solicitar cancelación cooperativa |

Los límites/políticas son mecanismos iniciales configurables, no decisiones productivas
definitivas. El registry conserva request, tres eventos y resultados hasta reinicio:
no TTL, eviction, recuperación ni entrega durable. Una vez lleno devuelve 503.

## API implementada

| Método / ruta | Comportamiento |
|---|---|
| POST /api/v1/prospecting/jobs | X-API-Key, validación, aceptación inmediata 202 |
| GET /health/live | Proceso vivo; no scraping ni llamadas externas |
| GET /health/ready | Configuración, prueba real de Engine/browser al arranque, worker y capacidad |

El request es `StartJobRequest`: jobId/tenantId CUID, query y callbackUrl. Query contiene
keyword/location no vacíos, source=google_maps y limit entero 1–100. No hay clamp ni
cambio silencioso del texto. Los errores de validación producen 400, no 422.
Se preservan los envelopes success/data/meta y success=false/error con timestamp UTC;
401 para credencial inválida, 409 para jobId repetido y 503 por indisponibilidad/capacidad.
No se registra un Job que no pudo encolarse.

No existen rutas de cancelación, lectura/listado de Jobs, exportación o recepción de
callbacks del Platform. La biblioteca/adaptadores internos no autorizan esas APIs.
Los endpoints operativos no sustituyen el contrato de dominio.

## Jobs, Engine, resultados y callbacks

Un único ThreadPoolExecutor ejecuta Engine síncrono y su prueba de browser. El worker
consume la cola en orden; el request HTTP no espera la búsqueda. Lifecycle implementado:
QUEUED -> RUNNING -> COMPLETED o FAILED. CANCELLED sólo puede emitirse por apagado
cooperativo, sin endpoint HTTP. Durante shutdown se deja de aceptar, se drena hasta la
gracia y después se solicita cancelación; se espera cleanup real. Una llamada browser
bloqueante puede exceder esa gracia: no se mata ni abandona un thread activo.

El adaptador consume SearchQuery, EngineConfig, ProspectorEngine y scopes públicos.
Mapea los siete campos de NormalizedBusiness, preservando orden, nulos y valores.
source proviene de la query; sourceIdentifier sólo de evidencia VERIFIED del namespace
google_maps/google_place_id; metadata=null. Nunca se infiere un Place ID. Email/website
inválidos provocan fallo explícito de mapping, sin corregir ni perder datos silenciosamente.

El cliente saliente usa el endpoint aprobado del Backend:
`POST /api/v1/internal/prospecting-jobs/{jobId}/events`. No lo expone en Service.
Cada evento tiene UUID, secuencia monotónica por Job y timestamp UTC; progress=null,
results sólo en COMPLETED (también []), error sólo en FAILED. No se inventan porcentajes.
Reintentos conservan UUID/secuencia/cuerpo exactos; se reintenta timeout/red, 408, 429 y
5xx, con máximo configurable. 401/4xx y redirecciones fallan sin seguimiento.
Un fallo final de entrega se registra y no cambia el resultado del Engine; no hay outbox,
replay persistente ni garantía de que Platform reciba todos los eventos.

callbackUrl debe ser exactamente la ruta de ese Job, absoluta en el origen configurado
o relativa a él. Se rechazan otros hosts, rutas, query/fragment/userinfo y redirecciones.
HTTP localhost sólo se permite explícitamente en desarrollo/test. El origen configurado
es una decisión de despliegue de confianza; no se acepta desde el cliente final.
[Contrato y drifts](docs/contracts.md) describe estas restricciones adicionales.

## Exportación interna

`prospector_service.adapters.export.export_results(records, "csv" | "xlsx")` devuelve
ExportArtifact utilizando exclusivamente prospector-export. Conserva Name, Category,
Address, Phone, Email, Website, Language y Businesses; no añade tenant/job/metadata.
No se añadió la ruta propuesta de exportación: [decisiones pendientes](docs/decisions-pending.md).

## Docker

```powershell
docker build -t prospector-service:dev .
docker run --rm --init --shm-size=1g --cap-drop=ALL --security-opt=no-new-privileges -p 8000:8000 --env-file .env prospector-service:dev
python scripts/container_smoke.py --image prospector-service:dev
```

Contexto exclusivo Service; builder obtiene Engine/export de commits oficiales y construye
wheels, runtime instala sin Git ni dependencias de desarrollo. Base fijada por digest,
Chromium instalado, UID 10001. No se incluyen .env, CLI, Backend o Flutter. HOST=0.0.0.0,
PORT=8000 por defecto en la imagen; PORT se consume al iniciar ASGI.
La imagen selecciona Chromium/headless para integración controlada; no certifica browser
productivo ni Google Maps live. Sin secretos configurados readiness es 503.
El smoke usa credenciales ficticias de test, valida ASGI y browser sin aceptar Jobs.

## Tests, build y CI

```powershell
python -m compileall -q src
python -m ruff check .
python -m ruff format --check .
python -m pytest -q -m "not browser"
python -m pytest -q -m browser
python -m pytest -q packages/prospector_export/tests
python -m build
# Preparación wheelhouse (puede usar red), seguida de smoke totalmente offline:
python -m pip wheel -c requirements/constraints.txt --wheel-dir .validation/wheels ".[dev]"
python scripts/installed_smoke.py --wheelhouse .validation/wheels
```

Las pruebas separan fake Engine inyectado, fachada real instalada con adquisición
controlada, browser local sin red y live E2E NO EJECUTADO. La copia de referencia del
YAML tiene hash y tests contractuales; no se alteró el original Backend.
[Testing](docs/testing.md) registra comandos/resultados y límites de evidencia.
[Arquitectura](docs/architecture.md) explica orquestación, memoria y apagado.

Se conserva .github/workflows/prospector-export.yml y se añade service-ci.yml:
quality, unit, integration, package y docker-build. Ningún check obligatorio usa Maps
live ni secretos de producción. La rama feature se publica para PR; no se fusiona a main.

## Preparación para Platform

Aplicación e integración Python inicial implementadas; habilitación productiva NO.
Faltan decisiones sobre browser productivo, persistencia/TTL/entrega durable,
concurrencia y política productiva de callbacks. [Decisiones](docs/decisions-pending.md)
incluye alternativas/riesgos/recomendaciones y trabajo independiente disponible.
El contrato admite limit>100/texto vacío/uri-reference libre; Service aplica restricciones
seguras del Engine y de destinos, documentadas como drifts, sin modificar OpenAPI Backend.

Los documentos conceptuales previos [RelacionConProspectorCLI.md](RelacionConProspectorCLI.md)
y [DependenciasServicePlatform.md](DependenciasServicePlatform.md) son contexto histórico.
El código y contrato aprobado prevalecen sobre sus descripciones tentativas.
