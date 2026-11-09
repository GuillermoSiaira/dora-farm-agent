# Prompt para Antigravity: SPEC-45 (planilla v2 con el modelo completo, OpenSolver y menú DORA)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Cuándo y en qué rama:** cuando la SPEC-46 esté commiteada, con su handoff y sin cambios pendientes, creá `spec-45-spreadsheet-v2` desde `spec-46-satellite-ndvi`. Traé la spec, y de paso la versión nueva de la SPEC-47 (cambió el orden y el nombre de su evaluación):
```
git checkout claude/satelite-dron-2bf2b7 -- docs/specs/SPEC-45-spreadsheet-v2.md docs/specs/SPEC-47-drone-mission.md docs/plan/planilla-v2-opensolver.md
```
Seguí `docs/specs/SPEC-45-spreadsheet-v2.md`.

**Por fases:** primero la A, con su commit `SPEC-45 implementation (phase A):` y su handoff, y frená para la revisión de Claude. La B va después de esa revisión. La C, solo si Guillermo aprueba el gasto en modelos.

**Pasos:** los mismos de siempre. Leé la spec entera y tocá solo los archivos que nombra. Corré sus tests y la **suite completa** (0 fallados, con `dora/data` limpio y sin restaurar nada a mano). Escribí el handoff con la salida real. Sin merge ni push. Anotá una línea en `docs/handoff/spec-40-41-log.md`.

**Lo que más importa:**
- **El modelo no cambia.** Los nombres de variables y filas son solo etiquetas: ningún número de ningún test existente puede moverse.
- **El test A5 es el corazón.** El problema que queda dentro de la planilla, resuelto con HiGHS sin usar `dora.engine`, tiene que dar el mismo plan que DORA, con y sin ediciones. Si una edición no se puede reflejar con fórmulas, la planilla lo dice: nunca aproximes una fórmula.
- **Paso 0 de A4:** armá `lp-minimo.xlsx` y escribí en el handoff, en tres líneas, qué tiene que hacer Guillermo para probarlo en Google Sheets. No adivines cómo guarda el modelo OpenSolver para Sheets.
- **No redespliegues `serve_app.py` ni `serve_mcp.py` antes del 10/11.** La ruta `/api/sheet` se prueba solo en local.
- **Apps Script:** ninguna clave en el código. Usá solo los permisos que nombra la spec.
- Ninguna clave en logs, en el handoff ni en la línea de comando.
