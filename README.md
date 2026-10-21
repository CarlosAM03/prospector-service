# Prospector Service

## Biblioteca de exportación implementada

[`packages/prospector_export`](packages/prospector_export/README.md) contiene
`prospector-export` 0.1.0: CSV independiente de dependencias externas, XLSX opcional
con openpyxl, artefactos en memoria y adaptador FastAPI opcional. Extraída del commit
congelado CLI v1.0.0 `bd50cf7cbba76ccd75517d06037662dff4797b05`.
La aplicación FastAPI y su conexión con Engine todavía no están implementadas aquí.
El export de Platform continúa deshabilitado (503); la operación HTTP interna propuesta
requiere aprobación del propietario. Véanse [decisiones pendientes](packages/prospector_export/docs/decisions-pending.md).
La descripción conceptual siguiente no representa una integración ya operativa.


Servicio de prospección desarrollado con **Python + FastAPI** que integra el **Prospector Engine** como módulo interno de lógica de extracción.

El servicio proporciona una interfaz API estructurada para que otros componentes de la plataforma puedan solicitar operaciones de prospección sin interactuar directamente con Playwright, Google Maps, crawlers o los componentes internos del motor.

> **Estado:** MVP inicial / arquitectura tentativa
> **Propósito actual:** Definición de la frontera de servicio e integración del motor
> **Motor:** Prospector Engine integrado como módulo interno
> **No representa todavía una implementación completa de producción.**

---

## 1. Objetivo

Prospector Service tiene como objetivo proporcionar una **interfaz de servicio para ejecutar procesos de prospección** utilizando el motor de extracción existente.

El servicio encapsula la complejidad técnica del proceso de extracción y proporciona una interfaz estructurada basada en:

* HTTP;
* FastAPI;
* DTOs;
* validación de tipos;
* validación de datos de entrada;
* orquestación del motor;
* transformación de resultados.

Conceptualmente:

```text
┌──────────────────────────────────────┐
│          Prospector Service          │
│                                      │
│              FastAPI                 │
│                 │                    │
│        Request / Response DTOs       │
│                 │                    │
│          Service Layer               │
│                 │                    │
│        Engine Orchestration          │
│                 │                    │
│        ┌───────────────────┐         │
│        │ Prospector Engine │         │
│        │                   │         │
│        │ Google Maps       │         │
│        │ Extraction        │         │
│        │ Detail Panel      │         │
│        │ Website Enrichment│         │
│        └───────────────────┘         │
└──────────────────────────────────────┘
```

---

## 2. Papel dentro de la arquitectura

Prospector Service forma parte de una arquitectura mayor:

```text
┌──────────────────────────┐
│      Cliente Flutter     │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│      SaaS Backend        │
│      NestJS + Prisma     │
│                          │
│  - Usuarios              │
│  - Tenants               │
│  - Campañas              │
│  - Reglas de negocio     │
│  - Autorización          │
└────────────┬─────────────┘
             │
             │ HTTP
             ▼
┌──────────────────────────┐
│    Prospector Service    │
│      Python + FastAPI    │
│                          │
│  ┌────────────────────┐  │
│  │ Prospector Engine  │  │
│  │                    │  │
│  │ Extracción         │  │
│  │ Enriquecimiento    │  │
│  └────────────────────┘  │
└──────────────────────────┘
```

El cliente Flutter **no consume directamente** Prospector Service.

El SaaS Backend funciona como consumidor del servicio y conserva la responsabilidad sobre las reglas de negocio de la plataforma.

---

## 3. Responsabilidades

### Prospector Service

El servicio será responsable de:

* Exponer endpoints HTTP.
* Definir contratos de entrada.
* Definir contratos de salida.
* Validar requests.
* Validar tipos.
* Transformar DTOs a objetos utilizados por el motor.
* Orquestar la ejecución del motor.
* Gestionar errores propios de la frontera HTTP.
* Transformar resultados del motor en respuestas estructuradas.
* Controlar aspectos propios de la ejecución del servicio.

### Prospector Engine

El motor será responsable de:

* Navegar por Google Maps.
* Ejecutar búsquedas.
* Cargar resultados.
* Extraer información de negocios.
* Enriquecer información mediante el detail panel.
* Realizar enriquecimiento mediante websites.
* Construir los objetos de dominio propios de la extracción.

### SaaS Backend

El backend principal será responsable de:

* Usuarios.
* Tenants.
* Autenticación.
* Autorización.
* Campañas.
* Reglas de negocio.
* Persistencia de la plataforma.
* Contexto del tenant.
* Decidir cómo utilizar y almacenar los resultados de prospección.

---

## 4. Separación entre extracción y negocio

Una regla fundamental del diseño es:

> **La lógica de extracción pertenece al Prospector Engine; la lógica de negocio pertenece al SaaS Backend.**

Por ejemplo:

```text
"Buscar restaurantes en Tijuana"
```

es una solicitud de extracción.

El motor puede interpretar:

```text
keyword = "restaurantes"
location = "Tijuana"
```

y obtener:

```text
Business[]
```

Pero decisiones como:

```text
¿A qué tenant pertenece?
¿Quién puede ejecutar la prospección?
¿La campaña está activa?
¿Cuántos prospectos puede generar el tenant?
¿Se debe guardar el prospecto?
¿El prospecto ya existe?
¿Puede el usuario ejecutar otra búsqueda?
```

son responsabilidades de la plataforma y no del motor de extracción.

---

## 5. Arquitectura interna

La estructura propuesta inicialmente es:

```text
prospector-service/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   └── prospecting.py
│   │   │
│   │   └── dependencies.py
│   │
│   ├── schemas/
│   │   ├── prospecting_request.py
│   │   ├── prospecting_response.py
│   │   └── business.py
│   │
│   ├── services/
│   │   └── prospecting_service.py
│   │
│   ├── engine/
│   │   └── prospector/
│   │       ├── core/
│   │       ├── domain/
│   │       ├── navigation/
│   │       ├── selectors/
│   │       ├── website/
│   │       └── utils/
│   │
│   ├── config/
│   │
│   └── errors/
│
├── tests/
│   ├── api/
│   ├── services/
│   └── engine/
│
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

La carpeta:

```text
app/engine/prospector/
```

representa el **Prospector Engine integrado dentro del servicio**.

No representa un proceso independiente ni otro servidor.

---

## 6. Flujo de una solicitud

El flujo conceptual de una operación es:

```text
HTTP Request
     │
     ▼
FastAPI Route
     │
     ▼
Request DTO
     │
     ▼
Validation
     │
     ▼
Prospecting Service
     │
     ▼
Engine Input
     │
     ▼
Prospector Engine
     │
     ├── Google Maps
     ├── Result Extraction
     ├── Detail Enrichment
     └── Website Enrichment
     │
     ▼
Engine Result
     │
     ▼
Response Transformation
     │
     ▼
Response DTO
     │
     ▼
HTTP Response
```

El servicio funciona como **orquestador de la ejecución del motor**.

---

## 7. Request DTO

El servicio no deberá aceptar directamente objetos internos del motor como contrato HTTP.

La entrada pública deberá estar definida mediante DTOs estructurados.

Conceptualmente:

```python
ProspectingRequest(
    keyword="restaurantes",
    location="Tijuana",
    source="google_maps",
    limit=50
)
```

El DTO será responsable de establecer:

* tipos;
* campos requeridos;
* campos opcionales;
* valores permitidos;
* límites;
* validaciones de entrada.

La representación exacta todavía es tentativa.

---

## 8. Transformación Request → Engine

El servicio deberá actuar como frontera entre el contrato HTTP y el contrato interno del motor.

```text
ProspectingRequest
        │
        ▼
Service Layer
        │
        ▼
SearchQuery
        │
        ▼
Prospector Engine
```

Por ejemplo:

```text
HTTP
{
    keyword,
    location,
    source,
    limit
}
        │
        ▼
DTO validation
        │
        ▼
SearchQuery
        │
        ▼
search_businesses()
```

Esto evita que el contrato HTTP dependa directamente de las estructuras internas del motor.

---

## 9. Response DTO

El servicio deberá proporcionar respuestas estructuradas.

Conceptualmente:

```text
ProspectingResponse
│
├── query
├── businesses[]
└── execution_time
```

Cada prospecto podrá representar información obtenida por el motor:

```text
Business
├── name
├── category
├── address
├── phone
├── website
├── email
├── language
├── website_title
├── website_description
└── website_status
```

La estructura definitiva de la respuesta todavía deberá validarse conforme se defina el contrato del servicio.

---

## 10. Validación y tipado

La frontera HTTP deberá validar la información antes de iniciar el motor.

Conceptualmente:

```text
Request
   │
   ▼
Type Validation
   │
   ▼
Business Validation
   │
   ▼
Engine
```

Esto permite evitar que errores de entrada lleguen directamente a componentes como:

* Playwright;
* Google Maps;
* Selectors;
* WebsiteCrawler.

La validación del servicio no sustituye las validaciones internas del motor; cada capa debe validar aquello que le corresponde.

---

## 11. Orquestación

El servicio deberá contener una capa responsable de coordinar la ejecución.

Conceptualmente:

```python
ProspectingService
        │
        ├── recibe DTO validado
        │
        ├── construye SearchQuery
        │
        ├── ejecuta Prospector Engine
        │
        ├── procesa resultado
        │
        └── construye Response DTO
```

El servicio **no deberá duplicar la lógica de extracción**.

Por ejemplo, la lógica:

```text
buscar feed
hacer scroll
encontrar anchors
extraer aria-label
abrir detail panel
extraer website
crawl website
extraer emails
```

pertenece al Engine.

El servicio solamente debe coordinar su ejecución.

---

## 12. Prospector Engine integrado

El Engine se considera un módulo interno del servicio:

```text
Prospector Service
│
├── API
├── Schemas
├── Services
├── Configuration
├── Error handling
│
└── Engine
    │
    ├── Search
    ├── Google Maps
    ├── Extraction
    ├── Navigation
    ├── Selectors
    └── Website Enrichment
```

No existe una comunicación HTTP entre Service y Engine.

La comunicación es mediante llamadas internas de Python:

```text
ProspectingService
        │
        ▼
search_businesses()
        │
        ▼
SearchResult
```

Esto permite mantener el motor como una pieza reutilizable sin convertirlo artificialmente en un microservicio independiente.

---

## 13. Google Maps como fuente

La primera fuente soportada es:

```text
Google Maps
```

El motor contiene actualmente componentes específicos de esta fuente:

* `GoogleMapsNavigation`;
* perfiles de selectores;
* selectores DOM;
* extracción de `place_id`;
* navegación;
* result list;
* detail panel.

Estos componentes forman parte del Engine y no de la capa FastAPI.

La arquitectura podrá soportar otras fuentes en el futuro, pero no se considera un requisito del MVP.

---

## 14. Website Enrichment

El enriquecimiento web forma parte del proceso de extracción.

El flujo es:

```text
Google Maps
     │
     ▼
Business.website
     │
     ▼
WebsiteCrawler
     │
     ▼
WebsiteParser
     │
     ▼
WebsiteExtractor
     │
     ▼
WebsiteMetadata
     │
     ▼
Business enriquecido
```

Prospector Service únicamente orquesta la ejecución de este pipeline mediante el Engine.

No implementa directamente la extracción HTML ni el crawling.

---

## 15. Multi-Tenancy

La administración de tenants **no pertenece a Prospector Service en esta etapa**.

El contexto de tenant pertenece al dominio de la plataforma SaaS.

Conceptualmente:

```text
Flutter
   │
   ▼
SaaS Backend
   │
   ├── Usuario
   ├── Tenant
   ├── Autorización
   ├── Campaña
   │
   ▼
Prospector Service
   │
   ▼
Prospector Engine
```

El SaaS Backend determina:

* quién ejecuta la operación;
* para qué tenant;
* bajo qué reglas;
* con qué permisos;
* cómo se utilizarán los resultados.

Prospector Service se concentra en la **capacidad técnica de prospección**.

La forma definitiva en que el contexto del tenant pueda acompañar una solicitud al servicio todavía deberá definirse como parte del contrato entre sistemas.

---

## 16. Persistencia

Prospector Service no tiene como responsabilidad principal administrar la base de datos de la plataforma SaaS.

El resultado de la prospección puede regresar al consumidor:

```text
Prospector Engine
      │
      ▼
Prospector Service
      │
      ▼
SaaS Backend
      │
      ▼
PostgreSQL
```

El SaaS Backend decidirá posteriormente:

* qué resultados almacenar;
* cómo asociarlos a un tenant;
* cómo asociarlos a una campaña;
* cómo manejar duplicados;
* qué información persistir.

---

## 17. Manejo de errores

El servicio deberá establecer una frontera entre errores internos del motor y respuestas HTTP.

Conceptualmente:

```text
Engine Error
     │
     ▼
Service Layer
     │
     ▼
Service Exception
     │
     ▼
HTTP Response
```

Ejemplos de categorías:

```text
Invalid Request
    ↓
400

Unsupported Source
    ↓
4xx

Extraction Failure
    ↓
5xx / respuesta estructurada

External Source Failure
    ↓
5xx / respuesta estructurada

Partial Extraction
    ↓
Resultado parcial
```

Los códigos y contratos definitivos todavía no están establecidos.

---

## 18. Responsabilidades por capa

| Capa           | Responsabilidad               |
| -------------- | ----------------------------- |
| API            | HTTP y endpoints              |
| DTOs / Schemas | Contratos y validación        |
| Service        | Orquestación                  |
| Engine         | Extracción                    |
| Navigation     | Navegación                    |
| Selectors      | Resolución de elementos       |
| Website        | Crawling y enriquecimiento    |
| Domain         | Modelos propios de extracción |
| SaaS Backend   | Reglas de negocio             |
| PostgreSQL     | Persistencia de plataforma    |

La separación busca evitar que la lógica de extracción se mezcle con las reglas de negocio del SaaS.

---

## 19. Qué NO debe hacer Prospector Service

El servicio no debe asumir responsabilidades que pertenecen al SaaS Backend.

No será responsable de:

* administrar tenants;
* administrar usuarios de la plataforma;
* administrar campañas;
* decidir permisos de negocio;
* implementar reglas comerciales;
* administrar la base de datos del SaaS;
* servir la aplicación Flutter;
* decidir qué prospectos pertenecen a qué tenant como regla de negocio;
* implementar nuevamente la lógica de extracción.

Su responsabilidad principal es:

```text
Request
  ↓
Validate
  ↓
Orchestrate
  ↓
Extract
  ↓
Transform
  ↓
Response
```

---

## 20. Estructura conceptual completa

La arquitectura actual propuesta puede resumirse como:

```text
                         SaaS Platform
                              │
                 ┌────────────┴────────────┐
                 │                         │
                 ▼                         │
          Cliente Flutter                  │
                 │                         │
                 ▼                         │
          SaaS Backend                     │
          NestJS + Prisma                  │
                 │                         │
       ┌─────────┼──────────┐              │
       │         │          │              │
       ▼         ▼          ▼              │
    Tenant    Campaigns   Business         │
       │         │        Rules             │
       └─────────┼──────────┘              │
                 │                         │
                 │ HTTP                    │
                 ▼                         │
        ┌──────────────────────┐           │
        │  Prospector Service  │           │
        │    Python + FastAPI  │           │
        │                      │           │
        │  API / DTOs          │           │
        │       │              │           │
        │  Service Layer       │           │
        │       │              │           │
        │       ▼              │           │
        │ Prospector Engine    │           │
        │       │              │           │
        │  ┌────┴──────────┐   │           │
        │  │ Google Maps   │   │           │
        │  │ Extraction    │   │           │
        │  │ Detail Panel  │   │           │
        │  │ Web Enrichment│   │           │
        │  └───────────────┘   │           │
        └──────────────────────┘           │
                                           │
```

---

## 21. Estado actual

Prospector Service se encuentra en una etapa de **definición inicial**.

La principal decisión arquitectónica establecida es que:

> **El Prospector Engine estará integrado dentro del Prospector Service como un módulo interno de lógica de extracción.**

La responsabilidad del servicio será proporcionar la frontera API y orquestar el motor mediante contratos estructurados y tipados.

La responsabilidad de la plataforma SaaS continuará separada:

```text
SaaS Backend
    │
    └── Lógica de negocio
        ├── Tenants
        ├── Usuarios
        ├── Campañas
        ├── Autorización
        └── Persistencia

Prospector Service
    │
    └── Capacidad de prospección
        ├── DTOs
        ├── Validación
        ├── Orquestación
        └── Prospector Engine
              ├── Google Maps
              ├── Extraction
              ├── Detail Enrichment
              └── Website Enrichment
```

---

## 22. Próximos pasos

La implementación podrá avanzar progresivamente:

### Etapa 1 — Base del servicio

* Crear proyecto FastAPI.
* Configurar estructura.
* Configurar Pydantic.
* Crear endpoint inicial.
* Crear DTOs iniciales.

### Etapa 2 — Integración del Engine

* Incorporar el motor auditado.
* Mantener su comportamiento inicial.
* Eliminar dependencias del CLI.
* Conectar `ProspectingService` con `search_businesses()`.

### Etapa 3 — Contratos

* Definir Request DTO.
* Definir Response DTO.
* Definir errores.
* Definir validaciones.
* Definir transformación Engine → API.

### Etapa 4 — Integración

Conectar:

```text
SaaS Backend
      │
      ▼
Prospector Service
      │
      ▼
Prospector Engine
```

### Etapa 5 — Evolución

Posteriormente podrán incorporarse:

* ejecución asíncrona;
* trabajos largos;
* colas;
* concurrencia;
* observabilidad;
* retries;
* límites de ejecución;
* nuevas fuentes.

Estas capacidades no forman parte del MVP inicial.

---

## 23. Decisiones abiertas

Todavía deberán definirse:

* Contrato definitivo del endpoint.
* Nombre de endpoints.
* Request DTO definitivo.
* Response DTO definitivo.
* Manejo de errores.
* Manejo de resultados parciales.
* Timeouts de servicio.
* Concurrencia.
* Ejecución síncrona vs. asíncrona.
* Límites de prospección.
* Autenticación entre SaaS Backend y Prospector Service.
* Transporte del contexto de tenant.
* Persistencia de resultados.
* Deduplicación.
* Estrategia de jobs para procesos largos.

Estas decisiones deberán validarse antes de considerarlas parte de la arquitectura definitiva.

---

## 24. Principios iniciales

1. **El Engine contiene la lógica de extracción.**
2. **El Service expone y orquesta el Engine.**
3. **Los DTOs definen la frontera externa del servicio.**
4. **Los tipos y validaciones deben aplicarse antes de ejecutar el motor.**
5. **El Service no debe duplicar lógica de extracción.**
6. **La lógica de negocio del SaaS pertenece al SaaS Backend.**
7. **La administración de tenants pertenece al SaaS Backend.**
8. **Flutter no debe consumir directamente el Prospector Service.**
9. **El Engine permanece integrado dentro del Service en el MVP.**
10. **Las decisiones todavía no definidas deberán mantenerse abiertas hasta validar los requerimientos del sistema.**
