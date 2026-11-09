# Noche de ejercicios con DORA: cuatro problemas que suben de a un escalón

Todos salen de Dorfman, Samuelson y Solow (1958) y están verificados con un solver. Para cada uno:
1. pegá el enunciado en DORA;
2. compará lo que dice con la respuesta del libro;
3. si no coincide, anotá en qué se equivocó: ese error también es material.

Para grabar alcanza con una captura del planteo, el gráfico o la tabla y tu voz explicando qué significa.

## Nivel 1: dos variables, se dibuja a mano
*DSS cap. 6, p. 133*

**Enunciado para pegar:**

> Una compañía automotriz fabrica automóviles y camiones en una planta organizada en cuatro departamentos: estampado de chapa, armado de motores, montaje final de automóviles y montaje final de camiones. La capacidad mensual de estampado permite procesar hasta 25.000 automóviles o 35.000 camiones (o combinación lineal equivalente); el armado de motores permite procesar hasta 33.333 automóviles o 16.667 camiones (un camión requiere el doble de capacidad de motor que un auto); el taller de montaje de autos tiene un tope propio de 22.500 unidades/mes; y el montaje de camiones tiene un tope de 15.000 unidades/mes. Cada automóvil deja un margen neto de 300 USD y cada camión deja 250 USD sobre costos directos. Se desea determinar la combinación mensual óptima de automóviles y camiones que maximice el beneficio total de manufactura.

**Respuesta del libro, para verificar:** Beneficio = 7.731.250 USD/mes con x1 = 20.370 automóviles y x2 = 6.481 camiones (p. 137). Estampado y motores al 100% de capacidad; líneas de montaje final con capacidad ociosa.

**La idea:** Con dos variables, el problema entero entra en un gráfico. Cada taller es una recta, la zona factible es un polígono, y el óptimo cae en una esquina, justo donde se cruzan los dos talleres que hacen de cuello de botella: estampado y motores.

**El visual:** Dibujá las cuatro rectas y la zona factible. Después mové la recta del beneficio (300 x1 + 250 x2 = k) hasta que toque la última esquina. Es un solo gráfico y un minuto de video.

**Para el mundo real:** Las fábricas no están limitadas por "todo", sino por uno o dos talleres. El post podría llamarse "¿Dónde está tu cuello de botella?".

## Nivel 2: el precio oculto de cada cosa
*DSS cap. 2, p. 13*

**Enunciado para pegar:**

> Se debe diseñar una dieta nutricional de costo mínimo satisfaciendo dos requerimientos biológicos diarios mínimos: al menos 700 unidades de calorías (C1) y al menos 400 unidades de vitaminas (C2). Se dispone de cinco alimentos alternativos en el mercado: el Alimento 1 aporta 1 caloría y 0 vitaminas por unidad y cuesta 2 USD; el Alimento 2 aporta 0 calorías y 1 vitamina y cuesta 20 USD; el Alimento 3 aporta 1 caloría y 0 vitaminas y cuesta 3 USD; el Alimento 4 aporta 1 caloría y 1 vitamina y cuesta 11 USD; el Alimento 5 aporta 2 calorías y 1 vitamina y cuesta 12 USD. Determinar la cantidad a consumir de cada alimento para cubrir los estándares al menor costo posible.

**Respuesta del libro, para verificar:** Costo mínimo Z = 4.700 USD con x1 = 0, x2 = 0, x3 = 0, x4 = 100, x5 = 300 (p. 13). Precios sombra de los nutrientes: calorías = 1 USD, vitaminas = 10 USD (pp. 50-54).

**La idea:** De cinco alimentos se usan dos. El problema dual le pone precio a cada nutriente (la caloría vale 1 USD y la vitamina 10 USD), y con esos precios se explica por qué los otros tres alimentos quedan afuera: son caros para lo que aportan.

**El visual:** Pedile a DORA la dieta y después preguntale cuánto vale una caloría más. Armá una tabla con el costo de cada alimento contra el valor de lo que aporta, a precios sombra.

**Para el mundo real:** Raciones para ganado: ¿estoy pagando de más por este balanceado? Es agro puro.

## Nivel 3: la máquina que sobra vale cero
*DSS cap. 6, p. 141*

**Enunciado para pegar:**

> Una planta química integrada produce tres sustancias (C1, C2 y C3) utilizando cuatro tipos de reactores o equipos (E1, E2, E3 y E4), cada uno con una disponibilidad mensual máxima del 100% de su capacidad. Se dispone de tres actividades productivas de transformación: Actividad 1 produce 100 USD de C1 consumiendo 10% de E1 y 5% de E2, con un costo variable directo de 70 USD (ingreso neto -70 USD); Actividad 2 produce 100 USD de C2 consumiendo 30 USD de C1, 4% de E2 y 5% de E3, con un costo directo de 50 USD (ingreso neto -50 USD); Actividad 3 produce 100 USD de C3 consumiendo 10 USD de C1, 50 USD de C2, 2% de E2 y 10% de E4, con un costo directo de 15 USD (ingreso neto -15 USD). Adicionalmente, existen tres actividades comerciales de venta: vender 100 USD de C1 (ingreso neto +100 USD), vender 100 USD de C2 (+100 USD) y vender 100 USD de C3 (+100 USD), las cuales no consumen capacidad de equipos. En equilibrio estacionario, los cambios netos de inventario de C1, C2 y C3 deben ser nulos (la producción interna debe igualar al consumo intermedio más las ventas). Se busca determinar el programa de producción y ventas que maximice el beneficio operativo mensual neto.

**Respuesta del libro, para verificar:** Beneficio neto = 700 USD/mes; x1 = 10 (produce 1000 USD de C1), x2 = 7.5 (produce 750 USD de C2), x3 = 10 (produce 1000 USD de C3), x4 = 6.75 (vende 675 USD de C1), x5 = 2.5 (vende 250 USD de C2), x6 = 10 (vende 1000 USD de C3). E1, E2 y E4 saturados al 100%; E3 utilizado al 37.5% (holgura x10 = 62.5%) (pp. 147-149).

**La idea:** Hay productos intermedios: lo que fabrica una actividad lo usa otra. Tres equipos quedan saturados y el E3 se usa al 37,5 %. Su precio sombra es cero: agrandarlo no deja ni un peso.

**El visual:** Hacé un gráfico de barras con el uso de cada equipo (100, 100, 37,5 y 100 %), y debajo de cada barra su precio sombra.

**Para el mundo real:** "Antes de invertir en una máquina nueva, mirá cuál es tu cuello de botella." Es el tipo de consejo que vende consultoría.

## Nivel 4: transporte, 15 rutas
*DSS cap. 5, p. 106*

**Enunciado para pegar:**

> Una empresa distribuye un producto homogéneo desde tres fábricas (A, B y C) hacia cinco centros de consumo locales (1, 2, 3, 4 y 5). Las capacidades mensuales de las fábricas son: Fábrica A = 50 toneladas, Fábrica B = 100 toneladas, Fábrica C = 150 toneladas (capacidad total = 300 toneladas). Los requerimientos mensuales de las localidades son: Localidad 1 = 25 ton, Localidad 2 = 115 ton, Localidad 3 = 60 ton, Localidad 4 = 30 ton, Localidad 5 = 70 ton (demanda total = 300 toneladas). Las tarifas de transporte unitarias por tonelada (USD/ton) desde cada fábrica a cada localidad son: desde A: (1: 10, 2: 15, 3: 20, 4: 20, 5: 40); desde B: (1: 20, 2: 40, 3: 15, 4: 30, 5: 30); desde C: (1: 30, 2: 35, 3: 40, 4: 55, 5: 25). Determinar el plan de despachos que minimice el flete total.

**Respuesta del libro, para verificar:** Costo mínimo total = 7.225 USD (p. 116). Plan de despachos óptimo (Tabla 5-7): A1=15, A2=35; B1=10, B3=60, B4=30; C2=80, C5=70. Plan óptimo alternativo (Tabla 5-9): A2=35, A4=15; B1=25, B3=60, B4=15; C2=80, C5=70.

**La idea:** Ya no se resuelve a mano en el momento: es el tipo de problema que te tiraban en la cursada. Tiene dos planes óptimos distintos con el mismo costo, 7.225 USD.

**El visual:** Hacé un mapa con flechas de las fábricas a las localidades, con el grosor según las toneladas. Preguntale a DORA si hay otro plan igual de bueno.

**Para el mundo real:** Logística: camiones de granos a acopio o a puerto. Es tu caso 2.

## Si sobra tiempo

- **Las planillas de ayer:** están en `material-privado/revision-planillas/`. Abrí `resultados.md` y algún `.xlsx` de `flash-lite/recipe/`. Sirven para ver cómo plantea un modelo chico.
- **El orden para publicar:** el nivel 1 es el primer post. Cada nivel suma un concepto y un caso real.
- **Las 12 ideas de divulgación**, con título en inglés y el visual de cada una, están en `04-ideas-divulgacion.md`.