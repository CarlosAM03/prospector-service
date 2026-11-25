# Prospector Service v1.0.0

Candidato de servicio HTTP privado para Platform. Admite batches FIFO de 1–5 consultas Google Maps, con hasta cinco tenants activos, cinco usuarios activos por tenant y un proceso Engine por batch. La implementación usa un único coordinador y SQLite durable para metadatos. Los datos comerciales permanecen volátiles.

- [Contrato batch y compatibilidad](docs/contracts/batch-api.v1.md)
- [OpenAPI 3.1](docs/contracts/batch-api.v1.openapi.json)
- [ADR ratificadas y trazabilidad](docs/service-v1-prelim/decisiones-v1.md)
- [Ejecución, despliegue y recuperación](docs/deployment-v1.md)
- [Gates y evidencia](docs/acceptance-v1.md)

```sh
python -m pip install -c requirements/constraints.txt -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m pytest -q -m 'not integration and not browser'
python -m playwright install --with-deps chromium
python -m pytest -q -m 'integration or browser'
```

Engine se consume en el SHA candidato declarado en `pyproject.toml`. El contrato individual histórico se conserva como referencia documental. La implementación, compatibilidad de Platform y capacidad real requieren sus gates antes de producción.
