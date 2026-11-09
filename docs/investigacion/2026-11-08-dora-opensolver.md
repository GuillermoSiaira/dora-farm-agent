# Nota: DORA como asistente para quien usa OpenSolver (8/11/2026, idea, sin implementar)

## La idea
OpenSolver (gratis, abierto, para Excel y Google Sheets) tiene usuarios que ya plantean problemas de programación lineal en planillas. Hoy no tienen un asistente que entienda su problema: lo que hay es rudimentario y no reconfigura el modelo. DORA puede ser ese asistente, porque ya es un arnés:
- cada modelo de lenguaje que se conecta recibe el prompt, la guía de modelado y las herramientas de DORA;
- un motor exacto resuelve;
- un verificador controla cada número.

La SPEC-45 ya va en esa dirección: el modelo completo dentro de la planilla, re-optimizable con OpenSolver. La fase B suma el menú de DORA dentro de Google Sheets.

**Licencias:** OpenSolver es GPL y DORA es Apache 2.0. Pueden trabajar juntos (la planilla de DORA lista para OpenSolver, un menú que llama a los dos), pero no hay que copiar código de OpenSolver dentro del repo de DORA.

## El problema de fondo (Guillermo)
Cuando no se conoce la respuesta de antemano, ¿cómo se sabe que el modelo de lenguaje formalizó bien el problema? En los experimentos lo sabemos porque nosotros armamos cada pregunta con su respuesta. En uso real, nadie la sabe. O hay un especialista en programación lineal que revisa, o el usuario se vuelve especialista. Y ninguna de las dos escala.

Es la misma distinción entre el **banco**, que conoce la respuesta, y el **verificador**, que no. El E9 midió el tamaño del hueco: con Qwen 14B, 25 de 52 respuestas que el verificador aceptó estaban mal, casi todas con un escenario mal armado. Con DeepSeek Flash, 1 de 36.

## Respuestas posibles (combinables; cada una es medible con el banco)
1. **El modelo no escribe el programa lineal; llena un formulario.** DORA ya lo hace: el modelo de lenguaje solo completa un escenario con parámetros con nombre (hectáreas, capital, contratos, plazos), y el código arma las 196 variables. El error posible baja de "formuló mal" a "cargó mal un dato", que es más fácil de controlar. Para un usuario de OpenSolver que escribe su propio modelo, el asistente propondría cambios como diferencias sobre el modelo existente ("agrego la fila X, cambio el coeficiente Y"), nunca reescribiéndolo entero.
2. **Devolverlo en el idioma del usuario y que confirme.** "Lo que entendí: 500 ha propias, 50.000 USD, mínimo 200 ha de soja por contrato." El productor no sabe programación lineal, pero sí sabe si eso es su campo. El experto en el problema es el usuario; el formulario lo pone en palabras que entiende. Falta medir cuántos errores atrapa la confirmación.
3. **Redundancia.** Dos modelos distintos, o dos intentos del mismo, arman el escenario por separado. Si coinciden, se sigue; si no, se pregunta. Es la señal en producción que propone el router de costos (línea 4c del mapa de investigación). Se puede medir hoy con los datos del E9 y del E12.
4. **Chequeos de sentido económico.** Restricciones que no pueden faltar (la caja por quincena no da negativa, no se vende más grano del que hay), precios sombra con el signo esperado, valores fuera de lo normal para la zona. Atrapan escenarios absurdos, no los sutiles.
5. **Certificar antes y vigilar después.** Con el banco, que conoce las respuestas, se elige qué modelos de lenguaje formalizan bien (DeepSeek Flash 97 %, Qwen 14B 41 %). En producción se usa uno certificado y se registra cada plan con su huella (SPEC-41) para compararlo al final de la campaña con lo que pasó.

La hipótesis de trabajo es que **2 + 3 cubren casi todo lo que el verificador no ve, a bajo costo**. Se puede probar con un experimento barato, sin GPU nueva: tomar las respuestas ya guardadas del E9 y del E12, simular la confirmación (¿el resumen "lo que entendí" muestra el dato mal cargado?) y la redundancia (¿dos modelos coinciden cuando está bien y discrepan cuando está mal?), y medir cuántas fallas silenciosas atrapa cada una.

## Qué aprendimos
- **DORA ya es la mitad de la respuesta:** el modelo no formaliza libremente, completa un formulario con nombre. Eso es lo que hace verificable el resto.
- **El usuario no necesita ser experto en programación lineal; necesita poder reconocer su propio problema** escrito en sus palabras. El trabajo del sistema es traducir en las dos direcciones y avisar cuando la traducción es dudosa.
- **Para OpenSolver, el valor de DORA no es resolver, es plantear y explicar.** El solver ya lo tienen; lo que les falta es alguien que arme bien el modelo, lo cambie con cuidado y explique los precios sombra.
