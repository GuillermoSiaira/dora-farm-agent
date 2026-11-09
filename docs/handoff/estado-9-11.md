# Estado al 9/11 a la noche (para la próxima sesión de Claude)

## Hecho y revisado
- **SPEC-50, el banco de planillas**, en la rama `spec-50-sheet-bench`:
  - el arreglo es el commit 255565a: el dual no condiciona `solved`, y Kaggle se llama con `python -m kaggle`;
  - el merge en `daily-experiments` es e76a736 y la cola es ba56e4f;
  - en la cola vienen, en orden: s50-flash-lite (10/11 a las 10:00), s50-nano, s50-granite, s50-gemini-flash, después las e9 y al final s50-sonnet.
- **SPEC-51, la receta como grafo**, commit 1 (12b2c57 en `spec-51-graph-recipe`):
  - están `graph.py`, `graph_checks.py`, los 12 fixtures y los tests 1 a 5;
  - en total pasan 543 tests;
  - verifiqué que los chequeos no leen `expected` ni `reference_lp`.
- **Material DSS**: está todo en `docs/material/dss/` (commits 8f27d21 y 8b03246).

## Pendiente
1. Revisar el commit 2 de la SPEC-51 cuando Antigravity lo entregue. Trae los brazos de grafo, el brazo de pasos, el proveedor Meta, el SVG en la auditoría y los tests 6 a 8. El prompt está en `docs/handoff/spec-51-prompt.md`.
2. Revisar la corrida s50-flash-lite del 10/11. Pasar los resultados al mapa de investigación (artifact 215zdPbFWqgPr26AJtPMTf) y al ledger de cómputo.
3. Esperar la revisión de Guillermo de `material-privado/revision-planillas/`, sobre todo el problema 5 (¿58.525 o 64.150?) y el 8 (aserradero: el enunciado es ambiguo con el crédito). Con eso, escribir los arreglos para Antigravity:
   - los enunciados;
   - aceptar fórmulas en `lhs` y `rhs` de las restricciones, o reportar los errores de formato aparte;
   - que la receta insista en preguntar cuando falta un dato. Con la receta, flash-lite dejó de preguntar.
4. Después de esa revisión, pasar la receta DSS condensada a `eval/sheets/data/recipe.*.md`.

## No hacer
- Bedrock y Mantle quedan descartados: Guillermo dijo que no, y no hay que volver a sacarlos. Los modelos abiertos van por Kaggle, sea por el proxy o por notebooks con GPU.
- No correr nada contra Meta (`DORA_API_KEY`, muse-spark-1.3) sin el visto bueno de Guillermo.
