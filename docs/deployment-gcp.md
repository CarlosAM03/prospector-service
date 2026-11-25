# Runbook de Prospector Service en Google Compute Engine

## Candidato y condición de apertura

Service `bf150e4d4eeff80de83208446eb540d880e30048` conserva el árbol del candidato `63488eb4d1152b431724bce546d423fc31767a4a`. Engine se instala desde el pin `68aca39b42a21ae8c0b54b6e6ca93840fdad27e5`. El contrato operativo es [batch v1](contracts/batch-api.v1.md).

Mantener la VM sin entrada externa durante el ensayo. La apertura del firewall, seccomp, egress, la primera prueba live y los riesgos residuales requieren aceptación del propietario. El overlay toma el perfil aprobado de un archivo externo. El perfil upstream versionado es una referencia de laboratorio. [Convergencia y ensayo protegido](engine-convergence-v1.md)

## Preparar la VM

1. Usar Ubuntu 24.04 LTS x86-64. Verificar reloj, kernel con `pidfd`, namespaces, cgroups y seccomp. Instalar Docker Engine, Buildx y el plugin Compose desde el repositorio oficial. Registrar versiones de kernel y Docker. [Docker para Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
2. Mantener un coordinador. Los límites de partida son 4 CPU, 4 GiB de RAM, 1 GiB de `/dev/shm`, 1024 PIDs y 512 MiB de tmpfs del worker. Reservar capacidad para Ubuntu y Nginx. Verificar límite de swap igual al de memoria, core deshabilitado y UID 10001 para Service.
3. Copiar [la plantilla](../deploy/gcp/service.env.example) a `/etc/prospector/service.env`. Protegerla y usar archivos de secretos externos. Proveer cuatro secretos independientes de al menos 32 bytes. Verificar lectura para el UID 10001 de Service y el UID 101 de Nginx según corresponda. Configurar un certificado TLS válido para el FQDN y fijar Nginx por digest aprobado. Mantener secretos fuera del contexto de build y los argumentos.
4. Proteger el volumen persistente `metadata` de SQLite, con WAL/SHM y clave HMAC estable. Mantener `/tmp`, `/run/prospector-tmp` y snapshots volátiles. Usar el mismo nombre de proyecto Compose para que arranque y rollback utilicen el volumen correcto.
5. Obtener los CIDR efectivos de **Connect → Outbound** en el Backend de Render. Usar esos CIDR en el archivo de directivas `allow` de Nginx y en el firewall de GCP, limitado al puerto TLS y a esa VM. Tras la aceptación, sustituir loopback por la interfaz de la VM prevista y verificar que 8000 permanece interno. Comprobar la política de egress aprobada y su bloqueo de redes internas y metadatos de GCP desde la extracción. [Render Outbound](https://render.com/docs/outbound-ip-addresses) · [Firewall de GCP](https://docs.cloud.google.com/firewall/docs/firewalls)

## Construir y ensayar

Usar el checkout verificado del candidato. El archivo del overlay puede obtenerse del PR de este runbook. Verificar su origen junto con los archivos de Compose. Si Engine es privado, resolver el acceso de solo lectura antes de construir y evitar incluir credenciales en URLs, capas o contexto de Docker.

```bash
git rev-parse HEAD
git merge-base --is-ancestor bf150e4d4eeff80de83208446eb540d880e30048 HEAD
docker version
docker compose version
docker compose --env-file /etc/prospector/service.env --project-name prospector-gcp config --quiet
docker compose --env-file /etc/prospector/service.env --project-name prospector-gcp build service
docker image inspect prospector-service:bf150e4 --format '{{.Id}}'
```

Ensayar primero el perfil seccomp predeterminado en loopback con fixtures controlados. Si el sandbox falla, conservar el puerto cerrado y entregar al propietario el error del host. Después de que autorice un perfil específico, registrar su SHA-256, digest de Nginx, ID de imagen del Service y pin de Engine. Usar el mismo conjunto de archivos en todos los comandos.

```bash
dc() {
  docker compose --env-file /etc/prospector/service.env --project-name prospector-gcp \
    -f compose.yaml -f deploy/gcp/compose.seccomp-candidate.yaml "$@"
}
dc config --quiet
dc up -d --no-build --wait
dc ps
```

Para el ensayo con el perfil predeterminado, omitir el argumento del overlay. Verificar que Nginx es el único contenedor con puerto publicado, que Service está healthy y que una fuente excluida no alcanza la API. Revisar aislamiento, egress, límites y cleanup en la VM antes de abrir el puerto.

## Comunicación y aceptación

```bash
# Desde una shell autorizada en Render
curl --fail --silent --show-error --max-time 12 "https://NOMBRE_SERVICE:PUERTO/health/ready"
# Desde GCP
curl --fail --silent --show-error --max-time 12 "https://NOMBRE_BACKEND/api/v1/health/ready"
```

Estas sondas prueban conectividad y TLS. Después de integrar el receptor de callbacks, el flujo sintético autorizado debe comprobar batch, callbacks autenticados, deduplicación, escritura PostgreSQL, snapshot, ACK después de commit y purga. Verificar expiración, replay de 48 h y pérdida de snapshots al reiniciar. Mantener la generación apagada hasta la aceptación. Flutter usa solo el origen de NestJS.

## Parada y recuperación

1. Cerrar ingreso a nuevas admisiones y ejecutar `dc stop --timeout 80`. Verificar salida de contenedores y procesos del runtime anterior. Revisar los eventos del supervisor sin copiar secretos.
2. Para rollback, mantener el puerto cerrado y volver a imagen y configuración anteriores compatibles con SQLite. Conservar volumen y HMAC. Revalidar readiness, sandbox, reconciliación y cleanup antes de abrir.
3. Tras un crash o cuarentena, no lanzar un segundo coordinador. Verificar el runtime anterior y conservar una copia consistente de SQLite. Reconciliar el estado con GET y reportar pérdida de snapshots RAM. El reinicio del contenedor no demuestra cleanup. La recuperación automática de reservas dudosas requiere nuevo boot Linux. [Guía de recuperación](deployment-v1.md)
