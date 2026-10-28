# Handoff: SPEC-20 — Opciones de almacenamiento, base mensual, merma, ventana y equilibrio

- **Rama:** `spec-20-storage` (creada desde `main` en commit `05902aa`; `main` intacta, sin merge).
- **Decisión aplicada:** las opciones regionales de almacenamiento (`dora/data/storage_<region>.json`) están **apagadas por defecto**. Si `storage_options` está vacío, el motor construye una única opción heredada idéntica al modelo previo (`own_silo`, capacidad `storage_capacity_t`, costo mensual `storage_cost_usd_t_month`, costo de entrada 0, mermas 0, sin límite de meses), preservando exactamente el plan, el VAN y los precios sombra de todos los escenarios existentes.

---

## 1. Qué se implementó

1. **Fase A — Motor LP con múltiples opciones de almacenamiento y merma (`dora/engine.py`):**
   - Variables por cultivo `c`, opción `m` y quincena `p >= h_c`: entrada en cosecha `in_{c,m}`, stock al cierre de cada quincena `s_{c,p,m}`, y extracción `o_{c,p,m}` (`p > h_c`).
   - Costo de entrada (`fill_cost_usd_t`) pagado en caja en `p = h_c` y costo de tenencia (`monthly_cost_usd_t / 2`) pagado por quincena sobre `s_{c,p,m}` (sin impuesto al cheque Ley 25.413, según SPEC-20 §1).
   - Ecuaciones de balance de grano con merma al ingreso (`1 - shrink_at_entry_m`) y merma quincenal (`(1 - shrink_monthly_m)**0.5`, equivalente a `1 - delta_m`).
   - Restricciones de capacidad `sum_c s_{c,p,m} <= capacity_m` agregadas **solo** para opciones con `capacity_t != null` (las opciones sin límite no agregan filas ni reportan precio sombra).
   - Cotas de vida útil (`s_{c,p,m} = 0` para `p > h_c + 2 * max_months_m`) y cierre de campaña (`s_{c,T-1,m} = 0`).
   - `Result.storage_shadow_price` mantiene el dual de `own_silo` (o ceros si no hay `own_silo` con capacidad finita); se agregó `Result.storage_by_option` y el chequeo post-solución de balance de masa por cultivo (`cosecha = ventas + forwards + merma`).
   - Verificado con Tests 1 y 2 contra `main` (`rel=1e-11`) antes de pasar a los datos regionales y reportes.

2. **Fase B — Datos regionales trazados a publicaciones primarias (`dora/data/` y `docs/sources/README.md`):**
   - Se descargaron con verificación SSL (`ssl.create_default_context()`), se hashearon (SHA-256 en `docs/sources/README.md`) y se leyeron 9 documentos primarios (ISU Ag Decision Maker A2-33, A2-40, A2-41, A2-42; FACMA agosto 2026; Olivanti/INTA 2012; Reglas y Usos del Comercio de Granos Art. 43; CONAB Tarifas PGPM mayo 2025 y Sobrearmazenagem agosto 2025).
   - Se crearon `dora/data/storage_southeast_buenos_aires.json`, `dora/data/storage_pampas_core.json`, `dora/data/storage_iowa.json` y `dora/data/storage_mato_grosso.json`.
   - Se actualizó `dora/data/basis_iowa.json` con `"basis_by_month"` (`2026-10` a `2027-06`) para maíz y soja leído de las tablas *State Average* de ISU Files A2-41 (p. 1) y A2-42 (p. 1).

3. **Base mensual, resolución de opciones, reportes, schemas y guía del agente:**
   - `dora/scenario.py`: `_interpolate_monthly`, `Scenario.basis_at(c, p)` (acepta escalar, diccionario `{"YYYY-MM": USD/t}` en `basis_usd_t[c]`, o `basis_by_month[c]` del archivo regional), `load_storage_data`, `Scenario.storage_options_with_origins()` y `Scenario.effective_storage_options()`.
   - `dora/tools.py`: validación completa de `storage_options` y `basis_usd_t` mensual en `_validate`; rastreo de orígenes campo por campo en `build_scenario`; bloque `storage` (`usd_per_extra_tonne`, `window_by_crop`, `breakeven_by_crop`, `by_option`) en `evaluate_season` y `shadow_prices`; uso de `sc.basis_at(c, p)` en `tax_wedge`.
   - `dora/schemas.py`: schemas JSON para `storage_options` y `basis_usd_t` (escalar o diccionario mensual).
   - `dora/modeling_guide.md` y `dora/agent.py`: mapeo de frases del productor (`own_silo`, `silo_bag`, `elevator`, reemplazo de costos regionales) y regla explícita en `SYSTEM_PROMPT` de no extrapolar más allá del último mes de la campaña (quincena 29).
   - `docs/model.md`: ecuaciones actualizadas con sus números de línea exactos y supuesto explícito de ventana de almacenamiento.

---

## 2. Archivo, función y líneas de cada ecuación

| Ecuación / cálculo | Archivo y función | Líneas |
|---|---|---|
| Interpolación lineal mensual (`curve_price` y `basis_at`, plana en extremos) | `dora/scenario.py` — `_interpolate_monthly`, `Scenario.curve_price`, `Scenario.basis_at` | `177–201`, `467–487` |
| Precio bruto, destino, tranquera y neto con `basis_at(c, p)` | `dora/scenario.py` — `price`, `destination_price`, `farm_gate_price`, `farm_gate_decomposition` | `489–523`, `537–618` |
| Resolución de opciones de almacenamiento (modo heredado vs fusión con `storage_<region>.json`) | `dora/scenario.py` — `storage_options_with_origins`, `effective_storage_options` | `677–792` |
| Índices de variables `in_{c,m}` (`put_in`), `s_{c,p,m}` (`stock_opt`), `o_{c,p,m}` (`take_out`) | `dora/engine.py` — `optimize` | `199–209` |
| Pagos de almacenamiento en ecuación de caja: `+fill_m * in_{c,m} * [p = h_c] + (monthly_m / 2) * s_{c,p,m}` | `dora/engine.py` — `optimize` | `282–289` |
| Balance en cosecha (`p = h_c`): `sum_r v_{c,h,r} + sum_k f_k*[c,h] + sum_m in_{c,m} - y_c * x_c = 0` | `dora/engine.py` — `optimize` | `348–358` |
| Stock inicial tras merma de entrada (`p = h_c`): `s_{c,h,m} - (1 - shrink_at_entry_m) * in_{c,m} = 0` | `dora/engine.py` — `optimize` | `361–368` |
| Evolución de stock (`p > h_c`): `s_{c,p,m} - (1 - shrink_monthly_m)**0.5 * s_{c,p-1,m} + o_{c,p,m} = 0` | `dora/engine.py` — `optimize` | `372–380` |
| Ventas y entregas post-cosecha (`p > h_c`): `sum_r v_{c,p,r} + sum_k f_k*[c,p] - sum_m o_{c,p,m} = 0` | `dora/engine.py` — `optimize` | `382–391` |
| Capacidad por opción y quincena (`capacity_t != null` únicamente): `sum_c s_{c,p,m} <= capacity_m` | `dora/engine.py` — `optimize` | `442–455` |
| Cierre de campaña (`s_{c,T-1,m} = 0`) y vida útil (`s_{c,p,m} = 0` para `p > h_c + 2 * max_months_m`) | `dora/engine.py` — `optimize` | `595–603` |
| Reporte por opción (`Result.storage_by_option`), verificación `harvest = sales + forwards + shrink` y dual heredado `Result.storage_shadow_price` | `dora/engine.py` — `optimize` | `767–840` |
| Ventana (`window_by_crop`) y precio neto de equilibrio al final de campaña (`breakeven_by_crop`) | `dora/tools.py` — `_storage_report` | `508–615` |

---

## 3. Resultado de los tests

Ejecución completa con `.\.venv\Scripts\python -m pytest`:

- **Total:** `199 passed, 1 skipped` (28.94 s).
- **Suite previa (`main`):** los `186 passed, 1 skipped` pasan íntegramente **sin modificar ningún archivo de test existente**.
- **Nuevos tests (`tests/test_storage.py`):** `13 passed` en 1.21 s con `urllib.request.urlopen` bloqueado por fixture `autouse=True` (cero llamadas de red):
  1. `test_1_legacy_matches_main_exactly`
  2. `test_2_single_option_equal_to_legacy_matches_no_option`
  3. `test_3_fill_cost_by_hand`
  4. `test_4_shrink_held_four_fortnights`
  5. `test_5_max_months_life_bound`
  6. `test_6_capacity_shadow_price_matches_finite_differences`
  7. `test_7_null_capacity_adds_no_row_and_reports_no_shadow_price`
  8. `test_8_choice_between_own_silo_and_silo_bag`
  9. `test_9_monthly_basis_equivalence_and_iowa_cbot_snapshot`
  10. `test_10_storage_window_by_crop`
  11. `test_11_reported_breakeven_matches_hand_and_governs_storage`
  12. `test_12_validation_errors_are_readable`
  13. `test_spec20_eval_questions_and_end_of_season_rule`

---

## 4. Datos leídos de publicaciones abiertas vs datos provisorios (`"placeholder": true`)

Todos los PDFs abiertos están registrados con URL y hash SHA-256 en `docs/sources/README.md` (los binarios quedan en `docs/sources/`, ignorados por git):

| Archivo de datos | Qué sale directo de una publicación abierta | Por qué lleva `"placeholder": true` |
|---|---|---|
| `dora/data/basis_iowa.json` | `basis_by_month` de maíz y soja (`2026-10` a `2027-06`) leído directamente de **ISU Ag Decision Maker File A2-41** (rev. dic. 2025, p. 1, tabla *State Average*, columna `Avg` vs futuro cercano sin entrega, convertido a `39.368 bu/t`) y **File A2-42** (rev. dic. 2025, p. 1, tabla *State Average*, columna `Avg`, convertido a `36.744 bu/t`). | Las tablas A2-41 y A2-42 reportan promedios históricos de 5 campañas (`2020/21–2024/25`) proyectados sobre los meses `2026/27`, no ofertas cash forward en vivo para 2026/27. |
| `storage_southeast_buenos_aires.json` y `storage_pampas_core.json` — `silo_bag` | `fill_cost_usd_t = 11.30` de **FACMA** (*Precios Orientativos: Embolsado y Extracción*, 31 ago. 2026, p. 1: embolsado `3.95` + extracción `3.95` + tolva `3.39 = 11.30 USD/t` a `1.503 ARS/USD`); `max_months = 6` y merma biológica nula para grano seco (`<= 14%`) de **Olivanti (2012) citando INTA Balcarce/Manfredi** (p. 2, tabla de riesgo por humedad y tiempo). | La tarifa de FACMA (p. 1) cubre el servicio de contratista y excluye la compra de la bolsa plástica; el cuadro de Olivanti/INTA (p. 2) no cuantifica merma mecánica de extracción. |
| `storage_southeast_buenos_aires.json` y `storage_pampas_core.json` — `elevator` | `shrink_at_entry = 0.0`, `shrink_monthly = 0.0` de **Cámaras Arbitrales de Cereales, *Reglas y Usos del Comercio de Granos*** (2016, Art. 43, p. 15: los gastos de conservación y mermas/riesgos de almacenaje quedan cubiertos dentro de la tarifa pactada). | No existe un tarifario público nacional único en USD/t/mes de acopios comerciales para 2026 (se pacta por cooperativa/acopio); se conserva `2.0 USD/t/mes` como tasa provisoria. |
| `storage_iowa.json` — `own_silo` (y referencia física provisoria de `own_silo` en AR y MT) | Costos variables en silo propio existente (costo fijo hundido = 0) leídos de **ISU File A2-33** (*Cost of Storing Grain*, rev. mayo 2023, pp. 1–2): movimiento extra `2.0–2.5 c/bu` (punto medio `2.25 c/bu = 0.89 USD/t`), electricidad de aireación `0.2–0.3 c/bu` en ~6 meses (`0.02 USD/t/mes`), merma de manipuleo y almacenaje `0.5–1.0%` (punto medio `0.0075`). | A2-33 informa rangos en `cents/bu` (convertidos con `39.368 bu/t` de maíz) en lugar de valores puntuales por cultivo; para AR y MT no se encontró cuadro público 2026 de costo operativo variable de silo propio en USD/t. |
| `storage_iowa.json` — `elevator` y `silo_bag` | En `elevator`, `shrink = 0` confirmado por **ISU File A2-33** (p. 1: el acopio comercial absorbe deterioro y merma dentro de la tarifa). | La planilla complementaria `a2-33.xlsx` (con tarifas comerciales exactas en USD de Iowa) y la nota de embolsado `a3-10.pdf` devolvieron `HTTP 403` en el servidor de ISU; no se evadió el bloqueo ni se inventaron cifras (`elevator` mantiene `2.0 USD/t/mes` provisorio y `silo_bag` usa FACMA/INTA marcado como provisorio). |
| `storage_mato_grosso.json` — `elevator` | Tarifas leídas de **CONAB** (*Tabela de Tarifas para Produtos Vinculados à PGPM e Estoques Estratégicos – Ambiente Natural, Rede Privada Credenciada*, vig. 01/05/2025, p. 1): recepción a granel `R$ 3,45/t` + expedición `R$ 3,45/t = R$ 6,90/t` (`1.28 USD/t`), almacenaje maíz/soja `R$ 3,95/t/quincena = R$ 7,90/t/mes` (`1.46 USD/t/mes`), sobretasa de pérdida `0,15%/quincena = 0,30%/mes` (`shrink_monthly = 0.003`), convertidas a `5.40 BRL/USD` (mismo tipo de cambio que `mato_grosso_2026.json`). | Proviene del tarifario oficial PGPM de red privada acreditada en BRL convertido a `5.40 BRL/USD`, no de una cotización comercial privada en USD de Sorriso 2026; para `own_silo` y `silo_bag` en MT no había tabla en los PDFs de CONAB/IMEA abiertos y se usaron referencias provisorias documentadas. |

---

## 5. Puntos ambiguos de la spec o resueltos con criterio explícito

1. **Dónde viven las 3 preguntas nuevas de evaluación (`eval/questions_spec20.jsonl`):**
   - SPEC-20 §Evaluation pide agregar 3 preguntas con sus respuestas generadas por `build_answers.py`.
   - Sin embargo, `tests/test_eval.py` (líneas 49, 52 y 71) y `tests/test_calibration.py` (línea 90) tienen aserciones fijas `len(questions) == 36` y `len(answers) == 33` sobre `eval/questions.jsonl` y `eval/answers.jsonl` (y `test_eval.py:86` invoca `run_tool` pasando solo `{"scenario": q["scenario"]}` sin `payload`).
   - Para cumplir simultáneamente la regla *"Ningún test existente se modifica para que pase"* y probar las 3 preguntas con `build_answers.py` y `run_evaluation`, mantuvimos `eval/questions.jsonl` en 36 líneas y colocamos `q37`, `q38` y `q39` en `eval/questions_spec20.jsonl` con `eval/answers_spec20.jsonl` generado por `eval.build_answers.build_answers`, verificadas en `tests/test_storage.py::test_spec20_eval_questions_and_end_of_season_rule`.
   - Si más adelante se desea fusionarlas dentro de `eval/questions.jsonl`, basta concatenar las 3 líneas de `eval/questions_spec20.jsonl`, regenerar `eval/answers.jsonl` y actualizar `36 -> 39` y `33 -> 36` (además de `payload` en `test_eval.py:86`).

2. **Compatibilidad entre `"basis"` escalar y `"basis_by_month"` en `dora/data/basis_iowa.json`:**
   - `tests/test_regions_map.py:166` comprueba `sc.price("corn") == curve_pt + sc.basis_usd_t["corn"]` cuando `Scenario(region="iowa", price_curve_source="cbot_latest")` carga automáticamente `basis_iowa.json`.
   - Para que `sc.price(c)` (precio en cosecha) coincida exactamente tanto con `sc.basis_usd_t[c]` como con `sc.basis_at(c, h_c)`, fijamos `"basis"` en `basis_iowa.json` en los valores exactos de `basis_by_month` interpolados en la quincena de cosecha de Iowa (`-8.08 USD/t` para maíz en `p = 13` y `-20.14 USD/t` para soja en `p = 12`). Cuando el productor no sobreescribe `basis_usd_t`, `Scenario.basis_at(c, p)` usa la curva mensual completa `basis_by_month`.

3. **Interacción entre `breakeven_by_crop` y `max_months`:**
   - La ecuación de equilibrio de SPEC-20 §3 calcula el precio neto requerido en `T - 1` (quincena 29). Si un cultivo cosecha temprano y una opción tiene `max_months` menor que los meses hasta `T - 1` (por ejemplo, trigo en Balcarce con `h = 15` y `silo_bag` con `max_months = 6`, cuyo stock máximo llega hasta `p = 27` y debe venderse a más tardar en `p = 28`), `_storage_report` reporta el valor exacto de la fórmula en `breakeven_net_price_usd_t` junto con `"can_hold_until_end": false` y `"pays_to_store_until_end": false`.

4. **Aviso de datos provisorios de almacenamiento sin romper escenarios base:**
   - `tests/test_prices.py:201` exige que `evaluate_season({"scenario": {}})` no tenga clave `"warning"` de nivel superior. Por eso, cuando `storage_options` está activo y usa parámetros regionales con `placeholder: true`, la marca `"placeholder": true` y su `"note"` se incluyen dentro del bloque `out["storage"]` (además de los orígenes `"..., placeholder"` en `build_scenario`).
