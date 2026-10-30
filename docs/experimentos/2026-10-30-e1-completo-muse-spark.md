# E1 completo: Muse Spark solo contra DORA (30/10/2026)

**Pregunta:** con la misma pregunta y los mismos datos, ¿un modelo de lenguaje solo da números correctos, estables y planes que se pueden cumplir? ¿Y DORA? Es el [piloto](2026-10-30-e1-piloto-muse-spark.md) con las 39 preguntas de la evaluación (`docs/plan-de-pruebas.md`, E1).

**Para leer las respuestas:** [página con las tres condiciones lado a lado](https://claude.ai/artifact/TPjuBiYuq5UJXFqJffMTGF) (también en [`2026-10-30-e1-respuestas.html`](2026-10-30-e1-respuestas.html)). Tiene, por pregunta y repetición, el texto que contestó el modelo, si acertó, los números sin respaldo y la evaluación del plan en el motor. Arriba hay una sección "Mirá estas" con seis casos para empezar.

## Montaje
- **Modelo:** Muse Spark 1.3, API de Meta (`api.meta.ai`), en las tres condiciones.
- **Condiciones:** las del piloto.
  - **A, el modelo solo:** recibe los datos del motor en texto, sin herramientas.
  - **B, DORA sin verificador.**
  - **C, DORA completo.**
- **Preguntas:** 39, de `eval/questions.jsonl` y `eval/questions_spec20.jsonl`. Son 27 en castellano y 12 en inglés: crédito y capital, formulación, restricciones, sensibilidad, almacenaje y precios, regiones, logística, y casos que hay que rechazar o en los que hay que pedir un dato. Las respuestas exactas del motor están en `eval/answers*.jsonl`.
- **Repeticiones:** 5 por pregunta y condición.
- **Preguntas que A no responde:** las 3 de comparar regiones (q33, q34, q36), porque necesitan datos de dos regiones que A no recibe.
- **Código:** commit `5daa7de`, igual a `main` antes de la SPEC-25. La SPEC-25 no cambia los números de estas preguntas: se comprobó con la comparación de herramientas antes de mergearla.
- **Comando** (desde la raíz, con `--baseline`, `--no-verifier` o nada para A, B y C):
  `python eval/run_eval.py --questions eval/questions.jsonl eval/questions_spec20.jsonl --answers eval/answers.jsonl eval/answers_spec20.jsonl --runs 5 --provider meta`
- **Horarios:**
  - B y C empezaron a las 11:17 y terminaron a las 12:18 y 12:22.
  - A terminó a las 15:43.

## Resultado

| | A · modelo solo | B · DORA sin verificador | C · DORA completo |
|---|---|---|---|
| Respuestas correctas | 69 de 180 (38 %) | 186 de 195 (95 %) | 189 de 195 (97 %) |
| Preguntas con las 5 repeticiones correctas | 9 de 36 | 36 de 39 | 36 de 39 |
| Preguntas con el mismo número en las 5 repeticiones | 5 de 33 | 33 de 34 | 34 de 35 |
| Respuestas con algún número sin respaldo | 154 de 180 | 23 de 195 | 19 de 195, corregidas antes de mostrarse (100 % verificadas) |
| Planes que no se pueden cumplir | 9 de 159 | 0 de 152 | 0 de 150 |
| Lo que deja sobre la mesa un plan factible (promedio; máximo) | 0,23 %; 5,74 % | 0 (ver medición) | 0 (ver medición) |
| Tiempo por respuesta (mediana) | 76,9 s | 18,1 s | 18,5 s |
| Tokens por pregunta, entrada / salida | 1.658 / 13.624 | 40.066 / 3.535 | 41.403 / 3.807 |

Salida cruda:
- [`eval/results/muse-spark-1_3_baseline_20261030_184350.json`](../../eval/results/muse-spark-1_3_baseline_20261030_184350.json)
- [`..._no_verifier_20261030_151832.json`](../../eval/results/muse-spark-1_3_no_verifier_20261030_151832.json)
- [`..._with_verifier_20261030_152205.json`](../../eval/results/muse-spark-1_3_with_verifier_20261030_152205.json)

### Casos para mirar
- **q22, un plan que no se puede pagar.** Iowa, insumos a 60 días con 2 % de recargo.
  - El modelo solo prometió unos 206.000 USD de valor presente, las 5 veces.
  - A sus planes les faltan entre 55.900 y 58.500 USD de capital y crédito.
  - La respuesta del motor es 163.866.
- **q32, de 0,52 a 1.620.000.** "¿Cuánto rinde el capital en el período más apretado?"
  - El modelo solo dio cinco números que no se parecen entre sí.
  - DORA dio 59,6 % las 5 veces.
- **q04 y q15, el valor presente con crédito.** El modelo solo dio cinco valores distintos, todos corridos. DORA dio el exacto las 5 veces.
- **q17, una factura sin las hectáreas.** El modelo solo arma un plan igual, distinto en cada repetición. DORA pregunta para cuántas hectáreas es.
- **q06, campo alquilado con poca plata.** Las tres condiciones contestan bien: no sembrar y quedarse con los 50.000 USD.

### Los errores de DORA, uno por uno
- **q33, comparar Pergamino con Iowa** (5 en B, 4 en C). DORA contesta bien dónde conviene, Iowa. El evaluador, en cambio, busca un número que DORA casi nunca escribe: el margen por hectárea sembrada en Pergamino. Es más un problema de cómo está escrita la pregunta de evaluación que de DORA.
- **q13, un rinde de soja tres veces el habitual** (1 en C, repetición 5). DORA armó un escenario distinto del pedido y dio 374.995 USD en vez de 383.130. El número sale del motor, así que **pasa el verificador**. El verificador controla de dónde sale cada número, no si el escenario es el que pidió el productor. Es el error más importante de los que encontró E1.
- **q17 y q30, preguntas que hay que rechazar** (B: q17 2 veces, q30 2 veces; C: q17 1 vez). En la mayoría pide el dato o se niega bien. En las que fallan, completa supuestos que el productor no dijo, como 500 ha, en vez de solo preguntar.

### Medición: lo que el resumen automático cuenta mal
- **"Planes factibles: 92 % y 91 %" para B y C es un error del contador.** El contador toma como "no factible" las respuestas que no traen plan, por ejemplo cuando la pregunta pide un precio sombra o la respuesta es no sembrar. Contando solo las respuestas que proponen un plan, DORA no propuso ningún plan imposible. La tabla de arriba ya está corregida.
- **Las brechas de DORA distintas de cero también vienen de la medición:**
  - en q14 y q27, el plan redondeado a 0,1 ha da unos pocos dólares más que el óptimo, por la tolerancia de 0,5 ha;
  - en q03 (B), q23 y q37 (C), la pregunta compara dos escenarios y el evaluador tomó el plan del otro.
- **Arreglo pendiente en `eval/run_eval.py`:** que el contador no cuente "sin plan" como no factible, y que tome el plan del escenario que se pregunta. No cambia ninguna respuesta, solo el resumen.

## Qué se puede concluir
- **El modelo solo no sirve para dar el número.** Acierta el 38 % y, en 28 de las 33 preguntas con número, da números distintos en las 5 repeticiones. Además, en 154 de 180 respuestas usa números que calculó de cabeza.
- **Y a veces propone planes imposibles con mucha seguridad:** en q22 prometió 42.000 USD más que lo posible, con un plan que no se puede pagar.
- **Razona bien las decisiones simples.** Acierta lo que se deduce sin cuentas largas: no sembrar si el alquiler no se paga, o la mitad del campo por rotación. Sus planes factibles quedan, en promedio, a 0,23 % del óptimo.
- **DORA da el mismo número cada vez** en 34 de 35 preguntas, acierta el 97 % y no propuso ningún plan imposible. Tarda la cuarta parte que el modelo solo.
- **El verificador hace su trabajo:**
  - las 19 respuestas de C con números sin respaldo se corrigieron antes de mostrarse;
  - en B, 23 respuestas salieron con algún número sin respaldo.
- **Lo que el verificador no cubre:** que el escenario armado sea el que pidió el productor (q13). Es el próximo control a agregar: comparar el escenario con lo que dice la pregunta.

## Costo
- **Saldo de créditos de Meta** (dev.meta.ai, Billing):
  - 133,52 USD al empezar (11:17);
  - 117,40 USD a las ~12:15;
  - 114,17 USD a las ~13:55.
- **Costo real:** falta el saldo final, porque Meta tarda hasta una hora en registrar el gasto.
- **Precio por token:** Meta no lo publica sin un acuerdo (`eval/pricing.json`), así que la comparación entre condiciones va en tokens.
  - A gasta poca entrada y mucha salida.
  - B y C gastan mucha entrada, sobre todo la parte fija del prompt ([ficha](2026-10-30-prompt-overhead.md)), y poca salida.

## Qué aprendimos
- **Repetir muestra lo que una corrida esconde.** Con 5 repeticiones se ve que el modelo solo cambia de número casi siempre. Una corrida sola habría dado un número que parece creíble.
- **Un plan "cerca del óptimo" puede ser imposible.** El modelo solo propone planes que suenan bien. El motor encontró que a 9 les faltaba plata, en un caso más de 58.000 USD. Por eso DORA no le cree al modelo: cada plan pasa por el programa lineal, que controla cada quincena de caja.
- **Verificar números no es verificar el problema.** El verificador asegura que cada número salga del motor. Pero si el modelo arma mal el escenario, el motor resuelve bien el problema equivocado y el número pasa. Es la diferencia entre una cuenta bien hecha y la pregunta bien entendida.
- **Las métricas también se equivocan.** El resumen automático decía que DORA hacía planes no factibles. Al leer las respuestas, era el contador el que fallaba. Por eso se guarda todo crudo y se leen las respuestas, no solo los porcentajes.
- **El costo se reparte distinto.** El modelo solo escribe mucho porque hace las cuentas a mano: unos 13.600 tokens de salida por pregunta. DORA lee mucho, porque cada pedido manda las instrucciones y las herramientas, pero escribe poco, porque las cuentas las hace el motor. Si los tokens de salida cuestan más que los de entrada, como suele pasar, esa diferencia pesa en la cuenta.
