# API pública 0.1.0

```python
ExportService.export(
    records: Iterable[ExportRecord],
    format: ExportFormat | str,
    *, filename_prefix: str = "businesses", limits: ExportLimits | None = None,
) -> ExportArtifact
```

ExportRecord es dataclass frozen/slots: name str requerido; category, address, phone,
email, website y language str|null opcionales. No acepta conversión implícita de números.
`from_normalized(NormalizedRecord)` lee siete propiedades; `from_service_result(Mapping)`
exige name y considera ausentes los opcionales. Ignora claves adicionales. Es responsabilidad
del llamante distinguir resultado normalizado de original: no se puede inferir por forma.
Un mapping o modelo del Engine no se acepta directamente como ExportRecord.

ExportFormat es str Enum con CSV="csv" y XLSX="xlsx"; sólo acepta esas cadenas exactas.
HEADERS es tuple inmutable de siete nombres oficiales. La iteración es de una pasada;
los iteradores del consumidor se consumen, las listas/objetos no se modifican.
Selecciones repetidas preservan repetidos; la biblioteca no contiene deduplicación.

ExportArtifact frozen/slots: filename str, content_type str, content bytes, format enum.
`open_binary() -> BytesIO` retorna un stream nuevo que debe cerrar el consumidor.
`save(directory: str | Path) -> Path` exige carpeta existente; no admite path traversal,
sobrescritura ni filename arbitrario. La carpeta se resuelve explícitamente; no se usa cwd
como destino implícito. Cada export genera un UUID nuevo; save del mismo artefacto por
segunda vez falla, no cambia de nombre por sorpresa.

ExportLimits: max_records=10000 (0 permitido), max_field_chars=32766,
max_input_bytes=16777216, max_output_bytes=16777216. Los otros límites son enteros
positivos, no bool. max_records <=1048575, max_field_chars <=32766. Entrada cuenta UTF-8
de valores, no overhead de Python ni cabeceras. Salida cuenta todos los bytes del archivo.
El prefijo CSV de seguridad puede añadir un carácter; el máximo común evita truncado
XLSX. La validación ocurre al consumir, por lo que un generador puede haberse consumido
parcialmente cuando se reporta error. Nunca se publica un artefacto incompleto.

| Error público | Significado |
|---|---|
| ExportError | Base |
| InvalidExportInput | Tipo/carácter/nombre/opción inválido |
| UnsupportedExportFormat | Formato fuera de csv/xlsx |
| MissingExportDependency | Instalar extra xlsx o fastapi |
| ExportLimitExceeded | Límite de filas, campo, entrada o salida |
| ExportWriteError | I/O o serialización fallida, causa encadenada |
| ExportFileExistsError | Destino ya existente, jamás reemplazado |

Errores arbitrarios lanzados por un iterable del consumidor se propagan; no se ocultan
como fallos del filesystem. MemoryError y terminación forzada no se recuperan.
`fastapi_adapter.to_response(artifact)` es la única integración HTTP opcional, sin rutas.
