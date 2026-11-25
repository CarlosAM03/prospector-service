# Gates de Prospector Service v1.0.0

**Estado** candidato en revisión. Esta página conserva las mediciones históricas con Engine `030a82d63a499a8abe65352d282ccc9bbc076ff3`. La evidencia del pin endurecido, las pruebas protegidas y el escaneo de imagen se registran por separado en [Convergencia Service–Engine](engine-convergence-v1.md).

| Gate | Evidencia y reproducción |
| --- | --- |
| A · Contrato y seguridad | `pytest tests/test_api.py tests/test_contract.py tests/test_config_and_architecture.py`. Cardinalidad 0–6, límites, IDs, binding, acceso delegado, replay y snapshot contractual histórico. |
| B · Admisión concurrente | `pytest tests/test_jobs.py` usa barreras lógicas. `pytest tests/test_runner.py` usa procesos Linux con fake. Observa 25 RUNNING y 100 QUEUED si los 25 hijos alcanzan el primer job. |
| C · Eventos y recuperación | `pytest tests/test_callbacks.py tests/test_runner.py`. Progreso antes de completar, retry bytes estables, estados, recuperación, cleanup, prefijo, pérdida RAM, TTL, ACK, purga y ausencia de sentinelas comerciales en SQLite/WAL. |
| D · Chromium controlado | `python -m scripts.benchmark_chromium --max-lanes 25` en Linux dentro de los límites propuestos. Escalones 1/2/3/5/10/15/20/25. Usa adquisición controlada Chromium con páginas HTML locales, sin llamadas a Maps. |
| E · Proxy y despliegue | `python scripts/container_smoke.py --image prospector-service:ci` y `python scripts/nginx_smoke.py --image prospector-service:ci`. Prueba TLS, body, misma IP, replay, callbacks por Nginx hacia un receptor fake, reinicio y datos volátiles. |

El benchmark registra muestras de CPU, RSS/PSS, PIDs y FDs, memoria cgroup, shm, concurrencia observada del navegador, latencias, duración, callbacks y cleanup. Avanza con resultados correctos y margen de recursos, y registra los escalones pendientes como NOT_RUN si se detiene. Un escenario sintético que pasa con 25 batches sigue sujeto a validación con el perfil de producción y con el backend real.

Los resultados de GitHub Actions deben corresponder al SHA de la rama revisada. [Draft PR #2](https://github.com/CarlosAM03/prospector-service/pull/2)

## Resultados registrados el 24 de noviembre de 2026

- **A–C.** En `316e1ede6217cee4b85287c2ea6a12175753d5b8` pasaron calidad, unitarias y contrato en Python 3.11 y 3.13, integración en Ubuntu y Windows, y build e instalación del paquete. En el job Ubuntu 3.11 pasaron ocho pruebas de integración, incluida la barrera de **25 procesos Linux con fake, 25 RUNNING y 100 QUEUED**. Los tests de subprocess se omiten en Windows por diseño. [Service CI, corrida 8](https://github.com/CarlosAM03/prospector-service/actions/runs/45538562576)
- **D.** Chromium real en Docker Desktop Linux, con 4 CPU, 4 GiB de RAM, 1 GiB de shm y sin red. Los escalones 1, 2, 3, 5 y 10 completaron todos los jobs y volvieron a cero descendientes. Con 10 batches se materializaron 50 snapshots en 51,391 s, con 2,25 GB de pico cgroup y 3,93 CPU medias muestreadas. El escalón 15 agotó los 180 s del fixture. Los escalones 20 y 25 quedaron NOT_RUN. El conteo inicial incluía auxiliares de Chromium y no acredita el pico de navegadores simultáneos. La primera corrida tuvo un problema de selección de canal en el fixture y se repitió con Chromium explícito. [Mediciones y límites](chromium-controlled-v1.json)
- **E.** El smoke de contenedor pasó en la corrida 8. El primer smoke Nginx falló porque el fixture podía emitir el terminal antes de que Nginx entregara la métrica coalescible. El fixture corregido esperó el progreso observado. La repetición local por TLS pasó con 25 POST desde la misma IP, callbacks a Platform fake, rechazo de body grande, upload truncado sin segunda ejecución, replay, ausencia de sentinelas comerciales en SQLite y pérdida de RAM tras reinicio. Comando `python scripts/nginx_smoke.py --image prospector-service:v1-candidate`.

La repetición corta con el contador corregido observó picos de 1, 2 y 3 navegadores principales en sus escalones respectivos, sin descendientes tras cleanup. También pasaron nueve pruebas locales adicionales de IPC, timeout cooperativo/forzado con un proceso separado de su grupo, recuperación, callbacks y contrato. `docker compose config --quiet` validó la sintaxis de la topología con valores de prueba.

La corrida 9 de Service CI pasó completa en `3979f16a1e5b29902efcc22318ab32bff2a422cd`, incluido el smoke Nginx corregido, Python 3.11/3.13 en Linux y Windows, build e instalación del paquete. Una repetición local posterior de Pytest en Windows quedó bloqueada por falta de espacio en el volumen temporal. [Service CI, corrida 9](https://github.com/CarlosAM03/prospector-service/actions/runs/45539590134)

En un segundo perfil de 8 CPU y 5 GiB, los escalones 1/2/3/5/10 completaron todos los jobs. Con 10 batches se observaron 9 navegadores principales simultáneos, 50 snapshots en 26,847 s, 2,04 GB de pico cgroup y cero descendientes tras cleanup. Durante el escalón 15, Docker Desktop respondió HTTP 500 a la consulta de estado y luego informó que estaba detenido. Ese escalón quedó inconcluso. No se estableció la causa del paro ni hay mediciones de 20/25. [Dos perfiles y mediciones](chromium-controlled-v1.json)

## Diferencias respecto al baseline

Se retiró POST individual y se añadió OpenAPI batch propio, sin editar el contrato histórico. SQLite conserva solo los recibos y estados administrativos. Los procesos Engine, callbacks asíncronos, snapshots volátiles, autorización por operación y Nginx sustituyen el flujo inicial de hilo y cola únicos. El adaptador de Platform sigue fuera de este repo.

## Gates pendientes antes de producción

Validar el receptor y firma de Platform reales, comprobar el perfil autorizado de Chromium con volúmenes de producción y ejecutar las etapas que quedaron faltantes con holgura. Revisar la cuarentena de cleanup tras crash y la separación de credenciales si se necesita un límite de seguridad físico. No hay certificación de 25 navegadores, resultados garantizados de Maps ni entrega de callbacks exactamente una vez.
