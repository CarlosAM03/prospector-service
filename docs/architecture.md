# Arquitectura inicial implementada

HTTP FastAPI -> DTO -> JobService -> registry/asyncio.Queue -> worker -> un único
ThreadPoolExecutor -> EngineAdapter -> prospector_engine público. CallbackClient es
HTTP saliente a Platform; export_results consume prospector_export público. No hay
scraping, normalización, deduplicación o persistencia SaaS en Service.

Engine se obtiene por Git SHA exacto publicado 70f6081688db5c5bc5ea612f5fabd5724aab0b20.
Export se obtiene del commit Service 0494f2b385e38c6a83202290a13fab33e345c7c4,
subdirectorio packages/prospector_export, que permanece disponible para desarrollo.
Ambas dependencias se instalan como paquetes separados. Los wheels no usan sys.path,
CLI, rutas personales ni importan internals del Engine.

## Ejecución y consistencia local

Una coroutine consume Jobs y envía QUEUED/RUNNING/terminal en orden. La ejecución
síncrona y observación del Engine ocurren en un solo thread dedicado; no bloquean
el event loop ni se ejecutan en una ruta async. El scope de observabilidad/cancelación
se abre dentro de ese thread. Los stages se registran sin texto de consulta/negocios;
progress=null hasta acordar una política global. No hay BackgroundTasks ni workers paralelos.

La admisión usa lock local y put_nowait; registra y encola antes del 202. Duplicate
jobId global del registry devuelve 409, incluso para otro tenant del mismo Platform.
lookup interno exige tenant+job; no se expone lectura HTTP de resultados. El tenant
se vincula al request autorizado por API key, sin asumir que esa credencial sustituye
JWT/RBAC del usuario final. Platform sigue siendo la frontera pública.

Cola: 16 pendientes; registry: 100 aceptados incluidos completados; request: 64 KiB;
resultados serializados: 1 MiB por Job. Son defaults iniciales configurables.
El registry guarda request, eventos y resultados hasta reinicio; no elimina resultados
ni aplica TTL unilateralmente. Al agotarse capacidad, 503. El overhead de objetos,
Engine/browser y copias de serialización no está incluido en el límite de bytes.
No se promete RAM fija ni disponibilidad tras reinicio.

Los fallos del Engine se traducen a códigos seguros. Errores recuperables/resultado
parcial siguen las semánticas del Engine; un retorno válido puede completar con
menos registros. No se reconstruye Business/NormalizedBusiness ni se mezclan vistas.
Los errores fatales no incluyen causa/paths/trazas ni contenido obtenido de sitios.
Un error de runtime deshabilita nuevas aceptaciones hasta reiniciar/verificar despliegue.

## Apagado y fallos

Se deja de aceptar; se intenta drenar durante shutdown_grace_seconds. Si no termina,
se solicita CancellationToken a Jobs pendientes/activos y se espera el cleanup real:
CANCELLED es un outcome interno de shutdown, no un nuevo protocolo HTTP.
Una llamada Playwright bloqueante puede exceder esa gracia. No se mata ni abandona
el thread; un supervisor puede terminar forzosamente y perder estado, por ser no durable.
Un fallo interno no recuperable del worker cierra admisión; shutdown no espera para
siempre el contador de una cola cuyo worker ya terminó. Los Jobs pendientes de tal
fallo no tienen garantía durable ni replay: se necesita una decisión de persistencia.

Callback delivery tiene reintentos acotados; cada evento es inmutable y se serializa
una sola vez para todos sus intentos. 401/4xx/redirecciones no se reintentan; red/timeouts,
408/429/5xx sí. Tras fallo final se registra estado local de entrega y se continúa la
ejecución; no se convierte un resultado de Engine correcto en FAILED por transporte.
No hay outbox, reentrega posterior ni garantía exactly-once. Platform puede perder un
evento o recibir una secuencia con huecos; ratificar operación productiva antes de habilitar.

## Runtime y readiness

Al iniciar, si configuración/auth están completas, se instancia Engine y se abre/cierra
un browser real mediante prospector_engine.browser.BrowserRuntime, con set_content local.
No hay requests a Maps ni sitios externos. El resultado queda cacheado para readiness;
health también comprueba worker, configuración y capacidad actual. Un fallo runtime
posterior invalida la disponibilidad. No se abre un browser por cada health request.
Liveness sólo acredita proceso; readiness técnica no acredita aceptación productiva.

Default consumidor: Edge/visible, preservando baseline. El contenedor configura Chromium
headless explícitamente como plataforma de integración controlada. El navegador productivo,
sizing, aislamiento de sitios no confiables y concurrencia siguen pendientes.
Docker no root, cap-drop/no-new-privileges/shm recomendados, un proceso ASGI. No se afirma
que esto certifique Google Maps live ni el sandbox Chromium productivo.

No se implementan HTTP cancel/export ni un microservicio de exportación separado.
Los metadatos no aprobados son null. Backend/Flutter/CLI y source/tests Engine no se modifican.
