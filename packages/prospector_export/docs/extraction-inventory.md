# Inventario de extracción

Autoridad: `CarlosAM03/prospector-cli`, tag v1.0.0, commit
`bd50cf7cbba76ccd75517d06037662dff4797b05`. El 2026-10-21 se consultó
`git/ref/tags/v1.0.0`: tag anotado `35088b4d53c31bb4fdde6c079b5e3d2f31873a32`,
cuyo objeto apunta al commit requerido. Es un tag sin firma; se verificó correspondencia,
no firma criptográfica. Cada archivo se leyó mediante GitHub por SHA fijo, porque la
copia local DocsProspectorCLI no contiene Git. No se tomó código de main posterior.

Los paths y SHA de blob exactos están en source-provenance.json. La licencia MIT y
copyright originales se preservan en LICENSE. No se vendorea la aplicación original.

| Fuente auditada | Reutilización / exclusión |
|---|---|
| src/exporters/csv.py | Adaptado csv.writer, UTF-8, cabeceras, proyección de siete campos y orden; destino pasa a bytes |
| src/exporters/excel.py | Adaptado Workbook, Businesses, cabeceras y proyección; import lazy y celdas de texto |
| src/exporters/base.py | Excluida ABC ligada a archivo y ExportView; despacho simple privado |
| src/exporters/export_view.py | Adaptado principio de vista seleccionada; Protocol sin query ni modelo CLI |
| src/services/export_service.py | Adaptada separación formato/serializador, nombres seguros y no sobrescritura; excluida dependencia de SearchResult, Batch y carpeta global |
| src/services/_export_directory.py | Excluido ContextVar/directorio CLI |
| src/utils/file_naming.py | Excluida dependencia de SearchQuery y reloj local; contexto opcional + UUID |
| src/models/normalized_business.py | Sólo siete campos equivalentes, contrato inmutable nuevo; excluidos campos de enriquecimiento |
| src/models/search_result.py | Excluido completo; consumidor entrega vista normalizada, no originales |
| src/models/search_query.py | Excluido; no source/query obligatorios para generar un archivo |
| src/models/batch.py | Excluidos coordinador, status, identidad, provenance y deduplicación; selección resuelta aguas arriba |
| tests/integration/test_export_service.py | Adaptados schema y fixture EXAMPLE CAFE para bytes y lectura openpyxl |
| tests/integration/test_batch_export.py | Adaptados selección, orden, no mutación, nombres, headers-only, no sobrescritura y limpieza; excluida selección/deduplicación Engine |
| tests/integration/test_portable_exports.py | Adaptados headers-only y destino explícito; sin contexto CLI |
| docs/architecture.md | Confirma exportación fuera del Engine, separación originales/normalizados |
| docs/history/v1.0.0/ContractInventory.md | Confirma contrato de siete columnas y archivos Batch independientes |
| docs/releases/v1.0.0/{FREEZE,KNOWN_LIMITATIONS,RELEASE_NOTES}.md | Auditados freeze, alcance CLI y exclusión de API/SaaS; su estado histórico de publicación no reemplaza tag remoto verificado |

## Diferencias deliberadas frente al CLI

Core independiente, formato canónico xlsx (sin alias excel), artefacto en memoria,
nombre sin query obligatoria, extras opcionales, validación tipada y límites explícitos.
CSV escapa campos sospechosos con apóstrofo; XLSX impide fórmulas/error coercion forzando
texto. Rechazo de controles/Unicode inválido y longitudes excesivas evita corrupción o
truncado silencioso. Estos cambios sólo afectan entradas inseguras/inválidas; la fixture
oficial ordinaria conserva sus valores exactos. Null y cadena vacía se leen como blanco
en XLSX, igual que con openpyxl original; CSV mantiene campos vacíos.

La lectura XLSX con et_xmlfile también se endurece para conservar retornos de carro:
la representación XML usa referencias de carácter en lugar de CR literal. Esta
diferencia corrige pérdida de integridad encontrada en regresión, sin normalizar datos.

No se conserva la reserva de nombre seguida de reapertura con modo w del CLI: el
guardado publica el archivo completo de manera exclusiva. Los límites son propios del
exportador, no el límite de extracción del Engine. No hay nuevos campos en los archivos.
