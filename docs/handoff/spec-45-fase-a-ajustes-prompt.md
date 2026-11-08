# Prompt para Antigravity: ajustes de la SPEC-45, fase A (revisión de Claude del 8/11)

Trabajás en **`D:\projects\dora-main`**, rama **`spec-45-spreadsheet-v2`** (último commit `35d3fda`). No toques `D:\projects\dora-hackathon`.

**Antes de empezar:** corré `git status`. Si hay cambios sin commitear, no los pises: avisá y esperá.

**Leé la revisión entera antes de tocar nada:**
```
git show claude/keen-wilson-695e01:docs/handoff/spec-45-review-claude.md
```
Si esa rama no está en dora-main, el texto de la revisión está en `D:\projects\dora-hackathon\.claude\worktrees\keen-wilson-695e01\docs\handoff\spec-45-review-claude.md` (solo leerlo, no editarlo).

**Para cuándo:** el jueves 12/11 Guillermo le muestra la planilla a un economista del INTA, y el miércoles 11 la prueba a mano. **El primer commit va lo antes posible**, porque es lo que el economista va a leer.

## Commit 1: el bloque de precios sombra del Resumen (punto 1 de la revisión)

Mensaje: `SPEC-45 phase A fixes (1): shadow-price block in Summary, consistent and short`

1. **Una sola manera de contar.**
   - Para el dinero de cada quincena, escribí el valor de hoy y la ganancia: "Cada dólar extra en la quincena 1 (1ª de mayo) termina valiendo 1,55 USD de hoy: gana 0,55."
   - El capital inicial, igual: "Un dólar más de capital propio gana 0,55 USD."
   - La línea de crédito: "Un dólar más de línea de crédito gana X USD", y en qué quincenas ata.
   - Nada de "vale 1,5478" en una fila y "vale 0,5478" en otra.
2. **Que sea corto.** Entre 3 y 5 renglones, con los recursos que atan ordenados por valor:
   - **Dinero por quincena:** un solo renglón con un rango, del tipo "Entre mayo y diciembre cada dólar extra gana entre 0,51 y 0,55 USD; desde enero, menos".
   - **Rotación:** cada cultivo en su tope ("La soja está en su tope de rotación (50 %): una hectárea más de soja permitida vale 211,58 USD").
   - **Crédito:** si ata.
   - **Tierra:** con la aclaración del punto 3.
   - El detalle por quincena (las 30) queda en Modelo y en Sensibilidad. Agregá en Resumen el renglón "Detalle por quincena: hoja Sensibilidad".
3. **La tierra, explicada.** Si la superficie sembrada es menor que la disponible (en Pergamino siembra 1.376 de 2.000 ha), el texto dice:
   > "La tierra sobra: quedan 624 ha sin sembrar, porque el capital no alcanza. Una hectárea más de tierra propia vale 105,79 USD solo porque sube el tope de soja de la rotación (0,5 ha más de soja por hectárea)."

   Si la tierra está toda usada, se queda la frase actual. El cálculo de `land_shadow_price` (`engine.py:1385`) **no se cambia**; solo el texto.
4. **Se mantiene** el aviso de "Estos precios sombra son del plan de DORA; para los del plan nuevo, pedíselos a DORA" cuando el plan se recalculó fuera de DORA.
5. **En inglés**, lo mismo (`lang="en"`).
6. **Test nuevo** `test_14_summary_shadow_block`, para pampas_core_2000:
   - el bloque tiene como mucho 6 renglones;
   - menciona "sin sembrar" y la cantidad de hectáreas (624 ± 1);
   - menciona la rotación de soja;
   - ningún número de caja aparece como "vale 1,5…";
   - la ganancia de la quincena 1 coincide con `capital_shadow_price` dentro de 0,01.
7. **Regenerá las planillas de ejemplo** de `docs/ejemplos/planillas/` con el bloque nuevo.

## Commit 2: tests que faltan y cruces (puntos 2, 3, 4 y 7)

Mensaje: `SPEC-45 phase A fixes (2): edited-scenario decisions, sales and repayments, shadow-price cross-checks`

- **Punto 2, test 5:** en las tres ediciones (soja +20 %, capital ×2, rinde de maíz −15 %), agregá `max|x_highs − x_dora| < 0,01` además del VNP. **No relajes la tolerancia.** Si alguna falla porque el programa lineal tiene óptimos múltiples (dos planes con el mismo VNP), no lo tapes:
  - comprobá que el `x` de HiGHS es factible en el modelo de DORA y da el mismo VNP;
  - decilo en el handoff, con qué variables difieren.
- **Agregá una cuarta edición: soja −20 %.** Es la que se va a usar en la demo, porque cambia el plan: la soja baja a 0 ha y el maíz sube a 783 ha. Con las mismas comparaciones.
- **Punto 3, test 11:** compará contra DORA, dentro de 0,01:
  - la columna M de la Caja (crédito cancelado);
  - Estrategia de venta: las ventas por cultivo, quincena y canal, y el stock en silo por quincena.

  Hacelo también con la edición soja −20 %, donde el plan cambia de verdad.
- **Punto 4, test 13:** agregá los cruces con lo que DORA ya publica:
  - dual de `cash_p0` − 1 = `res.capital_shadow_price` (± 1e-4);
  - duales `credit_p*` = `res.credit_shadow_price[p]` con el mismo factor de impuesto que usa el motor (si no coinciden, explicá por qué en el handoff; no ajustes el test para que pase);
  - el número de la tierra en Resumen = `res.land_shadow_price`.
- **Fila 7 de Modelo:** el rótulo dice qué es el costo reducido: "Costo reducido (DORA): USD de VNP que se pierden por cada unidad que se fuerza en el plan". Revisá que el signo coincida con esa frase. Si hoy está al revés, cambiá el signo en la hoja (no en el motor) y anotalo.
- **Punto 7:** en el handoff, una línea que diga que el aviso "Cambiaste el modelo" de Resumen A1 revisa solo 15 celdas y que el control completo lo hace `read_plan_xlsx`.

## Commit 3: handoff y log (puntos 5 y 6)

Mensaje: `SPEC-45 phase A fixes (3): handoff with real outputs, server.py note, Wednesday manual test`

- **Punto 5:** explicá en el handoff por qué borraste el parche de `DORA_OFFLINE` en `mcp_server/server.py`:
  - qué test fallaba o qué archivo de `dora/data` se ensuciaba;
  - que `feeds.refresh` ya tiene su guarda (`feeds.py:366`), pero solo cuando `feed is None`.

  Si algún test llama a `refresh` con un `feed` propio sin red, decilo. No cambies `server.py` de nuevo.
- **Punto 6:**
  - **Números reales.** Regenerá todos los números del handoff con la salida real de los tests de hoy. El handoff dice 660.186 USD para pampas_core y el código da 1.036.105. Decí con qué curvas de precios (`as_of` de `dora/data/price_curves`).
  - **Comentario del test 12.** Corregí "credit line is 0": son 100.000 USD.
  - **Sección "Lo que Guillermo prueba a mano el miércoles":**
    1. Subir a Google Sheets la planilla de Pergamino (`pampas-core-2000ha.xlsx`).
    2. Ver si la hoja oculta `__OpenSolver__` sobrevive a la subida, y si OpenSolver carga el modelo solo. Si no, cargarlo con el recuadro de la hoja Modelo.
    3. Bajar la soja un 20 % en Supuestos, resolver con OpenSolver, y comparar con lo que da DORA: la soja baja a 0 ha y el maíz sube a unas 783 ha.
    4. Mirar que la Caja y la Estrategia de venta cambian, y que el aviso dice "Plan recalculado fuera de DORA".
- **Log:** una línea por commit en `docs/handoff/spec-40-41-log.md`.

## Reglas de siempre
- Tocá solo `dora/spreadsheet.py`, `tests/test_spec45.py`, `scripts/make_example_sheets.py`, las planillas de ejemplo y su README, y los dos archivos del handoff.
- **`dora/engine.py` no se toca.**
- Después de cada commit:
  - corré `tests/test_spec45.py`, `tests/test_spec42.py` y la **suite completa** (0 fallados);
  - `git status --porcelain dora/data observatory` tiene que quedar vacío, sin restaurar nada a mano;
  - pegá la salida real en el handoff.
- Costo cero: nada llama a modelos de lenguaje ni a servicios pagos.
- No redespliegues. Sin merge ni push. Ninguna clave en logs, handoff ni línea de comando.
- Cuando termines, Claude revisa los tres commits.
