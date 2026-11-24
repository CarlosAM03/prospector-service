# Auditoría de Prospector Service v1.0.0 y ADR C1–C6

**Auditoría** 2026-11-23. **Cierre documental** 2026-11-24 (America/Tijuana). El propietario ratificó el alcance 5×5×5. Los mecanismos concretos de C1–C6 siguen propuestos. [Índice del cierre preliminar](README.md)

Service es privado por solución. El objetivo es admitir 25 POST de cinco jobs para cinco tenants con cinco usuarios cada uno. Cada usuario tiene un batch activo y su propio FIFO. En el pico objetivo son 25 búsquedas RUNNING y 100 QUEUED. El diseño propone una llamada síncrona a `search_many` por lane, con cinco consultas ordenadas y límite solicitado de hasta 150 por consulta. El resultado real depende de la fuente. Engine se consume como biblioteca intacta. Nginx gestiona HTTP, TLS, límites y distribución de tráfico.

## Baseline y brechas

| Área | Evidencia local | Brecha para 5×5×5 |
| --- | --- | --- |
| Ingreso | `src/prospector_service/api.py:20–39`, `schemas.py:30–50`. API key con comparación de tiempo constante. Un POST `/api/v1/prospecting/jobs` acepta un job con `tenantId`, query y callback. El DTO local limita a 100 y el YAML solo declara mínimo 1. | Ruta aditiva, cinco entradas exactas, límite 150 explícito en el nuevo contrato, identidad de usuario verificable y correlación ordenada. |
| Admisión y ejecución | `jobs.py:37–95`, `config.py:19–28`, `__main__.py:15–24`. Registro global por `jobId`, cola RAM de 16 por defecto, registro de 100 incluido lo finalizado, un task y un hilo Engine. Duplicado da 409 y no hay replay. Un proceso ASGI. | Reserva todo-o-nada, 25 lanes bajo cinco unidades lógicas tenant, idempotencia y presupuesto agregado. Definir transición para el endpoint individual. |
| Engine y dedup | `adapters/engine.py:59–73` llama `search`; `adapters/results.py:8–40` mapea un resultado completo. `pyproject.toml:17` fija Engine en `70f6081688db5c5bc5ea612f5fabd5724aab0b20`. El objeto Git de ese pin ya contiene `search_many`, con máximo 100. El candidato `f7ccdc0` eleva a 150, declara `0.1.0.dev0` y el checkout carece de tags locales listados. | Gate de distribución Engine v1.0.0, SHA aprobado y smoke del wheel. Adaptar al resultado agregado y respetar `export_indices` de Engine. |
| Progreso y callbacks | `adapters/engine.py:62–69` registra eventos. `jobs.py:97–162` fija `progress=None` y espera la entrega de callbacks dentro del único worker. `adapters/callbacks.py:12–69` restringe destino y preserva bytes e IDs en los reintentos. El YAML exige porcentaje cuando existe progreso. | Relay de eventos reales separado de la ejecución, contrato sin porcentaje obligatorio y terminales tras materializar el agregado. |
| Retención y export | `jobs.py:25–34,93–95,125–162` guarda resultados y eventos en RAM, con límite de 1 MiB por resultado por defecto. `adapters/export.py` integra CSV/XLSX como librería. El router solo expone POST individual y sondas. | Snapshots independientes del worker con scope, TTL, ACK, purga, acceso a export y presupuesto de bytes. |
| Procesos y despliegue | `jobs.py:178–211` drena y solicita cancelación cooperativa durante el shutdown, con espera posterior sin plazo. `Dockerfile` ejecuta como UID 10001 y usa Chromium. `api.py:47–60` mezcla disponibilidad con saturación en readiness. | Supervisor de procesos y descendientes, prueba de cleanup y límites del host, readiness coherente, proxy reproducible. |
| Backend y autoridad de contrato | `Docs/Contracts/prospector-service-api.v1.yaml` en Backend y `docs/contracts/prospector-service-api.v1.yaml` en Service tienen SHA-256 idéntico `cb790bdecd3ca951f5abd382b4ef4178fb53576c9f1d913191a32b9fe9b62299`, coincidente con `authority.json`. `src/prospector-client/prospector-client.service.ts:5–22` deshabilita el adaptador. El receptor protegido de eventos tampoco procesa la entrega en el checkout. `TenantContextService` ya dispone de `userId` y `tenantId`. | Coordinar activación de productor y consumidor, y aprobación del YAML del Backend antes de copiar el snapshot a Service. No hay integración batch operativa. |
| Evidencia de pruebas | `tests/test_jobs.py:42` caracteriza ejecución serial y `tests/test_api.py`, `test_contract.py`, `test_callbacks.py`, `test_engine_and_results.py` y `test_export_integration.py` cubren el baseline. `.github/workflows/service-ci.yml` declara calidad, contrato, integración, build y smoke Docker. | Suite determinista de 25 lanes, prueba con procesos y suite HTTP contractual después de aprobar C1–C6. CI declarado no equivale a una corrida del candidato. |

Checkouts auditados read-only para código y contratos. Service `feat/fastapi-service-foundation` en `69c54a15601d238638610d0a5c08af46e3da7f14`. Engine `feat/engine-v1-limit-150` en `f7ccdc02c01e3f79a3ee0babea63fdd07f81de27`. Backend `feat/sprint-campana-prospector` en `81fa2652feec48ef853d0d3f61cf62ddd8d7f482`. Los archivos preexistentes fuera de Git se trataron como contexto, incluidos los reportes locales de Engine.

El cierre usa como base de Service `566bbbe67a59a0fda307ea7d8c5f6bf46fd93aab`, el `main` publicado al abrir la rama documental. El diff entre esa base y `69c54a1` solo contiene dos documentos históricos. Se verificó que no hay diferencias en código, dependencias, tests, workflows, imagen ni snapshot contractual. Las observaciones de Engine y Backend pertenecen a la auditoría del 23 de noviembre.

## C1. Contrato batch e identidad

**Propuesta.** Añadir `POST /api/v1/prospecting/batches` y conservar el DTO individual. Platform genera y registra antes del POST un `batchId` y cinco `jobId` CUID únicos en el espacio de la solución. Así puede correlacionar callbacks aunque lleguen antes de recibir el 202. El body propuesto es `{batchId, jobs:[{jobId,query}, ...]}` con cinco elementos exactos. La posición 0–4 se deriva del array. Cada `query` conserva `source=google_maps`, texto validado y `limit` entero 1–150. El destino se obtiene de la configuración de Service. La respuesta 202 propone el envelope vigente con `data={batchId,jobIds,status,acceptedAt}`, IDs en orden del POST, `status=QUEUED` como recibo de admisión y fecha UTC del commit. `Idempotency-Key` es obligatorio. Uso individual en transición según C2.

**Binding.** Platform deriva tenant activo y usuario de su contexto autenticado, verifica pertenencia vigente y permiso de prospección y genera una aserción firmada exclusiva para Service. La API key identifica la solución y es requisito de ingreso. La aserción en header interno separado aporta `iss`, `aud`, `sub` (usuario), `tenantId`, alcance `prospecting:batches:create`, `iat`, `exp`, método, ruta, clave de idempotencia y digest SHA-256 del body exacto. Service verifica firma con clave pública registrada para ese principal, algoritmo explícito, emisor, audiencia, vigencia con tolerancia acotada, scope y coincidencia con la solicitud. Validar el contexto y el DTO antes de reservar. Las operaciones de snapshot, ACK y export aplican el mismo patrón con scope propio y sobre el recurso solicitado. No confiar en `X-Tenant-Id`, `X-User-Id` ni JWT de navegador. En cada retry Platform puede emitir otra aserción sobre el mismo body y la misma clave. Validarlo incluso si hay replay. En rutas de lectura, responder de forma uniforme ante recurso inexistente o fuera de scope. Un actor administrador sin tenant efectivo no puede iniciar un batch.

**Impacto.** La firma liga la autorización de Platform a una operación concreta. La autoridad sobre membresías permanece en Platform. Platform valida también que los IDs de callbacks pertenezcan a su registro y al batch correlacionado. Publicar el delta OpenAPI y probar paridad del snapshot después de la aprobación.

El [borrador HTTP](contrato-batch-propuesto.md) reúne el ejemplo de petición y recibo, errores, reglas de replay y propuestas de eventos para revisión.

## C2. Admisión, cuotas e idempotencia

**Propuesta.** Un solo coordinador y un almacén transaccional local persistente como primera opción para conservar recibos y reanudar entregas tras reinicio del proceso. Una transacción breve comprueba idempotencia, unicidad y cuotas y registra cinco jobs, el lease de capacidad y el recibo. El lanzamiento se dispara tras commit y se reconcilia si falla antes de despachar. ACK HTTP 202 solo tras commit, sin esperar spawn, scraping ni callback. Prevalidar todo el array. Sin espera fuera de un batch admitido cuando el presupuesto esté agotado.

- Scope de idempotencia `(solución, tenant, usuario, Idempotency-Key)`. Mismo body byte a byte dentro de ventana devuelve el recibo 202 original, aun con la lane ocupada o ya cerrada. Mismo scope y clave con otro body devuelve 409. Comparar antes de cuotas. `batchId` y `jobId` reutilizados en otra admisión devuelven 409 genérico.
- Dos POST distintos para una misma pareja tenant/usuario activa compiten bajo la misma transacción. La propuesta devuelve 409 al segundo. Se recomienda 429 para un sexto tenant activo o sexto usuario activo en un tenant, y 503 para drenaje o reserva física indisponible. Usar `Retry-After` cuando exista una espera estimable. Proponer 400 para datos inválidos, 401 para credencial o aserción inválida y 403 para scope insuficiente.
- Un tenant cuenta mientras tenga alguna lane reservada. Una lane permanece reservada hasta la finalización registrada y el cleanup confirmado, independientemente del ACK de datos. Mientras el proceso arranca, hay cinco jobs pendientes. Al empezar la primera consulta se observa 1 RUNNING + 4 QUEUED; globalmente 25/100 si coinciden los 25 inicios.
- Proponer que el despliegue batch mantenga el contrato de la ruta individual pero deshabilite su admisión por configuración, con el 503 vigente para indisponibilidad. Si Platform necesita coexistencia, aprobar cómo se acredita usuario también en legado y cómo se comparte el mismo techo de capacidad.

**Recuperación.** Persistir una marca de inicio antes de ceder el batch al hijo. Al reiniciar, completar el despacho de filas cuya ejecución aún no se autorizó. Los casos de inicio incierto se cierran con el outcome de interrupción acordado, tras verificar la terminación del runtime anterior. Evitar reejecución automática de una extracción con inicio posible. Reanudar la entrega de eventos ya confirmados mediante outbox. La garantía propuesta cubre reinicio del proceso con el volumen disponible. Pérdida del host o volumen exige otra política. Una opción RAM exigiría aceptar explícitamente pérdida de recibos, resultados e idempotencia al reiniciar.

## C3. Aislamiento y operación de workers

**Propuesta.** Una unidad lógica por tenant y un proceso hijo dedicado por batch activo, hasta cinco por tenant y 25 en la instalación. Cada hijo crea su Engine y ejecuta `search_many` una vez. En Engine, el runtime de navegador se abre y se cierra por consulta, y un navegador puede implicar varios procesos OS. IPC con mensajes acotados, identificador de ejecución y secuencia. El coordinador posee identidad, admisión, estados, callbacks, snapshots y supervisión. El hijo recibe consultas y canal asignado, sin credenciales de ingreso ni de callback. Aislar temporales y confinar el árbol de procesos mediante el mecanismo del host de destino. Confirmar que no queden hijos antes de reciclar la capacidad, incluso tras timeout o crash. En Linux probar terminación del grupo o cgroup y recolección de procesos huérfanos. Validar el mecanismo equivalente si Windows entra al alcance.

**Alternativa.** Contenedor por tenant con cinco procesos, con límites y separación de filesystem/red por tenant. Añade gestión de imágenes, arranque, memoria base y operación. Seleccionar con mediciones de C3 y requisitos de aislamiento del cliente. Un proceso OS ofrece separación de runtime y fallas. La protección ante un hijo hostil exigiría un límite de seguridad adicional. No fijar tamaño de host por multiplicar el RSS de un Chromium aislado.

| Opción pendiente | Creación y destrucción | Límite que debe demostrarse |
| --- | --- | --- |
| Proceso por batch, dentro del despliegue Service | El supervisor reserva, crea el hijo, pasa consultas y recibe el agregado. Al terminar, espera salida y confirma la liberación de browser, pipes y temporales. | El hijo no hereda secretos y la carga de una lane no agota la memoria, PIDs, FD, IPC ni temporales de las demás. |
| Contenedor por tenant con hasta cinco hijos | El supervisor dispone hasta cinco entornos tenant, activos mientras tengan trabajo reservado. Drena y destruye cada entorno cuando ya no tenga hijos ni leases activos. | Límites explícitos por entorno más presupuesto global. Medir tiempo de arranque, reclamación de disco y tiempo de recuperación tras fallo. |

## C4. Progreso en tiempo real y terminales

**Propuesta.** Abrir `observe_execution` dentro de cada hijo. Usar `execution_started` con `stage=query` e índice cero-based para mover el cursor de ejecución; asignar eventos internos que carecen de índice a la consulta vigente dentro de esa invocación. Consumir etapas, métricas y contadores con una lista permitida y conservar origen y timestamp. `execution_completed/failed` de la consulta confirma que su ejecución terminó. El coordinador libera ese RUNNING internamente y mantiene el job a la espera de consolidación mientras arranca el siguiente. Exponer esa transición como evento de fase si se aprueba, para que Platform pueda distinguir ejecución de disponibilidad de datos.

El observador deposita mensajes ligeros sin esperar HTTP. El relay publica progreso durante el batch, con cola acotada, coalescencia de métricas repetitivas y medición de descartes. Proteger las transiciones en un canal prioritario y reconciliar tras pérdida del canal. Usar un stream de callback ordenado por job, con secuencias crecientes, reintentos con identidad y bytes estables, y envíos en paralelo entre lanes mediante un pool acotado. Proponer un schema de evento batch aditivo con porcentaje opcional, `kind`, etapa, métricas y correlación. Solo publicar cantidades observadas con la semántica que emite Engine. Mantener las métricas del agregado a nivel de batch. El receptor deduplica por evento y secuencia. El progreso solo puede afirmarse en vivo cuando se observa recibido mientras Engine sigue ejecutando.

**Límite verificado.** En Engine `engines/prospector_engine.py:75–165` los eventos de fin de consulta se emiten durante el bucle, con métricas e índice, sin payload de resultados. `search_many` devuelve `BatchSearchResult` al final. Si levanta `BatchInterruptedError`, expone un prefijo previo en `completed`, la consulta interrumpida y las restantes. Los terminales Service con datos salen tras recibir y materializar ese agregado o prefijo. Si el proceso muere sin devolverlo, los eventos previos solo prueban progreso; no se pueden recuperar resultados de ese proceso a partir de los eventos. Una falla tipada recuperable puede ocupar una entrada y permitir que Engine continúe. Proponer terminal de éxito con snapshot y calidad `SUCCESS/SUCCESS_WITH_ISSUES/PARTIAL`, fallo tipado para entrada `FAILED` y cancelación o fallo de infraestructura para interrumpidas u omitidas según causa, con motivo explícito y sin simular RUNNING. Este último caso exige aprobación porque el YAML actual describe transiciones vía RUNNING. Materializar solo las filas ordenadas por `export_indices` y conservar métricas de dedup verificada. Platform mantiene dedup histórico.

## C5. Snapshots, retención y fallos

**Propuesta.** Materializar snapshots inmutables por solución/tenant/usuario/batch/job antes de publicar terminales que los referencien. Outbox desacoplado por evento. Presupuestar bytes de snapshots, export concurrente y eventos pendientes además de 125 × 150 = 18 750 observaciones solicitadas en una oleada. Limitar cardinalidad y evaluar peso real en memoria y disco, incluido el pico de serialización. Ofrecer consulta/export CSV/XLSX y ACK explícito con autenticación y scope de C1. Export sigue la selección de Engine. ACK idempotente después de que Platform haya guardado lo que necesita. Coordinar ACK/TTL por transacción y permitir que una lectura ya autorizada termine aun si se purga la referencia, dentro de un plazo acotado. Retener recibos y marcas mínimas de idempotencia aparte de resultados.

Para aprobación, punto de partida de laboratorio de 24 h para snapshots desde la materialización, ventana separada de 48 h para recibos desde admisión y reintentos acotados dentro de la disponibilidad del snapshot. Proponer terminal con referencia al snapshot para la ruta batch, con reconciliación autenticada tras fallo de entrega. Limitar cronogramas de borrado y almacenamiento según volumen acordado. Si el presupuesto se agota, suspender nuevas admisiones sin invalidar las aceptadas.

**Timeout y readiness.** Proponer 2 h por ejecución de batch desde autorización de inicio, cancelación cooperativa y un plazo de gracia medido antes de terminar el árbol del proceso. Separar tiempo admisión→inicio, ejecución y cleanup. `/health/live` reporta el proceso y `/health/ready` si el plano de control está operativo, configurado y fuera de drenaje. Saturación ordinaria se comunica en admisión con C2. Si se cae un hijo, reconciliar su batch, verificar cleanup y mantener operativas las otras lanes cuando el supervisor esté sano.

## C6. Nginx y despliegue

**Propuesta.** Arrancar con Nginx privado y un gateway ASGI bajo un solo coordinador de admisión, supervisión e idempotencia. Proteger el upstream por red interna y TLS según tramo; separar credenciales de ingreso, firma de aserciones y callback. Nginx limita body y conexiones HTTP, aplica TLS y puede repartir tráfico entre réplicas cuando exista coordinación aprobada. Configurar límites que soporten una ráfaga legítima de 25 POST desde una IP de Platform, más tráfico de salud; alinear body máximo con la validación de Service, timeouts con el objetivo de admisión y buffering con el tamaño real. No reintentar POST ambiguos en el proxy. Probar errores de proxy y su distinción del envelope de Service. El FIFO corresponde al orden del array dentro de Service.

Una réplica ASGI con memoria propia crea otro registro. Para redundancia futura, requerir un único estado autoritativo, reserva atómica, ownership con fencing, outbox, recuperación y pruebas de split-brain antes de cambiar upstreams. Verificar en laboratorio el despliegue non-root, perfil seccomp, capabilities mínimas, cgroups/PID/FD y `/dev/shm`. Fijar digests y registrar inventario y hallazgos SCA de aplicación e imagen contra versiones efectivamente instaladas.

## Plan reproducible

1. **Reproducir el baseline.** En cada checkout guardar `git rev-parse HEAD` y `git status --short --branch`. Comparar los YAML con `Get-FileHash -Algorithm SHA256`. En Service, usar Python 3.11 y una venv con acceso a las dependencias fijadas. Ejecutar los comandos del workflow. Guardar hora, salida y código de retorno por comando.

   ```powershell
   python -m pip install -c requirements/constraints.txt -e '.[dev]'
   python -m ruff check .
   python -m ruff format --check .
   python -m pytest -q -m 'not integration and not browser and not contract'
   python -m pytest -q -m contract
   python -m playwright install chromium
   python -m pytest -q -m 'integration or browser'
   ```

2. **Prototipo aislado con fake.** Tras esta auditoría, diseñar un ejecutor que reciba cinco entradas etiquetadas y emita el contrato interno del observador. Usar reloj controlable, barreras, proceso fake lanzable y un receptor de callback configurable. Construir IDs y calendario de fallos desde fixtures fijos. Arrancar 25 clientes con una barrera común; congelar el primer job de cada proceso hasta observar todos los recibos y estados. Comprobar el pico por barrera en lugar de inferirlo de tiempos o depender de `sleep`. Repetir en varias planificaciones con semilla registrada. El spike valida invariantes; la versión HTTP depende de C1–C6. La suite existente sigue siendo regresión de legado.

3. **Cerrar contrato y dependencia.** Con las decisiones aprobadas, preparar proveedor/consumidor y el delta YAML en el repo autoritativo. Verificar el artefacto Engine v1.0.0 y su SHA, instalarlo aislado y ejecutar una consulta controlada con 150, una invocación batch de 1–5 y el rechazo de 151 antes de I/O. Agregar pruebas de contrato contra el snapshot sincronizado de Platform y la respuesta real de su receptor. El receptor baseline deshabilitado puede servir como control negativo de 503.

4. **Prueba extremo a extremo del candidato.** Usar un origen local controlado, Chromium real y casos reproducibles de errores y contenido. Validar la ruta privada pasando por Nginx, el scope de lecturas, el lifecycle, la recuperación, el volumen de resultados y el cleanup antes del benchmark escalonado. Registrar evidencias por SHA, imagen, configuración y semilla.

### Pruebas fake de 25 lanes propuestas

| Prueba | Entrada y comprobación observable | Estado |
| --- | --- | --- |
| T1 | 1 tenant, 5 usuarios, 5 jobs por POST. Los cinco recibos llegan con la barrera cerrada. Pico 5 RUNNING + 20 QUEUED. | NOT_RUN |
| T2 | 5 tenants, 1 usuario por tenant. Bloquear un tenant y terminar en los otros cuatro. Abrir otra lane en el tenant bloqueado y comprobar independencia también dentro del tenant. | NOT_RUN |
| T3 | 25 POST lanzados juntos, 125 jobs. Los 25 recibos de cinco llegan antes de abrir la barrera. Medir 25 procesos fake distintos y verificar 25 RUNNING + 100 QUEUED. Un solo índice activo por batch. | NOT_RUN |
| T4 | Liberación de barreras en orden global variable. Los cinco inicios por batch conservan el orden del POST, cada ID aparece una sola vez y todos los datos llevan la correlación de su dueño. Una lane lenta o callback caído no bloquea el avance de otra. | NOT_RUN |
| T5 | Segundo batch del mismo usuario, 6.º tenant/usuario, job duplicado, 4/6 entradas, límite 151, replay concurrente del POST y conflicto de digest. Probar claims vencidos, firma/audiencia/clave incorrectas y cambio de tenant, usuario, llave o body. Comprobar cero mutaciones ante rechazo y una sola reserva para el replay. | NOT_RUN |
| T5b | Asesinar un hijo después de progreso y antes del agregado. Simular excepción tipada con prefijo, error de spawn, interbloqueo, salida tras capturar terminal y reinicio a ambos lados del commit. Verificar cleanup, liberación de slots, reanudación de outbox y ausencia de terminal de éxito sin snapshot. | NOT_RUN |
| T7 | Recibir progreso verificable antes de liberar el fake. Demorar el receptor y probar orden, reintentos, coalescencia y lag. Probar TTL y ACK simultáneos con export, aislamiento por usuario/tenant, CSV/XLSX y fixture de 18 750 filas sintéticas. Usar entradas fake con `export_indices` conocidos para probar la adaptación, y Engine real controlado para validar la dedup. | NOT_RUN |
| T8–T9 | En candidato integrado, probar 25 POST por Nginx desde una IP, body y TLS, semántica del timeout HTTP, non-root y paridad del YAML y SHA/versiones. | NOT_RUN |

### Benchmark progresivo con Chromium real

**Preparación.** Ejecutar en Linux de laboratorio representativo con imagen y Engine fijados por digest/SHA, origen controlado y receptor de callbacks instrumentado. Registrar vCPU, RAM, cgroups, swap, `/dev/shm`, límite PID y FD, almacenamiento, versión de browser, región y perfil de red. Registrar tamaño y distribución de payloads y si la corrida incluye enriquecimiento web. Empezar con cinco consultas sintéticas por batch, cada una con límite 150 y fixture reproducible con casos parciales y duplicados. Tráfico a una fuente externa queda sujeto a autorización y presupuesto de esa fuente. La suite fake y los smokes no certifican ese perfil.

| Lanes objetivo | Reparto tenants × usuarios | Estado |
| --- | --- | --- |
| 1 / 2 / 3 | 1 tenant con 1 / 2 / 3 usuarios | NOT_RUN |
| 5 | 1 tenant con 5 y, en corrida aparte, 5 tenants con 1 | NOT_RUN |
| 10 / 15 / 20 / 25 | 2 / 3 / 4 / 5 tenants con 5 usuarios | NOT_RUN |

En cada escalón ejecutar una oleada en frío y al menos tres en caliente en el mismo perfil, además de oleadas repetidas para detectar tendencia de retención. Medir concurrencia **observada** de workers y browsers, hijos por browser, CPU pico y sostenida, RSS/PSS y memoria de cgroup, `/dev/shm`, PID/FD, I/O, tamaño de snapshots/exports, OOM y fallos por causa. Medir HTTP de aceptación p50/p95/p99, latencia admisión→inicio, duración por query/batch, lag de callback (evento observado→recepción), descartes, retraso de terminales, tiempo de cleanup y memoria al volver al reposo. Agregar muestras de varias oleadas para interpretar percentiles, reportar su cantidad y resolver timestamps con reloj coherente. Si los 25 browsers no coinciden, declarar pico observado y alcance demostrado.

**Gate de avance.** Antes de iniciar, registrar objetivos de admisión/lag y márgenes de CPU, memoria, shm, FD y PID del host. Una etapa avanza con objetivos cumplidos, holgura para el siguiente escalón, sin OOM, mezcla, pérdida de admisiones ni huérfanos y con recuperación a reposo. Al fallar, mantener los escalones pendientes como NOT_RUN y registrar la causa y capacidad observada. Separar fallos del host de fallos de la fuente. Para costo, seleccionar la menor configuración que cumpla estos gates y estimar `horas de disponibilidad × tarifa del host + volumen + egreso + observabilidad`. En despliegue permanente usar las horas reales de servicio del mes. Faltan mediciones de host, región y tarifa para cuantificar.

## Dudas que requieren decisión de contrato

1. **C1.** Confirmar IDs emitidos por Platform, CUID y envelope, header/scope/claims de aserción y quién puede consultar o acusar recepción de datos además del usuario dueño.
2. **C2.** Aprobar replay 202, semántica 409/429/503 y garantía de reinicio con volumen persistente. Confirmar si la ruta individual queda disponible durante rollout y cómo contabiliza las cuotas en ese caso.
3. **C4.** Aprobar schema o versión de callback batch sin porcentaje obligatorio, fase de consolidación, política de secuencias y terminales para parciales, interrumpidos y nunca ejecutados.
4. **C5.** Fijar TTL de snapshot y recibo, ACK/purga, endpoints y autorización de export/reconciliación, reintentos y alcance del timeout de dos horas. Confirmar si Platform acepta referencias a snapshots en el terminal.
5. **C6.** Confirmar envelope esperado cuando rechaza el proxy y requisitos de disponibilidad/recuperación del despliegue inicial. El reparto físico de C3 se valida con el benchmark y los límites de aislamiento exigidos por la solución.

## Evidencia de la auditoría del 23 de noviembre

Lectura de código, tests, configuración y workflow en los tres HEAD indicados. Comparación SHA-256 de ambos YAML con `Get-FileHash` y consulta del pin de Engine con `git cat-file` y `git grep`. Estas comprobaciones establecen la paridad del snapshot y el máximo 100 del pin. **PASS estático local** con `python.exe -B -` de Thonny y PyYAML sobre ambos YAML, sin levantar el servicio. Se verificaron igualdad de bytes y hash autoritativo, rutas, campos obligatorios del job, ausencia de `userId`, límite del YAML y porcentaje obligatorio cuando hay progreso.

Docker respondió acceso denegado a su daemon en esta sesión. El alias local de Python no arrancó y el intérprete de Thonny reportó Python 3.10.11, por debajo del mínimo 3.11 de Service. La suite Service, el spike fake y todas las etapas del benchmark quedan **NOT_RUN**. El reporte local de Engine describe pruebas previas de su candidato.

El diff de Service y Backend contra sus HEAD quedó vacío. Durante esa auditoría apareció en el árbol de Engine una edición ajena en `docs/runtime.md` sobre la imagen base. Se dejó intacta. Las conclusiones sobre el Engine fijado se verificaron contra su objeto Git. Los gates del cierre se registran por separado en [validación](validacion.md).
