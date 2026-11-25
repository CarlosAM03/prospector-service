# Gates de Prospector Service v1.0.0

**Estado** candidato en revisión. La rama de trabajo se basa en `98382eb501d61512b1409adf8855b662fd81b810`. El Engine fijado es `030a82d63a499a8abe65352d282ccc9bbc076ff3`, candidato con límite 150. La compatibilidad del consumidor y la preparación productiva requieren evidencia adicional.

| Gate | Evidencia y reproducción |
| --- | --- |
| A · Contrato y seguridad | `pytest tests/test_api.py tests/test_contract.py tests/test_config_and_architecture.py`. Cardinalidad 0–6, límites, IDs, binding, acceso delegado, replay y snapshot contractual histórico. |
| B · Admisión concurrente | `pytest tests/test_jobs.py` usa barreras lógicas. `pytest tests/test_runner.py` usa procesos Linux con fake. Observa 25 RUNNING y 100 QUEUED si los 25 hijos alcanzan el primer job. |
| C · Eventos y recuperación | `pytest tests/test_callbacks.py tests/test_runner.py`. Progreso antes de completar, retry bytes estables, estados, recuperación, cleanup, prefijo, pérdida RAM, TTL, ACK, purga y ausencia de sentinelas comerciales en SQLite/WAL. |
| D · Chromium controlado | `python -m scripts.benchmark_chromium --max-lanes 25` en Linux dentro de los límites propuestos. Escalones 1/2/3/5/10/15/20/25. Usa adquisición controlada Chromium con páginas HTML locales, sin llamadas a Maps. |
| E · Proxy y despliegue | `python scripts/container_smoke.py --image prospector-service:ci` y `python scripts/nginx_smoke.py --image prospector-service:ci`. Prueba TLS, body, misma IP, replay, callbacks por Nginx hacia un receptor fake, reinicio y datos volátiles. |

El benchmark registra muestras de CPU, RSS/PSS, PIDs y FDs, memoria cgroup, shm, concurrencia observada del navegador, latencias, duración, callbacks y cleanup. Avanza con resultados correctos y margen de recursos, y registra los escalones pendientes como NOT_RUN si se detiene. Un escenario sintético que pasa con 25 batches sigue sujeto a validación con el perfil de producción y con el backend real.

Los resultados de GitHub Actions deben corresponder al SHA de la rama revisada. [Draft PR #2](https://github.com/CarlosAM03/prospector-service/pull/2)
