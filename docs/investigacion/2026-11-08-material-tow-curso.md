# Material: Fernando Víctor Tow, "Programación lineal como instrumento de modelado microeconómico" (8/11/2026)

**El libro:** Cuadernos Universitarios Macchi n.º 2, Ediciones Macchi, Buenos Aires, 1999 (ISBN 950-537-495-X). Corresponde al programa de Microeconomía I y II de la FCE-UBA. Tow fue profesor de Guillermo en investigación de operaciones.

**El archivo:** un PDF escaneado, sin texto, de 69 páginas, guardado por Guillermo en `D:\Material Clases\` y en `D:\Material Clases\Operaciones\`. **Tiene derechos de autor:** no se sube al repo ni se copia texto. Se usa como guía para armar material propio, citándolo.

## Qué tiene y para qué nos sirve

| Parte del libro | Páginas del libro | Para DORA o el curso |
|---|---|---|
| El esquema de los cinco pasos para armar un modelo | 18–20 | Es la forma de enseñar a plantear: actividades, ítems, coeficientes insumo-producto, flujos externos y ecuaciones de balance. Es lo mismo que hace DORA cuando el modelo de lenguaje llena el escenario y el código arma la matriz. Sirve como primera clase del curso y como guía de modelado para el agente. |
| Producción, ensilaje y venta | 23–24 | El caso agropecuario: trigo y cebada con tierra, mano de obra, semilla y fertilizante; **vender ya** a un precio, o **guardar en silos** de tres tipos y vender más adelante a otro. El mismo problema, planteado de dos maneras (con y sin ítems intermedios), en tablas de Dantzig. No es venta a término con riesgo: es **guardar o vender**, que DORA ya resuelve por quincena. Sirve para mostrar de dónde viene DORA: el ejercicio de clase, y después el campo real con caja, crédito y precios del día. |
| Otro problema de economía agraria | 25–26 | Granjero con trigo, maíz y chanchos, mano de obra familiar y contratada, comprar o vender grano. Bueno para un video: el grano como insumo de la ganadería. |
| Dieta, organización industrial, transporte, gallina y huevo | 24–33 | Ejercicios clásicos para el curso. |
| Dualidad e interpretación económica (precios sombra), análisis de sensibilidad | 48–60 | El núcleo de lo que DORA explica en el Resumen de la planilla. |
| **Problemas del apéndice sobre la economía de Omán (al menos X a XIII; el comienzo de la serie está en las páginas anteriores, que no revisé)** | hasta la 71 | Lo que Guillermo recordaba como "la economía de Omán". Una sociedad con caza y pesca, sin procesar y procesadas, hombres y mujeres, mercaderes que intercambian. Cada gobierno cambia algo: la apertura comercial, la prohibición del trabajo femenino, la "Gran Obra Pública" y cómo financiarla, la autarquía. Todo se resuelve con programación lineal y dualidad: ventajas comparativas, equilibrio y política fiscal. **Es material ideal para el juego y para videos**, porque es una economía chica con historia y personajes. |
| **Problema XIV: FAMASA, aserradero en Salta** | 71–72 | Tablones que se venden o se convierten en mesas, sillas y juegos de camping en otras plantas. Tres tipos de rollizo, capacidad por planta, demanda, crédito en dos tramos de tasa, subproductos (aserrín, recortes) y un subsidio a la exportación. **Es un caso 2 casi armado para el paquete de dominio "aserradero"**, a la medida de la experiencia de Guillermo en Alto Paraná. |
| Problema XVII: rotación en varios períodos | 73 | Tres cultivos, cuatro períodos y reglas de rotación. Es la versión de clase de las restricciones de rotación de DORA. |

## Ideas para usarlo
- **Curso "programación lineal con IA en tu computadora".** Cada clase sigue el mismo recorrido:
  1. el ejercicio de Tow, con los cinco pasos;
  2. lo resuelve DORA o la planilla con OpenSolver;
  3. se pasa al caso real (el campo de Pergamino, la comparación con Gemini);
  4. un modelo local hace lo mismo y se mide si acierta.
- **Videos con visuales técnicos** (por ejemplo, Manim):
  - la región factible y el método simplex, como en las figuras V a VIII del libro;
  - el precio sombra como "cuánto vale relajar una restricción";
  - Omán como animación de una economía de dos bienes con ventajas comparativas.
- **El juego:** las reformas de Omán (apertura, prohibiciones, impuestos, autarquía) son niveles naturales. En cada uno, el jugador cambia una regla y la programación lineal calcula el nuevo equilibrio.
- **Banco de preguntas (SPEC-48):** los enunciados de Tow pueden ser plantillas extra, siempre redactadas por nosotros, nunca copiadas.

## Qué aprendimos
- **El método de los cinco pasos es la "guía de modelado" que buscábamos para los paquetes de dominio:** primero actividades e ítems, después coeficientes y balances. Le sirve al agente y le sirve al alumno.
- **El ejercicio de clase y DORA son el mismo problema a distinta escala.** Mostrar el salto del uno al otro es la mejor explicación de qué agrega DORA.
- **El aserradero (caso 2) ya tiene un enunciado de partida** en el problema XIV.
