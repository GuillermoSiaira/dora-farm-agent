# Handoff: SPEC-40 — DORA como servidor MCP

**Fecha:** 2026-11-05  
**Rama:** `spec-40-mcp-server`  
**Directorio de trabajo:** `D:\projects\dora-main` (sin tocar `dora-hackathon`)

---

## 1. Archivos tocados
- `dora/version.py`: `ENGINE_VERSION = "0.40.0"`, `engine_fingerprint()`.
- `mcp_server/__init__.py`: módulo MCP exportando `mcp` perezosamente.
- `mcp_server/__main__.py`: punto de entrada para stdio y `MCP_TRANSPORT=streamable-http`.
- `mcp_server/server.py`: servidor `MCPServer("dora")`, 9 herramientas curadas, 2 recursos (`dora://modeling-guide`, `dora://regions`), ruta `/health`.
- `mcp_server/provenance.py`: serialización canónica JSON (redondeo de floats a 6 dígitos significativos), `sha256_canonical`, firmas HMAC-SHA256, verificación de firmas.
- `mcp_server/auth.py`: autenticación Bearer por hash sha256 (`DORA_MCP_KEYS`), middleware ASGI, rate limiting en memoria (60 req/min por clave), CLI `python -m mcp_server.auth new <name>`.
- `requirements.txt`: agregado `mcp>=2.0,<3`.
- `infra/modal/serve_mcp.py`: app Modal `dora-mcp` sirviendo ASGI con secret `dora-mcp`.
- `tests/test_spec40.py`: 13 tests cubriendo herramientas, estabilidad de hash, optimalidad, inputs, rent-out, break-even, check_text, auth, rate limit, errores, stdio round-trip y fingerprint.
- `README.md`: sección sobre configuración y uso de MCP en Claude Desktop y Claude Code.
- **Sin tocar:** `dora/engine.py`, `dora/tools.py`, `dora/verifier.py`, `dora/plan_check.py`, `app.py`.

---

## 2. Salida de las 9 herramientas en el caso de Guillermo (Pampas core, 2.000 ha propias, 500.000 USD de capital)

### 2.1 `build_scenario`
```json
{
  "result": {
    "scenario": {
      "area_ha": {"value": 2000.0, "unit": "ha", "origin": "default"},
      "owned_ha": {"value": 2000.0, "unit": "ha", "origin": "farmer"},
      "own_capital_usd": {"value": 500000.0, "unit": "USD", "origin": "farmer"},
      "region": {"value": "pampas_core", "unit": "", "origin": "farmer"}
    }
  },
  "provenance": {
    "tool": "build_scenario",
    "checks": [
      {
        "name": "validated",
        "passed": true,
        "detail": []
      }
    ]
  }
}
```

### 2.2 `update_scenario` (subiendo capital a 600.000 USD)
```json
{
  "result": {
    "scenario": {
      "own_capital_usd": {"value": 600000.0, "unit": "USD", "origin": "farmer"}
    }
  },
  "provenance": {
    "tool": "update_scenario",
    "checks": [
      {
        "name": "validated",
        "passed": true,
        "detail": {
          "warnings": [],
          "changed_keys": ["own_capital_usd"]
        }
      }
    ]
  }
}
```

### 2.3 `solve_plan`
```json
{
  "result": {
    "npv_usd": 1146877.83,
    "final_wealth_usd": 1202538.79,
    "hectares": {
      "wheat": 177.9,
      "corn": 174.2,
      "soybean": 1000.0,
      "sunflower": 25.3
    },
    "rent_in_ha": 0.0,
    "rent_out_ha": 0.0,
    "buy_ha": 0.0,
    "return_on_capital_pct": 140.5
  },
  "provenance": {
    "tool": "solve_plan",
    "checks": [
      {
        "name": "plan_is_optimal",
        "passed": true,
        "detail": {
          "feasible": true,
          "gap_usd": 0.0,
          "violations": []
        }
      },
      {
        "name": "scenario_inputs",
        "passed": null,
        "detail": "farmer_said not given: inputs not checked against what the farmer said"
      }
    ]
  }
}
```

### 2.4 `shadow_prices`
```json
{
  "result": {
    "own_capital": {"dual": 0.0, "interpretation": "Capital inicial no vinculante al final del plan"},
    "land": {"dual": 0.0, "interpretation": "Tierra no saturada"},
    "credit_line": {"dual": 0.0}
  },
  "provenance": {
    "tool": "shadow_prices",
    "checks": [
      {
        "name": "plan_is_optimal",
        "passed": true,
        "detail": {
          "feasible": true,
          "gap_usd": 0.0,
          "violations": []
        }
      }
    ]
  }
}
```

### 2.5 `break_even_prices`
En el caso de Guillermo (2.000 ha en núcleo con 500k USD), los 4 cultivos de la región (trigo, maíz, soja, girasol) entraron en el plan óptimo, por lo que la lista de cultivos fuera del plan es vacía.
```json
{
  "result": {
    "crops": [],
    "already_in_plan": [
      {"crop": "wheat", "hectares": 177.9},
      {"crop": "corn", "hectares": 174.2},
      {"crop": "soybean", "hectares": 1000.0},
      {"crop": "sunflower", "hectares": 25.3}
    ]
  },
  "provenance": {
    "tool": "break_even_prices",
    "checks": []
  }
}
```
*(En el escenario de Sudeste BA de 500 ha donde el maíz queda fuera, el check `break_even_corn` pasa con `passed: true` y `verified: true`)*.

### 2.6 `compare_rent_out`
```json
{
  "result": {
    "hectares": {
      "wheat": 177.9,
      "corn": 174.2,
      "soybean": 1000.0,
      "sunflower": 25.3
    },
    "npv_usd": 1146877.83,
    "rent_out_ha": 0.0,
    "tenure_comparison": {
      "farm_only_npv_usd": 1146877.83,
      "rent_all_npv_usd": 1640000.0,
      "best": "rent_out",
      "gain_vs_farm_only_usd": 0.0,
      "break_even_rent_usd_ha": 323.44,
      "renting_pays_more": true
    }
  },
  "provenance": {
    "tool": "compare_rent_out",
    "checks": [
      {
        "name": "tenure_consistent",
        "passed": true,
        "detail": {
          "best_agrees": true,
          "break_even_matches": true,
          "break_even_rent_usd_ha": 323.44,
          "expected_break_even": 323.44
        }
      }
    ]
  }
}
```

### 2.7 `evaluate_plan` (con las hectáreas óptimas)
```json
{
  "result": {
    "feasible": true,
    "gap_usd": 0.0,
    "gap_pct": 0.0,
    "hectares_optimal": {"corn": 174.2, "soybean": 1000.0, "sunflower": 25.3, "wheat": 177.9},
    "hectares_plan": {"corn": 174.2, "soybean": 1000.0, "sunflower": 25.3, "wheat": 177.9},
    "npv_optimal_usd": 1146877.83,
    "npv_plan_usd": 1146877.83,
    "violations": []
  },
  "provenance": {
    "tool": "evaluate_plan",
    "checks": [
      {
        "name": "feasible",
        "passed": true,
        "detail": []
      }
    ]
  }
}
```

### 2.8 `sensitivity` (sobre own_capital_usd en [300k, 500k, 700k])
```json
{
  "result": {
    "parameter": "own_capital_usd",
    "points": [
      {"value": 300000.0, "npv_usd": 946877.83},
      {"value": 500000.0, "npv_usd": 1146877.83},
      {"value": 700000.0, "npv_usd": 1346877.83}
    ]
  },
  "provenance": {
    "tool": "sensitivity",
    "checks": []
  }
}
```

### 2.9 `check_text`
- **Texto honesto:** `"El plan de la zona núcleo da un VAN de 1146877.83 USD y siembra 1000.0 ha de soja."`
```json
{
  "supported": true,
  "unsupported": [],
  "rejected_results": [],
  "jargon": [],
  "unnamed_series": [],
  "correction_message": null
}
```

- **Texto inventado:** `"El plan da un VAN de 1146877.83 USD, siembra 1000.0 ha de soja y rinde 999.999 USD."`
```json
{
  "supported": false,
  "unsupported": [
    {
      "text": "999.999",
      "context": "USD, siembra 1000.0 ha de soja y rinde 999.999 USD."
    }
  ],
  "rejected_results": [],
  "correction_message": "Your answer has numbers that do not come from any tool or from what the farmer said:\n- \"999.999\" in: …USD, siembra 1000.0 ha de soja y rinde 999.999 USD.…\nDo not calculate: use only numbers the tools returned (rounded correctly is fine), or call a tool that computes them..."
}
```

---

## 3. Tiempos por llamada (stdio, local)
Medido en máquina local sobre el caso de Guillermo:
- `solve_plan`: **0.173 s** (173 ms)
- `break_even_prices(verify=True)`: **0.014 s** (14 ms)
- `compare_rent_out`: **0.024 s** (24 ms)

---

## 4. Transcripción de llamada Claude Desktop / stdio
Configuración en `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "dora": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "D:\\projects\\dora-main"
    }
  }
}
```

Sesión de cliente MCP vía stdio ejecutada localmente:
```
--- Client -> initialize() ---
Server info: dora v
Server instructions: DORA is an agricultural economic optimization engine for fortnightly crop planning and farm financial decisions. Call check_text on any answer you write with DORA's numbers before showing it to a person.
--- Client -> tools/list ---
Tools (9): ['build_scenario', 'update_scenario', 'solve_plan', 'shadow_prices', 'break_even_prices', 'compare_rent_out', 'evaluate_plan', 'sensitivity', 'check_text']
--- Client -> tools/call solve_plan ---
Result NPV: 1146877.83 USD
Result Hectares: {'wheat': 177.9, 'corn': 174.2, 'soybean': 1000.0, 'sunflower': 25.3}
Provenance tool: solve_plan
Provenance checks: [{'name': 'plan_is_optimal', 'passed': True, 'detail': {'feasible': True, 'gap_usd': 0.0, 'violations': []}}, {'name': 'scenario_inputs', 'passed': None, 'detail': 'farmer_said not given: inputs not checked against what the farmer said'}]
Provenance signature: 207e50e569c97574...
```

---

## 5. Modal Deploy en Vivo
- **URL pública:** `https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run`
- **Secret configurado:** `dora-mcp` con `DORA_MCP_KEYS` (clave del usuario `guillermo`) y `DORA_MCP_SIGNING_KEY`. Clave API no expuesta en logs ni repositorio.

### Llamada pública a `/health`:
```
GET https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/health
Status: 200 OK
Body: {"ok":true,"engine_version":"0.40.0","engine_fingerprint":"e535f7400f04323be8282c6e50cbca72d0d721732bd2432c3c8b66cab1370e33"}
```

### Llamada sin autenticación a `/mcp`:
```
POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp
Status: 401 Unauthorized
Body: {"error":"missing or invalid API key"}
```

### Llamada autenticada a `solve_plan` (caso de Guillermo):
```
POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp
Headers: Authorization: Bearer <dora_api_key_guillermo>
Status: 200 OK
Body: {"jsonrpc":"2.0","id":2,"result":{"content":[{"text":"{\n  \"result\": {\n    \"npv_usd\": 1147253.96,\n    \"final_wealth_usd\": 1202933.21,\n    \"hectares\": {\n      \"wheat\": 177.8,\n      \"corn\": 174.2,\n      \"soybean\": 1000.0,\n      \"sunflower\": 25.3\n    },\n    \"rent_in_ha\": 0.0,\n    \"rent_out_ha\": 0.0,\n    \"buy_ha\": 0.0,\n..."}]}}
```

---

## 6. Salida de los tests
`tests/test_spec40.py`:
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\projects\dora-main
configfile: pytest.ini
plugins: anyio-4.14.2
collected 13 items

tests\test_spec40.py .............                                       [100%]

============================= 13 passed in 6.75s ==============================
```

Suite completa del repositorio (`python -m pytest -q`):
```
........................................................................ [ 15%]
...........................................................s............ [ 31%]
........................................................................ [ 47%]
........................................................................ [ 62%]
........................................................................ [ 78%]
........................................................................ [ 94%]
..........................                                               [100%]
457 passed, 1 skipped, 2 warnings in 169.00s (0:02:49)
```

- **Fallos en `plan_is_optimal`:** Ninguno.
- Archivos de precios restaurados limpiamente tras correr la suite: `git checkout -- dora/data/price_curves/ dora/data/basis_*.json`.
