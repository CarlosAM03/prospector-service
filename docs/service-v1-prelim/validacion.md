# Gates del cierre preliminar

**Fecha** 2026-11-24 (America/Tijuana). **Base de código probada** `566bbbe67a59a0fda307ea7d8c5f6bf46fd93aab`. El cambio de esta fase se limita a documentación. El plan para software futuro y sus estados están en la [auditoría](auditoria-y-adr.md).

| Gate local | Comando o comprobación | Resultado |
| --- | --- | --- |
| Compilación | `C:/Python313/python.exe -m compileall -q src`, con una copia temporal de `src` en ruta corta | PASS, 14 fuentes y 14 archivos de bytecode, salida 0. El intento en la ruta larga de Windows falló al escribir bytecode. |
| Ejemplo batch y snapshot | Python 3.13.4 con `json`, `re` y `hashlib.sha256` | PASS, ejemplos parseables, cinco CUID de job únicos y en el mismo orden en el recibo, límites y fuente válidos, hash SHA-256 del YAML vigente igual a `authority.json`. |
| Docker local | `docker info --format '{{.ServerVersion}}'` | Acceso denegado al daemon. Build y smoke de contenedor locales NOT_RUN. |
| Fake de 25 lanes y carga real | T1–T9 y escalones 1/2/3/5/10/15/20/25 del plan | NOT_RUN. Requieren el candidato batch. |

Service CI se activa al abrir un PR contra `main`. El workflow actual no tiene trigger de push para la rama preliminar. Los resultados de CI se vinculan al SHA del PR. Los tests de baseline se interpretan con el alcance documentado en [validación del Service inicial](../testing.md).
