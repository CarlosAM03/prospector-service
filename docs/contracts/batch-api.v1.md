# Contrato privado batch v1.0.0

[OpenAPI 3.1](batch-api.v1.openapi.json) · [ADR C1–C6](../service-v1-prelim/decisiones-v1.md)

Platform registra los CUID antes del envío. El único ingreso es `POST /api/v1/prospecting/batches`. Recibe de 1 a 5 consultas ordenadas `google_maps` con texto no vacío y límite entero de 1 a 150. Los IDs de job son únicos en la solución y los de batch tienen su propio espacio. El 202 confirma la transacción y entrega `batchId`, `jobIds` en orden, `acceptedAt` UTC y estado inicial `QUEUED` bajo `data`. Los mismos bytes y clave dentro de 48 h reproducen el recibo aun bajo saturación o tras reinicio.

## Aserción elegida para el candidato

Usar `X-API-Key` y `X-Platform-Assertion`. La aserción es un JWS compacto HS256 con header exactamente `{"alg":"HS256","typ":"JWT"}`, base64url sin padding y clave dedicada, distinta de las claves HTTP y del HMAC de SQLite. TLS protege el transporte.

| Claims | Validación |
| --- | --- |
| `iss`, `aud`, `solutionId` | Igualdad exacta con la configuración. |
| `iat`, `exp` | Unix entero en segundos. Vigencia máxima de 120 s, tolerancia de emisión futura de 30 s, expiración estricta. |
| `tenantId`, `sub` | CUID del tenant y usuario propietario, también para delegación técnica. |
| `actorType`, `scope` | `owner` para crear, consultar o exportar. `platform` con `prospecting:results:import` permite la importación técnica vinculada al recurso vía GET results. ACK y purga aceptan actor `owner` o `platform` con scope específico. |
| `method`, `path`, `query` | Método en mayúsculas, path HTTP crudo y query crudo sin `?`. La ruta vincula los IDs del recurso. Usar `""` sin query. |
| `idempotencyKey`, `bodySha256` | Clave ASCII 1–128 de `A-Z a-z 0-9 . _ ~ -` en admisión, `""` en otras rutas. Digest SHA-256 hexadecimal en minúsculas del body exacto, incluido el body vacío. |

Scopes en el orden de las operaciones HTTP documentadas: `prospecting:batches:create`, `prospecting:batches:read`, `prospecting:results:read`, `prospecting:results:export`, `prospecting:results:ack`, `prospecting:results:purge`. Roles de negocio no conceden accesos automáticos. Un recurso inexistente o ajeno devuelve el mismo 404.

ACK conserva el primer timestamp y no implica purga. Purga elimina la referencia de RAM. Lecturas o exports autorizados que ya tienen una copia inmutable pueden terminar. Disponibilidad terminada devuelve 410. Una consulta todavía pendiente de consolidar devuelve 409. Las operaciones distintas de admisión requieren cuerpo vacío. Respuestas de datos y errores llevan `Cache-Control: no-store`.

El conflicto de clave con otros bytes válidos, IDs ya registrados o un segundo batch activo del usuario devuelve 409. Cuota devuelve 429. Drenaje, cleanup sin verificar o indisponibilidad devuelve 503. Cuerpo demasiado grande devuelve 413. Los errores de Service usan `success=false` y `error={code,message,details,timestamp}`. Nginx puede rechazar antes de Service.

## Callbacks

Service llama a `POST /api/v1/internal/prospecting-batches/{batchId}/jobs/{jobId}/events` en el origen configurado de Platform, usando una API key saliente distinta. 2xx confirma recepción. 408, 429, 5xx y fallos de transporte son reintentables en RAM. Las redirecciones y demás 4xx son definitivos. Cada intento usa los mismos bytes, evento y secuencia. La secuencia aumenta por job y puede tener huecos. Se coalescen métricas pendientes. Platform puede reconciliar con el GET de estado.

`QUEUED → RUNNING → AWAITING_RESULTS` describe ejecución. La materialización del agregado o prefijo emite terminal `COMPLETED` con calidad o `FAILED`, `INTERRUPTED`, `SKIPPED` según outcome. Un job omitido puede ir de QUEUED a SKIPPED. El terminal con snapshot incluye ID opaco y vencimiento, sin prospectos. EXPIRED, PURGED y UNAVAILABLE cambian disponibilidad sin cambiar el outcome. Tras caída abrupta solo se conservan resultados que se materializaron desde un agregado o prefijo real y siguen en RAM. Tras reiniciar se puede emitir nueva información administrativa, pero no se recupera ninguna consulta ni payload comercial perdido.

## Compatibilidad

La retirada de `POST /api/v1/prospecting/jobs` es incompatible e intencional. El [YAML histórico](prospector-service-api.v1.yaml) y su [checksum](authority.json) conservan la referencia del Backend anterior. El callback nuevo añade correlación, elimina los prospectos inline y expone exclusivamente progreso observado, sin porcentajes inventados. El adaptador y receptor reales de Platform requieren validación de su equipo.
