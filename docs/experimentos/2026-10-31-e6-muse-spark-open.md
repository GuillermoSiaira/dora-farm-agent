# E6: Muse Spark Open en Baseten (31/10/2026)

**Pregunta:** ¿la arquitectura de DORA sigue andando con otro modelo de Meta, servido por otro proveedor? Es E1 completo (39 preguntas, 5 repeticiones, condiciones A, B y C) con Muse Spark Open en la API por token de Baseten. Se compara con E1 hecho con Muse Spark 1.3 Standard ([ficha](2026-10-30-e1-completo-muse-spark.md)) y con Muse Spark 1.3 Contributor.

**Para leer las respuestas:** [página con las tres condiciones lado a lado](https://claude.ai/artifact/4LRbQBFNArd8mTTpu962gg) (también en [`2026-10-31-e6-respuestas.html`](2026-10-31-e6-respuestas.html)).

## Montaje
- **Modelo:** `meta-models/muse-spark-open-1026`, en la API compatible con OpenAI de Baseten (`https://inference.baseten.co/v1`).
  - Es el que Baseten lista como "[HACKATHON] Muse Spark Open": los mismos pesos (`Muse-Spark-Open-816B-A42B-NVFP4`) que el modelo público `meta-models/muse-spark-open`.
  - La clave del hackathon da 403 con el modelo público ("please check the api-key you provided") y funciona con el `-1026`. Por eso `run_eval.py` usa el `-1026` por defecto.
  - Según el listado `/v1/models` de Baseten, soporta herramientas (`tools`), modo JSON y razonamiento, y tiene un contexto de 1.048.576 tokens.
- **Precio:** 1,25 / 0,15 / 4,25 USD por millón de tokens de entrada / entrada en caché / salida, el mismo que Muse Spark 1.3 Standard. Fuentes: baseten.co/pricing y `/v1/models`, leídos el 31/10 (`eval/pricing.json`).
- **Condiciones, preguntas y respuestas exactas:** las mismas de E1.
  - **A:** el modelo solo, sin herramientas.
  - **B:** DORA sin verificador.
  - **C:** DORA completo.
  - Preguntas en `eval/questions.jsonl` y `eval/questions_spec20.jsonl`; respuestas en `eval/answers.jsonl` y `eval/answers_spec20.jsonl`.
- **Código:** commit `b76094f`.
  - El archivo de resultados dice `b76094f-dirty` porque, mientras corría, se editó `eval/answers_page.py`, que solo arma la página de lectura.
  - `b76094f` agrega `max_retries=6` al cliente, para que un error pasajero de la API no corte una corrida larga. No cambia ninguna respuesta.
- **Comando** (desde la raíz, con `BASETEN_API_KEY` en `.env`; para A se agrega `--baseline`, para B `--no-verifier` y para C nada):
  `python eval/run_eval.py --questions eval/questions.jsonl eval/questions_spec20.jsonl --answers eval/answers.jsonl eval/answers_spec20.jsonl --runs 5 --provider baseten --concurrency 4`
- **Horarios:**
  - Las tres condiciones empezaron juntas a las 18:35.
  - B terminó a las 18:49 y C a las 18:53.
  - A terminó a las 19:42.
- **Piloto:** q04, q22 y q31 en C, una corrida: 3 de 3 correctas y verificadas, 0,13 USD.

## Resultado

Las tres columnas se cuentan con el mismo script sobre los archivos crudos. En "mismo número en las 5" se cuentan solo las preguntas en las que las 5 repeticiones devolvieron un número del motor. Por eso los totales no coinciden con los de la ficha de E1.

### A · el modelo solo

| | Open (Baseten) | 1.3 Standard (Meta) |
|---|---|---|
| Respuestas correctas | 66 de 180 (37 %) | 69 de 180 (38 %) |
| Preguntas con las 5 correctas | 9 de 36 | 9 de 36 |
| Mismo número en las 5 | 5 de 14 | 5 de 32 |
| Respuestas con algún número sin respaldo | 131 de 195 | 154 de 195 |
| Planes que no se pueden cumplir | 5 de 121 | 9 de 159 |
| Tiempo por respuesta (mediana) | 91,0 s | 72,8 s |
| Tokens por pregunta, entrada / salida | 1.781 / 22.837 | 1.658 / 13.624 |
| Costo de la corrida (a precio de lista) | 19,15 USD | 11,69 USD |

### B · DORA sin verificador

| | Open (Baseten) | 1.3 Standard | 1.3 Contributor |
|---|---|---|---|
| Respuestas correctas | 180 de 195 (92 %) | 186 de 195 (95 %) | 186 de 195 (95 %) |
| Preguntas con las 5 correctas | 32 de 39 | 36 de 39 | 36 de 39 |
| Mismo número en las 5 | 29 de 32 | 30 de 31 | 33 de 34 |
| Respuestas con algún número sin respaldo | **118 de 195** | 23 de 195 | 21 de 195 |
| Planes que no se pueden cumplir | 0 de 153 | 0 de 152 | 0 de 155 |
| Tiempo por respuesta (mediana) | 16,5 s | 18,1 s | 27,4 s |
| Tokens por pregunta, entrada / salida | 42.935 / 2.201 | 40.066 / 3.535 | 43.118 / 3.678 |
| Costo de la corrida (a precio de lista) | 3,97 USD | 6,39 USD | 0,33 USD |

### C · DORA completo

| | Open (Baseten) | 1.3 Standard | 1.3 Contributor |
|---|---|---|---|
| Respuestas correctas | 182 de 195 (93 %) | 189 de 195 (97 %) | 186 de 195 (95 %) |
| Preguntas con las 5 correctas | 34 de 39 | 36 de 39 | 35 de 39 |
| Mismo número en las 5 | 30 de 33 | 30 de 31 | 30 de 32 |
| Respuestas que el verificador tuvo que corregir | **127 de 195** | 19 de 195 | 16 de 195 |
| Respuestas verificadas al mostrarse | 195 de 195 | 195 de 195 | 195 de 195 |
| Planes que no se pueden cumplir | 0 de 154 | 0 de 150 | 0 de 152 |
| Tiempo por respuesta (mediana) | 20,9 s | 18,5 s | 28,6 s |
| Tokens por pregunta, entrada / salida | 57.125 / 3.399 | 41.403 / 3.807 | 45.163 / 3.893 |
| Costo de la corrida (a precio de lista) | 5,38 USD | 6,54 USD | 0,34 USD |
| Costo por pregunta | 0,028 USD | 0,034 USD | 0,002 USD |

Salida cruda en [`eval/results/e6-baseten/`](../../eval/results/e6-baseten/): `e1_baseline.json`, `e1_no_verifier.json`, `e1_with_verifier.json`, el piloto y los logs. Para comparar se usaron estos archivos:
- **Standard:** `eval/results/muse-spark-1_3_*_20261030_*.json`, commit `5daa7de`.
- **Contributor:** `muse-spark-1_3-contributor_*_20261031_*.json`, commit `b38ce88`, que están en el checkout `dora-e1`.

### Los errores de DORA en C, uno por uno
- **q33, comparar Pergamino con Iowa (4 de 5).** Es el mismo caso que en Standard. El motor devuelve el número esperado (372,18 USD por ha sembrada), pero DORA no lo escribe en la respuesta. Es un problema de la pregunta de evaluación.
- **q30, "plantar en -50 hectáreas" (3 de 5).** Hay que rechazar la pregunta. Open la toma como 50 ha y arma un plan.
- **q03 (3 de 5) y q12 (2 de 5), insumos a 90 días con recargo.** DORA armó un escenario distinto del pedido. En q12, dos veces devolvió el valor del escenario base, 88.186,6 USD, en vez de 92.191,18. Los números salen del motor, así que pasan el verificador. Es el mismo tipo de error que q13 en Standard.
- **q38, cuánto vale agrandar el silo (1 de 5).** En una repetición, el número del motor fue 0 en vez de 5,96.

### Por qué tantos números sin respaldo
Open hace cuentas propias con los números del motor. Por ejemplo, en q35 escribe "16,5 sobre 208,5 = 7,9 %" y "tranquera 192,0". Cada cuenta está bien hecha, pero el número no lo devolvió ninguna herramienta.
- **Sin verificador (B):** 118 de 195 respuestas salieron con al menos un número así. Con Standard fueron 23.
- **Con verificador (C):** todas se corrigieron antes de mostrarse.

## Costo
- **Gasto en Baseten, a precio de lista:** unos 28,7 USD.
  - Las tres condiciones: 28,50 USD.
  - Piloto: 0,13 USD.
  - Pruebas de conexión: pocos centavos.
- **A fue lo más caro (19,15 USD):** Open, solo, escribe unos 22.800 tokens por pregunta haciendo las cuentas a mano.
- **El saldo real de créditos de Baseten no se verificó:** Guillermo tiene que mirarlo en app.baseten.co.
- **Este experimento pasó lo que se había pensado gastar** (unos 25 USD de los 100), aunque no superó el tope de 30 USD.

## Qué se puede concluir
- **La arquitectura funciona con otro modelo y otro proveedor sin cambiar nada de DORA.** Solo cambió la dirección de la API y el nombre del modelo. En C, el 100 % de las respuestas salió verificada y ningún plan fue imposible.
- **Solo, Open es tan malo como Standard para dar el número:** 37 % contra 38 %. Escribe más (cuesta más) y propone algunos planes imposibles: 5 de 121.
- **Con DORA acierta un poco menos que Standard:** 93 % contra 97 %. Las diferencias son de armado del escenario (q03, q12) y de una pregunta que había que rechazar (q30), no de números inventados.
- **El verificador trabaja mucho más con Open:** corrigió 127 de 195 respuestas, contra 19 con Standard. Con un modelo que tiende a hacer cuentas propias, el verificador es lo que mantiene la garantía.
- **Por pregunta, C con Open sale algo más barato que con Standard** al mismo precio por token (0,028 contra 0,034 USD), porque escribe menos. Lee más, porque hay más rondas de corrección, pero gran parte de esa entrada se cobra como caché.

## Qué aprendimos
- **"El mismo modelo" puede tener varios nombres.** La clave del hackathon no abría `muse-spark-open`, pero sí `muse-spark-open-1026`, con los mismos pesos. El error decía "revisá la clave", y el problema era el permiso sobre ese modelo. Pedir la lista de modelos (`/v1/models`) mostró la salida.
- **El verificador vale más cuanto peor se porta el modelo.** Con Standard casi no tenía trabajo. Con Open frenó más de la mitad de las respuestas por números calculados de cabeza. Sin verificador (B), esas respuestas le habrían llegado al productor.
- **Verificar números no es verificar el escenario.** Igual que en E1, los errores que quedan en C son escenarios armados distinto de lo que se pidió (q03, q12) o una pregunta que había que rechazar (q30). El próximo control sigue siendo el mismo: comparar el escenario con lo que dice la pregunta.
- **El costo depende de cómo escribe el modelo, no solo del precio por token.** Open y Standard cobran igual, pero Open solo gastó un 64 % más (escribe más cuentas a mano) y Open con DORA un 18 % menos (escribe menos).
- **Correr en paralelo y con reintentos acorta la espera.** Las tres condiciones corrieron a la vez, cuatro preguntas por proceso, y B y C terminaron en menos de 20 minutos.
