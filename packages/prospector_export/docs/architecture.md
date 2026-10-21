# Arquitectura

`NormalizedBusiness[] -> selección del consumidor -> adapters -> ExportRecord[] ->
ExportService -> ExportArtifact -> Response opcional -> NestJS -> Flutter`.

El core depende de la biblioteca estándar. openpyxl se importa únicamente dentro de
render_xlsx. FastAPI se importa dentro de to_response, en módulo separado.
No se copia SearchResult, Business, BatchSearchResult, Engine, CLI ni sus dependencias.
Los adaptadores leen campos sin normalizar y crean un contrato nuevo de exportación;
no reconstruyen ni mutan los objetos del dominio.

La API primaria genera bytes con límites durante la iteración y escritura. CSV mantiene
un buffer de fila y un buffer final. XLSX usa Workbook ordinario en memoria para evitar
temporales openpyxl de write_only; el tipo de cada celda de datos es texto explícito.
Cuando hay retornos de carro, una segunda pasada ZIP acotada convierte CR literal a
referencias XML `&#13;`, para impedir su normalización a LF al releer con et_xmlfile.
Esto utiliza dos buffers comprimidos como máximo y chunks de 64 KiB sin temporales.
No hay promesa de streaming de generación: open_binary abre un stream del artefacto
ya completo. Response es apropiada para este MVP acotado. Aumentar límites requiere
presupuesto de memoria y concurrencia del consumidor; el XLSX comprimido no representa
el costo de RAM. El input ya residente en el consumidor queda fuera de estos límites.

El guardado explícito usa mkstemp en el directorio final, escritura/flush/fsync y hard
link exclusivo al nombre final. El temporal se retira en finally. Así otro lector no ve
un archivo final incompleto y una carrera por el mismo nombre sólo tiene un ganador.
No se crean directorios ni se usa cwd/ContextVar. Requiere un directorio de confianza
y soporte de enlaces duros. No pretende garantizar durabilidad ante pérdida de energía
ni limpiar archivos tras terminación forzada del proceso. No se usa replace/rename que
pueda sobrescribir en POSIX. La API nunca permite una ruta dentro de filename.

## Modelos de despliegue

| Opción | Estado | Uso |
|---|---|---|
| A: biblioteca en FastAPI | Capacidad lista, app pendiente | MVP preferido: instalación local/wheel y adaptador opcional |
| B: paquete independiente | Implementado | Wheel instalable fuera del monorepo, sin sys.path ni Engine |
| C: servicio HTTP separado | No implementado, opcional | Sólo si aislamiento de recursos/escalado independiente lo justifica |

C requeriría contrato aprobado, autenticación, tenant binding, transporte/retención de
resultados, límites, observabilidad y despliegue propios. Ninguna necesidad actual
justifica agregar otro servidor, Redis, cola o dominio.

NestJS conserva JWT, RBAC, tenant y autorización del Job; Python genera archivos. La
biblioteca no puede verificar esas decisiones. Una API key identifica al servicio
llamante, no autoriza por sí misma cualquier tenant/Job. La propuesta de frontera
detalla los controles que la futura aplicación debe implementar antes de exponerla.
