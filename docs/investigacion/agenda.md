# Agenda de investigación: eficiencia de los sistemas con LLM (M2M Labs, noviembre de 2026)

Guillermo Siaira, investigador independiente. Borrador de trabajo para pedidos de financiamiento y de créditos de cómputo.

## La pregunta
Cuando una empresa usa un modelo de lenguaje para resolver un problema real, ¿cuándo conviene pagar un modelo más grande y cuándo conviene una mejor arquitectura alrededor del modelo (herramientas exactas, un verificador, un agente)? ¿Cuánto cambia la precisión y cuánto el costo en cada caso?

Casi todos los trabajos reportan "el sistema acierta X %". Nosotros medimos lo que necesita quien decide:
- aciertos verificados por dólar;
- cómo cambia el error con el tamaño y la generación del modelo (la elasticidad);
- a partir de qué modelo la arquitectura alcanza un nivel útil (el umbral).

## Lo que ya medimos (con DORA, un agente de planificación agropecuaria)
DORA combina un LLM que conversa, un motor de optimización que calcula el plan exacto (HiGHS) y un verificador que revisa cada número citado. Como el motor da la respuesta exacta, cada respuesta se corrige sola: sin jueces humanos y sin otro LLM opinando.

| Experimento | Qué se midió | Resultado |
|---|---|---|
| E1, E6 | Muse Spark (Meta) solo y dentro de DORA | 37-38 % solo; 93-97 % con DORA |
| E8 | cuatro generaciones de Muse Spark | solas, todas 36-38 %; con DORA, 93-100 %, escribiendo 4 veces menos |
| E9 | Qwen2.5 de 1,5B a 72B, cuatro brazos | solo: 5-12 % en todos los tamaños, sin mejorar con el tamaño. Con DORA: de 0 a 67 %; el error cae un 20 % cada vez que el modelo se duplica, hasta 32B. De 32B a 72B no mejora y el costo por acierto se triplica |
| E10 (en curso) | modelos abiertos por API; primero DeepSeek V4.1 Flash | solo: 9 % (36 % con la regla del E1); con DORA: 97 %, igual que Muse Spark, a un cuarto del precio por token |

**Lectura:** solo, el modelo no mejora ni con más parámetros ni con versiones más nuevas. La arquitectura amplifica lo que el modelo sabe hacer (armar el problema y llamar bien las herramientas) y lo convierte en respuestas exactas y verificadas. Cada tamaño se equivoca distinto:
- los chicos no saben usar herramientas;
- los medianos arman mal el problema;
- los grandes a veces se saltean el motor.

Esos errores dicen qué arreglar en la arquitectura, sin tocar el modelo.

Detalle y datos crudos: `docs/experimentos/` (E1, E6, E8, E9), con todas las respuestas publicadas.

## Qué falta para que sea un resultado general
1. **Más dominios.** Hoy todo es agro. Hacen falta 2 o 3 dominios más con motores deterministas: impuestos de pymes (ARCA), logística o energía. Si el patrón se repite, es un resultado; si no, el trabajo es explicar de qué depende.
2. **Más preguntas.** Pasar de 36 a varios cientos, generadas y variadas, con su respuesta exacta.
3. **Más familias de modelos,** para separar el efecto del tamaño del de la familia y el entrenamiento.
4. **Revisión externa:** publicar en arXiv y someter a revisión por pares.

## Plan a 12 meses

| Trimestre | Trabajo | Entregable |
|---|---|---|
| 1 (nov-ene) | Consolidar E1-E10; ampliar las preguntas de DORA a 300 o más; tabla pública de modelos | Benchmark v1, abierto, con su arnés; primer paper en arXiv (la arquitectura como amplificador: curvas por tamaño y generación, y tipos de error) |
| 2 (feb-abr) | Segundo dominio (impuestos de pymes con ARCA o logística) con motor y verificador | Benchmark v2 con dos dominios; ¿se repite el patrón? |
| 3 (may-jul) | El verificador como recompensa: entrenar modelos chicos y abiertos (Qwen 7B-14B) con aprendizaje por refuerzo, premiando las respuestas correctas y verificadas | Segundo paper: ¿un modelo chico entrenado iguala a uno 10 veces más grande dentro de la arquitectura? Modelos y datos abiertos |
| 4 (ago-oct) | Tabla viva: correr cada modelo nuevo que salga; guía práctica para empresas | Tablero público actualizado; guía "modelo o arquitectura" con números |

En paralelo, todo el año: DORA en producción para productores, como bien público, y el MCP abierto para que cualquier agente use el motor verificado.

## Qué devolvemos
1. **Un benchmark abierto y vivo.** Tareas de decisión con respuesta exacta y el arnés para correr cualquier modelo, con precisión y costo por respuesta correcta, solo y dentro de la arquitectura. Cada modelo nuevo se mide en horas y por pocos dólares.
2. **Papers públicos** con datos y código: la amplificación y el verificador como recompensa.
3. **Herramientas abiertas:** el patrón motor + verificador + MCP, reutilizable en otros dominios.
4. **Una guía práctica:** cuándo invertir en modelo y cuándo en arquitectura.
5. **DORA para productores,** gratis y verificable.

## Cómputo que pedimos y en qué se usa
Cada pedido de crédito tiene un destino medido de antemano: piloto primero, costo estimado y costo real publicados. El uso se publica en un tablero abierto (créditos por laboratorio, cuánto se usó, en qué experimento, con qué resultado).

Referencia de costos medidos:
- E9 completo (6 tamaños, 4 brazos, más la repetición con 64k de contexto): 12,9 USD de GPU.
- Una corrida de un modelo por API con las 36 preguntas: de 0,5 a 15 USD, según el modelo.

Estimación para el plan de 12 meses (a revisar con cada piloto):

| Línea | Cómputo estimado |
|---|---|
| Tabla viva (unos 30 modelos al año × 3 dominios × 4 brazos × 300 preguntas) | 1.500 a 3.000 USD en APIs |
| Entrenamiento con el verificador como recompensa (modelos de 7B a 14B, varias corridas) | 2.000 a 5.000 USD en GPU |
| Servir modelos abiertos para medir tamaños | 500 a 1.000 USD en GPU |

Los laboratorios y los proveedores de cómputo a los que pedir se listan en el tablero, con el estado de cada pedido.

## Límites que declaramos
- Un solo dominio medido hasta ahora; 36 preguntas; ningún resultado revisado por pares todavía.
- La comparación entre arquitecturas internas de los modelos (mezcla de expertos contra densos, por ejemplo) queda como pregunta de largo plazo: hoy el entrenamiento y la familia confunden el efecto.
- Investigador independiente, sin institución: los fondos se reciben a título personal.
