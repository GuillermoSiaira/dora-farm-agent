# Mozilla Human-Scale AI Incubator: borrador de propuesta inicial

**Cierre:** viernes 20/11/2026, 23:59 PST (sábado 21/11, 04:59 hora de Buenos Aires). Formulario: https://mozillafoundation.tfaforms.net/w/humanscaleai. Charla informativa: 12/11.
**Estado:** borrador de Claude, actualizado el 8/11 con los experimentos E9 a E12. Todavía sin revisar por Guillermo. Las respuestas van en inglés: el formulario acepta español, pero el jurado lee inglés.

## Antes de completar: lo que falta (en español)

| # | Punto | Estado | Qué hace Guillermo |
|---|---|---|---|
| 1 | Elegibilidad como individuo desde Argentina | Mozilla financia individuos de cualquier país no sancionado por OFAC | Confirmar que tenés una cuenta que recibe USD por transferencia desde EE. UU. y que podés estar en la cohorte de 12 meses desde abril de 2027 |
| 2 | Propósito caritativo, no comercial | **Decidido (5/11):** se financia la parte pública (motor, verificador, banco de evaluación, investigación, herramienta gratis). El MCP pago existe aparte y la propuesta no lo menciona como objetivo. El repo tiene licencia Apache 2.0 | Nada |
| 3 | Puntos débiles dichos con honestidad | **Actualizado (8/11)** con E9 a E12: no hay usuarios reales todavía; los modelos abiertos medianos arman mal el escenario; el verificador no detecta un escenario mal armado | Leer |
| 4 | Video de 2 minutos | Fuertemente recomendado. Se puede recortar del video del hackathon (youtu.be/W4zBWeavPi0) y sumar el gráfico del E9 | Decidir si lo recortamos |
| 5 | Socio piloto | **Lo que más sumaría.** Un correo de un asesor, un grupo CREA o una cooperativa que diga que lo probaría cambia la sección de tracción | Conseguirlo, si se puede antes del 20/11 |
| 6 | Declaración de IA | Responder que sí (borrador asistido por Claude, revisado y editado por vos). Las propuestas "mayormente generadas por IA" tienen revisión extra | Reescribir con tu voz al menos el resumen y el equipo |
| 7 | Tamaño del modelo más grande | **Propuesta (8/11):** 72B, el Qwen2.5 más grande que corrimos en GPU propia. No sabemos los parámetros de Muse Spark ni de DeepSeek V4.1 Flash: no los pongas sin confirmarlos | Confirmar |

**Cambio importante respecto del 5/11: la meta del modelo.** El borrador prometía "un modelo abierto de 10B o menos al 90 %". Los experimentos de esta semana no lo sostienen:
- **E9:** Qwen2.5 7B llega a 22 % dentro de DORA;
- **E12:** con ejemplos, el 7B copia los números del ejemplo; el 14B pasa de 41 a 71 %;
- **E10:** DeepSeek V4.1 Flash, abierto pero mucho más grande, llega a 97 %.

La meta nueva es **"un modelo abierto de 14B o menos, que corre en una sola GPU, al 90 % en preguntas nuevas"**, con el plan del año para cerrar la distancia (71 % hoy). Es ambiciosa pero tiene un punto de partida medido. Si preferís una meta más segura, cambiá 14B por 32B: el 32B ya llega a 67 % sin ejemplos.

---

## Project Overview

**Proposed Project Title**
DORA: small open models that plan a farm season correctly, because a solver does the math and a verifier checks every number

**Project Summary** (short)
Family grain farmers in Argentina make their largest decisions of the year (what to sow, when to sell, whether to borrow or rent out the land) with spreadsheets or with chatbots that invent numbers. DORA is an open agent where the language model only talks: it asks the farmer, builds the scenario and explains the result. A linear-programming engine plans the season fortnight by fortnight, and a deterministic verifier blocks any number in the answer that the engine did not produce. We have measured it with more than a dozen models from four families, open and closed. Alone, none of the models we measured in full passed 38 % correct answers, and neither a newer version nor a larger size changed that. Inside DORA, the strongest models reach 93–97 %. An open-weight model (DeepSeek V4.1 Flash) reaches 97 % inside DORA at about USD 0.006 per correct, verified answer, and a 14-billion-parameter open model that a cooperative can run on one GPU goes from 41 % to 71 % with two worked examples. We want to close that last gap so that a small open model is reliable enough for real farm decisions, test DORA with real farmers, and publish the engine, the verifier and the evaluation set so that others can apply the pattern to other planning problems.

**Human-Scale AI principles**
- **Small:** the architecture moves the hard part (optimisation, arithmetic) out of the model into a solver that runs in milliseconds on a laptop. The model only has to understand the farmer and call tools. We have measured how small it can be today: with our architecture, a 14B open model reaches 71 % and a 7B model is not yet usable. The project is about making the smallest model reliable, and measuring what each step costs.
- **Intentional:** the farmer sees and controls every input. The agent asks before assuming, one question at a time, starting with the one that would be most costly to get wrong. No number reaches the farmer unless it can be traced to the engine. Plans can be recorded as a dated hash, so the farmer, not a platform, holds the proof of what was advised.
- **Tailored:** built around Argentine grain farming as it is: fortnightly cash flows, export duties and local taxes, land rent, storage in silo bags, prices from local markets, Spanish voice notes and photos of invoices, and satellite images of the farmer's own field.

**Project Stage:** Working prototype

**Early signals of product-community fit:** None of these yet *(cambiar si conseguís un socio piloto, ver punto 5)*

**Approximate users:** Less than 100

**Primary Output(s):** Technology platform or tool; Research publication; Dataset

**Frontier API dependence:** Partly. The public demo uses Meta's Muse Spark through Meta's API. We have already measured open-weight models inside DORA (Qwen2.5 from 1.5B to 72B on our own GPUs, DeepSeek V4.1 Flash). Removing the dependence entirely is the goal of the project.

**Largest model parameter count:** *(punto 7: propuesta "72B, the largest open model we run ourselves")*

**Charitable purpose:** Yes.
**Public benefit:** Advancing open scientific research on how to make small language models reliable for numerical decisions, published with code and evaluation data; and a free planning tool for small and medium family farmers who cannot pay for agronomic and financial advice.

**How will you work in the open:** Open sourcing code; publishing research and evaluation data; documenting experiments publicly.

## Project Details

**What technology are you building and how does it address this cohort's theme?**
DORA has three parts:
1. **An agent** that interviews the farmer in plain Spanish, by text, voice note or a photo of an invoice, and turns that into a structured scenario.
2. **A linear-programming engine** that plans the whole season in fortnights: hectares per crop and sowing window, when to sell or store each tonne, when to use credit, and the value of each scarce resource (the shadow prices of cash, land, storage and credit). It also answers questions farmers actually ask: is it better to rent the land out, and at what price would a crop left out of the plan become worth sowing.
3. **A deterministic verifier:** every number in the agent's answer must match a tool result or something the farmer said; otherwise the answer goes back to the model for correction before the farmer sees it.

*Small:* the model never computes; a solver does. That is why the same model is both more accurate and cheaper inside DORA.

Our measurements show where small models still fail, and that is the work we propose:
- below about 7B parameters, models do not call the tools correctly;
- mid-size models call them, but translate the farmer's words into the wrong scenario (an invented region, the wrong capital, a missing contract);
- the solver then answers a different problem exactly.

We will build a generator of hundreds of farmer questions with exact answers computed by the engine, split so that what a model is tuned on is never what it is tested on. With it we will measure, for each way of improving a small model (better instructions, worked examples, light fine-tuning on verified traces), how much accuracy it buys and at what cost, and publish the curve.

*Intentional:* the verifier and the question order are explicit, inspectable rules, not prompt instructions. Each answer can carry a provenance record (engine version, hash of inputs and result) that the farmer keeps.

*Tailored:* the data (costs, yields, prices, taxes, rents) come from Argentine public sources for each region. The tool speaks the farmer's language and units, and can read the farmer's own field from free Sentinel-2 satellite images.

**Traction and evidence of early product-community fit**
DORA was built in October and November 2026 for Meta's hackathon and evaluated systematically on 36 farmer questions with exact answers, each repeated several times. Results so far, all published with the raw answers:
- **Meta's Muse Spark:** 38 % correct alone, 97 % inside DORA. Four generations of the model all scored 36–38 % alone and 93–100 % inside DORA: the architecture, not the model version, solves the problem.
- **Model size (Qwen2.5, 1.5B to 72B, on our own GPUs):** alone, 5–12 % at every size. Inside DORA, from 0 % to 67 %, with the error falling about 20 % each time the model doubles, up to 32B.
- **An open model (DeepSeek V4.1 Flash):** 9 % alone, 97 % inside DORA, at about USD 0.006 per correct, verified answer.
- **Frontier models through Kaggle's model proxy:** first pilot, the same pattern (Gemini 3 Flash: 1 of 5 alone, 5 of 5 inside DORA).
- **Improving a small model:** two worked examples took a 14B model from 41 % to 71 %. They also cut the wrong answers that pass the verifier from 26 to 7. Forcing the tool call with constrained decoding did not help, and doubled those silent errors for a 7B model.
- **Robustness:** trap questions (missing data, impossible scenarios, pressure): 55 of 55 handled with the verifier; without it, 11 of 55 answers reached the farmer with unsupported numbers.

The open-model experiments (size, DeepSeek, frontier pilot and the improvement test) cost under USD 20 of compute, tracked experiment by experiment in a ledger we will publish. We have not yet tested DORA with real farmers; that is the first goal of the incubator year.

**Challenges and biggest blockers**
1. **Small open models.** Mid-size models build the wrong scenario. Our verifier stops invented numbers but cannot tell that a scenario misrepresents the farmer: the number does come from the solver, only for another problem. Measured: of the answers the verifier accepted, 25 of 52 were wrong with Qwen2.5 14B, against 1 of 36 with DeepSeek V4.1 Flash. Closing this gap needs a larger evaluation set, compute for fine-tuning, and a runtime signal that detects a wrong scenario without knowing the answer.
2. **Real-world validation:** getting farmers and advisers to use it on their own season, and comparing plans with what actually happened at harvest.
3. **Data maintenance:** prices, costs and taxes change every season and need a sustainable, open update process. A daily public refresh already runs.
4. **Running costs** for a free public service.

**Team and relevant experience**
Guillermo Siaira *(reescribir en primera persona y con tu trayectoria)*: economist and developer, independent researcher. Author of earlier research on the shadow prices of capital over a crop season, the basis of DORA's engine. Built DORA's engine, agent, verifier and evaluation, and runs its experiments. Works with AI coding agents under explicit specifications and reviews.

## Impact and Openness

**Success at 12 and 36 months, and how it is measured**
- **12 months:**
  - an open model of 14B parameters or fewer, running on one GPU, reaches at least 90 % correct and verified answers on a public, held-out set of several hundred questions, measured with the same harness used today;
  - the cost and gain of each improvement step is published;
  - at least 30 farmers or advisers have used DORA on their own season;
  - the engine, verifier, question generator and evaluation set are published under an open licence, with documentation.
- **36 months:**
  - plans made at sowing are compared with harvest outcomes for two seasons, and the hits and misses are published;
  - the pattern (solver plus verifier around a small model) has been reused in at least one other planning domain, by us or by others.

**Sustainability**
The open core stays free. Running costs are low because the solver is cheap and the model is small, and a cooperative or an extension service can host its own copy. Paid services for institutions, if any, would be separate from the grant-funded public work.

**What would the $300,000 grant unlock?**
- twelve months of full-time work on the open core and the research;
- compute to evaluate and fine-tune open models of several sizes;
- field work with farmers and advisers in at least two regions;
- the data work to keep regional prices, costs and taxes current and public.

**How code, learnings and data will be shared**
- The code is already public on GitHub (github.com/GuillermoSiaira/dora-farm-agent) under the Apache License 2.0, and everything built during the incubator stays there.
- The evaluation questions, scoring rules and raw results are published with each experiment, as we do today.
- The engine is also available to any AI agent through an open MCP server.
- We will write a report and a paper on the size, accuracy and cost results.

**Novel approaches to AI systems**
- **The model as interviewer and explainer, never a calculator.** A symbolic optimiser produces every number, and a deterministic verifier enforces it before the user sees the answer.
- **Two kinds of checks, never mixed.** The grader that knows the right answer exists only in evaluation, to certify which models are good enough. The runtime verifier, which does not know the answer, protects each user.
- **Improving a small model as an economic question.** Each fix (instructions, examples, fine-tuning) is measured by how many verified answers it buys per dollar, including how many silent errors it adds.

**Link to code, demo or website:** https://github.com/GuillermoSiaira/dora-farm-agent · demo: https://guillermosiaira--dora-web.us-east.modal.run
**Two-minute video:** *(recorte del video del hackathon, punto 4)*
