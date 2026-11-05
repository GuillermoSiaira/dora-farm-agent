# Prompt para Antigravity: SPEC-40 (servidor MCP) y SPEC-41 (registro on-chain)

Trabajás en **`D:\projects\dora-main`** (checkout de `main`). **No toques `D:\projects\dora-hackathon`**: ahí otra sesión trabaja en la rama `spec-37-scenario-clarity`; no cambies de rama ni edites archivos en esa carpeta.

**Orden y ramas:**
1. SPEC-40 `docs/specs/SPEC-40-mcp-server.md`, en una rama `spec-40-mcp-server` creada desde `main`.
2. SPEC-41 `docs/specs/SPEC-41-onchain-plan-record.md`, en una rama `spec-41-onchain-record` creada desde `spec-40-mcp-server` cuando la 40 esté commiteada.

**Para cada spec:**
1. Leé la spec entera, incluida cualquier sección "Claude's review" al final.
2. Implementá solo lo que pide y tocá solo los archivos que nombra. La spec 40 dice que **no** se tocan `dora/engine.py`, `dora/tools.py`, `dora/verifier.py`, `dora/plan_check.py` ni `app.py`: el servidor MCP es una capa fina que reusa lo que ya existe. Si te falta algo ahí, parate y anotalo en el handoff.
3. Corré sus tests nuevos y después la suite completa (`python -m pytest -q`). Restaurá los archivos de precios: `git checkout -- dora/data/price_curves/ dora/data/basis_*.json`.
4. Escribí el handoff que pide la spec en `docs/handoff/`. Pegá la salida real de los tests y de las llamadas. No marques nada como aprobado si la salida no lo prueba.
5. Commiteá en la rama de la spec con un mensaje que empiece con `SPEC-NN implementation:`. No hagas merge a `main` y no hagas push.
6. Agregá una línea a `docs/handoff/spec-40-41-log.md` (crealo si no existe): `HH:MM SPEC-NN terminada, commit <hash>, tests <N passed / M failed>` o `HH:MM SPEC-NN bloqueada: <motivo>`.

**Referencias que la spec nombra (solo lectura, no las modifiques):**
- `D:\projects\sig-agent\mcp_server\server.py`: cómo se arma un `MCPServer` con el SDK `mcp` 2.x (ya instalado, versión 2.0.0).
- `D:\projects\euyin-agent\mcp_server\server.py`: transporte HTTP sin estado (`stateless_http`) y cómo leer headers del request.
- `infra/modal/serve_app.py`: imagen y deploy en Modal.
- `D:\projects\Abu-Oracle\specs_pending\CHAIN-C01.md` y `D:\projects\Abu-Oracle\next_app\public\.well-known\agent-registration.json`: ERC-8004 en Base.

**Límites:**
- No llamás a ningún modelo de lenguaje: ninguna de las dos specs lo necesita.
- **Modal:** podés desplegar `infra/modal/serve_mcp.py` (SPEC-40, sección 6) cuando los tests locales pasen. Generá la clave de API con `python -m mcp_server.auth new guillermo`, guardala solo en el secret de Modal y en el handoff poné el nombre, no la clave.
- **Blockchain:** solo **Base Sepolia**. Ninguna transacción en mainnet, ni de esquemas, ni de registro del agente, ni de atestaciones. Nunca uses una clave con fondos reales ni la wallet de Abu Oracle. Generá una clave nueva de Sepolia, escribí solo la dirección en el handoff y pedile a Guillermo que la fondee desde un faucet (tienen captcha: no lo intentes vos). Mientras no haya fondos, implementá y testeá todo offline y dejá la parte en vivo como pendiente.
- Las claves privadas y de API nunca van al repo, a los logs ni al handoff. `records/` va al `.gitignore`.
- Si algún test existente falla, no lo edites para que pase, salvo los que la spec nombra (en la 41, solo el test 1 de `test_spec40.py`). Listalo en el handoff.
- Si una spec dice "stop and ask in the handoff", parate en ese punto, anotalo en el handoff y en `spec-40-41-log.md`, y seguí con lo que no dependa de eso.
- Claude revisa cada rama cuando aparece su línea en `spec-40-41-log.md` y deja sus comentarios al final de la spec, en una sección "Claude's review". Si ves una de esas secciones en una spec que ya terminaste, corregila antes de seguir y anotá la corrección en el log.
