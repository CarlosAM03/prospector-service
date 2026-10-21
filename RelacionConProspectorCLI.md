
---

# Acta v1.0

# Acta de Propuesta Conceptual

## Sistema de Prospección Automatizada y Gestión de Campañas de Marketing

**Versión:** 1.0 — Propuesta conceptual
**Fecha:** Agosto 2026
**Asignatura:** Desarrollo de Software con Cómputo en la Nube
**Profesor:** Ramon Loaiza Chavez

---

# 1. Integrantes del equipo

| Nombre completo                 | Número de control |
| ------------------------------- | ----------------: |
| Armenta Marquez Carlos Benjamin |          22211523 |
| Rodríguez Sánchez André Gael    |          22211646 |
| Gonzalez Gamboa Angeles Jizeth  |          22211573 |
| Lopez Calvillo Angel Ivan       |          22211596 |

---

# 2. Identificación del sistema

**Nombre del proyecto:**

**Sistema de Prospección Automatizada y Gestión de Campañas de Marketing**

**Tipo de sistema:**

Plataforma SaaS multiplataforma para prospección y gestión de campañas de marketing digital.

**Modelo de arquitectura:**

Sistema distribuido de arquitectura políglota, compuesto por componentes con responsabilidades claramente delimitadas y orientado a permitir despliegues locales, híbridos o completamente en la nube.

**Modelo de operación:**

Software as a Service (SaaS) con arquitectura multi-tenant.

---

# 3. Descripción general

El sistema será una plataforma orientada a organizaciones que requieren obtener, administrar, organizar y utilizar prospectos comerciales dentro de procesos de marketing y prospección B2B.

La plataforma permitirá centralizar el ciclo de vida de los prospectos dentro de un entorno multi-tenant, proporcionando mecanismos para administrar organizaciones, usuarios, campañas y prospectos.

La obtención automatizada de prospectos será proporcionada por un componente especializado basado en el motor desarrollado previamente en **Prospector CLI**.

La plataforma no implementará directamente las técnicas de extracción utilizadas por dicho motor. En su lugar, consumirá una interfaz de servicio que permita solicitar operaciones de prospección y recibir sus resultados.

La arquitectura busca separar claramente:

```text
Interfaz de usuario
        ↓
Lógica y dominio de negocio
        ↓
Persistencia y gobierno de datos
        ↓
Servicio de prospección
        ↓
Motor de extracción
        ↓
Fuentes públicas
```

Esta separación permitirá que el sistema principal evolucione independientemente de las tecnologías utilizadas para obtener los prospectos.

---

# 4. Antecedentes

El proyecto surge de la necesidad de automatizar y centralizar actividades relacionadas con la obtención y administración de prospectos comerciales.

La generación de prospectos puede involucrar búsquedas manuales, extracción de información desde fuentes públicas, procesamiento de resultados, validación, organización y posteriormente utilización de la información dentro de procesos comerciales.

Como antecedente tecnológico se encuentra **Prospector CLI**, proyecto desarrollado previamente para automatizar la obtención de información empresarial a partir de fuentes públicas.

La versión **Prospector CLI v0.7.0** representa la primera versión funcional capaz de generar prospectos con la información requerida para un caso de uso real del área de Marketing.

Los resultados generados mediante esta versión han sido utilizados en actividades reales de prospección comercial, proporcionando una validación inicial de la utilidad del proceso automatizado de obtención de información.

Este antecedente constituye la base tecnológica para evolucionar el motor hacia una capacidad reutilizable que pueda ser utilizada tanto mediante una aplicación CLI como mediante un servicio API.

---

# 5. Relación con Prospector CLI

## 5.1. Validación previa

Prospector CLI v0.7.0 constituye un antecedente funcional del sistema debido a que actualmente cuenta con:

* Motor funcional de prospección.
* Obtención automatizada de información.
* Procesamiento y normalización de resultados.
* Validación de información.
* Deduplicación.
* Exportación de resultados.
* Información alineada con necesidades reales de Marketing.
* Uso de resultados en procesos reales de prospección comercial.

Esta versión permitió validar inicialmente que el proceso automatizado puede generar información útil para un escenario real.

---

## 5.2. Productos y componentes independientes

El sistema académico **no constituye una nueva versión de Prospector CLI**.

Prospector y la plataforma SaaS serán proyectos relacionados, pero con responsabilidades diferentes.

La plataforma utilizará la capacidad de prospección como un componente externo especializado.

Conceptualmente:

```text
Prospector
    ↓
Obtiene prospectos

Plataforma SaaS
    ↓
Administra y utiliza prospectos
```

Por lo tanto, la evolución arquitectónica propuesta es:

```text
                    ┌──────────────────┐
                    │  Prospector Core │
                    │     Python       │
                    └────────┬─────────┘
                             │
                  ┌──────────┴──────────┐
                  │                     │
                  ▼                     ▼
          ┌──────────────┐     ┌──────────────────┐
          │ Prospector   │     │ Prospector       │
          │ CLI          │     │ Service          │
          │              │     │ FastAPI          │
          └──────────────┘     └────────┬─────────┘
                                        │
                                        ▼
                              Plataforma SaaS
```

---

# 6. Prospector Core

Prospector Core será la evolución del núcleo reutilizable del motor desarrollado actualmente dentro de Prospector CLI.

Su responsabilidad será contener la lógica necesaria para realizar el proceso de prospección independientemente de la interfaz mediante la cual sea utilizado.

Conceptualmente:

```text
Input
  ↓
Configuration
  ↓
Query / Navigation
  ↓
Scraping
  ↓
Normalization
  ↓
Validation
  ↓
Deduplication
  ↓
Business[]
```

El Core no será responsable del dominio comercial de la plataforma.

No tendrá conocimiento de:

* usuarios;
* tenants;
* campañas;
* permisos de negocio;
* dashboards;
* relaciones comerciales;
* gobierno de datos de la plataforma.

Su responsabilidad será producir información de prospectos.

---

# 7. Definición de Business

Dentro de la arquitectura de prospección:

> **Business representa un prospecto obtenido mediante el motor de prospección.**

Por lo tanto:

```text
Business = Prospecto obtenido
```

Una operación de prospección podrá devolver una colección de objetos `Business`.

Conceptualmente:

```text
Prospecting Request
        ↓
Prospector Core
        ↓
Business[]
```

Si una operación solicita 100 prospectos, el resultado esperado será una colección de hasta 100 objetos `Business`, dependiendo de la disponibilidad y validez de los resultados obtenidos.

Los atributos concretos de `Business` serán definidos a partir del contrato definitivo del motor y de la información disponible en las fuentes utilizadas.

---

# 8. Separación entre Prospector y la plataforma

La frontera conceptual entre ambos sistemas será:

```text
┌────────────────────────────────────────────┐
│              PROSPECTOR                    │
│                                            │
│ Obtención de información                  │
│ Navegación                                │
│ Scraping                                  │
│ Normalización                             │
│ Validación                                │
│ Deduplicación                             │
└──────────────────────┬─────────────────────┘
                       │
                       │ Business[]
                       ▼
┌────────────────────────────────────────────┐
│              PLATAFORMA                    │
│                                            │
│ Usuarios                                  │
│ Tenants                                   │
│ Campañas                                  │
│ Prospectos                                │
│ Persistencia                              │
│ Gobierno de datos                         │
│ Análisis                                  │
│ Exportaciones                             │
└────────────────────────────────────────────┘
```

La plataforma será responsable del ciclo de vida de los datos una vez incorporados a su dominio.

---

# 9. Visión general del sistema

La plataforma permitirá que diferentes organizaciones utilicen el mismo sistema manteniendo aislada su información.

Cada organización representa un **tenant**.

Los usuarios accederán mediante una aplicación multiplataforma desarrollada con **Dart + Flutter**.

La aplicación se comunicará con el backend principal mediante una API.

El backend será desarrollado con **Node.js + NestJS** y utilizará **Prisma ORM** para acceder a PostgreSQL.

El backend será responsable de la lógica y gobierno de la plataforma.

La obtención automatizada de prospectos será delegada a **Prospector Service**, desarrollado con **Python + FastAPI**.

---

# 10. Arquitectura global

```text
                         USUARIO
                            │
                            ▼
                  ┌──────────────────┐
                  │ Flutter Client   │
                  │                  │
                  │ Web / Desktop /  │
                  │ Mobile           │
                  └────────┬─────────┘
                           │ HTTPS
                           ▼
                  ┌──────────────────┐
                  │ Platform API     │
                  │ NestJS           │
                  │                  │
                  │ Auth             │
                  │ Tenants          │
                  │ Users            │
                  │ Campaigns        │
                  │ Prospects        │
                  │ Analytics        │
                  │ Integration      │
                  └───────┬─────┬────┘
                          │     │
                    Prisma│     │HTTP
                          │     │
                          ▼     ▼
                 ┌────────────┐ ┌────────────────────┐
                 │ PostgreSQL │ │ Prospector Service │
                 │            │ │ Python + FastAPI   │
                 └────────────┘ └─────────┬──────────┘
                                          │
                                          ▼
                                ┌────────────────────┐
                                │ Prospector Core    │
                                │ Python             │
                                └─────────┬──────────┘
                                          │
                                          ▼
                                  Public Data Sources
                                    Google Maps
```

---

# 11. Principio arquitectónico

El sistema utilizará una arquitectura distribuida y políglota basada en componentes con responsabilidades claramente delimitadas.

No se establece una arquitectura de microservicios como requisito.

El backend principal será inicialmente concebido como un **monolito modular**, mientras que Prospector será separado como servicio debido a sus características técnicas y operativas.

La distribución de componentes responde a responsabilidades reales del sistema y no a la intención de dividir artificialmente la aplicación.

Los principios principales serán:

1. Separación de responsabilidades.
2. Alta cohesión dentro de cada componente.
3. Bajo acoplamiento entre componentes.
4. Contratos explícitos de comunicación.
5. Independencia tecnológica cuando resulte conveniente.
6. Portabilidad.
7. Mantenibilidad.
8. Seguridad.
9. Aislamiento de tenants.
10. Evolución incremental.

---

# 12. Arquitectura políglota

La arquitectura utilizará diferentes tecnologías cuando cada una resulte apropiada para la responsabilidad que debe resolver.

| Componente              | Tecnología              | Responsabilidad                          |
| ----------------------- | ----------------------- | ---------------------------------------- |
| Cliente                 | Dart + Flutter          | Interfaz multiplataforma                 |
| Backend de plataforma   | Node.js + NestJS        | API y dominio de negocio                 |
| ORM                     | Prisma                  | Modelado y acceso a datos                |
| Base de datos           | PostgreSQL              | Persistencia relacional                  |
| Servicio de prospección | Python + FastAPI        | Exposición del motor                     |
| Motor de prospección    | Python                  | Obtención y procesamiento                |
| Automatización web      | Playwright              | Interacción automatizada con fuentes web |
| Contenedores            | Docker                  | Empaquetamiento y portabilidad           |
| Infraestructura         | Local / Cloud / Híbrida | Ejecución del sistema                    |

La selección tecnológica definitiva de componentes adicionales se realizará posteriormente cuando sus responsabilidades hayan sido especificadas.

---

# 13. Arquitectura de software de la plataforma

La plataforma utilizará una arquitectura modular dentro de NestJS.

```text
NestJS Application
│
├── Auth
├── Tenants
├── Users
├── Campaigns
├── Prospects
├── Prospect Acquisition
├── Analytics
├── Exports
└── External Integrations
```

Estos módulos formarán parte inicialmente de una misma aplicación backend.

La separación será lógica y arquitectónica, sin requerir que cada módulo sea desplegado como un servicio independiente.

---

# 14. Responsabilidades de NestJS

NestJS será el núcleo de la plataforma.

Será responsable de:

* autenticación;
* autorización;
* gestión de usuarios;
* gestión de organizaciones;
* resolución del contexto del tenant;
* reglas de negocio;
* gestión de campañas;
* gestión de prospectos;
* persistencia;
* consultas y filtrado;
* análisis de información;
* exportaciones;
* integración con Prospector Service;
* validación de solicitudes;
* trazabilidad de operaciones relevantes;
* exposición de la API de la plataforma.

NestJS **no será responsable de implementar el scraping**.

---

# 15. Responsabilidades de Prospector Service

Prospector Service será un servicio externo especializado desarrollado mediante **Python + FastAPI**.

Su función será proporcionar una interfaz de servicio para consumir Prospector Core.

```text
NestJS
   │
   │ HTTP
   ▼
Prospector Service
   │
   ▼
Prospector Core
   │
   ▼
Public Data Sources
```

Será responsable de:

* recibir solicitudes de prospección;
* validar los parámetros propios de la operación;
* iniciar ejecuciones del motor;
* administrar el estado de las ejecuciones;
* transformar los resultados del Core al contrato del servicio;
* devolver resultados;
* comunicar estados y errores de ejecución.

No será responsable de administrar:

* usuarios;
* tenants;
* campañas;
* permisos;
* dashboards;
* relaciones comerciales;
* persistencia de negocio de la plataforma.

---

# 16. Contrato entre plataforma y Prospector Service

La comunicación entre NestJS y Prospector Service se realizará mediante una interfaz HTTP.

Conceptualmente:

```text
NestJS
   │
   │ Prospecting Request
   ▼
Prospector Service
   │
   │ Business[]
   ▼
NestJS
```

El contrato definitivo será especificado posteriormente.

La arquitectura establece desde este momento una regla fundamental:

> **NestJS dependerá del contrato del servicio y no de la implementación interna de Prospector.**

Por lo tanto, NestJS no deberá conocer:

* Playwright;
* selectores;
* DOM;
* navegación de Google Maps;
* detalles internos del scraper;
* mecanismos internos de sincronización;
* componentes internos del motor.

---

# 17. Ejecuciones de prospección

Debido a la naturaleza de la automatización web, una operación de prospección puede requerir un tiempo considerable.

Por ello, conceptualmente una operación será tratada como un **Job de prospección**.

```text
Solicitud
    ↓
Prospecting Job
    ↓
Queued
    ↓
Running
    ↓
Completed / Failed
```

Los mecanismos técnicos específicos utilizados para ejecutar y coordinar estos trabajos serán definidos durante el diseño técnico.

---

# 18. Gobierno de datos

Una de las principales diferencias entre Prospector y la plataforma será el gobierno de datos.

Prospector tendrá como responsabilidad:

```text
Obtener
Procesar
Normalizar
Validar
Entregar
```

La plataforma tendrá como responsabilidad:

```text
Recibir
Validar
Persistir
Relacionar
Organizar
Consultar
Analizar
Exportar
```

Por lo tanto:

> **Prospector produce información; la plataforma gobierna los datos que utiliza el negocio.**

Prospector Service no será el sistema de registro permanente de los prospectos pertenecientes a la plataforma.

---

# 19. Arquitectura de persistencia

PostgreSQL será el sistema principal de persistencia de la plataforma.

La información estará organizada alrededor de las relaciones existentes entre:

```text
Tenant
  │
  ├── Users
  │
  └── Campaigns
          │
          └── Prospects
```

Prisma ORM será utilizado desde NestJS como capa de modelado y acceso a la base de datos.

La estructura definitiva del modelo se desarrollará posteriormente a partir del dominio y de los requerimientos detallados.

---

# 20. Estrategia Multi-Tenancy

La estrategia inicial será:

> **Shared Database + Shared Schema + Tenant ID**

Esto significa que múltiples organizaciones utilizarán la misma infraestructura de base de datos y esquema, manteniendo una separación lógica mediante la identificación del tenant.

Las entidades pertenecientes al dominio multi-tenant estarán asociadas a un tenant.

Conceptualmente:

```text
Tenant
 │
 ├── Users
 ├── Campaigns
 ├── Prospects
 └── Prospecting Jobs
```

---

# 21. Aislamiento de tenants

El aislamiento será una responsabilidad fundamental de la plataforma.

El contexto del tenant deberá derivarse del usuario autenticado y de su pertenencia a una organización.

Conceptualmente:

```text
Authentication
      ↓
User
      ↓
Tenant Membership
      ↓
Tenant Context
      ↓
Business Logic
      ↓
Data Access
```

La plataforma no deberá confiar únicamente en identificadores de tenant proporcionados directamente por el cliente.

Los mecanismos adicionales de aislamiento a nivel de base de datos podrán incorporarse durante el diseño técnico.

---

# 22. Modelo conceptual de datos

El modelo inicial estará compuesto por las siguientes entidades principales:

```text
Tenant
 │
 ├───────────────┐
 │               │
 ▼               ▼
User          Campaign
                 │
                 ├──────────────┐
                 │              │
                 ▼              ▼
          ProspectingJob   CampaignProspect
                                  │
                                  ▼
                              Prospect
```

Este modelo representa la estructura conceptual inicial y podrá evolucionar durante el diseño detallado.

---

# 23. Entidades principales

## 23.1. Tenant

Representa una organización que utiliza la plataforma.

Atributos conceptuales iniciales:

```text
id
name
slug
status
created_at
updated_at
```

---

## 23.2. User

Representa a un usuario perteneciente a una organización.

```text
id
tenant_id
name
email
password_hash / identity_reference
role
status
created_at
updated_at
```

---

## 23.3. Campaign

Representa una campaña de prospección dentro de un tenant.

```text
id
tenant_id
name
description
status
created_at
updated_at
```

---

## 23.4. Prospect

Representa un prospecto almacenado dentro de la plataforma.

Conceptualmente:

```text
Prospect
    =
Business persistido dentro del dominio de la plataforma
```

Atributos iniciales:

```text
id
tenant_id
name
category
address
phone
email
website
source
source_identifier
language
metadata
created_at
updated_at
```

La estructura definitiva dependerá del contrato final de Prospector y de las necesidades del dominio.

---

## 23.5. CampaignProspect

Representa la relación entre una campaña y un prospecto.

```text
campaign_id
prospect_id
status
added_at
```

Esta entidad permitirá asociar prospectos con campañas sin duplicar necesariamente la información principal del prospecto.

---

## 23.6. ProspectingJob

Representa una solicitud de obtención de prospectos.

```text
id
tenant_id
campaign_id
status
query
requested_limit
requested_by
started_at
completed_at
error
created_at
```

Conceptualmente:

```text
Campaign
    ↓
ProspectingJob
    ↓
Prospector Service
    ↓
Business[]
    ↓
Prospects
```

---

# 24. Flujo principal de prospección

```text
Usuario
   │
   ▼
Flutter
   │
   │ Solicitud
   ▼
NestJS
   │
   ├── Validar usuario
   ├── Validar tenant
   ├── Validar campaña
   └── Crear Job
   │
   ▼
Prospector Service
   │
   ▼
Prospector Core
   │
   ▼
Fuente pública
   │
   ▼
Business[]
   │
   ▼
NestJS
   │
   ├── Validación
   ├── Normalización
   ├── Deduplicación de dominio
   └── Persistencia
   │
   ▼
PostgreSQL
   │
   ▼
CampaignProspect
   │
   ▼
Flutter
```

---

# 25. Responsabilidad de la deduplicación

Prospector contará con mecanismos propios de deduplicación como parte de su proceso de generación de resultados.

Sin embargo, la plataforma también deberá considerar la identidad de los prospectos dentro de su propio dominio.

Esto se debe a que:

```text
Deduplicar resultados de una ejecución
```

y

```text
Determinar si un prospecto ya existe dentro de una organización
```

son problemas diferentes.

La primera pertenece al procesamiento del motor.

La segunda pertenece al gobierno de datos de la plataforma.

La estrategia definitiva de identidad y deduplicación será especificada durante el diseño del modelo de datos.

---

# 26. Gestión de campañas

Una campaña representará el contexto en el cual una organización utiliza determinados prospectos.

Conceptualmente:

```text
Campaign
   │
   ├── Search criteria
   ├── Prospecting Jobs
   ├── Prospects
   └── Metrics
```

Las campañas permitirán organizar las operaciones de prospección y posteriormente consultar y analizar los prospectos asociados.

---

# 27. Requerimientos funcionales

## RF-01 — Gestión de organizaciones

El sistema deberá permitir administrar organizaciones que representen tenants.

## RF-02 — Autenticación

El sistema deberá permitir a los usuarios autenticarse.

## RF-03 — Gestión de usuarios

El sistema deberá permitir administrar usuarios pertenecientes a una organización de acuerdo con sus permisos.

## RF-04 — Aislamiento de información

El sistema deberá impedir que un usuario acceda a información perteneciente a otro tenant.

## RF-05 — Gestión de campañas

El sistema deberá permitir crear, consultar, modificar y administrar campañas.

## RF-06 — Solicitud de prospectos

El sistema deberá permitir solicitar prospectos mediante criterios de búsqueda y una cantidad solicitada.

## RF-07 — Ejecución de prospección

El sistema deberá comunicarse con Prospector Service para ejecutar operaciones de prospección.

## RF-08 — Seguimiento de ejecución

El sistema deberá permitir consultar el estado de una operación de prospección.

Estados conceptuales:

```text
Queued
Running
Completed
Failed
```

## RF-09 — Persistencia de resultados

El sistema deberá almacenar los resultados válidos de las operaciones de prospección.

## RF-10 — Asociación con campañas

El sistema deberá permitir asociar prospectos con campañas.

## RF-11 — Consulta de prospectos

El sistema deberá permitir consultar los prospectos pertenecientes al tenant del usuario.

## RF-12 — Búsqueda y filtrado

El sistema deberá permitir buscar y filtrar prospectos mediante atributos disponibles.

## RF-13 — Exportación

El sistema deberá permitir exportar información de prospectos en formatos definidos por la plataforma.

## RF-14 — Análisis

El sistema deberá proporcionar información agregada relacionada con campañas y prospectos.

## RF-15 — Gestión de errores

El sistema deberá informar cuando una operación de prospección no pueda completarse.

## RF-16 — Integración externa

El sistema deberá comunicarse con Prospector Service mediante un contrato definido.

---

# 28. Requerimientos no funcionales

## RNF-01 — Seguridad

Las comunicaciones entre componentes deberán utilizar mecanismos seguros de comunicación.

## RNF-02 — Aislamiento multi-tenant

La información de cada organización deberá permanecer aislada.

## RNF-03 — Portabilidad

Los componentes principales deberán poder ejecutarse mediante contenedores.

## RNF-04 — Escalabilidad

Los componentes con diferentes características de consumo deberán poder escalar de manera independiente cuando la infraestructura lo permita.

## RNF-05 — Mantenibilidad

Los componentes deberán mantener responsabilidades claramente delimitadas.

## RNF-06 — Observabilidad

El sistema deberá registrar información relevante sobre operaciones, errores y ejecuciones.

## RNF-07 — Interoperabilidad

Los componentes desarrollados con tecnologías diferentes deberán comunicarse mediante interfaces definidas.

## RNF-08 — Disponibilidad

La plataforma deberá mantener disponible el backend principal independientemente del tiempo requerido por una operación individual de prospección.

## RNF-09 — Trazabilidad

Las operaciones relevantes deberán poder relacionarse con los elementos correspondientes del sistema.

Conceptualmente:

```text
Tenant
   ↓
User
   ↓
Campaign
   ↓
Prospecting Job
   ↓
Prospect
```

## RNF-10 — Evolución

La arquitectura deberá permitir evolucionar o sustituir el motor de prospección sin modificar innecesariamente el dominio principal de la plataforma.

---

# 29. Alcance de la versión 1

La primera versión tendrá como objetivo construir un **MVP SaaS multi-tenant de prospección y gestión de campañas**.

## 29.1. Plataforma

Se contempla:

* Aplicación multiplataforma mediante Flutter.
* Backend mediante NestJS.
* PostgreSQL.
* Prisma ORM.
* Autenticación.
* Gestión de tenants.
* Gestión de usuarios.
* Gestión de campañas.
* Gestión de prospectos.
* Solicitud de prospectos.
* Seguimiento de operaciones de prospección.
* Persistencia de resultados.
* Consulta y filtrado.
* Exportación.
* Métricas básicas.

## 29.2. Servicio de prospección

Se contempla:

* Prospector Core.
* Prospector Service.
* Python.
* FastAPI.
* Integración con el motor existente.
* Google Maps como fuente inicial.

## 29.3. Infraestructura

Se contempla:

* Docker.
* Entorno local.
* Entorno cloud.
* Posibilidad de infraestructura híbrida.
* Configuración mediante variables de entorno.
* PostgreSQL.
* Comunicación segura entre componentes.

---

# 30. Fuera del alcance de la versión 1

La primera versión no tendrá como objetivo:

* convertir Prospector en una arquitectura de microservicios;
* desarrollar un CRM completo;
* implementar múltiples fuentes de prospección;
* automatización avanzada de correo electrónico;
* campañas multicanal;
* integración con WhatsApp;
* inteligencia artificial avanzada;
* scoring avanzado mediante Machine Learning;
* facturación SaaS completa;
* marketplace;
* sistema avanzado de suscripciones;
* infraestructura multi-cloud avanzada;
* Kubernetes como requisito;
* arquitectura de microservicios completa.

Estas capacidades podrán evaluarse en versiones posteriores.

---

# 31. Frontera de responsabilidades

La arquitectura establece las siguientes responsabilidades principales:

```text
Flutter
    ↓
Presentación e interacción

NestJS
    ↓
Dominio, reglas de negocio y gobierno

PostgreSQL
    ↓
Persistencia e integridad de datos

Prospector Service
    ↓
Exposición del servicio de prospección

Prospector Core
    ↓
Obtención y procesamiento de prospectos

Public Sources
    ↓
Fuentes de información
```

---

# 32. Responsabilidades de Flutter

Flutter será responsable principalmente de:

* interfaz de usuario;
* navegación;
* formularios;
* visualización de campañas;
* visualización de prospectos;
* interacción con el usuario;
* consumo de la API de la plataforma.

Flutter no deberá:

* acceder directamente a PostgreSQL;
* ejecutar consultas SQL;
* realizar scraping;
* comunicarse directamente con Prospector Core;
* implementar reglas de negocio críticas;
* administrar el aislamiento de tenants.

---

# 33. Responsabilidades de NestJS

NestJS será responsable de:

* API de la plataforma;
* dominio de negocio;
* autenticación;
* autorización;
* multitenancy;
* campañas;
* prospectos;
* persistencia;
* gobierno de datos;
* integración con servicios externos.

NestJS no deberá:

* controlar Playwright;
* manipular directamente el DOM de Google Maps;
* implementar scraping;
* conocer selectores del scraper;
* ejecutar directamente el código interno de Prospector Core.

---

# 34. Responsabilidades de Prospector Service

Prospector Service será responsable exclusivamente de proporcionar la capacidad de prospección mediante una API.

No será responsable de:

* usuarios;
* tenants;
* campañas;
* permisos de negocio;
* dashboards;
* CRM;
* persistencia comercial de prospectos;
* relaciones entre prospectos y campañas.

Su responsabilidad conceptual será:

> **Obtener prospectos a partir de criterios de búsqueda y proporcionar sus resultados mediante una interfaz de servicio.**

---

# 35. Responsabilidades de PostgreSQL

PostgreSQL será responsable de:

* persistencia;
* integridad referencial;
* relaciones entre entidades;
* restricciones de datos;
* almacenamiento de información de la plataforma;
* consultas necesarias para el dominio.

No será responsable de:

* scraping;
* navegación web;
* lógica de interfaz;
* ejecución del motor;
* reglas de presentación.

---

# 36. Arquitectura de infraestructura

La infraestructura deberá permitir ejecutar los componentes de manera independiente.

Un escenario local podrá representarse como:

```text
Local Environment
│
├── Flutter
├── NestJS
├── PostgreSQL
└── Prospector Service
       │
       └── Prospector Core
```

Un escenario completamente cloud podrá representarse como:

```text
Cloud
│
├── Flutter / Web
├── NestJS
├── PostgreSQL
└── Prospector Service
       │
       └── Prospector Core
```

Un escenario híbrido podrá separar físicamente la plataforma del motor:

```text
Cloud
│
├── Flutter
├── NestJS
└── PostgreSQL

Dedicated / Local Infrastructure
│
└── Prospector Service
       │
       └── Prospector Core
```

La comunicación entre los componentes deberá realizarse mediante interfaces definidas.

---

# 37. Justificación de infraestructura híbrida

Prospector puede presentar requerimientos de infraestructura diferentes a los de la plataforma.

El motor puede requerir:

* automatización de navegador;
* recursos de CPU y memoria variables;
* procesos de ejecución prolongada;
* características específicas del entorno de ejecución;
* aislamiento de procesos.

La plataforma, por otro lado, estará orientada principalmente a:

* procesamiento de solicitudes;
* operaciones transaccionales;
* persistencia;
* autenticación;
* consultas;
* gestión de usuarios y campañas.

La separación física permitirá desplegar cada componente donde resulte técnicamente conveniente.

---

# 38. Evolución de las fuentes de prospección

Google Maps será la fuente inicial del motor.

La arquitectura deberá permitir incorporar fuentes adicionales sin modificar el dominio principal de la plataforma.

Conceptualmente:

```text
                     ┌── Google Maps
                     │
Prospector Core ─────┼── Future Source
                     │
                     └── Future Source
```

La plataforma deberá permanecer desacoplada de las implementaciones particulares de cada fuente.

---

# 39. Evolución del motor

La evolución de Prospector seguirá conceptualmente:

```text
Prospector CLI v0.7.0
          │
          ▼
Identificación del Core reutilizable
          │
          ▼
Prospector Core
          │
     ┌────┴─────┐
     ▼          ▼
    CLI       Service
               │
               ▼
             FastAPI
```

El objetivo será evitar duplicar la lógica del motor entre el CLI y el servicio.

Tanto el CLI como Prospector Service deberán utilizar el mismo núcleo cuando la funcionalidad corresponda al Core.

---

# 40. Principio de reutilización

La arquitectura deberá evitar que:

```text
CLI
    └── implementación propia del motor

API
    └── otra implementación del motor
```

En su lugar:

```text
              Prospector Core
               /           \
              /             \
             ▼               ▼
        Prospector CLI   Prospector Service
                              │
                              ▼
                         Plataforma SaaS
```

Esto permitirá mantener una única implementación de la lógica central del motor.

---

# 41. Estrategia de evolución del sistema

La evolución del sistema se realizará progresivamente:

```text
Requerimientos
      ↓
Dominio
      ↓
Arquitectura
      ↓
Contratos
      ↓
Modelo de datos
      ↓
Implementación
      ↓
Infraestructura
      ↓
Integración
      ↓
Testing
      ↓
Despliegue
```

Las decisiones técnicas deberán derivarse de los requerimientos y responsabilidades reales del sistema.

No se incorporará infraestructura o tecnología únicamente por anticipación.

---

# 42. Organización conceptual del trabajo

El proyecto contempla responsabilidades distribuidas entre desarrollo, integración y dirección técnica.

Las principales áreas serán:

### Backend y arquitectura

* NestJS.
* FastAPI.
* Integración entre servicios.
* Diseño de dominio.
* Diseño de API.
* PostgreSQL.
* Prisma.
* Multitenancy.
* Infraestructura.
* DevOps.
* Integración.
* Testing.
* Supervisión técnica.

### Frontend

* Dart.
* Flutter.
* Interfaces.
* Navegación.
* Formularios.
* Dashboard.
* Visualización de campañas.
* Visualización de prospectos.
* Integración con la API.

### Base de datos

* Modelo relacional.
* Prisma Schema.
* Relaciones.
* Migraciones.
* Consultas.
* Índices.
* Integridad de datos.

La distribución definitiva de tareas será establecida durante la planificación de implementación.

---

# 43. Riesgos iniciales

## R-01 — Acoplamiento entre plataforma y Prospector

Existe riesgo de que el backend dependa de detalles internos del motor.

**Mitigación:** comunicación mediante contrato HTTP definido por Prospector Service.

---

## R-02 — Duración de las operaciones de prospección

Las operaciones de automatización web pueden requerir tiempos superiores a una petición HTTP convencional.

**Mitigación:** tratar las operaciones como Jobs y separar la ejecución del proceso de la solicitud inicial.

---

## R-03 — Aislamiento multi-tenant

Un error en el acceso a datos podría provocar exposición de información entre organizaciones.

**Mitigación:** contexto de tenant, restricciones del modelo de datos y mecanismos adicionales de aislamiento cuando sean necesarios.

---

## R-04 — Cambios en las fuentes públicas

Las fuentes utilizadas por el motor pueden modificar su estructura o comportamiento.

**Mitigación:** mantener las implementaciones específicas de cada fuente aisladas dentro de Prospector.

---

## R-05 — Complejidad prematura

Existe riesgo de introducir infraestructura distribuida innecesaria antes de que exista una necesidad real.

**Mitigación:** utilizar inicialmente un backend modular y separar únicamente aquellos componentes cuya separación aporte una ventaja técnica clara.

---

# 44. Decisiones arquitectónicas preliminares

| ID      | Decisión                                                                                     |
| ------- | -------------------------------------------------------------------------------------------- |
| ARCH-01 | Flutter será el cliente multiplataforma                                                      |
| ARCH-02 | NestJS será el backend principal de la plataforma                                            |
| ARCH-03 | Prisma será utilizado como ORM                                                               |
| ARCH-04 | PostgreSQL será la base de datos principal                                                   |
| ARCH-05 | Prospector Service será desarrollado mediante FastAPI                                        |
| ARCH-06 | Prospector Core será independiente del dominio SaaS                                          |
| ARCH-07 | Prospector podrá ser consumido mediante CLI y API                                            |
| ARCH-08 | La plataforma utilizará arquitectura multi-tenant                                            |
| ARCH-09 | La estrategia inicial será Shared Database + Shared Schema + Tenant ID                       |
| ARCH-10 | NestJS será inicialmente un Modular Monolith                                                 |
| ARCH-11 | Las operaciones de prospección serán tratadas como Jobs                                      |
| ARCH-12 | Los componentes podrán ser empaquetados mediante Docker                                      |
| ARCH-13 | La arquitectura deberá permitir infraestructura local, cloud o híbrida                       |
| ARCH-14 | Google Maps será la fuente inicial de prospección                                            |
| ARCH-15 | La plataforma será responsable del gobierno y persistencia de los prospectos                 |
| ARCH-16 | `Business` representará un prospecto obtenido por Prospector                                 |
| ARCH-17 | La plataforma dependerá del contrato de Prospector Service y no de su implementación interna |

Estas decisiones representan el nivel conceptual de la arquitectura. Las decisiones técnicas específicas se documentarán conforme avance el diseño.

---

# 45. Arquitectura conceptual final

```text
┌─────────────────────────────────────────────────────────────┐
│                     PRESENTACIÓN                            │
│                                                             │
│                  Dart + Flutter                             │
│                                                             │
│              Web / Desktop / Mobile                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             │ HTTPS
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                       PLATAFORMA                            │
│                                                             │
│                    Node.js + NestJS                          │
│                                                             │
│ Auth │ Tenants │ Users │ Campaigns │ Prospects │ Analytics │
│                                                             │
│               Integration / API Layer                       │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                │ Prisma                      │ HTTP
                ▼                             ▼
┌─────────────────────────┐       ┌───────────────────────────┐
│       PostgreSQL        │       │   Prospector Service      │
│                         │       │        FastAPI            │
│ Tenant                  │       │                           │
│ User                    │       │ Prospecting API           │
│ Campaign                │       │ Job Management             │
│ Prospect                │       │ Result Transformation     │
│ ProspectingJob          │       │                           │
└─────────────────────────┘       └─────────────┬─────────────┘
                                                │
                                                ▼
                                    ┌──────────────────────────┐
                                    │    Prospector Core       │
                                    │         Python            │
                                    │                          │
                                    │ Navigation               │
                                    │ Scraping                 │
                                    │ Normalization             │
                                    │ Validation               │
                                    │ Deduplication             │
                                    │ Enrichment                │
                                    └────────────┬─────────────┘
                                                 │
                                                 ▼
                                          Public Sources
                                          Google Maps
```

---

# 46. Principio rector

El principio fundamental de la arquitectura será:

> **Cada componente debe resolver un problema concreto y exponer únicamente las capacidades que otros componentes necesitan consumir.**

Por lo tanto:

```text
Flutter
    → presenta e interactúa

NestJS
    → gobierna el dominio

PostgreSQL
    → persiste

Prospector Service
    → expone la capacidad de prospección

Prospector Core
    → obtiene y procesa prospectos

Public Sources
    → proporcionan información
```

La plataforma no necesita conocer cómo Prospector obtiene la información.

Prospector no necesita conocer para qué campaña comercial será utilizada.

---

# 47. Definición de la versión 1

La versión 1 será un **MVP de una plataforma SaaS multi-tenant para prospección y gestión de campañas**, compuesto por:

```text
Cliente multiplataforma
        +
Backend de plataforma
        +
Persistencia relacional
        +
Servicio especializado de prospección
        +
Motor reutilizable de prospección
```

El objetivo principal será demostrar la integración funcional entre estos componentes manteniendo sus responsabilidades separadas.

La primera versión deberá permitir:

1. Registrar y administrar organizaciones.
2. Administrar usuarios.
3. Mantener aislada la información de cada tenant.
4. Crear y administrar campañas.
5. Solicitar prospectos.
6. Ejecutar operaciones mediante Prospector Service.
7. Consultar el estado de dichas operaciones.
8. Recibir resultados representados como prospectos.
9. Persistir los resultados.
10. Asociar prospectos con campañas.
11. Consultar y filtrar prospectos.
12. Obtener información agregada básica.
13. Exportar información.
14. Ejecutar los componentes en infraestructura local, cloud o híbrida.

---

# 48. Estado del documento

Este documento representa la **arquitectura conceptual inicial del sistema**.

Define el contexto, alcance, responsabilidades, componentes principales y principios arquitectónicos de la versión 1.

No constituye todavía la especificación técnica definitiva de implementación.

Los siguientes elementos serán definidos posteriormente:

```text
Requerimientos detallados
        ↓
Casos de uso
        ↓
Modelo de dominio
        ↓
Modelo ER definitivo
        ↓
Prisma Schema
        ↓
Contrato API de plataforma
        ↓
Contrato de Prospector Service
        ↓
OpenAPI
        ↓
Autenticación
        ↓
Autorización
        ↓
Tenant Resolution
        ↓
Estrategia definitiva de aislamiento
        ↓
Arquitectura de Jobs
        ↓
Docker
        ↓
Infraestructura Cloud
        ↓
CI/CD
        ↓
Observabilidad
        ↓
Testing
        ↓
Seguridad
        ↓
Plan de implementación
```

Estos elementos no se consideran decisiones cerradas en esta acta hasta que sean diseñados y validados.

---

# 49. Conclusión

El **Sistema de Prospección Automatizada y Gestión de Campañas de Marketing** será una plataforma SaaS multi-tenant orientada a centralizar la obtención, administración y utilización de prospectos dentro de campañas de marketing.

La plataforma utilizará una arquitectura distribuida y políglota para separar la experiencia de usuario, el dominio de negocio, la persistencia y la obtención automatizada de información.

**Dart + Flutter** será utilizado para la aplicación multiplataforma.

**NestJS + Prisma + PostgreSQL** conformarán el núcleo de la plataforma y serán responsables del dominio, gobierno y persistencia de los datos.

**Prospector Service + FastAPI** proporcionará una frontera de servicio para consumir la capacidad de prospección.

**Prospector Core** contendrá la lógica reutilizable derivada del motor desarrollado previamente en Prospector CLI.

Esta separación permitirá mantener Prospector como un proyecto independiente, con posibilidad de conservar una interfaz CLI y, simultáneamente, proporcionar su capacidad mediante un servicio API.

La plataforma será responsable del ciclo de vida de los prospectos una vez incorporados a su dominio, mientras que Prospector será responsable exclusivamente de su obtención y procesamiento.

La arquitectura no establece una implementación basada en microservicios como requisito. Se utilizará inicialmente un backend modular y se mantendrán separados aquellos componentes cuya naturaleza técnica justifique una frontera de servicio independiente.

La primera versión priorizará:

```text
Separación de responsabilidades
        +
Multi-tenancy
        +
Gobierno de datos
        +
Integración de servicios
        +
Persistencia
        +
Portabilidad de infraestructura
```

sobre la incorporación prematura de complejidad operacional.

Este documento constituye el punto de partida para el diseño técnico, implementación, integración y evolución posterior del sistema.
