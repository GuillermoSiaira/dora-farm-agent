"""Usage: python eval/plot_e6.py docs/screenshots/model-comparison.png (needs matplotlib).

Bar chart of E6: each Meta model alone vs inside DORA (numbers from docs/experimentos/2026-10-31-e6-muse-spark-open.md)."""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

out = sys.argv[1]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e1e0d9"
ALONE, DORA = "#2a78d6", "#eb6834"   # categorical slots 1 and 2

models = ["Muse Spark Open\n(Baseten)", "Muse Spark 1.3\n(Meta API)"]
acc_alone = [66 / 180 * 100, 69 / 180 * 100]          # condition A
acc_dora = [182 / 195 * 100, 189 / 195 * 100]          # condition C
cost_alone = [19.15 / 180, 11.69 / 180]                # list price, USD per answer
cost_dora = [5.38 / 195, 6.54 / 195]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "text.color": INK,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
fig, axes = plt.subplots(1, 2, figsize=(12, 6.2), facecolor=SURFACE)
w, gap = 0.36, 0.02


def panel(ax, a, d, title, fmt, ymax):
    ax.set_facecolor(SURFACE)
    for i in range(2):
        for x, v, c in ((i - w / 2 - gap / 2, a[i], ALONE), (i + w / 2 + gap / 2, d[i], DORA)):
            ax.add_patch(FancyBboxPatch((x - w / 2, 0), w, v, boxstyle="round,pad=0,rounding_size=0.03",
                                        mutation_aspect=ymax / 3, fc=c, ec="none"))
            ax.text(x, v + ymax * 0.015, fmt(v), ha="center", va="bottom", fontsize=13, color=INK, weight="bold")
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, ymax)
    ax.set_xticks([0, 1], models)
    ax.set_title(title, loc="left", fontsize=14, color=INK, pad=12)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0)


panel(axes[0], acc_alone, acc_dora, "Correct answers", lambda v: f"{v:.0f}%", 110)
axes[0].set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
panel(axes[1], cost_alone, cost_dora, "Cost per answer (USD, list price)", lambda v: f"${v:.3f}", 0.125)
axes[1].set_yticks([0, 0.025, 0.05, 0.075, 0.1], ["0", "0.025", "0.05", "0.075", "0.10"])

handles = [plt.Rectangle((0, 0), 1, 1, fc=ALONE), plt.Rectangle((0, 0), 1, 1, fc=DORA)]
fig.legend(handles, ["Model alone", "Model inside DORA (engine + verifier)"], loc="upper left",
           bbox_to_anchor=(0.06, 0.885), ncol=2, frameon=False, fontsize=12)
fig.suptitle("Same Meta models: DORA makes them right, and cheaper per answer", x=0.06, ha="left",
             fontsize=17, weight="bold", y=0.975)
fig.text(0.06, 0.02, "E6, 31/10/2026. Alone: 36 questions x 5 runs (180). Inside DORA: 39 questions x 5 runs (195); "
         "100% of the answers shown were verified, 0 impossible plans.\nBoth models cost the same per token; "
         "the difference per answer comes from how much each one writes.",
         fontsize=10, color=INK2, ha="left")
fig.subplots_adjust(left=0.06, right=0.98, top=0.76, bottom=0.2, wspace=0.18)
fig.savefig(out, dpi=150, facecolor=SURFACE)
print("saved", out)
