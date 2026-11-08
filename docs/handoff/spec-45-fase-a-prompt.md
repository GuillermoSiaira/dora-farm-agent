# Prompt para Antigravity: SPEC-45, fase A (el modelo dentro de la planilla, para re-optimizar con OpenSolver)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Antes de empezar:** corré `git status`. Si hay cambios sin commitear, no los pises: avisá y esperá.

**Rama y spec:** creá `spec-45-spreadsheet-v2` desde `spec-46-satellite-ndvi` (la SPEC-46 quedó aprobada en `04d2646`). Traé la spec desde la rama de Claude:
```
git checkout claude/satelite-dron-2bf2b7 -- docs/specs/SPEC-45-spreadsheet-v2.md
```
Hacé **solo la fase A** (secciones A1 a A10 y los tests de la fase A). Las fases B (menú de DORA en Google Sheets) y C (una planilla por modelo certificado) van después, cada una con su propio pedido. La C además gasta, y se pregunta antes.

**Para qué es y para cuándo.** El jueves 12/11 Guillermo le muestra DORA a un economista del INTA. El objetivo de esa demo: abrir una planilla de ejemplo en Google Sheets, cargar el modelo en OpenSolver (un minuto, con el recuadro de la A4), cambiar el precio de la soja, resolver y ver que el plan cambia igual que si lo calculara DORA. Para que Guillermo lo pruebe el miércoles 11, commiteá en este orden:

1. **Primer commit, lo antes posible: A1, A2, A3, A5 y A10.** Nombres de variables y filas, qué coeficientes son fórmulas, la hoja Modelo, el test de re-resolución independiente y las seis planillas de ejemplo en `docs/ejemplos/planillas/` con su README. Mensaje: `SPEC-45 implementation (phase A, part 1): model sheet, independent re-solve test, example sheets`.
2. **Segundo commit: A4.** Primero leé el código de OpenSolver para Google Sheets (es abierto) y escribí en el handoff dónde y en qué formato guarda el modelo, con archivo y línea. Después hacé lo que dice la "Decision (7/11)" de la spec: si es developer metadata, preparalo para que la fase B lo escriba; si son propiedades propias del complemento, el recuadro con las cuatro entradas arriba de la hoja Modelo. Los nombres `solver_*` de Excel se quedan en el `.xlsx`.
3. **Tercer commit: A6 a A9.** El aviso de "plan de DORA" contra "plan recalculado fuera de DORA", la lectura de una planilla re-resuelta, la hoja de estrategia de venta y la verificación visible.

**Pasos:** los mismos de siempre. Leé la spec entera y tocá solo los archivos que nombra. Corré sus tests y la **suite completa** después de cada commit (0 fallados, con `dora/data` y `observatory` limpios y sin restaurar nada a mano). Escribí el handoff (`docs/handoff/spec-45-spreadsheet-v2.md`) con la salida real después de cada commit. Anotá una línea por commit en `docs/handoff/spec-40-41-log.md`. Sin merge ni push.

**Lo que más importa:**
- **El modelo de la planilla tiene que ser el mismo problema que resuelve DORA.** El test A5 lo prueba: abre el `.xlsx` exportado, arma las matrices desde las celdas evaluadas, resuelve con HiGHS **sin usar `dora.engine`**, y compara con DORA (objetivo dentro de 0,01 USD, hectáreas y ventas dentro de 0,01). Después cambia un supuesto (soja +20 %, capital ×2, rinde de maíz −15 %), vuelve a evaluar y a resolver, y compara con DORA resolviendo el escenario editado. Si este test no pasa, la demo no se puede hacer: no lo ablandes. Si algún supuesto no puede ser fórmula, va a `value_only_inputs` con la razón, y la planilla avisa que ese cambio necesita a DORA.
- **No cambies el modelo matemático de `dora/engine.py`:** solo agregás etiquetas a variables y filas (A1).
- **Costo cero:** nada de esta fase llama a modelos de lenguaje ni a servicios pagos.
- **No redespliegues `serve_app.py` ni `serve_mcp.py`** hasta que Claude revise. Esta fase no necesita despliegue.
- **Las planillas de ejemplo pesan menos de 1 MB cada una** y se abren sin errores en LibreOffice o Excel. Si podés, verificalo abriéndolas con la biblioteca `formulas` que ya usa la SPEC-42.
- **Pendiente chico de la SPEC-46, no lo hagas ahora:** que cada test de satélite use su propia carpeta de caché. Va con la próxima spec que toque `dora/satellite.py`.
- Ninguna clave en logs, en el handoff ni en la línea de comando.

**Lo que Guillermo prueba a mano el miércoles** (anotalo en el handoff como pendiente; vos no lo podés hacer):
1. Subir a Google Sheets la planilla de ejemplo de Pergamino (2.000 ha, 500.000 USD).
2. Abrir Extensiones → OpenSolver y cargar el modelo con el recuadro de la hoja Modelo.
3. Cambiar el precio de la soja en Supuestos, resolver y comparar con lo que da DORA para el mismo cambio.
