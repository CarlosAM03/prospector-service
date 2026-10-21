# Contrato vigente y diferencias

Autoridad: Backend_Nestjs/saas-platform-backend/Docs/Contracts/prospector-service-api.v1.yaml.
La copia exacta [contracts/prospector-service-api.v1.yaml](contracts/prospector-service-api.v1.yaml)
y su [hash](contracts/authority.json) permiten validar el paquete fuera del workspace.
El YAML original del Backend no se modifica. La copia no crea un contrato nuevo.

Implementado: POST /api/v1/prospecting/jobs con X-API-Key, StartJobRequest y 202
AcceptedJobResponse (success/data/meta), errores 400/401/409/503 con ErrorResponse.
No hay 422 público para validación. Se rechazan bool/strings como limit, sin clamp.
Callbacks: cliente saliente POST /api/v1/internal/prospecting-jobs/{jobId}/events;
esa ruta pertenece a Platform y NO se registra en Service. El cliente exige 200 con
success=true para considerar confirmado el evento; Backend real permanece deshabilitado.

## Mapping

Siete valores normalizados -> BusinessResult.name/category/address/phone/email/website/language.
Query source -> source. Sólo evidencia VERIFIED, source google_maps y kind
google_place_id -> sourceIdentifier; UNVERIFIED u otro namespace -> null.
metadata=null. Se preservan orden, nulos, casing y texto; la validación de email/HTTP(S)
no hace DNS ni transforma valores. Valores que no cumplen formatos fallan explícitamente
como RESULT_MAPPING_FAILED, evitando callbacks que Platform rechazaría sin corrección silenciosa.
Los errores públicos del Job sólo contienen código seguro y mensaje genérico.

UUID eventId, timestamp UTC, sequence incremental por Job, progress=null. COMPLETED
siempre tiene results (incluido []); sólo FAILED tiene error. Reintentos preservan el
mismo cuerpo. No hay porcentajes inventados, estados nuevos ni deduplicación nueva.

## Drifts / restricciones adicionales documentadas

| Autoridad | Implementación inicial | Motivo / resolución |
|---|---|---|
| limit >=1, sin máximo | Máximo 100 estricto | Contrato público Engine; ratificar máximo en Platform |
| keyword/location string, admite vacío | Rechazo de vacío o sólo espacios | Consulta segura, sin cambiar texto |
| callbackUrl uri-reference libre | Sólo ruta exacta de Job en origen Platform configurado; relativas resueltas allí | Fail-closed contra SSRF; ratificar política productiva |
| Sin cuotas HTTP/registry | Request 64 KiB, resultados 1 MiB, cola/registry acotados | Mecanismo provisional inicial, no política productiva aprobada |
| Callback sin retry policy normativa | Timeouts y reintentos acotados configurables | No se promete entrega durable; requiere ratificación |
| Regla de email/uri declarada | Validación sintáctica sin DNS; URL HTTP(S) | Alinear con DTO real de Backend, sin normalización paralela |
| Sin persistencia de Jobs aprobada | Registry/cola en memoria, un proceso, sin TTL | Sólo desarrollo/integración inicial |

No se afirma paridad irrestricta por esas diferencias. Campos extra del request se ignoran
como permite additionalProperties implícito del YAML; nunca pasan directamente al Engine.
No se devuelve input inválido, trazas o secretos en errores. El límite de request devuelve
400 contractual incluso si el tamaño impediría parsearlo.

Health live/ready son auxiliares de infraestructura. FastAPI docs/OpenAPI HTTP están
deshabilitados; app.openapi() sigue disponible para inspección/test local.
No se implementan nuevas APIs de cancelación/exportación/listado ni callbacks receptores.
El endpoint público NestJS y su integración productiva siguen sin habilitar.

## Idempotencia, resultados parciales y recuperación

La detección de duplicados usa jobId dentro del registry del proceso y devuelve 409;
no implementa Idempotency-Key, replay de una respuesta previa ni deduplicación durable.
Tras un reinicio puede admitirse otra vez el mismo jobId. Platform debe acordar la
recuperación y correlación antes de habilitar producción; 202 sólo acredita admisión
en memoria, nunca persistencia o ejecución exactamente una vez.

El Engine puede devolver resultados parciales con issues recuperables. Service mapea
los negocios retornados y conserva su orden; los issues no se convierten en campos
nuevos del callback ni en porcentajes. Un resultado retornado válidamente, incluido
el vacío, termina COMPLETED; una excepción fatal o un mapping inválido termina FAILED.
La política pública de issues/progreso sigue pendiente (S-05). No existe recuperación
de eventos tras reinicio, TTL, consulta de expiración ni exportación HTTP aprobada.
