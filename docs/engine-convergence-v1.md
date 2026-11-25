# Convergencia Service–Engine v1.0.0

Base Service `1b73839af2262e2d5524b557749cdd9c2b909cbf`. Engine candidato `68aca39b42a21ae8c0b54b6e6ca93840fdad27e5`, distribución `0.1.0.dev0`. Las ADR C1–C6, el contrato batch, la persistencia, las cuotas y el control de slots conservan su alcance. [Suplemento oficial del Engine](https://github.com/CarlosAM03/prospector-engine/blob/68aca39b42a21ae8c0b54b6e6ca93840fdad27e5/docs/v1.0.0/service-runtime-supplement.md)

## Dependencias y procedencia

| Componente | Candidato Service |
| --- | --- |
| Python y base | 3.11.18-slim-bookworm por digest en ambas etapas. Service requiere Python ≥3.11.5 para que el pin de Soup Sieve se aplique también al instalar el wheel. CI ejecuta 3.11.18 y 3.13. |
| Browser y driver | Playwright 1.65.2, Chromium 159.0.8154.6 y Node 26.13.1 según el suplemento. La imagen final instala el browser correspondiente y `libatomic1`. |
| Parser | BeautifulSoup4 4.15.0 y Soup Sieve 4.1.3. `pyee` sale de constraints porque Playwright ya no la declara. |
| Empaquetado | pip 26.3 en ambas etapas Docker. Setuptools 84.2.1 y wheel 0.48.0 fijados para build y retirados como distribuciones independientes del runtime. `pip check` después de instalar. El resto de pins de Service se conserva. |

CI verifica el SHA VCS de la instalación de Engine en integración. El smoke offline comprueba el requisito VCS declarado por el wheel de Service y las versiones de Playwright y Soup Sieve instaladas. El inventario del contenedor registra el ID de imagen, CPython, driver, navegador, `libatomic1`, paquetes Debian y distribuciones Python efectivas. El requisito de origen del wheel y la comprobación de una instalación VCS son dos evidencias distintas.

## Sandbox y alcance del laboratorio

`PROSPECTOR_CHROMIUM_SANDBOX` admite los valores explícitos `0` y `1`. La imagen y Compose solicitan `1`. El supervisor establece el valor validado en cada worker a partir de Settings, con la misma lista permitida de entorno general. Los secretos y sus rutas no se copian al entorno del hijo. El perfil protegido requiere Chromium administrado por Playwright. Si el arranque protegido falla, Engine devuelve un fallo; Service no reintenta sin sandbox. El valor `0` queda disponible como selección explícita para pruebas de compatibilidad.

El laboratorio parte de Docker seccomp por defecto y prueba por separado el perfil upstream verificado por SHA-256 y el perfil con `chroot` descrito por Engine. El perfil upstream carece de `pidfd_open` y `pidfd_send_signal`. Son necesarios para que Service verifique el árbol en terminación forzada. Por ello ambos perfiles de Engine se prueban con un diagnóstico directo, y se ensaya Service con una variante de laboratorio que añade esos dos syscalls al perfil con `chroot`. Los perfiles se generan en un temporal y quedan fuera de Compose.

La prueba integrada se limita a una lane con datos sintéticos y red deshabilitada. Comprueba UID/GID 10001, init de Docker, raíz de solo lectura, tmpfs, seccomp activo, cero capacidades efectivas, `no-new-privileges`, límites de recursos, swap y core deshabilitados y lanzamiento sin `--no-sandbox`. Un éxito de laboratorio no autoriza el perfil seccomp del host productivo. Faltan validar perfiles de egress y el host de destino.

## Imagen final y aplicabilidad

El job Docker escanea la imagen final de Service con el binario oficial verificado de Trivy 0.76.2. Publica SBOM CycloneDX, reporte de vulnerabilidades sin supresiones, agrupación de altas y críticas, conteo de hallazgos de secretos e inventario efectivo. Los matches de secretos permanecen fuera del artefacto público. El resultado del escaneo expresa lo que catalogó la base de datos en esa corrida. La revisión aplicable del Chromium y Node embebidos requiere cruzar sus versiones efectivas con los avisos del proveedor, aunque el escáner omita ambos binarios. [Release de Trivy](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2)

- Soup Sieve 4.1.3 supera el rango afectado por el aviso documentado en el endurecimiento de Engine. El parser de Engine usa `find` y `find_all`. [Aviso](https://github.com/advisories/GHSA-mmhr-3c5m-f64f)
- CPython 3.11.18 incorpora la corrección del parser HTML que motivó retirar 3.11.14. Setuptools y wheel corregidos se usan para construcción e instalación. Los componentes que pip vendoriza requieren evaluación por ruta de uso y versión, incluso si las distribuciones independientes están ausentes. [Notas de CPython](https://www.python.org/downloads/release/python-31118/)
- Los componentes Debian que usa Chromium siguen dentro del alcance de revisión de imagen. Un aviso en un servidor que Service no inicia tiene otra exposición que un aviso en biblioteca cliente, TLS o parser. No se suprimen por esa diferencia.

## Riesgo residual de UID compartido

El filtro de entorno reduce exposición accidental al ejecutar el hijo. Compartir UID 10001 y montaje permite al hijo abrir archivos de credenciales legibles por ese UID y acceder al SQLite/WAL. La prueba Linux usa una credencial sintética modo 0400 y confirma acceso de lectura y escritura a la ruta SQLite por el mismo UID. Nunca usa claves de una instalación. La raíz de solo lectura no protege el volumen SQLite escrito por el coordinador. Los archivos de secretos, el proceso padre y el volumen siguen sin ser una frontera frente a código comprometido que opere con ese UID.

Dentro de la topología ratificada, evaluar hacer no volcable al coordinador y limitar acceso a /proc y ptrace sin romper pidfd ni las pruebas de cleanup. Separar y rotar credenciales por instalación, reducir el alcance del egress, mantener permisos restrictivos y comprobar integridad y copias del volumen. Las medidas de ptrace no resuelven el acceso directo a los montajes. Una frontera fuerte de credenciales y SQLite frente al hijo requiere autorización para cambiar el aislamiento.

El smoke TLS prueba SQLite y WAL bajo un volumen persistente, ausencia de sentinelas comerciales en ambos y en stdout/stderr de Service y Nginx, exportación XLSX y limpieza de staging en tmpfs. También verifica swap y core deshabilitados dentro del contenedor y pérdida de snapshots tras reinicio. Estas comprobaciones cubren el fixture y su configuración. El host de producción debe validar su propia política de memoria y captura de volcados.

## Propuesta de recuperación sin reiniciar el host

1. Con el coordinador en cuarentena, registrar la generación anterior mediante ID de contenedor, boot ID, namespace PID e identidad de cgroup. Detener el contenedor anterior y bloquear nuevos arranques del mismo volumen.
2. Desde el host confiable, comprobar que la generación registrada ya no ejecuta procesos. Capturar `cgroup.events` con `populated 0` del cgroup cuya identidad se verificó antes de detenerlo, o evidencia equivalente del runtime que verifique que el árbol completo fue recolectado. Un PID ausente o un contenedor nuevo no bastan. Con alcance incorrecto, timeout o evidencia faltante, conservar la cuarentena.
3. En mantenimiento offline y bajo el lock de coordinador, guardar evidencia y backup de metadatos. Un procedimiento a aprobar validaría evidencia, generación y estado en una transacción, y liberaría únicamente las reservas de esa generación. Los terminales administrativos y recibos se conservan. Los resultados volátiles siguen indisponibles y no hay reejecución.
4. Antes de autorizar ese procedimiento, ensayar un hijo que cambia de sesión, un descendiente vivo, cgroups reciclados, evidencia repetida y dos coordinadores compitiendo por el lock. Aceptar solo la generación sin procesos y verificar replay y readiness después. El código actual conserva su criterio previo de liberación.

## Evidencia de ejecución

Service utiliza los nueve jobs existentes. El job Docker agrega inventario, escaneo y el ensayo protegido separado del smoke de red de Platform fake. El volumen Windows local tenía menos de 1 GiB libre al iniciar la convergencia, por lo que no se construyó otra imagen ni se repitió carga allí. Gate D anterior permanece como evidencia histórica. [Perfil anterior con Engine 030a82d](chromium-controlled-v1.json)
