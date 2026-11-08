# Prompt para Antigravity: SPEC-49, venta a término como decisión, con riesgo de precio

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon` salvo para copiar la spec.

**Antes de empezar:** corré `git status`. Si hay cambios sin commitear, no los pises: avisá y esperá.

## Rama y spec
- Creá `spec-49-price-risk` desde `spec-45-spreadsheet-v2`. La fase A quedó aprobada en `fc6a4b2`.
- Traé la spec:
  ```
  git show claude/keen-wilson-695e01:docs/specs/SPEC-49-forward-sales-price-risk.md > docs/specs/SPEC-49-forward-sales-price-risk.md
  ```
  Si esa rama no existe en dora-main, copiala de `D:\projects\dora-hackathon\.claude\worktrees\keen-wilson-695e01\docs\specs\SPEC-49-forward-sales-price-risk.md`.
- **Leela entera antes de tocar código.** También leé `_optimize_stochastic` en `dora/engine.py` (SPEC-25): la nueva función se arma igual, en dos etapas.

## Para qué es
El productor pregunta "¿vendo a término o a cosecha, y cuánto?". Hoy DORA solo toma la venta a término como dato. Esta spec la convierte en decisión, con escenarios de precio y una frontera entre resultado esperado y riesgo (media-CVaR).

Guillermo quiere tenerlo para mostrarlo pronto. **Lo más importante es que sea correcto y verificable, no que tenga todo:** la sección 4 (precio × clima) puede ir en el último commit.

## Orden de commits

1. **`SPEC-49 implementation (1): price scenarios and the two-stage model`.**
   - Secciones 1, 2 y 3 de la spec: campos nuevos, escenarios de precio deterministas, `_optimize_price_risk` y el despacho en `optimize`.
   - El archivo `dora/data/price_risk_<region>.json` de las 4 regiones. Si no podés calcular la volatilidad con datos que ya están en el repo, poné los valores de la spec con `"placeholder": true`, y decilo.
   - Tests 1, 2, 3, 4, 6, 9 y 10.
2. **`SPEC-49 implementation (2): hedge_analysis tool, frontier, independent per-scenario check`.**
   - Sección 5: la herramienta `hedge_analysis`, expuesta en `mcp_server/server.py`, con la frontera, los duales, el precio de indiferencia y el texto.
   - La guía del agente.
   - Tests 5 y 7.
3. **`SPEC-49 implementation (3): price x climate grid`.**
   - Sección 4.
   - Test 8.

## Lo que más importa
- **El camino sin `price_risk` no cambia.** El test 1 compara contra `optimize` en los 6 escenarios de ejemplo de la SPEC-45, con tolerancia 1e-6. Si falla, no sigas.
- **El test 7 es la verificación central y no se ablanda.**
  - Se fija la primera etapa (hectáreas y toneladas a término).
  - Cada escenario se re-resuelve aparte con el motor determinista de siempre: sus precios, `min_area = max_area` y la venta a término como `forward_sale`.
  - Hay que comparar el VNP de cada escenario (± 0,01 USD) y recalcular el CVaR ordenando esos VNP, sin usar el LP.

  Si no coincide, **no aflojes la tolerancia**: buscá por qué y contalo en el handoff.
- **No anticipación:** todo lo que se decide antes de conocer el precio (siembra, gastos tempranos, crédito temprano) es igual en todos los escenarios. Decí en el handoff cómo lo implementaste (filas de igualdad, o variables armadas una sola vez) y en qué quincena empieza la segunda etapa.
- **No cambies el modelo determinista de `optimize` ni `_optimize_stochastic`.** Si compartís código con ellos, el test 1 y los tests de la SPEC-25 tienen que seguir dando lo mismo.
- **El texto de `hedge_analysis` sale solo de números del resultado.**
  - Nunca "conviene cubrirse" sin números.
  - Nunca recomendar un corredor, un mercado o un producto.
  - **DORA no elige el nivel de riesgo por el productor:** muestra la frontera y él elige.
- **Si la volatilidad es supuesta**, cada respuesta lo dice: "volatilidad supuesta, no medida".
- **Medí y anotá en el handoff** el tamaño del LP (variables y filas) y el tiempo de resolución con 9 escenarios, y con la grilla si llegás al commit 3.

## Reglas de siempre
- Tocá solo los archivos que nombra la spec.
- Después de cada commit:
  - corré `tests/test_spec49.py`, los tests de la SPEC-25 y la **suite completa** (0 fallados);
  - `git status --porcelain dora/data observatory` tiene que quedar vacío **sin restaurar nada a mano**. Si algo lo ensucia, encontrá por qué y decilo.
  - pegá la salida real en el handoff (`docs/handoff/spec-49-price-risk.md`).
- Una línea por commit en `docs/handoff/spec-40-41-log.md`.
- Costo cero: nada llama a modelos de lenguaje ni a servicios pagos.
- No redespliegues. Sin merge ni push. Ninguna clave en logs, handoff ni línea de comando.
- Cuando termines cada commit, avisá: Claude revisa.

## La prueba en vivo (no la hacés vos; dejala anotada en el handoff como pendiente para Guillermo)
En la app: "Tengo 500 ha propias en Pergamino y 260.000 dólares. ¿Me conviene vender parte de la soja a término? Me ofrecen 330 a mayo." La respuesta tiene que:
- llamar a `hedge_analysis`;
- mostrar la frontera en una tabla corta;
- decir si la volatilidad es medida o supuesta;
- no inventar ningún porcentaje que no haya calculado.
