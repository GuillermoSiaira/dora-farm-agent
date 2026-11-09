# Índice y Guía de Contenidos: Dorfman, Samuelson y Solow (1958)

**Referencia bibliográfica:** Robert Dorfman, Paul A. Samuelson y Robert M. Solow, *Linear Programming and Economic Analysis*, McGraw-Hill Book Company, Nueva York, 1958 (The RAND Series, 538 páginas).

**Ubicación del archivo fuente:**
- Copia local: `material-privado/Dorfman-Samuelson-Solow-Linear-Programming-and-Economic-Analysis.pdf` (538 páginas escaneadas).
- Correspondencia de paginación: Páginas 1–38 del libro = PDF páginas 8–45 (+7 de desfase); Páginas 39–264 = PDF páginas 45–270 (+6 de desfase); Páginas 265–416 = PDF páginas 271–422 (+6/+7 de desfase); Páginas 417–506 = PDF páginas 423–512 (+6 de desfase).

---

## Estructura General y Fichas por Capítulo

### Capítulo 1: Introduction (pp. 1–7 | PDF pp. 8–14)
- **Qué contiene:** Reseña histórica del surgimiento conjunto de la programación lineal (Dantzig, USAF), el análisis insumo-producto (Leontief) y la teoría de juegos (von Neumann), como ramas de una matemática común: el análisis de desigualdades lineales.
- **Utilidad:** **Divulgación** (la historia de cómo la economía lineal unificó problemas de defensa, planificación y mercados) y **Receta** (la justificación de por qué la linealidad no destruye el análisis económico realista).
- **Para DORA / Cursos:** Excelente narrativa introductoria para el curso y para un video de apertura sobre el origen de la optimización con restricciones.

---

### Capítulo 2: Basic Concepts of Linear Programming (pp. 8–38 | PDF pp. 15–45)
- **Qué contiene:** Definición de proceso, actividad y función de producción lineal; planteo geométrico y algebraico del problema de la dieta (Stigler) y comercio internacional; región factible, soluciones básicas y la frontera de eficiencia (sustitución sin curvas suaves).
- **Utilidad:** **Receta** (definición rigurosa de actividades, insumos y aditividad), **Ejemplos** (el problema de la dieta de 5 alimentos y 2 nutrientes, Tablas 2-1 y 2-2) y **Divulgación** (animación de vértices e hiperplanos de corte con Manim).
- **Para DORA / Cursos:** Base formal del generador de modelos de DORA: muestra cómo la sustitución técnica ocurre por combinación de recetas discretas.

---

### Capítulo 3: The Valuation Problem; Market Solutions (pp. 39–63 | PDF pp. 45–69)
- **Qué contiene:** Introducción a la dualidad y los precios sombra; interpretación económica de los multiplicadores como rentas de factores y costos de oportunidad; resolución del problema de la dieta desde el lado del vendedor de nutrientes y condiciones de equilibrio competitivo.
- **Utilidad:** **Receta** (interpretación y validación de precios sombra en el balance), **Ejemplos** (dual de la dieta y asignación descentralizada de recursos) y **Divulgación** (por qué el precio sombra de un recurso no saturado es cero: holgura complementaria).
- **Para DORA / Cursos:** El fundamento teórico de la explicación en lenguaje natural que genera DORA para justificar planes ante un gerente.

---

### Capítulo 4: The Algebra of Linear Programming (pp. 64–105 | PDF pp. 70–111)
- **Qué contiene:** Formalización matricial completa de la programación lineal; desarrollo exhaustivo del método Simplex de Dantzig (variables de holgura, pivoteo, cambio de base, criterios de parada); tratamiento riguroso de la degeneración y ciclos.
- **Utilidad:** **Receta** (reglas de no-negatividad, estandarización de restricciones y chequeo de bases factibles), **Ejemplos** (tablas simplex paso a paso para la dieta) y **Divulgación** (el Simplex como caminata guiada por los vértices de un politopo).
- **Para DORA / Cursos:** Guía esencial para que el agente entienda los diagnósticos del solver (`infeasible`, `unbounded`, `degenerate basis`).

---

### Capítulo 5: The Transportation Problem (pp. 106–129 | PDF pp. 112–135)
- **Qué contiene:** Planteo canónico del problema de transporte de Hitchcock-Kantorovich con orígenes y destinos; propiedades de la base triangular; técnica del "stepping-stone" (reparto modal); manejo de degeneración; dualidad espacial, precios de base (*basing points*) y rentas de localización.
- **Utilidad:** **Receta** (ecuaciones de conservación de flujo y balances en redes), **Ejemplos** (red de 3 orígenes y 4 destinos, con costos y demandas enteras) y **Divulgación** (animación gráfica de flujos en un mapa y arbitraje de precios espaciales).
- **Para DORA / Cursos:** Plantilla directa para el paquete de dominio de logística y transporte en SPEC-48.

---

### Capítulo 6: Linear-programming Analysis of the Firm (pp. 130–165 | PDF pp. 136–171)
- **Qué contiene:** Microeconomía de la empresa con tecnologías discretas; contraste entre la visión del ingeniero (recetas de taller) y la del economista (curvas neoclásicas); integración vertical, productos conjuntos e insumos intermedios; modelo completo de una planta automotriz y una planta química.
- **Utilidad:** **Receta** (el paso a paso definitivo de balance de ítems intermedios y capacidades fijas), **Ejemplos** (el problema automotriz de autos vs. camiones y la planta química de 3 productos y 4 reactores) y **Divulgación** (cómo una fábrica real combina procesos).
- **Para DORA / Cursos:** La piedra angular de la receta de modelado para DORA y para el paquete de dominio industrial (aserradero, manufactura).

---

### Capítulo 7: Application to the Firm; Valuation and Duality (pp. 166–185 | PDF pp. 172–191)
- **Qué contiene:** Teoría de la imputación de valor y productividad marginal interna en la empresa; cálculo de precios de transferencia contable entre talleres; descentralización interna sin planificador central omnisciente; relación entre costos marginales y precios duales.
- **Utilidad:** **Receta** (cómo auditar si un proceso no utilizado es antieconómico mediante costos imputados), **Ejemplos** (valuación de capacidades de estampado y ensamble) y **Divulgación** (la contabilidad de gestión explicada como dualidad matemática).
- **Para DORA / Cursos:** Permite que DORA genere informes de costo de oportunidad ("este taller pierde \$X por hora por culpa del cuello de botella Y").

---

### Capítulo 8: Nonlinear Programming (pp. 186–203 | PDF pp. 192–209)
- **Qué contiene:** Extensión a rendimientos decrecientes y funciones objetivo cóncavas; condiciones de Kuhn-Tucker para óptimos con restricciones de desigualdad; linealización por tramos (*piecewise linear*); el caso de precios de venta que caen con el volumen (ingreso marginal decreciente).
- **Utilidad:** **Receta** (fronteras de validez de la programación lineal y cuándo subdividir actividades en tramos), **Ejemplos** (modelo automotriz con curva de demanda no lineal) y **Divulgación** (visual de curvas de isobeneficio circulares sobre poliedros).
- **Para DORA / Cursos:** Referencia de diseño para saber cuándo DORA debe linealizar un problema o advertir que se requiere programación cuadrática.

---

### Capítulo 9: The Statical Leontief System (pp. 204–229 | PDF pp. 210–235)
- **Qué contiene:** Fundamentos de las matrices insumo-producto abiertas y cerradas de Leontief; tecnología de coeficientes fijos $a_{ij}$; vector de demanda final autónoma; condiciones de solvencia económica (matriz de Hawkins-Simon); el teorema de no-sustitución.
- **Utilidad:** **Receta** (el balance intersectorial como caso particular donde cada sector tiene una única actividad), **Ejemplos** (economías de 2 y 3 sectores con carbón, acero y agricultura) y **Divulgación** (la red de dependencias circulares de una economía nacional).
- **Para DORA / Cursos:** Modelo ideal para ejercicios macroeconómicos y para entender el balance de masa intermedio en cadenas productivas complejas.

---

### Capítulo 10: The Statical Leontief System (Continued) (pp. 230–264 | PDF pp. 236–270)
- **Qué contiene:** Dualidad de precios en el modelo de Leontief (teoría del valor-trabajo añadida y rentas); problemas de agregación de industrias y pérdida de información; algoritmos de inversión matricial para computación práctica; interpretación del multiplicador de Cornfield-Leontief.
- **Utilidad:** **Receta** (advertencias sobre los sesgos de agregar actividades heterogéneas), **Ejemplos** (inversión de matrices $3 \times 3$ con números reales) y **Divulgación** (cómo un aumento de salario o de energía se transmite a todos los precios de la canasta).
- **Para DORA / Cursos:** Casos de prueba rigurosos para multiplicación matricial y cadenas de valor.

---

### Capítulo 11: Dynamic Aspects of Linear Models (pp. 265–308 | PDF pp. 271–314)
- **Qué contiene:** Modelos lineales multi-período en tiempo discreto; diferenciación estricta entre flujos de producción y stocks de capital fijo; rezagos de maduración de inversiones (*gestation lags*); el modelo dinámico de Leontief y ecuaciones en diferencias acopladas.
- **Utilidad:** **Receta** (modelado multi-período: indexación temporal de actividades $x_{j,t}$ y balances de stock $S_t = S_{t-1} + I_t - D_t$), **Ejemplos** (acumulación de capital en 2 sectores a lo largo de $T$ períodos) y **Divulgación** (animación de trayectorias temporales de inversión).
- **Para DORA / Cursos:** Conexión directa con la lógica quincenal de DORA (guardar en silo vs. vender, rotación de cultivos, flujo de caja proyectado).

---

### Capítulo 12: Efficient Programs of Capital Accumulation (pp. 309–345 | PDF pp. 315–351)
- **Qué contiene:** El problema de Ramsey linealizado y trayectorias óptimas de acumulación de bienes de capital; el célebre "Teorema de la Autopista" (*Turnpike Theorem*); crecimiento balanceado a la tasa máxima sobre el rayo de von Neumann; dualidad intertemporal y tasas de descuento implícitas.
- **Utilidad:** **Receta** (fijación de condiciones de contorno terminales en modelos dinámicos para evitar que el solver liquide todo el capital al final), **Ejemplos** (trayectorias numéricas de 3 períodos) y **Divulgación** (la metáfora de la autopista: desviarse para acelerar).
- **Para DORA / Cursos:** Concepto clave para fijar el valor de rezago o inventario final en modelos de planificación de horizontes finitos.

---

### Capítulo 13: Linear Programming and General Equilibrium (pp. 346–389 | PDF pp. 352–395)
- **Qué contiene:** Resolución del problema inconcluso de Walras: existencia, unicidad y no-negatividad de precios y cantidades en equilibrio general; uso del Lema de Farkas, teoremas de separación de convexos y punto fijo de Kakutani; conexión con Arrow-Debreu.
- **Utilidad:** **Receta** (verificación de condiciones de equilibrio y compatibilidad global de mercados), **Ejemplos** (economía de intercambio y producción simplificada) y **Divulgación** (la "mano invisible" formalizada con hiperplanos separadores).
- **Para DORA / Cursos:** Nivel avanzado para cursos universitarios y material de lectura profunda para el equipo técnico.

---

### Capítulo 14: Linear Programming and Welfare Economics (pp. 390–416 | PDF pp. 396–422)
- **Qué contiene:** Los dos teoremas fundamentales de la economía del bienestar derivados mediante programación lineal; optimalidad de Pareto como frontera de posibilidades de utilidad; precios duales como tasas marginales de sustitución social; análisis de externalidades e impuestos pigouvianos.
- **Utilidad:** **Receta** (formulación de funciones objetivo sociales y ponderaciones de bienestar), **Ejemplos** (asignación de recursos entre consumidores y firmas con compensación) y **Divulgación** (por qué los precios de mercado descentralizan un óptimo social bajo convexidad).
- **Para DORA / Cursos:** Marco conceptual para explicar por qué optimizar la función objetivo de una empresa no perjudica la eficiencia interna.

---

### Capítulo 15: Elements of Game Theory (pp. 417–445 | PDF pp. 423–451)
- **Qué contiene:** Juegos bipersonales de suma cero en forma normal; matrices de pagos; estrategias puras vs. estrategias mixtas; principio y Teorema del Minimax de von Neumann; puntos de silla; interpretación económica en duopolios y competencia militar/estratégica.
- **Utilidad:** **Receta** (modelado de incertidumbre adversarial y criterios de decisión robustos *maximin*), **Ejemplos** (juegos $2 \times 2$ y $3 \times 3$ de duopolio con resolución geométrica) y **Divulgación** (el juego de piedra, papel o tijera y estrategias aleatorizadas en negocios).
- **Para DORA / Cursos:** Base para escenarios competitivos o juego de simulación (Omán, mercados agrícolas bajo incertidumbre).

---

### Capítulo 16: Interrelations between LP and Game Theory (pp. 446–464 | PDF pp. 452–470)
- **Qué contiene:** Demostración constructiva de la equivalencia matemática total entre un juego matricial de suma cero y un par de programas lineales duales; transformación de cualquier LP en un juego simétrico y viceversa; el algoritmo de Brown-von Neumann de juego ficticio (*fictitious play*).
- **Utilidad:** **Receta** (técnica para resolver juegos usando cualquier solver simplex estándar), **Ejemplos** (conversión paso a paso de la matriz de juego a un problema primal-dual acotado) y **Divulgación** (la dualidad explicada como dos jugadores adversarios que compiten por el valor del juego).
- **Para DORA / Cursos:** Demostración elegante y práctica de que el solver de DORA sirve también para resolver problemas de estrategia competitiva.

---

### Apéndices y Referencias
- **Apéndice A: Chance, Utility, and Game Theory (pp. 465–469 | PDF pp. 471–475):** Axiomática de la utilidad esperada de von Neumann-Morgenstern; medición de aversión al riesgo; sirve para **Divulgación** y contextualización teórica de por qué optimizar valores esperados es racional.
- **Apéndice B: The Algebra of Matrices (pp. 470–506 | PDF pp. 476–512):** Tratado pedagógico exhaustivo y autosuficiente de álgebra lineal (espacios vectoriales, matrices, determinantes, rango, independencia lineal, inversión, conos conexos y lema de Farkas); sirve como **Receta de cómputo** y referencia matemática para programadores y agentes.
- **Bibliografía Comentada (pp. 507–512 | PDF pp. 513–518):** Reseñas analíticas de los textos fundacionales clasificados por áreas (programación lineal, insumo-producto, teoría de juegos, economía matemática).
- **Índice Alfabético Analítico (pp. 513–531 | PDF pp. 519–538):** Catálogo temático detallado de términos, modelos y autores citados en el texto.

