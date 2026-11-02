# Guion del video (3 minutos, categoría Indie)

La voz va en inglés, porque el jurado es global. Debajo de cada bloque está la traducción, para ensayar. La app se muestra en castellano, porque el productor es argentino, salvo en la escena 5, donde se cambia a inglés para mostrar que anda en los dos idiomas.

Reglas para grabar:
- Todo en la app pública: https://guillermosiaira--dora-web.us-east.modal.run. Abrirla 2 minutos antes, para que el contenedor ya esté despierto.
- Ningún número se dice de memoria: se lee el que aparece en pantalla.
- Si una respuesta tarda, se corta en la edición (en E1 la mediana es de 18 s).
- Archivos para las escenas 3 y 4: `eval/e3/media/invoices/f1.png` y una nota de voz de `D:\projects\dora-audio\`.

---

## 1. El problema (0:00–0:20)
**Pantalla:** la pestaña Chat, vacía.

> An Argentine farmer has to decide, months ahead, how many hectares of each crop to sow, when to sell, and whether the money lasts until harvest. A chatbot will happily answer — but ask it the same question five times and you get five different numbers.

*Un productor argentino tiene que decidir con meses de anticipación cuántas hectáreas sembrar de cada cultivo, cuándo vender y si la plata le alcanza hasta la cosecha. Un chatbot contesta igual, pero si le hacés la misma pregunta cinco veces te da cinco números distintos.*

## 2. La idea (0:20–0:40)
**Pantalla:** el diagrama de "How it works" del README, o la pestaña Escenario con el gráfico de caja por quincena.

> DORA splits the job. Meta's Muse Spark talks with the farmer and builds the scenario. A linear-programming engine computes the plan, fortnight by fortnight. And a verifier checks that every number in the answer came from the engine. The model talks; the math decides.

*DORA divide el trabajo. Muse Spark, de Meta, habla con el productor y arma el escenario. Un motor de programación lineal calcula el plan quincena por quincena. Y un verificador revisa que cada número de la respuesta haya salido del motor. El modelo habla; la matemática decide.*

## 3. La entrevista (0:40–1:25): la escena central
**Pantalla:** Chat. Escribir:
`Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites.`
Contestar una pregunta por vez: `El campo es propio.` → `El banco me presta hasta 30000 USD.` → `Pago al contado.`

> Instead of guessing, DORA asks — one question at a time, starting with the one that would cost the most to get wrong. Each question says what it will assume if I don't know. When I answer, it recalculates and tells me what changed. It stops by itself when nothing left can move the plan by more than one percent.

*En vez de adivinar, DORA pregunta: una cosa por vez, empezando por la que más costaría errar. Cada pregunta dice qué va a suponer si no sé. Cuando contesto, recalcula y me dice qué cambió. Termina sola cuando lo que queda no mueve el plan más de un uno por ciento.*

**Al final, señalar en pantalla:** las hectáreas de cada cultivo, el valor actual y "lo que te limita" (la plata, con sus quincenas).

## 4. Foto y voz (1:25–1:55)
**Pantalla:** subir la foto de una factura y preguntar `¿Cómo cambia el plan con estos costos?`. Después, mandar la nota de voz.

> Farmers don't type spreadsheets. DORA reads an invoice photo line by line and loads the cost per hectare. In our tests it got it right six out of six times from the photo, and two out of six when the farmer typed the numbers. Voice notes give the same answer as writing.

*Los productores no escriben planillas. DORA lee la foto de una factura renglón por renglón y carga el costo por hectárea. En las pruebas acertó 6 de 6 con la foto y 2 de 6 cuando el productor tipeaba los números. Las notas de voz dan la misma respuesta que lo escrito.*

## 5. Regiones (1:55–2:15)
**Pantalla:** cambiar el idioma a English. Pestaña Regional Observatory: el mapa con Balcarce, Pergamino, Iowa y Mato Grosso, sus etiquetas de retorno y flete y la ★. Pasar el mouse por una ruta.

> The same engine compares regions with their own prices, freight and export routes: return on capital and freight to port, side by side.

*El mismo motor compara regiones con sus propios precios, fletes y rutas de exportación: retorno sobre el capital y flete al puerto, lado a lado.*

## 6. Los resultados (2:15–2:45)
**Pantalla:** la tabla "Muse Spark alone vs. DORA" del README.

> We measured it. Muse Spark alone got 38 percent of our questions right and proposed nine plans that cannot be carried out. With DORA, 97 percent — every answer verified, and not a single impossible plan. On the frozen final model: 121 out of 123, for five dollars for the whole run.

*Lo medimos. Muse Spark solo acertó el 38 % de nuestras preguntas y propuso nueve planes que no se pueden cumplir. Con DORA, el 97 %: todas las respuestas verificadas y ningún plan imposible. Con el modelo final congelado: 121 de 123, por cinco dólares toda la corrida.*

## 7. Lo que sigue (2:45–3:00)
**Pantalla:** la pestaña Chat con el plan de la escena 3.

> Next: DORA on WhatsApp, and an agent one step ahead — with the farmer's permission, it sees the new invoice the accountant loaded and updates the plan before the farmer asks. DORA, built during the Meta hackathon.

*Lo que sigue: DORA en WhatsApp, y un agente que se adelanta: con permiso del productor, ve la factura nueva que cargó el contador y actualiza el plan antes de que se lo pidan. DORA, hecho durante el hackatón de Meta.*

---

## Antes de grabar: ensayo
1. Correr la escena 3 una vez en la app pública y anotar si alguna pregunta sale distinta del guion (puede cambiar con los precios del día). Si cambia, se contesta lo que pregunte: lo que importa es que pregunte de a una.
2. Probar la factura `f1.png` y la nota de voz en la app pública.
3. Ver la escena 5 en una pantalla de 1366 × 768 o más grande: con menos, la leyenda tapa parte del mapa.
