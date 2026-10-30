# Registro de experimentos

Cada corrida que se usa para afirmar algo deja acá su ficha y su salida cruda. Ningún número de la entrega se escribe a mano: sale de un archivo de esta carpeta o de `eval/results/`.

## Qué tiene cada ficha
- **Fecha y commit** del código con que se corrió.
- **Modelo y dónde corre** (proveedor, GPU, versión del servidor).
- **Qué se preguntó** y el comando exacto.
- **Resultado:** tiempos, herramientas llamadas, tokens, si quedó verificado, si acertó.
- **Costo,** con el precio de lista y su fuente.
- **Qué falló y cómo se arregló,** también cuando el error fue nuestro.
- **Qué significa,** y qué no se puede concluir de una sola corrida.
- **Salida cruda** en `raw/`, sin claves.

## Fichas

| Fecha | Experimento | Modelo · entorno | Resultado en una línea |
|---|---|---|---|
| 30/10/2026 | [Primera prueba de Llama en Modal](2026-10-30-modal-llama-8b-q08.md) | Llama 3.1 8B Instruct · Modal, L40S, vLLM 0.9.2 | Responde, pero no llama herramientas e inventa datos; el verificador lo frena |
| 30/10/2026 | [Parte fija del prompt](2026-10-30-prompt-overhead.md) | Muse Spark 1.3 · API de Meta | 10.469 tokens por pedido, antes de la pregunta |
| 30/10/2026 | [Dos arreglos del chasis para Llama](2026-10-30-modal-llama-8b-arreglos.md) | Llama 3.1 8B Instruct · Modal, plantilla de vLLM y herramienta obligatoria | Ninguno alcanza: el problema es el modelo, no cómo se sirve |
