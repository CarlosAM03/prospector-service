Sí. Con el estado actual del Backend Platform y del cliente Flutter, podemos separar con bastante precisión qué parte de **Plataforma v1.0.0** está realmente bloqueada por el Prospector Service y qué parte todavía puede terminarse sin Python.

La conclusión principal es: **la mayor parte de la plataforma v1.0.0 ya no depende del servicio externo**. La dependencia está concentrada casi totalmente en el ciclo operativo de `ProspectingJob` y en las funciones que consumen sus resultados.

# Dependencias de Plataforma v1.0.0 respecto al Prospector Service

## 1. Lo que NO depende del Prospector Service

Todo este alcance puede considerarse independiente de Python:

```text
Auth
Tenants
Users
Campaigns
Prospects persistidos
Prospect manual create
CSV Import V1
Multi-tenancy
RBAC
PlatformApi
Dashboard basado en datos existentes
Jobs List de registros persistidos
Job Detail de registros persistidos
```

En otras palabras, el Service **no bloquea**:

- Login/logout/session.
- Cambio de tenant.
- Administración de tenants.
- Administración de usuarios.
- CRUD de campañas.
- CRUD de prospectos.
- Importación manual mediante CSV.
- Deduplicación de CSV V1.
- Dashboard simple.
- Jobs read-only.
- Deploy de NestJS.
- Deploy de Flutter.
- PostgreSQL.
- CI/CD.

Por eso André puede terminar:

```text
Dashboard real
Jobs List
Jobs Detail
CSV Import UI
```

sin esperar a Prospector.

---

# 2. Dependencia directa: creación real de Jobs

Actualmente existe públicamente:

```http
POST /api/v1/prospecting-jobs
```

pero Backend hace:

```text
validar JWT
validar tenant
validar DTO
validar Idempotency-Key
        ↓
ProspectorClient.assertAvailable()
        ↓
503 PROSPECTOR_INTEGRATION_PENDING
```

Para que la operación sea real, Platform necesita poder hacer conceptualmente:

```text
Flutter
   ↓
POST Platform /prospecting-jobs
   ↓
Platform crea Job
   ↓
Platform → Prospector Service
   ↓
POST /api/v1/prospecting/jobs
   ↓
202 Accepted
   ↓
QUEUED
```

Ésta es una dependencia **directa y bloqueante**.

### Pendiente Platform relacionado

- [ ] Activar `ProspectorClientService`.
- [ ] Implementar llamada HTTP Platform → Service.
- [ ] Configurar `PROSPECTOR_SERVICE_URL`.
- [ ] Configurar `PROSPECTOR_API_KEY`.
- [ ] Crear/persistir Job correctamente.
- [ ] Implementar semántica real de `Idempotency-Key`.
- [ ] Manejar aceptación `202`.
- [ ] Manejar errores del Service.
- [ ] Definir timeout.
- [ ] Definir retries seguros.
- [ ] Probar integración real.

Sin Prospector Service no puede cerrarse operacionalmente.

---

# 3. Dependencia directa: ejecución de la prospección

El contrato interno ya dice que el Service recibe:

```text
jobId
tenantId
query
callbackUrl
```

con:

```text
keyword
location
source = google_maps
limit
```

La ejecución:

```text
Google Maps
Playwright
BeautifulSoup
Engine
```

no pertenece a Platform.

La cadena correcta sigue siendo:

```text
Flutter
   ↓
Platform Backend
   ↓
Prospector Service
   ↓
Prospector Engine
   ↓
Google Maps / Web
```

Nunca:

```text
Flutter → Engine
```

ni:

```text
Platform → Engine directamente
```

Por tanto todo el scraping real está completamente fuera del Platform Backend.

---

# 4. Dependencia directa: callbacks de progreso

Platform ya tiene la ruta:

```http
POST /api/v1/internal/prospecting-jobs/{jobId}/events
```

y ya tiene:

```text
X-API-Key
DTO validation
InternalApiKeyGuard
```

pero actualmente un callback válido termina en:

```text
503 PROSPECTOR_INTEGRATION_PENDING
```

El contrato ya define eventos:

```text
eventId
jobId
sequence
status
progress
timestamp
results
error
```

Para v1.0.0 operacional falta procesarlos.

### Pendientes

- [ ] Aceptar callbacks reales del Service.
- [ ] Validar `jobId`.
- [ ] Validar `eventId`.
- [ ] Manejar `sequence`.
- [ ] Ignorar/rechazar eventos duplicados.
- [ ] Impedir regresión de secuencia.
- [ ] Aplicar transiciones de lifecycle.
- [ ] Persistir estado del Job.
- [ ] Actualizar `startedAt`.
- [ ] Actualizar `completedAt`.
- [ ] Persistir/gestionar error.
- [ ] Actualizar progreso temporal.
- [ ] Recibir resultados finales.

Esto depende directamente del Service porque alguien tiene que emitir esos eventos.

---

# 5. Estados reales de Jobs

Actualmente Platform puede almacenar estados, pero no existe ejecución que los produzca dinámicamente.

El lifecycle contractual es:

```text
QUEUED
   ↓
RUNNING
   ↓
COMPLETED
FAILED
CANCELLED
```

Mientras Prospector no exista, esos estados sólo pueden venir de fixtures/seed.

Por tanto, para v1.0.0 real dependen del Service:

- [ ] `QUEUED` generado por aceptación real.
- [ ] `RUNNING` generado por ejecución real.
- [ ] `COMPLETED` generado por ejecución terminada.
- [ ] `FAILED` generado por error real.
- [ ] `CANCELLED` coherente con ejecución real.

---

# 6. Progreso del Job

El contrato ya define:

```text
PipelineProgress
├── source
├── stage
├── message
└── percentage
```

pero Backend hoy responde siempre:

```json
"progress": null
```

Por tanto depende del Service:

- [ ] Generación de progreso.
- [ ] Envío de progreso.
- [ ] Recepción por Platform.
- [ ] Caché/estado temporal.
- [ ] Exposición en `GET /prospecting-jobs/{id}`.

Después de eso Flutter puede implementar polling útil.

---

# 7. Resultados temporales

Actualmente:

```text
resultsAvailable = false
results = null
```

incluso para un Job almacenado como:

```text
COMPLETED
```

El contrato interno define:

```text
BusinessResult[]
```

con:

```text
name
category
address
phone
email
website
source
sourceIdentifier
language
metadata
```

El origen de esos datos es el Service/Engine.

Por tanto dependen directamente de Prospector:

- [ ] Recibir `BusinessResult[]`.
- [ ] Mantener resultados temporales.
- [ ] `resultsAvailable=true`.
- [ ] Exponer resultados desde Job Detail.
- [ ] Asociarlos inequívocamente al job/tenant.

---

# 8. Caché real de resultados

La plataforma todavía no tiene cache productiva para resultados temporales.

Ésta es una dependencia interesante:

**la implementación técnica de la caché podría desarrollarse antes**, pero **no puede validarse operacionalmente sin resultados del Service**.

Flujo esperado:

```text
Prospector Service
       ↓ callback COMPLETED
BusinessResult[]
       ↓
Platform temporary results/cache
       ↓
GET Job Detail
       ↓
Flutter
```

Pendientes:

- [ ] Elegir implementación V1 de cache.
- [ ] Almacenar resultados por `jobId`.
- [ ] Aislar por tenant.
- [ ] TTL.
- [ ] Eviction.
- [ ] Cleanup.
- [ ] Comportamiento ante restart.
- [ ] Límites de tamaño.
- [ ] Pruebas de concurrencia.

### Clasificación

```text
Implementable sin Service: SÍ
Validable end-to-end sin Service: NO
Necesario operacionalmente antes de resultados: NO
```

---

# 9. Persist Results

Existe:

```http
POST /api/v1/prospecting-jobs/{id}/persist
```

Hoy responde 503.

Su función futura sería:

```text
Temporary BusinessResults
        ↓
Platform Backend
        ↓
validación
deduplicación
        ↓
Prospect
CampaignProspect
        ↓
PostgreSQL
```

La persistencia en sí ocurre en Platform, no en Prospector Service.

Pero no puede ejecutarse realmente si no existen resultados temporales.

Por tanto:

```text
Prospector Service
→ dependencia indirecta pero obligatoria operacionalmente
```

### Pendientes Platform

- [ ] Validar Job COMPLETED.
- [ ] Obtener resultados temporales.
- [ ] Mapear `BusinessResult → Prospect`.
- [ ] Deduplicar.
- [ ] Crear o vincular prospectos.
- [ ] Asociar campaña.
- [ ] Transacción.
- [ ] Resultado de persistencia.
- [ ] Idempotencia.
- [ ] Limpiar/actualizar cache después de persist.

Parte de esta lógica puede desarrollarse con fixtures antes de tener Service.

---

# 10. Export Results

Existe:

```http
GET /api/v1/prospecting-jobs/{id}/export?format=csv|xlsx
```

pero hoy devuelve 503 JSON.

La generación del archivo probablemente pertenece a Platform.

Por tanto técnicamente puede implementarse con fixtures.

Pero operacionalmente necesita:

```text
resultados reales del Job
```

producidos por Prospector.

Dependencia:

```text
Service
  ↓
results
  ↓
Platform
  ↓
CSV/XLSX
```

Pendientes:

- [ ] Export CSV.
- [ ] Export XLSX.
- [ ] MIME correcto.
- [ ] filename.
- [ ] aislamiento tenant.
- [ ] validar estado Job.
- [ ] resultado vacío.
- [ ] pruebas.

---

# 11. Cancelación

Éste es un punto especial.

La API pública de Platform tiene:

```http
POST /prospecting-jobs/{id}/cancel
```

pero el contrato interno actual **no tiene una ruta final de cancelación hacia Prospector Service**.

De hecho, la documentación dice que una ruta adicional de cancelación Python fue retirada del baseline.

Por tanto aquí no tenemos sólo:

```text
"falta implementar"
```

sino una **decisión de integración todavía no cerrada**.

Tenemos que definir cómo Platform ordenará al Service:

```text
cancel job X
```

Opciones conceptuales futuras:

```text
POST /prospecting/jobs/{id}/cancel
```

o algún mecanismo equivalente.

Hasta cerrar eso, no conviene implementar cancelación física real.

### Dependencia

```text
DIRECTA + DECISIÓN CONTRACTUAL PENDIENTE
```

---

# 12. Idempotencia persistente

`POST /prospecting-jobs` exige:

```http
Idempotency-Key
```

pero actualmente Platform:

```text
lo valida
pero no lo guarda
```

Para Jobs reales habrá que evitar que:

```text
doble tap
retry HTTP
timeout cliente
```

genere dos prospecciones distintas.

Esto podría implementarse en Platform antes del Service.

Pero la semántica final tiene que coordinarse con:

```text
aceptación del Prospector Service
```

para resolver casos como:

```text
Platform guardó Job
Service recibió
respuesta se perdió
cliente reintenta
```

Por tanto es una dependencia de integración, aunque no necesariamente de código Python.

---

# 13. Retries y timeout

Hoy ProspectorClient explícitamente no tiene:

```text
timeout operacional
retry
circuit breaker
```

Antes de producción real necesitamos definir:

```text
Platform → Service
```

### Timeout

¿Qué ocurre si Service tarda:

```text
2 s
10 s
30 s
```

en aceptar?

### Retry

Un retry automático de:

```text
POST create job
```

sin idempotencia puede duplicar trabajo.

Por eso el orden correcto es:

```text
idempotencia
   ↓
timeout
   ↓
retry policy
```

Estos temas dependen de conocer cómo se comportará el Service real.

---

# 14. Autenticación interna

El contrato ya define:

```text
X-API-Key
```

en ambas direcciones.

Platform → Service:

```text
X-API-Key
```

Service → Platform callback:

```text
X-API-Key
```

Backend ya tiene guard para callback.

Pero falta validar con el Service real:

- [ ] misma política de header.
- [ ] provisioning de secret.
- [ ] variables de entorno.
- [ ] comparación segura.
- [ ] rotación.
- [ ] comportamiento ante clave inválida.
- [ ] separación dev/prod.
- [ ] despliegue seguro del secreto.

Esto sólo puede cerrarse completamente con ambos servicios.

---

# 15. URL de callback

Platform enviará al Service:

```text
callbackUrl
```

Esto introduce otro requisito operativo.

En producción Service debe poder alcanzar:

```text
https://<platform>/api/v1/internal/prospecting-jobs/{jobId}/events
```

Por tanto habrá que validar:

```text
Prospector Service
       ↓ HTTPS
Render/NestJS
       ↓
internal callback
```

Eso requiere Service desplegado o un entorno equivalente.

---

# 16. Flutter que depende del Service

Del cliente Flutter, estas capacidades **sí dependen de Prospector**:

### Bloqueadas

- [ ] Generate Prospecting Job real.
- [ ] Mostrar progreso real.
- [ ] Polling de Job con cambios reales.
- [ ] Mostrar resultados temporales.
- [ ] Cancel Job real.
- [ ] Persist Results real.
- [ ] Export Results real.
- [ ] Discard temporal útil.
- [ ] Caché Riverpod de resultados por `jobId`.

### No bloqueadas

- [ ] Jobs List.
- [ ] Job Detail.

Esas dos deberían terminarse antes.

---

# 17. Lo que no debemos esperar al Service para implementar

No conviene convertir Prospector en un bloqueo artificial del proyecto.

Podemos terminar antes:

```text
CSV Import UI
Dashboard real
Jobs List
Jobs Detail
seed Jobs limpio
routing Jobs
tests Jobs read-only
```

También se puede adelantar mediante fixtures:

```text
callback processing
event sequencing
result cache
persist mapping
export generation
idempotency
```

si decidimos que vale la pena.

Pero no podremos llamar **integración cerrada** hasta ejecutar el sistema con Service real.

---

# 18. Dependencia real Service ↔ Engine

Hay además dos niveles distintos:

```text
Platform
   ↓
Prospector Service
   ↓
Prospector Engine
```

Para Platform v1.0.0, Platform **sólo debe conocer el Service**.

Por tanto:

### Platform depende del Service

Sí.

### Platform depende directamente del Engine

No.

### Service depende del Engine

Sí, para producir resultados reales.

Esto permite que el contrato Platform ↔ Service permanezca estable aunque internamente cambie:

```text
Playwright
BeautifulSoup
Selectors
Google Maps strategy
```

---

# 19. Mapa de dependencias de v1.0.0

La situación queda:

```text
PLATAFORMA V1.0.0
│
├── Auth                         ✅ independiente
├── Tenants                      ✅ independiente
├── Users                        ✅ independiente
├── Campaigns                    ✅ independiente
├── Prospects CRUD               ✅ independiente
├── Manual Prospect              ✅ independiente
├── CSV Import                   ✅ independiente
├── Dashboard simple             ✅ independiente
│
└── Prospecting Jobs
    │
    ├── List                     ✅ independiente
    ├── Detail persistido        ✅ independiente
    │
    ├── Create Job               🔴 Prospector Service
    ├── Execution                🔴 Prospector Service
    ├── Progress                 🔴 Prospector Service
    ├── Results                  🔴 Prospector Service
    ├── Callback lifecycle       🔴 Prospector Service
    ├── Cancel                   🔴 Service + decisión contractual
    │
    ├── Cache results            🟡 implementable antes / valida con Service
    ├── Persist results          🟡 Platform, pero necesita results
    ├── Export                   🟡 Platform, pero necesita results
    ├── Idempotency              🟡 Platform + integración
    └── Retry/timeout            🟡 integración real
```

---

# 20. Qué necesitamos del Prospector Service para desbloquear v1.0.0

El **mínimo Service viable** que yo exigiría no necesita implementar todas las optimizaciones futuras.

Debe poder hacer:

```text
POST /api/v1/prospecting/jobs
```

recibiendo:

```text
jobId
tenantId
query
callbackUrl
```

y responder:

```text
202

jobId
QUEUED
acceptedAt
```

Después debe poder emitir callbacks:

```text
QUEUED
RUNNING
COMPLETED
FAILED
```

con:

```text
eventId
sequence
timestamp
progress
results
error
```

y autenticarse mediante:

```text
X-API-Key
```

Con eso ya podemos desbloquear:

```text
Create Job
real lifecycle
progress
results
polling
cache
persist
export
```

La cancelación podría incluso quedar como el último punto porque su contrato interno necesita decisión adicional.

---

# 21. Orden que recomiendo desde este punto

Para no bloquear Plataforma v1.0.0:

```text
PLATFORM / FLUTTER
──────────────────
1. CSV UI
2. Jobs List/Detail
3. Dashboard real
4. seed Jobs corregido
       ↓

PROSPECTOR
──────────
5. Engine v1.0.0
6. Prospector Service mínimo
7. POST accept Job
8. callbacks lifecycle/results
       ↓

PLATFORM INTEGRATION
────────────────────
9. activar ProspectorClient
10. Create Job
11. callback processing
12. progress/results cache
13. polling Flutter
14. persist
15. export
       ↓

DECISIÓN FINAL
──────────────
16. cancelación física
17. idempotencia/retries/timeouts
18. smoke E2E completo
```

Eso significa que **no necesitamos esperar a Prospector para continuar cerrando Flutter**, pero sí necesitamos empezar ya a tratar Prospector Service como el siguiente gran bloque de integración si la meta es que **v1.0.0 incluya prospección automatizada real**, y no sólo gestión manual/CSV.

La frontera es muy clara: **sin Prospector Service podemos cerrar toda la plataforma administrativa; con Prospector Service desbloqueamos el núcleo de “prospección automatizada” que le da sentido al producto completo.**