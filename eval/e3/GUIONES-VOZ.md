# E3: guiones para las notas de voz

Seis notas cortas (15 a 25 segundos cada una). Los campos y los números son inventados.

**Cómo grabar**
- Leé el guion con tu forma de hablar. Podés cambiar palabras ("lucas" en vez de "mil dólares") si los números siguen iguales. Si cambiás algo, anotalo abajo de cada guion.
- Guardá cada archivo en `eval/e3/media/voice/` con el nombre del caso: `v1.wav`, `v2.wav`, ... `v6.wav`.
- **Formato:** WAV, si se puede. La grabadora de Windows y los celulares graban m4a u ogg: esos sirven solo si está instalado ffmpeg (por ejemplo `winget install Gyan.FFmpeg`). Otra opción sin instalar nada: grabar con el micrófono en la pestaña Chat de la app, que guarda WAV.
- Después: `python eval/e3/run_e3.py --only voice --voice-dir eval/e3/media/voice`.

---

**v1.** Hola DORA, te cuento. Tengo ochocientas hectáreas propias, ciento veinte mil dólares para arrancar, y el banco me ofrece una línea de hasta doscientos mil dólares al doce por ciento anual. ¿Cuál sería el valor presente de la campaña?

**v2.** Buenas. Tengo trescientas cincuenta hectáreas y sesenta mil dólares propios. A la soja le calculo un rinde de cuatro toneladas por hectárea y un precio de trescientos treinta dólares la tonelada. ¿Qué valor presente me da?

**v3.** Mirá, tengo seiscientas hectáreas y noventa mil dólares. Por un contrato con la cooperativa tengo que sembrar por lo menos doscientas cincuenta hectáreas de soja. ¿Cómo queda el valor presente?

**v4.** Hola. Tengo cuatrocientas hectáreas y setenta mil dólares. Ya vendí trescientas toneladas de soja para mayo, a trescientos diez dólares la tonelada. ¿Cuál es el valor presente?

**v5.** Te paso los datos. Mil hectáreas, ciento cincuenta mil dólares propios. No quiero más de cuatrocientas hectáreas de maíz. Y el de los agroquímicos me financia a noventa días, con un recargo del tres por ciento. ¿Cuál es el valor presente?

**v6.** Tengo quinientas hectáreas y ochenta mil dólares, y un silo propio donde entran mil quinientas toneladas de grano. ¿Cuál es el valor presente?

---

Lo que DORA tendría que entender en cada caso está en `eval/e3/cases.json` (campo `scenario`).
