# Llama 3.1 8B en Modal: dos arreglos del chasis (30/10/2026)

**Pregunta:** en la [primera prueba](2026-10-30-modal-llama-8b-q08.md) Llama 3.1 8B escribió la llamada a la herramienta como texto, con JSON inválido, e inventó los datos. ¿Se arregla cambiando solo cómo se sirve el modelo (el chasis), sin cambiar de modelo?

## Montaje
Igual que la primera prueba (Modal, L40S, vLLM 0.9.2, `transformers` 4.53.2, misma pregunta `q08`), con dos cambios:
1. **Plantilla de herramientas de Llama 3.1** de vLLM (`tool_chat_template_llama3.1_json.jinja`, de la versión 0.9.2), cargada con `--chat-template`. Código: [`infra/modal/serve_llama.py`](../../infra/modal/serve_llama.py).
2. **Herramienta obligatoria en el primer pedido** (`tool_choice="required"`), con la que vLLM fuerza un JSON válido. El agente no cambia: la prueba envuelve el cliente ([`infra/modal/probe.py`](../../infra/modal/probe.py), `--required-first`).

**Comandos:**
- `.venv/Scripts/python.exe infra/modal/probe.py q08 --attempts 2 --label template-auto`
- `.venv/Scripts/python.exe infra/modal/probe.py q08 --attempts 1 --required-first --label template-required`

## Resultado

| Variante | Tiempo | Herramientas | Tokens entrada / salida | Verificada |
|---|---|---|---|---|
| Plantilla, intento 1 (arranque en frío, modelo ya guardado) | 146,8 s | ninguna | 43.128 / 1.642 | no |
| Plantilla, intento 2 | 48,8 s | ninguna | 44.055 / 1.864 | no |
| Plantilla + herramienta obligatoria | error a los 91,2 s | ninguna | — | — |

Salida cruda completa: [`raw/2026-10-30_1035_modal_q08_template-auto.json`](raw/2026-10-30_1035_modal_q08_template-auto.json) y [`raw/2026-10-30_1036_modal_q08_template-required.json`](raw/2026-10-30_1036_modal_q08_template-required.json).

## Qué pasó
1. **La plantilla no cambió nada.** El primer intento usó exactamente los mismos tokens que en la primera prueba (43.128 / 1.642): la plantilla de vLLM y la que trae el modelo producen el mismo texto para el modelo.
2. **El modelo vuelve a escribir la llamada como texto**, con `False` al estilo Python, y **completa los ~40 parámetros del escenario con valores inventados**: crédito al 12 %, insumos a 90 días, silo de 1.000 t, región zona núcleo, precios y rindes redondos. La pregunta solo decía 400 ha y 100.000 USD. Un modelo grande llena solo lo que el productor dijo; este llena todo el formulario.
3. **Con herramienta obligatoria, el servidor devolvió error 400** (`json_invalid`): ni con la decodificación guiada de vLLM 0.9.2 salió un JSON que pasara la validación. El esquema del escenario es grande y anidado.
4. **El verificador frenó todas las respuestas,** como en la primera prueba.

## Costo
Unos 12 minutos de GPU L40S (arranque, cuatro pedidos y los 5 minutos de espera) a 0,000542 USD por segundo: alrededor de 0,39 USD. Es una estimación; el exacto está en la consola de Modal.

## Qué se puede concluir
- **Sí:** con este modelo de 8 mil millones de parámetros, cambiar el chasis (plantilla, decodificación guiada) no alcanza. El problema es el motor: no sigue un esquema de herramientas grande ni se limita a lo que dijo el productor.
- **No:** que no haya ningún modelo abierto que pueda. Faltan el motor más grande y menos texto fijo.

## Próximos pasos
1. **Un motor más grande:** Llama 3.1 70B (o Llama 4) en Baseten, misma pregunta.
2. **Menos para leer:** una herramienta mínima para el modelo chico (solo los campos que dijo el productor) en vez del esquema completo.
