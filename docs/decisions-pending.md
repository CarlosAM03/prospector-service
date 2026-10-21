# Decisiones reales del propietario

Ninguna de estas propuestas se convierte aquí en contrato vigente. El bootstrap y
sus gates continúan funcionando sin aprobarlas; Platform producción NO habilitado.

| ID / problema | Contrato afectado | Alternativas y riesgos | Recomendación | Trabajo disponible |
|---|---|---|---|---|
| S-01 Browser productivo | Runtime Engine/Service | Edge visible baseline vs Chromium Linux/headless; localhost no prueba Maps | Aceptación live acotada antes de elegir despliegue | Engine configurable, Docker y smoke controlado |
| S-02 Persistencia/TTL/resultados | Ciclo de Jobs y consulta/export futuras | Memoria sin recuperación vs almacén durable; pérdida al reiniciar, duplicados o fuga si falta tenant binding | Aprobar almacenamiento/TTL/eliminación y recuperación juntos; no añadir Redis por defecto | Registry acotado sin eviction/TTL, adaptador de exportación interno |
| S-03 Entrega de callbacks | ProspectingJobEvent | Reintento acotado actual vs outbox durable; pérdida/huecos si Platform falla | Ratificar orígenes, TLS, rotación/scopes, timeout/retry/backoff y recuperación | Cliente fail-closed probado con mocks; ningún request arbitrario |
| S-04 Validación de inputs | StartJobRequest/ProspectingQuery | Mantener YAML amplio vs máximo100/texto no vacío; Backend puede enviar valores rechazados | Ratificar límites del Engine en los repos dueños del contrato | Service rechaza 400 sin alterar consulta ni Backend |
| S-05 Progreso, issues y metadata | PipelineProgress/BusinessResult | null actual vs política global; inventar porcentajes o ampliar schema puede romper consumidores | Acordar mapping específico, mantener null hasta entonces | Observación interna real y siete campos + identidad verificada |
| S-06 Cancelación HTTP | No hay operación interna aprobada | Nuevo protocolo cooperativo vs diferir; browser bloqueante no termina instantáneamente | Definir semántica/estados/timeout antes de exponer endpoint | Cancelación sólo durante shutdown con token público |
| S-07 Exportación HTTP | No hay operación interna aprobada | Snapshot Service vs datos persistidos Platform; autorización/TTL/expiración distintos | Aprobar una propuesta completa; biblioteca no implica autorización de ruta | CSV/XLSX por adaptador Python, siete columnas |
| S-08 Concurrencia/cuotas productivas | Admisión/capacidad | Un worker inicial vs coordinación multiproceso/durable; duplicados y memoria | Medir sizing, límites por tenant y coordinación antes de escalar | Cola/thread únicos, 503 por saturación, configuración acotada |

La propuesta exportadora histórica en packages/prospector_export/docs/decisions-pending.md
sigue marcada PROPOSED — OWNER APPROVAL REQUIRED. Esta implementación no la aprueba.
La primera integración instalada Engine→Service sí se prueba aquí; no es habilitación
del adaptador NestJS ni aceptación de Google Maps productivo. Versión sigue 0.1.0.dev0.

Repo Engine conectado/main publicado/CI/ruleset se verifican en docs/testing.md y GitHub;
sus documentos de extracción previos conservan estado histórico por permiso de sólo
Git/workflows en Engine. No se reescribieron esos documentos ni se publicó release.
