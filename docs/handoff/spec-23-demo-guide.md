# Handoff: SPEC-23 — Demo que se explica sola y DORA como guía

## 1. Resumen de Cambios

Se implementaron todos los requisitos de `docs/specs/SPEC-23-demo-guide.md` en la rama `spec-23-demo-guide`, creada a partir de `main` (congelada en el tag `model-frozen-2026-10-29`). El motor de cálculo (`dora/engine.py`) **no fue modificado** y los números de las herramientas se mantienen estrictamente idénticos a `main` a $10^{-9}$ (verificado en el Test 6 con el fixture `tests/data/spec23_main_tool_numbers.json`).

### Archivos Modificados y Creados

1. **`app.py`**:
   - **Carga inicial no vacía (`app.load`):** Al abrir la aplicación o recargar la página, `on_app_load` ejecuta el escenario por defecto (Balcarce, 500 ha, $50.000 de capital propio, $100.000 de crédito) con la misma función y lógica que el botón "Calcular Plan Óptimo", poblando inmediatamente el plan, las tarjetas y los 4 gráficos de la pestaña Escenario.
   - **Observatorio Regional sin red:** En la carga inicial y selecciones de pestaña, se lee directamente el último snapshot `observatory/latest.json`. Si no existe, informa el estado sin llamadas de red.
   - **Gráficos vacíos con mensaje centrado:** Se añadió `make_empty_chart(msg)` que despliega un mensaje centrado en lugar del ícono vacío (`"Apretá **Calcular Plan Óptimo** para ver este gráfico"` / `"Press **Calculate Optimal Plan** to see this chart"`, y en la pestaña Comparar `"Apretá **Comparar** para ver este gráfico"` / `"Press **Compare** to see this chart"`).
   - **Manejo de errores amigable:** Si la optimización falla o se ingresan datos incompatibles, el error se muestra como texto explicativo en la página, no como gráficos rotos.
   - **Panel "¿Cómo empiezo?":** Nuevo acordeón colapsable en la parte superior de la pestaña Escenario (`open=True` por defecto) con 3 pasos en una línea cada uno:
     1. Elegí un ejemplo abajo o delimitá tu lote en el mapa.
     2. Apretá **Calcular Plan Óptimo** (o hacé clic en cualquiera de los ejemplos para cargarlo y calcularlo).
     3. Mirá qué falta y qué sobra: los gráficos te dicen cuánto te vale un dólar, una hectárea o una tonelada más de almacenaje.
   - **Botones de ejemplo que cargan y calculan:** Los 3 botones ("Capital restringido", "Insumos a 90 días", "Contrato de maíz") se trasladaron al panel "¿Cómo empiezo?", con botones grandes y una oración explicativa debajo de cada uno. Al presionarlos, **actualizan los controles del formulario y ejecutan la optimización inmediatamente**, actualizando todas las salidas.
   - **Botón "Preguntale a DORA":** Permite pasar directamente a la pestaña de Chat (cuando el chat está habilitado con `DORA_API_KEY`).
   - **Reorganización del formulario (Layout):**
     - Campos básicos agrupados en la columna izquierda: Región, Superficie, Cultivos disponibles, Capital propio, Línea de crédito, Tasa del crédito, Almacenaje propio, Fuente de precios.
     - Justo debajo de estos campos básicos: botón principal `⚡ Calcular Plan Óptimo`.
     - Campos avanzados encapsulados en el acordeón `⚙️ Opciones avanzadas / Advanced options` (cerrado por defecto): Delimitar campo en el mapa (Leaflet), Decisiones de tierra y alquiler, Plazos de insumos y recargo, Ganadería, y Restricciones específicas.
     - En pantallas estándar (1366×768), el resultado (Plan Propuesto, Diagnóstico, Tarjeta de Tierra y Recursos) y el Gráfico A ("¿Cuánto vale un dólar en cada quincena?") son visibles sin necesidad de scroll vertical.
   - **Correcciones de pantalla (Sección 4 de la spec):**
     - **Separación limpia de idiomas:** Con `lang="es"`, desapareció la frase en inglés `"an extra hectare is worth"` y todos los encabezados y etiquetas son 100% en español. Con `lang="en"`, no se muestran etiquetas en español.
     - **Tarjeta de tierra con hectáreas sin sembrar:** Cuando hay hectáreas sin sembrar y el precio sombra de la tierra es positivo, la tarjeta agrega explícitamente:  
       `"aunque quedan X ha sin sembrar: el valor viene de la rotación (con una hectárea más podés sembrar más del cultivo que está en su tope)"` (donde X proviene de la herramienta, e.g. `62,5 ha`). En inglés: `"even though X ha remain unsown: the value comes from the rotation (with an extra hectare you can sow more of the crop that is at its cap)"`.
     - **Retornos con su período:** Se muestra claramente `"en la campaña (14,5 meses)"` y a su lado la tasa anualizada y la tasa de depósito de referencia (`return_on_capital_annual_pct`, `deposit_rate_annual_pct`). Cuando la tierra no tiene precio asignado, se informa el retorno sobre el capital y se explica por qué no se calcula el retorno sobre capital y tierra.
     - **Derechos de exportación en la cuña fiscal:** La fila de retenciones indica `"(alícuotas a verificar (placeholder))"` junto al monto, y la nota al pie aclara que los precios de MAGyP son FAS (ya netos de derechos de exportación), por lo que la fila es informativa.
   - **Mensaje inicial de chat:** Inicializado con: `"Contame tu campaña: hectáreas, cultivos, plata y crédito. Podés escribir o mandar un audio."` (mostrado en la interfaz, sin enviar llamada a la API hasta que el usuario interactúe).

2. **`dora/agent.py`**:
   - `Agent.ask` acepta `screen_scenario: dict | None = None`. Cuando el usuario consulta desde el chat, el agente recibe los parámetros del último escenario calculado en la pantalla (sin resultados precalculados).
   - Registra `self.screen_scenario` y agrega el contexto en el historial de mensajes solo cuando cambia respecto a la consulta anterior.
   - Agrega los parámetros a `self.user_texts` para que el verificador reconozca los números del productor como verificados.

3. **`dora/modeling_guide.md`**:
   - Se añadió la sección `## 5. Using the DORA screen` detallando:
     - Guía para el usuario novato (los 3 pasos iniciales).
     - Propósito de cada una de las pestañas (Escenario, Observatorio Regional, Comparar, Chat).
     - Interpretación económica clara de cada gráfico (Gráfico A de tasas internas vs. banco al 4%, Gráfico B de precios sombra por dólar de capital y crédito, Gráfico C de caja y deuda, Gráfico de ventas).
     - Explicación de los precios sombra y de por qué la tierra tiene valor positivo aun cuando sobran hectáreas (cuello de botella de rotación agronómica).
     - Significado de los tres escenarios de ejemplo ("Capital restringido", "Insumos a 90 días", "Contrato de maíz").

4. **`dora/tools.py` y `dora/schemas.py`**:
   - `evaluate_season`: cuando `clean_lang == "es"`, genera `land_comparison` en español: `"una hectárea más te vale X; alquilar una cuesta Y; la plata inmovilizada en una cuesta Z por año"`.
   - `tax_wedge`: acepta parámetro opcional `lang: str | None = None` para traducir los nombres de los impuestos y el disclaimer al español o inglés según corresponda, manteniendo idénticos los cálculos numéricos.
   - `schemas.py`: actualizado el esquema de `tax_wedge` con `"lang": _LANG`.

5. **`tests/test_demo_guide.py`**:
   - Nueva suite con 8 tests de aceptación correspondientes a los 8 criterios de SPEC-23.

---

## 2. Descripción de la Pantalla: Antes y Después

| Elemento | Antes (Commit `5f4a9e5`) | Después (SPEC-23) |
|---|---|---|
| **Carga Inicial** | La página abría completamente vacía. Todos los gráficos mostraban cuadros grises oscuros vacíos. Había que buscar el botón al fondo del formulario para ver algo. | La página abre precalculada con el escenario Balcarce: plan visible, tarjetas de recursos y tierra con sus retornos, y los 4 gráficos trazados. El observatorio carga desde el snapshot local. |
| **Gráficos sin calcular** | Cajas grises oscuras con ícono de gráfico genérico. | Mensaje centrado en tipografía clara: `"Apretá **Calcular Plan Óptimo** para ver este gráfico"` / `"Apretá **Comparar** para ver este gráfico"`. |
| **Inicio para usuarios nuevos** | El formulario arrancaba con un mapa largo de Leaflet y campos complejos. Los ejemplos estaban escondidos al final. | Acordeón superior visible `"¿Cómo empiezo?"` con 3 pasos numerados, 3 botones de ejemplo destacados con descripción, y botón `"Preguntale a DORA"`. |
| **Acceso a Opciones Avanzadas** | Mapa, tenencia de tierra, ganadería, restricciones y plazos ocupaban toda la columna izquierda, empujando el botón Calcular fuera de vista. | Campos básicos (8 controles) inmediatamente seguidos del botón `⚡ Calcular Plan Óptimo`. Todo lo avanzado está colapsado en `⚙️ Opciones avanzadas`. |
| **Visibilidad 1366×768** | Requería scroll amplio para ver el plan y los gráficos. | En 1366×768, el Plan propuesto, la tarjeta de decisiones de tierra, la tarjeta de recursos y el Gráfico A (Tasa de oportunidad quincenal) quedan visibles sin scroll. |
| **Idiomas en pantalla** | Mezclaba español e inglés: `"an extra hectare is worth..."`, encabezados `"Impuesto / Tax"`, `"Monto / USD"`, etc. | 100% segregado por idioma: español rioplatense pulido o inglés limpio según el selector. |
| **Tarjeta de Tierra y Rotación** | Decía que la tierra valía 37,73 USD/ha sin explicar por qué si sobraban 62,5 ha sin sembrar. | Explica: `"aunque quedan 62,5 ha sin sembrar: el valor viene de la rotación (con una hectárea más podés sembrar más del cultivo que está en su tope)"`. |
| **Período de los Retornos** | Decía solo `ROC: 84.9%`, prestando a confusión sobre si era anual o de la campaña. | Detalla: `"84,9% en la campaña (14,5 meses) (66,3% anual vs. tasa depósito 4,0%)"`. Si la tierra no tiene precio asignado, aclara por qué no se calcula ROC + tierra. |
| **Retenciones en Cuña Fiscal** | Mostraba retenciones sin advertencia sobre vigencia de alícuotas ni aclaración del precio FAS. | Advierte `"(alícuotas a verificar (placeholder))"` y nota al pie aclarando que los precios MAGyP ya son netos de retenciones (FAS). |

---

## 3. Investigación sobre la Voz de Meta (Sección 6)

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

## 4. Resultado de los Tests

Toda la suite de pruebas se ejecuta de forma 100% offline (sin llamadas de red).

### Tests de Aceptación SPEC-23 (`tests/test_demo_guide.py`)
- `test_1_app_load_fills_scenario_outputs`: **PASSED** (la aplicación en el evento de carga populates el plan y los gráficos con datos).
- `test_2_example_buttons_load_and_compute`: **PASSED** (los botones de ejemplo cargan parámetros y optimizan; maíz contrato tiene $\ge 150\text{ ha}$).
- `test_3_language_separation`: **PASSED** (sin frases en inglés en español; sin etiquetas en español en inglés).
- `test_4_land_card_contains_rotation_sentence_with_unsown_ha`: **PASSED** (oración de rotación con hectáreas de la herramienta presentes en la tarjeta).
- `test_5_returns_show_season_annual_and_deposit_rate`: **PASSED** (coincidencia de retornos con los campos de `evaluate_season`).
- `test_6_frozen_tool_numbers_match_main_to_1e9`: **PASSED** (números de `evaluate_season`, `shadow_prices` y `tax_wedge` idénticos a `main` a $10^{-9}$).
- `test_7_guide_system_prompt_and_screen_context`: **PASSED** (prompt del sistema incluye guía de pantalla y pasa el contexto de la pantalla al modelo).
- `test_8_voice_output_policy`: **PASSED** (verificación de ausencia de botones TTS ante la inexistencia de endpoint en la API de Meta).

### Suite Completa del Repositorio (`pytest`)
- **Total:** 227 passed, 1 skipped en 34,04 s.
- **Resultado:** 100% verde (219 tests existentes de main + 8 tests nuevos de SPEC-23). Ningún test preexistente fue modificado.
