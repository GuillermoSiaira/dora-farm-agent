# Texto para el formulario de envío (Cerebral Valley, 4/11, 23:00 de Buenos Aires)

Cada bloque es un campo, listo para copiar. Están en inglés porque el formulario y el jurado son en inglés. Si el formulario pide un campo que no está acá, buscarlo en el README. Los números salen del README y de las fichas de `docs/experimentos/`.

Antes de enviar:
- abrir la app en vivo y confirmar que contesta;
- tener el link del video;
- categoría: Indie.

---

## Project name
DORA: a crop-season planning agent

## Tagline (one line)
A farmer describes the season in words, voice or a photo; Muse Spark builds the scenario, an optimization engine plans it, and every number is verified before the farmer sees it.

## Links
- Live demo: https://guillermosiaira--dora-web.us-east.modal.run
- Code: https://github.com/GuillermoSiaira/dora-farm-agent
- Video: <pegar el link>

## Description
Argentine grain farmers decide every season how many hectares to sow of each crop, whether to rent the land out instead, when to sell or store the harvest and when to take credit. They usually decide with a spreadsheet or with advice that nobody can check. A language model alone gets these numbers wrong: in our tests, Muse Spark alone answered 38 % of the planning questions correctly.

DORA splits the work. The farmer talks to an agent running on Muse Spark 1.3, in Spanish or English, by text, voice note, a photo of an invoice or a field drawn on a map. The agent turns that into a scenario and calls a linear-programming engine (HiGHS) that plans the season fortnight by fortnight: cash, credit, storage, land tenure, sowing windows, climate scenarios and livestock. The engine also returns what each scarce resource is worth (shadow prices of cash, capital, land, storage and credit). A deterministic verifier checks that every number in the agent's answer comes from a tool result before the farmer sees it; if one does not, the agent gets a correction round. When something the farmer did not say could change the plan, the agent asks one question at a time, starting with the one that would cost the most to get wrong, and says what it will assume if the farmer does not know.

The language model talks; the math decides.

## How we used Meta's tools
- **Muse Spark 1.3:** the agent. It holds the conversation, builds the scenario, calls 9 tools and explains the result. It also reads invoice photos line by line (vision).
- **Voice Transcribe:** voice notes from the farmer. With 6 voice notes, the plan came out the same as with the written question 6 of 6 times.
- **SAM 3.1:** measures water on aerial photos of the field, so flooded hectares are not planned. On drawn test images it was within one point of the true share.
- **Muse Spark Open (on Baseten):** the same harness with the open model: 93 % correct, 100 % verified, no impossible plan.
- **Muse Spark 1.3 Contributor:** 95 % correct, 100 % verified; 1.23 USD for the three conditions.
- **Llama 3.1 8B (on Modal):** tested; it does not call the tools, which is written down in the experiment card.

## Results
Each question has a right answer computed by the engine. Everything below has an experiment card with its commit, command, raw output and cost (`docs/experimentos/`).
- **Muse Spark alone vs. DORA** (39 questions × 5 repetitions): alone, 38 % correct and 154 of 180 answers with an unsupported number. Full DORA: 97 % correct, 100 % verified, 0 plans that cannot be carried out.
- **Final run on the frozen model** (41 questions × 3, including livestock): 121 of 123 correct, 123 of 123 verified, 17.8 s median per answer, 5.24 USD for the whole run.
- **Robustness** (11 trap questions × 5): with the verifier, no answer reaches the farmer with unsupported numbers; without it, 11 of 55 do.
- **Invoices:** the cost per hectare was loaded right 6 of 6 times from the photo, against 2 of 6 when the farmer typed it.
- **The interview:** 10 questions in 14 turns over 4 simulated farmers, one question per reply, and every reply verified.

## Technical depth (if there is a field for it)
- An LP engine written for this project: fortnightly cash flow, credit lines, storage, rented vs. owned land, sowing windows, three climate scenarios and livestock in heads (cow-calf, backgrounding, finishing, pasture balance by season).
- A verifier that matches every number in the answer against tool results, with tolerances and a correction round.
- An evaluation harness that runs three conditions on the same question set: A is the model alone, B is DORA without the verifier, C is full DORA. 365 automated tests.
- Prices are fetched live (Chicago and Argentine quotes plus regional basis) and fall back to the last saved ones, with their date.
- Four regions with their export routes and freight: Southeast Buenos Aires, the Pampas core, Iowa and Mato Grosso.

## What is next
- WhatsApp: the webhook is written; the Meta business number could not be verified in time.
- An agent one step ahead: with the farmer's permission, connected to the tax agency or the mail, it updates the plan when a new invoice arrives, before the farmer asks.
- Real invoice and field photos (tests so far used synthetic ones), and checking the livestock data against their sources (marked provisional in the app).

## Prior work
The idea builds on earlier research by the author: a paper on shadow prices of capital over a crop season and a private prototype of the optimizer. No code from that prototype was copied; everything in the repository was written during the event (Oct 27 – Nov 4, 2026), as the git history shows.

## Team
Guillermo Siaira (solo). <agregar rol, ciudad o LinkedIn si el formulario lo pide>
