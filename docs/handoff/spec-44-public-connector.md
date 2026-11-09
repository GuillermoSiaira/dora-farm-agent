# Handoff: SPEC-44 - DORA como conector público de Claude

**Fecha:** 2026-11-06  
**Rama:** `spec-44-public-connector` (creada desde `spec-42-plan-spreadsheet`)  
**Workspace:** `D:\projects\dora-main` (sin tocar `dora-hackathon`, sin merge ni push)

---

## 1. Qué cambió

1. **Autenticación y rate limiting (`mcp_server/auth.py`):**
   - Implementados los dos niveles (tiers) en `AuthMiddleware`:
     - **Anónimo (sin header `Authorization`):** Habilitado en `/mcp` cuando `DORA_MCP_PUBLIC=1`. Límite de **20 llamadas por minuto por IP de cliente** (tomando la primera IP de `X-Forwarded-For` provista por Modal o `scope["client"][0]`) y un tope global de **2.000 llamadas anónimas por día**. Si se supera cualquiera de los límites, devuelve HTTP 429 con `{"error": "rate limit exceeded: anonymous use is limited; ask for a key at https://github.com/GuillermoSiaira/dora-farm-agent#use-dora-from-claude-cursor-or-codex"}`.
     - **Con clave válida:** Mantiene el comportamiento de SPEC-40 (60 llamadas por minuto por clave, sin tope diario).
     - **Con clave inválida:** Devuelve HTTP 401 `{"error": "missing or invalid API key"}`. Una clave incorrecta nunca se degrada silenciosamente a anónima.
     - `DORA_MCP_PUBLIC=0` o no seteada: Devuelve 401 si no hay clave (comportamiento exacto de SPEC-40).
   - El tier actual (`"anonymous"` o el nombre de la clave) se guarda en `scope["state"]["auth_tier"]` y en `current_auth_tier` (ContextVar), y se registra en logs por llamada (`logger.info`) sin loguear jamás la clave secreta.

2. **Restricciones de operaciones anónimas (`mcp_server/server.py`):**
   - `solve_plan(record=True)` y `record_outcome` exigen clave API.
   - En modo anónimo, devuelven:
     - `solve_plan(record=True)`: `{"error": "recording on-chain needs an API key", "provenance": ...}` con `provenance` marcada con `scenario_hash=None`, `result_hash=None`, `signature=None` (is_error), y la cola on-chain queda intacta.
     - `record_outcome`: `{"error": "recording on-chain needs an API key", "status": "refused", "provenance": ...}` sin encolar nada.
   - `record_status` y `verify_record` permanecen 100% abiertos en modo anónimo (para permitir verificación pública). Todas las demás herramientas de cálculo y optimización permanecen abiertas.

3. **Configuración de despliegue (`infra/modal/serve_mcp.py`):**
   - Se configuró `DORA_MCP_PUBLIC=1` en `env` de la función `@app.function` de `serve_mcp.py`.
   - Se desplegó **únicamente** `serve_mcp.py`. No se tocó `serve_app.py` ni `dora-refresh`.

4. **Documentación (`README.md`):**
   - Se agregó la sección `## Use DORA from Claude, Cursor or Codex` con instrucciones para:
     - Claude Desktop y Web (Settings → Connectors → Add custom connector con URL directa).
     - Claude Code CLI (`claude mcp add --transport http dora <URL>`).
     - Cursor (`mcp.json` con `url` y headers opcionales).
     - Información de límites anónimos y solicitud de clave mediante issue en el repositorio.
     - Ejemplo de consulta en español e inglés combinando plan, precios sombra y costo de oportunidad de alquiler (`compare_rent_out`).

5. **Suite de pruebas (`tests/test_spec44.py`):**
   - 9 tests cubriendo todos los requisitos de la spec con `TestClient` (Starlette) en modo offline.

---

## 2. Salida de tests

### Tests específicos de la SPEC-44 (`tests/test_spec44.py`):
```text
tests/test_spec44.py::test_1_public_no_header_succeeds PASSED            [ 11%]
tests/test_spec44.py::test_2_wrong_key_gives_401 PASSED                  [ 22%]
tests/test_spec44.py::test_3_public_disabled_gives_401 PASSED            [ 33%]
tests/test_spec44.py::test_4_anonymous_per_ip_limit PASSED               [ 44%]
tests/test_spec44.py::test_5_global_anonymous_daily_cap PASSED           [ 55%]
tests/test_spec44.py::test_6_solve_plan_record_key_required PASSED       [ 66%]
tests/test_spec44.py::test_7_anonymous_record_status_and_verify PASSED   [ 77%]
tests/test_spec44.py::test_8_key_never_appears_in_logs PASSED            [ 88%]
tests/test_spec44.py::test_9_clean_dora_data PASSED                      [100%]

======================== 9 passed, 1 warning in 18.67s ========================
```

### Última línea de la suite completa (`pytest -q`):
```text
511 passed, 1 skipped, 3 warnings in 261.85s (0:04:21)
```

Estado de `git status --porcelain dora/data observatory`:
```text
(vacío - 100% limpio sin restaurar nada a mano)
```

---

## 3. Chequeos en vivo en Modal (`serve_mcp.py`)

Despliegue realizado:
```text
✓ Created objects.
├── ✓ Uploaded D:\projects\dora-main\infra\modal\serve_mcp.py
├── ✓ Uploaded D:\projects\dora-main
├── ✓ Created Function mcp_app
│   └── https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run 
│       (unauthenticated)
└── ✓ Created Function drain_publisher.
✓ App deployed in 14.395s! 🎉
```

Resultados reales de los 4 chequeos ejecutados contra `https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp`:

### Chequeo 1: `curl` POST `initialize` a `/mcp` sin header → 200 OK
```bash
curl.exe -i -s -X POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-check","version":"1.0"}}}'
```
**Salida real:**
```http
HTTP/1.1 200 OK
Alt-Svc: h3=":443"; ma=2592000
Content-Length: 460
Content-Type: application/json
Date: Fri, 06 Nov 2026 15:50:00 GMT
Modal-Function-Call-Id: fc-01M6RRTXE5GJZRMKJAM1M8P2DD
Vary: accept-encoding

{"jsonrpc":"2.0","id":1,"result":{"capabilities":{"prompts":{"listChanged":false},"resources":{"listChanged":false,"subscribe":false},"tools":{"listChanged":false}},"instructions":"DORA is an agricultural economic optimization engine for fortnightly crop planning and farm financial decisions. Call check_text on any answer you write with DORA's numbers before showing it to a person.","protocolVersion":"2024-11-05","serverInfo":{"name":"dora","version":""}}}
```

---

### Chequeo 2: El mismo con Bearer incorrecto → 401 Unauthorized
```bash
curl.exe -i -s -X POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer bad_key_12345" \
  --data-binary '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl-check","version":"1.0"}}}'
```
**Salida real:**
```http
HTTP/1.1 401 Unauthorized
Alt-Svc: h3=":443"; ma=2592000
Content-Length: 38
Content-Type: application/json
Date: Fri, 06 Nov 2026 15:50:11 GMT
Modal-Function-Call-Id: fc-01M6RRV82MYQ4PKF2TGC8M6A9Z
Vary: accept-encoding

{"error":"missing or invalid API key"}
```

---

### Chequeo 3: `solve_plan` anónimo para Pampas core (500 ha propias, 100k USD) → 200 OK con `plan_is_optimal: true`
```bash
curl.exe -i -s -X POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  --data-binary '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"solve_plan","arguments":{"scenario":{"region":"pampas_core","area_ha":500,"owned_ha":500,"own_capital_usd":100000}}}}'
```
**Salida real (extracto de checks en provenance):**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "text": "{\n  \"result\": {\n    \"npv_usd\": 279146.05,\n    \"hectares\": {\n      \"wheat\": 49.3,\n      \"corn\": 105.1,\n      \"soybean\": 250.0,\n      \"sunflower\": 8.4\n    },\n    ...\n  },\n  \"provenance\": {\n    \"engine_version\": \"0.40.0\",\n    \"engine_fingerprint\": \"9b1a40c38f23436f829a3e0873b0d989a271706e6d6668dd9569f0c40edbdf9f\",\n    \"tool\": \"solve_plan\",\n    \"checks\": [\n      {\n        \"name\": \"plan_is_optimal\",\n        \"passed\": true,\n        \"detail\": {\n          \"feasible\": true,\n          \"gap_usd\": -0.0,\n          \"violations\": []\n        }\n      },\n      {\n        \"name\": \"scenario_inputs\",\n        \"passed\": null,\n        \"detail\": \"farmer_said not given: inputs not checked against what the farmer said\"\n      }\n    ],\n    \"signature\": \"dd205771223832193ac0fc104cc3a74a7688080c1d6a3577d1672a843e819999\"\n  }\n}",
        "type": "text"
      }
    ],
    "isError": false
  }
}
```

---

### Chequeo 4: `solve_plan` anónimo con `record=True` → error "needs an API key"
```bash
curl.exe -i -s -X POST https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  --data-binary '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"solve_plan","arguments":{"scenario":{"region":"pampas_core","area_ha":500,"owned_ha":500,"own_capital_usd":100000},"record":true}}}'
```
**Salida real:**
```http
HTTP/1.1 200 OK
Alt-Svc: h3=":443"; ma=2592000
Content-Length: 544
Content-Type: application/json
Date: Fri, 06 Nov 2026 15:50:27 GMT
Modal-Function-Call-Id: fc-01M6RRVR3VAVW1N2CQCSB1AG6G
Vary: accept-encoding

{"jsonrpc":"2.0","id":3,"result":{"content":[{"text":"{\n  \"error\": \"recording on-chain needs an API key\",\n  \"provenance\": {\n    \"engine_version\": \"0.40.0\",\n    \"engine_fingerprint\": \"9b1a40c38f23436f829a3e0873b0d989a271706e6d6668dd9569f0c40edbdf9f\",\n    \"tool\": \"solve_plan\",\n    \"scenario_hash\": null,\n    \"result_hash\": null,\n    \"solver\": \"HiGHS (scipy.optimize.linprog)\",\n    \"checks\": [],\n    \"issued_at\": \"2026-11-06T15:50:27Z\",\n    \"signature\": null\n  }\n}","type":"text"}],"isError":false}}
```

---

## 4. Pasos para Guillermo: Agregar DORA como conector en Claude

Para conectar DORA a Claude sin necesitar clave:
1. Abrir **Claude** (desktop o web en https://claude.ai).
2. Ir a **Settings** (o Configuración) → **Connectors** (Conectores).
3. Seleccionar **Add custom connector** (Agregar conector personalizado).
4. Completar los campos:
   - **Name:** `DORA`
   - **URL:** `https://guillermosiaira--dora-mcp-mcp-app.us-east.modal.run/mcp`
5. Guardar el conector. Listo: las 12 herramientas de planificación, optimización, verificación de texto y planilla quedan inmediatamente disponibles para Claude.
6. **Limpieza del Claude Desktop:** Para evitar tener dos servidores DORA en simultáneo, podés remover la entrada `"dora"` en tu `claude_desktop_config.json` que apuntaba a `mcp-remote`.
