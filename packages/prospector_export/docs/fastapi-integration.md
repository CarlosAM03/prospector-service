# Adaptación para el futuro Service

```python
from prospector_export import ExportFormat, ExportService, from_normalized
from prospector_export.fastapi_adapter import to_response


def build_download(selected_normalized_records):
    records = (from_normalized(item) for item in selected_normalized_records)
    artifact = ExportService.export(records, ExportFormat.CSV)
    return to_response(artifact)
```

No se importa Engine. El Protocol exige name, category, address, phone, email, website,
language como propiedades legibles. tests/test_integration.py define NormalizedFixture
tipada, independiente. La conformidad con el contrato público final del Engine requiere
verificación posterior: no se afirma conexión operativa. Para BusinessResult del contrato
Platform ya existente usar from_service_result(mapping); sourceIdentifier/metadata no
entran al archivo. No pasar `original_businesses` ni el contenedor SearchResult.

Instalar [fastapi] en la aplicación consumidora. Response resulta apropiada porque el
archivo ya está generado y acotado en RAM; envolver BytesIO en StreamingResponse no
reduce la memoria de generación. El consumidor puede usar open_binary para su propio
transporte/almacenamiento, asumiendo su cierre. No ejecutar generación síncrona pesada
en el event loop: usar handler síncrono/threadpool con concurrencia acotada.

| Cabecera | Valor |
|---|---|
| Content-Type CSV | text/csv; charset=utf-8 |
| Content-Type XLSX | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet |
| Content-Disposition | attachment; filename="basename_seguro.csv\|xlsx" |
| Cache-Control | no-store |
| X-Content-Type-Options | nosniff |

La prueba HTTP registra una ruta sólo en una app fixture; no se crea ninguna ruta del
Service. La futura ruta debe validar servicio llamante, tenant ligado al Job, estado,
retención y límites antes de consultar/generar. Platform mantiene autorización del usuario.
La librería no contiene autenticación, almacenamiento ni ciclo de vida del Job.

Errores y política HTTP propuestos están en decisions-pending.md, requieren aprobación.
El backend continúa con export 503 y no fue modificado.
