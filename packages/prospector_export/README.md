# prospector-export 0.1.0

Biblioteca Python independiente para serializar registros **ya normalizados y seleccionados**
en CSV y XLSX. Extrae y adapta el contrato de Prospector CLI v1.0.0, commit
`bd50cf7cbba76ccd75517d06037662dff4797b05`. El tag anotado se verificó contra GitHub;
los blobs auditados están en [source-provenance.json](docs/source-provenance.json).
Conserva la licencia MIT original. No importa ni ejecuta CLI o Engine.

## Instalación

Python >=3.11. Desde este directorio:

```powershell
python -m pip install -e ".[dev]"
```

CSV sólo usa la biblioteca estándar y el paquete no tiene dependencias obligatorias.
Para XLSX o la adaptación HTTP opcional:

```powershell
pip install "prospector-export[xlsx]"
pip install "prospector-export[fastapi]"
# Desarrollo completo, incluida la prueba HTTP:
python -m pip install -e ".[dev,xlsx,fastapi]"
```

La instalación desde un wheel local funciona también fuera del repositorio:
`python -m pip install /ruta/prospector_export-0.1.0-py3-none-any.whl`.
La ausencia de openpyxl al pedir XLSX produce `MissingExportDependency`.

## Uso

```python
from prospector_export import ExportFormat, ExportRecord, ExportService

records = [
    ExportRecord(name="EMPRESA EJEMPLO", category="INDUSTRIA", address="TIJUANA", language="ES")
]
csv_artifact = ExportService.export(records=records, format=ExportFormat.CSV)
xlsx_artifact = ExportService.export(records=records, format=ExportFormat.XLSX)
print(csv_artifact.filename, csv_artifact.content_type, len(csv_artifact.content))
with csv_artifact.open_binary() as stream:
    content = stream.read()
# Opcional: directorio de confianza existente, sin sobrescritura ni archivo parcial visible.
# path = csv_artifact.save("/ruta/exports")
```

`ExportArtifact` es inmutable y contiene `filename`, `content_type`, `content` (bytes) y
`format`. [API pública](docs/public-api.md) documenta tipos, límites y errores.
`from_normalized(objeto)` adapta un objeto con las siete propiedades sin modificarlo;
`from_service_result(mapping)` adapta el DTO de integración sin exportar metadata.
El consumidor debe escoger `result.businesses` normalizados, nunca los originales.
Batch entrega selecciones explícitas en llamadas independientes; se preservan orden y
duplicados. `filename_prefix="batch_id_q01"` añade contexto opcional; UUID evita colisiones.

## Formatos y seguridad

Valores canónicos: `csv`, `xlsx`; no se admite el alias legado `excel`.
Columnas exactas: **Name, Category, Address, Phone, Email, Website, Language**.
CSV usa `csv.writer`, coma, CRLF y UTF-8 sin BOM; null se representa como celda vacía.
XLSX usa una hoja `Businesses`; los null son celdas vacías. Cero registros genera cabeceras.

CSV antepone `'` a posibles fórmulas (`= + - @` y variantes de ancho completo,
incluido prefijo con espacios) y a campos que empiezan con tab/CR/LF. Ese carácter forma
parte del valor exportado; también afecta teléfonos con `+`. XLSX fuerza celdas de texto
y conserva esos valores literalmente. El modelo original nunca se modifica.
La mitigación CSV protege la exportación inicial, pero no garantiza seguridad tras
regrabar/importar con configuraciones arbitrarias de una hoja de cálculo. Para lectores
de hojas de cálculo se prefiere XLSX con tipo de celda explícito. Véase la
[guía OWASP](https://owasp.org/www-community/attacks/CSV_Injection).

Se rechazan controles incompatibles con XML, surrogates y campos demasiado largos; no
hay truncado silencioso. Los nombres son ASCII seguros con extensión controlada.
El guardado publica por hard link exclusivo desde un temporal en el mismo directorio y
lo elimina al terminar. Un filesystem sin soporte de hard links produce error tipado.
El directorio debe ser de confianza y no estar sujeto a cambios hostiles concurrentes.

Límites predeterminados por exportación: 10.000 registros, 32.766 caracteres por campo,
16 MiB de texto UTF-8 de entrada y 16 MiB de archivo. `ExportLimits` permite reducirlos
o ajustarlos dentro de la capacidad XLSX. Se consume como máximo un registro adicional
para detectar exceso. El archivo completo reside en memoria; XLSX además construye
celdas openpyxl, con memoria superior al tamaño de entrada/salida. Estos límites no son
un límite absoluto de RAM; limitar concurrencia corresponde al Service. No hay un
generador HTTP de archivos enormes ni temporales de workbook en disco.

## FastAPI y estado de Platform

```python
from prospector_export.fastapi_adapter import to_response

# Dentro de un handler autorizado, después de resolver selección/tenant/Job:
response = to_response(csv_artifact)
```

`Response` conserva MIME y `Content-Disposition: attachment; filename="..."`, añade
`no-store` y `nosniff`. No registra rutas ni implementa autorización.
[Integración FastAPI](docs/fastapi-integration.md) explica la frontera.
El Service todavía no tiene una app conectada. El endpoint público Platform
`GET /api/v1/prospecting-jobs/{id}/export?format=csv|xlsx` sigue devolviendo 503.
La propuesta HTTP interna está marcada **PROPOSED — OWNER APPROVAL REQUIRED** en
[decisiones pendientes](docs/decisions-pending.md). No se cambió el OpenAPI del Backend.

## Validación y distribución

```powershell
python -m compileall -q src
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build
# Descarga de dependencias sólo como preparación del smoke aislado:
python -m pip download --only-binary=:all: --dest .validation/wheels "openpyxl>=3.1.5,<4"
python scripts/validate.py --wheelhouse .validation/wheels
```

Los tests son offline; no necesitan browser, Google Maps ni PostgreSQL. El gate prueba
wheel en un venv limpio fuera de src, primero sin openpyxl/FastAPI y después con XLSX.
En Windows con rutas largas puede utilizarse un drive temporal `subst` que apunte al
Service; los entornos de validación deben ser propios y nunca los del Engine.
[Testing](docs/testing.md) explica CI, evidencia y limitaciones.

## Arquitectura

La opción A integra esta biblioteca en el futuro FastAPI; la B distribuye el mismo
paquete como wheel. Ambas están soportadas sin acoplar el core a HTTP.
La opción C (microservicio separado) sólo se evalúa en [arquitectura](docs/architecture.md);
no se implementa. No se generan archivos en NestJS ni se modifican Backend, Flutter,
Engine o CLI. No hay scraping, normalización, enriquecimiento ni deduplicación aquí.

Más detalles: [inventario de extracción](docs/extraction-inventory.md),
[API pública](docs/public-api.md), [decisiones del propietario](docs/decisions-pending.md).
