# Revisión de Claude: SPEC-45, fase A (8/11/2026)

Rama `spec-45-spreadsheet-v2` en dora-main, commits `d1e49a0`, `22fb470` y `35d3fda`, sobre `04d2646`. La revisión leyó el diff y corrió chequeos propios con `DORA_OFFLINE=1`. `dora/data` quedó limpio después.

**Veredicto: aprobada para la prueba del miércoles 11, con cambios pedidos antes del merge.** El fondo está bien: la planilla es el mismo problema que resuelve DORA. Lo que falta son tests que no cubren todo lo pedido y un bloque de precios sombra que hoy confundiría a un economista. Ese bloque (punto 1) conviene arreglarlo antes del jueves 12.

## Lo que está bien (verificado, no solo leído)
- **El motor no cambió en lo matemático.** El diff de `dora/engine.py` agrega etiquetas, `LPModel` y `keep_lp`. El renombre de `y, m` a `y_m, m_m` en el bucle de contratos evita pisar la variable `m` de acopio; no cambia resultados. La suite pasa.
- **A5 se hizo bien.** `_solve_highs_from_workbook_eval` arma las matrices desde las celdas evaluadas por `formulas` y resuelve con `linprog`, sin `dora.engine`. Toma de `lp` solo las dimensiones y `obj_constant` (0 en pampas_core). Lo repetí con soja +20 %: el VNP difiere en 0,001 USD y la decisión en 0,0012 como máximo.
- **A11:** la Caja (saldo, deuda, crédito tomado) sigue a `dora_vars` quincena por quincena. Plan por cultivo también.
- **A12:** los chequeos verde/rojo y el resumen funcionan. El test rompe la línea de crédito y aparece en rojo.
- **A4:** OpenSolver para Google Sheets guarda el modelo en una hoja oculta `__OpenSolver__` (`src/modelStorage.gs`), y la planilla la trae precargada. Que Google Sheets la conserve al subir el `.xlsx` es justo lo que se prueba el miércoles.
- **Los precios sombra tienen sentido económico.** En pampas_core (2.000 ha propias, 500.000 USD):
  - el dual de la caja va de 1,548 en mayo a 0,954 al final, que es el factor de descuento;
  - 1,548 − 1 = 0,548, que es el precio sombra del capital propio;
  - el crédito ata en las quincenas 14, 18 y 20.

## Cambios pedidos

1. **El bloque de precios sombra en Resumen (antes del jueves).**
   - **Mezcla bruto con neto.** "Un dólar más en la quincena 1 vale 1,5478 USD" incluye el dólar mismo. En cambio, "un dólar más de capital inicial vale 0,5478" es la ganancia neta. Hay que decirlo igual en todas las filas: "cada dólar extra en la quincena 1 termina valiendo 1,55 USD de hoy (gana 0,55)".
   - **Es largo.** Son 21 filas de capital por quincena, y el pedido decía "bloque corto". Que muestre de 3 a 5 recursos que atan, ordenados por valor, con un rango para la caja ("entre mayo y diciembre, cada dólar gana entre 0,51 y 0,55"). Las 30 filas van en Modelo y en Sensibilidad.
   - **La tierra va a confundir.** Dice "una hectárea más de tierra propia vale 105,79 USD/ha", pero el plan deja **624 ha sin sembrar** (siembra 1.376 de 2.000). El número es correcto: sale de `raw_land_sp` en `engine.py:1385`, y una hectárea más sube el tope de rotación de la soja en 0,5 ha (dual de `rot_soybean` 211,58 × 0,5). Pero así escrito parece que falta tierra. Tiene que decir: "la tierra sobra (624 ha sin sembrar, porque el capital no alcanza); una hectárea más vale 105,79 solo porque sube el tope de soja de la rotación". Y la rotación de soja tiene que aparecer como recurso propio.
2. **A5: comparar también las decisiones en los escenarios editados.** El test 5 solo compara el VNP; el pedido decía "hectáreas y ventas dentro de 0,01". Hay que agregar `max|x_highs − x_dora| < 0,01` en las tres ediciones. Yo lo medí en soja +20 % y da 0,0012, así que debería pasar.
3. **A11: faltan Estrategia de venta y el crédito cancelado.** El pedido decía "lo mismo con Plan por cultivo y Estrategia de venta". Hay que agregar la comparación de las ventas por quincena y canal y del stock en silo contra DORA, y la de la columna M (crédito cancelado).
4. **A13: comparar contra lo que ya publica DORA, no solo contra el arreglo nuevo.** El test compara la hoja con `res.lp.duals_*`, que se calculan en el mismo commit. Hay que agregar al menos tres cruces:
   - dual de `cash_p0` − 1 = `capital_shadow_price`;
   - duales `credit_p*` = `credit_shadow_price` (con el factor de impuesto si corresponde);
   - el texto de la tierra = `land_shadow_price`.

   Además, en la fila 7 de Modelo hay que aclarar el signo del costo reducido: `lower.marginals` va sin cambio de signo, mientras que los duales se cambian de signo. Por ejemplo: "USD de VNP que se pierden por cada unidad que se fuerza".
5. **`mcp_server/server.py` quedó fuera del pedido.** Se borró el parche que, con `DORA_OFFLINE=1`, reemplazaba `dora.feeds.refresh`. Creo que el cambio está bien: `feeds.refresh` ya tiene su guarda offline (`feeds.py:366`), y el parche reemplazaba la función en todo el proceso apenas se importaba el servidor. Pero tiene que quedar explicado en el handoff: qué test fallaba o qué archivo de `dora/data` se ensuciaba. Ojo: la guarda de `feeds.py` solo cubre `feed is None`.
6. **Handoff.**
   - Los VNP del handoff (660.186 USD en pampas_core) no coinciden con los que da el código hoy (1.036.105 USD con los datos del repo). Hay que regenerarlos con la salida real y decir con qué curvas de precios.
   - Falta la sección "lo que Guillermo prueba a mano el miércoles" que pedía el prompt.
   - El comentario del test 12 dice "credit line is 0" y la línea es de 100.000 USD. El test sigue valiendo (pone 1.000.000), pero hay que corregir el comentario.
7. **Menor.** El aviso "Cambiaste el modelo" de Resumen A1 revisa con `ISFORMULA` solo 15 celdas. Está bien como alarma rápida, pero hay que anotar en el handoff que el control completo lo hace `read_plan_xlsx`.

## Para la demo del jueves (Guillermo)
- **Cambiar la soja +20 % no cambia las hectáreas.** La soja ya está en el tope de rotación (1.000 de 2.000 ha). Solo sube el VNP: de 1,036 a 1,276 millones de USD. Para mostrar que el plan cambia, conviene:
  - **soja −20 %:** la soja baja a 0 ha y el maíz sube de 178 a 783 ha; el VNP baja a 0,824 millones;
  - **capital ×2:** siembra las 2.000 ha; el VNP sube a 1,798 millones.
- **El economista va a preguntar por qué quedan 624 ha sin sembrar.** La respuesta está en la planilla: el capital ata en todas las quincenas hasta diciembre, y el crédito, en tres. Es un buen momento para mostrar los precios sombra.

## Qué aprendimos
- **Un test independiente vale lo que vale su lista de comparaciones.** El A5 está bien hecho, pero en los escenarios editados se quedó en el VNP. Dos planes distintos pueden tener el mismo VNP.
- **Un precio sombra correcto puede ser engañoso si no dice de dónde sale.** "La tierra vale 105 USD/ha" con 624 ha ociosas es verdad (por la rotación) y a la vez confunde. En la planilla, cada dual tiene que decir qué restricción mueve.
- **Antes de una demo hay que probar que el cambio que se va a mostrar mueve el plan.** En un programa lineal, un recurso en su tope hace que un cambio grande de precio no mueva nada.

## Revisión de los ajustes (commits `35f8b16` y `dd04c85`, 8/11, con el commit 3 todavía en curso)
- **Pampas core, bien.** El bloque de Resumen quedó corto (rotación, tierra, dinero por quincena, crédito y detalle) y consistente ("termina valiendo 1,55 USD de hoy: gana 0,55"). La tierra está explicada con las 624 ha sin sembrar. La fila 7 de Modelo tiene el rótulo pedido.
- **Tests, bien.** Las tolerancias no se aflojaron:
  - el test 5 compara las decisiones en las cuatro ediciones, incluida soja −20 %;
  - el test 11 agrega el crédito cancelado, las ventas por fila y el stock en silo;
  - el test 13 cruza con `capital_shadow_price`, `credit_shadow_price` (con `tax_mult`) y `land_shadow_price`.
- **Error nuevo, hay que arreglarlo: el texto de la tierra explica una causa fija en vez de la que dicen los duales.** En `rented-300ha.xlsx` el bloque dice "La tierra sobra: quedan 300 ha sin sembrar, porque el capital no alcanza. Una hectárea más vale 443,94 USD solo porque sube el tope de soja de la rotación". El mismo bloque dice, dos renglones más abajo, "el capital no es restrictivo". Y la soja no está en su tope. La causa real es otra: con 570 USD/ha de alquiler regional, ninguna hectárea alquilada paga el alquiler, y por eso DORA no alquila. Es justamente el punto de la comparación con Gemini (`docs/investigacion/2026-11-08-gemini-sheets-vs-dora.md`): hay que nombrar el dato que decide.
  - **Arreglo:** la causa se arma solo con las restricciones que atan:
    - capital (dual de la caja − factor de descuento > 1e-6);
    - rotación (`rotation_shadow_price` > 0);
    - alquiler (`rent_in` = 0 con tierra disponible, y valor de la hectárea menor que `regional_rent_usd_ha`): "no se alquila porque el alquiler de la zona (570 USD/ha) es mayor que lo que rinde una hectárea (443,94 USD/ha)";
    - y "tierra propia" solo cuando hay tierra propia.

    Si no ata ninguna, que lo diga sin inventar una causa.
  - **Test:** `test_14` con `rented_300`:
    - no dice "el capital no alcanza";
    - no menciona el tope de soja;
    - sí menciona el alquiler y su valor.

    Que se sumen las seis planillas de ejemplo como chequeo: el texto de la tierra no contradice el renglón del capital.
- **Menor:** los números del bloque salen con punto decimal (211.58) y el resto de la hoja en castellano usa formato de celda. En español deberían salir con coma.
