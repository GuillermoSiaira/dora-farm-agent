# Prompt para Antigravity: SPEC-43 (la actualización diaria pasa a Modal)

Trabajás en **`D:\projects\dora-main`**. No toques `D:\projects\dora-hackathon`.

**Rama:** creá `spec-43-modal-refresh` desde `spec-41-onchain-record` y seguí `docs/specs/SPEC-43-modal-daily-refresh.md`. Va **antes** que la SPEC-42; la 42 después sale de esta rama.

**Pasos:** los mismos de `docs/handoff/spec-40-41-prompt.md`. Leé la spec entera y tocá solo los archivos que nombra. Corré sus tests y la suite completa, y restaurá los archivos de precios si cambiaron. Escribí el handoff con la salida real y commiteá en la rama con mensajes que empiecen `SPEC-43 implementation:`. No hagas merge ni push de la rama. Anotá la línea en `docs/handoff/spec-40-41-log.md`.

**Lo que más importa:**
- Por qué existe esta spec: la cuenta de GitHub está bloqueada por facturación, así que las Actions no corren. El workflow diario nunca llegó a commitear.
- El token de GitHub lo crea Guillermo y lo pone en `.env` como `DORA_GITHUB_PUSH_TOKEN`. Vos lo leés de ahí para crear el secret `dora-github` en Modal, **sin imprimirlo nunca**: ni en la consola, ni en logs, ni en el handoff, ni en mensajes de error (`redact`). Si no está, terminá todo con `push=False` y avisalo en el handoff.
- El job solo puede commitear los archivos de datos permitidos, nunca otra cosa, y nunca `--force`.
- La prueba en vivo con push va a la rama `refresh-smoke`, **no a `main`**. A `main` empuja solo el cron programado.
- Sin modelos pagos: el observatorio corre sin `DORA_API_KEY`, igual que en el workflow.
- Al redesplegar la app, no uses `DORA_WARM`: debe seguir escalando a cero.
