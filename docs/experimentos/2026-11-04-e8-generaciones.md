# E8: cuatro modelos de Meta, solos y dentro de DORA (4/11/2026)

**Pregunta.** ¿La arquitectura de DORA (motor de optimización + verificador + herramientas) hace que importe menos qué modelo se usa? Es el primer paso de la línea de investigación "eficiencia de las arquitecturas alrededor de los LLM".

**Qué se corrió.** Las preguntas de E1 (`eval/questions.jsonl`, 36 preguntas; 33 con respuesta numérica para el modelo solo), 1 repetición, con Muse Spark 1.1 y 1.2 por la API de Meta, en dos condiciones: el modelo solo (`--baseline`) y DORA completo (con verificador). Commit `cee1609` de `main` (con cambios locales solo en docs). Se intentó una curva por tamaño con modelos de 2B, 9B, 27B y 120B en Baseten: la clave del hackathon solo habilita los modelos de Meta (403 en los demás), así que la curva es por generación, no por tamaño.

```
python eval/run_eval.py --model muse-spark-1.1 --runs 1 --concurrency 4 --output eval/results/e8/muse-spark-1_1_dora.json
python eval/run_eval.py --model muse-spark-1.1 --runs 1 --concurrency 4 --baseline --output eval/results/e8/muse-spark-1_1_alone.json
(ídem con muse-spark-1.2)
```
Salida cruda: `eval/results/e8/`. Gráfico: `eval/plot_e8.py` → `docs/screenshots/e8-generations.png`.

| Modelo | Solo: correctas | DORA: correctas | Solo: planes posibles | DORA: planes posibles | Tokens de salida por respuesta (solo → DORA) |
|---|---|---|---|---|---|
| Muse Spark 1.1 (E8, ×1) | 12 de 33 (36 %) | 36 de 36 (100 %), 100 % verificadas | 26 de 30 | 100 % | 19.069 → 4.660 |
| Muse Spark 1.2 (E8, ×1) | 12 de 33 (36 %) | 34 de 36 (94 %), 100 % verificadas | 24 de 30 | 100 % | 14.225 → 3.570 |
| Muse Spark 1.3 (E1, ×5) | 69 de 180 (38 %) | 189 de 195 (97 %) | — | 0 imposibles | — |
| Muse Spark Open (E6, ×5) | 66 de 180 (37 %) | 182 de 195 (93 %) | — | 0 imposibles | — |

**Qué muestra.** Solos, las cuatro versiones aciertan lo mismo (36-38 %): la generación del modelo no cambia el resultado en este problema. Dentro de DORA todas pasan a 93-100 %, también las dos más viejas. Con DORA cada modelo escribe 4 veces menos (el motor hace la cuenta); a cambio lee más (unos 67.000 tokens de entrada por pregunta, con buena parte en caché). No calculamos el costo en USD de 1.1 y 1.2 porque no tenemos su precio de lista en `eval/pricing.json`.

**Límites.** 1 repetición en 1.1 y 1.2 contra 5 en 1.3 y Open: el 100 % de 1.1 es sobre 36 respuestas y no hay medida de variación. No es una curva por tamaño de modelo: para eso hacen falta modelos abiertos de varios tamaños (siguiente paso, con crédito de cómputo).

## Qué aprendimos
- La parte difícil del problema (optimizar con restricciones de caja, crédito y tierra) no la resuelve una generación más nueva del modelo: las cuatro aciertan lo mismo solas.
- Sacar la matemática del modelo y verificar cada número hace que hasta la versión más vieja llegue al 94-100 %. La arquitectura vale más que la versión del modelo.
- Medir antes de afirmar: la curva por tamaño quedó como hipótesis porque no tuvimos acceso a los modelos; lo que se muestra es solo lo medido.
