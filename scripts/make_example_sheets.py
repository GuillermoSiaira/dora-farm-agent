#!/usr/bin/env python3
"""Generate the 6 example spreadsheets and minimal LP for SPEC-45 Phase A.

Outputs written to docs/ejemplos/planillas/:
  1. pampas-core-2000ha.xlsx (Guillermo's demo case)
  2. se-ba-500ha.xlsx (Southeast Buenos Aires owned)
  3. rented-300ha.xlsx (300 ha rented with credit)
  4. se-ba-rent-out.xlsx (Southeast BA with rent out option)
  5. livestock-500ha.xlsx (Livestock SPEC-30 cow-calf)
  6. iowa-400ha.xlsx (US Corn Belt Iowa 400 ha)
  7. lp-minimo.xlsx (3-variable, 2-constraint minimal LP for step 0)
  8. README.md explaining each file and how to solve with OpenSolver.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ["DORA_OFFLINE"] = "1"

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from dora.spreadsheet import export_plan_xlsx

OUTPUT_DIR = ROOT_DIR / "docs" / "ejemplos" / "planillas"

SCENARIOS = {
    "pampas-core-2000ha.xlsx": {
        "region": "pampas_core",
        "area_ha": 2000,
        "owned_ha": 2000,
        "own_capital_usd": 500000,
    },
    "se-ba-500ha.xlsx": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
    },
    "rented-300ha.xlsx": {
        "region": "pampas_core",
        "area_ha": 300,
        "owned_ha": 0,
        "own_capital_usd": 30000,
        "credit_line_usd": 200000,
    },
    "se-ba-rent-out.xlsx": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 50000,
        "allow_rent_out": True,
    },
    "livestock-500ha.xlsx": {
        "region": "southeast_buenos_aires",
        "area_ha": 500,
        "owned_ha": 500,
        "own_capital_usd": 100000,
        "crops": [],
        "livestock": ["cow_calf"],
    },
    "iowa-400ha.xlsx": {
        "region": "iowa",
        "area_ha": 400,
        "owned_ha": 400,
        "own_capital_usd": 300000,
    },
}


def build_lp_minimo() -> openpyxl.Workbook:
    """Build lp-minimo.xlsx: 3 variables, 2 <= constraints, optimum (2.5, 1.5, 0) -> 10.5."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Modelo"

    # Styling
    var_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    hdr_fill = PatternFill(start_color="EAECEE", end_color="EAECEE", fill_type="solid")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_normal = Font(name="Calibri", size=10)

    # Box guide at top
    ws["B1"] = "x"
    ws["C1"] = "y"
    ws["D1"] = "z"
    for col in ("B", "C", "D"):
        ws[f"{col}1"].font = font_bold

    ws["B2"] = "x"
    ws["C2"] = "y"
    ws["D2"] = "z"

    # Row 3: Decision cells B3:D3 (initial 0, optimal 2.5, 1.5, 0)
    ws["A3"] = "Variables"
    ws["B3"] = 0.0
    ws["C3"] = 0.0
    ws["D3"] = 0.0
    for col in ("B", "C", "D"):
        ws[f"{col}3"].fill = var_fill
        ws[f"{col}3"].font = font_bold

    # Row 4: Lower bounds
    ws["A4"] = "Cota inferior"
    ws["B4"] = 0.0
    ws["C4"] = 0.0
    ws["D4"] = 0.0

    # Row 5: Upper bounds (blank)
    ws["A5"] = "Cota superior"

    # Row 6: Objective coefficients: 3, 2, 1
    ws["A6"] = "Coef. objetivo"
    ws["B6"] = 3.0
    ws["C6"] = 2.0
    ws["D6"] = 1.0

    # Row 8: Objective cell B8
    ws["A8"] = "Valor presente del plan (maximizar)"
    ws["B8"] = "=SUMPRODUCT(B6:D6, B3:D3)"
    ws["A8"].font = font_bold
    ws["B8"].font = font_bold

    # Row 10: Constraint headers
    ws["A10"] = "Descripción"
    ws["B10"] = "x"
    ws["C10"] = "y"
    ws["D10"] = "z"
    ws["E10"] = "LHS"
    ws["F10"] = "Rel"
    ws["G10"] = "RHS"
    for col in ("A", "B", "C", "D", "E", "F", "G"):
        ws[f"{col}10"].font = font_bold
        ws[f"{col}10"].fill = hdr_fill

    # Row 11: 2x + y + 2z <= 6.5
    ws["A11"] = "Restricción 1"
    ws["B11"] = 2.0
    ws["C11"] = 1.0
    ws["D11"] = 2.0
    ws["E11"] = "=SUMPRODUCT(B11:D11, $B$3:$D$3)"
    ws["F11"] = "<="
    ws["G11"] = 6.5

    # Row 12: x + y + 2z <= 4.0
    ws["A12"] = "Restricción 2"
    ws["B12"] = 1.0
    ws["C12"] = 1.0
    ws["D12"] = 2.0
    ws["E12"] = "=SUMPRODUCT(B12:D12, $B$3:$D$3)"
    ws["F12"] = "<="
    ws["G12"] = 4.0

    # Defined names for Excel Solver and DORA
    from openpyxl.workbook.defined_name import DefinedName
    wb.defined_names.add(DefinedName("dora_vars", attr_text="Modelo!$B$3:$D$3"))
    wb.defined_names.add(DefinedName("dora_objective", attr_text="Modelo!$B$8"))
    wb.defined_names.add(DefinedName("dora_le_lhs", attr_text="Modelo!$E$11:$E$12"))
    wb.defined_names.add(DefinedName("dora_le_rhs", attr_text="Modelo!$G$11:$G$12"))

    wb.defined_names.add(DefinedName("solver_opt", attr_text="Modelo!$B$8"))
    wb.defined_names.add(DefinedName("solver_typ", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_adj", attr_text="Modelo!$B$3:$D$3"))
    wb.defined_names.add(DefinedName("solver_neg", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_lin", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_eng", attr_text="2"))
    wb.defined_names.add(DefinedName("solver_num", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_lhs1", attr_text="Modelo!$E$11:$E$12"))
    wb.defined_names.add(DefinedName("solver_rel1", attr_text="1"))
    wb.defined_names.add(DefinedName("solver_rhs1", attr_text="Modelo!$G$11:$G$12"))

    # Add hidden __OpenSolver__ sheet
    ws_os = wb.create_sheet(title="__OpenSolver__")
    ws_os.sheet_state = "hidden"
    os_entries = [
        '="ModelSheet=Modelo!A:G"',
        '="solver_opt=Modelo!$B$8"',
        '="solver_typ=1"',
        '="solver_adj=Modelo!$B$3:$D$3"',
        '="solver_neg=1"',
        '="solver_lin=1"',
        '="solver_eng=2"',
        '="solver_num=1"',
        '="solver_lhs1=Modelo!$E$11:$E$12"',
        '="solver_rel1=1"',
        '="solver_rhs1=Modelo!$G$11:$G$12"',
        '="OpenSolver_ChosenSolver=Google"',
        '="OpenSolver_HasLoadedModel=1"',
    ]
    for r_idx, val in enumerate(os_entries, 1):
        ws_os.cell(row=r_idx, column=1, value=val)

    return wb


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating example spreadsheets in {OUTPUT_DIR}...")

    # 1-6. Example scenarios
    for filename, sc_dict in SCENARIOS.items():
        out_path = OUTPUT_DIR / filename
        print(f"  Generating {filename}...")
        data = export_plan_xlsx(sc_dict, lang="es")
        out_path.write_bytes(data)
        size_kb = len(data) / 1024
        print(f"    Saved {filename} ({size_kb:.1f} KB)")
        assert size_kb < 1000, f"File {filename} exceeds 1 MB ({size_kb:.1f} KB)"

    # 7. lp-minimo.xlsx
    min_path = OUTPUT_DIR / "lp-minimo.xlsx"
    print("  Generating lp-minimo.xlsx...")
    wb_min = build_lp_minimo()
    wb_min.save(min_path)
    print(f"    Saved lp-minimo.xlsx ({min_path.stat().st_size / 1024:.1f} KB)")

    # 8. README.md
    readme_path = OUTPUT_DIR / "README.md"
    readme_content = r"""# Planillas de ejemplo de DORA (SPEC-45)

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
"""
    readme_path.write_text(readme_content, encoding="utf-8")
    print(f"  Saved {readme_path.name}")
    print("Done! All example sheets and README generated successfully.")


if __name__ == "__main__":
    main()
