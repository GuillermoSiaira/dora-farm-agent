"""Human audit tool for linear programming spreadsheet formulation (SPEC-50).

Generates static HTML audit pages (<out>/audit.html) where an auditor (e.g. Guillermo)
reviews a sampled set of 6 formulations per run (2 passed, 2 failed, 2 invented/incomplete).
The page runs entirely in the browser with no server, exporting verdicts to audit.jsonl.

Also provides `audit.py --agreement` to compare human verdicts with automatic grader verdicts.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from eval.sheets.grader import grade_sheet, parse_variables_list
from eval.sheets.render import render_sheet_to_xlsx


def sample_audit_items(items: list[dict[str, Any]], sample_size: int = 6, seed: int = 42) -> list[dict[str, Any]]:
    """Sample answers for audit: 2 passed, 2 failed, and 2 invented or incomplete."""
    rng = random.Random(seed)

    passed = []
    failed = []
    invented_or_incomplete = []

    for item in items:
        res = item.get("grade_result", {})
        prob = item.get("problem", {})
        is_inv = len(res.get("invented_numbers", [])) > 0
        is_inc = bool(prob.get("incomplete"))
        is_solved = bool(res.get("solved") or res.get("handled"))

        if is_inv or is_inc:
            invented_or_incomplete.append(item)
        elif is_solved:
            passed.append(item)
        else:
            failed.append(item)

    rng.shuffle(passed)
    rng.shuffle(failed)
    rng.shuffle(invented_or_incomplete)

    target_per_cat = max(1, sample_size // 3)
    sample = []
    sample.extend(passed[:target_per_cat])
    sample.extend(failed[:target_per_cat])
    sample.extend(invented_or_incomplete[:target_per_cat])

    # Fill remaining from anything not already sampled
    sampled_ids = {id(it) for it in sample}
    remaining = [it for it in items if id(it) not in sampled_ids]
    rng.shuffle(remaining)
    while len(sample) < sample_size and remaining:
        sample.append(remaining.pop())

    return sample


def _cells_to_grid(cells: dict[str, Any], variables: set[str]) -> list[list[dict[str, Any]]]:
    """Convert a sparse dictionary of cells like {'B2': 10, 'F10': '=...'} into a 2D table grid."""
    import re
    coords = []
    for ref, val in cells.items():
        m = re.match(r"^([A-Z]+)([0-9]+)$", str(ref).strip().upper())
        if m:
            col_letters, row_str = m.groups()
            # Convert col_letters to 0-indexed int
            col_idx = 0
            for char in col_letters:
                col_idx = col_idx * 26 + (ord(char) - ord("A") + 1)
            coords.append((col_idx, int(row_str), ref.upper(), val))

    if not coords:
        return []

    min_col = min(c[0] for c in coords)
    max_col = max(c[0] for c in coords)
    min_row = min(c[1] for c in coords)
    max_row = max(c[1] for c in coords)

    # Limit max grid display to reasonable dimensions
    max_col = min(max_col, min_col + 15)
    max_row = min(max_row, min_row + 25)

    def col_name(n: int) -> str:
        s = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    grid = []
    header_row = [{"ref": "", "val": "", "is_var": False, "is_header": True}]
    for c in range(min_col, max_col + 1):
        header_row.append({"ref": col_name(c), "val": col_name(c), "is_var": False, "is_header": True})
    grid.append(header_row)

    cells_by_coord = {(c[0], c[1]): (c[2], c[3]) for c in coords}

    for r in range(min_row, max_row + 1):
        row = [{"ref": str(r), "val": str(r), "is_var": False, "is_header": True}]
        for c in range(min_col, max_col + 1):
            coord = (c, r)
            if coord in cells_by_coord:
                ref_name, val = cells_by_coord[coord]
                row.append({
                    "ref": ref_name,
                    "val": val,
                    "is_var": ref_name in variables,
                    "is_header": False,
                })
            else:
                row.append({"ref": "", "val": "", "is_var": False, "is_header": False})
        grid.append(row)

    return grid


def generate_audit_html(
    items: list[dict[str, Any]],
    output_path: str | Path,
    title: str = "Auditoría Humana de Modelado en Planillas (SPEC-50)",
) -> Path:
    """Generate static HTML audit page for the sampled items."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    cards_html = []
    for idx, item in enumerate(items, 1):
        prob = item.get("problem", {})
        pid = item.get("id") or prob.get("id", f"p_{idx}")
        p_title = prob.get("title", "")
        statement = prob.get("statement_es") or prob.get("statement_en", "")

        sheet = item.get("parsed_sheet") or {}
        cells = sheet.get("cells", {})
        variables = set(parse_variables_list(sheet.get("variables", "")))
        objective = sheet.get("objective", {})
        constraints = sheet.get("constraints", [])

        grade = item.get("grade_result", {})
        status = grade.get("status", "unknown")
        solved = grade.get("solved", False)
        handled = grade.get("handled", False)
        obj_val = grade.get("objective")
        invented = grade.get("invented_numbers", [])
        missing_nonneg = grade.get("missing_nonneg", False)
        error = grade.get("error")

        xlsx_rel = item.get("xlsx_rel_path", "")

        grid = _cells_to_grid(cells, variables)
        grid_rows_html = []
        for r_data in grid:
            cells_td = []
            for c_info in r_data:
                if c_info["is_header"]:
                    cells_td.append(f'<th class="hdr">{c_info["val"]}</th>')
                else:
                    v_class = "var-cell" if c_info["is_var"] else "norm-cell"
                    val_str = str(c_info["val"])
                    val_esc = val_str.replace("<", "&lt;").replace(">", "&gt;")
                    title_attr = f'title="{c_info["ref"]}: {val_esc}"'
                    cells_td.append(f'<td class="{v_class}" {title_attr}>{val_esc}</td>')
            grid_rows_html.append("<tr>" + "".join(cells_td) + "</tr>")
        grid_table = f'<div class="grid-wrap"><table class="sheet-grid">{"".join(grid_rows_html)}</table></div>' if grid_rows_html else '<p><em>Sin celdas</em></p>'

        con_rows = []
        for c in constraints:
            if isinstance(c, dict):
                con_rows.append(f'<tr><td><code>{c.get("lhs")}</code></td><td>{c.get("op")}</td><td><code>{c.get("rhs")}</code></td></tr>')
        con_table = f'<table class="con-table"><tr><th>LHS</th><th>Op</th><th>RHS</th></tr>{"".join(con_rows)}</table>' if con_rows else '<p><em>Sin restricciones</em></p>'

        badge_class = "badge-success" if (solved or handled) else "badge-danger"
        badge_text = "RESUELTO" if solved else "MANEJADO" if handled else "NO RESUELTO"

        xlsx_link = f'<a href="{xlsx_rel}" download class="btn-xlsx">Descargar .xlsx</a>' if xlsx_rel else ''

        card = f"""
        <div class="audit-card" data-idx="{idx}" data-pid="{pid}">
          <div class="card-header">
            <div class="card-title">
              <span class="pid">{pid}</span> {p_title}
              <span class="badge {badge_class}">{badge_text}</span>
            </div>
            {xlsx_link}
          </div>

          <div class="card-body">
            <div class="section-title">Enunciado</div>
            <div class="statement-box">{statement}</div>

            <div class="columns-wrap">
              <div class="col-left">
                <div class="section-title">Planilla Formulada</div>
                {grid_table}
                <div class="solver-summary">
                  <strong>Objetivo:</strong> <code>{objective.get("cell")}</code> ({objective.get("sense")}) |
                  <strong>Variables:</strong> <code>{sheet.get("variables")}</code>
                </div>
                <div class="section-title" style="margin-top:12px;">Restricciones</div>
                {con_table}
              </div>

              <div class="col-right">
                <div class="section-title">Dictamen del Corrector Automático</div>
                <div class="grader-box">
                  <div class="grader-row"><strong>Estado HiGHS:</strong> <span>{status}</span></div>
                  <div class="grader-row"><strong>Valor Objetivo:</strong> <span>{obj_val}</span></div>
                  <div class="grader-row"><strong>Falta no negatividad:</strong> <span>{"SÍ" if missing_nonneg else "NO"}</span></div>
                  <div class="grader-row"><strong>Números inventados:</strong> <span>{", ".join(map(str, invented)) if invented else "Ninguno"}</span></div>
                  {f'<div class="grader-row error-row"><strong>Error:</strong> <span>{error}</span></div>' if error else ''}
                </div>

                <div class="section-title" style="margin-top:16px;">Veredicto de Auditoría Humana (Guillermo)</div>
                <div class="audit-actions">
                  <label class="btn-verdict btn-correct">
                    <input type="radio" name="verdict_{idx}" value="correcto"> Correcto
                  </label>
                  <label class="btn-verdict btn-incorrect">
                    <input type="radio" name="verdict_{idx}" value="incorrecto"> Incorrecto
                  </label>
                  <label class="btn-verdict btn-doubt">
                    <input type="radio" name="verdict_{idx}" value="dudoso"> Dudoso
                  </label>
                </div>
                <div style="margin-top:10px;">
                  <textarea class="audit-notes" name="notes_{idx}" placeholder="Observaciones o notas sobre la formulación..."></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>
        """
        cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: #f8fafc;
      color: #0f172a;
      margin: 0;
      padding: 24px;
    }}
    .top-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: white;
      padding: 16px 24px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      margin-bottom: 24px;
      position: sticky;
      top: 12px;
      z-index: 100;
    }}
    h1 {{ margin: 0; font-size: 20px; font-weight: 700; color: #1e293b; }}
    .btn-export {{
      background: #2563eb;
      color: white;
      border: none;
      padding: 10px 18px;
      border-radius: 6px;
      font-weight: 600;
      cursor: pointer;
      font-size: 14px;
    }}
    .btn-export:hover {{ background: #1d4ed8; }}
    .audit-card {{
      background: white;
      border-radius: 8px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
      margin-bottom: 24px;
      border: 1px solid #e2e8f0;
    }}
    .card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #f1f5f9;
      padding: 12px 20px;
      border-top-left-radius: 8px;
      border-top-right-radius: 8px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .card-title {{ font-size: 16px; font-weight: 600; display: flex; align-items: center; gap: 8px; }}
    .pid {{ background: #0f172a; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; font-family: monospace; }}
    .badge {{ font-size: 12px; padding: 3px 8px; border-radius: 12px; font-weight: 600; }}
    .badge-success {{ background: #dcfce7; color: #166534; }}
    .badge-danger {{ background: #fee2e2; color: #991b1b; }}
    .btn-xlsx {{
      background: #107c41;
      color: white;
      text-decoration: none;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 600;
    }}
    .card-body {{ padding: 20px; }}
    .section-title {{ font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 8px; }}
    .statement-box {{
      background: #f8fafc;
      border-left: 4px solid #3b82f6;
      padding: 12px 16px;
      border-radius: 0 4px 4px 0;
      margin-bottom: 16px;
      font-size: 14px;
      line-height: 1.5;
    }}
    .columns-wrap {{ display: flex; gap: 20px; }}
    .col-left {{ flex: 1.3; overflow: hidden; }}
    .col-right {{ flex: 0.9; }}
    .grid-wrap {{
      max-height: 280px;
      overflow: auto;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      margin-bottom: 10px;
    }}
    .sheet-grid {{
      border-collapse: collapse;
      font-size: 12px;
      font-family: monospace;
      width: 100%;
    }}
    .sheet-grid th.hdr {{
      background: #e2e8f0;
      color: #475569;
      padding: 4px 8px;
      border: 1px solid #cbd5e1;
      text-align: center;
      position: sticky;
      top: 0;
    }}
    .sheet-grid td {{
      padding: 4px 8px;
      border: 1px solid #cbd5e1;
      white-space: nowrap;
      text-overflow: ellipsis;
      max-width: 150px;
      overflow: hidden;
    }}
    .sheet-grid td.var-cell {{ background: #d9ead3; font-weight: bold; }}
    .solver-summary {{ font-size: 13px; color: #334155; margin-bottom: 8px; }}
    .con-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      border: 1px solid #e2e8f0;
    }}
    .con-table th, .con-table td {{
      padding: 6px 10px;
      border: 1px solid #e2e8f0;
      text-align: left;
    }}
    .con-table th {{ background: #f8fafc; color: #64748b; }}
    .grader-box {{
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 12px;
      font-size: 13px;
    }}
    .grader-row {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
    .error-row {{ color: #dc2626; }}
    .audit-actions {{
      display: flex;
      gap: 10px;
      margin-top: 8px;
    }}
    .btn-verdict {{
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 10px;
      border-radius: 6px;
      border: 2px solid #cbd5e1;
      cursor: pointer;
      font-weight: 600;
      font-size: 13px;
      user-select: none;
    }}
    .btn-correct:has(input:checked) {{ background: #dcfce7; border-color: #22c55e; color: #15803d; }}
    .btn-incorrect:has(input:checked) {{ background: #fee2e2; border-color: #ef4444; color: #b91c1c; }}
    .btn-doubt:has(input:checked) {{ background: #fef3c7; border-color: #f59e0b; color: #b45309; }}
    .audit-notes {{
      width: 100%;
      box-sizing: border-box;
      height: 70px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 8px;
      font-family: inherit;
      font-size: 13px;
      resize: vertical;
    }}
  </style>
</head>
<body>
  <div class="top-bar">
    <div>
      <h1>{title}</h1>
      <span style="font-size: 13px; color: #64748b;">Muestra de auditoría (6 casos seleccionados)</span>
    </div>
    <button class="btn-export" onclick="exportAuditJsonl()">Descargar Dictámenes (audit.jsonl)</button>
  </div>

  <div class="container">
    {"".join(cards_html)}
  </div>

  <script>
    function exportAuditJsonl() {{
      const cards = document.querySelectorAll('.audit-card');
      const lines = [];
      cards.forEach(card => {{
        const pid = card.getAttribute('data-pid');
        const idx = card.getAttribute('data-idx');
        const checkedRadio = card.querySelector(`input[name="verdict_${{idx}}"]:checked`);
        const verdict = checkedRadio ? checkedRadio.value : 'sin_revisar';
        const notes = card.querySelector(`textarea[name="notes_${{idx}}"]`).value;
        lines.push(JSON.stringify({{
          problem_id: pid,
          verdict: verdict,
          notes: notes,
          audited_at: new Date().toISOString()
        }}));
      }});
      const blob = new Blob([lines.join('\\n') + '\\n'], {{ type: 'application/jsonl' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit.jsonl';
      a.click();
      URL.revokeObjectURL(url);
    }}
  </script>
</body>
</html>"""
    out.write_text(html_content, encoding="utf-8")
    return out


def report_agreement(audit_jsonl_path: str | Path, results_path: str | Path | None = None) -> dict[str, Any]:
    """Compute agreement between human auditor and automated grader."""
    p_audit = Path(audit_jsonl_path)
    if not p_audit.exists():
        print(f"Audit file {p_audit} does not exist.")
        return {"total": 0, "agreement_rate": None, "disagreements": []}

    audits = {}
    for line in p_audit.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rec = json.loads(line)
            audits[rec.get("problem_id")] = rec

    # Load grader verdicts if results path is provided
    grader_verdicts = {}
    if results_path is not None and Path(results_path).exists():
        r_data = json.loads(Path(results_path).read_text(encoding="utf-8"))
        # Can be run results dict or list
        items = r_data if isinstance(r_data, list) else r_data.get("detailed_results", [r_data])[0]
        for it in items:
            pid = it.get("id") or it.get("problem", {}).get("id")
            if pid:
                grader_verdicts[pid] = bool(it.get("grade_result", {}).get("solved"))

    agreed = 0
    disagreed = 0
    disagreements = []

    for pid, a_rec in audits.items():
        h_verdict = a_rec.get("verdict")
        # Map human verdict to bool
        if h_verdict == "correcto":
            h_bool = True
        elif h_verdict == "incorrecto":
            h_bool = False
        else:
            h_bool = None  # dudoso or sin_revisar

        g_bool = grader_verdicts.get(pid)
        if g_bool is not None and h_bool is not None:
            if h_bool == g_bool:
                agreed += 1
            else:
                disagreed += 1
                disagreements.append({
                    "problem_id": pid,
                    "human_verdict": h_verdict,
                    "grader_solved": g_bool,
                    "notes": a_rec.get("notes"),
                })

    total = agreed + disagreed
    rate = (agreed / total) if total > 0 else None
    print(f"Agreement: {f'{rate:.1%}' if rate is not None else 'N/A'} ({agreed}/{total})")
    if disagreements:
        print("\nDisagreements:")
        for d in disagreements:
            print(f"  - {d['problem_id']}: Human={d['human_verdict']} vs Grader={d['grader_solved']}. Notes: {d['notes']}")

    return {
        "total": total,
        "agreed": agreed,
        "disagreed": disagreed,
        "agreement_rate": rate,
        "disagreements": disagreements,
    }


def build_sample_audit_html(fixtures_dir: Path | str = "tests/fixtures/spec50", output_html: Path | str = "eval/sheets/data/audit.html") -> Path:
    """Build sample audit.html from test fixtures so Guillermo sees the page."""
    from eval.sheets import load_problems, grade_sheet
    fdir = Path(fixtures_dir)
    out_p = Path(output_html)
    probs = {p["id"]: p for p in load_problems()}

    items = []
    xlsx_dir = out_p.parent / "sample_xlsx"
    xlsx_dir.mkdir(parents=True, exist_ok=True)

    for pid in sorted(probs.keys()):
        fpath = fdir / f"{pid}.json"
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        res = grade_sheet(data, problem=probs[pid])
        xlsx_file = xlsx_dir / f"{pid}.xlsx"
        render_sheet_to_xlsx(data, xlsx_file, grade_result=res)

        items.append({
            "id": pid,
            "problem": probs[pid],
            "parsed_sheet": data,
            "grade_result": res,
            "xlsx_rel_path": f"sample_xlsx/{pid}.xlsx",
        })

    sampled = sample_audit_items(items, sample_size=6, seed=42)
    return generate_audit_html(sampled, out_p, title="Auditoría Humana de Modelado en Planillas — Muestra de Fixtures")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--agreement", action="store_true", help="Report agreement between grader and human audit")
    p.add_argument("--audit-jsonl", default="eval/sheets/data/audit.jsonl")
    p.add_argument("--results", default=None, help="Path to run results JSON to compare with audit")
    p.add_argument("--sample-from-fixtures", action="store_true", help="Generate sample audit.html from test fixtures")
    p.add_argument("--out", default="eval/sheets/data/audit.html")
    a = p.parse_args()

    if a.agreement:
        report_agreement(a.audit_jsonl, results_path=a.results)
    elif a.sample_from_fixtures:
        out_file = build_sample_audit_html(output_html=a.out)
        print(f"Sample audit HTML generated at: {out_file}")
    else:
        out_file = build_sample_audit_html(output_html=a.out)
        print(f"Audit page generated at: {out_file}")


if __name__ == "__main__":
    main()

