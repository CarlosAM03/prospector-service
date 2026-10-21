# Contrato Platform ↔ Service

**PROPOSED — OWNER APPROVAL REQUIRED**

Inspección 2026-10-21: Backend Docs/Contracts/prospector-service-api.v1.yaml contiene
POST /api/v1/prospecting/jobs y POST /api/v1/internal/prospecting-jobs/{jobId}/events.
No contiene exportación. Usa X-API-Key; BusinessResult incluye siete campos equivalentes,
source/sourceIdentifier/metadata. En src/prospecting-jobs/prospecting-jobs.service.ts el
export delegado a assertAvailable sigue deshabilitado (503,
PROSPECTOR_INTEGRATION_PENDING). No hay cache de Jobs implementada actualmente.

El endpoint público existente sigue siendo
GET /api/v1/prospecting-jobs/{id}/export?format=csv|xlsx, controlado por NestJS.
El siguiente diseño no está aprobado, no cambia el OpenAPI vigente y no registra rutas.

## Operación propuesta

GET /api/v1/prospecting/jobs/{jobId}/export?format=csv|xlsx.
Autenticación Platform -> Service mediante credencial interna X-API-Key del esquema
existente, con TLS y rotación administrada por entorno. Proponer además X-Tenant-Id
derivado por Platform del JWT validado (nunca del tenant arbitrario del cliente).
La API key identifica al llamante; Service debe validar scope de ese principal y comparar
el tenant con el binding inmutable (jobId, tenantId) registrado en aceptación del Job.
Consultar resultados exclusivamente por esa clave compuesta. No basta conocer jobId.
No se reenvía JWT de Flutter ni se permite llamada directa Flutter -> Service.

Propuesta: Service mantiene un snapshot temporal normalizado, seleccionado y ligado al
Job completado, separado de los prospectos persistidos en PostgreSQL por Platform.
No se implementa ese almacenamiento aquí. Owner debe decidir medio (memoria/almacenamiento
temporal), capacidad, supervivencia a reinicios, TTL y retención de tombstones. Se propone
TTL inicial de 1 hora tras COMPLETED, sujeto a aprobación. Sin tombstone scoped no se
puede distinguir expirado de desconocido; en ese caso devolver 404, sin fingir 410.
Reexportación de prospectos ya persistidos sería otro caso contractual.

## Semántica propuesta

| Caso | Respuesta propuesta |
|---|---|
| COMPLETED, datos disponibles, tenant autorizado | 200 binario; mismas columnas y MIME del core |
| COMPLETED sin filas | 200 archivo sólo con cabeceras |
| Formato inválido | 400 INVALID_EXPORT_FORMAT |
| Credencial ausente/inválida | 401 UNAUTHORIZED |
| Principal interno sin permiso de exportar | 403 FORBIDDEN |
| Job inexistente o ajeno al tenant | 404 JOB_NOT_FOUND, sin revelar existencia cross-tenant |
| QUEUED/RUNNING/FAILED/CANCELLED | 409 EXPORT_NOT_READY; no exportar parciales sin nueva decisión |
| Snapshot expirado con tombstone autorizado | 410 EXPORT_RESULTS_EXPIRED |
| Filas/campo/input/output excede límites | 413 EXPORT_LIMIT_EXCEEDED, sin archivo parcial |
| Datos inválidos internos / fallo serialización | 500 EXPORT_FAILED, detalle público seguro |
| Capacidad temporal saturada | 503 EXPORT_UNAVAILABLE |

Errores en envelope del contrato actual: success=false, error={code,message,details,
timestamp}. No enviar paths, contenido de registros, trazas o credenciales a Flutter.
Platform debe traducir/propagar códigos de forma contractual, preservar MIME y
Content-Disposition al retransmitir el binario, y no envolver bytes en JSON/base64.
Un fallo previo al inicio de respuesta no debe dar un 200 parcial.

Filename: businesses_{UUID}.{csv|xlsx}, o prefijo de Job seguro sin tenant/datos personales.
MIME CSV text/csv; charset=utf-8; XLSX application/vnd.openxmlformats-officedocument.
spreadsheetml.sheet (sin salto de línea real). Content-Disposition attachment con nombre
ASCII seguro. Cache-Control no-store en ambos servicios; evitar logs/caches con datos.

Límites iniciales propuestos por operación iguales al core: 10.000 filas, campo 32.766
caracteres, entrada 16 MiB UTF-8 y archivo 16 MiB. Definir además cuota/concurrencia por
tenant y timeout Platform↔Service antes de habilitar. Nunca aceptar del cliente límites
ilimitados ni una selección de filas de otro tenant. No agregar nuevos campos de datos
al formato oficial sin decisión explícita.

## Decisiones reales pendientes

1. Aprobar ruta, códigos, esquema del tenant y autenticación/scopes/rotación.
2. Aprobar propietario y estrategia de snapshots, TTL/tombstones, capacidad y reinicios.
3. Aprobar límites HTTP/concurrencia/timeout y tratamiento de trabajos parciales.
4. Cerrar contrato público Engine→Service y conectar selección normalizada al adaptador.
5. Configurar repositorio/remote del Service para publicar el workflow y abrir PR.

La biblioteca A/B funciona sin estas decisiones. C (microservicio independiente) queda
opcional, no implementado. No se aprueba ninguna ruta unilateralmente.
