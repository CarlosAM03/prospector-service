# Validación reproducible

Preparación (puede requerir red): instalar Python >=3.11, entorno exclusivo, extras
[dev,xlsx,fastapi], setuptools y wheel. Descargar openpyxl y et_xmlfile en wheelhouse.
No utilizar entornos, caches ni dist/build del Engine.

```powershell
python -m pip install -e ".[dev,xlsx,fastapi]" setuptools wheel
python -m pip download --only-binary=:all: --dest .validation/wheels "openpyxl>=3.1.5,<4"
python scripts/validate.py --wheelhouse .validation/wheels
```

El gate compila, ejecuta Ruff lint/format, pruebas unitarias e integración, build de
sdist+wheel y dos smokes de wheel instalado. El venv nuevo está fuera de src (bajo
.validation) y el proceso consumidor usa -I desde otra carpeta: no hay PYTHONPATH ni
sys.path modificado. Primero instala wheel con --no-index --no-deps, verifica ausencia
real de openpyxl y FastAPI, CSV y error XLSX tipado. Después instala XLSX desde wheelhouse
con --no-index, abre Businesses y verifica Unicode. Todos esos checks son offline;
instalar las herramientas y obtener dependencias se considera preparación separada.
El gate usa build --no-isolation para evitar descargas durante checks; `python -m build`
también está soportado con la preparación normal del backend de build.

Las pruebas adaptan las fixtures congeladas y cubren valores especiales, headers-only,
orden, no mutación, selección sin deduplicación, límites, tipos, nombres, fórmulas,
fsync/link fallidos, colisiones concurrentes, dependencias opcionales y Response real
en TestClient local. No se contacta Maps ni base de datos. Tests XLSX/HTTP se omiten si
sus extras no están presentes; el gate completo requiere instalarlos y no debe reportar
esos casos como verificados si fueron omitidos.

CI está preparado en .github/workflows/prospector-export.yml del Service, matriz Python
3.11/3.12/3.13 en Ubuntu/Windows. No requiere browsers ni Docker. El Service no tenía Git
ni remote en la inspección inicial: este workflow sólo puede ejecutarse remotamente tras
incorporarlo al repositorio correcto. Ejecución local no equivale a CI remoto verde.

Resultados locales y versiones exactas utilizadas se registran en validation-report.md.
`.validation/gate-result.json` es evidencia local ignorada, generada sólo al completar
todos los gates. Un fallo posterior no debe confundirse con un resultado viejo: verificar
la salida/fecha del proceso correspondiente.
