# Receta de Modelado de Programación Lineal: Enfoque Dorfman-Samuelson-Solow (1958) y Método Tow (1999)

**Destinatarios:**
1. **Agente autónomo de DORA:** Reglas de formulación y chequeos para pasar de descripciones informales a modelos matemáticos.
2. **Paquetes de dominio:** Patrones para agro, aserradero, química y transporte.
3. **Analistas:** Guía de modelado microeconómico con programación lineal.

---

## 1. Fundamentos Conceptuales de Dorfman, Samuelson y Solow

Dorfman, Samuelson y Solow (DSS) estructuran el modelo a partir de la microeconomía de la producción de la empresa (DSS, Cap. 6, pp. 130–165).

### 1.1. La visión del ingeniero frente a la función de producción tradicional
- La teoría económica neoclásica utiliza funciones de producción continuas y diferenciables ($Q = f(K, L)$) (DSS, p. 131).
- En la ingeniería de planta, las opciones no consisten en variaciones infinitesimales de insumos, sino en elegir entre distintas "formas de hacer las cosas" (*ways of doing things*) (DSS, p. 132).
- Un **proceso** o **actividad** es una relación técnica fija entre tasas de consumo de insumos y tasas de producción por unidad de intensidad operativa (DSS, p. 132).
- La sustitución entre factores o productos surge de operar simultáneamente dos o más procesos a distintos niveles (DSS, p. 133).
- La **frontera de posibilidades de producción** es un poliedro convexo lineal por tramos, cuyos vértices son los procesos puros (DSS, Cap. 2, pp. 33–38; Cap. 6, pp. 133–136).

### 1.2. Los cuatro supuestos del modelo lineal
Para representar un sistema mediante programación lineal deben cumplirse cuatro condiciones empíricas (DSS, pp. 132–134):
1. **Proporcionalidad:** Cada proceso opera a rendimientos constantes a escala. Duplicar la escala duplica insumos y productos (DSS, p. 132).
   - *Desviaciones reconocidas por los autores:* En el campo agrícola, la proporcionalidad es solo una aproximación. El rinde varía en los bordes del lote respecto al centro; el tiempo de viaje dentro de la parcela no es proporcional al área; y la longitud del cercado crece con el perímetro (raíz cuadrada de la superficie), no linealmente con la superficie (DSS, p. 132, ítems 1–4).
2. **Aditividad:** Al ejecutar procesos simultáneos, los insumos totales consumidos y productos obtenidos son la suma directa de los insumos y productos de cada proceso, sin interferencias ni sinergias tecnológicas no modeladas (DSS, p. 133).
3. **Divisibilidad:** Los niveles de actividad $x_j$ pueden tomar cualquier valor real no negativo continuo ($x_j \ge 0$) (DSS, p. 133).
   - *Dominio estrictamente continuo:* La receta está formulada para variables continuas. Las variables enteras y binarias (programación lineal entera o mixta, MIP/MILP) quedan fuera de este marco. En modelos con variables enteras o binarias se pierde la lectura directa de los precios sombra y del análisis de sensibilidad, ya que la región factible deja de ser un poliedro convexo y no existen hiperplanos de soporte continuos en los vértices discretos.
4. **Finitud:** El número de procesos tecnológicos disponibles es finito y discreto (DSS, p. 133).

---

## 2. Comparación Sistemática: DSS (1958) vs. Tow (1999)

Fernando Tow formalizó un método pedagógico de cinco pasos para la formulación de modelos lineales (Tow, 1999, pp. 18–20).

### Tabla de Correspondencia

| Paso de Tow (1999, pp. 18–20) | Enfoque DSS (1958) | Diferencias y complementos |
|---|---|---|
| **1. Identificación de actividades** ($x_j$) | Definición de procesos $P_j$ y niveles $x_j$ (DSS, p. 132). | DSS separa las actividades de transformación física de las actividades de compra y venta de mercado (DSS, pp. 142–143). |
| **2. Identificación de ítems** | Vector de flujos netos $y$ (DSS, pp. 142–146). | DSS divide los ítems en factores fijos/capacidades (utilización $\le 100\%$) e ítems intermedios (balance neto $= 0$) (DSS, p. 145). |
| **3. Coeficientes insumo-producto** ($a_{ij}$) | Matriz de tecnología $A$ por columnas de procesos (DSS, pp. 143–145). | Coincidencia en la representación matricial de Dantzig (DSS, p. 143; Tow, p. 24). |
| **4. Flujos externos** ($b_i$) | Vector de limitaciones $s$ (DSS, p. 145). | DSS modela capacidades de planta y cuotas de mercado en el mismo vector de restricciones (DSS, p. 145). |
| **5. Ecuaciones de balance y Objetivo** | Sistema $y = Ax \ge s$ y $\max Z = c'x$ (DSS, p. 145). | DSS añade la teoría de precios sombra para imputación contable interna y control (DSS, Cap. 3 y Cap. 7). |

### Puntos de coincidencia
1. **Matriz Actividad $\times$ Ítem:** Ambos utilizan la tabla de Dantzig con actividades en columnas e ítems en filas (DSS, p. 143; Tow, p. 24).
2. **Ecuaciones de balance universales:** Cada bien o factor físico requiere una ecuación contable cerrada (DSS, p. 145; Tow, p. 20).
3. **Ítems intermedios:** Tanto el modelo de ensilaje de Tow (Tow, pp. 23–24) como la planta química de DSS (DSS, pp. 141–151) exigen que la producción de un bien intermedio cubra el consumo de otros procesos más las ventas.
4. **Interpretación del dual:** Los valores duales corresponden a rentas de factores y costos de oportunidad de los cuellos de botella (DSS, pp. 39–45, 174–178; Tow, pp. 48–60).

### Qué agrega DSS
1. **Diferenciación estricta de productos intermedios y factores:** En la planta química, los productos $C_1, C_2, C_3$ tienen cota cero ($y_k = 0$), mientras los equipos $E_1 \dots E_4$ tienen cotas de capacidad mensual ($s_i = -100$) (DSS, p. 145).
2. **Límites de la descentralización por precios:** DSS demuestran que los precios sombra por sí solos no bastan para descentralizar la producción dentro de la empresa (DSS, pp. 61–63, 170–172). En el óptimo, toda actividad utilizada da beneficio neto imputado igual a cero; por ende, el precio no le indica al jefe de taller cuánto producir. Además, los intentos de ajuste descentralizado por tanteo suelen oscilar sin converger de forma directa (DSS, p. 63). Se requiere una asignación cuantitativa central de cuotas o balances (DSS, p. 61).
3. **Estructura espacial de transporte:** DSS formalizan cómo las tarifas de flete determinan diferencias de precios geográficos y sistemas de precios de base (*basing points*) mediante variables duales (DSS, Cap. 5, pp. 106–127).

### Errores de modelado señalados por DSS
1. **Definir variables por producto en lugar de proceso:** Si un bien puede fabricarse con dos tecnologías, definir una sola variable agregada impide optimizar la elección de técnica (DSS, p. 132).
2. **Inconsistencia de horizonte temporal:** Mezclar capacidades mensuales con tasas horarias o demandas anuales (DSS, p. 145).
3. **Omitir el balance de bienes intermedios:** No incluir una fila de balance que vincule etapas sucesivas de producción (DSS, p. 145).
4. **Olvidar restricciones de capacidad secundaria:** Restringir solo el equipo principal y omitir talleres auxiliares o espacio de almacenaje (DSS, p. 145).
5. **Extrapolar precios sombra fuera del rango de base:** Un precio sombra solo rige dentro del intervalo de variación del recurso que no altera la base óptima (DSS, pp. 180–183).

---

## 3. Guía de Construcción del Modelo para el Agente

### Paso 1: Definir el horizonte temporal
Fijar una única unidad de tiempo para todo el modelo (mes, quincena o año). Todas las tasas, disponibilidades y demandas deben referirse a dicho período (DSS, p. 145).

### Paso 2: Identificar el catálogo de ítems (filas)
Clasificar cada ítem en una de cinco categorías (DSS, pp. 142–146; Tow, pp. 19–20):
1. **Factores fijos y equipos limitantes:** Horas de máquina, capacidad de reactores, superficie de tierra.
2. **Insumos comprados:** Materias primas y suministros provistos externamente.
3. **Ítems intermedios:** Bienes producidos internamente que se consumen en etapas posteriores o se venden.
4. **Productos finales:** Bienes terminados para entrega externa.
5. **Ítems financieros:** Saldos de caja y líneas de crédito.

### Paso 3: Identificar el menú de actividades (columnas)
Definir variables de decisión $x_j \ge 0$ (DSS, pp. 142–143; Tow, p. 19):
1. Procesos de transformación física.
2. Procesos de compra de insumos.
3. Procesos de venta de productos.
4. Procesos de almacenamiento o transferencia intertemporal.
5. Procesos financieros (endeudamiento o colocación).

### Paso 4: Construir la matriz de coeficientes ($a_{ij}$) y convención de signos
DSS utiliza una única convención contable (DSS, p. 143, Tabla 6-4; p. 145, Eq. 6-2):
- **Consumo de un ítem:** Coeficiente con signo negativo ($-a_{ij}$).
- **Producción de un ítem:** Coeficiente con signo positivo ($+a_{ij}$).
- **Restricción canónica matricial:**
  $$y = Ax \ge s$$
  donde $y$ es el vector de resultados netos y $s$ es el vector de cotas externas.
  - Para ítems intermedios en equilibrio: $y_k = 0$ (o $\ge 0$).
  - Para capacidades fijas de equipos: $s_i = -100$ (disponibilidad máxima del 100%).
  - *Ejemplo de DSS (Cap. 6, p. 145, equipo $E_2$):*
    $$y_5 = -5x_1 - 4x_2 - 2x_3 + 0x_4 + 0x_5 + 0x_6 \ge -100$$
- **Traducción a la forma estándar en planillas y solvers:**
  Multiplicando por $-1$, la restricción se expresa como "consumo $\le$ capacidad" con coeficientes positivos:
  $$5x_1 + 4x_2 + 2x_3 \le 100$$

### Paso 5: Especificar flujos externos y cotas ($b_i$)
Asignar la cota para cada fila: capacidades máximas de factores, requerimientos mínimos de entrega y balances cero para intermedios (DSS, p. 145; Tow, p. 20).

### Paso 6: Formular la función objetivo
Definir la maximización de ingresos netos o minimización de costos directos asignando el margen unitario neto $c_j$ a cada actividad (DSS, p. 145; Tow, p. 20).

---

## 4. Chequeos Críticos de Validación

El agente debe verificar las siguientes condiciones antes y después de resolver (DSS, pp. 145–147, 174–178; Tow, p. 20):

1. **Consistencia dimensional por fila:** En cada fila $i$, $\text{Unidad}(a_{ij}) \times \text{Unidad}(x_j) = \text{Unidad}(b_i)$ (DSS, p. 145).
2. **No negatividad y continuidad explícita:** $x_j \ge 0$ continua para toda actividad física o económica (DSS, p. 145). Si el problema requiere variables enteras o binarias, advertir que se pierde la lectura marginal directa de los precios sombra.
3. **Cierre de ítems intermedios:** Todo bien intermedio debe poseer al menos un proceso generador ($a_{ij} > 0$) y un proceso demandante o de venta ($a_{ik} < 0$) (DSS, p. 145).
4. **Acotamiento:** Toda actividad con beneficio unitario positivo debe consumir al menos un recurso con cota superior finita (DSS, p. 145).
5. **Conservación de flujo en redes:** La oferta total debe igualar o superar la demanda total (DSS, Cap. 5, p. 107).
6. **Holgura complementaria post-solución (DSS, pp. 174–178):**
   - Si la capacidad tiene holgura ($b_i - \sum a_{ij} x_j^* > 0$), su precio sombra debe ser cero ($u_i^* = 0$).
   - Si el precio sombra es positivo ($u_i^* > 0$), la capacidad debe estar saturada ($\sum a_{ij} x_j^* = b_i$).
   - Si la actividad no se utiliza ($x_j^* = 0$), su costo imputado debe ser mayor o igual a su ingreso ($\sum u_i^* a_{ij} \ge c_j$).
   - Si la actividad se utiliza ($x_j^* > 0$), su costo imputado debe igualar con exactitud a su ingreso ($\sum u_i^* a_{ij} = c_j$).

---

## 5. Versión Condensada de la Receta (máx. 600 palabras)

### Pasos Operativos de Modelado

1. **Horizonte temporal:** Fijar un único período homogéneo para flujos, capacidades y demandas (mes, quincena o año) (DSS, p. 145).
2. **Catálogo de ítems (filas):** Listar todos los ítems clasificados en cinco grupos: capacidades de equipos, insumos comprados, productos intermedios, productos finales y saldos financieros (DSS, pp. 142–146; Tow, pp. 19–20).
3. **Menú de actividades (columnas):** Definir variables $x_j \ge 0$ para cada técnica productiva, compra de insumos, venta de productos, almacenamiento y financiación (DSS, pp. 142–143; Tow, p. 19).
4. **Matriz técnica y convención de signos:**
   - En el planteo de DSS ($y = Ax \ge s$), consumo lleva signo negativo y producción signo positivo (DSS, p. 145). Para el equipo $E_2$: $-5x_1 - 4x_2 - 2x_3 \ge -100$.
   - En formato estándar de planilla o solver, expresar "consumo $\le$ capacidad" con coeficientes positivos: $5x_1 + 4x_2 + 2x_3 \le 100$.
   - Para bienes intermedios, fijar balance neto en cero: producción interna menos consumos internos menos ventas $= 0$ (DSS, p. 145; Tow, p. 24).
5. **Flujos externos:** Establecer lados derechos ($b_i$): cuotas de mercado, capacidades de planta y metas de demanda (DSS, p. 145; Tow, p. 20).
6. **Función objetivo:** Maximizar el margen neto total asignando a cada actividad su precio de venta, costo directo o costo de compra unitario (DSS, p. 145; Tow, p. 20).

### Chequeos Obligatorios

1. **Unidades:** Comprobar que en cada fila todos los términos sumen en la misma unidad que el lado derecho (DSS, p. 145).
2. **Cierre de intermedios:** Verificar que ningún producto intermedio quede sin fuente de abastecimiento ni sin sumidero (DSS, p. 145).
3. **Acotamiento:** Asegurar que ninguna actividad rentable pueda crecer sin límite sin agotar algún factor fijo (DSS, p. 145).
4. **Holgura complementaria:** En el reporte final, comprobar que todo recurso con capacidad remanente tenga precio sombra nulo, y que toda actividad en uso cubra exactamente sus costos imputados (DSS, pp. 174–178).
5. **Límite de precios duales y variables continuas:** Recordar que los precios sombra identifican cuellos de botella y costos de oportunidad, pero no bastan por sí solos para descentralizar los talleres sin cuotas físicas centrales de producción (DSS, pp. 61–63, 170–172). Asimismo, el método rige exclusivamente para variables continuas: en variables enteras o binarias se anula la interpretación directa de los precios sombra.
