# Registro de Lectura y Pendientes: Dorfman, Samuelson y Solow (1958)

Este documento registra los rangos de páginas leídos y analizados, la verificación de citas en fuentes primarias, incidencias de escaneo o legibilidad, y el estado de avance para `02-ejemplos.jsonl`.

---

## 1. Verificación de Citas Textuales y Páginas

Todas las citas de las secciones 1, 2 y 4 de la receta (`01-receta-de-modelado.es.md` y `01-modeling-recipe.en.md`) fueron contrastadas directamente en los PDFs originales:

| Afirmación / Concepto | Fuente Primaria | Página Verificada | Estado |
|---|---|---|---|
| Esquema de los cinco pasos de modelado | Fernando Tow (1999), Macchi | pp. 18–20 (Sección 1) | **Verificado** en PDF `p15-p16.png` |
| Problema de producción, ensilaje y venta | Fernando Tow (1999), Macchi | pp. 23–24 (Tablas I y II de Dantzig) | **Verificado** en PDF `p19-p20.png` |
| Visión del ingeniero vs. curvas neoclásicas | Dorfman, Samuelson y Solow (1958) | pp. 130–132 | **Verificado** en PDF pp. 136–138 |
| Definición de proceso como "forma de hacer las cosas" | Dorfman, Samuelson y Solow (1958) | p. 132 | **Verificado** en PDF p. 138 |
| Los 4 supuestos (proporcionalidad, aditividad, divisibilidad, finitud) | Dorfman, Samuelson y Solow (1958) | pp. 132–134 | **Verificado** en PDF pp. 138–140 |
| Desviaciones de proporcionalidad: cercado no proporcional a la superficie | Dorfman, Samuelson y Solow (1958) | p. 132 (ítem 3: *"length of fencing is not proportional to acreage"*) | **Verificado** en PDF p. 138 |
| Frontera de eficiencia lineal por tramos | Dorfman, Samuelson y Solow (1958) | pp. 33–38; pp. 133–136 | **Verificado** en PDF pp. 40–45, 139–142 |
| Matriz tecnológica de planta química (Tabla 6-4) | Dorfman, Samuelson y Solow (1958) | p. 143 | **Verificado** en PDF p. 149 |
| Convención de signos $y = Ax \ge s$, fila de equipo $E_2$ | Dorfman, Samuelson y Solow (1958) | p. 145 (Eq. 6-2) | **Verificado** en PDF p. 151 |
| Solución de planta química (700 USD/mes, $x_1=10, x_2=7.5, x_3=10, x_4=6.75, x_5=2.5, x_6=10$) | Dorfman, Samuelson y Solow (1958) | pp. 147–149 | **Verificado** en PDF pp. 153–155 y resuelto con `scipy.optimize.linprog` |
| Descentralización: oscilación del tanteo y "descentralizado pero no descoordinado" | Dorfman, Samuelson y Solow (1958) | pp. 61–63 | **Verificado** en PDF pp. 67–69 |
| Precios duales: beneficio neto imputado cero en actividades en uso | Dorfman, Samuelson y Solow (1958) | pp. 170–172, 176–178 | **Verificado** en PDF pp. 176–178, 182–184 |
| Transporte canónico y rentas de localización (*basing points*) | Dorfman, Samuelson y Solow (1958) | pp. 106–127 | **Verificado** en PDF pp. 112–133 |

---

## 2. Registro de Lectura y Estado por Capítulos

- **Capítulos 1 a 7 (pp. 1–185):** Leídos en su totalidad mediante OCR e inspección directa de páginas de tablas. Fundamentos de modelado, simplex, transporte, teoría de la firma y dualidad completamente analizados.
- **Capítulos 8 a 16 (pp. 186–464) y Apéndices A-B:** Relevados a nivel de estructura, índice temático del libro y secciones clave. **Regla metodológica:** No se les atribuye contenido no leído de forma directa.
- **Paginación:** Desfase `PDF = Libro + 7` en Caps. 1-2; `PDF = Libro + 6` en Caps. 3-16.

---

## 3. Verificaciones de Soluciones Numéricas con `scipy.optimize.linprog`

1. **Planta Química (DSS, pp. 141–150):**
   - **Resultado del libro (p. 147–149):**
     - $Z = 700$ USD/mes.
     - Niveles de actividad: $x_1 = 10, x_2 = 7.5, x_3 = 10, x_4 = 6.75, x_5 = 2.5, x_6 = 10$.
     - Estado de equipos: $E_1, E_2, E_4$ utilizados al 100% (holgura = 0). Equipo $E_3$ utilizado al 37.5% (holgura = 62.5%, variable $x_{10} = 62.5$).
     - *Nota sobre fe de erratas del libro (p. 149):* El libro rotula $x_{10}$ como capacidad ociosa de $E_3$ cuando $A_{10}$ correspondía en la numeración a $E_4$, pero numéricamente el equipo saturado es $E_4$ ($10 \times 10 = 100\%$) y el subutilizado es $E_3$ ($5 \times 7.5 = 37.5\%$).
   - **Resultado `scipy.optimize.linprog` (método HiGHS):**
     - `fun`: $-700.0$ (ingreso neto $+700.0$ USD).
     - `x`: `[10.0, 7.5, 10.0, 6.75, 2.5, 10.0]`.
     - `slack`: $E_1 = 0.0\%$, $E_2 = 0.0\%$, $E_3 = 62.5\%$, $E_4 = 0.0\%$.
     - `verificado`: **true** (diferencia absoluta: $0.0$).
