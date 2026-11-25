# Gates del cierre preliminar

**Fecha** 2026-11-24 (America/Tijuana). **Base de código probada** `566bbbe67a59a0fda307ea7d8c5f6bf46fd93aab`. El cambio de esta fase se limita a documentación. Se usó Python 3.13.4 y un directorio temporal con paquetes de caché contrastados con `requirements/constraints.txt`. Los wheels de Engine y exportación se identificaron con sus `origin.json`, que apuntan a los SHA fijados en `pyproject.toml`. El plan para software futuro y sus estados están en la [auditoría](auditoria-y-adr.md).

| Gate local | Comando o comprobación | Resultado |
| --- | --- | --- |
| Compilación | `C:/Python313/python.exe -m compileall -q src`, con una copia temporal de `src` en ruta corta | PASS, 14 fuentes y 14 archivos de bytecode, salida 0. El intento en la ruta larga de Windows falló al escribir bytecode. |
| Ruff 0.17.1 | `ruff check .` y `ruff format --check .` | PASS ambos, salida 0. 59 archivos ya formateados. |
| Unit/API | `python -m pytest -q -m 'not integration and not browser and not contract'` | PASS, 81 pasaron, 13 deseleccionadas. |
| Contrato vigente | `python -m pytest -q -m contract` | PASS, 7 pasaron, 87 deseleccionadas. |
| Integración y navegador | `python -m pytest -q -m 'integration or browser'` | FAIL local, 5 pasaron, incluido smoke Chromium controlado, y 1 falló. El test de procedencia del Engine lee `direct_url.json`, que pip no genera al resolver desde un wheel del caché por nombre. El aserto del límite 101 se ejecutó antes de ese fallo. CI reproduce la instalación Git fijada. |
| Regresión export | `python -m pytest -q packages/prospector_export/tests` | FAIL local, 96 pasaron y 7 fallaron. Windows denegó `os.link` en seis casos. El subproceso con `-I` ignoró la instalación por `PYTHONPATH` en el séptimo. |
| Build de distribuciones | `python -m build --no-isolation --sdist --wheel`, desde `git archive` del commit documental `9e649451b358c3c9d30657ba027d6bc00d477a88` en un temporal | PASS, se generaron sdist y wheel `0.1.0.dev0`, salida 0. El primer intento de construir el wheel desde el sdist falló por longitud de ruta de Windows. La variante local construye ambos desde fuente. |
| Smoke de instalación | `python scripts/installed_smoke.py --wheelhouse <wheelhouse>` | NOT_RUN local. El job `package` de Service CI prepara el wheelhouse y ejecuta el smoke en una venv limpia. |
| Ejemplo batch y snapshot | Python 3.13.4 con `json`, `re` y `hashlib.sha256` | PASS, ejemplos parseables, cinco CUID de job únicos y en el mismo orden en el recibo, límites y fuente válidos, hash SHA-256 del YAML vigente igual a `authority.json`. |
| Referencias de documentación | Python 3.13.4, destinos relativos normalizados, y `git diff --cached --check` | PASS, enlaces locales del entregable resuelven y el diff supera la revisión de espacios. |
| Docker local | `docker info --format '{{.ServerVersion}}'` | Acceso denegado al daemon. Build y smoke de contenedor locales NOT_RUN. |
| Fake de 25 lanes y carga real | T1–T9 y escalones 1/2/3/5/10/15/20/25 del plan | NOT_RUN. Requieren el candidato batch. |

Service CI se activa al abrir un PR contra `main`. El workflow actual no tiene trigger de push para la rama preliminar. Los resultados de CI se vinculan al SHA del PR. Los tests de baseline se interpretan con el alcance documentado en [validación del Service inicial](../testing.md).

Pytest reportó la advertencia de Starlette TestClient sobre la deprecación de su integración con httpx. Se mantuvieron las dependencias fijadas.
