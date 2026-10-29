# Handoff: SPEC-23 — Demo que se explica sola y DORA como guía

## 1. Resumen de Cambios

Se implementaron todos los requisitos de `docs/specs/SPEC-23-demo-guide.md` y las correcciones de su revisión en la rama `spec-23-demo-guide`, creada a partir de `main` (congelada en el tag `model-frozen-2026-10-29`). El motor de cálculo (`dora/engine.py`) **no fue modificado** y los números de las herramientas se mantienen estrictamente idénticos a `main` a $10^{-9}$ (verificado en el Test 6 con el fixture `tests/data/spec23_main_tool_numbers.json`).

### Archivos Modificados y Creados

1. **`app.py`**:
   - **Carga inicial no vacía (`app.load`):** Al abrir la aplicación o recargar la página, `on_app_load` ejecuta el escenario por defecto (Balcarce, 500 ha, $50.000 de capital propio, $100.000 de crédito) con la misma función y lógica que el botón "Calcular Plan Óptimo", poblando inmediatamente el plan, las tarjetas y los 4 gráficos de la pestaña Escenario.
   - **Observatorio Regional sin red:** En la carga inicial y selecciones de pestaña, se lee directamente el último snapshot `observatory/latest.json`. Si no existe, informa el estado sin llamadas de red. Soporta bilingüismo en títulos de banner y gráficos de dispersión/barras.
   - **Gráficos vacíos con mensaje centrado:** Se añadió `make_empty_chart(msg)` que despliega un mensaje centrado en lugar del ícono vacío (`"Apretá **Calcular Plan Óptimo** para ver este gráfico"` / `"Press **Calculate Optimal Plan** to see this chart"`, y en la pestaña Comparar `"Apretá **Comparar** para ver este gráfico"` / `"Press **Compare** to see this chart"`).
   - **Manejo de errores amigable:** Si la optimización falla o se ingresan datos incompatibles, el error se muestra como texto explicativo en la página, no como gráficos rotos.
   - **Panel "¿Cómo empiezo?" compacto:** Acordeón colapsable en la parte superior de la pestaña Escenario (`open=True` por defecto) con 3 pasos en una línea cada uno:
     1. Elegí un ejemplo abajo o delimitá tu lote en el mapa.
     2. Apretá **Calcular Plan Óptimo** (o hacé clic en cualquiera de los ejemplos para cargarlo y calcularlo).
     3. Mirá qué falta y qué sobra: los gráficos te dicen cuánto te vale un dólar, una hectárea o una tonelada más de almacenaje.
   - **Botones de ejemplo en fila de 4 columnas:** Los 3 botones ("Capital restringido", "Insumos a 90 días", "Contrato de maíz") junto al botón "Preguntale a DORA" se disponen en una fila compacta con descripción concisa debajo de cada uno. Al presionarlos, **actualizan los controles del formulario y ejecutan la optimización inmediatamente**, actualizando todas las salidas.
   - **Reorganización del formulario (Layout 1366×768 sin scroll):**
     - Encabezado unificado en una sola fila compacta con selector de idioma en la esquina superior derecha.
     - Fila superior en 3 columnas:
       - **Columna 1:** Parámetros básicos en cuadrícula 2×2 (Región, Superficie, Capital propio, Línea de crédito), seguidos inmediatamente por el botón principal `⚡ Calcular Plan Óptimo`. Los parámetros secundarios y avanzados (mapa Leaflet, tenencia de tierra, plazos, ganadería, restricciones) están dentro de `⚙️ Opciones avanzadas / Advanced options` (cerrado por defecto).
       - **Columna 2:** Plan Propuesto en markdown, Tarjeta de Decisiones de Tierra, y Tarjeta de Recursos y Retornos.
       - **Columna 3:** Gráfico A ("¿Cuánto vale un dólar en cada quincena?", altura compacta de 260px).
     - Tanto con el panel "¿Cómo empiezo?" abierto como cerrado, el botón `⚡ Calcular Plan Óptimo` y el Gráfico A quedan completamente dentro del viewport de 1366×768 (altura 768px, inner viewport 673px) sin necesidad de scroll vertical.
   - **Corrección de Bloqueante en Chat:** `on_run`, `on_example_*` y `on_app_load` guardaban `sc_params` (que contenía un `DataFrame` de restricciones) en `last_scenario_state`. Al consultar el chat, `json.dumps` en `dora/agent.py:128` fallaba con `TypeError: Object of type DataFrame is not JSON serializable`. Se corrigió para almacenar `res.get("scenario_payload", {})` (diccionario JSON puro devuelto por `run_scenario`), desacoplando el estado del agente de los componentes de UI.
   - **Aviso de Alícuotas de Retenciones:** En `tax_wedge`, la fila de derechos de exportación utiliza `"key": "export_duties"`. Se corrigió la condición en `app.py` para verificar `tx.get("key") == "export_duties" or tx.get("tax") == "export_duties"`, garantizando que aparezca `"(alícuotas a verificar (placeholder))"` en español y `"(rates to be verified (placeholder))"` en inglés.
   - **Cambio de Idioma Completo:** El handler `on_lang_change` recalcula el último escenario en el idioma seleccionado, actualiza todas las salidas de la pestaña Escenario, redibuja el banner, mapa, tabla y gráficos del Observatorio Regional, regenera los avisos y gráficos vacíos de Comparar, y actualiza las etiquetas y placeholders del chat (`"Tu mensaje"`, `"Fotos de facturas"`, texto de ayuda, botón Enviar).
   - **Rutas traducidas en pantalla:** Se traduce `"Direct freight"` a `"Flete directo"` cuando `lang == "es"`.
   - **Retorno sobre Capital y Tierra:** En `run_entry`, `"return_on_capital_and_land"` se asigna a `None` cuando la tierra no tiene precio asignado (`land_price_val <= 0`), evitando transferir erróneamente el retorno sobre el capital a dicho campo.

2. **`dora/tools.py` y `dora/schemas.py`**:
   - `land_comparison`:
     - En español, utiliza formato decimal con coma argentina (`_fmt_es`, ej. `"37,73 USD/ha"`).
     - Si el alquiler regional o el precio de la tierra es 0 o no está definido, se omiten limpiamente las cláusulas `"alquilar una cuesta 0,00 USD/ha"` y `"la plata inmovilizada en una cuesta 0,00 USD/ha por año"`.
   - `tax_wedge`: acepta parámetro opcional `lang: str | None = None` para traducir los nombres de los impuestos y el disclaimer al español o inglés según corresponda, manteniendo idénticos los cálculos numéricos.
   - `schemas.py`: actualizado el esquema de `tax_wedge` con `"lang": _LANG`.

3. **`dora/agent.py`**:
   - `Agent.ask` acepta `screen_scenario: dict | None = None`. Cuando el usuario consulta desde el chat, el agente recibe los parámetros del último escenario calculado en la pantalla (sin resultados precalculados).
   - Registra `self.screen_scenario` y agrega el contexto en el historial de mensajes solo cuando cambia respecto a la consulta anterior.
   - Agrega los parámetros a `self.user_texts` para que el verificador reconozca los números del productor como verificados.

4. **`dora/modeling_guide.md`**:
   - Se añadió la sección `## 5. Using the DORA screen` detallando guía de uso, pestañas, interpretación de gráficos y precios sombra.

5. **`tests/test_demo_guide.py`**:
   - Suite completa con 12 tests de regresión y aceptación:
     - Tests 1 a 8: Carga inicial, botones de ejemplo, separación de idioma, tarjeta de tierra con rotación, retornos por período, números congelados idénticos a main, guía en system prompt y política de voz.
     - Test 9: Ejecución de `on_run` con restricciones DataFrame y posterior llamada al chat con mock de OpenAI sin error de serialización JSON.
     - Test 10: Verificación del aviso de retenciones placeholder en español e inglés.
     - Test 11: Cambio dinámico de idioma recalcula y actualiza escenario, observatorio, comparar y etiquetas del chat.
     - Test 12: Coma argentina en comparación de tierra, omisión de cláusulas con costo 0, traducción de `"Flete directo"`, y valor `None` en retorno sobre capital y tierra sin precio de tierra.

---

## 2. Descripción de la Pantalla: Antes y Después

| Elemento | Antes (Commit `5f4a9e5`) | Después de la Revisión SPEC-23 |
|---|---|---|
| **Carga Inicial** | La página abría completamente vacía. Todos los gráficos mostraban cuadros grises oscuros vacíos. Había que buscar el botón al fondo del formulario para ver algo. | La página abre precalculada con el escenario Balcarce: plan visible, tarjetas de recursos y tierra con sus retornos, y los 4 gráficos trazados. El observatorio carga desde el snapshot local. |
| **Gráficos sin calcular** | Cajas grises oscuras con ícono de gráfico genérico. | Mensaje centrado en tipografía clara: `"Apretá **Calcular Plan Óptimo** para ver este gráfico"` / `"Apretá **Comparar** para ver este gráfico"`. |
| **Inicio para usuarios nuevos** | El formulario arrancaba con un mapa largo de Leaflet y campos complejos. Los ejemplos estaban escondidos al final. | Acordeón superior compacto `"¿Cómo empiezo?"` con 3 pasos numerados, 3 botones de ejemplo destacados en 4 columnas junto a `"Preguntale a DORA"`. |
| **Acceso a Opciones Avanzadas** | Mapa, tenencia de tierra, ganadería, restricciones y plazos ocupaban toda la columna izquierda, empujando el botón Calcular fuera de vista. | Campos básicos (cuadrícula 2×2) inmediatamente seguidos del botón `⚡ Calcular Plan Óptimo`. Todo lo avanzado está colapsado en `⚙️ Opciones avanzadas`. |
| **Visibilidad 1366×768 (Scroll)** | El botón Calcular y el Gráfico A quedaban desplazados verticalmente más allá de 1000px/1200px, exigiendo scroll para operar. | **Cero scroll:** En viewport 1366×768, con el panel abierto el Gráfico A inicia en $y=353\text{ px}$ y el botón Calcular en $y=629\text{ px}$ (termina en $669\text{ px} < 673\text{ px}$). Con el panel cerrado, arrancan en $y=246\text{ px}$ y $y=523\text{ px}$. Entran completos sin scroll vertical. |
| **Integración Chat tras Calcular** | Al presionar Calcular y luego consultar al chat, el servidor arrojaba `500 Internal Server Error` (`DataFrame is not JSON serializable`). | `last_scenario_state` recibe `scenario_payload` saneado. El chat procesa fluidamente el estado de la pantalla. |
| **Aviso de Retenciones** | Nunca aparecía el aviso de alícuotas placeholder debido al chequeo de clave `"tax"`. | Aparece explícitamente `"(alícuotas a verificar (placeholder))"` junto al monto de derechos de exportación. |
| **Cambio de Idioma** | Solo cambiaban los controles del formulario; plan, tarjetas, observatorio y chat quedaban congelados en el idioma previo. | Al alternar entre ES y EN, todo el contenido visual, cálculos, tablas, observatorio y etiquetas del chat se redibujan instantáneamente en el nuevo idioma. |
| **Comparación de Tierra** | Mostraba punto decimal en castellano (`37.73`) y frases confusas como `"alquilar una cuesta 0.0"`. | Formato con coma argentina (`37,73 USD/ha`) y omisión automática de cláusulas con costo nulo. |
| **Detalle de Flete en Rutas** | Decía `"Direct freight (18.0 USD/t)"` en la pantalla en español. | Muestra `"Flete directo (18.0 USD/t)"` en español. |
| **Retorno Capital + Tierra** | Asignaba el ROC financiero si no había precio de tierra. | Devuelve `None` y no confunde al usuario con retornos de tierra inexistentes. |

---

## 3. Comprobación en Navegador y Capturas Reales

### Metodología de Prueba
Para verificar el comportamiento visual y la geometría real en un entorno sin dependencias de red, se ejecutó Google Chrome en modo headless con emulación estricta de ventana de escritorio:
- **Resolución de ventana:** `--window-size=1366,768`
- **Viewport interno renderizado:** $1366 \times 673\text{ px}$ (descontando marco y barra de herramientas)
- **Protocolo:** Chrome DevTools Protocol (CDP) mediante conexión de depuración remota.
- **Sincronización:** Se utilizó `--virtual-time-budget=10000` y espera de montaje de componentes Svelte de Gradio para asegurar el renderizado completo de gráficos Plotly, Leaflet y fuentes tipográficas.

### Mediciones de Coordenadas (`getBoundingClientRect`)

Las mediciones en el DOM arrojaron las siguientes posiciones para los elementos críticos:

1. **Con el panel "¿Cómo empiezo?" desplegado (estado inicial):**
   - **Gráfico A (`chart_rates_output`):**
     - $y_{\text{top}} = 353\text{ px}$
     - $y_{\text{bottom}} = 613\text{ px}$ (altura: $260\text{ px}$)
   - **Botón `⚡ Calcular Plan Óptimo` (`run_btn`):**
     - $y_{\text{top}} = 629\text{ px}$
     - $y_{\text{bottom}} = 669\text{ px}$ (altura: $40\text{ px}$)
   - **Resultado:** Ambos elementos se sitúan holgadamente por encima del límite del viewport ($673\text{ px}$), siendo 100% interactivos y visibles sin necesidad de desplazar la barra de scroll.

2. **Con el panel colapsado:**
   - **Gráfico A:** $y_{\text{top}} = 246\text{ px}$, $y_{\text{bottom}} = 506\text{ px}$.
   - **Botón Calcular:** $y_{\text{top}} = 523\text{ px}$, $y_{\text{bottom}} = 563\text{ px}$.

### Capturas Generadas
Se reemplazaron los archivos de captura anteriores por capturas reales completas generadas por el motor de renderizado de Chrome:
- `docs/screenshots/load_screen.png` ($142.5\text{ KB}$): Captura a pantalla completa ($1366 \times 768$) mostrando la carga inicial completa con el plan, las tarjetas y los gráficos.
- `docs/screenshots/demo_load_1366x768.png` ($142.5\text{ KB}$): Captura idéntica de referencia geométrica.

---

## 4. Investigación sobre la Voz de Meta (Sección 6)

Se consultó la documentación oficial de la API de Meta (`https://api.meta.ai/v1` y portal de desarrolladores `https://dev.meta.ai`):
- **Páginas consultadas:**
  - `https://dev.meta.ai/docs/overview` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/models` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/api-reference/voice` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/speech-to-text` (fecha de consulta: 29 de octubre de 2026).
- **Hallazgo:**
  La API de Meta dispone únicamente de modelos y endpoints para reconocimiento de voz (ASR / Speech-to-Text), a través del modelo `muse-voice-transcribe-1.0` en `POST https://api.meta.ai/v1/asr/transcribe` y streaming en `wss://api.meta.ai/v1/asr/realtime`.
  La documentación oficial de Meta especifica textualmente:
  > *"The Meta Voice API currently provides Automated Speech Recognition (ASR). It is speech-to-text only; it does not synthesize speech or provide a text-to-speech / speech-to-speech conversation endpoint."*
- **Resolución según SPEC-23 Sección 6:**
  La especificación estipula:
  > *"If it exists: a '🔊 Escuchar' button under each chat answer that reads it aloud with that endpoint. Audio is generated only when the button is pressed.*  
  > *If it does not exist: do nothing in this spec. Do not use the browser's speech or another provider presented as Meta."*
  Por lo tanto, **no se implementó salida de voz ni botón TTS**, respetando estrictamente la directiva de no utilizar síntesis del navegador ni proveedores terceros haciéndolos pasar por Meta.

---

## 5. Resultado de los Tests

Toda la suite de pruebas se ejecuta de forma 100% offline (sin llamadas de red).

### Suite de Aceptación y Revisión SPEC-23 (`tests/test_demo_guide.py`)
- `test_1_app_load_fills_scenario_outputs`: **PASSED** (carga inicial puebla plan, tarjetas y gráficos).
- `test_2_example_buttons_load_and_compute`: **PASSED** (botones de ejemplo cargan y optimizan; contrato de maíz $\ge 150\text{ ha}$).
- `test_3_language_separation`: **PASSED** (segregación total de idiomas en textos generados).
- `test_4_land_card_contains_rotation_sentence_with_unsown_ha`: **PASSED** (oración de rotación con hectáreas de la herramienta presentes en la tarjeta).
- `test_5_returns_show_season_annual_and_deposit_rate`: **PASSED** (retornos sincronizados con `evaluate_season`).
- `test_6_frozen_tool_numbers_match_main_to_1e9`: **PASSED** (números de `evaluate_season`, `shadow_prices` y `tax_wedge` idénticos a `main` a $10^{-9}$).
- `test_7_guide_system_prompt_and_screen_context`: **PASSED** (prompt del sistema incluye guía de pantalla y pasa el contexto de la pantalla al modelo).
- `test_8_voice_output_policy`: **PASSED** (ausencia de botones TTS ante inexistencia de endpoint en la API de Meta).
- `test_9_chat_handles_scenario_state_from_calculate`: **PASSED** (el estado de la pantalla tras presionar Calcular pasa sin `TypeError` al chat).
- `test_10_export_duties_placeholder_notice`: **PASSED** (aparición del aviso de alícuotas placeholder en español e inglés).
- `test_11_language_switch_recomputes_and_updates_all_components`: **PASSED** (recalcula y actualiza escenario, observatorio, comparar y etiquetas de chat al cambiar de idioma).
- `test_12_minor_fixes`: **PASSED** (coma decimal argentina, omisión de costos nulos de tierra/alquiler, traducción de flete directo y `return_on_capital_and_land is None`).

### Suite Completa del Repositorio (`pytest`)
- **Total:** 231 passed, 1 skipped.
- **Resultado:** 100% verde (219 tests existentes de main + 12 tests de SPEC-23). Ningún test preexistente fue modificado.
