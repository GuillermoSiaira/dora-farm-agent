# Plan para subir a main lo que quedó afuera durante el hackathon (9/11)

Ya hecho, solo en local, sin subir nada:
- Etiqueta `hackathon-submission` en 6dc9fd6, la versión entregada el 4/11.
- Worktree `.claude/worktrees/merge-post-hackathon` con la rama `merge-post-hackathon`, que es `origin/main` más la tanda 1.

**Importante:** subir a `main` no cambia la app online. La app se publica a mano con `modal deploy infra/modal/serve_app.py`, como dice `docs/deploy.md`. El push solo actualiza el repo público `GuillermoSiaira/dora-farm-agent`, aunque el refresco diario de GitHub Actions corre sobre `main`.

## Cómo están armadas las ramas
- **Línea de la app**, una sola cadena: 40 → 41 → 43 → 42 → 44 → 46 → 45 → 49. La rama `spec-49-price-risk` contiene todas. Es la que está abierta en `D:\projects\dora-main`.
- **Línea de investigación**, que sale de la 43: e9-model-size → keen-wilson (este worktree) y spec-50 → spec-51 y daily-experiments.
- **Sueltas**, de un commit o de documentos: spec-37 (`hackatones-2026-27.md`), e1-pilot (arreglo del esquema de herramientas para Muse Spark), spec-27-answers (ya tiene rama propia en origin) y satelite-dron (specs 45, 46 y 47 y las decisiones del 7/11).

Probé con `git merge-tree` y todas se mergean sin conflictos contra `origin/main` y entre sí.

## Tandas
0. **Subir la etiqueta:** `git push origin hackathon-submission`. Si el jurado mira el repo, queda fija la versión entregada.
1. **La app (SPEC-40 a 49):** `spec-49-price-risk` ya está mergeada en `merge-post-hackathon` (fc34e22: 90 archivos, unas 16.600 líneas). El 9/11 pasó la suite completa (553 passed, 1 skipped). En el diff solo aparecen claves falsas de tests (`0xabcdef…`, `ghp_1234…`, `github_pat_11ABCXYZ987`). Lo que falta es el push.
2. **Las sueltas:** spec-37, e1-pilot, spec-27-answers y satelite-dron. Son documentos y un arreglo de dos líneas.
3. **La investigación:** keen-wilson, que trae la e9, el material DSS y las specs 50 y 51, más spec-50 y daily-experiments. spec-51 entra cuando termine el commit 2.
4. **Publicar la app online:** después de la prueba manual de la planilla del miércoles 11/11, `modal deploy`. Es aparte del push.

## Lo que no se sube
- `dora/data/basis_argentina.json` ni `dora/data/price_curves/*.json` con cambios locales: eso lo actualiza el bot. Nunca usar `git commit -a`.
- `material-privado/`, que está en el gitignore.
- Los resultados sin commitear de la carpeta principal (`eval/results/*.json`, `docs/video/`) se revisan uno por uno antes de subir algo.
