"""The cut list of the DORA demo video: scenes, narration and which part of each take.

Times come from the markers record.py saved, so a retake only needs edit.py again
(and a look at the narration if the numbers on screen changed).
"""
from edit import Scene, Seg, take, wait


def chat_turns(tk_name: str, scene: str, n: int, read: float = 2.2) -> list[Seg]:
    """n chat turns: typing at real speed, the wait sped up, then `read` s on the answer."""
    tk = take(tk_name)
    segs = []
    for k in range(n):
        typing = [m["t"] for m in tk.all(scene, "typing")]
        sent = tk.t(scene, "sent", k)
        start = typing[k] - 0.4 if k < len(typing) and typing[k] < sent else sent - 1.0
        segs.append(Seg(tk_name, start, sent + 0.3, speed=2.0))
        segs.append(wait(tk_name, scene, k, target=1.6))
        ans = tk.t(scene, "answer", k)
        segs.append(Seg(tk_name, ans, ans + read))
    return segs


def SCENES() -> list[Scene]:
    es, en = "chat_es", "chat_en"
    t_es, t_en = take(es), take(en)
    n_es = len(t_es.all("es", "answer"))
    n_inv = len(t_es.all("invoice", "answer"))
    return [
        Scene(
            "intro",
            "An Argentine farmer has to decide, months ahead, what to sow, when to sell, "
            "and whether the cash lasts until harvest. Ask a chatbot the same question five times, "
            "and you get five different numbers.",
            card=("DORA", ["A crop-season planning agent", "built on Meta's Muse Spark"],
                  "Meta Global AI Developer Hackathon · 2026"),
            segs=[Seg(es, ("es", "empty chat", 0, -0.5), ("es", "typing", 0, -0.3))],
        ),
        Scene(
            "idea",
            "DORA splits the job. Muse Spark talks with the farmer and builds the scenario. "
            "A linear-programming engine computes the plan, fortnight by fortnight. "
            "And a verifier checks that every number in the answer came from the engine. "
            "The model talks; the math decides.",
            segs=[Seg("readme", ("readme", "how", 0, -0.8), ("readme", "e1", 0, -1.0))],
        ),
        Scene(
            "interview",
            "Here the farmer writes in Spanish. Instead of guessing, DORA asks one question at a time, "
            "starting with the one that would cost the most to get wrong, and says what it will assume "
            "if he doesn't know. When nothing left can move the plan, it stops and answers: "
            "hectares per crop, present value, what limits him, cash between November and April, "
            "and what renting the land out would pay instead.",
            label="Spanish  ·  Muse Spark 1.3 (Meta API)",
            segs=chat_turns(es, "es", n_es) + [Seg(es, ("es", "plan", 0), ("es", "plan", 0, 5.0))],
        ),
        Scene(
            "invoice",
            "Farmers don't type spreadsheets. DORA reads an invoice photo line by line. "
            "When it can't tell which crop it is for, it asks. Here, wheat fertilizer at a hundred forty dollars "
            "a hectare, against two hundred fourteen in the region, and the plan improves. "
            "Voice notes work too: the farmer says, in Spanish, that he has a silo and more capital, "
            "and DORA now stores grain until July.",
            label="Invoice photo and voice note",
            segs=[Seg(es, ("invoice", "invoice attached", 0, -6.0), ("invoice", "typing", 0, -0.3), speed=2.0)]
            + chat_turns(es, "invoice", n_inv)
            + [Seg(es, ("invoice", "result", 0), ("invoice", "result", 0, 4.0)),
               Seg(es, ("voice", "voice attached", 0, -3.0), ("voice", "sent", 0, 0.3), speed=2.0),
               wait(es, "voice", 0, target=1.6),
               Seg(es, ("voice", "result", 0), ("voice", "result", 0, 4.0))],
        ),
        Scene(
            "english",
            "The same agent speaks English, and runs on another Meta model: Muse Spark Open, served on Baseten. "
            "Asked whether to farm or rent out, it compares both: renting is worth three hundred eighty-five thousand dollars "
            "of present value, against two hundred fifty-eight thousand if he farms. "
            "Then it gives the price corn would need for sowing to beat the rent: "
            "two hundred fourteen dollars and fifty cents a tonne at the port, seventeen percent above today.",
            label="English  ·  Muse Spark Open (Baseten)",
            segs=[Seg(en, ("en", "english", 0, -2.5), ("en", "typing", 0, -0.3), speed=1.5)]
            + chat_turns(en, "en", 1)
            + [Seg(en, ("en", "plan", 0), ("en", "plan", 0, 5.0))]
            + chat_turns(en, "breakeven", 1)
            + [Seg(en, ("breakeven", "result", 0), ("breakeven", "result", 0, 5.0))],
        ),
        Scene(
            "scenario",
            "Every plan can be opened in the Scenario tab, from the date the farmer picks: "
            "what renting would pay, what an extra dollar returns in each fortnight, cash and debt, "
            "and which taxes are already inside the present value.",
            label="Scenario tab",
            segs=[Seg("scenario", ("scenario", "computing", 0, -0.8), ("end", "done", 0), speed=2.8)],
        ),
        Scene(
            "regions",
            "The same engine compares regions with their own prices, freight and export routes: "
            "return on capital and freight to port for Balcarce, Pergamino, Iowa and Mato Grosso.",
            label="Regional Observatory",
            segs=[Seg("regions", ("regions", "map", 0, -0.5), ("regions", "route", 1, 1.5), speed=1.4)],
        ),
        Scene(
            "results",
            "We measured it. Muse Spark alone got thirty-eight percent of our questions right, "
            "and proposed nine plans that cannot be carried out. Inside DORA: ninety-seven percent, "
            "every answer verified, and no impossible plan. On the frozen final model, "
            "a hundred twenty-one out of a hundred twenty-three, for five dollars for the whole run. "
            "Across four generations of Muse Spark, the gain comes from the architecture, not from a newer model.",
            segs=[Seg("readme", ("readme", "e1", 0, -0.5), ("end", "done", 0))],
        ),
        Scene(
            "close",
            "Next: DORA on WhatsApp, and an agent one step ahead, that updates the plan "
            "when the accountant loads a new invoice. DORA: the model talks, the math decides.",
            card=("DORA", ["The model talks; the math decides.",
                           "guillermosiaira--dora-web.us-east.modal.run",
                           "github.com/GuillermoSiaira/dora-farm-agent"], ""),
            min_seconds=6.0,
        ),
    ]
