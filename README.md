# DORA: a crop-season planning agent

Built during the Meta Global AI Developer Hackathon (build period: Oct 27 – Nov 4, 2026). Everything in this repository was written during the event; the git history starts on Oct 27.

An Argentine grain farmer describes the season (by text, voice note or a photo of a cost sheet). An agent running on a Meta model turns that into a scenario and calls a linear-programming engine that plans the season fortnight by fortnight: how many hectares of each crop, when to sell or store, when to use credit, and what each scarce resource is worth (shadow prices of cash, capital, land, storage and credit). A deterministic verifier checks that every number in the agent's answer comes from the engine.

## Status
- [x] Engine v1: fortnightly cash flow, own capital, credit line, storage, sales timing, shadow prices validated against perturbation.
- [x] Agent tools (JSON in/out, validated inputs, origin of every parameter) and number verifier
- [ ] Agent on a Meta model
- [ ] Photo and voice input
- [ ] Web demo and evaluation set

## Run
```
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest
```

## Data
Costs, yields and prices: public report "Márgenes y Resultados", June 2026, Southeast Buenos Aires, from Argentina's Secretariat of Agriculture (MAGyP). The payment and harvest calendar is an assumption stated in `dora/scenario.py`. Equations, signs and code lines: `docs/model.md`.
