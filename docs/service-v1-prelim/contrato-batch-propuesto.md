> **Histórico.** Las [decisiones ratificadas del 24 de noviembre](decisiones-v1.md) prevalecen sobre esta propuesta preliminar.

# Contrato HTTP batch · Propuesta para revisión

Estado **propuesto**. El [YAML vigente](../contracts/prospector-service-api.v1.yaml) sigue siendo la autoridad para el flujo individual. El delta contractual se prepara con el dueño del contrato tras la aprobación de las [ADR C1–C6](auditoria-y-adr.md).

## Petición y recibo

`POST /api/v1/prospecting/batches` con `Content-Type: application/json`, `X-API-Key`, `Idempotency-Key` y una aserción de Platform en header interno. El nombre del header de aserción y el formato de la clave de idempotencia quedan pendientes. IDs y consultas de ejemplo son sintéticos.

```json
{
  "batchId": "c00000000000000000001",
  "jobs": [
    {"jobId":"c00000000000000000002","query":{"source":"google_maps","keyword":"librería","location":"Zona A","limit":150}},
    {"jobId":"c00000000000000000003","query":{"source":"google_maps","keyword":"librería","location":"Zona B","limit":150}},
    {"jobId":"c00000000000000000004","query":{"source":"google_maps","keyword":"librería","location":"Zona C","limit":150}},
    {"jobId":"c00000000000000000005","query":{"source":"google_maps","keyword":"librería","location":"Zona D","limit":150}},
    {"jobId":"c00000000000000000006","query":{"source":"google_maps","keyword":"librería","location":"Zona E","limit":150}}
  ]
}
```

```json
{
  "success": true,
  "data": {
    "batchId": "c00000000000000000001",
    "jobIds": [
      "c00000000000000000002",
      "c00000000000000000003",
      "c00000000000000000004",
      "c00000000000000000005",
      "c00000000000000000006"
    ],
    "status": "QUEUED",
    "acceptedAt": "2026-11-24T20:00:00Z"
  },
  "meta": {}
}
```

Platform registra los IDs antes del POST. Los cinco `jobId` son distintos, la posición en el array fija el FIFO y `limit` es entero entre 1 y 150. La admisión devuelve 202 solo después de reservar la lane y registrar el recibo y los cinco jobs. El recibo describe la aceptación y puede preceder a la creación del proceso. La aceptación se conserva para replay aunque cambie el estado del batch.

## Identidad y errores propuestos

Platform acredita al usuario activo y su membresía autorizada. Service comprueba que la API key identifica la solución y que la aserción está firmada para esa misma solución. Valida emisor, audiencia, vigencia, usuario, tenant, scope, método, ruta, digest del body exacto y clave de idempotencia. Los IDs no otorgan acceso por sí mismos. Los callbacks se envían al origen configurado y Platform valida la correlación antes de aplicar el evento.

| HTTP | Condición propuesta |
| --- | --- |
| 202 | Admisión completa o replay de bytes idénticos con la misma clave para la misma solución/tenant/usuario dentro de la ventana. El replay usa el recibo original y una aserción aún válida. |
| 400 | DTO inválido, incluida cardinalidad distinta de cinco, job repetido dentro del body o límite fuera de rango. |
| 401 / 403 | Credencial o aserción inválida / aserción válida sin permiso suficiente para la operación. |
| 409 | Clave idempotente reutilizada con otro body, colisión de un ID admitido o batch distinto del mismo usuario con otro activo. |
| 429 | Se superan cinco tenants activos o cinco usuarios activos del tenant. |
| 503 | Drenaje o capacidad operativa indisponible. |

Cada rechazo de admisión deja el batch sin efectos. Un 429 o 503 puede incluir `Retry-After` si Service conoce una espera estimable. Un cliente con respuesta perdida repite la clave y el body exacto y renueva la aserción cuando corresponda. Platform conserva la correlación entre IDs y actor. La vía de reconciliación posterior a la ventana de replay queda pendiente en C5.

## Progreso, resultados y retención

El evento propuesto incluye `eventId`, `batchId`, `jobId`, posición, secuencia por job, hora UTC de observación y tipo. El progreso usa etapa y métricas realmente observadas, con porcentaje opcional cuando exista información para calcularlo. Ejemplos de tipos sujetos a revisión son inicio, progreso, fin de ejecución pendiente de consolidación y terminal con referencia de snapshot u outcome de error.

La entrega puede repetirse. El consumidor deduplica y verifica secuencia. Una consulta que terminó en Engine puede quedarse pendiente de consolidación mientras corre la siguiente. El terminal con datos se publica después de materializar el agregado de `search_many` o un prefijo recuperable. Se conserva el outcome parcial y la selección de filas de Engine. Si el hijo muere y solo se recibió progreso, no hay snapshot recuperable para ese resultado. Estado y motivo para los jobs pendientes de ejecutar requieren aprobación.

Las propuestas de consulta, export CSV/XLSX, ACK, purga por TTL y recuperación se detallan en C5. El terminal de batch referencia el snapshot del job y la API autentica de nuevo antes de entregarlo. La recepción del callback y el ACK de datos son operaciones distintas.
