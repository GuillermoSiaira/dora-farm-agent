# Handoff: SPEC-23 — Demo que se explica sola y DORA como guía

## 1. Resumen de Cambios

Se implementaron todos los requisitos de `docs/specs/SPEC-23-demo-guide.md` y las correcciones de su primera y segunda revisión en la rama `spec-23-demo-guide`, creada a partir de `main` (congelada en el tag `model-frozen-2026-10-29`). El motor de cálculo (`dora/engine.py`) **no fue modificado** y los números de las herramientas se mantienen estrictamente idénticos a `main` a $10^{-9}$ (verificado en el Test 6 con el fixture `tests/data/spec23_main_tool_numbers.json`).

### Archivos Modificados y Creados

1. **`app.py`**:
   - **Carga inicial no vacía (`app.load`):** Al abrir la aplicación o recargar la página, `on_app_load` ejecuta el escenario por defecto (Balcarce, 500 ha, $50.000 de capital propio, $100.000 de crédito) con la misma función y lógica que el botón "Calcular Plan Óptimo", poblando inmediatamente el plan, las tarjetas y los 4 gráficos de la pestaña Escenario.
   - **Gráfico A a todo el ancho y perfectamente legible:**
     - Se ubicó el Gráfico A ("¿Cuánto vale un dólar en cada quincena?", `chart_rates_output`) inmediatamente debajo de la fila de parámetros y plan, ocupando todo el ancho de la pantalla ($1.216\text{ px}$ útiles a $1366\times 768$).
     - Altura ampliada a $320\text{ px}$ (área neta de trazado superior a $215\text{ px}$, resolviendo la compresión a $60\text{ px}$ de la versión anterior).
     - **Título y subtítulo completos:** Título claro en la esquina superior izquierda con subtítulo explicativo sin truncamiento.
     - **Leyenda horizontal superior:** Situada en la parte superior derecha (`y=1.02`), fuera del área del gráfico, garantizando que nunca se superponga con las curvas de escasez y mercado.
     - **Etiquetas de quincenas legibles y sin superposición:** Eje x configurado con orientación horizontal (`tickangle: 0`) y marcas espaciadas cada dos quincenas (una por mes calendárico: `1ª may`, `1ª jun`, ..., `1ª may (+1)` en español; `early May`, `early Jun`, ..., `early May (+1)` en inglés). Al pasar el cursor, el tooltip despliega el nombre completo y los valores exactos para cada una de las 30 quincenas.
   - **Cartel de verificación del Chat en español:**
     - En `STRINGS["es"]["chat_badge_verified"]`, se corrigió la frase a: `✅ **verificado: cada número sale del motor**` (reemplazando `"every number comes from the engine"`).
   - **Pestaña Regiones (Observatorio) 100% bilingüe y con voseo:**
     - Texto del mapa en castellano con voseo: `"Mapa del Observatorio Regional: hacé clic en los marcadores para ver el retorno sobre el capital y flete de cada región."` (en inglés: `"Regional Observatory Map: click on markers to view each region's return on capital and freight."`).
     - Leyenda del mapa Leaflet: en inglés despliega `"Return on Capital (%)"` y `"Freight Routes"` (con etiquetas `Truck`, `Rail`, `Barge`, `Ocean`); en castellano despliega `"Retorno sobre Capital (%)"` y `"Rutas de Flete"` (con etiquetas `Camión`, `Tren`, `Barcaza`, `Barco`).
     - Línea de referencia del 4% anual en el gráfico de tasas internas: anotada limpiamente como `"Tasa de mercado (4.0%)"` en español y `"Market rate (4.0%)"` en inglés.
     - Títulos y encabezados de la tabla del observatorio y gráficos segregados por idioma.
   - **Layout general y panel "¿Cómo empiezo?":**
     - Encabezado unificado en una sola fila compacta con selector de idioma en la esquina superior derecha.
     - Acordeón superior colapsable "¿Cómo empiezo?" con 3 pasos en 1 línea y fila de 4 botones ("Capital restringido", "Insumos a 90 días", "Contrato de maíz", y "Preguntale a DORA").
     - Fila superior en 2 columnas (50% / 50%):
       - **Columna 1:** Parámetros básicos en cuadrícula 2×2 (Región, Superficie, Capital propio, Línea de crédito), seguidos inmediatamente por el botón `⚡ Calcular Plan Óptimo` y el acordeón colapsado de `⚙️ Opciones avanzadas`.
       - **Columna 2:** Plan Propuesto, Tarjeta de Decisiones de Tierra y Tarjeta de Recursos.
     - Debajo de ambas columnas: Gráfico A a todo el ancho, seguido por Gráficos B y C en 2 columnas, Gráfico de Ventas mensual, Guardar corrida, Restricciones y Cuña fiscal.
   - **Corrección de Bloqueante en Chat:** `last_scenario_state` almacena `scenario_payload` saneado (diccionario JSON puro devuelto por `run_scenario`), evitando errores de serialización `DataFrame is not JSON serializable`.
   - **Aviso de Alícuotas de Retenciones:** Verificación con clave `"export_duties"` para desplegar `(alícuotas a verificar (placeholder))` en la fila de retenciones de la cuña fiscal.
   - **Cambio de Idioma:** Redibujado y recomputación dinámica de plan, tarjetas, observatorio, gráficos vacíos y etiquetas de chat.

2. **`dora/tools.py` y `dora/schemas.py`**:
   - `land_comparison`: Formato decimal con coma argentina (`_fmt_es`) y omisión automática de cláusulas con costo nulo cuando alquiler o tierra son 0.
   - `tax_wedge`: Parámetro opcional `lang: str | None = None` para traducir nombres de impuestos y disclaimer.

3. **`dora/agent.py`**:
   - `Agent.ask` recibe `screen_scenario` sin resultados precalculados, registrándolo en el historial y en `user_texts` para el verificador.

4. **`dora/modeling_guide.md`**:
   - Sección `## 5. Using the DORA screen` detallando guía de uso, interpretación de gráficos y precios sombra.

5. **`tests/test_demo_guide.py`**:
   - Suite ampliada a 15 tests unitarios y de integración para cubrir exhaustivamente los criterios de la spec y las dos rondas de revisión.

---

## 2. Descripción de la Pantalla: Antes y Después

| Elemento | Antes (Commit `5f4a9e5`) | Primera Revisión (Commit `f70000b`) | Segunda Revisión (Actual) |
|---|---|---|---|
| **Gráfico A (Tasas internas quincenales)** | Ocupaba el fondo del formulario, requiriendo amplio scroll. | Confinado en una 3ra columna estrecha (altura 260 px, área neta ~60 px). Curvas apretadas, leyenda tapando el dibujo y etiquetas pisadas. | **Todo el ancho (1.216 px útiles, altura 320 px).** Área de dibujo amplia (215 px netos). Leyenda horizontal superior (`y=1.02`) que no tapa las curvas. 15 marcas horizontales cada 2 quincenas (`1ª may`, `1ª jun`...) perfectamente legibles. |
| **Visibilidad 1366×768** | El botón Calcular y el gráfico quedaban desplazados verticalmente más allá de 1000 px / 1200 px. | Botón Calcular y Gráfico A entraban en 673 px de alto, a costa de encoger el gráfico hasta hacerlo ilegible. | **Medición real y diseño transparente:** El botón `⚡ Calcular Plan Óptimo` queda 100% visible sin scroll ($y=607\text{ px}$ con panel abierto, $y=495\text{ px}$ con panel cerrado). El Gráfico A inicia en $y=1000\text{ px}$ (abierto) / $y=888\text{ px}$ (cerrado) debajo del plan, priorizando legibilidad total con un leve scroll. |
| **Cartel del Chat (Español)** | Decía `"✅ verificado: every number comes from the engine"`. | Decía `"✅ verificado: every number comes from the engine"`. | Dice **`"✅ verificado: cada número sale del motor"`**. |
| **Texto de Mapa del Observatorio** | Decía `"haga clic en los marcadores..."`. | Decía `"haga clic en los marcadores..."`. | En castellano usa voseo: **`"hacé clic en los marcadores..."`**. En inglés: **`"click on markers..."`**. |
| **Leyenda del Mapa Leaflet** | Hardcodeada en español `"Retorno sobre Capital (%)"`. | Hardcodeada en español. | **Bilingüe:** `"Return on Capital (%)"` / `"Freight Routes"` en inglés; `"Retorno sobre Capital (%)"` / `"Rutas de Flete"` en castellano. |
| **Línea 4% Gráfico Observatorio** | Decía `"Tasa de mercado / Market rate (4.0%)"`. | Decía `"Tasa de mercado / Market rate (4.0%)"`. | **Segregado por idioma:** `"Tasa de mercado (4.0%)"` en español; `"Market rate (4.0%)"` en inglés. |

---

## 3. Comprobación en Navegador y Mediciones de Geometría

### Metodología de Medición
Se ejecutó Google Chrome en modo headless con conexión al protocolo de depuración remota (CDP):
- **Parámetros del proceso:** `chrome.exe --headless=new --window-size=1366,768 --remote-debugging-port=9223`
- **Viewport interno renderizado:** $1350 \times 673\text{ px}$ (descontando bordes y barras de interfaz).
- **Inspección del DOM:** Mediante llamada `Runtime.evaluate` en CDP evaluando `getBoundingClientRect()` sobre `#chart_rates_full_width`, botones y contenedores de gráficos Plotly SVG.

### Resultados de Medición (`getBoundingClientRect`)

1. **Botón `⚡ Calcular Plan Óptimo` (`run_btn`):**
   - **Con panel desplegado:** $y_{\text{top}} = 607\text{ px}$, $y_{\text{bottom}} = 639\text{ px}$ (altura: $32\text{ px}$).
   - **Con panel cerrado:** $y_{\text{top}} = 495\text{ px}$, $y_{\text{bottom}} = 527\text{ px}$.
   - **Evaluación:** En ambos casos queda **completamente visible dentro de la pantalla inicial ($< 673\text{ px}$)** sin necesidad de scroll.

2. **Gráfico A (`#chart_rates_full_width`):**
   - **Ancho del elemento:** $1.216\text{ px}$ (ocupa el 100% del contenedor centrado).
   - **Altura total:** $320\text{ px}$ (con área de trazado neta de $215\text{ px}$).
   - **Posición vertical:**
     - Con panel abierto: $y_{\text{top}} = 1.000\text{ px}$, $y_{\text{bottom}} = 1.320\text{ px}$.
     - Con panel colapsado: $y_{\text{top}} = 888\text{ px}$, $y_{\text{bottom}} = 1.208\text{ px}$.
   - **Eje de Quincenas y Leyenda:**
     - Leyenda: $y=1.068\text{ px}$ (abierto) / $y=956\text{ px}$ (cerrado), orientada horizontalmente arriba a la derecha.
     - Eje x de quincenas: $y=1.268\text{ px}$ (abierto) / $y=1.156\text{ px}$ (cerrado).
   - **Diagnóstico y Transparencia:**
     Debido a la presencia combinada del formulario de parámetros (izquierda) y el resumen completo del plan propuesto con sus decisiones de tierra y diagnósticos (derecha), el Gráfico A no entra completo en los primeros $673\text{ px}$ si se le otorga el ancho completo y una altura legible ($\ge 300\text{ px}$). Tal como se solicitó expresamente en la revisión (*"Si no entra entero, decirlo y medirlo, no achicarlo hasta que deje de leerse"*), se priorizó la máxima legibilidad: con un leve scroll vertical de rueda, el gráfico se presenta con nitidez absoluta, sin recorte de títulos, sin solapamiento de leyendas y con sus 15 etiquetas horizontales perfectamente espaciadas.

### Capturas Generadas
Se generaron capturas reales completas a $1366 \times 768$ utilizando `Page.captureScreenshot` de CDP:
- `docs/screenshots/load_screen.png` ($113.7\text{ KB}$): Captura real de la carga inicial de la aplicación.
- `docs/screenshots/demo_load_1366x768.png` ($113.7\text{ KB}$): Captura de referencia a resolución de escritorio.

---

## 4. Investigación sobre la Voz de Meta (Sección 6)

Se consultó la documentación oficial de la API de Meta (`https://api.meta.ai/v1` y portal de desarrolladores `https://dev.meta.ai`):
- **Páginas consultadas:**
  - `https://dev.meta.ai/docs/overview` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/models` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/api-reference/voice` (fecha de consulta: 29 de octubre de 2026).
  - `https://dev.meta.ai/docs/speech-to-text` (fecha de consulta: 29 de octubre de 2026).
- **Hallazgo:**
  La API de Meta dispone únicamente de modelos y endpoints para reconocimiento de voz (ASR / Speech-to-Text), a través del modelo `muse-voice-transcribe-1.0` en `POST https://api.meta.ai/v1/asr/transcribe` y streaming en `wss://api.meta.ai/v1/asr/realtime`. No existe un endpoint para síntesis de voz (TTS / Text-to-Speech).
- **Resolución según SPEC-23 Sección 6:**
  Por directiva expresa de la especificación (*"If it does not exist: do nothing in this spec. Do not use the browser's speech or another provider presented as Meta"*), **no se implementó botón de síntesis de voz**.

---

## 5. Resultado de los Tests

Toda la suite de pruebas se ejecuta de forma 100% offline (sin llamadas de red).

### Suite Específica SPEC-23 (`tests/test_demo_guide.py`)
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
- `test_13_chart_rates_readability_and_ticks`: **PASSED** (Gráfico A con altura $\ge 300\text{ px}$, marcas horizontales espaciadas cada 2 quincenas y leyenda superior fuera del dibujo).
- `test_14_chat_badge_verified_in_spanish`: **PASSED** (cartel de chat en español indica `verificado: cada número sale del motor`).
- `test_15_observatory_bilingual_map_and_chart`: **PASSED** (mapa del observatorio con voseo en español, inglés en inglés y anotación de tasa de mercado segregada por idioma).

### Suite Completa del Repositorio (`pytest`)
- **Total:** 234 passed, 1 skipped en 35,44 s.
- **Resultado:** 100% verde (219 tests existentes de main + 15 tests de SPEC-23). Ningún test preexistente fue modificado.
