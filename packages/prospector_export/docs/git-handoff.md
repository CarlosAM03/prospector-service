# Preparación de commit y PR

El Service no tenía Git al inicio. Durante la ejecución apareció un repositorio local,
branch master, commit inicial `138313bb87fc6d5e186d15d5bca2a8afce5bd431`, que incluye
la implementación y el workflow. Se conserva ese snapshot; no se atribuye su creación
a este trabajo ni se reescribe su historial. No hay remote. El commit de cierre sólo
agrega validation-report.md y este git-handoff.md, ambos propios, tras inspeccionar
el staged diff vacío. No se inventa destino remoto ni se crea PR sin repositorio destino.

Inventario de rutas de implementación propias ya incluidas en el snapshot inicial:

- README.md: sólo el nuevo bloque de biblioteca implementada al inicio.
- .gitignore: exclusiones locales de esta extracción.
- .github/workflows/prospector-export.yml: workflow nuevo y acotado.
- packages/prospector_export/README.md, pyproject.toml, LICENSE, MANIFEST.in.
- packages/prospector_export/src/prospector_export/: módulos y py.typed.
- packages/prospector_export/tests/: tres módulos test_*.py.
- packages/prospector_export/scripts/validate.py.
- packages/prospector_export/docs/: documentos de esta extracción y source-provenance.json.

Excluir entornos, build/dist, egg-info, caches y .validation*.log. No agregar Docs ni los
tres documentos conceptuales preexistentes del Service. Si aparecen cambios adicionales
en README/.gitignore, usar staging de hunks y conservar trabajo ajeno. Inspeccionar
git diff --cached antes de commit. No usar git add . ni Git desde la raíz global.

Título: `feat(export): extract standalone CSV/XLSX package from CLI v1.0.0`.

Descripción preparada:

> Añade prospector-export 0.1.0 para generar CSV/XLSX desde registros normalizados
> seleccionados. Conserva siete columnas y Businesses de CLI v1.0.0, con artefactos
> en memoria, límites, prevención de fórmulas, nombres seguros y guardado exclusivo.
> openpyxl/FastAPI son extras; CLI/Engine no son dependencias. Incluye adaptación de
> DTOs y Response sin registrar rutas.
>
> Windows Python 3.11.9/3.13.4: 100 unitarias + 3 integraciones por versión, compile,
> Ruff, sdist/wheel y smokes instalados sin/con openpyxl. CI Linux/Windows configurado,
> aún sin ejecución remota. Platform↔Service pendiente de contrato; Backend sin cambios.
