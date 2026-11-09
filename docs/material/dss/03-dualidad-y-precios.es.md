# Dualidad, Precios Sombra y Valuación Económica: El Enfoque Dorfman-Samuelson-Solow (1958)

**Destinatarios:**
- **Motor explicativo de DORA:** Cómo traducir los multiplicadores matemáticos del solver en explicaciones económicas en lenguaje natural para productores, gerentes y analistas.
- **Analistas y consultores:** Marco conceptual para interpretar costos de oportunidad, rentas de cuellos de botella y límites del análisis marginal.

---

## 1. El Problema de la Valuación como Espejo de la Asignación

En el Capítulo 3 (pp. 39–63) y el Capítulo 7 (pp. 166–185), Dorfman, Samuelson y Solow (DSS) explican que todo programa lineal contiene dos problemas económicos inseparables:

1. **El problema primal (asignación física):** Cómo combinar actividades y recursos limitados para maximizar el ingreso neto o satisfacer una demanda al menor costo (DSS, p. 39).
2. **El problema dual (imputación de valor):** Cómo asignar un valor económico unitario (precio contable, precio sombra o renta) a cada recurso escaso, de modo que el valor total imputado a los factores justifique exactamente el resultado económico obtenido (DSS, pp. 40–42).

### 1.1. La parábola de la píldora sintética (El dual de la dieta)
Para ilustrar la dualidad sin abstracciones, DSS recurren al problema de la dieta (DSS, pp. 45–48):
- **Primal:** Una persona busca la combinación más barata de alimentos naturales ($x_j$) para cubrir requerimientos mínimos de calorías ($C_1 = 700$) y vitaminas ($C_2 = 400$).
- **Dual:** Un fabricante de productos químicos ofrece nutrientes puros sintéticos en píldoras: píldoras de calorías a un precio $u_1$ y píldoras de vitaminas a un precio $u_2$.
- **Restricción del vendedor:** Para que el consumidor acepte comprar las píldoras en lugar de comida natural, ninguna combinación de nutrientes sintéticos equivalente a un alimento real puede costar más que ese alimento en el mercado:
  $$a_{1j} u_1 + a_{2j} u_2 \le p_j \quad \text{para todo alimento } j$$
- **Objetivo del vendedor:** Maximizar el valor de venta de los nutrientes requeridos: $\max 700 u_1 + 400 u_2$.
- **Resultado económico:** En el óptimo, el valor máximo que puede cobrar el fabricante de píldoras coincide exactamente con el costo mínimo de la dieta natural: $\min \sum p_j x_j = \max \sum C_i u_i = 4.700$ USD (DSS, p. 48). Los precios sombra resultan ser $u_1 = 1$ USD por caloría y $u_2 = 10$ USD por vitamina (DSS, pp. 50–54).

---

## 2. El Teorema Fundamental y las Condiciones de Holgura Complementaria

El vínculo operativo entre el plan físico ($x^*$) y el sistema de precios duales ($u^*$) se rige por tres teoremas económicos (DSS, pp. 42–45, 174–178):

### 2.1. Igualdad de valores extremos
$$\sum_{j=1}^n c_j x_j^* = \sum_{i=1}^m b_i u_i^*$$
El beneficio total de la empresa o el costo del sistema se agota exactamente en la valuación imputada a sus factores limitantes. No hay "beneficio económico puro" residual: todo el ingreso neto se distribuye como rentas de escasez a los recursos cuellos de botella (DSS, p. 43).

### 2.2. Regla de saturación del recurso (Holgura del factor)
$$u_i^* \cdot \left( b_i - \sum_{j=1}^n a_{ij} x_j^* \right) = 0$$
- Si un recurso no se agota por completo en el plan óptimo (capacidad ociosa $> 0$), su precio sombra **es estrictamente cero** ($u_i^* = 0$) (DSS, p. 44). Un factor abundante no frena la producción; por ende, adquirir una unidad adicional no aportaría ningún incremento al beneficio.
- Si un recurso tiene precio sombra positivo ($u_i^* > 0$), su disponibilidad física **debe estar saturada al 100%** (DSS, p. 44).

### 2.3. Regla de rentabilidad de la actividad (Costo de oportunidad)
$$x_j^* \cdot \left( \sum_{i=1}^m a_{ij} u_i^* - c_j \right) = 0$$
- **Para actividades no utilizadas ($x_j^* = 0$):** El costo imputado de los recursos consumidos supera al margen unitario que aportaría la actividad: $\sum a_{ij} u_i^* > c_j$. La diferencia es el **costo reducido** (*reduced cost*), que mide cuánto debería subir el precio del bien (o bajar su costo directo) para que sea rentable producirlo (DSS, pp. 176–178).
- **Para actividades en uso ($x_j^* > 0$):** El costo de los recursos imputados iguala con exactitud al margen neto unitario: $\sum a_{ij} u_i^* = c_j$ (DSS, p. 177). El beneficio contable imputado de operar la actividad es exactamente cero.

---

## 3. Imputación Contable Interna en la Empresa: El Caso Químico

En el Capítulo 7 (pp. 166–185), DSS aplican la dualidad a la planta química descrita en el Capítulo 6 (pp. 141–151), ilustrando cómo se calculan los precios internos de transferencia:

### 3.1. Valuación de equipos y reactores
El modelo resuelve un beneficio neto de 700 USD/mes con cuatro equipos ($E_1, E_2, E_3, E_4$) (DSS, p. 147):
- **Equipo $E_1$ (saturado al 100%):** Precio sombra $u_{E1} = 0,50$ USD por cada 1% de capacidad mensual (DSS, p. 178).
- **Equipo $E_2$ (saturado al 100%):** Precio sombra $u_{E2} = 5,00$ USD por cada 1% de capacidad mensual (DSS, p. 178).
- **Equipo $E_3$ (utilizado al 37,5%, holgura de 62,5%):** Precio sombra $u_{E3} = 0,00$ USD (DSS, p. 178).
- **Equipo $E_4$ (saturado al 100%):** Precio sombra $u_{E4} = 1,50$ USD por cada 1% de capacidad mensual (DSS, p. 178).

### 3.2. Diagnóstico operativo de gestión
1. **Identificación del cuello de botella crítico:** El equipo $E_2$ es el factor más limitante de toda la planta. Ampliar la capacidad de $E_2$ en un 1% mensual incrementa el beneficio neto global en 5,00 USD, diez veces más que ampliar $E_1$ (0,50 USD) y más del triple que $E_4$ (1,50 USD).
2. **Capacidad redundante:** Invertir en mantenimiento o ampliación del equipo $E_3$ tiene un retorno marginal nulo a corto plazo, ya que el 62,5% del reactor está ocioso por falta de insumos de etapas previas.
3. **Valuación de productos intermedios:** Las sustancias intermedias $C_1, C_2, C_3$ adquieren precios de transferencia contable internos de 1,00 USD por unidad (DSS, p. 178). Todo litro de $C_1$ consumido internamente en producir $C_2$ se debita a 1,00 USD, exactamente lo que rendiría si se vendiera en el mercado final.

---

## 4. Descentralización: Posibilidades y Advertencias de DSS

Un tema central de DSS es si la dirección general puede fijar los precios duales y dejar que cada taller decida su producción de forma autónoma (DSS, pp. 59–63, 170–172).

### 4.1. Qué sí logran los precios sombra
- **Filtro de actividades antieconómicas:** Si a un jefe de taller se le cobra por los recursos consumidos al precio sombra $u_i^*$, cualquier propuesta de producto ineficiente arrojará pérdidas contables y será descartada localmente (DSS, p. 171).
- **Evaluación de nuevas tecnologías:** Para evaluar si incorporar una nueva actividad técnica $A_{k}$, basta con calcular su margen neto imputado: $\Delta = c_k - \sum a_{ik} u_i^*$. Si $\Delta > 0$, la técnica mejora el beneficio global de la empresa (DSS, p. 172).

### 4.2. Lo que los precios sombra no pueden resolver por sí solos
DSS señalan dos limitaciones cruciales:
1. **Indeterminación de escala interna:** Para todas las actividades que componen el plan óptimo, el beneficio neto imputado es cero ($c_j - \sum u_i^* a_{ij} = 0$) (DSS, p. 171). Por ende, el precio sombra le dice al taller que esa actividad es admisible, pero no le indica a qué escala operar. Si el taller opera al 50% o al 200%, su balance local sigue dando cero. Se requiere que la dirección fije cuotas físicas de producción o ecuaciones de balance para coordinar el ensamble (DSS, p. 61).
2. **Inestabilidad del tanteo descentralizado:** En mercados o divisiones internas que ajustan precios y cantidades por ensayo y error (*tâtonnement*), las respuestas descentralizadas tienden a sobrecorregir y generar oscilaciones en torno al equilibrio en lugar de converger suavemente (DSS, p. 63). Por ello, las empresas exitosas son "descentralizadas pero no descoordinadas" (*decentralized but not uncoordinated*, DSS, p. 61).

---

## 5. Dualidad Espacial y Transporte (Cap. 5, pp. 122–127)

En el problema de transporte (distribución de fábricas a centros de consumo con fletes $c_{ij}$), las variables duales adquieren una interpretación geográfica directa:
- $u_i$: Valor del producto en boca de fábrica (origen $i$).
- $v_j$: Valor del producto entregado en el mercado local (destino $j$).
- **Condición de no arbitraje:** $v_j - u_i \le c_{ij}$. El diferencial de precios entre dos plazas no puede superar el costo de flete.
- **Rutas activas:** En toda ruta utilizada ($x_{ij}^* > 0$), se cumple $v_j - u_i = c_{ij}$. El precio de destino refleja el precio de origen más el flete exacto.
- **Rentas de localización (*basing points*):** Las fábricas mejor ubicadas respecto a la demanda obtienen una renta diferencial de localización ($u_A > u_B$), reflejada en su variable dual (DSS, pp. 124–127).

---

## 6. Guía para el Agente DORA: Cómo Explicar el Plan al Usuario

Cuando DORA resuelve un modelo para una explotación agrícola o una pyme industrial, debe estructurar la explicación en lenguaje natural siguiendo esta plantilla basada en la dualidad de DSS:

1. **El valor del plan:**
   - Reportar el margen total óptimo ($Z^*$) y explicar que dicho valor representa la máxima rentabilidad alcanzable con los recursos disponibles a los precios vigentes.
2. **Los cuellos de botella (Precios Sombra):**
   - Ordenar las restricciones de mayor a menor precio sombra ($u_i^* > 0$).
   - Explicar en lenguaje directo: *"El recurso más limitante es [Recurso X]. Si pudiera disponer de una unidad adicional (por ejemplo, 1 hora más de tractor o 1 hectárea más de tierra), el beneficio total aumentaría en \$[u_X] por período"*.
3. **Las capacidades sobrantes (Holgura Cero):**
   - Listar los factores con capacidad no utilizada ($s_i > 0$).
   - Explicar: *"El factor [Recurso Y] tiene [s_Y] unidades sin utilizar. Su precio sombra es \$0, lo que significa que incorporar más capacidad en este rubro no aumentará los ingresos mientras persistan los cuellos de botella en [Recurso X]"*.
4. **Las alternativas descartadas (Costos Reducidos):**
   - Para actividades que el modelo dejó en nivel cero ($x_k = 0$), reportar su costo reducido:
   - Explicar: *"El plan no incluye [Producto Z] porque al valorar los recursos que consume a su costo de oportunidad (\$[\sum u_i a_{ik}]), el margen unitario (\$c_k) resulta insuficiente por una diferencia de \$[costo\_reducido]. Para que convenga producirlo, su precio de venta debería subir al menos \$[costo\_reducido]"*.
5. **Rango de validez y cautela:**
   - Advertir que los precios sombra son marginales: *"Esta valuación es válida para variaciones pequeñas de capacidad. Si la ampliación de [Recurso X] supera el límite de base, otro taller pasará a ser el cuello de botella y el valor unitario adicional descenderá"* (DSS, pp. 180–183).
