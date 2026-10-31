# E1 con Muse Spark 1.3 Contributor: el mismo DORA con un modelo 19 veces más barato (31/10/2026)

**Pregunta:** si DORA corre con la versión barata de Muse Spark (Contributor), ¿sigue acertando? Y el modelo barato solo, ¿falla igual que el Standard solo?

## Cómo se corrió
- **Modelo:** `muse-spark-1.3-contributor` (API de Meta). Contributor cuesta 0,10 / 0,002 / 0,20 USD por millón de tokens de entrada, caché y salida (Standard: 1,25 / 0,15 / 4,25). Meta usa el contenido para entrenar y limita la velocidad. Las preguntas no tienen datos de productores reales.
- **Código:** rama `e1-pilot`, commit `b38ce88`: el mismo de E1 con Standard más un arreglo del esquema de herramientas (`sowing_windows` tenía `minimum: null`, que Contributor rechaza con error 400; Standard lo ignoraba). Los números del motor no cambian.
- **Preguntas y condiciones:** las mismas de [E1 completo](2026-10-30-e1-completo-muse-spark.md): 39 preguntas × 5 repeticiones × A (modelo solo, `--baseline`), B (DORA sin verificador) y C (DORA completo).
- **Comando** (desde `D:\projects\dora-e1`):
  `python eval/run_eval.py --questions eval/questions.jsonl eval/questions_spec20.jsonl --answers eval/answers.jsonl eval/answers_spec20.jsonl --runs 5 --provider meta --model muse-spark-1.3-contributor` (+ `--baseline` o `--no-verifier`).
- **Resultados:** `eval/results/muse-spark-1_3-contributor_{baseline,no_verifier,with_verifier}_20261031_*.json`. [Respuestas lado a lado](2026-10-31-e1-contributor-respuestas.html).

## Resultado
| | Standard solo | Contributor solo | Contributor B | Contributor C | Standard C |
|---|---|---|---|---|---|
| Correctas (de 195) | 69 | 67 | 186 | 186 | 189 |
| Con números sin respaldo en el primer borrador | 154 | 143 | 21 | 16 | 19 |
| Verificadas | — | — | 174 | 195 | 195 |
| Planes imposibles | 9 | 6 | 0 | 0 | 0 |
| Tiempo por respuesta (mediana) | 73 s | 104 s | 27 s | 29 s | 18,5 s |

- **Fallas de C:** q33 5/5 (el control mide un número que la pregunta no pide; también falla con Standard), q17 2, q13 1, q30 1. Son las mismas preguntas que fallan con Standard; la [SPEC-27](../specs/SPEC-27-answers-and-checks.md) las trata.
- **Tiempos raros:** q05 (C) promedia 269 s y q08 (B) 391 s, por alguna repetición que esperó mucho, probablemente por el límite de velocidad. La mediana no se mueve.

## Costo
Con los precios de `eval/pricing.json`:
| | Entrada (en caché) | Salida | USD |
|---|---|---|---|
| A | 323.385 (8.098) | 2.660.163 | 0,56 |
| B | 8.407.976 (6.705.374) | 717.151 | 0,33 |
| C | 8.806.812 (7.026.693) | 759.146 | 0,34 |
| **Total** | | | **1,23** |

En C, unos 0,0018 USD por respuesta, contra 0,034 con Standard: unas 19 veces menos.

## Qué aprendimos
- **La certeza la da DORA, no el modelo caro.** El modelo barato solo acierta un tercio (34 %), igual que el caro solo (35 %). Dentro de DORA acierta el 95 %, con el 100 % de las respuestas verificadas y ningún plan imposible.
- **Lo que se pierde con el modelo barato es tiempo, no exactitud.** Tarda unos 10 segundos más por respuesta, por el límite de velocidad.
- **Un modelo más estricto encuentra errores escondidos.** El esquema con `minimum: null` andaba con Standard porque lo ignoraba; Contributor lo rechazó. Probar con más de un modelo sirve también para revisar el código.
- **Las fallas que quedan son de DORA o de las preguntas, no del modelo:** se repiten con Standard, Contributor y Muse Spark Open.
