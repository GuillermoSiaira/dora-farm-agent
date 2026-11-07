# Ficha: el mecánico de LLM (idea, 7/11/2026, sin implementar)

Línea nueva de la agenda de eficiencia (M2M Labs). Parte de E9 y E10 (`docs/experimentos/`, rama `claude/e9-model-size-74c177`) y del piloto del E11 que figura en el índice de investigación.

## La idea
Con un modelo abierto que corre en máquinas propias (Qwen, DeepSeek, Llama) se puede abrir el motor: cambiarle el prompt, los ejemplos, los pesos o las activaciones, o la forma en que elige cada token. Cada perilla arregla algunos errores y puede romper otros. El **mecánico** es un agente que:
1. mira en qué se equivoca el modelo en un problema concreto (acá: armar el escenario de programación lineal de DORA);
2. elige qué perillas tocar con un presupuesto;
3. mide si arregló, cuánto costó y qué rompió.

Y lo estudiamos desde la eficiencia: cuánto cuesta cada ajuste, cuánto rinde, y cuál es el **precio sombra** del presupuesto (cuántos aciertos más da un dólar más).

## La pregunta
Para un modelo que **casi acierta** dentro de DORA (Qwen2.5 14B con 38 %, 32B con 67 %), ¿qué combinación de perillas convierte más errores en respuestas correctas y verificadas por dólar, sin aumentar las fallas que el verificador no ve? ¿Y cuándo eso le gana a la alternativa obvia, que es cambiar de modelo (DeepSeek V4.1 Flash: 97 % a 0,006 USD por acierto, E10)?

## Las perillas: qué arreglan, qué cuestan, qué pueden romper
El E9 ya dice dónde está el error en cada tamaño (DORA, 64k, 72 respuestas por tamaño). Eso define qué perilla tiene sentido:

| Error del E9 | 3B | 7B | 14B | 32B |
|---|---|---|---|---|
| No llamó ninguna herramienta | 29 | 13 | 9 | 5 |
| Llamó herramientas, todas con error | 17 | 14 | 6 | 2 |
| Armó otro escenario | 13 | 20 | 21 | 12 |
| El motor tenía el número; la respuesta no lo dice | 2 | 4 | 4 | 4 |
| Debía negarse o preguntar | 4 | 2 | 2 | 0 |

| Perilla | Qué ataca | Costo fijo (una vez) | Costo variable (por respuesta) | Qué puede romper |
|---|---|---|---|---|
| **Prompt y guía** | nombres de parámetros, formato. Ya rindió: con el 32B, 4 % sin guía, 26 % con guía, 67 % con el agente completo | casi cero (tiempo de diseño) | tokens de entrada: DORA ya lee 58.000-86.000 por respuesta | el contexto: en el E9 el límite de 32k cortó la mitad de las respuestas del 14B |
| **Ejemplos (few-shot)** | llamada escrita como texto, escenario "eco" | casi cero | más tokens de entrada (2 trazas ≈ 4.000-8.000) | el modelo copia el ejemplo en vez de leer al productor |
| **Decodificación restringida con gramática** (que la llamada solo pueda salir con el esquema de la herramienta) | "todas con error" y parte de "no llamó" (el 1,5B y el 72B escriben la llamada como texto) | bajo: configurar el servidor (vLLM tiene salida guiada) | casi cero; algo de latencia | no arregla el escenario mal armado; si obliga a llamar siempre, rompe las preguntas donde hay que negarse |
| **LoRA con trazas verificadas por DORA** | "armó otro escenario", el error más grande en 7B-32B | generar trazas (con DeepSeek Flash, unos 0,006 USD por traza correcta) + 1-3 h de GPU para un 7B-14B | cero; puede bajar, si permite acortar el prompt | otras habilidades del modelo; se ajusta a las preguntas de entrenamiento |
| **Destilación** (la LoRA es destilación de trazas; además, destilar el prompt: que el modelo se comporte como si tuviera la guía sin leerla) | lo mismo que LoRA, y el costo de leer | como LoRA | **baja** el costo variable: menos tokens de entrada | lo mismo que LoRA |
| **Steering de activaciones** (sumar un vector en una capa para empujar una conducta) | conductas de sí o no: "llamá al motor en vez de responder de memoria", "negate cuando no hay datos" | bajo: pares de ejemplos contrastivos y minutos de GPU | cero | es la perilla menos probada en tareas estructuradas; puede romper la fluidez o los números. Es la más "abrir el motor" y la más arriesgada |
| **Cuantización** (FP8, 4 bits) | ninguno: es una perilla de costo, no de calidad | bajo | **baja** el costo de GPU (2 H100 → 1) | aciertos; hay que medir cuántos pierde. El 32B y el 72B del E9 ya corrieron en FP8 |
| **Muestreo múltiple con voto** (armar el escenario 2-3 veces y comparar) | "armó otro escenario", sin entrenar | cero | multiplica el costo por 2-3 | nada en calidad; sí en costo. Es la señal que la agenda propone para el router (línea 4c) |

Cuentas de techo, con el 14B: de 45 errores, la gramática apunta a unos 6-15 (llamadas con error y parte de las no hechas): como mucho, +8 a +21 puntos. El grueso (21 escenarios mal armados) solo lo atacan ejemplos, LoRA o voto. Por eso la gramática sola no lleva al 90 %.

## Cómo se mide: dos medidores que no son lo mismo
- **El banco (offline).** El evaluador del set (`strict_score`) conoce la respuesta exacta. Sirve para elegir perillas y estimar cuánto arregla cada una. Condición: separar preguntas de ajuste y de prueba. Con 36 preguntas eso es poco; hace falta el generador de cientos de preguntas que ya está en la agenda (trimestre 1).
- **El verificador (en producción).** No conoce la respuesta: solo controla que cada número salga de una herramienta. No ve el error más común de los medianos: el número sale del motor, pero de otro problema.

De ahí la medida que el mecánico no puede ignorar: **fallas silenciosas** = respuestas incorrectas que el verificador deja pasar. Una perilla que baja los errores visibles y sube los silenciosos empeora el sistema. Riesgo concreto: entrenar una LoRA premiando solo "pasó el verificador" le enseña al modelo a citar números del motor aunque el escenario esté mal. Para entrenar, la recompensa sale del evaluador del banco (con las preguntas de ajuste), nunca del verificador solo. Y el mecánico en producción solo puede decidir con señales que el verificador ve (por ejemplo, que dos muestras armen el mismo escenario), no con la respuesta, que no tiene.

## La elección de perillas como problema de optimización
Las perillas no suman en línea recta: la gramática y los ejemplos arreglan en parte los mismos errores. Una forma lineal que lo respeta es pensarlo por **tipo de error**:

- `e_j` = errores de tipo `j` del modelo hoy (la tabla del E9).
- `x_k` ∈ [0, 1] = si se aplica la perilla `k` (o en qué dosis).
- `a_kj` = fracción de los errores de tipo `j` que arregla la perilla `k`; `b_k` = respuestas correctas que rompe. Se estiman con pilotos chicos en el banco.
- `y_j` = errores de tipo `j` arreglados: `y_j ≤ e_j` y `y_j ≤ Σ_k a_kj · e_j · x_k` (no se puede arreglar más de lo que hay).

Maximizar `Σ_j y_j − Σ_k b_k · x_k` (aciertos ganados netos), sujeto a:
- **presupuesto:** `Σ_k (fijo_k + Q · variable_k) · x_k ≤ B`, con `Q` = respuestas previstas;
- **fallas silenciosas:** `Σ_k s_k · x_k ≤ S` (lo que cada perilla agrega de fallas que el verificador no ve);
- **contexto:** tokens de entrada ≤ el límite del servidor (en el E9, 65.536).

Lo que da el problema, además del plan:
- **precio sombra del presupuesto:** aciertos por dólar extra. Si es bajo, no conviene seguir ajustando;
- **precio sombra de las fallas silenciosas:** cuántos aciertos cuesta exigir más seguridad;
- **precio sombra del contexto:** cuánto vale ahorrar tokens (y justifica la destilación del prompt);
- **costo reducido de cada perilla no usada:** cuánto tendría que rendir para entrar. Eso le dice al mecánico qué probar en el próximo piloto.

**Hitos y meritocracia.** El valor no es lineal en el acierto: un DORA al 85 % no se puede ofrecer y uno al 90 % sí (es el umbral N\* del E9). Si el objetivo tiene hitos (50, 75, 90 %), el problema pasa a ser entero-mixto: una variable binaria por hito alcanzado. Eso arma la meritocracia: el presupuesto de ajuste va primero a los modelos que están cerca de un hito y cuyos errores son de tipos arreglables (14B y 32B: escenario y formato), no a los que fallan por falta de capacidad (1,5B: no sabe usar herramientas). Cada modelo "se gana" el siguiente peso de presupuesto mostrando en el piloto que su `a_kj` es alto.

**El costo de oportunidad.** Toda perilla compite con cambiar de modelo. Hoy, en DORA, DeepSeek V4.1 Flash por API da 97 % a 0,006 USD por acierto, y Qwen2.5 14B servido por nosotros costaba 0,024 USD por acierto con 38 %. Ajustar un modelo local conviene cuando:
- hay que correr sin API (privacidad, sin conexión en el campo, soberanía de datos); o
- el volumen amortiza el costo fijo: conviene si `fijo / Q < costo por acierto de la alternativa − costo por acierto del modelo ajustado`.

La ficha no da eso por hecho: es parte de lo que hay que medir.

## Hipótesis
1. **H1.** La gramática sube mucho a 3B-7B (errores de formato) y poco a 14B-32B (errores de escenario).
2. **H2.** Para el escenario mal armado, la LoRA con trazas verificadas rinde más por dólar que los ejemplos en el prompt, cuando `Q` pasa unos pocos miles de respuestas (se paga una vez y no agrega tokens).
3. **H3.** Las perillas que tocan pesos o activaciones (LoRA, steering) suben más las fallas silenciosas que las que tocan la entrada o la salida (prompt, gramática, voto). Hay que medirlo, no suponerlo.
4. **H4.** La matriz `a_kj` depende más del tipo de error que del modelo: lo que arregla la gramática en Qwen lo arregla también en Llama. Si se cumple, el mecánico puede reutilizar lo aprendido entre modelos.

## Primer experimento barato (E12, piloto)
**Paso 0, gratis: la matriz a priori.** Volver a leer las respuestas del E9 que ya están en `eval/results/e9/ctx64k/` y marcar en cada error qué perilla lo arreglaría (llamada como texto → gramática; escenario mal armado → ejemplos o LoRA; respondió de memoria → steering o prompt). Sale una primera `a_kj` y el techo de cada perilla, sin gastar nada.

**Paso 1, dos perillas baratas en dos tamaños.** Qwen2.5 7B y 14B, brazo DORA con 64k, 2 repeticiones, igual que la repetición de los arreglos del E9:
- **gramática:** las llamadas a herramientas solo pueden salir con el esquema (salida guiada de vLLM). Antes de correr hay que confirmar cómo se combina con la elección automática de herramientas en la versión de vLLM que usamos;
- **ejemplos:** 2 trazas correctas de DeepSeek Flash (del E10) en el prompt.

Por respuesta se registra: tipo de error (la clasificación del E9), si pasó el verificador, tokens y costo. De ahí sale `a_kj`, `b_k` y `s_k` medidos, se resuelve el problema lineal con HiGHS (el mismo motor de DORA) y se leen los precios sombra.

**Costo y dónde.** La repetición de los arreglos del E9 (3 tamaños, 2 repeticiones) costó 1,20 USD en Modal. Esto son 2 perillas × 2 tamaños × 2 repeticiones: estimado 1,5-2,5 USD de Modal, dentro del saldo de noviembre (unos 15 de 30 USD). Alternativa sin costo: el 7B en las GPU gratis de Kaggle Notebooks, si entra con 64k de contexto. **Antes de gastar se pregunta a Guillermo.**

**Paso 2, solo si el paso 1 muestra que el escenario es el cuello.** LoRA de un 7B con unas 500-1.000 trazas verificadas, generadas con preguntas distintas de las de prueba. Necesita el generador de preguntas y el crédito de Baseten (cobro fallido en el E10) o el proxy de Kaggle. Se especifica después del paso 1.

Implementación: Claude escribe la spec; Antigravity implementa.

## Preguntas abiertas para Guillermo
- ¿El caso de uso que justifica el mecánico es el modelo local (sin API, privacidad) o el costo con volumen? Cambia el valor de `Q` y la alternativa contra la que se compara.
- ¿El hito que importa es 90 % (el N\* del E9) o hay un hito intermedio útil para el producto (por ejemplo, 75 % con confirmación del productor)?
- ¿Steering entra en el primer piloto o queda para después? Es la perilla más interesante para "abrir el motor", y también la que menos evidencia tiene en tareas como esta.

## Qué aprendimos
- **El mecánico no empieza tocando el modelo, empieza clasificando errores.** La tabla de tipos de error del E9 ya es la mitad del diagnóstico: dice qué perilla tiene techo alto y cuál no. La gramática no puede llevar a un 14B al 90 % porque su error principal es de escenario, no de formato.
- **Elegir perillas es un problema lineal si se razona por tipo de error.** Con "no se arregla más de lo que hay" como restricción, los solapamientos entre perillas entran sin salir de la programación lineal. Los precios sombra dicen cuánto vale un dólar más, un token más de contexto o una falla silenciosa menos.
- **Los dos medidores tienen que quedar separados.** El banco conoce la respuesta y sirve para elegir y entrenar; el verificador no la conoce y no ve los escenarios mal armados. Un ajuste que solo mira el verificador puede enseñar al modelo a esconder el error.
- **La vara es el costo de oportunidad.** Hoy cambiar a DeepSeek Flash da 97 % más barato que cualquier ajuste de Qwen. El mecánico tiene valor donde no se puede o no conviene usar una API, y eso hay que decirlo antes de gastar.
- **Los hitos vuelven el problema entero y justifican la meritocracia:** el presupuesto rinde más en los modelos que casi aciertan y cuyos errores son arreglables, no en los más chicos.
