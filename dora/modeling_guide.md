# Guía de Modelado Económico y Formulación de Escenarios para DORA

Esta guía define cómo formular problemas agrícolas a partir de las declaraciones y documentos del productor, y cómo analizar los resultados económicos.

---

## 1. Traducción de Frases del Productor a Parámetros y Restricciones

El productor habla en su lenguaje habitual. Debes mapear sus expresiones a los parámetros y restricciones exactos del motor:

| Frase del productor | Parámetro o Restricción en el Escenario |
|---|---|
| "Por el contrato con la cooperativa tengo que hacer mínimo 200 de soja." | `constraints: [{"type": "min_area", "crop": "soybean", "ha": 200}]` |
| "Ya vendí 300 toneladas de soja para mayo a 320." | `constraints: [{"type": "forward_sale", "crop": "soybean", "month": "2027-05", "tonnes": 300, "price_usd_t": 320}]` |
| "El de los agroquímicos me da a cosecha, pero me recarga un 4%." | `input_payment_delay_fortnights: 6` (o quincenas hasta cosecha), `input_delay_surcharge: 0.04` |
| "Tengo 50 lucas propias y el banco me da hasta 100 al 10%." | `own_capital_usd: 50000, credit_line_usd: 100000, credit_rate_annual: 0.10` |
| "No quiero más de la mitad del campo en maíz." | `constraints: [{"type": "max_area", "crop": "corn", "ha": 0.5 * area}]` o `max_crop_share: 0.5` |
| "El campo es alquilado." | `rented_land: true` |
| "Tengo 500 hectáreas propias." | `area_ha: 500, rented_land: false` |

### Reglas de Unidades y Términos Temporales:
- **"lucas"**: Miles de dólares (ej. "50 lucas" = 50.000 USD).
- **"días" a quincenas**: Cada quincena son 15 días. "90 días" = 6 quincenas; "60 días" = 4 quincenas; "30 días" = 2 quincenas.
- **Superficie**: En Argentina la unidad es hectárea (`ha`). Para Iowa (Estados Unidos), 1 acre = 0.404686 hectáreas.
- **Meses de entrega en contratos forwards**: Formato `YYYY-MM` (ej. "mayo" de la cosecha = `2027-05`).

---

## 2. Coherencia de Documentos y Facturas

Una factura o remito aislado por sí solo no define una campaña completa. Un documento únicamente **reemplaza coeficientes específicos** dentro de un escenario completo estructurado sobre los valores regionales por defecto (MAGyP):

1. **Reemplazo puntual**: Una factura de fertilizante define el costo de ese fertilizante y su plazo comercial, no altera rendimientos ni precios de venta.
2. **Totales a valores por hectárea**: Convierte totales de facturas a USD/ha **únicamente cuando la superficie aplicada es conocida**. Si el productor presenta una factura por USD 30.000 de fertilizante sin indicar cuántas hectáreas cubre, **pregunta la superficie antes de calcular o asumir**.
3. **Verificación de desvíos (>50%)**: Compara cada coeficiente reemplazado con el valor por defecto regional. Si difiere en más de un 50% (o 3× el promedio de la zona), **pide confirmación al productor** antes de utilizarlo; puede tratarse de una compra parcial, un insumo para otro cultivo o un error de tipeo.
4. **Completitud y transparencia**: Informa siempre con claridad qué coeficientes provienen de los documentos del productor y cuáles se mantienen como supuestos o referencias regionales por defecto.

---

## 3. Cuándo Preguntar en Vez de Asumir

Nunca supongas parámetros que alteran sustancialmente el resultado económico y carecen de un valor por defecto universal:
- **Tenencia de la tierra**: Si el campo es propio o alquilado (`rented_land`).
- **Superficie total**: La cantidad de hectáreas disponibles (`area_ha`).
- **Cultivos admisibles**: Qué cultivos puede o quiere sembrar el productor (`crops`). Si menciona un cultivo no soportado (ej. arroz), aclara qué cultivos admite el motor (trigo, maíz, soja, girasol).
- **Datos faltantes o imposibles**: Si faltan datos críticos o el escenario es matemáticamente contradictorio, plantea una pregunta aclaratoria concisa.

---

## 4. Diagnóstico Post-Optimización

Luego de calcular el plan óptimo (`evaluate_season`), realiza un diagnóstico profundo de los cuellos de botella:
1. **Escasez de capital**: Si la tasa interna o el precio sombra del capital propio (`capital_shadow_price > 0`) indican escasez, evalúa alternativas con `sensitivity` (ej. plazos de pago de insumos con proveedores a 90 días o ampliación de la línea de crédito).
2. **Capacidad de almacenaje**: Si el almacenaje tiene precio sombra positivo (`usd_per_extra_tonne > 0`), cuantifica cuánto aporta una tonelada adicional de capacidad propia frente a la venta obligada a cosecha.
3. **Restricciones activas**: Si una restricción contractual (`min_area`, `max_area`, `forward_sale`) resulta activa (`binding: true`), explica su **costo de oportunidad** en términos claros para el productor (ej. cuánto dinero de valor presente cuesta o aporta cumplir con ese contrato).
