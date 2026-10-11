"""Paired bootstrap CI for micro-F1 of selected strategies (full sample)."""
import sys, json, numpy as np
sys.argv = ["analyze.py", "sample.jsonl", "jev=results/jev.jsonl", "clef=results/clef.jsonl", "clef-flash=results/clef-flash.jsonl"]
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    import analyze as A
strats = {
  "分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個": lambda s, y: A.strat_top1_fallback(s, 0.7, 2),
  "逐類門檻（max F1, CV）": lambda s, y: A.cv_per_label(s, y),
  "逐類門檻（precision ≥ 0.9, CV）": lambda s, y: A.cv_per_label(s, y, min_precision=0.9),
}
rng = np.random.default_rng(1)
B = 1000
Y = A.Yc
print("| 策略 | " + " | ".join(f"{n} micro-F1 [95% CI]" for n in A.P) + " | jev − clef [95% CI] |")
print("|---|" + "---|" * (len(A.P) + 1))
for name, fn in strats.items():
    preds = {n: fn(A.P[n], Y) for n in A.P}
    def f1(pred, idx):
        return A.prf(pred[idx], Y[idx])[2]
    boots = {n: [] for n in A.P}; diff = []
    for _ in range(B):
        idx = rng.integers(0, len(Y), len(Y))
        vals = {n: f1(preds[n], idx) for n in A.P}
        for n in A.P: boots[n].append(vals[n])
        diff.append(vals["jev"] - vals["clef"])
    cells = [f"{f1(preds[n], np.arange(len(Y))):.3f} [{np.percentile(boots[n],2.5):.3f}, {np.percentile(boots[n],97.5):.3f}]" for n in A.P]
    print(f"| {name} | " + " | ".join(cells) + f" | {np.mean(diff):+.3f} [{np.percentile(diff,2.5):+.3f}, {np.percentile(diff,97.5):+.3f}] |")
