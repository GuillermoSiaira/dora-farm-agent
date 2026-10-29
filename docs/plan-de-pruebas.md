# Plan de pruebas de DORA (29/10/2026)

Qué queremos poder decir en la entrega, y con qué experimento se prueba cada cosa. Todo sale de corridas guardadas en `eval/results/`, con fecha, modelo y commit. Ningún número de la entrega se escribe a mano.

Modelo congelado: tag `model-frozen-2026-10-29` (commit `424dff0`). Si un experimento muestra un error del motor, se arregla y se vuelve a correr todo lo que dependa de él.

## E1. Un LLM solo contra DORA: certeza para decidir (el experimento central)

**Lo que queremos mostrar:** ante la misma pregunta de un productor, un modelo de lenguaje solo da números que cambian de una vez a otra, planes que no se pueden cumplir y planes peores. DORA da el mismo número cada vez, siempre factible y óptimo, y cada número está respaldado.

**Condiciones** (mismo modelo, Muse Spark 1.3, mismas preguntas):
- **A. LLM solo:** recibe la pregunta y **los mismos datos** que usa el motor (rindes, costos por hectárea y su calendario, precios, tasas, capital, crédito, silo, rotación), en texto, sin herramientas. Tiene que proponer un plan (hectáreas por cultivo, cuándo vender) y dar los números que se le piden.
- **B. LLM con herramientas, sin verificador.**
- **C. DORA completo:** herramientas y verificador.

Darle los datos a A es lo justo: no medimos si el modelo sabe precios de memoria, sino si puede razonar el problema de optimización.

**Preguntas:** las 39 de la evaluación (`eval/questions.jsonl` y `eval/questions_spec20.jsonl`), más 6 preguntas de decisión nuevas, del tipo "¿cuánto siembro de cada cultivo?", "¿vendo en cosecha o guardo?", "¿tomo el crédito?", "¿alquilo o doy en alquiler?".

**Repeticiones:** 5 por pregunta y condición, para medir la dispersión.

**Métricas:**
1. **Respuesta correcta:** el número coincide con el del motor (`eval/answers.jsonl`), con la tolerancia del verificador.
2. **Dispersión:** el desvío entre las 5 repeticiones del mismo número. Es la medida directa de la certeza.
3. **Factibilidad del plan de A:** el plan propuesto se carga en el motor con las hectáreas fijas y se controla si respeta capital, crédito, tierra, silo y rotación.
4. **Brecha de optimalidad:** el valor presente del plan de A, evaluado por el motor, contra el óptimo. "El plan del LLM solo deja X USD sobre la mesa".
5. **Números sin respaldo** (lo que ya mide el verificador).

**Herramienta nueva:** un modo `--baseline` en `eval/run_eval.py` que arma el prompt con los datos y le pide al modelo un JSON con el plan y los números. Más una función que evalúa ese plan en el motor (hectáreas fijas como restricciones `min_area`/`max_area`).

**Costo estimado:** unos 28.000 tokens de entrada por pregunta en B y C, menos en A. Con 45 preguntas × 3 condiciones × 5 repeticiones = 675 corridas, unos 25 USD de los 150 del crédito de Meta. Se corre primero con 5 preguntas para controlar el costo real.

**Resultado para la entrega:** una tabla (correctas, dispersión, factibles, brecha) y un gráfico de dispersión por condición.

## E2. Panorama regional: cómo viene la campaña en las principales zonas

**Lo que queremos mostrar:** DORA da, con datos del día, una foto comparable de las cuatro regiones: zona núcleo y sudeste de Buenos Aires, Iowa (cinturón maicero) y Mato Grosso. Margen por hectárea, alquiler, rendimiento sobre capital y tierra, impuestos, flete y escasez de capital.

**Cómo:** el observatorio diario (`observatory.py`) y `compare_regions` con un mismo campo (500 ha, 500.000 USD), los dos modos ("misma finca" y "misma plata"). Se le pregunta al agente "¿cómo viene la campaña en las cuatro regiones?" y se controla con el verificador.

**Cuidado con lo que se afirma:** son cuatro zonas, no todo el hemisferio. Los datos de Balcarce, Mato Grosso, impuestos y rutas son provisorios, y la respuesta tiene que decirlo. El experimento también muestra si el agente lo dice: contamos las respuestas que mencionan los provisorios.

**Resultado para la entrega:** la tabla de las cuatro regiones con la fecha de los datos, y una respuesta del agente verificada.

## E3. Multimodal de verdad: texto, voz, foto de factura y foto aérea

**Lo que queremos mostrar:** el productor no llena un formulario. Habla, manda una foto de la factura de insumos o una foto del lote, y el resultado es el mismo que si hubiera escrito los datos.

**Cómo:** 
- **Voz:** 6 notas de voz grabadas por nosotros con escenarios conocidos (Muse Voice Transcribe). Métrica: el escenario armado coincide con el esperado (la métrica de formulación que ya existe).
- **Factura:** 6 facturas sintéticas con números conocidos, armadas por nosotros (no de productores reales). Métrica: costos extraídos contra los verdaderos.
- **Foto aérea:** 3 imágenes con daño marcado (SPEC-18, SAM 3.1). Métrica: hectáreas dañadas contra las conocidas, y el plan que se vuelve a optimizar.
- **De punta a punta:** para cada caso, el resultado final por voz o foto es igual al que da el texto escrito.

## E4. Datos en tiempo real, y qué pasa cuando fallan

**Lo que queremos mostrar:** los precios salen solos de fuentes públicas (CBOT, MAGyP, dólar del BCRA) con su fecha. Si una fuente no responde, DORA usa la última copia guardada y lo dice. No inventa.

**Cómo:** una corrida con red y otra sin red (o con la fuente bloqueada). Se controla la fecha y la fuente de cada precio en la respuesta, y la marca de "dato guardado".

## E5. Robustez: lo que un LLM solo suele hacer mal

Preguntas armadas para tentar al modelo a inventar o a pasarse:
- Datos que faltan: tiene que preguntar o decir qué supuso.
- Fuera de alcance, como guardar hasta la cosecha siguiente: tiene que decir que el modelo termina en julio.
- Escenarios imposibles, como un mínimo de soja mayor que la tierra: tiene que decir qué restricción lo impide.
- Presión, como "decime cuánto gano sí o sí", o pedirle un número que ninguna herramienta da: el verificador lo tiene que frenar.

Métrica: respuestas que cumplen, con y sin verificador. Entra en la tabla de E1 como fila aparte.

## E6. Otros modelos de Meta (Baseten)

Las condiciones B y C de E1 con modelos abiertos de Meta en Baseten, uno grande y uno chico. Muestra que la arquitectura, y no un modelo en particular, es lo que da la certeza: con verificador, hasta un modelo chico no inventa números. Suma en "uso de las herramientas de Meta".

## E7. WhatsApp de punta a punta

Cuando esté la cuenta: texto, audio y foto desde un celular, con escenarios inventados y solo números nuestros. Se graba para el video.

## Auditoría independiente

Al final, con los resultados en la mano: un modelo distinto del que escribió y revisó el código (Fable) lee `docs/model.md`, `dora/engine.py`, las revisiones del mapa del código y los resultados de E1 a E5, y busca errores de matemática, de interpretación de los precios sombra y afirmaciones de la entrega que los datos no sostienen. Su informe va completo al repo, aunque diga cosas incómodas.

## Orden y fechas

| Día | Qué |
|---|---|
| Jue 29 | Modo `--baseline` y evaluación de planes en el motor (E1); preguntas nuevas de decisión y de robustez (E1, E5); prueba piloto con 5 preguntas |
| Vie 30 | E1 completo con Muse Spark; E4 |
| Sáb 31 | E2; E3 (grabar audios, armar facturas y fotos); Baseten (E6) |
| Dom 1 | Producto en vivo; WhatsApp (E7) si está la cuenta |
| Lun 2 | Auditoría; corregir lo que salga |
| Mar 3 | Tres corridas finales de E1 (condición C); README con las tablas; video |
| Mié 4 | Entrega antes de las 23:00 |
