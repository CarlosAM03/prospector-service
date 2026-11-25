# ADR C1–C6 ratificadas · 2026-11-24

| ADR | Decisión ratificada | Implementación y gates |
| --- | --- | --- |
| C1 | Un POST batch de 1–5 jobs en FIFO. IDs CUID de Platform. API key más aserción firmada contextual. Retirada de POST individual. Solo el propietario lee o exporta. Operaciones técnicas delegadas mediante scope y binding al dueño/recurso. | API, esquemas y verificación de aserción. Gate A. |
| C2 | Commit atómico previo al 202. Cuotas 5 tenants × 5 usuarios × un batch de hasta 5 jobs. Replay 48 h antes de cuotas. SQLite durable WAL/FULL solo para metadatos. Nunca reejecutar después de restart. | Registro SQLite, coordinador y reconciliación. Gates A–C. |
| C3 | Un coordinador FastAPI, un proceso hijo Engine por batch activo, `search_many` una vez y candidato `030a82d63a499a8abe65352d282ccc9bbc076ff3`. Timeout 120 min desde inicio, 30 s cooperativos y 30 s de terminación/verificación. Retener capacidad si no se verifica cleanup. | Supervisor, IPC, worker y adapter. Gates B–D. |
| C4 | Progreso observable en tiempo real, estados de espera de consolidación y terminal sin prospectos. Usar únicamente agregado o prefijo entregado por Engine. Callback saliente a Platform. | Relay, máquina de estados y fake receptor. Gate C. |
| C5 | Datos comerciales en RAM. Snapshot por job con TTL 60 min, ACK separado de purga, CSV/XLSX mediante prospector-export. No preservar payloads comerciales entre reinicios. | Snapshots, export y expiración. Gates A y C. |
| C6 | Nginx y Service en dos contenedores principales, red privada, TLS, límites y un coordinador ASGI. Cuotas y FIFO son de Service. Readiness independiente de la saturación normal. | Docker, Nginx, despliegue y prueba de proxy. Gate E. |

## Recuperación y autorización

Platform autentica, autoriza membresía y firma para cada operación. OWNER y ADMIN carecen de acceso automático por rol. Lectura y export requerirán scope, sujeto y tenant coincidentes, sin delegación. ACK y purga permiten una aserción técnica vinculada al propietario y al recurso. Respuestas de recurso ajeno y ausente son uniformes. El destino de callback es fijo por configuración.

La recuperación conserva los recibos y estados administrativos. Un reinicio interrumpe lo que pudo empezar y omite lo pendiente; los resultados perdidos pasan a UNAVAILABLE. Si los procesos anteriores no pueden declararse limpios, no se reabre el plano de ejecución hasta verificar el entorno. Toda evidencia de progreso sigue siendo distinta de una prueba de resultados materializados.

Los detalles de interoperabilidad definidos en el [contrato](../contracts/batch-api.v1.md) son elecciones técnicas para revisión. Cambios de política de autorización, de durabilidad comercial, de capacidad o de topología requieren aprobación del propietario.
