# E4: precios en vivo, y qué pasa cuando la fuente no responde (31/10/2026)

**Pregunta:** ¿los precios salen solos de las fuentes públicas (CBOT, MAGyP, dólar del BCRA) con su fecha? Si una fuente no responde, ¿DORA usa la última copia guardada y lo dice? (`docs/plan-de-pruebas.md`, E4).

**Para leer las respuestas:** [página de E2 y E4](https://claude.ai/artifact/PJYgpRFvd1UxfaHUqYB3pc) (también en [`2026-10-31-e2-e4-respuestas.html`](2026-10-31-e2-e4-respuestas.html)).

## Montaje
- **Modelo:** Muse Spark 1.3 Standard (`muse-spark-1.3`), API de Meta, con verificador.
- **Código:** commit `641e43e` más el script nuevo `eval/run_e2_e4.py` (no toca el motor). El código de precios es el de siempre: `dora/feeds.py` (`refresh`, copia guardada si la bajada falla).
- **Cómo se bloquea una fuente:** el script cambia la dirección de la fuente por un dominio que no existe (`dora-blocked.invalid`). Para que `refresh()` intente de verdad la red, el script envejece la fecha de los archivos guardados (48 h).
- **Condiciones:**
  - **Con red:** se baja cada fuente por separado y después `refresh()`.
  - **Todo bloqueado:** CBOT, MAGyP y BCRA sin respuesta.
  - **Solo MAGyP bloqueado:** sin agente, solo para ver qué hace `refresh()`.
- **Dos preguntas al agente, 3 veces en cada condición:**
  - **P1:** "¿A cuánto están hoy la soja y el maíz para un campo en Pergamino? Decime de qué fecha y de qué fuente es cada precio."
  - **P2:** "Tengo 500 ha propias en Pergamino y 500.000 USD. Con la curva de precios de hoy (futuros de Chicago más la base de MAGyP), ¿cuánto me conviene sembrar de soja y de maíz? Decime de qué fecha y de qué fuente son los precios que usaste."
- **Comandos** (desde la raíz; la clave se lee de `.env`, no se imprime):
  - `python eval/run_e2_e4.py e4 --env RUTA/.env` (P1, y las fuentes una por una)
  - `python eval/run_e2_e4.py e4curve --env RUTA/.env` (P2)
- **Horario:** 31/10, de 18:29 a 18:46 (Buenos Aires).
- **Los archivos de precios bajados no se commitean.** `refresh()` escribe sobre `dora/data/price_curves/`, que es parte del modelo congelado. Los precios del día quedaron guardados dentro de los resultados (`files` en cada condición), y los archivos del repo se restauraron.

## Resultado: las fuentes

| Fuente | Con red | Fecha del dato | Bloqueada |
|---|---|---|---|
| CBOT (Yahoo Finance, demorado) | 24 contratos (maíz 7, soja 10, trigo 7), 152 s | 31/10/2026 | 0 contratos; `refresh()` deja la copia anterior |
| MAGyP (precios FOB y FAS) | soja FOB 484 USD/t, maíz FOB 204 USD/t, 1,4 s | 30/10/2026 | error de red |
| BCRA (dólar mayorista, A 3500) | 1.537,35 ARS/USD, 17,9 s | 30/10/2026 | error de red |

- **Con red**, `refresh()` respondió `updated`. La curva argentina (CBOT más la base de MAGyP) quedó al 30/10. Base de soja: −89,82 USD/t (al 26/10 era −84,52).
- **Todo bloqueado**, `refresh()` respondió `kept_last` y dejó la copia de unos minutos antes. No se rompió nada.
- **Solo MAGyP bloqueado**, `refresh()` respondió `updated`, aunque la curva argentina no se pudo actualizar (ver "Errores encontrados").

## Resultado: las respuestas del agente

| | P1 con red | P1 bloqueado | P2 con red | P2 bloqueado |
|---|---|---|---|---|
| Respuestas | 3 | 3 | 3 | 3 |
| Verificadas | 3 | 3 | 3 | 3 |
| Con números sin respaldo en el primer borrador (corregidos) | 1 | 1 | 0 | 2 |
| Usó la curva del día (`price_curve_source`) | 0 | 0 | 3 | 3 |
| Precio que dio | jun-2026 (MAGyP, informe de márgenes) | jun-2026 | 31/10 (CBOT) + base 30/10 | 31/10 + base 30/10 |
| Dice fecha y fuente de cada precio | 3 | 3 | 3 | 3 |
| Dice que es una copia guardada | — | 0 | — | 0 |
| Tiempo por respuesta (mediana) | 19,4 s | 24,0 s | 17,7 s | 38,4 s |

- **P1: el agente no usa los precios en vivo.** Con o sin red, dio soja 327 y maíz 183 USD/t del informe de márgenes de MAGyP de junio de 2026. Las 6 veces aclaró que no es un precio de hoy, y una vez ofreció cargar una cotización con fecha. No inventó un precio del día.
- **P2: cuando se le pide la curva del día, la usa.** Las 6 veces pasó `price_curve_source: "cbot_latest"`. Dio la fuente y la fecha tal como las devuelve el motor ("CBOT futures via Yahoo Finance (delayed), as of 2026-10-31"), y dos veces también la fecha de la base de MAGyP. El plan fue el mismo las 6 veces: 250 ha de maíz y 250 de soja, valor actual 738.981 USD.
- **Ninguna respuesta dice que el precio es una copia guardada.** No es culpa del modelo: ninguna herramienta se lo dice. `refresh()` devuelve `kept_last`, pero las herramientas lo llaman y tiran el resultado. El agente solo ve la fecha (`as_of`).
- **En esta corrida, la copia guardada era de unos minutos antes**, así que la fecha era la misma con red y sin red. Con una copia vieja, el productor vería una fecha vieja, pero nadie le diría que la fuente no respondió.
- **Con todo bloqueado, cada llamada tarda más** (mediana 38 s contra 18 s): cada herramienta vuelve a intentar las fuentes antes de usar la copia.

## Errores encontrados (para arreglar; no se tocaron)
1. **"Fresco" se mide por la fecha del archivo, no por la del precio** (`dora/feeds.py`, `refresh`). Al clonar el repo o crear un worktree, los archivos tienen la fecha de hoy, y `refresh()` cree que la copia del 27/10 es de hoy: no baja nada por 24 horas. Se vio al empezar: la copia del worktree era del 27/10 y tenía fecha de archivo del 31/10. Afecta a la app desplegada recién instalada.
2. **La falla de una fuente no le llega al agente ni al productor.** `refresh()` devuelve `kept_last`, pero en `dora/tools.py` (`_validate`) se descarta. Falta una marca del tipo "dato guardado, la fuente no respondió" en el origen del precio.
3. **Si falla MAGyP o el BCRA, `refresh()` dice `updated` igual.** La curva de CBOT se actualiza y la argentina queda vieja, sin aviso: el `except: pass` del final de `refresh()` se traga el error.
4. **Etiqueta equivocada de la fuente para Pergamino.** En `dora/tools.py`, `SOURCE_MAGYP` dice "MAGyP margins report, Jun-2026, Southeast Buenos Aires" para todas las regiones argentinas. En P1, para Pergamino, el agente citó "... Southeast Buenos Aires" en 2 de 6 respuestas. Los números sí son los de la zona núcleo (`magyp_nucleo_2026-06.json`); lo que está mal es el nombre.
5. **El precio por defecto no es el del día.** Si el productor no pide la curva, DORA usa los precios del informe de junio. El agente lo dice bien, pero "los precios salen solos" solo es cierto en el observatorio y cuando el modelo elige la curva. Es una decisión de diseño para Guillermo: usar la curva del día por defecto, o dejarlo así y decirlo.

## Costo
- **Tokens** (12 + 6 respuestas del agente, sumando P1 y P2):
  - entrada: 582.111, de los cuales 508.313 en caché;
  - salida: 48.407;
  - 41 pedidos al modelo.
- **USD**, con los precios de `eval/pricing.json` (1,25 / 0,15 / 4,25 USD por millón, entrada / caché / salida): P1 0,174 USD; P2 0,201 USD. **Total 0,37 USD**, unos 0,03 USD por respuesta.
- Las bajadas de precios no cuestan: son fuentes públicas.

Salida cruda:
- [`eval/results/e4_muse-spark-1_3_20261031_212907.json`](../../eval/results/e4_muse-spark-1_3_20261031_212907.json) (P1, las fuentes una por una, solo MAGyP bloqueado)
- [`eval/results/e4curve_muse-spark-1_3_20261031_214259.json`](../../eval/results/e4curve_muse-spark-1_3_20261031_214259.json) (P2)

## Qué aprendimos
- **Que haya una fuente en vivo no quiere decir que se use.** El código baja bien CBOT, MAGyP y el BCRA, con su fecha. Pero el agente, si no se le pide, usa los precios de junio. Hay que mirar el camino entero, desde la fuente hasta la respuesta, no solo que la bajada funcione.
- **No inventar no alcanza; hay que poder decir de dónde viene.** El modelo nunca inventó un precio de hoy: cuando no lo tenía, lo dijo. Pero no puede avisar que la fuente falló si la herramienta no se lo cuenta. El verificador controla los números, no lo que falta decir.
- **Las fallas silenciosas son las peligrosas.** Tres de los cuatro errores encontrados son silencios: un `except: pass`, un estado que nadie lee y una fecha de archivo que miente. Ninguno rompe nada, por eso no los vio ningún test.
- **Probar en un lugar recién instalado encuentra errores distintos.** El problema de la fecha de los archivos apareció porque el worktree era nuevo. En la máquina de desarrollo, donde los archivos tienen su fecha real, no se ve.
