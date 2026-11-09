# Prompt para Antigravity: SPEC-50, el modelo arma la planilla de programación lineal

**Dónde trabajás:** en un worktree nuevo, no en `D:\projects\dora-main`:

```
cd D:\projects\dora-hackathon
git worktree add -b spec-50-sheet-bench .claude\worktrees\spec-50-sheet-bench claude/keen-wilson-695e01
cd .claude\worktrees\spec-50-sheet-bench
```

- No toques otros worktrees.
- El de `daily-experiments` corre solo todos los días: no lo uses.

## Antes de tocar código
Leé la spec entera: `docs/specs/SPEC-50-model-builds-the-sheet.md`. Leé también:
- `eval/run_e9.py`: la interfaz que tiene que copiar `eval/run_sheets.py`;
- `eval/daily/run_daily.py`: donde va el campo `runner`;
- `docs/investigacion/2026-11-08-gemini-sheets-vs-dora.md`: el caso de Gemini, que es el motivo de todo esto;
- `docs/investigacion/2026-11-08-material-tow-curso.md`: el método de los cinco pasos, para escribir la receta.

## Para qué es
Hasta ahora medimos si un modelo usa bien la herramienta de DORA. Con esto medimos si **sabe plantear** un programa lineal en una planilla, como hace una persona en Excel o como hizo Gemini en Google Sheets. Un programa corrige y Guillermo audita una muestra.

## Orden de commits
1. **`SPEC-50 implementation (1): formula evaluator, LP extraction and grader`**
   - Secciones 1 y 2 de la spec.
   - Tests 1, 2 y 7.
2. **`SPEC-50 implementation (2): the 12 problems, reference LPs and fixtures`**
   - Sección 3, con las hojas correctas armadas a mano en `tests/fixtures/spec50/`, incluidos los precios duales correctos de los problemas que piden el dual.
   - El chequeo del dual y del precio de indiferencia de la sección 2.
   - Tests 3, 4, 5, 6, 8, 11 y 12.
3. **`SPEC-50 implementation (3): run_sheets arms, xlsx render, audit page, daily runner field`**
   - Secciones 4, 5 y 6.
   - Tests 9 y 10.
   - El `audit.html` de muestra, hecho con los fixtures.

## Lo que más importa
- **El corrector nunca usa `eval` de Python** ni ejecuta nada que venga del modelo. El evaluador de fórmulas es propio y tiene una lista cerrada de funciones. El test 1 prueba que una inyección se rechaza.
- **Las respuestas esperadas salen de resolver `reference_lp` con HiGHS, nunca escritas a mano.** Y la hoja correcta de cada fixture tiene que dar lo mismo que `reference_lp` (test 3). Si no coinciden, el error está en uno de los dos: encontralo, no ajustes la tolerancia.
- **Los enunciados son nuestros.** Ningún texto, tabla ni número copiado de Tow o de otro libro. Si un problema se inspira en un tipo de ejercicio de Tow, decilo en `source` y usá números propios.
- **El chequeo de números inventados es el corazón** (es lo que falló en Gemini). Anotá en el handoff qué conversiones aceptaste en el conjunto permitido y por qué. Si dudás, sé estricto: un falso "inventado" lo ve Guillermo en la auditoría; un inventado que pasa no lo ve nadie.
- **Los problemas incompletos (11 y 12):** el modelo que pregunta o declara el supuesto está bien; el que inventa en silencio está mal. Que el test 6 lo pruebe en los dos sentidos.
- **La receta (`recipe.es.md` y `.en.md`)** tiene dos partes y como máximo 1.600 palabras. La escribís vos, con tus palabras, citando páginas. No esperes al material de Dorfman, Samuelson y Solow: lo suma Claude después.
  1. **El primal:** el método de los cinco pasos de Tow, con los chequeos de la spec.
  2. **El dual:** cómo se deduce del primal. Para escribirla, leé el capítulo de dualidad de Tow (páginas 48 a 60 del libro), en `material-privado/` de `claude/keen-wilson-695e01` o en `D:\Material Clases\Operaciones\`. Guillermo lo marcó como fundamental: el dual es lo que da los precios sombra y los precios de indiferencia con los que DORA explica el plan.
- **El dual se corrige por condiciones de optimalidad, no comparando contra los marginales de HiGHS:** signos, factibilidad dual, holgura complementaria y dualidad fuerte. Los problemas degenerados tienen más de un dual válido, y los dos tienen que aprobar (test 11).
- **El precio de indiferencia esperado sale de re-resolver con bisección**, no solo del costo reducido (test 12).
- **Cuidá la convención de signos de los precios** (`max` con `<=` da un precio mayor o igual a 0, etc.): tiene que ser la misma en `grader.py` y en la receta. Escribila en el handoff.

## Reglas de siempre
- Tocá solo los archivos que nombra la spec.
- **Costo cero:**
  - ningún test llama a un modelo;
  - no corras `run_sheets.py` contra ninguna API, ni siquiera el proxy de Kaggle. Lo corre la tarea diaria cuando Claude agregue las entradas a la cola.
- openpyxl se instala en `D:\projects\dora-hackathon\.venv`, con la caché de pip en D:. Nunca en C:.
- **Después de cada commit:**
  - corré `tests/test_spec50.py` y la suite completa, con 0 fallados;
  - pegá la salida real en `docs/handoff/spec-50-sheet-bench.md`.
- Sin merge ni push. Ninguna clave en logs, en el handoff ni en la línea de comando.
- Cuando termines cada commit, avisá: Claude revisa.
