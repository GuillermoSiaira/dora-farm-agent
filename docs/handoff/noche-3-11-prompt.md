# Prompt para Antigravity: noche del 3/11

Cuando termines la SPEC-36, seguí con las otras tres, de a una y en este orden. Trabajás en `D:\projects\dora-hackathon`.

**Orden y ramas** (cada una sale de la anterior; no esperes a que se mergee nada):
1. SPEC-36 `docs/specs/SPEC-36-invoice-lines.md`, en la rama `spec-36-invoice-lines` (la que tenés ahora).
2. SPEC-38 `docs/specs/SPEC-38-owned-land-can-be-rented-out.md`, en una rama `spec-38-rent-out` creada desde `spec-36-invoice-lines` cuando esa esté commiteada.
3. SPEC-39 `docs/specs/SPEC-39-break-even-prices.md`, en una rama `spec-39-break-even-prices` creada desde `spec-38-rent-out`.
4. SPEC-37 `docs/specs/SPEC-37-scenario-dates-and-taxes.md`, en una rama `spec-37-scenario-clarity` creada desde `spec-39-break-even-prices`.

Las specs están en `main` (commit 5af9d86 o posterior). Antes de empezar cada una, traela a tu rama con `git checkout main -- docs/specs/` para tener la última versión.

**Para cada spec:**
1. Leé la spec entera, incluida cualquier sección "Claude's review" al final.
2. Implementá solo lo que pide y tocá solo los archivos que nombra.
3. Corré sus tests nuevos y después la suite completa (`python -m pytest -q`). Restaurá los archivos de precios: `git checkout -- dora/data/price_curves/ dora/data/basis_*.json`.
4. Escribí el handoff que pide la spec en `docs/handoff/`. Pegá la salida real de los tests. No marques nada como aprobado si la salida no lo prueba.
5. **Esta noche, excepción a la regla de siempre:** commiteá el trabajo en la rama de esa spec, con un mensaje que empiece con `SPEC-NN implementation:`. No hagas merge a `main`, no hagas push y no despliegues.
6. Agregá una línea a `docs/handoff/noche-3-11.md` (crealo si no existe): `HH:MM SPEC-NN terminada, commit <hash>, tests <N passed / M failed>` o `HH:MM SPEC-NN bloqueada: <motivo>`.
7. Creá la rama de la próxima spec desde esta y seguí.

**Límites:**
- No corras modelos pagos salvo lo que pide la SPEC-36 (piloto r1 primero; si el piloto falla, no corras el resto y anotalo). Las SPEC-38, 39 y 37 no llaman a ningún modelo.
- Si una spec dice "stop and ask in the handoff", parate en ese punto, anotalo en el handoff y en `noche-3-11.md`, y seguí con lo que no dependa de eso.
- Si te bloqueás en la SPEC-38, no sigas con la 39 (la necesita); anotalo y pasá a la 37 sin las partes que dependen de la 38 y la 39 (la 7 de la sección 6 y la tabla de precios).
- Si algún test existente falla, no lo edites para que pase, salvo los que la spec nombra. Listalo en el handoff.
- Claude revisa cada rama apenas aparece su línea en `noche-3-11.md` y deja sus comentarios al final de la spec, en una sección "Claude's review". Si ves una de esas secciones en una spec que ya terminaste, corregila antes de seguir con la próxima y anotá la corrección en `noche-3-11.md`.
