# E2: panorama regional, cómo viene la campaña en las cuatro zonas (31/10/2026)

**Pregunta:** ¿DORA da, con datos del día, una foto comparable de la zona núcleo, el sudeste de Buenos Aires, Iowa y Mato Grosso? ¿Y el agente dice cuáles datos son provisorios? (`docs/plan-de-pruebas.md`, E2).

**Para leer las respuestas:** [página de E2 y E4](https://claude.ai/artifact/PJYgpRFvd1UxfaHUqYB3pc) (también en [`2026-10-31-e2-e4-respuestas.html`](2026-10-31-e2-e4-respuestas.html)).

## Montaje
- **Modelo:** Muse Spark 1.3 Standard (`muse-spark-1.3`), API de Meta, con verificador.
- **Código:** commit `641e43e` más el script nuevo `eval/run_e2_e4.py` (no toca el motor).
- **Precios del día:** los que bajó E4 minutos antes ([ficha](2026-10-31-e4-precios-en-vivo.md)):
  - CBOT al 31/10/2026;
  - curva argentina (CBOT más base de MAGyP) y dólar del BCRA al 30/10/2026.
- **El resto de los datos no es del día:**
  - costos y rindes: MAGyP junio de 2026, Iowa State 2026, IMEA;
  - tierra, impuestos y rutas: archivos de `dora/data/`.
  - **Son provisorios:** los datos de Balcarce (tierra), los de Mato Grosso (región y tierra), todos los impuestos y todas las rutas.
- **Tres partes:**
  1. **Observatorio** (`dora/observatory.py`, `run_observatory`): 500 ha y 500.000 USD, sin comentario del modelo. Una segunda corrida pide el comentario de unas 120 palabras que el observatorio controla con el verificador.
  2. **`compare_regions`**, con el mismo campo: modos "misma finca" (`same_farm`) y "misma plata" (`same_budget`), cada uno con la curva del día (`argentina_latest`) y con los precios por defecto de cada región.
  3. **El agente**, 5 veces: "¿Cómo viene la campaña en las cuatro regiones?". Sin más datos: se ve qué supone.
- **Comando** (desde la raíz, después de E4): `python eval/run_e2_e4.py e2 --env RUTA/.env`
- **Horario:** 31/10, de 18:46 a 18:49 (Buenos Aires).

## Resultado: la foto de las cuatro regiones

**`compare_regions`, misma finca: 500 ha propias, 500.000 USD, curva del día.**

| | Sudeste BA (Balcarce) | Zona núcleo (Pergamino) | Iowa (central) | Mato Grosso (Sorriso) |
|---|---|---|---|---|
| Plan óptimo | dar las 500 ha en alquiler | dar las 500 ha en alquiler | 250 ha maíz + 250 ha soja | dar las 500 ha en alquiler |
| Valor actual (USD) | 666.450 | 775.790 | 852.874 | 688.500 |
| Margen agrícola por ha sembrada, sin costo de la tierra (USD) | 199,52 | 507,48 | 788,53 | 428,23 |
| Retorno anual sobre el capital, solo agricultura | 16,2 % | 40,4 % | 61,8 % | 34,3 % |
| Retorno anual sobre capital y tierra | 2,7 % | 2,7 % | 2,2 % | 3,2 % |
| Alquiler de la región (USD/ha) | 350 | 570 | 677,1 | 380 |
| Precio de la tierra (USD/ha) | 11.000 | 17.900 | 28.539 | 10.530 |
| Flete hasta el puerto (USD/t; parte del ingreso) | 18; 6,2 % | 16,5; 5,7 % | 40; 17,4 % | 75; 25,1 % |
| Precio sombra del capital | 0 | 0 | 0,0141 | 0 |
| Precios | MAGyP + CBOT, 30/10 | MAGyP + CBOT, 30/10 | CBOT, 31/10 | CBOT, 31/10 |
| Datos provisorios | tierra, impuestos, rutas | impuestos, rutas | impuestos, rutas | región, tierra, impuestos, rutas |

- **Ranking por valor actual:** Iowa, núcleo, Mato Grosso, sudeste. Es el mismo con la curva del día y con los precios por defecto de cada región.
- **Con 500.000 USD el capital no aprieta en ninguna región argentina ni en Mato Grosso.** En Iowa, un dólar más vale 1,4 centavos sobre el depósito.
- **Con la tierra a precio de mercado, dar el campo en alquiler le gana a sembrar en tres de las cuatro regiones.** El retorno sobre capital y tierra (2,2 a 3,2 % anual) queda debajo del depósito (4 %).
- **Misma plata, 500.000 USD sin tierra** (precios por defecto de cada región; ver error 1):
  - solo en Iowa conviene producir: alquila 356,9 ha, siembra 178,4 de maíz y 178,4 de soja, y llega a un valor actual de 538.214 USD (10,5 % anual sobre capital y tierra);
  - en las otras tres, el óptimo es no producir y dejar la plata en el depósito (valor actual 500.000).

**Observatorio** (mismo campo, curva del día): Iowa 857.946 USD, núcleo 738.989, Mato Grosso 684.716, sudeste 587.678. El orden es el mismo, pero los números no coinciden con los de `compare_regions` (ver error 3).

## Resultado: el agente (5 repeticiones)

| | Valor |
|---|---|
| Respuestas verificadas | 5 de 5 |
| Con números sin respaldo en el primer borrador (corregidos antes de mostrarse) | 2 de 5 (una con 4 números, otra con 1) |
| Mismo ranking y mismos valores actuales | 5 de 5 |
| Herramienta usada | `compare_regions`, misma finca, escenario vacío: 5 de 5 |
| Usó la curva del día | 0 de 5 |
| Menciona datos provisorios | 5 de 5 |
| ... cuáles nombra | impuestos 5, fletes o rutas 5, valor de la tierra 1 |
| ... nombra que los datos de Mato Grosso son provisorios | 0 de 5 |
| Tiempo por respuesta (mediana) | 24,5 s |

- **Como no se le dio un campo, el agente usó los supuestos del modelo:** 500 ha, 50.000 USD propios y 100.000 de crédito, con los precios del informe de junio. Lo dijo en las 5 respuestas ("Tuyos: ninguno"), y en las 5 ofreció recalcular con los datos del productor.
- **Su foto:** Iowa 379.208 USD (758 por ha), núcleo 325.790, Mato Grosso 238.500, sudeste 216.450. Es otra foto que la de la tabla: tiene 10 veces menos capital y precios de junio.
- **Las 5 dicen que impuestos y fletes son provisorios.** Ninguna dice que los costos y rindes de Mato Grosso lo son, aunque la herramienta lo marca (`placeholder_flags.region_data`).
- **Retornos que confunden:** 4 de las 5 respuestas dan "695,2 % sobre capital en la temporada" para Iowa. El número es correcto, porque sale del motor: es la ganancia sobre 50.000 USD propios, con la renta de 232 ha dadas en alquiler. Pero un productor lo lee como "gano siete veces la plata". Es lo mismo que Guillermo marcó en q33 de E1: dar primero la decisión y la diferencia en USD.

## Errores encontrados (para arreglar; no se tocaron)
1. **"Misma plata" con la curva argentina les pone precios argentinos a Iowa y Mato Grosso.** En `dora/tools.py` (`compare_regions`), el modo `same_farm` cambia `argentina_latest` por `cbot_latest` fuera de Argentina, pero el modo `same_budget` no. Resultado con la curva del día: Iowa y Mato Grosso figuran con "MAGyP official spot prices ..., as of 2026-10-30", e Iowa pasa de producir (538.214 USD) a no producir (500.000).
2. **La marca de dato provisorio de la región no coincide entre herramientas.** `compare_regions` toma `placeholder` del diccionario `REGIONS`, que no lo tiene para el núcleo, y marca `region_data: false`. Pero `magyp_nucleo_2026-06.json` dice `placeholder: true` (por el flete dentro de los gastos de comercialización), y el observatorio, que lee el archivo, sí marca el núcleo como provisorio.
3. **El observatorio y `compare_regions` dan dos fotos distintas del mismo campo:**
   - El observatorio no cobra el alquiler de la tierra: el núcleo siembra maíz y soja (738.989 USD), mientras `compare_regions` da la tierra en alquiler (775.790).
   - El flete de Iowa es 12 USD/t en uno (solo el camión al río) y 40 en el otro (la ruta entera).
   - El observatorio anualiza con 15 meses (`FORTNIGHTS / 24`); el resto del modelo usa una temporada de 14,5 meses.

   No es un error de cuentas, pero la "foto regional" depende de qué herramienta se mire.
4. **El comentario del observatorio desde la línea de comandos llama a un modelo llamado "default".** Por lectura del código, no corrido: en `python -m dora.observatory` con `DORA_API_KEY` en el entorno, `_generate_commentary` recibe `model="default"`, la llamada falla y el error se descarta, así que el comentario queda vacío. Con el modelo bien puesto (corrida de este experimento), el comentario sale en inglés, con números sin unidad ("return on capital at 59.98") y sin mencionar los datos provisorios. Pasa el verificador igual, porque el verificador controla números, no unidades ni advertencias.

## Costo
- **Tokens del agente** (5 respuestas):
  - entrada: 526.409, de los cuales 334.834 en caché;
  - salida: 31.630;
  - 18 pedidos al modelo.
- **USD**, con los precios de `eval/pricing.json`: **0,42 USD**, 0,085 por respuesta. Es más del doble que en E4 (0,03), porque `compare_regions` devuelve un resultado largo: cuatro regiones, cada una con su plan.
- **El comentario del observatorio** (1 pedido) no se midió: el observatorio no devuelve el uso. Por tamaño, debería costar menos que una respuesta del agente.
- El observatorio y `compare_regions` solos no usan el modelo: tardan menos de un segundo.

Salida cruda: [`eval/results/e2_muse-spark-1_3_20261031_214628.json`](../../eval/results/e2_muse-spark-1_3_20261031_214628.json). Pesa 1,2 MB porque guarda el resultado completo de cada herramienta.

## Qué aprendimos
- **La foto regional depende de la pregunta, no solo de los datos.** Con la tierra a precio de mercado, en tres de cuatro regiones conviene dar el campo en alquiler. Sin contar la tierra, las cuatro siembran y el núcleo rinde 40 % anual. Las dos cosas son ciertas. DORA tiene que decir cuál de las dos está contando, y lo hace a medias.
- **El agente es estable y honesto, pero cuenta poco.** Las 5 respuestas dan el mismo ranking, los mismos números y dicen que hay datos provisorios. Pero nombran los provisorios genéricos (impuestos y fletes), no el más importante para esta comparación: los costos y rindes de Mato Grosso.
- **Sin datos del productor, el agente responde con los supuestos del modelo, y lo dice.** Es mejor que inventar un campo o negarse. Pero la "foto de la campaña" sale con 50.000 USD de capital y precios de junio, no con los del día.
- **Dos herramientas que miran lo mismo tienen que coincidir.** El observatorio y `compare_regions` nacieron en momentos distintos, y difieren en el alquiler, el flete y la duración de la temporada. Para la entrega conviene mostrar una sola, `compare_regions`, que es la que ve el agente.
- **El error de "misma plata" solo apareció al cruzar los modos con la curva del día.** Probar cada opción por separado no alcanza: hay que combinarlas.
