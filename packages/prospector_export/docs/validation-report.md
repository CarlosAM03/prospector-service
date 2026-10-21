# Informe de entrega — 2026-10-21

## Source provenance

CLI source commit: `bd50cf7cbba76ccd75517d06037662dff4797b05`.
Repository: CarlosAM03/prospector-cli. Tag: v1.0.0, objeto anotado
`35088b4d53c31bb4fdde6c079b5e3d2f31873a32`, verificado por API GitHub de lectura;
sin firma. Blobs auditados: source-provenance.json.
Reutilizados/adaptados: dialecto/proyección CSV, Workbook/Businesses/esquema XLSX,
vista seleccionada y principios de nombres seguros/no sobrescritura del ExportService.
Excluidos: modelos de búsqueda/Batch, ContextVar, queries, deduplicación, browser y UI.
Detalle completo: extraction-inventory.md.

## Package y API

Ubicación absoluta:
`C:\Users\Carl0\Desktop\ProyectosPersonales\DesarrolloDeSoftwareConComputoEnLaNube\PlataformaDeProspeccionAutomatizadaYGestionDeCampañasDeMarketing\DocumentacionGlobal\ProspectorDocs\PROSPECTOR_SERVICE\packages\prospector_export`.

Nombre: prospector-export; import: prospector_export; versión: 0.1.0; Python >=3.11.
Dependencias core: ninguna. XLSX: openpyxl>=3.1.5,<4 y et_xmlfile transitiva.
FastAPI: extra independiente. Instalable: wheel verificado desde procesos externos -I;
editable [dev] verificado desde sdist en ruta corta, sin hacks de sys.path/PYTHONPATH.
Wheel: dist/prospector_export-0.1.0-py3-none-any.whl; sdist también generado.

CSV/XLSX: ExportService.export(records, ExportFormat.CSV/XLSX).
ExportArtifact: filename, content_type, content bytes, format, open_binary y save explícito.
Batch: selecciones ya resueltas, orden/duplicados preservados, UUID, headers-only;
sin nueva deduplicación. FastAPI adapter: to_response, probado con fixtures/TestClient
para ambos formatos, sin rutas de producción ni imports de Engine.

## Gates locales ejecutados

| Gate | Python 3.11.9 Windows x64 | Python 3.13.4 Windows x64 |
|---|---|---|
| compileall | PASS | PASS |
| Ruff lint / format | PASS / PASS | PASS / PASS |
| Unitarias | 100 PASS | 100 PASS |
| Integración offline | 3 PASS | 3 PASS |
| sdist + wheel, build sin aislamiento | PASS | PASS |
| Wheel instalado en venv limpio | PASS | PASS |
| CSV sin openpyxl/FastAPI instalados | PASS | PASS |
| XLSX instalado offline y leído con openpyxl | PASS | PASS |

También se ejecutó `python -m build` con aislamiento predeterminado en Python 3.13:
PASS. Wheel final SHA256:
`72b0e960d990c3e817ae51d5b65cbea6d51eaea44307773f977e07f061cd0ae1`.

Sin tests omitidos en los gates. La suite conjunta también registró 103 PASS.
Se corrigieron integridad CR en XML/XLSX y cierre ZIP al superar límite; pytest ahora
trata errores de recursos no propagados como fallo. Queda una advertencia de deprecación
de Starlette TestClient con httpx; las respuestas HTTP pasan y el core no resulta afectado.
Herramientas: openpyxl 3.1.5, et_xmlfile 2.0.0, pytest 9.1.1, Ruff 0.17.1,
build 1.6.1, setuptools 84.2.1, wheel 0.48.0, FastAPI 0.156.8,
Starlette 1.9.0 y httpx 0.28.1. Python 3.12/Linux: configurados, no ejecutados localmente.
Preparación de dependencias con red; tests/smokes offline, sin Maps/PostgreSQL.
Logs locales ignorados: .validation-gate.log y .validation-gate311.log. JSON de gates
en el temporal privado prospector-export-01a15e71/checks y checks311. No son CI remoto.

## Particularidad Windows

El árbol supera MAX_PATH. Se usó una asignación temporal X: al mismo Service y entornos
propios en `C:\Users\Carl0\AppData\Local\Temp\prospector-export-01a15e71`.
P: ya pertenecía al Engine y se conservó. No se cambió la política global de Windows.
El editable sobre la ruta física larga no pudo importar módulos: setuptools resuelve
el drive al path original. Por ello se comprobó la instalación editable normal desde
sdist en ruta corta. Para desarrollo en este Windows utilizar checkout corto o sdist;
wheel instalado no presenta esta limitación. El gate admite --work-dir para temporales
cortos propios. Se eliminaron venv parciales fallidos dentro del Service.

## Arquitectura, Git y CI

CLI dependency: NO. Engine dependency: NO. FastAPI core dependency: NO.
Backend modified: NO. Engine modified: NO. CLI modified: NO. Flutter modified: NO.
Sólo se editaron archivos del Service y temporales de validación explícitos; no se
compartió venv/build/dist/caches con Engine ni se ejecutaron sus pruebas/builds.

En la inspección inicial Service y raíz global no tenían .git. Durante la ejecución
apareció Git local en el Service: branch master, commit inicial externo
`138313bb87fc6d5e186d15d5bca2a8afce5bd431` (2026-10-21 05:54 America/Tijuana),
que ya incluye implementación y workflow. Se preservó ese snapshot concurrente.
El commit de cierre propio se limita a validation-report.md y git-handoff.md;
su SHA puede consultarse en git log. Remote: no configurado. PR: no creado.
No se creó Git anidado ni se modificó Git en otros proyectos.
CI configured: .github/workflows/prospector-export.yml, matriz Python 3.11/3.12/3.13,
Ubuntu/Windows. CI executed remotely: NO. CI result: CONFIGURED ONLY.
Preparación de commit/PR: git-handoff.md; propietario debe definir/incorporar remote Service.

## Contrato Platform ↔ Service

Endpoint público existente: GET /api/v1/prospecting-jobs/{id}/export?format=csv|xlsx,
sigue devolviendo 503. Contrato interno vigente: aceptación de Jobs y callbacks con
X-API-Key; sin exportación. Propuesta: GET /api/v1/prospecting/jobs/{jobId}/export,
snapshots ligados a tenant+Job, csv/xlsx, COMPLETED, TTL y errores explícitos.
Marcada PROPOSED — OWNER APPROVAL REQUIRED en decisions-pending.md. Pendiente aprobar
ruta, autenticación/scopes/binding tenant, almacenamiento/TTL, límites HTTP/concurrencia,
timeouts y contrato final Engine→Service. OpenAPI del Backend sin cambios.

## Estado final

| Componente | Estado |
|---|---|
| EXPORT LIBRARY | READY |
| CSV | VERIFIED |
| XLSX | VERIFIED |
| FASTAPI ADAPTER | READY; conexión a app/contrato pendiente |
| MICROSERVICE | OPTIONAL / NOT IMPLEMENTED |
| PLATFORM INTEGRATION | PENDING CONTRACT |
| CI | CONFIGURED ONLY |
