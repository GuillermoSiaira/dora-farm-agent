# E1, piloto: Muse Spark solo contra DORA (30/10/2026)

**Pregunta:** con la misma pregunta y los mismos datos, ¿un modelo de lenguaje solo da números correctos, estables y planes que se pueden cumplir? ¿Y DORA? (`docs/plan-de-pruebas.md`, E1).

## Montaje
- **Modelo:** Muse Spark 1.3, API de Meta (`api.meta.ai`), en las tres condiciones.
- **Condiciones:**
  - **A, el modelo solo:** recibe la pregunta y, en texto, los mismos datos con que resuelve el motor (rindes, pagos por quincena, precios netos por quincena, capital, crédito, silo, rotación). Sin herramientas. Devuelve un JSON con el plan y el número pedido (`eval/baseline.py`).
  - **B, DORA sin verificador:** el agente con herramientas.
  - **C, DORA completo:** herramientas y verificador.
- **Preguntas (5):** q04 (valor presente con crédito), q08 (hectáreas de trigo), q15 (valor presente con un forward), q25 (Iowa, mínimo de maíz), q37 (precio de equilibrio del silo bolsa en Balcarce). Respuestas exactas del motor en `eval/answers*.jsonl`, comprobadas contra el motor actual antes de correr.
- **Repeticiones:** 5 por pregunta y condición, 75 respuestas en total.
- **Código:** commit `b1e4c03` (B y C). A registró `c6c2571` porque el registro lee el commit al terminar y en el medio se commitearon dos specs; entre los dos commits solo cambiaron documentos en `docs/`, no el código.
- **Comando** (desde la raíz, con `--baseline`, `--no-verifier` o nada para A, B y C):
  `python eval/run_eval.py --ids q04,q08,q15,q25,q37 --questions eval/questions.jsonl eval/questions_spec20.jsonl --answers eval/answers.jsonl eval/answers_spec20.jsonl --runs 5 --provider meta`

## Resultado

| | A · modelo solo | B · DORA sin verificador | C · DORA completo |
|---|---|---|---|
| Respuestas correctas (tolerancia del verificador) | 11 de 25 (44 %) | 25 de 25 | 25 de 25 |
| Respuestas en que cada número sale de los datos, la pregunta o una herramienta | 0 de 25 | 24 de 25 | 25 de 25 |
| Preguntas con el mismo número en las 5 repeticiones | 2 de 5 | 5 de 5 | 5 de 5 |
| Planes que se pueden cumplir | 24 de 25 | 25 de 25 | 25 de 25 |
| Lo que deja sobre la mesa el plan (promedio) | 0,07 % (máximo 0,42 %) | 0 | 0 |
| Tiempo por respuesta (mediana) | 65,5 s | 17,4 s | 16,9 s |
| Tokens por pregunta, entrada / salida | 1.877 / 12.915 | 38.580 / 3.420 | 40.188 / 3.480 |

### Pregunta por pregunta, condición A

| Pregunta | Respuesta exacta | Lo que dijo el modelo solo en las 5 repeticiones | Correctas |
|---|---|---|---|
| q04, valor presente | 88.186,60 | 88.070 · 88.129 · 88.070 · 88.028 · 88.214 | 0 |
| q08, hectáreas de trigo | 200 | 200 · 200 · 200 · 200 · 200 | 5 |
| q15, valor presente con forward | 88.145,52 | 87.700 · 88.031 · 87.714 · 88.080 · 87.777 | 0 |
| q25, maíz en Iowa | 250 | 250 · 250 · 250 · 250 · 250 | 5 |
| q37, equilibrio del silo bolsa | 264,90 | 264,47 · 264,47 · 264,47 · 264,47 · 264,91 | 1 |

En una repetición de q37, el plan del modelo solo no se podía cumplir: le faltaban 1.198 USD de capital y crédito.

Salida cruda: [`eval/results/muse-spark-1_3_baseline_20261030_140534.json`](../../eval/results/muse-spark-1_3_baseline_20261030_140534.json), [`..._no_verifier_20261030_134752.json`](../../eval/results/muse-spark-1_3_no_verifier_20261030_134752.json), [`..._with_verifier_20261030_134752.json`](../../eval/results/muse-spark-1_3_with_verifier_20261030_134752.json). Cada una tiene, por respuesta, el texto, el plan, la evaluación del plan en el motor, el tiempo y los tokens.

## Qué se puede concluir
- **El modelo solo razona bien, pero no da el número.** Sus planes quedan muy cerca del óptimo (en promedio deja 0,07 % sobre la mesa). Pero los valores presentes le salen corridos entre 27 y 445 USD, y **cambian de una vez a otra**: en q04 y q15 dio cinco números distintos para la misma pregunta.
- **Acierta lo que se deduce sin cuentas:** 200 ha de trigo es la mitad de 400 (el tope de rotación) y 250 ha de maíz es la mitad de 500. Falla donde hay que hacer las cuentas de la campaña.
- **Todas sus respuestas tienen números que calculó de cabeza y no salen de los datos ni de la pregunta,** así que nadie los puede rastrear. En DORA completo, ninguna.
- **DORA da el mismo número cada vez, exacto, con plan factible y óptimo,** en la cuarta parte del tiempo.
- **Es un piloto:** 5 preguntas. Con los datos dados, el modelo solo hizo un buen trabajo; las preguntas de decisión nuevas (cuánto sembrar, guardar o vender, tomar crédito) van a medir mejor la brecha.

## Costo
La API de Meta no publica precio por token sin un acuerdo (`eval/pricing.json`), así que el costo se informa en tokens. El modelo solo usa poca entrada (1.877 tokens) pero mucha salida (12.915): razona largo para hacer a mano las cuentas que el motor hace en milisegundos.
