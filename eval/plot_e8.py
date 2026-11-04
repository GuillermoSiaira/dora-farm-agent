"""E8 chart: four Meta models alone vs inside DORA (correct answers and output tokens per answer)."""
import matplotlib.pyplot as plt

models = ["Muse Spark 1.1", "Muse Spark 1.2", "Muse Spark 1.3", "Muse Spark Open"]
alone = [12 / 33, 12 / 33, 69 / 180, 66 / 180]          # E8 (1 run) and E1/E6 (5 runs)
dora = [36 / 36, 34 / 36, 189 / 195, 182 / 195]
out_alone = [19069, 14225, None, None]                    # output tokens per answer, E8 only
out_dora = [4660, 3570, None, None]

fig, ax = plt.subplots(figsize=(10, 5.2))
x = range(len(models))
w = 0.38
b1 = ax.bar([i - w / 2 for i in x], [v * 100 for v in alone], w, color="#2a78d6", label="Model alone")
b2 = ax.bar([i + w / 2 for i in x], [v * 100 for v in dora], w, color="#eb6834", label="Model inside DORA (engine + verifier)")
for bars in (b1, b2):
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.5, f"{b.get_height():.0f}%", ha="center", fontsize=11, fontweight="bold")
ax.set_xticks(list(x)); ax.set_xticklabels(models, fontsize=11)
ax.set_ylim(0, 125); ax.set_ylabel("Correct answers (%)")
ax.spines[["top", "right"]].set_visible(False); ax.yaxis.grid(True, color="#e5e5e5"); ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper left", ncols=2)
ax.set_title("Four Meta models: alone they get about 4 in 10 right; inside DORA, 94-100%", fontsize=13, fontweight="bold", loc="left")
fig.text(0.01, 0.01, "E8 (4/11/2026): 1.1 and 1.2, E1 questions x 1 run (alone 33 scored, DORA 36). 1.3 and Open: E1/E6, x 5 runs (180 / 195).\n"
         "Output tokens per answer, E8: 1.1 19,069 alone vs 4,660 in DORA; 1.2 14,225 vs 3,570.", fontsize=8.5, color="#444")
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig("docs/screenshots/e8-generations.png", dpi=150)
