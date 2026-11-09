# Comparación: Gemini dentro de Google Sheets contra DORA (8/11/2026)

**El pedido de Guillermo a Gemini:** "problema agrícola ganadero, campo propio o a alquilar de 500 hectáreas en la zona de Pergamino, considera vender a término, empezamos lo antes posible, dime superficie por cultivo y precio sombra". Gemini le hizo un formulario (tenencia, actividades, restricciones) y Guillermo eligió campo arrendado. Gemini armó la hoja `Optimizacion_Agro`.

La planilla bajada está en `docs/ejemplos/comparaciones/gemini-sheets-pergamino-500ha-2026-11-08.xlsx`.

## Lo que hizo bien
- **Resolvió bien su propio problema.** Re-resolví su modelo con HiGHS, con sus coeficientes:
  - el óptimo es el mismo: soja 232,32 ha, maíz 25, trigo/soja 2ª 150, ganadería 80;
  - el margen bruto es el mismo: 270.063 USD;
  - los cinco precios sombra son los mismos (0; 67,12; 199,43; 85,16; 1,10).
- **Preguntó antes de armar**, con un formulario de opciones. Eso es lo que DORA todavía no hace bien: es la idea de "confirmar lo que entendí" de la nota DORA–OpenSolver.
- **Lo presentó prolijo:** tabla de márgenes, restricciones con holgura, precios sombra con una recomendación en palabras.

## Lo que está mal o falta
1. **Inventó los datos que deciden el resultado, sin avisar.** Guillermo no dio capital, ni división entre tierra agrícola y bajos, ni alquiler, ni topes de rotación. Gemini puso todo esto como si fueran datos:
   - capital de 260.000 USD;
   - 420 ha agrícolas y 80 de bajos (en Pergamino, zona núcleo, casi no hay bajos ganaderos);
   - un tope de 150 ha de trigo/soja 2ª;
   - un mínimo de 175 ha de gramíneas;
   - un alquiler de 180.000 USD.
2. **El alquiler contradice su propio rótulo.** Dice "14 qq de soja por hectárea", que con su precio de soja (305 USD/t) son 427 USD/ha, o 213.500 USD en total. Puso 180.000 USD. Con su propio dato, el margen neto baja de 90.066 a **56.564 USD**: un error de 33.500 USD que no se ve.
3. **La decisión más importante cambia de signo con el alquiler.** DORA usa el alquiler regional de Márgenes Agropecuarios (subzona maicera de la zona núcleo, junio 2026): 570 USD/ha. Con ese dato, el modelo de Gemini da una **pérdida de 14.937 USD**. Y DORA, con el mismo campo arrendado de 500 ha y 260.000 USD, **no siembra nada**: con los márgenes de junio de 2026, ningún cultivo paga ese alquiler. El valor de una hectárea propia sale en 414 USD/ha. Gemini dice "alquilá y ganás 90.000"; DORA dice "a ese precio, no alquiles". (Nota: el alquiler de 570 USD/ha es un dato que hay que confirmar; es una buena pregunta para el amigo del INTA.)
4. **No es dinámico.** Es un margen bruto anual. No hay caja por quincena, ni crédito, ni momento de venta, ni acopio. "Vender a término" quedó solo en el rótulo de los precios: no hay contratos como decisión.
5. **La planilla no se re-optimiza.** Las hectáreas (C19:F19) y los precios sombra (C34:C38) son números escritos a mano. Si se cambia un precio, el plan y los duales no se mueven. La hoja oculta `__OpenSolver__` existe, pero con `solver_num=0`: no hay ninguna restricción cargada. Gemini resolvió en otro lado y copió los números.
6. **No hay fuentes verificables.** La columna "Referencia" dice "INTA Pergamino", "Matba-Rofex", pero los números no se pueden rastrear a una consulta concreta.

## Qué cambia esto para DORA
- **Resolver un programa lineal chico ya no es el aporte.** Un modelo de frontera lo hace bien.
- **El aporte está en tres lugares:**
  - **los datos con fuente**, como el alquiler de 570 USD/ha, que da vuelta la decisión;
  - **el modelo dinámico** (caja, crédito, ventas, acopio);
  - **un resultado que se puede verificar y re-optimizar** (SPEC-45: la planilla es el mismo problema que DORA, y cambiar un supuesto mueve el plan).
- **El riesgo real de Gemini no es que resuelva mal, sino que resuelva bien un problema con datos inventados**, y lo presente con la misma seguridad. Es la misma "falla silenciosa" del E9, en otra forma.
- **Para DORA, copiar dos cosas de Gemini:** el formulario inicial de preguntas, y marcar cada dato supuesto como supuesto ("no me diste el capital; puse 260.000, ¿está bien?").

## Para el jueves
Este caso es una demo en sí mismo. Primero se muestra la planilla de Gemini. Después se pregunta "¿y si el alquiler es el de la zona?". Después se muestra DORA con la fuente del dato.

## Qué aprendimos
- **Un solver correcto con datos inventados da una respuesta equivocada con total seguridad.** Verificar la aritmética no alcanza. Hay que verificar de dónde sale cada dato.
- **En este caso, la pregunta que decide el resultado no la hizo nadie: "¿conviene alquilar a este precio?".** Un buen modelo tiene que sacar a la luz los datos de los que depende la decisión.
- **Lo que DORA tiene que aprender de Gemini es la conversación, no la optimización:** preguntar con opciones y declarar los supuestos.
