# Despliegue académico Windows + ngrok: operación y recuperación

Fecha de referencia: 2026-11-26. Perfil temporal de entrega, no equivalente al hardening de una VM productiva permanente. Presupuesto adicional cero. No cambia contratos, lógica ni dependencias.

## Identidad y topología

- Service main congelado: `296ed076dc7b530af4be7a66472640205b8452a8`. Rama académica equivalente: `f4a6292c296119a893dbec085c2d921a088edc20` (comparación sin archivos diferentes antes de este cambio documental).
- Engine integrado: `68aca39b42a21ae8c0b54b6e6ca93840fdad27e5`.
- Imagen local reconstruida: `prospector-service:entrega-final`, ID observado `sha256:015e05aa78193cff77492a025667f1ee9d7119f0c08860b129e5e582ab4086b7`. No se promete identidad binaria al recompilar; restaurar con docker load y comprobar ID.
- Nginx: `nginxinc/nginx-unprivileged@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8`.
- Entorno observado: Windows 11, PowerShell 5.1, Docker Desktop 4.97.0 / Engine 29.9.2 con WSL2, ngrok 3.39.11. Docker requiere al menos 6 GiB y 4 CPU según prepare-offline.ps1.
- Vercel -> Platform Backend (Render) -> HTTPS ngrok con allowlist de salida de Render -> HTTPS Nginx en 127.0.0.1:8443 -> Service privado en 8000 -> Engine integrado. Service -> Platform por callbacks HTTPS; acceso a fuentes públicas por egreso online. PostgreSQL de Platform permanece fuera de este host.
- Un único coordinador. No publicar Service directamente ni exponer la API local del agente ngrok.

## Aprovisionamiento desde cero (no ejecutar sobre instalación activa)

Clonar el repositorio y situarse en la revisión congelada indicada, no actualizar dependencias. Instalar Docker Desktop WSL2, Git, Python, OpenSSL, curl compatible con CA, y ngrok autenticado por el operador. Revisar [prepare-offline.ps1](../deploy/local/prepare-offline.ps1). Este genera archivos ausentes, no reemplaza claves existentes, prepara seccomp y certificado local. Para una recuperación, restaurar los archivos existentes primero; no regenerar secretos por defecto. El script necesita Python y OpenSSL, y su opción -Start exige curl.exe y puede escribir la allowlist tras observar el peer. No ejecutar -Start sobre el stack online activo. En una máquina nueva provisionar primero en modo offline con el script, construir/cargar la imagen y verificar recursos. Si curl.exe no existe, instalar una distribución confiable o comprobar HTTPS con una sonda de certificado fijado; no usar -k. Si el aprovisionamiento termina únicamente en la sonda curl ausente, inspeccionar los recursos ya creados antes de repetirlo.

```powershell
$cfg = Join-Path $env:LOCALAPPDATA 'PROSPECTOR\EntregaFinal'
$ops = Join-Path $env:LOCALAPPDATA 'PROSPECTOR\OPS'
New-Item -ItemType Directory -Path $ops -Force | Out-Null
& .\deploy\local\prepare-offline.ps1 -ConfigDir $cfg
$c = @('--project-name','prospector-final-local','--env-file',(Join-Path $cfg 'service.env'),'-f','compose.yaml','-f','deploy/gcp/compose.seccomp-candidate.yaml','-f','deploy/local/compose.offline.yaml')
docker compose @c config --quiet
# Si no se dispone de imagen respaldada:
docker compose @c build service
docker compose @c pull nginx
# Solo instalación nueva/offline y con prerrequisitos completos:
& .\deploy\local\prepare-offline.ps1 -ConfigDir $cfg -Start
```

Verificar códigos de salida de cada comando antes de continuar. Las rutas absolutas de service.env deben corresponder al usuario y host de destino. Los secretos service_key, assertion_key, callback_key y metadata_key son independientes; nunca imprimirlos. Los primeros tres corresponden respectivamente a PROSPECTOR_BATCH_API_KEY, PROSPECTOR_BATCH_ASSERTION_KEY y PROSPECTOR_BATCH_CALLBACK_KEY en Platform. Mantener metadata_key junto a SQLite para replay. Configurar solución, emisor, audiencia y callback origin idénticos a Platform. No reutilizar JWT_SECRET. No copiar credenciales de otra instalación sin autorización. El certificado local generado por prepare-offline tiene 7 días de vigencia; comprobar nombre, fechas y correspondencia clave-certificado. Renovación: ventana sin trabajo activo, actualizar archivos y volumen TLS de forma coordinada, reiniciar Nginx y ngrok con la nueva CA; verificar nuevamente. No desactivar validación TLS.

## Perfil online (excepción académica aprobada)

Guardar fuera de Git, en OPS/compose.online.yaml:

```yaml
services:
  service:
    networks:
      online_egress: {}
networks:
  online_egress:
    external: true
    name: prospector-online-egress
```

Crear la red solo si no existe: `docker network create --driver bridge prospector-online-egress`. Comprobar que no es interna y no hay conflictos. El overlay conserva upstream y egress internos y añade salida general; no es un firewall de destinos. Nginx conserva ingress y upstream, filesystem de solo lectura y publicación exclusiva loopback. No usar modo privilegiado ni desactivar seccomp/sandbox. El perfil requiere aprobación del host y pruebas Chromium. En el host original el gateway ingress fue 192.168.176.1 y la allowlist Nginx incluyó únicamente loopbacks y ese peer /32 observado; en otro host no copiar ciegamente esa IP. Usar la comprobación de peer del aprovisionador.

```powershell
$online = $c + @('-f',(Join-Path $ops 'compose.online.yaml'))
docker compose @online config --quiet
docker compose @online up -d --no-build --pull never --wait --wait-timeout 120
docker compose @online ps
docker exec prospector-final-local-nginx-1 nginx -t
```

Inspeccionar configuración efectiva sin imprimir variables/secretos: Service en upstream, egress y online_egress; Nginx en ingress y upstream; volúmenes de credenciales montados ro; metadata rw. Validar readiness HTTPS local con certificado fijado y nombre/vigencia. Validar desde el contenedor DNS y HTTPS a Platform y Google Maps. HTTP 200 de Google Maps no demuestra extracción real.

## ngrok y Platform

Crear ngrok-policy.yaml en configuración privada con estructura siguiente. Los CIDR deben verificarse contra las IP de salida del servicio Render real antes de usar; ejemplo histórico del host de entrega, no lista universal:

```yaml
on_http_request:
  - actions:
      - type: restrict-ips
        config:
          enforce: true
          allow:
            - 74.220.48.0/24
            - 74.220.56.0/24
```

Autenticar agente por separado; no guardar authtoken en Git. Conservar dominio asignado a la cuenta y configurar PROSPECTOR_BATCH_SERVICE_ORIGIN en Platform con su origen HTTPS exacto, sin ruta. Si cambia dominio, coordinar actualización y nueva aceptación de Platform. No modificar variables de Render durante un simple encendido/apagado.

```powershell
$domain = '<dominio-asignado-ngrok>'
ngrok http https://127.0.0.1:8443 --url "https://$domain" --traffic-policy-file "$cfg\ngrok-policy.yaml" --upstream-tls-verify --upstream-tls-verify-cas "$cfg\tls_crt" --inspect=false
```

Mantener consola abierta. Comprobar endpoint local del agente en 127.0.0.1:4040/api/endpoints; no exponer esa API. La allowlist de ngrok no reemplaza API key ni aserciones. Acreditar desde Platform admisión, callbacks, reconciliación, extracción real, CSV/XLSX, incorporación, ACK/purga; repetir con clave inválida únicamente en pruebas controladas. Una sonda local no acredita comunicación desde Render.

## Administración rápida

Los scripts OPS de entrega se conservan en el paquete local del operador, fuera de Git: Common-, Start-, Status-, Stop-Prospector.ps1 y compose.online.yaml. Los scripts iniciales tienen identidad de imagen, repositorio, dominio y CIDR fijados para la instalación original; adaptar explícitamente esas referencias si se migra y volver a validar. Mantener el checkout de ejecución congelado (no apuntarlo a la rama documental). Con Docker Desktop iniciado:

```powershell
$ops = Join-Path $env:LOCALAPPDATA 'PROSPECTOR\OPS'
& "$ops\Status-Prospector.ps1" -Egress
& "$ops\Start-Prospector.ps1"
# Solo después de verificar ausencia de consultas activas y snapshots pendientes en TODOS los tenants:
& "$ops\Stop-Prospector.ps1"
```

En RemoteSigned, revisar archivos descargados y desbloquear únicamente los cuatro PS1 confiables con Unblock-File; no rebajar política global. Status con TLS y egreso acreditado el 26/11/2026. Start/Stop automatizados pendientes de ensayo al escribir esta guía. Start mantiene ngrok en primer plano; si queda agente vacío tras Stop, cerrar solo su consola. Si API local falla o endpoint tiene URI inesperada, detenerse y revisar; no matar todos los agentes.

## Respaldo y restauración

Antes de detener: coordinar ventana sin nuevas solicitudes, comprobar todos los tenants, terminar exportación/incorporación y ACK/purga. Snapshots comerciales viven en RAM, no se recuperan mediante backup. No hay bloqueo global de admisión en scripts OPS; la comprobación es manual. Desconectar solo endpoint de PROSPECTOR y detener solo Nginx y Service (90 s). No usar compose down -v, prune, reset WSL/Docker, ni eliminar recursos de otros proyectos.

Con contenedores detenidos y sin otro proceso usando los volúmenes:
1. Guardar ambas imágenes con docker image save -o (Service por tag, Nginx por digest; si el CLI no admite referencia digest, guardar por ID y comprobar que la referencia Compose se restaura). Verificar tar y SHA256.
2. Guardar metadata, service_credentials y nginx_credentials en tar.gz separados mediante contenedor auxiliar de la imagen Service, red none, raíz ro, volumen origen readonly, usuario root solo para preservar propietario/permisos. Guardar WAL/SHM. Verificar SQLite quick_check sobre copia temporal, no original.
3. Copiar configuración privada (sin cuenta smoke si no se necesita), scripts OPS y overlay a carpeta protegida; no incluir authtoken ngrok. Guardar versión Docker, SHA de código, ID imágenes, inspección de redes sin secretos y checksums. Proteger archivos en disco con ACL y cifrado, en particular antes de copiar a HDD. Un hash no cifra.
4. Conservar copia del código congelado (git bundle o clon). No incluir credenciales ni archivos sin seguimiento.
5. Verificar hashes tras copiar al HDD. Mantener copia local hasta comprobar destino. Copia en mismo SSD no protege contra avería del SSD.

Restauración: validar hashes, cargar imágenes, comprobar identidad y referencias, restaurar configuración a rutas correctas, y crear volúmenes/redes solo si faltan. Para volúmenes ausentes extraer tar conservando UID/GID y permisos con contenedor auxiliar offline; no sobreescribir volúmenes existentes ni conectar dos coordinadores. Validar metadata sobre copia, HMAC original, credenciales ro, TLS y gateway observado. Arrancar usando Compose y overlay sin build/pull, comprobar readiness, egress y túnel. Reconciliar estados en Platform. Si hay cuarentena o cleanup no comprobado, seguir procedimiento de incidentes de [deployment-v1.md](deployment-v1.md); no borrar SQLite para forzar arranque. La restauración completa en otro host requiere ensayo independiente.

## Evidencia y riesgos

El 26/11 se recuperaron imágenes tras eliminación accidental, se preservaron los tres volúmenes, se comprobó SQLite quick_check=ok, se reconstruyó Service y se recuperó Nginx fijado, se validó Compose online, TLS local y egreso HTTP 200 hacia Platform y Google Maps. Se observaron admisiones y callbacks HTTP 200 desde la integración productiva. No se considera acreditado el ciclo de Stop/Start ni la restauración completa de backup hasta registrar sus resultados. El host presentó apagados inesperados y error recurrente de boot 0xc0000098; mantener corriente, ventilación, evitar suspensión durante la presentación y disponer de contingencia. No atribuir causa al SSD sin diagnóstico.
