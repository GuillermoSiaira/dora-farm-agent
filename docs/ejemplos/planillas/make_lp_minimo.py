import sys
from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.styles import Font, PatternFill
from scipy.optimize import linprog
out = sys.argv[1]
# max 3x + 2y + 4z  s.t.  x + y + 2z <= 4 ; 2x + z <= 5 ; x, y, z >= 0
res = linprog([-3, -2, -4], A_ub=[[1, 1, 2], [2, 0, 1]], b_ub=[4, 5], method="highs")
print("optimo:", res.x.round(4), -res.fun)
wb = Workbook(); ws = wb.active; ws.title = "Modelo"
yellow = PatternFill("solid", fgColor="FFF2CC"); b = Font(bold=True)
ws["A1"] = "Variable"; ws["B1"], ws["C1"], ws["D1"] = "Trigo (ha)", "Soja (ha)", "Maíz (ha)"
ws["A2"] = "Clave"; ws["B2"], ws["C2"], ws["D2"] = "x", "y", "z"
ws["A3"] = "Valor (lo que cambia el solver)"
for c in "BCD": ws[c + "3"] = 0; ws[c + "3"].fill = yellow
ws["A6"] = "Ganancia por unidad"; ws["B6"], ws["C6"], ws["D6"] = 3, 2, 4
ws["A8"] = "Objetivo (maximizar)"; ws["B8"] = "=SUMPRODUCT(B6:D6,B3:D3)"; ws["A8"].font = b
ws["A10"] = "Restricción"; ws["E10"], ws["F10"], ws["G10"] = "Usado", "Sentido", "Límite"
ws["A11"] = "Tierra"; ws["B11"], ws["C11"], ws["D11"] = 1, 1, 2; ws["E11"] = "=SUMPRODUCT(B11:D11,$B$3:$D$3)"; ws["F11"] = "<="; ws["G11"] = 4
ws["A12"] = "Capital"; ws["B12"], ws["C12"], ws["D12"] = 2, 0, 1; ws["E12"] = "=SUMPRODUCT(B12:D12,$B$3:$D$3)"; ws["F12"] = "<="; ws["G12"] = 5
ws["A14"] = f"Óptimo conocido: objetivo = {-res.fun:g}  (x={res.x[0]:g}, y={res.x[1]:g}, z={res.x[2]:g})"
ws["A15"] = "Prueba: Extensiones → OpenSolver. ¿Aparece el modelo cargado? Si no, definilo a mano y apretá Save."
ws.column_dimensions["A"].width = 34
names = {"solver_opt": "Modelo!$B$8", "solver_typ": "1", "solver_adj": "Modelo!$B$3:$D$3",
         "solver_num": "1", "solver_lhs1": "Modelo!$E$11:$E$12", "solver_rel1": "1",
         "solver_rhs1": "Modelo!$G$11:$G$12", "solver_neg": "1", "solver_lin": "1", "solver_eng": "2", "solver_ver": "3"}
for k, v in names.items():
    wb.defined_names[k] = DefinedName(k, attr_text=v)                       # libro
    ws.defined_names[k] = DefinedName(k, attr_text=v)                       # hoja (como lo guarda Excel)
wb.save(out); print("ok", out)
