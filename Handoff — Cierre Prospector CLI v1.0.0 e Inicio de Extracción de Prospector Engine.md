# Handoff — Cierre Prospector CLI v1.0.0 e Inicio de Extracción de Prospector Engine

**Fecha de corte:** 8 de Octubre 2026  
**Estado:** Prospector CLI v1.0.0 cerrado. Siguiente frente: Prospector Engine → Prospector Service.  
**Owner técnico / integración:** Carlos Armenta

---

# 1. Punto de transición

Prospector CLI `v1.0.0` ha terminado su ciclo de implementación, hardening, aceptación, freeze y publicación.

Desde este punto:

```text
Prospector CLI
DEJA DE SER
el proyecto activo

y pasa a ser

BASELINE TÉCNICO
+
BASELINE CONTRACTUAL
+
BASELINE DE PRUEBAS
+
REFERENCIA HISTÓRICA
```

El nuevo frente de trabajo es:

```text
Prospector CLI v1.0.0
        ↓
identificación del motor reusable real
        ↓
Prospector Engine
        ↓
integración in-process
        ↓
Prospector Service
        ↓
FastAPI
        ↓
SaaS Backend NestJS
        ↓
Flutter
```

No debe continuarse desarrollando el CLI durante esta fase salvo que posteriormente se abra explícitamente una línea de mantenimiento `v1.0.x`.

---

# 2. Estado final de Prospector CLI v1.0.0

## Release

```text
Producto:
Prospector CLI

Versión:
v1.0.0

Estado:
STABLE / RELEASED / COMPLETE
```

## Tag

```text
v1.0.0
```

Tag object:

```text
35088b4d53c31bb4fdde6c079b5e3d2f31873a32
```

Frozen source:

```text
bd50cf7cbba76ccd75517d06037662dff4797b05
```

El tag debe considerarse inmutable.

---

# 3. Release público

GitHub Release:

```text
https://github.com/CarlosAM03/prospector-cli/releases/tag/v1.0.0
```

Portable:

```text
Prospector-CLI-v1.0.0-win64.zip
```

Tamaño:

```text
53,658,917 bytes
```

SHA-256:

```text
A219F5A2F9A060A16135B4A61DC3CDC940659111EEE1790933E30B7C50245C1C
```

El owner descargó posteriormente este mismo asset desde GitHub y verificó que funciona correctamente.

Windows muestra la advertencia habitual de aplicación desconocida porque el ejecutable no está firmado mediante un certificado de confianza/reputación.

Esto está aceptado para `v1.0.0`.

---

# 4. Verificación final conocida

Suite aceptada:

```text
229 unit tests
PASS

69 integration tests
PASS

298 offline tests
PASS

1 live E2E
PASS
```

Además se verificó el portable publicado mediante uso real de:

```text
single search
batch de búsquedas
Visible
Background
paginación
CSV
XLSX
deduplicación
resultados parciales
logs
exports
```

No existe blocker activo de `v1.0.0`.

---

# 5. Gate final

```text
R01 PASS
R02 PASS
R03 PASS
R04 PASS
R05 PASS
R06 PASS
R07 PASS

R08 OWNER_WAIVED / DEFERRED_POST_RELEASE

R09 PASS
R10 PASS
R11 PASS
R12 PASS
R13 PASS
R14 PASS

R15 OPTIONAL_SKIPPED

R16 PASS
R17 PASS
R18 PASS
R19 PASS

R20 OWNER_ACCEPTED
```

Freeze audit:

```text
PASS
```

Release:

```text
PUBLISHED
```

---

# 6. Capacidades reales heredables del CLI

El baseline v1.0.0 ya contiene una capacidad significativamente más madura que la documentación conceptual original del futuro Engine.

Debe partirse del código real, no de diseños antiguos.

La capacidad técnica actual incluye:

```text
ProspectorEngine

EngineConfig

SearchQuery

SearchResult

Business

NormalizedBusiness

SearchIssue

BatchQuery

BatchQueryResult

BatchSearchResult

errores tipados

Google Maps navigation

result loading

summary extraction

detail panel enrichment

website enrichment

normalización global

identidad verificada de fuente

deduplicación estricta interquery

observabilidad interna

BrowserRuntime

resource lifecycle

partial results

batch secuencial

contratos deterministas
```

---

# 7. Contratos públicos de referencia

El inventario de extracción debe comenzar preservando al menos:

```text
EngineConfig

ProspectorEngine(config)

ProspectorEngine.search(SearchQuery)

ProspectorEngine.search_many(Sequence[BatchQuery])

Business

NormalizedBusiness

SearchQuery

SearchResult

SearchIssue

BatchQuery

BatchQueryResult

BatchSearchResult

typed errors
```

No deben rediseñarse simultáneamente con la extracción física.

Principio inicial:

```text
EXTRAER PRIMERO
PRESERVANDO COMPORTAMIENTO

REFACTORIZAR DESPUÉS
SOLO CON DECISIÓN EXPLÍCITA
```

---

# 8. ExportService

El CLI v1.0.0 conserva:

```text
ExportService
```

fuera de:

```text
ProspectorEngine
```

Esto es correcto.

El Engine no debe asumir:

```text
CSV
XLSX
directorio exports/
nombres de archivo
interacción de usuario
```

La plataforma SaaS tiene además su propio dominio de exportaciones.

No incorporar automáticamente `ExportService` al Prospector Engine extraído.

---

# 9. Frontera que buscamos obtener

Objetivo conceptual:

```text
Prospector Engine
│
├── configuration
├── models/domain
├── typed errors
├── execution
├── browser/runtime abstractions necesarias
├── source adapters
│   └── Google Maps
├── extraction
├── detail enrichment
├── website enrichment
├── normalization
├── source identity
├── batch
├── verified deduplication
└── observability interna
```

Debe poder ejecutarse sin:

```text
Rich

input()

menús

paginación visual

confirmaciones

CSV/XLSX

logs específicos del portable

app_paths

PyInstaller

README_PORTABLE

Windows portable UX
```

---

# 10. Elementos CLI-only que NO deben migrarse ciegamente

Auditar especialmente:

```text
src/cli_app.py
src/cli_runtime.py
src/main.py
src/app_paths.py

presentation / Rich

session loop

confirmations

pagination

interactive export selection

portable exports path

portable logs path

Windows close behavior

Ctrl+C confirmation UX

PyInstaller packaging
```

El hecho de que estos elementos utilicen el Engine no los convierte en parte del Engine.

---

# 11. BrowserRuntime requiere diseño explícito

`BrowserRuntime` contiene comportamiento útil y reusable, pero también una adaptación específica de Windows introducida para la CLI v1.0.0.

En particular, el workaround R09 modifica temporalmente:

```text
asyncio.create_subprocess_exec
```

para aislar el proceso driver de Playwright del Ctrl+C de la consola Windows.

Esto es válido bajo las condiciones del CLI:

```text
single process
single user
sequential
one BrowserRuntime/query
```

No debe heredarse automáticamente como arquitectura genérica para:

```text
FastAPI
concurrencia
multiple requests
workers
server execution
```

Durante la extracción debe decidirse qué parte es:

```text
runtime reusable
```

y qué parte es:

```text
CLI / Windows host adapter
```

---

# 12. Edge también debe tratarse como decisión del host CLI

El portable v1.0.0 usa:

```text
Microsoft Edge Stable
```

mediante:

```text
channel="msedge"
```

y no redistribuye browser.

Esta decisión fue tomada específicamente para la distribución Windows del CLI.

No asumir automáticamente:

```text
Prospector Engine == Microsoft Edge obligatorio
```

El Engine extraído debería expresar la necesidad de una capacidad de browser/runtime sin acoplar prematuramente todo su contrato público a la política de distribución Windows del CLI.

La ejecución concreta de Prospector Service deberá definirse durante su diseño.

---

# 13. Website Engine y seguridad

Antes de exponer el Engine mediante un servicio que procese inputs externos debe diseñarse una política explícita para navegación de websites.

Actualmente el enriquecimiento puede navegar al website obtenido desde una fuente externa.

Para un CLI local esto era aceptable.

Para ejecución server-side deben considerarse:

```text
localhost

127.0.0.1

::1

redes privadas

link-local

internal DNS

cloud metadata endpoints

redirects

scheme validation
```

Debe diseñarse protección SSRF-like antes de considerar Website Enrichment seguro dentro de un API multiusuario.

No necesariamente bloquea la extracción física del Engine.

Sí bloquea asumir que el Engine actual puede exponerse directamente a inputs no confiables.

---

# 14. Bug post-release confirmado

Existe un bug conocido de calidad de datos:

```text
Google Maps operational/status text
puede terminar interpretado como Address
```

Ejemplos observados:

```text
Cierra a las 10 p.m.
Cierra a las 3 p.m.
Cierra a las 5 p.m.
```

No corregirlo como parte accidental de la extracción del Engine.

Debe permanecer en el backlog de mantenimiento del CLI/Engine.

Candidato natural:

```text
v1.0.1
```

La extracción debe preservar primero el comportamiento conocido.

---

# 15. Otros hallazgos post-v1 registrados

Backlog de Prospector CLI / infraestructura heredada:

```text
CLI-001
operational Maps text interpretado como address

CLI-002
website URL/network policy antes del API

CLI-003
revisar monkeypatch global de Playwright antes de concurrencia

CLI-004
limpiar dependencias runtime

CLI-005
resolver código CLI legacy en main.py

CLI-006
auditar broad except Exception

CLI-007
CI offline

CLI-008
branch protection

CLI-009
clean Windows host test post-release

CLI-010
parser regression corpus

CLI-011
mejor diagnóstico de degradación

CLI-012
selector drift monitoring

CLI-013
revisar confiabilidad Background

CLI-014
code signing

CLI-015
reproducibilidad del packaging

CLI-016
dependency/security review

CLI-017
legacy style cleanup

CLI-018
clasificar CLI-only vs Engine

CLI-019
preservar inventory de contratos

CLI-020
server-side execution isolation

CLI-021
UX para datos inciertos

CLI-022
maintenance release policy
```

Los items más relevantes para la nueva fase son:

```text
CLI-002
CLI-003
CLI-004
CLI-018
CLI-019
CLI-020
```

---

# 16. Documentación inicial existente del siguiente sistema

La siguiente documentación ya existe localmente dentro de:

```text
ProspectorDocs/
```

Documentos directamente relacionados:

```text
ProspectorDocs/
└── PROSPECTOR_SERVICE/
    ├── README.md
    ├── RelacionConProspectorCLI.md
    └── PROSPECTOR_ENGINE/
        └── README.md

PlanInterno.md
```

Estos documentos constituyen contexto inicial.

No deben considerarse automáticamente como descripción exacta de la implementación final porque fueron escritos durante etapas anteriores del diseño.

---

# 17. Corrección de temporalidad documental

Parte de la documentación inicial describe:

```text
Prospector CLI v0.7.0
        ↓
Engine v0.7.1
        ↓
v0.8
        ↓
v0.9
        ↓
Engine v1.0.0
```

Pero el trabajo realizado posteriormente evolucionó **Prospector CLI** hasta:

```text
v1.0.0
```

incorporando dentro de su arquitectura:

```text
normalización
deduplicación
batch
identidad
errors
resource lifecycle
observability
hardening
```

Por tanto, la nueva fase NO debe repetir:

```text
v0.7 → v0.8 → v0.9 → v1
```

para el Engine.

Debe comenzar desde:

```text
Prospector CLI v1.0.0 frozen source
        ↓
inventory real
        ↓
separación física
        ↓
Prospector Engine baseline
```

---

# 18. Prospector Engine no es un microservicio

Decisión conceptual vigente:

```text
Prospector Service
    Python + FastAPI
        │
        └── Prospector Engine
              módulo interno Python
```

NO:

```text
Prospector Service
        │ HTTP
        ▼
Prospector Engine Service
```

El Engine conserva separación lógica, contractual y potencialmente de repositorio para permitir:

```text
desarrollo
pruebas
versionado
reutilización
documentación
```

pero su uso en el MVP es:

```text
in-process
```

dentro de Prospector Service.

---

# 19. Prospector Service

Prospector Service constituye la frontera:

```text
HTTP
↓
DTOs
↓
validation
↓
application/service layer
↓
Prospector Engine
↓
response transformation
```

Es responsable de:

```text
FastAPI

request DTOs

response DTOs

tipado

validación de entrada

orquestación

traducción Engine ↔ API

errores de servicio

control de ejecución propio del servicio
```

No debe duplicar:

```text
Google Maps navigation

DOM extraction

selectors

detail enrichment

website parsing

normalization

verified identity

Engine deduplication
```

---

# 20. SaaS Backend

El backend principal continúa siendo:

```text
NestJS
+
Prisma
+
PostgreSQL
```

Responsabilidades:

```text
auth
users
tenants
roles
campaigns
prospects
domain rules
tenant isolation
persistence
platform exports
Prospector Service integration
```

Regla:

```text
NestJS depende del contrato de Prospector Service

NO

de Prospector Engine
```

NestJS no debe importar ni conocer:

```text
Playwright
selectors
DOM
Google Maps navigation
Python internals
```

---

# 21. Estado actual de integración en Backend

El backend ya contiene la frontera conceptual de integración, pero deliberadamente no ejecuta Prospector actualmente.

El hardening dejó:

```text
ProspectingJobs
lectura disponible

operaciones de integración
503

ProspectorClient
adapter deshabilitado

callbacks válidos
503

reason
PROSPECTOR_INTEGRATION_PENDING
```

No existe actualmente:

```text
cliente HTTP activo

cache real de resultados

importación BusinessResult

export de scraping

cancelación física

idempotencia persistente del flujo Python
```

Esto es deliberado.

No inventar una arquitectura sustituta antes de diseñar Prospector Service.

---

# 22. Baseline del backend que no debemos romper

Backend funcional ya existente:

```text
Auth
Users
Tenants
Campaigns
Prospects
JWT
roles
tenant context
tenant isolation
validation
pagination
logging/requestId
Health
PostgreSQL
```

Prospector integration está pendiente.

Esto permite trabajar en paralelo:

```text
Ángel
Backend funcional

Carlos
Engine + Service + integración

André
Flutter features

Ángeles
UI/UX + documentación
```

---

# 23. Frontend

Flutter consume:

```text
SaaS Backend
```

No consume directamente:

```text
Prospector Service
Prospector Engine
PostgreSQL
```

Esto debe preservarse.

---

# 24. Ownership vigente del equipo

Para Fase 5, la distribución vigente es:

| Integrante | Ownership principal | Responsabilidades secundarias |
|---|---|---|
| **Carlos** | Foundation Flutter, arquitectura, integración y DevOps | ApiClient, Auth, routing, DTOs base, configuración, documentación técnica, Prospector Engine, Prospector Service y apoyo transversal |
| **Ángel** | Backend de plataforma | NestJS, Prisma, PostgreSQL y endpoints funcionales |
| **André** | Features Flutter | Pantallas, repositories, providers, widgets y tests de features |
| **Ángeles** | UI/UX y documentación académica | Wireframes, componentes visuales, estados de UI y documentación visual |

Los roles representan ownership, no exclusividad.

---

# 25. Rol específico de Carlos en la siguiente fase

Carlos concentrará principalmente:

```text
diseño

arquitectura

consolidación

baseline técnico

estructura de componentes

Prospector Engine

Prospector Service

contratos

integración transversal

DevOps

infraestructura

quality gates
```

La estrategia NO es que Carlos implemente individualmente toda la plataforma.

Frontend y Backend pueden avanzar en paralelo dentro de las fronteras y contratos definidos.

---

# 26. Repositorios delegados

Actualmente existen repositorios separados para:

```text
Backend NestJS
Frontend Flutter
```

En ellos el equipo puede avanzar con:

```text
features
services
endpoints
UI
tests
```

Carlos mantiene principalmente:

```text
arquitectura
baselines
contratos transversales
estructura
integración
consolidación
```

Las decisiones que crucen componentes deben coordinarse.

---

# 27. Documentos normativos de la plataforma

La documentación general/histórica no sustituye los documentos normativos vigentes del frontend/backend.

En particular, el contexto proporcionado indica como autoridades vigentes según fase:

```text
ADR-004
contrato OpenAPI
FormularioDecisionesFase5.md
ADR-005-FlutterFoundation.md
```

Antes de definir un contrato Engine/Service que afecte al Backend o Flutter, debe contrastarse contra estas autoridades.

No asumir que documentación conceptual de agosto sigue teniendo precedencia.

---

# 28. Objetivo académico

Proyecto:

```text
Sistema de Prospección Automatizada y Gestión de Campañas
```

Materia principal:

```text
Desarrollo de Software con Cómputo en la Nube
```

Meta:

```text
pasar de arquitectura diseñada

a

MVP funcional
integrado
desplegable
multi-tenant
```

La arquitectura objetivo es:

```text
Flutter
   ↓
SaaS Backend
   ↓
Prospector Service
   ↓
Prospector Engine
   ↓
External Sources
```

---

# 29. Principio clave del próximo trabajo

No comenzar construyendo FastAPI.

Primero:

```text
ENTENDER
↓
AUDITAR
↓
CLASIFICAR
↓
DEFINIR FRONTERA
↓
EXTRAER
↓
PROBAR EQUIVALENCIA
↓
DESPUÉS
INTEGRAR SERVICE
```

---

# 30. Primera fase siguiente — Auditoría de extracción

El próximo chat deberá comenzar con una auditoría de extracción completa contra:

```text
Prospector CLI v1.0.0 frozen source
```

Objetivo:

identificar exactamente qué código constituye Prospector Engine.

Debe producir como mínimo:

```text
Engine Source Inventory

Dependency Graph

Contract Inventory

CLI Coupling Inventory

Runtime/Browser Inventory

Filesystem Coupling Inventory

Logging/Observability Inventory

Export Coupling Inventory

Dependency Inventory

Test Mapping

Extraction Risk Matrix
```

---

# 31. Preguntas que la auditoría deberá resolver

## A. ¿Qué archivos pertenecen realmente al Engine?

No asumir:

```text
src/engines/
==
Prospector Engine
```

porque parte del motor se encuentra también en:

```text
src/models/
src/scraper/
src/services/
src/utils/
```

y parte de `src/engines/` puede contener adaptaciones específicas del host.

---

## B. ¿Qué debe permanecer en CLI?

Clasificar cada componente como:

```text
ENGINE
CLI
SHARED/ADAPTER
UNRESOLVED
```

---

## C. ¿Cuáles son los contratos que no debemos romper?

Definir baseline verificable de:

```text
inputs
outputs
errors
partial results
batch behavior
identity semantics
normalization
deduplication
resource lifecycle
```

---

## D. ¿Qué tests migran con Engine?

Mapear:

```text
tests/unit
tests/integration
tests/e2e
tests/research
```

a:

```text
Engine-owned
CLI-owned
shared contract
research-only
```

No copiar toda la suite ciegamente.

---

## E. ¿Qué dependencias requiere realmente Engine?

Separar:

```text
Engine runtime
Service runtime
CLI runtime
development
build
```

No heredar todo `requirements.txt` del CLI.

---

# 32. Estrategia de extracción recomendada

No realizar una reescritura.

Secuencia:

```text
1. Inventory
2. Contract freeze
3. Extraction map
4. New Engine baseline
5. Move/copy minimal source
6. Move relevant tests
7. Make imports independent from CLI
8. Preserve behavior
9. Run controlled equivalence
10. Version Engine baseline
11. Integrate into Prospector Service
```

---

# 33. Regla de equivalencia

La extracción inicial debe demostrar:

```text
Input equivalente
        ↓
CLI Engine baseline
        =
Extracted Engine
        ↓
Output contractual equivalente
```

No exigir igualdad exacta de resultados live de Google Maps.

Sí exigir equivalencia de:

```text
model contracts
normalization
dedupe
error semantics
partial-result policy
exportable business view where relevant
```

# 33.1. Regla de evolución después de la extracción

La preservación de comportamiento aplica a la **fase inicial de extracción**.

Su objetivo es obtener primero un baseline demostrable de:

```text
Prospector CLI v1.0.0
        ↓
motor identificado
        ↓
Prospector Engine reusable
        ↓
equivalencia contractual demostrada
```

Una vez que ese baseline del Engine haya sido:

```text
extraído
+
probado
+
documentado
+
aceptado
```

Prospector Engine pasa a tener una línea de evolución propia.

Desde ese momento estará permitido diseñar e implementar cambios que sean necesarios para convertirlo en un componente reutilizable adecuado para Prospector Service, incluyendo cuando estén justificados:

```text
bug fixes

hardening

seguridad para ejecución server-side

cambios de BrowserRuntime

eliminación de acoplamientos heredados del CLI

mejoras de configuración

observabilidad

mejor manejo de errores

nuevos contratos internos

mejoras de lifecycle

capacidades necesarias para Service

nuevas funcionalidades propias del motor
```

También podrán incorporarse funcionalidades adicionales de prospección cuando exista un requerimiento real y se determine que pertenecen a la responsabilidad del Engine.

La secuencia obligatoria es:

```text
EXTRAER
↓
DEMOSTRAR EQUIVALENCIA
↓
CERRAR BASELINE REUSABLE
↓
DISEÑAR EVOLUCIÓN
↓
IMPLEMENTAR NUEVAS CAPACIDADES
```

No:

```text
EXTRAER
+
REDISEÑAR
+
AGREGAR FEATURES
+
CAMBIAR CONTRATOS
```

todo simultáneamente.

Esto permite distinguir claramente:

```text
deuda heredada del CLI

vs.

arquitectura propia del nuevo Engine
```

Las modificaciones posteriores del Engine **no modifican retroactivamente**:

```text
Prospector CLI v1.0.0

tag v1.0.0

frozen source

release publicado

contratos históricos del CLI
```

Prospector CLI permanece como referencia histórica y baseline de procedencia.

---

# 33.2. Reconciliación de la documentación conceptual existente

Los documentos existentes de:

```text
Prospector Engine

Prospector Service

relación con Prospector CLI

arquitectura general
```

deben utilizarse como:

```text
contexto
+
intención arquitectónica
+
restricciones conocidas
```

y no como especificación inmutable.

Durante la auditoría y el diseño será válido modificar, sustituir o retirar afirmaciones que contradigan:

```text
el código real de Prospector CLI v1.0.0

los contratos efectivamente implementados

las decisiones normativas actuales

los requerimientos actuales del MVP
```

La reconciliación deberá distinguir entre:

```text
HECHO IMPLEMENTADO

DECISIÓN VIGENTE

DECISIÓN PROPUESTA

HIPÓTESIS

DOCUMENTACIÓN HISTÓRICA
```

El objetivo no es preservar literalmente el diseño conceptual anterior.

El objetivo es utilizarlo como punto de partida y convertirlo progresivamente en documentación que describa la arquitectura real del nuevo Prospector Engine y Prospector Service.

---

# 34. No mezclar extracción con API

Durante la primera etapa:

```text
Prospector Engine
```

NO debe adquirir:

```text
FastAPI

Pydantic HTTP DTOs

HTTP status codes

service authentication

tenant context

job state

callback logic
```

Eso pertenece posteriormente a:

```text
Prospector Service
```

---

# 35. No mezclar Engine con dominio SaaS

Engine no administra:

```text
Tenant

User

Campaign

Prospect persistence

PostgreSQL

Prisma

JWT

RBAC

billing

subscription

platform quotas

CampaignProspect
```

---

# 36. Deduplicación — mantener fronteras

Existen dos problemas distintos.

## Engine

```text
same execution / batch
        ↓
verified source identity
        ↓
suppress repeated observations
```

## SaaS Backend

```text
incoming Business
        ↓
tenant
database
campaign
domain identity
        ↓
existing Prospect?
```

Nunca fusionar ambas responsabilidades.

---

# 37. Contrato de Service todavía no debe asumirse final

Los documentos existentes contienen ideas como:

```text
Create Prospecting Job
Get Job Status
Get Job Results
callbacks
jobs
async execution
```

pero algunas pertenecen a diseño conceptual previo.

El estado actual del Backend deliberadamente retiró una integración previa demasiado adelantada.

Por tanto, el próximo trabajo deberá volver a validar:

```text
sync vs job
request contract
response contract
partial results
timeouts
cancellation
callbacks
authentication
idempotency
execution ownership
```

antes de considerarlos arquitectura definitiva.

---

# 38. Prioridad académica

El proyecto tiene una restricción temporal real.

Principio:

```text
INTEGRACIÓN FUNCIONAL
>
ARQUITECTURA SOFISTICADA
```

Evitar inicialmente:

```text
RabbitMQ

Kafka

Redis obligatorio

Kubernetes

distributed scheduler

microservice adicional para Engine

complex worker orchestration

plugin system

multi-source abstraction innecesaria
```

salvo que un requerimiento demostrado lo exija.

---

# 39. Primera vertical objetivo

Después de extraer Engine y construir el mínimo Service:

```text
Flutter
   ↓
NestJS
   ↓
Prospector Service
   ↓
Prospector Engine
   ↓
Google Maps
   ↓
Business[]
   ↓
Prospector Service
   ↓
NestJS
   ↓
persistencia
   ↓
Flutter
```

No necesitamos todas las capacidades futuras para demostrar esta vertical.

---

# 40. Riesgo principal

El mayor riesgo no es que cada componente individual sea imperfecto.

Es terminar con:

```text
Flutter      ✓
NestJS       ✓
PostgreSQL   ✓
FastAPI      ✓
Engine       ✓
```

pero:

```text
INTEGRACIÓN
✗
```

Por ello la estrategia debe permanecer:

```text
Fundaciones
↓
Contratos
↓
Integración vertical
↓
Desarrollo paralelo
↓
Hardening
↓
MVP
```

---

# 41. Estado de Prospector CLI después de este handoff

```text
Prospector CLI

ACTIVE DEVELOPMENT
NO

ROLE
BASELINE / REFERENCE IMPLEMENTATION

v1.0.0
IMMUTABLE

maintenance backlog
PRESERVED

possible future line
v1.0.x

current priority
NONE
```

No iniciar trabajo adicional sobre CLI durante el nuevo frente.

---

# 42. Nuevo proyecto activo

Desde el próximo chat:

```text
ACTIVE PROJECT

Prospector Engine extraction
+
Prospector Service foundation
```

Primer objetivo:

```text
obtener un Prospector Engine físicamente separado,
contractualmente equivalente al motor de Prospector CLI v1.0.0,
sin UI ni responsabilidades del SaaS,
listo para integrarse in-process dentro de Prospector Service.
```

---

# 43. Primer entregable requerido

El siguiente trabajo NO debe empezar escribiendo código.

Primer entregable:

```text
Prospector Engine Extraction Audit
```

que debe responder:

```text
qué extraer
qué no extraer
qué adaptar
qué preservar
qué desacoplar
qué tests mover
qué dependencias conservar
qué riesgos resolver ahora
qué riesgos posponer
```

Después:

```text
Extraction Design
```

Después:

```text
Implementation Plan
```

Solo entonces:

```text
Implementation
```

---

# 44. Fuentes iniciales para el próximo chat

Usar conjuntamente:

```text
Prospector CLI repository
tag v1.0.0
main post-release docs

Prospector CLI post-v1 backlog

ProspectorDocs/PROSPECTOR_SERVICE/README.md

ProspectorDocs/PROSPECTOR_SERVICE/RelacionConProspectorCLI.md

ProspectorDocs/PROSPECTOR_SERVICE/PROSPECTOR_ENGINE/README.md

PlanInterno.md

platform project context docs

Backend normative ADRs/contracts

Flutter normative ADRs/decisions
```

En caso de contradicción:

```text
current implemented code
+
accepted contracts
+
current normative ADRs
```

tienen precedencia sobre documentación conceptual antigua.

---

# 45. Roles para la siguiente conversación

## Carlos

```text
Owner de arquitectura

Owner de Prospector Engine

Owner de Prospector Service

Owner de integración transversal

Owner de DevOps / infraestructura

Owner de baselines y estructura

Owner de consolidación técnica
```

## Ángel

```text
Backend NestJS
Prisma
PostgreSQL
endpoints
integración backend
```

## André

```text
Flutter features
screens
repositories
providers
widgets
feature tests
```

## Ángeles

```text
UI/UX
wireframes
visual components
UI states
academic / visual documentation
```

Carlos puede apoyar transversalmente, pero no debe asumir automáticamente la implementación completa de las demás áreas.

---

# 46. Final handoff status

```text
PROSPECTOR CLI v1.0.0
DONE

RELEASE
DONE

TAG
DONE

DOCUMENTATION
DONE

POST-v1 BACKLOG
DEFINED

CLI ACTIVE WORK
STOPPED

NEXT ACTIVE WORK
PROSPECTOR ENGINE EXTRACTION

NEXT ARTIFACT
EXTRACTION AUDIT

NEXT ARCHITECTURAL DESTINATION
PROSPECTOR SERVICE / FASTAPI

FINAL SYSTEM DESTINATION
Flutter
→ NestJS
→ Prospector Service
→ Prospector Engine
→ External Sources
```

---

# 47. Inicio sugerido del siguiente chat

Comenzar con:

> Prospector CLI v1.0.0 está cerrado y ya no es el proyecto activo. A partir del frozen source debemos diseñar y planificar la extracción física del motor reusable para convertirlo en Prospector Engine e integrarlo posteriormente como módulo interno de Prospector Service. Antes de implementar, quiero una auditoría de extracción completa del código v1.0.0 que clasifique archivos, dependencias, contratos, tests, acoplamientos CLI y riesgos, utilizando también la documentación conceptual existente del Engine/Service y los contratos normativos actuales de la plataforma.

Ese será el nuevo punto cero.