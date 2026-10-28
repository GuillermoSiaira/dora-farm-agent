# Where DORA is going

## What DORA is today
An analyst for a farm business that takes any kind of input and turns it into the numbers of one model:
- a farmer's words, typed or spoken (Muse Spark and Meta's voice model),
- photos of invoices,
- a field drawn on a map,
- vertical aerial photos of the field, measured with SAM 3.1,
- market data (futures, local basis, freight routes, land prices, taxes) for four regions.

The model is always the same: a linear program over 30 fortnights whose cash equation makes money worth something different in each fortnight. What changes from one farm to another is the data and the constraints. The language model never computes: it formulates the scenario, reads the engine's results and explains them, and a verifier checks every number it writes.

## Where it should go: situational awareness
An analyst is not only someone who answers. A good one notices what the farmer did not ask about: that a strong El Niño year raises the risk of flooding in southeastern South America; that selling forward covers part of that risk; that the supplier's 90-day term is cheaper than the money the farmer lacks in October. We call this **situational awareness**: reading the context, seeing the risk, and deciding with it. It can be measured and trained.

Three steps:

1. **Climate as scenarios.** National services publish seasonal outlooks as probabilities of drier, normal or wetter months: SMN in Argentina, NOAA CPC in the United States, INMET and CPTEC in Brazil. Crossed with each district's yield history in dry, normal and wet years (MAGyP, USDA NASS, IBGE and CONAB), they give a few yield scenarios with probabilities for the farm in question. The engine then plans against all of them at once: what is decided now (crops, forward sales, supplier terms) is one decision; what comes later (when to sell, how much credit) adapts to each scenario. This is two-stage stochastic programming, the natural extension of the current model. The farmer gets a plan that holds in the three climates, the loss in each, how much to cover, and what the forecast is worth. Weather radar (INTA, SMN, NOAA, CEMADEN) helps to know where to look; the damage itself is measured from vertical photos, as SAM 3.1 does today.

2. **Training data from an exact engine.** Every scenario the engine solves has an exact answer. That makes it possible to generate many examples (the farmer's question, the right scenario, the result, an explanation that uses only the result's numbers) covering each financial and agronomic decision, with the verifier as an automatic grader. Examples that fail the verifier are discarded or corrected.

3. **Small models that run locally.** With that data, a small open model (an open Llama or Muse Spark model) can be fine-tuned to formulate scenarios and to raise the questions a good analyst raises, and run on a farm's own computer or a cooperative's server. The data is the hard part to copy: it comes from an exact engine, not from text found online.

## What we do not claim
- DORA does not estimate national production. The grain exchanges, MAGyP, USDA and CONAB already do; DORA takes their estimates as data and answers what they mean for one farm or one region.
- Data marked as provisional in `dora/data` stays provisional until read in its source, and the agent says so.
- The engine's answers are as good as its coefficients. For a farm's real decisions, its own costs and terms replace the regional defaults.
