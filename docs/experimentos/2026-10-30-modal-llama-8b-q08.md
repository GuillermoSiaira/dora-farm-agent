# Primera prueba de Llama en Modal (30/10/2026)

**Pregunta:** ¿un modelo abierto de Meta, chico, servido por nosotros en una GPU alquilada, puede hacer el trabajo del agente de DORA (formular el escenario y llamar las herramientas)?

## Montaje
- **Modelo:** `meta-llama/Llama-3.1-8B-Instruct` (Hugging Face, licencia Llama 3.1 aceptada el 29/10).
- **Dónde:** Modal, app `dora-llama`, GPU Nvidia L40S de 48 GB, vLLM 0.9.2 con `transformers` 4.53.2, contexto de 32.768 tokens, llamadas a herramientas con `--enable-auto-tool-choice --tool-call-parser llama3_json`. Se apaga a los 5 minutos sin uso. Código: [`infra/modal/serve_llama.py`](../../infra/modal/serve_llama.py).
- **Agente:** el de DORA sin cambios (mismo prompt, guía de modelado y herramientas que con Muse Spark), con verificador. El código del agente era el de la rama `spec-24-economics`, que solo agrega contadores (mergeada en `main` como `f2650f6`).
- **Prueba:** [`infra/modal/probe.py`](../../infra/modal/probe.py), pregunta `q08` dos veces seguidas.
- **Comando:** `.venv/Scripts/python.exe infra/modal/probe.py q08`

## La pregunta
`q08`: "Con 400 ha y capital de 100.000 USD, ¿cuántas hectáreas de trigo me conviene sembrar?". Respuesta del motor: **200 ha** (`eval/answers.jsonl`).

## Resultado

| | Primera (con arranque en frío) | Segunda (en caliente) |
|---|---|---|
| Tiempo | 277,7 s | 49,3 s |
| Herramientas llamadas | ninguna | ninguna |
| Pedidos al modelo | 3 | 3 |
| Tokens de entrada / salida | 43.128 / 1.642 | 43.935 / 1.849 |
| Verificada | no | no |
| "Correcta" según el evaluador | sí (falso acierto) | sí (falso acierto) |

Salida cruda: [`raw/2026-10-30_modal_llama31-8b_q08_probe.log`](raw/2026-10-30_modal_llama31-8b_q08_probe.log). En esta corrida la respuesta se guardó recortada a 1.200 caracteres; desde ahora `probe.py` guarda todo en un JSON en `raw/`.

## Qué pasó
1. **No llamó ninguna herramienta.** En lugar de devolver una llamada a `build_scenario`, escribió la llamada como texto. El servidor no la reconoce como llamada, así que el motor nunca se ejecutó.
2. **El JSON que escribió es inválido:** usa `False` (al estilo Python) en vez de `false`.
3. **Inventó los datos:** rindes de 2 a 5 t/ha y precios redondos (trigo 200, maíz 150, soja 300 USD/t). Ninguno sale de MAGyP ni del productor.
4. **El verificador lo frenó:** la respuesta quedó como no verificada. Es lo que tiene que pasar.
5. **Falso acierto del evaluador:** el evaluador busca el número esperado en el texto. Encontró "200" (el precio inventado del trigo) y lo contó como correcto. Con modelos que escriben números al azar, "correcta" sin "verificada" no sirve: la métrica que vale es correcta **y** verificada, la de la SPEC-24.

## Costo
GPU a 0,000542 USD por segundo (modal.com/pricing, leído el 30/10). Unos 10 minutos de GPU entre el arranque, las dos preguntas y los 5 minutos de espera antes de apagarse: alrededor de 0,33 USD. Es una estimación; el costo exacto está en la consola de Modal.

## Lo que falló antes, y cómo se arregló
1. **La consola de Windows cortó el despliegue** al escribir la barra de progreso. Se despliega con `PYTHONUTF8=1 PYTHONIOENCODING=utf-8`.
2. **Modal cortó la construcción de la imagen** una vez ("external shut-down"). Al reintentar, anduvo.
3. **El servidor no arrancaba:** vLLM 0.9.2 choca con `transformers` más nuevo (`'aimv2' is already used`). Se fijó `transformers==4.53.2`.
4. **Hugging Face rechazó la clave** (401, repositorio restringido): la clave guardada en Modal se había borrado. Con una clave nueva, anduvo.

## Qué se puede concluir, y qué no
- **Sí:** con el mismo agente y el mismo prompt, Llama 3.1 8B no maneja las herramientas de DORA en esta configuración, y el verificador impide que sus números inventados pasen como buenos.
- **No:** que un modelo abierto no pueda hacerlo. Es una sola pregunta, un solo modelo chico y una sola configuración del servidor. Hay cambios por probar (ver "Próximos pasos").

## Próximos pasos (cada uno es una prueba chica)
1. **Plantilla de herramientas de Llama 3.1:** vLLM recomienda una plantilla de chat propia para las llamadas en JSON (`tool_chat_template_llama3.1_json.jinja`). Sin ella el modelo puede escribir la llamada como texto.
2. **Obligar a llamar una herramienta** en el primer turno (`tool_choice="required"`): vLLM fuerza un JSON válido con decodificación guiada.
3. **Menos texto fijo para el modelo chico:** 10.469 tokens de prompt fijo por pedido (ver la [ficha del prompt](2026-10-30-prompt-overhead.md)) es mucho para un 8B.
4. **Un modelo más grande** (Llama 3.1 70B o Llama 4) en Baseten, con la misma prueba.
