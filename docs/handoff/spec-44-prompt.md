# Prompt para Antigravity: SPEC-44 (DORA como conector público de Claude)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Cuándo y en qué rama:** cuando estén commiteadas las correcciones de la revisión de la SPEC-42, creá `spec-44-public-connector` desde `spec-42-plan-spreadsheet` y seguí `docs/specs/SPEC-44-public-connector.md`.

**Pasos:** los mismos de siempre. Leé la spec entera, tocá solo los archivos que nombra, corré sus tests y la **suite completa** (0 fallados, con `dora/data` limpio y sin restaurar nada a mano), escribí el handoff con la salida real y commiteá con mensajes que empiecen `SPEC-44 implementation:`. Sin merge ni push. Anotá la línea en `docs/handoff/spec-40-41-log.md`.

**Lo que más importa:**
- **No redespliegues `serve_app.py`** (la app pública, en evaluación del hackathon hasta el 10/11) **ni `dora-refresh`**. Solo `serve_mcp.py`.
- Una clave inválida sigue dando 401: nunca pasa a modo anónimo.
- Grabar on-chain (`record=True`, `record_outcome`) exige clave. Consultar registros es abierto.
- Ninguna clave en logs, en el handoff ni en la línea de comando.
