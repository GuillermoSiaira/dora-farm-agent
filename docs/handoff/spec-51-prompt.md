# Prompt para Antigravity: SPEC-51, la receta como grafo

**Dónde trabajás:** en un worktree nuevo, cortado de la rama de la SPEC-50, que ya está revisada:

```
cd D:\projects\dora-hackathon
git worktree add -b spec-51-graph-recipe .claude\worktrees\spec-51-graph-recipe spec-50-sheet-bench
cd .claude\worktrees\spec-51-graph-recipe
```

- No toques otros worktrees.
- El de `daily-experiments` corre solo todos los días: no lo uses.

## Antes de tocar código
Leé la spec entera. Está en el worktree `keen-wilson-695e01`, no en el tuyo: `D:\projects\dora-hackathon\.claude\worktrees\keen-wilson-695e01\docs\specs\SPEC-51-recipe-as-graph.md`. Copiala a `docs/specs/` de tu worktree en el primer commit.

Leé también:
- todo `eval/sheets/` y `eval/run_sheets.py`: lo hiciste vos en la SPEC-50 y la SPEC-51 lo reutiliza sin cambiarlo;
- `docs/material/dss/01-receta-de-modelado.es.md`, sección de signos (DSS p. 145), del worktree `keen-wilson-695e01`.

## Para qué es
Comparar la receta en **texto** (SPEC-50) con la receta como **grafo** de actividades e ítems. El orden es fijo: primero, ¿acierta más el modelo?; después, ¿cuesta menos por problema resuelto? Interesan sobre todo los modelos chicos que están en el umbral.

## Orden de commits
1. **`SPEC-51 implementation (1): graph format, compiler and graph checks`**
   - Secciones 1 y 2 de la spec: `eval/sheets/graph.py` y `eval/sheets/graph_checks.py`.
   - Los 12 grafos correctos en `tests/fixtures/spec51/`.
   - Tests 1, 2, 3, 4 y 5.
2. **`SPEC-51 implementation (2): graph arms, steps arm, Meta provider, audit SVG`**
   - Secciones 3, 4, 6 y 7.
   - La receta del grafo, `recipe_graph.es.md` y `.en.md`, de 600 palabras como máximo.
   - Tests 6, 7 y 8.

## Lo que más importa
- **Convención de signos:** la de DSS: consumo negativo, producción positivo. Tiene que ser una sola, escrita igual en `graph.py`, en la receta del grafo y en el handoff. El test 4 prueba que la forma "consumo ≤ capacidad" da el mismo programa lineal.
- **El compilador es código nuestro.** El modelo nunca escribe el programa lineal en el brazo `graph_only`.
- **El grafo compilado tiene que dar lo mismo que `reference_lp`** (test 1). Si no da, el error está en el grafo o en el compilador. Encontralo; no aflojes la tolerancia.
- **Los siete chequeos de grafo no usan la respuesta esperada.** Nunca leen `expected` ni `reference_lp`, porque después van a correr en DORA, con problemas reales de usuarios. Que haya un test que lo verifique: pasales un problema sin `expected` y tienen que andar igual.
- **Una sola reparación por brazo.** Así el costo queda acotado y es comparable entre brazos.
- **Métricas:** `usd_per_solved` es el número principal de costo. Hay que contar los tokens de todos los turnos, incluidas la reparación y los pasos.
- **La receta es solo para variables continuas**, igual que la de la SPEC-50. Las enteras quedan fuera.

## Proveedor Meta (Muse Spark)
- La clave ya existe: `DORA_API_KEY` y `DORA_API_BASE` en `D:\projects\dora-hackathon\.env`. El modelo es `muse-spark-1.3`.
- No la leas en los tests. El test 7 hace monkeypatch de `subprocess.run`.
- **No corras nada contra la API de Meta.** Los créditos los cuida Guillermo.

## Reglas de siempre
- Tocá solo los archivos que nombra la spec.
- **Costo cero:** ningún test llama a un modelo. No corras `run_sheets.py` contra ninguna API.
- **Después de cada commit:**
  - corré `tests/test_spec51.py`, `tests/test_spec50.py` y la suite completa, con 0 fallados;
  - pegá la salida real en `docs/handoff/spec-51-graph-recipe.md`.
- Sin merge ni push. Ninguna clave en logs, en el handoff ni en la línea de comando.
- Cuando termines cada commit, avisá: Claude revisa.
