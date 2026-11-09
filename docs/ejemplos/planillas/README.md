# Planillas de ejemplo de DORA (SPEC-45)

Este directorio contiene seis planillas de ejemplo con el modelo de optimización lineal completo incorporado en la hoja **Modelo**, además de un modelo lineal mínimo de prueba (`lp-minimo.xlsx`).

Cada archivo puede resolverse de manera independiente con el complemento **OpenSolver** en Google Sheets o en Microsoft Excel, reproduciendo exactamente la solución óptima del motor de DORA sin requerir conexión a internet ni confiar a ciegas en el asistente: *"No nos creas: resolvelo vos"*.

---

## Archivos de ejemplo

1. **`pampas-core-2000ha.xlsx`**
   - **Caso:** Zona núcleo agrícola, 2.000 ha propias, capital inicial de 500.000 USD.
   - **Propósito:** Caso de demostración principal de Guillermo para el INTA. Muestra la rotación óptima soja/maíz/trigo-soja de segunda, financiamiento quincenal y opciones de acopio en silo bolsa y acopio comercial.
   - **Dimensiones del LP:** ~196 variables, ~181 restricciones.

2. **`se-ba-500ha.xlsx`**
   - **Caso:** Sudeste de Buenos Aires, 500 ha propias, capital inicial de 50.000 USD con rotación que incluye cebada y girasol.
   - **Propósito:** Muestra un plan con restricción de capital activo donde el crédito bancario financia la siembra de fina.

3. **`rented-300ha.xlsx`**
   - **Caso:** Zona núcleo, 300 ha 100 % alquiladas, capital propio de 30.000 USD y línea de crédito de 200.000 USD.
   - **Propósito:** Evaluación de riesgo en campos arrendados con pago de alquiler quincenal.

4. **`se-ba-rent-out.xlsx`**
   - **Caso:** Sudeste de Buenos Aires, 500 ha propias, capital de 50.000 USD con opción de ceder en alquiler parte del campo (`allow_rent_out=True`).
   - **Propósito:** Muestra la decisión endógena entre sembrar por cuenta propia o arrendar hectáreas a terceros según el costo de oportunidad del capital.

5. **`livestock-500ha.xlsx`**
   - **Caso:** Cuenca del Salado / Sudeste bonaerense, 500 ha ganaderas (cría bovina, `cow_calf`), sin cultivos agrícolas (SPEC-30).
   - **Propósito:** Optimización ganadera en cabezas de hacienda condicionada por la receptividad forrajera invernal.

6. **`iowa-400ha.xlsx`**
   - **Caso:** Corn Belt de EE.UU. (Iowa), 400 ha (aprox. 1.000 acres), rotación corn/soybean con estructura de costos ISU Ag Decision Maker y curva CBOT.
   - **Propósito:** Demostración internacional del motor en el hemisferio norte.

7. **`lp-minimo.xlsx`**
   - **Caso:** Modelo lineal mínimo de prueba de 3 variables ($x, y, z$) y 2 restricciones de desigualdad ($\le$), con solución óptima conocida $x=2.5, y=1.5, z=0$ y función objetivo $10.5$.
   - **Propósito:** Archivo liviano de diagnóstico rápido para verificar el funcionamiento de OpenSolver y los nombres definidos.

---

## Cómo abrir y re-optimizar en Google Sheets con OpenSolver

### Paso 1: Subir el archivo
1. Abre [Google Drive](https://drive.google.com) y arrastra cualquiera de los archivos `.xlsx` a tu unidad.
2. Haz doble clic en el archivo y selecciona **Abrir con Hojas de cálculo de Google**.

### Paso 2: Instalar OpenSolver (solo la primera vez)
1. En el menú superior de Google Sheets, ve a **Extensiones → Complementos → Descargar complementos**.
2. Busca `OpenSolver` (desarrollado por la Universidad de Auckland, de código abierto).
3. Haz clic en **Instalar** y concede los permisos requeridos.

### Paso 3: Cargar y resolver el modelo
1. Ve a la hoja **Modelo**.
2. En el menú superior, selecciona **Extensiones → OpenSolver → Open OpenSolver**.
3. En el panel lateral derecho de OpenSolver:
   - **Objective Cell:** Selecciona la celda del objetivo (`dora_objective` o celda `B8`). Configura **Objective Sense** en **Maximise**.
   - **Variable Cells:** Selecciona las celdas amarillas de decisión (`dora_vars` o fila 3).
   - **Constraints:**
     - Agrega las igualdades: `dora_eq_lhs = dora_eq_rhs`
     - Agrega las desigualdades: `dora_le_lhs <= dora_le_rhs`
   *(Nota: si el archivo incluye los metadatos de OpenSolver, estos campos aparecerán precargados automáticamente).*
4. Haz clic en **Solve**.
5. Observa cómo OpenSolver encuentra la solución óptima y escribe los valores directamente en las celdas amarillas de `dora_vars`. Todas las hojas vinculadas (Resumen, Plan por cultivo, Caja por quincena) se actualizarán al instante a través de las fórmulas vivas.

---

## Cómo resolver en Microsoft Excel

1. Abre el archivo `.xlsx` en Microsoft Excel.
2. Si tienes instalado **OpenSolver para Excel** o el **Solver de Excel**:
   - Los nombres del modelo (`solver_opt`, `solver_adj`, `solver_lhs*`, `solver_rhs*`) ya están definidos como nombres del libro.
   - Ve a la pestaña **Datos → Solver** (o **OpenSolver**). El modelo se cargará automáticamente con todas sus variables y restricciones.
   - Haz clic en **Resolver**.

---

## Independencia y Transparencia

El modelo dentro de la planilla es idéntico al problema que resuelve el motor de DORA:
- Los coeficientes de precios e insumos son fórmulas dinámicas vinculadas a la hoja **Supuestos**.
- Puedes cambiar un supuesto (por ejemplo, subir el precio de la soja un 20 % en la hoja Supuestos), hacer clic en **Solve** en OpenSolver, y ver cómo el plan de siembra y el flujo de fondos se adaptan exactamente igual a como lo haría DORA.
