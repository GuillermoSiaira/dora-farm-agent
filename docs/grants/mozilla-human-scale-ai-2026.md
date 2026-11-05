# Mozilla Human-Scale AI Incubator: borrador de propuesta inicial

**Cierre:** viernes 20/11/2026, 23:59 PST (sábado 21/11, 04:59 hora de Buenos Aires). Formulario: https://mozillafoundation.tfaforms.net/w/humanscaleai
**Estado:** borrador de Claude (5/11), sin revisar por Guillermo. Las respuestas van en inglés (el formulario acepta español, pero el jurado lee inglés).

## Antes de completar: lo que hay que decidir (en español)

1. **Elegibilidad: sí, como individuo desde Argentina.** La guía de elegibilidad de Mozilla dice que financian individuos "based around the world"; solo excluyen países sancionados por OFAC (Argentina no lo está). Requisitos: poder recibir fondos de una organización de EE. UU. por transferencia, cuenta que acepte USD, firmar el acuerdo. La convocatoria pide disponibilidad para una cohorte de 12 meses desde abril de 2027.
2. **La condición que más pesa: propósito caritativo, no comercial.** Mozilla es una 501(c)(3): "we cannot fund work whose primary purpose is commercial gain". Si se presenta DORA como producto a vender, queda afuera. Lo que se puede financiar es **la parte pública**: el motor y el verificador abiertos, el banco de evaluación, la investigación de qué modelo chico alcanza con la arquitectura, y una herramienta gratuita para productores chicos. El servicio MCP pago puede existir aparte, pero la propuesta no lo financia ni lo menciona como objetivo. **Decidido (5/11):** el núcleo queda abierto. El repo `GuillermoSiaira/dora-farm-agent` ya era público pero no tenía licencia (eso equivale a "todos los derechos reservados"); se agregó Apache 2.0 (`LICENSE` y sección en el README).
3. **Puntos débiles, dichos con honestidad en el borrador:** no hay usuarios reales todavía (etapa "working prototype"); hoy DORA depende de una API de frontera (Muse Spark de Meta); Llama 3.1 8B no llamó a las herramientas en nuestra prueba. La propuesta convierte eso en el plan de trabajo: llevar DORA a modelos abiertos chicos y probarlo con productores reales.
4. **Video de 2 minutos:** "fuertemente recomendado" y con prioridad en la evaluación. Se puede recortar del video del hackathon (youtu.be/W4zBWeavPi0), mostrando el verificador frenando un número.
5. **Productores o socios piloto:** si conseguís aunque sea una carta o un correo de un asesor, un grupo CREA o una cooperativa que diga que lo probaría, cambia la sección de tracción. Es lo que más sumaría.
6. **Declaración de IA:** el formulario pregunta si se usó IA para redactar. Hay que responder que sí (borrador asistido por Claude, revisado y editado por vos). Las propuestas "mayormente generadas por IA" pasan por revisión extra: reescribí con tu voz al menos el resumen y el equipo.
7. **Tamaño del modelo:** el formulario pregunta el tamaño del modelo más grande que usa el proyecto. No sé cuántos parámetros tiene Muse Spark 1.3; completalo vos o poné el objetivo del proyecto (10B o menos).

---

## Project Overview

**Proposed Project Title**
DORA: small models that plan a farm season correctly, because a solver does the math and a verifier checks every number

**Project Summary** (short)
Family grain farmers in Argentina make their largest decisions of the year (what to sow, when to sell, whether to borrow or rent out the land) with spreadsheets or with chatbots that invent numbers. DORA is an open agent where the language model only talks: it asks the farmer, builds the scenario and explains the result, while a linear-programming engine plans the season fortnight by fortnight and a deterministic verifier blocks any number in the answer that the engine did not produce. In our evaluation the same Meta model went from 38 % correct answers alone to 97 % inside DORA, and the cost per answer fell by half or more because the model stops doing arithmetic. We want to take this architecture to small open models that a farmers' cooperative can run itself, test it with real farmers, and publish the engine, the verifier and the evaluation set so others can apply the pattern to other high-stakes planning problems.

**Human-Scale AI principles**
- **Small:** the architecture moves the hard part (optimisation, arithmetic) out of the model into a solver that runs in milliseconds on a laptop. The model only has to understand the farmer and call tools. Our next research step is to find the smallest open model that DORA makes reliable.
- **Intentional:** the farmer sees and controls every input; the agent asks before assuming, one question at a time, starting with the one that would be most costly to get wrong; no number reaches the farmer unless it can be traced to the engine. Plans can be recorded as a dated hash so the farmer, not a platform, holds the proof of what was advised.
- **Tailored:** built around Argentine grain farming as it is: fortnightly cash flows, export duties and local taxes, land rent, storage in silo bags, prices from local markets, Spanish voice notes and photos of invoices.

**Project Stage:** Working prototype

**Early signals of product-community fit:** None of these yet *(cambiar si conseguís un socio piloto, ver punto 5)*

**Approximate users:** Less than 100

**Primary Output(s):** Technology platform or tool; Research publication; Dataset

**Frontier API dependence:** Yes (today: Meta's Muse Spark through Meta's API). Removing this dependence is a goal of the project.

**Largest model parameter count:** *(completar; ver punto 7)*

**Charitable purpose:** Yes.
**Public benefit:** Advancing scientific research on how to make small language models reliable for numerical decisions, published openly with code and evaluation data; and a free planning tool for small and medium family farmers who cannot pay for agronomic and financial advice.

**How will you work in the open:** Open sourcing code; publishing research and evaluation data; documenting experiments publicly.

## Project Details

**What technology are you building and how does it address this cohort's theme?**
DORA has three parts. (1) An agent that interviews the farmer in plain Spanish, by text, voice note or a photo of an invoice, and turns that into a structured scenario. (2) A linear-programming engine that plans the whole season in fortnights: hectares per crop and sowing window, when to sell or store each tonne, when to use credit, and the value of each scarce resource (shadow prices of cash, land, storage and credit). It also answers questions farmers actually ask: is it better to rent the land out, and at what price would a crop left out of the plan become worth sowing. (3) A deterministic verifier: every number in the agent's answer must match a tool result or something the farmer said; otherwise the answer goes back to the model for correction before the farmer sees it.
*Small:* the model never computes; a solver does. That is why the same model is both more accurate and cheaper inside DORA. The work we propose is to replace the current API model with small open models (10B parameters or fewer) running on modest hardware, and to measure the accuracy-versus-size curve with and without the architecture.
*Intentional:* the verifier and the question order are explicit, inspectable rules, not prompt instructions. Each answer can carry a provenance record (engine version, hash of inputs and result) that the farmer keeps.
*Tailored:* the data (costs, yields, prices, taxes, rents) come from Argentine public sources for each region, and the tool speaks the farmer's language and units.

**Traction and evidence of early product-community fit**
DORA was built in October–November 2026 for Meta's hackathon and evaluated systematically: 39–41 farmer questions, three to five repetitions each, three conditions (model alone, DORA without verifier, full DORA). Results: 38 % correct answers for the model alone, 97 % for full DORA, with every number verified; four generations of Meta's model all scored 36–38 % alone and 93–100 % inside DORA, which suggests the architecture, not the model version, solves the problem. A robustness test with trap questions (missing data, impossible scenarios, pressure) passed 55 of 55 with the verifier; without it, 11 of 55 answers reached the farmer with unsupported numbers. We have not yet tested DORA with real farmers; that is the first goal of the incubator year.

**Challenges and biggest blockers**
(1) Small open models: our first test with an 8B model failed because it did not call the tools; we need time and compute to test stepped sizes, structured tool calling and light adaptation. (2) Real-world validation: getting farmers and advisers to use it on their own season and comparing plans with what actually happened at harvest. (3) Data maintenance: prices, costs and taxes change every season and need a sustainable, open update process. (4) Running costs for a free public service.

**Team and relevant experience**
Guillermo Siaira *(reescribir en primera persona y con tu trayectoria)*: economist/developer; author of earlier research on shadow prices of capital over a crop season, the basis of DORA's engine. Built DORA's engine, agent, verifier and evaluation. Works with AI coding agents under explicit specs and reviews.

## Impact and Openness

**Success at 12 and 36 months, and how it is measured**
12 months: DORA runs on an open model of 10B parameters or fewer with at least 90 % correct and verified answers on the public evaluation set (measured with the same harness used today); at least 30 farmers or advisers have used it on their own season; the engine, verifier and evaluation set are published under an open licence with documentation. 36 months: plans made at sowing are compared with harvest outcomes for two seasons, and the hits and misses are published; the pattern (solver plus verifier around a small model) has been reused in at least one other planning domain by us or by others.

**Sustainability**
The open core stays free. Running costs are low because the solver is cheap and the model is small; a cooperative or an extension service can host its own copy. Paid services for institutions, if any, would be separate from the grant-funded public work.

**What would the $300,000 grant unlock?**
Twelve months of full-time work on the open core; compute to test open models of several sizes; field work with farmers and advisers in at least two regions; and the data work to keep regional prices, costs and taxes current and public.

**How code, learnings and data will be shared**
The code is already public on GitHub (github.com/GuillermoSiaira/dora-farm-agent) under the Apache License 2.0, and everything built during the incubator stays there; the evaluation questions, scoring rules and raw results published with each experiment, as we do today; a written report of the size-versus-accuracy results.

**Novel approaches to AI systems**
Treating the language model as an interviewer and explainer, never a calculator: a symbolic optimiser produces every number, and a deterministic verifier enforces that before the user sees the answer. The question we want to answer with evidence is how small a model can be once it no longer has to reason numerically.

**Link to code, demo or website:** https://github.com/GuillermoSiaira/dora-farm-agent *(agregar la URL de la app en Modal)*
**Two-minute video:** *(recorte del video del hackathon)*
