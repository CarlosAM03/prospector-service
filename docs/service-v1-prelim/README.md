# Prospector Service v1.0.0 · Fase preliminar 5×5×5

El propietario ratificó un Service HTTP privado por solución, con API key entre servidores. Platform autentica usuarios, autoriza por tenant y conserva históricos. Service admite de forma atómica cinco jobs ordenados por POST y responde 202 tras admitir el batch. Gestiona las colas, workers, progreso y resultados temporales. Engine sigue siendo una biblioteca síncrona independiente. Nginx se encarga de reverse proxy, TLS, límites HTTP y distribución de tráfico.

La capacidad objetivo es cinco tenants concurrentes, hasta cinco usuarios activos por tenant y un batch activo por usuario. Son 25 POST, 125 jobs y hasta 25 búsquedas RUNNING con 100 QUEUED en 25 FIFO independientes. El orden se aplica dentro del batch. La capacidad requiere demostración con fake y validación progresiva con Chromium real.

## Entregables

- [Auditoría, matriz baseline/gap, ADR C1–C6 y plan de pruebas](auditoria-y-adr.md)
- [Propuesta de contrato HTTP batch](contrato-batch-propuesto.md)
- [Resultados verificables del cierre](validacion.md)
- [Contrato individual vigente](../contracts.md)

## Estado de decisiones

| ADR | Pendiente de aprobar |
| --- | --- |
| C1 | Ruta y DTO batch, claves e IDs, aserción de tenant/usuario y scopes de acceso. |
| C2 | Idempotencia, política de cuotas y errores, durabilidad y coexistencia con la ruta individual. |
| C3 | Proceso dedicado por batch o contenedor por tenant, con límites respaldados por el benchmark. |
| C4 | Esquema de eventos, secuencias y terminales para parciales, interrupciones y jobs sin iniciar. |
| C5 | Retención por bytes y TTL, snapshots, ACK, purga, export, timeout y recuperación. |
| C6 | Límites y errores HTTP de Nginx, topología inicial y garantías de disponibilidad. |

## Implementación posterior

Primero cerrar C1–C6 y confirmar la distribución de Engine capaz de solicitar 150 negocios por consulta. Validar el coordinador con fake determinista en 25 lanes. Después integrar el Engine fijado con navegador controlado y ejecutar pruebas de contrato con Platform cuando su adaptador y receptor estén habilitados. Finalmente, probar el candidato por Nginx y escalar Chromium según los gates documentados.

Los riesgos principales son un reclamo de identidad insuficiente, recibos duplicados tras reinicios, callbacks bloqueantes, pérdida de resultados antes de consolidar `search_many`, procesos de navegador huérfanos y agotamiento de memoria, shm o PIDs al escalar. La auditoría especifica cómo probar cada caso y qué decisiones los afectan.
