# E3: el productor habla o manda una foto (31/10/2026)

**Qué queríamos mostrar:** que el productor no llena un formulario. Habla, manda la foto de una factura o una foto aérea del lote, y DORA llega al mismo resultado que si lo hubiera escrito.

- **Código:** rama `claude/e3-multimodal-1f5142` (base `641e43e`), con el arreglo de voz de esta ficha.
- **Modelos (API de Meta):** Muse Spark 1.3 (Standard) con verificador; `muse-voice-transcribe-1.0` para la voz; `sam-3.1` para las fotos aéreas.
- **Casos:** `eval/e3/cases.json`. Todo inventado: campos, facturas, vendedores (CUIT 30-00000000-0) y fotos. Ningún dato de productores reales.
- **Comando:** `python eval/run_e3.py` (y `--only aerial --sam-only` para SAM solo). Cada caso corre una vez con la voz o la foto y una vez con lo mismo escrito.
- **Salida cruda:** `eval/results/e3_muse-spark-1_3_voice_invoices_aerial_20261031_190037.json` y `..._aerial_sam_20261031_184117.json`.
- **Respuestas lado a lado:** https://claude.ai/artifact/6zSiC4b2nyZrX8XYskjS1q (copia en `2026-10-31-e3-respuestas.html`).

## Antes de correr: la voz no andaba

`dora/media.py` llamaba a `/audio/transcriptions` (formato OpenAI). En la API de Meta esa ruta da 404. La de Meta es `POST /v1/asr/transcribe`, con dos partes: `request` (JSON con el modelo) y `audio` (WAV mono de 16 bits a 16 o 24 kHz; dev.meta.ai/docs/speech-to-text). Se cambió `transcribe()` y se agregó `to_asr_wav()`, que convierte cualquier WAV a ese formato. Otros formatos (m4a, ogg del celular) necesitan ffmpeg, que esta máquina no tiene: el error lo dice. Test nuevo sin red en `tests/test_multimodal.py`.

También: la app muestra en el chat lo que DORA entendió del audio (antes decía solo "[Nota de voz]"), y `chat.py` acepta `audio ARCHIVO.wav` y `foto ARCHIVO.png texto`.

## Resultados

### Voz (6 notas)
Las notas de esta corrida **no son de Guillermo**: las leyó la voz sintética de Windows (Sabina, español de México), mientras llegan las grabaciones. Una voz real, con acento rioplatense y ruido, puede salir peor.

| | Con voz | Escrito |
|---|---|---|
| Escenario armado igual al esperado | 5/6 | 5/6 |
| Mismo valor presente que escrito | 6/6 | |
| Respuesta verificada | 6/6 | 6/6 |

- La transcripción repite palabras sueltas ("trescientos trescientos treinta", "tengo tengo", "noventa noventa"). El modelo no se confundió con ninguna.
- v6 (silo de 1.500 t): con voz y escrito, el modelo usó `storage_options` (silo propio, de SPEC-20) en vez de `storage_capacity_t`, que es lo que pusimos como esperado. Es otra forma válida de decir lo mismo; el valor presente difiere del esperado (124.966 contra 122.930 USD) porque el silo de SPEC-20 trae sus costos regionales. Hay que decidir cuál es la respuesta correcta antes de usar este caso.
- En v5 el primer borrador dijo "90" (días) y el verificador lo frenó: el productor dijo "noventa", en letras, y el verificador busca cifras. Se corrigió sola en la segunda vuelta. Con voz, todos los números llegan en letras: esto va a pasar más.

### Facturas (6 imágenes)
Facturas sintéticas armadas con `eval/e3/make_media.py` (5 limpias en PNG; f6 como foto de celular: girada, con sombra y ruido). La verdad es el subtotal neto, sin IVA.

| | Con foto | Escrito |
|---|---|---|
| Importes leídos exactos, renglón por renglón | 6/6 | |
| Tomó el total con IVA en vez del neto | 0/6 | |
| Costo por hectárea cargado correcto | **6/6** | **2/6** |
| Mismo valor presente que el exacto | 6/6 | 2/6 |

La sorpresa está al revés de lo esperado: **la foto anduvo mejor que el texto.**
- Con la foto, el modelo leyó todos los importes bien, incluida la foto torcida y la de pesos (f4: 8.640.000 ARS, convertidos con el dólar del BCRA a 46,83 USD/ha).
- Con el texto ("21.000 USD para 100 ha de trigo"), el modelo pasó la superficie a `record_document` como otro renglón (`{"amount": 100, "unit": "ha"}`). La herramienta no entiende ese renglón y divide por la superficie del campo: 21.000 / 500 = 42 USD/ha en vez de 210. Pasó en f1, f5 y f6. **Las tres respuestas salieron verificadas**, porque el 42 lo devolvió una herramienta. El verificador controla de dónde sale un número, no si el escenario está bien armado.
- En f3 escrito, la herramienta propuso 22,5 USD/ha (9.000 / 400), avisó que se desviaba 67 % del promedio de la zona, y el modelo paró a preguntar. El aviso de desvío evitó un error, aunque por casualidad.
- Con la foto, el modelo esquivó el problema pasando `area_ha` = hectáreas de la factura dentro del escenario de `record_document`.

### Fotos aéreas (3 imágenes)
Fotos dibujadas por nosotros (`make_media.py`): lotes con surcos y agua en manchas irregulares con borde de barro. El agua verdadera se conoce al píxel (máscaras `a*_mask.png`). Son fáciles para SAM: sirven para controlar la cuenta, no para afirmar que SAM anda con fotos reales.

| | a1 (una mancha) | a2 (dos manchas) | a3 (14 charcos) |
|---|---|---|---|
| Agua verdadera | 10,0 % · 40,0 ha de 400 | 25,0 % · 62,5 ha de 250 | 4,0 % · 24,0 ha de 600 |
| SAM midió | 9,99 % | 25,01 % | 4,79 % |
| Coincidencia con el agua dibujada (IoU) | 0,996 | 0,997 | 0,836 |
| Hectáreas que dijo DORA | 40,0 | 62,5 | **23,9 (mal)** |
| Valor presente después: con SAM / con el agua verdadera | 73.633 / 73.621 | 25.986 / 26.005 | 124.854 / 127.054 |

- En a3, SAM marcó también el barro alrededor de los charcos: 4,8 % contra 4,0 %.
- **Error de DORA en a3:** el modelo armó el escenario con `owned_ha: 600` sin `area_ha`. `assess_field_image` usa `area_ha`, que por defecto vale 500, y respondió "23,9 ha, 4,8 % de la superficie": el 4,8 % de 500, no de 600 (serían 28,7 ha). Que 23,9 se parezca a las 24 reales es casualidad. En a1 y a2 pasó lo mismo en la primera llamada, pero el modelo vio "500 ha" y volvió a llamar con `area_ha`. Salió verificada igual.

## Costo

| Qué | Cuánto | Fuente del precio |
|---|---|---|
| Muse Spark 1.3: 27 corridas, 124 pedidos, 2,01 M tokens de entrada (1,74 M en caché), 212.000 de salida | 1,50 USD | `eval/pricing.json` |
| Voz: 84 s de audio | 0,004 USD | 0,18 USD por hora, dev.meta.ai/docs/pricing-rate-limits |
| SAM 3.1: 22 imágenes (2 conceptos por foto: 2 corridas de SAM solo y 5 llamadas del agente) | 0,06 USD | 2,50 USD cada 1.000 imágenes, misma página |
| **Total** | **~1,6 USD** | |

Tiempo: 19 minutos para todo. Por caso, con voz 16 a 31 s; con factura 51 a 122 s (el escrito 26 a 67 s); con foto aérea 34 a 73 s.

## Qué significa y qué no
- La voz funciona de punta a punta con una voz clara: mismo resultado que escrito en 6 de 6. Falta probarla con las grabaciones de Guillermo.
- Leer facturas no es el problema: el modelo leyó 6 de 6. El problema está en cómo `record_document` recibe las hectáreas.
- SAM mide bien el agua en fotos fáciles. No se puede concluir nada sobre fotos reales de campo con esto.
- Una corrida por caso. No mide cuánto varía entre repeticiones.

## Para arreglar (no se tocó acá)
1. `record_document`: aceptar las hectáreas que cubre la factura (un campo `area_ha` por renglón en el esquema, o entender el renglón con `unit: "ha"`), y avisar cuando divide por la superficie del campo.
2. `assess_field_image`: tomar la superficie de `owned_ha` (más lo arrendado) cuando no viene `area_ha`.
3. `record_document`: "agroquímicos" con tilde no se reconoce como `crop_protection` (busca "agroquim").
4. Verificador: aceptar números dichos en letras cuando vienen de una nota de voz ("noventa" = 90).
5. Decidir el esperado de v6 (silo propio: `storage_capacity_t` o `storage_options`).

## Qué aprendimos
- **Transcripción (ASR):** pasar audio a texto. El modelo de Meta devuelve el texto y nada más; los números salen en letras ("ochocientas hectáreas"). El modelo de lenguaje los entiende, pero cualquier control que busque cifras tiene que saber leer letras.
- **Formato de audio:** el WAV es un contenedor; adentro, el audio tiene canales (mono o estéreo), frecuencia de muestreo (16.000 o 24.000 muestras por segundo) y bits por muestra. Una API puede aceptar solo una combinación; convertir es remuestrear y mezclar canales.
- **Datos sintéticos con verdad conocida:** si dibujamos el agua nosotros, sabemos cuántos píxeles son agua y podemos medir el error exacto. La contra: lo dibujado es más fácil que la realidad.
- **IoU (intersección sobre unión):** cuánto se superponen dos zonas marcadas. 1 es igual; 0,84 en a3 es porque SAM sumó el barro.
- **Verificado no es correcto:** el verificador asegura que cada número sale de una herramienta. Si el modelo arma mal la entrada de la herramienta, el número sale mal y verificado igual. Por eso hace falta medir la formulación, no solo la verificación.
- **Valores por defecto peligrosos:** un parámetro que falta y toma un valor razonable (500 ha) no da error; da un resultado plausible y equivocado. Es más difícil de ver que un error.
