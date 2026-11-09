# Receta de Modelado de Programación Lineal en Planillas

Esta guía metodológica enseña a formular programas lineales para planillas de cálculo, basada en el método microeconómico de Fernando V. Tow (*Programación lineal como instrumento de modelado microeconómico*, Ediciones Macchi, Buenos Aires, 1999, pp. 18–20 y 48–60).

---

## Parte 1: El Primal — Método de los Cinco Pasos (Tow, pp. 18–20)

Para construir el modelo primal, organizá el problema en una tabla de actividades e ítems siguiendo estos cinco pasos secuenciales:

### Paso 1: Actividades (Variables de Decisión $x_j$)
Identificá qué decisiones cuantitativas debe tomar el productor o decisor.
- Cada actividad es una columna de la planilla (rango de celdas de decisión, ej. `B5:E5`).
- Ejemplos: hectáreas sembradas de cada cultivo, toneladas vendidas en cosecha, toneladas ensiladas, animales criados, unidades transportadas o producidas.
- Inicializá siempre estas celdas en `0` en la planilla.

### Paso 2: Ítems, Factores y Balances (Restricciones $i$)
Identificá qué factores productivos, capacidades físicas, fondos de caja o balances de materiales intervienen en el sistema.
- Cada ítem es una fila en la planilla.
- Ejemplos: tierra disponible (ha), mano de obra (horas), capacidad de almacenamiento en silos (t), grano cosechado vs. destino, caja propia o línea de crédito (USD), cupos de rotación agronómica.

### Paso 3: Coeficientes Insumo-Producto ($a_{ij}$)
Determiná cuánto insume o produce una unidad unitaria de cada actividad respecto a cada ítem.
- Insumo: si la actividad consume del factor (ej. 1 ha de maíz consume 1 ha de tierra, 2 horas de trabajo, 600 USD de capital).
- Producto: si la actividad genera disponibilidad de un bien intermedio (ej. 1 ha de maíz rinde 6 toneladas de grano).
- Convención de signos: lo consumido suma en el lado izquierdo; lo producido por una actividad interna resta del insumo o suma al balance.

### Paso 4: Flujos Externos y Disponibilidades ($b_i$)
Establecé las dotaciones iniciales fijas provistas desde el entorno exterior (lado derecho o RHS de cada fila).
- Dotaciones disponibles: tierra total disponible $\le 100$ ha; capital propio $\le 260.000$ USD; capacidad de silo $\le 300$ t.
- Requerimientos o demandas mínimas: entrega requerida en puerto $\ge 250$ t; contenido proteico mínimo $\ge 12$ unidades.
- Balances de transferencia interna: grano vendido + grano consumido $\le$ grano cosechado, es decir, $-\text{cosecha} + \text{venta} + \text{consumo} \le 0$.

### Paso 5: Ecuaciones de Balance y Función Objetivo
Expresá las relaciones en fórmulas de planilla:
- **Función Objetivo:** calculá el margen o beneficio total neto mediante `=SUMPRODUCT(variables, márgenes)` (para maximizar) o `=SUMPRODUCT(variables, costos)` (para minimizar).
- **Restricciones:** en cada fila, calculá el uso total del recurso con fórmulas lineales (ej. `=SUM(B5:E5)` o `=SUMPRODUCT(B5:E5, B3:E3)`) y vinculalo con el límite mediante `<=`, `>=`, o `=`.

### Lista de Chequeo Obligatoria del Primal
1. **¿Cada ítem tiene su fila de balance?** Verificá que ningún recurso escaso o flujo de materia quede sin restricción.
2. **¿Las unidades son coherentes?** Toda la fila debe medirse en la misma unidad física o monetaria (no mezcles kg con toneladas ni meses con años).
3. **¿Declaraste la no-negatividad?** Incluí explícitamente `variables >= 0`. Olvidarla permite hectáreas o ventas negativas absurdas.
4. **¿Hay números inventados?** Cada constante numérica debe provenir explícitamente del enunciado. Si falta un dato esencial (capital, arriendo, demanda), **preguntalo al usuario en `questions_to_user` o declaralo expresamente en `assumptions`**. ¡Nunca inventes datos en silencio!

---

## Parte 2: El Dual y la Interpretación Económica (Tow, pp. 48–60)

El dual es la representación económica del problema primal en términos de **precios sombra** o costos de oportunidad de los recursos (Tow, pp. 48–52). No se resuelve a mano: la máquina lo resuelve transponiendo la estructura del primal.

### Deducción del Dual desde el Primal
En el esquema de Tow, la tabla primal de actividades (columnas) $\times$ ítems (filas) se transpone:
1. **Una variable dual por cada fila primal ($y_i$):** cada restricción primal $i$ tiene un precio sombra imputado $y_i$, que representa el valor marginal de disponer de una unidad adicional de ese recurso.
2. **Una restricción dual por cada columna primal ($j$):** cada actividad primal genera una condición de coste de oportunidad: el valor de los insumos consumidos por la actividad, valorados a sus precios sombra, debe ser al menos igual al beneficio neto que la actividad aporta:
   $$\sum_{i} a_{ij} y_i \ge c_j \quad (\text{para primal de maximización})$$
3. **Sentido opuesto:**
   - Si el primal es **maximizar**, el dual es **minimizar** el valor imputado total de los recursos disponibles: $\min w = \sum_i b_i y_i$.
   - Si el primal es **minimizar**, el dual es **maximizar** el valor de los requerimientos: $\max w = \sum_i b_i y_i$.

### Regla Canónica de Signos de los Precios (Tow, pp. 50–51)
- **Primal `max`:**
  - Restricción $\le$ (recurso escaso): $y_i \ge 0$. Relajar la restricción (más recurso) aumenta el beneficio.
  - Restricción $\ge$ (cuota o exigencia): $y_i \le 0$. Aumentar la exigencia disminuye el beneficio.
  - Restricción $=$ (balance estricto): $y_i$ libre (puede ser positivo o negativo).
- **Primal `min`:**
  - Restricción $\ge$ (requerimiento mínimo): $y_i \ge 0$. Aumentar el requerimiento eleva el costo.
  - Restricción $\le$ (límite superior de costo): $y_i \le 0$.
  - Restricción $=$: $y_i$ libre.

### Teoremas Fundamentales y Lectura Económica (Tow, pp. 53–57)
- **Dualidad Fuerte:** si el primal tiene solución óptima finita, el dual también la tiene y ambos objetivos coinciden exactamente:
  $$\max z = \min w$$
- **Holgura Complementaria:**
  - Si un recurso tiene holgura positiva ($b_i - \sum a_{ij} x_j > 0$, recurso abundante), su precio sombra es estrictamente cero ($y_i = 0$). Un recurso que sobra no vale nada en el margen.
  - Si un precio sombra es estrictamente positivo ($y_i > 0$), el recurso está completamente agotado (restricción activa).
  - Si una actividad se realiza a nivel positivo ($x_j > 0$), el costo imputado de sus insumos iguala exactamente su margen ($c_j = \sum a_{ij} y_i$).
- **Costo Reducido y Precio de Indiferencia:**
  - Para una actividad atractiva no realizada ($x_j = 0$), el costo reducido es $r_j = c_j - \sum a_{ij} y_i \le 0$. Mide cuánto pierde el sistema por unidad si fuerza la realización de esa actividad.
  - El **precio de indiferencia** es el precio mínimo de mercado necesario para que la actividad entre al plan óptimo: $P^* = P_{\text{actual}} - r_j$.
- **Rango de Validez del Lado Derecho (RHS Range):**
  - Es el intervalo $[b_i^{\min}, b_i^{\max}]$ en el cual el precio sombra $y_i$ permanece constante. Fuera de ese rango, la base óptima cambia y el recurso adquiere un valor marginal diferente.

### Lista de Chequeo Obligatoria del Dual
1. **¿Existe un precio $y_i$ por cada restricción primal?** Mapealo con `price_of_row`.
2. **¿El sentido del objetivo está invertido?** (Minimización si el primal es maximización).
3. **¿Los signos de los precios respetan la convención canónica?** ($\ge 0$ para recursos $\le$ en maximización).
4. **¿Se cumple la dualidad fuerte?** El valor óptimo del dual debe ser idéntico al del primal dentro del 0,1%.
5. **¿Los recursos con holgura tienen precio sombra cero?**

