# Prompt para Antigravity: SPEC-42 (el plan como planilla)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Cuándo y en qué rama:** primero va la SPEC-43 (`docs/handoff/spec-43-prompt.md`). Cuando esté commiteada en `spec-43-modal-refresh`, creá desde ahí la rama `spec-42-plan-spreadsheet` y seguí con `docs/specs/SPEC-42-plan-spreadsheet.md`. Si la 41 quedó bloqueada esperando fondos de Sepolia, pero su código y sus tests offline están commiteados, igual podés arrancar la 42: solo usa de la 41 el estado del registro.

**Pasos:** los mismos de `docs/handoff/spec-40-41-prompt.md`: leer la spec entera, tocar solo los archivos que nombra, correr sus tests y la suite completa, restaurar los archivos de precios, escribir el handoff con la salida real, commitear en la rama con `SPEC-42 implementation:`, sin merge ni push, y anotar la línea en `docs/handoff/spec-40-41-log.md`.

**Lo que más importa de esta spec:**
- El libro de caja del motor (sección 1) **no cambia el modelo**: solo etiqueta lo que ya está en las filas de caja. Si algún test existente del motor cambia un número, está mal.
- El test que pidió Guillermo: abrir la planilla exportada sin tocar nada y comprobar que las fórmulas dan **exactamente** (a 0,01 USD) lo que dio el motor. Si un grupo de flujos no se puede escribir como fórmula exacta, va como valor con su aviso. No aproximes una fórmula para que el test pase.
- Leer una planilla que mandó el productor: nunca evaluar ni ejecutar nada del archivo, solo leer valores.
- La prueba en Google Sheets la hace Guillermo a mano. Vos dejá el archivo de ejemplo y la lista de qué mirar en el handoff.
- No llamás a ningún modelo pago salvo que la app ya esté configurada y quieras mostrar un turno real del chat; en ese caso, uno solo, y lo decís en el handoff.
