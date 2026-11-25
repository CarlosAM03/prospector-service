# Ejecución y despliegue del candidato

Prospector Service requiere Linux con soporte `pidfd`, PID namespace privado y un filesystem volátil para temporales. En Windows se pueden correr tests con fake inyectado y un smoke independiente de Chromium. La ruta real de supervisión se valida en Linux.

## Dos contenedores

La imagen y Compose solicitan el sandbox nativo de Chromium. El perfil seccomp adicional se evalúa solo en laboratorio y requiere aprobación para el host de destino. Un host sin soporte devolverá fallo de ejecución. [Convergencia y ensayo protegido](engine-convergence-v1.md)

[compose.yaml](../compose.yaml) inicia Nginx y Service. Solo Nginx publica puerto. El upstream está en una red privada interna, con una red separada para egress de Service. Limite esa salida a los destinos autorizados por la instalación. El origen de callbacks debe ser HTTPS, configurado y confiable; puede usar una CA privada con `PLATFORM_CALLBACK_CA_FILE`. En el flujo normal el callback va directamente a Platform. El smoke añade un receptor fake detrás de Nginx exclusivamente durante la prueba.

Provisione estas variables en un entorno de despliegue ajeno a Git. Proporcione rutas de archivos absolutos y asegure lectura para el UID 10001 de Service o 101 de Nginx según corresponda. Use cuatro secretos independientes de al menos 32 bytes. No copie los secretos al contexto de build.

| Variables | Uso |
| --- | --- |
| `SOLUTION_ID`, `ASSERTION_ISSUER`, `PLATFORM_CALLBACK_ORIGIN` | Identidad confiable de Platform. Audiencia por defecto `prospector-service/v1`. |
| `SERVICE_API_KEY_FILE`, `PLATFORM_ASSERTION_KEY_FILE`, `SQLITE_HMAC_KEY_FILE`, `CALLBACK_API_KEY_FILE` | Archivos de secreto. Mantener estable el HMAC de SQLite durante la ventana de replay. |
| `TLS_CERT_FILE`, `TLS_KEY_FILE`, `PLATFORM_ALLOWLIST_FILE` | Certificado, clave y archivo de directivas `allow` para las redes efectivas de Platform. Ver ejemplo en `deploy/nginx/`. |
| `LISTEN_IP`, `HTTPS_PORT`, `NGINX_IMAGE` | Ingreso TLS privado y referencia de imagen. Fijar una imagen aprobada por digest en producción. |
| `SERVICE_MEMORY_LIMIT`, `SERVICE_CPUS`, `SERVICE_PIDS_LIMIT`, `SERVICE_SHM_SIZE`, `WORKER_TMPFS_BYTES` | Límites de infraestructura de partida, sujetos a benchmark. |

```sh
docker compose config --quiet
docker compose up --build -d
curl --cacert /ruta/ca.crt https://nombre-privado:8443/health/ready
docker compose stop
```

Nginx impone TLS, allowlist y máximo de 64 KiB por body. Mantiene buffering de request y response del proxy deshabilitado y no reintenta POST. La configuración deja pasar una ráfaga autorizada de 25 POST desde la misma IP. Los timeouts son de transporte HTTP. Las colas, cuotas y el timeout de Engine viven en Service. Las sondas distinguen liveness de readiness; la saturación ordinaria devuelve 429 en admisión y conserva readiness.

## Estado, RAM y reinicios

Proteger y monitorizar el volumen SQLite, incluidos los archivos WAL y SHM. Solo un coordinador puede abrirlo a la vez. Las consultas, prospectos, exports y eventos comerciales quedan fuera del volumen. El hijo solo recibe el batch y configuración de navegador; se filtra su entorno y se usan pipes IPC acotados. No exponer secretos a las rutas temporales. Chromium y el staging temporal de XLSX usan tmpfs. El entorno productivo debe impedir swap y core dumps para los datos volátiles y restringir el acceso a procesos y montajes.

El proceso hijo comparte UID y contenedor con el coordinador. El aislamiento separa ejecución y ciclo de vida. Si la instalación exige una frontera de seguridad contra código nativo comprometido, debe evaluarse una separación adicional de credenciales y filesystem.

Ajustar `MAX_SNAPSHOT_BYTES`, `SNAPSHOT_BUDGET_BYTES`, `MAX_SNAPSHOTS`, `IPC_MAX_BYTES`, `EXPORT_CONCURRENCY` y `MAX_EXPORT_BYTES` si el perfil medido lo requiere. Las respuestas y el procesamiento transitorio de IPC/export consumen RAM adicional a los bytes retenidos. El snapshot vence a los 60 min. Si no cabe, se comunica indisponibilidad con error explícito. Se preservan los snapshots ya retenidos. ACK se registra como metadato; purga y expiración liberan la referencia de RAM.

En un apagado ordenado el coordinador deja de admitir, solicita cancelación y verifica cleanup antes de liberar cada lane. El reloj de ejecución tiene 120 min, seguido por 30 s cooperativos y hasta 30 s de terminación/verificación. Los jobs sin agregado pasan a INTERRUPTED o SKIPPED, según su ejecución observada. Tras reiniciar, las referencias RAM desaparecen y el replay de recibos sigue disponible 48 h. Platform debe reconciliar por GET de estado. La entrega de un callback previo al reinicio puede ser incierta.

Un crash con hijos cuya terminación no pudo demostrarse deja al coordinador en cuarentena, aunque esté vivo y pueda recuperar metadatos. Un nuevo PID namespace por sí solo no prueba que los procesos anteriores dejaron de ejecutarse. El candidato solo limpia automáticamente reservas de cleanup dudoso al comprobar un nuevo boot de Linux. Aislar el incidente y verificar el runtime anterior antes de optar por un procedimiento alternativo de recuperación, que queda para aprobación. No conectar un segundo coordinador ni resetear el volumen para simular recuperación.

Las huellas dejan de participar en replay a las 48 h. IDs y estados administrativos se mantienen para correlación. La política de archivo o eliminación de metadatos a largo plazo y la rotación del HMAC con recibos activos quedan pendientes de operación.
