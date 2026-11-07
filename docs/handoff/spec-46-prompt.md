# Prompt para Antigravity: SPEC-46 (NDVI satelital del lote que entra al plan)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Antes de empezar:** corré `git status`. Si hay cambios sin commitear (hoy aparece `docs/handoff/spec-44-public-connector.md` modificado), no los pises: avisá y esperá.

**Rama y spec:** creá `spec-46-satellite-ndvi` desde `spec-44-public-connector`. Traé la spec y la nota de diseño desde la rama de Claude:
```
git checkout claude/satelite-dron-2bf2b7 -- docs/specs/SPEC-46-satellite-ndvi.md docs/specs/SPEC-47-drone-mission.md docs/plan/mediciones-reales-satelite-dron.md
```
Seguí `docs/specs/SPEC-46-satellite-ndvi.md`. La SPEC-47 (dron) va después, en otra rama apilada sobre esta: no la empieces ahora.

**Pasos:** los mismos de siempre. Leé la spec entera y tocá solo los archivos que nombra. Corré sus tests y la **suite completa** (0 fallados, con `dora/data` limpio y sin restaurar nada a mano). Escribí el handoff con la salida real y commiteá con mensajes que empiecen con `SPEC-46 implementation:`. Sin merge ni push. Anotá una línea en `docs/handoff/spec-40-41-log.md`.

**Lo que más importa:**
- **Costo cero.** Earth Search no pide cuenta ni clave. No uses Copernicus, Sentinel Hub ni ningún servicio pago.
- **No redespliegues `serve_app.py` ni `serve_mcp.py` antes del 10/11.** Sumá `requirements-geo.txt` a las imágenes de Modal, pero sin desplegar.
- **Regla de reflectancia (sección 1):** si la escena dice `earthsearch:boa_offset_applied: true`, la reflectancia es DN × 0,0001, sin el offset −0,1 que igual declara. Un NDVI fuera de [−1, 1] es un bug.
- **Nubes:** se miden con la clasificación SCL dentro del lote, nunca con `eo:cloud_cover` de la imagen entera.
- **El rinde propuesto es una regla y el productor lo confirma.** La herramienta nunca cambia el escenario sola. `assess_field_image` tiene que devolver exactamente lo mismo que antes, y `tests/test_field_image.py` tiene que pasar sin tocarlo.
- **Caché en D:.** `DORA_CACHE_DIR=D:\projects\tools\dora-cache` va en `.env`. Nada se guarda en `C:\Users`.
- **Prueba en vivo de la sección 8, con la salida real pegada en el handoff:** el cuadrado de lon −61,00 / lat −33,90 con fecha 2026-10-05 tiene que dar la escena del 2/10, 100 % despejada y NDVI cerca de 0,58. Si da distinto, explicá por qué.
- Ninguna clave en logs, en el handoff ni en la línea de comando.
