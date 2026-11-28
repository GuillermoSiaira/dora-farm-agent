# Instrucciones para agentes (Claude Code, Gemini en Antigravity, Codex)

**DORA** planifica la campaña agrícola. El productor describe su campaña (texto, voz, foto de una factura o un lote en el mapa). Un modelo de lenguaje arma el escenario, y un motor de programación lineal (HiGHS) decide hectáreas, ventas, almacenaje y crédito por quincena y da los precios sombra. Un verificador impide que la respuesta tenga números que no salieron del motor. Es una creación de M2M Labs: **el modelo habla, la matemática decide.**

- Repo **público**: `github.com/GuillermoSiaira/dora-farm-agent`. Carpeta principal `D:\projects\dora-hackathon`; `dora-main`, `dora-e1`, `dora-video` y `.claude/worktrees/*` son worktrees del mismo repo.
- El prototipo previo (`D:\projects\granos-optimizer`, privado) **no se copia** a este repo.
- Demo: https://guillermosiaira--dora-web.us-east.modal.run · MCP público: `https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp`

> Este archivo es corto a propósito: se carga en cada sesión. **No anotes acá bitácoras de sesión ni estados de specs.** Eso va al handoff (`docs/handoff/`), a la tarjeta del experimento (`docs/experimentos/`) o al spec.

## Cómo se trabaja
1. **Claude escribe el spec** (`docs/specs/SPEC-NN-*.md`) con tests de aceptación concretos, la lista "Touch only" y la rama.
2. **Antigravity lo implementa** en la rama del spec, en un worktree propio. Commits con el prefijo `SPEC-NN implementation:`. Al terminar escribe el handoff en `docs/handoff/`.
3. **Claude revisa**: tests, signos del motor, cuentas a mano y la demo en el navegador. Recién después se integra a `main`.
- Sin merge a `main` ni push si Guillermo no lo pide. Nunca commitear en un worktree donde otra sesión tiene una rama activa.
- La carpeta principal suele estar en una rama vieja: para algo nuevo, creá un worktree desde `origin/main`.

## Comandos
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # primera vez
.venv/Scripts/python -m pytest                 # tests (sin red; los que la usan llevan la marca `live`)
python app.py                                  # app web Gradio, http://localhost:7860
python -m mcp_server                           # MCP por stdio
MCP_TRANSPORT=streamable-http python -m mcp_server   # MCP por HTTP en $PORT (8000), con DORA_MCP_KEYS
python chat.py                                 # chat de terminal
python eval/run_eval.py --runs 3               # evaluación (--no-verifier o --baseline para los brazos B y A)
```
El venv que usa la corrida diaria es `D:\projects\dora-hackathon\.venv`. Los extras están en `requirements-dev.txt`, `requirements-geo.txt` y `requirements-chain.txt`.

**Despliegue** (solo si Guillermo lo pide): `modal deploy infra/modal/serve_app.py` (app) y `infra/modal/serve_mcp.py` (MCP). Detalle en `docs/deploy.md`.

**Automático:**
- GitHub Actions (`.github/workflows/refresh.yml`, lunes a viernes 21:30 UTC) actualiza los precios y el observatorio y commitea en `main`.
- La tarea de Windows "DORA experimento diario" corre `eval/daily/run_daily.py` desde el worktree `daily-experiments`, un experimento por día con el cupo gratis del proxy de modelos de Kaggle (cola en `eval/daily/queue.json`).

## Mapa del código
```
app.py / dora/whatsapp.py → dora/agent.py (prompt + dora/modeling_guide.md, herramientas en schemas.py)
  → dora/tools.py (valida parámetros, arma el Scenario) → dora/scenario.py (completa con dora/data/)
  → dora/engine.py optimize() (matrices, HiGHS, plan y precios sombra) → dora/verifier.py (coteja cada número)
mcp_server/   servidor MCP (auth.py, provenance.py: procedencia firmada de cada respuesta)
dora_chain/   registro del plan en cadena (Base Sepolia)
eval/         evaluación: run_eval.py, run_e9.py (otros modelos), eval/sheets/ (el modelo arma la planilla, SPEC-50), eval/daily/
infra/        modal/, kaggle/, daily/
```
- Ecuaciones, signos y la línea de código de cada una: `docs/model.md`. Recorrido para revisar la matemática: `docs/mapa-del-codigo.md`.
- Receta de modelado (Tow; Dorfman, Samuelson y Solow): `eval/sheets/data/recipe.es.md` (y `.en.md`).

## Reglas
- **El modelo nunca calcula el plan ni los precios.** Arma el escenario, llama a las herramientas y explica. Toda cuenta va al motor.
- **No inventar datos:** cada número viene de una fuente citada o queda marcado como `placeholder`. Si falta un dato del productor, se pregunta.
- SSL siempre verificado. Tests sin red, salvo los marcados `live`.
- Resultados publicados solo desde una tarjeta de experimento con su commit, comando, salida cruda y costo.
- No correr evaluaciones pagas ni con el cupo de Kaggle (cualquier runner con `--kaggle`) sin el visto bueno de Guillermo.
- Secretos solo en `.env` (ignorado por git): `DORA_API_KEY`, `WHATSAPP_*`, `KAGGLE_API_TOKEN`, `DORA_MCP_KEYS`. El repo es público.

## Foco y estrategia
- Foco vigente: `docs/plan/foco-2026-11.md`, sobre modelos especialistas en investigación de operaciones y el arnés como valor.
- Plan de M2M Labs: `docs/plan/plan-m2m-labs.md`. Nota común: `D:\second-brain\Proyectos\M2M Labs.md`.
