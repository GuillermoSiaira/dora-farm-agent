# Plan de M2M Labs (6/11/2026)

Documento vivo. Junta la tesis, los proyectos, cómo se financia y qué se muestra. El estado día a día de cada pieza está en `docs/handoff/estado-2026-11-06.md`; los créditos disponibles, en `docs/grants/creditos-y-programas.md`.

## 1. La tesis
**Arquitectura híbrida para eficiencia económica.** Los modelos determinísticos (optimización, cálculo, simulación) sostienen las decisiones. Los modelos de lenguaje, probabilísticos, interpretan, conversan y explican. Un verificador controla que lo dicho coincida con lo calculado.

Qué se gana:
- **Precisión:** los números no los inventa el modelo.
- **Costo:** el modelo no razona la matemática. Escribe menos y puede ser más chico.
- **Prueba:** cada número lleva su verificación. Opcionalmente queda un registro público en la blockchain.

Frase corta: *"El modelo conversa, el motor calcula, y cada número llega con su prueba."*

Cómo decirlo con honestidad: el cálculo no tiene error, pero el modelo puede cargar mal un dato o citar mal un número. El verificador lo detecta en parte. Nunca decir "cero errores".

## 2. Los proyectos: una tesis, varias aplicaciones
| Proyecto | Motor determinístico | Qué hace el modelo de lenguaje | Estado |
|---|---|---|---|
| **DORA** (agro) | Optimizador lineal: plan de campaña, caja, crédito, tierra | Arma el escenario y explica el plan | Producto andando: app, MCP público, planilla, registro on-chain (en Sepolia) |
| **Abu Oracle** | Cálculo astronómico | Interpreta | En producción, con su propio MCP |
| **Invisible Hand** (juego educativo) | Simulación económica | Enseña, conduce el juego | Prototipo. Falta sumarle la tesis |
| **Juego de matemáticas** | Cálculo exacto | Enseña | Por desarrollar |
| Próximas verticales de DORA | El mismo motor con otros modelos: logística, depósitos fiscales, consolidación en puerto, producción | Igual | Cuando un cliente las pida |

Regla: ante un inversor se **vende uno** (hoy DORA). Los demás se muestran como **prueba de que la tesis se generaliza**.

## 3. Estructura
- **Investigación abierta:** el núcleo de DORA, Apache-2.0, con sus experimentos públicos. Se financia con **grants**: Mozilla, programas de laboratorios de IA y de blockchains.
- **M2M Labs como empresa** (cuando haga falta): vende servicios encima del núcleo abierto. Por ejemplo, el MCP con clave y más uso, implementaciones para empresas y verticales a medida. Hoy no existe la sociedad. Las opciones son una SAS en Argentina o una C-Corp en Delaware vía Stripe Atlas (unos 500 USD). Constituirla además destrabaría créditos que piden empresa, como NVIDIA Inception.
- Marca en GitHub: organización `m2m-labs` (nombre visible "M2M Labs"). El perfil personal sigue mostrando a Guillermo, porque los grants se dan a la persona.

## 4. Financiamiento, en este orden
1. **Créditos de cómputo** (no son efectivo): primero AWS Activate Founders y Together AI, porque sirven para el E9. Después Microsoft for Startups, Salad y otros de `docs/grants/creditos-y-programas.md`. Casi todos piden un mail con dominio propio: `contact@abu-oracle.com` u otro de M2M Labs.
2. **Grants:**
   - Mozilla Human-Scale AI (20/11). El borrador está en `docs/grants/mozilla-human-scale-ai-2026.md`.
   - Telegraph (1/12): el MCP cobrando por consulta.
   - Base Builder Grants: cuando haya atestaciones reales.
   - Programas de Anthropic y otros laboratorios cuando abran.
3. **Hackatones:**
   - Resultados de Meta: 9/11.
   - Aleph Rosario (27–28/11): agro, desafíos de empresas de la región. Es la puerta a clientes.
4. **Inversión, recién con lo anterior en la mano:** producto andando, cómputo cubierto, evidencia experimental y, si es posible, un primer interesado.

**Cómo presentar los créditos.** Sirven como prueba de ejecución, y porque bajan el costo operativo casi a cero durante meses. *"El cómputo está cubierto por 12 meses; la inversión va a personas y ventas."* **No** son capital que se pueda aportar ni valuar como participación: no se pueden transferir y vencen. Mostrarlos siempre tal cual son.

**Cómo recupera la plata un inversor** (hipótesis a validar):
- MCP con clave, cobrado por consulta (x402, USDC en Base) o por suscripción.
- Implementaciones para empresas agro: acopios, consultoras, aseguradoras y crédito agrícola, con el registro on-chain como argumento.
- Nuevas verticales con el mismo motor.

## 5. Experimentos: la evidencia de la tesis
| Exp. | Qué midió | Resultado |
|---|---|---|
| E1 | Muse Spark 1.3, solo contra con DORA (×5) | 38 % → 97 % correctas |
| E6 | Muse Spark Open, ídem | 37 % → 93 % |
| E8 | Cuatro versiones de Muse Spark | Solas 36–38 %; con DORA 93–100 %; escriben unas 4 veces menos tokens |
| **E9 (en curso)** | **Tamaño del modelo** (Qwen2.5 de 1,5B a 32B, en Modal): solo, con nuestro agente y con un agente genérico vía MCP | Diseño en `docs/experimentos/2026-11-06-e9-diseno.md`; el piloto cuesta ~1 USD y espera OK |

El E9 avanza con el crédito actual de Modal. Los créditos nuevos permitirían sumar modelos más grandes y una segunda familia (Llama).

**Medidas que hay que mostrar, simples pero técnicas:**
- **Precisión:** respuestas correctas y verificadas, en %.
- **Productividad:** respuestas correctas por dólar, y por hora de GPU.
- **Costo por respuesta correcta**, en USD.
- **Elasticidad del error respecto del tamaño:** cuánto baja la tasa de error, en %, cuando el modelo crece 1 %. Con DORA se espera casi cero por encima del umbral. Agrandar el modelo ya no compra precisión, solo costo.
- **Umbral:** el modelo más chico que llega a 90 % con DORA.
- **Tokens escritos por respuesta:** el modelo trabaja menos porque el motor hace la cuenta.

Regla: nunca mostrar una curva con más puntos de los medidos.

## 6. Qué se muestra (comunicación)
- **Página de experimentos en el repo:** una entrada por experimento, con pregunta, método, resultado, gráfico y "Qué aprendimos". Ya existe `docs/experimentos/`; falta un índice visible desde el README.
- **Gráficos**, sobrios y en inglés y español:
  1. precisión contra tamaño del modelo, solo y con DORA, con el tamaño en escala logarítmica;
  2. costo por respuesta correcta contra tamaño;
  3. elasticidad del error;
  4. tokens escritos, solo y con DORA;
  5. el diagrama de arquitectura (`docs/diagramas/dora-mcp-antes-despues.pdf`).
- **Videos cortos (2–3 min), en inglés y en español** (herramientas: `infra/video/record.py` y `edit.py --voice`):
  1. la tesis, con el diagrama;
  2. DORA desde Claude vía conector: pregunta real y respuesta con su prueba;
  3. los resultados del E9 con sus gráficos.
- **Tono:** la simplicidad de la precisión técnica. Pocas palabras, cada número con su fuente, sin promesas que no se midieron.

## 7. Próximos pasos
1. OK al piloto del E9 (~1 USD de Modal) en la sesión del E9.
2. Pedir créditos: AWS Founders y Together AI. Guillermo completa los formularios; Claude prepara los textos.
3. Completar los 7 puntos de Mozilla, con E1/E6/E8 como evidencia y el E9 como resultado preliminar o plan.
4. Inscribirse en Aleph Rosario.
5. Agregar DORA como conector en Claude y grabar el video 2.
6. Después del 10/11: revisión final y merge a `main` de las SPEC-40 a 44.
7. Después del 1/12: Invisible Hand con la tesis; decidir si se constituye la empresa.
