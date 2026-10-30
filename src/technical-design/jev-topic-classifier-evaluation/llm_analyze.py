"""Evaluate LLM list outputs (Haiku 5.5) against ground truth, side by side with decision-model strategies.

usage: python3 -I llm_analyze.py <sample.jsonl> <name>=<llm_res.jsonl> [...] -- <name>=<decision_res.jsonl> [...]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import KEY2TITLE, KEYS  # noqa: E402

PRICE = {"in": 0.10, "out": 0.50}  # Claude Haiku 5.5, USD per M tokens (prompts up to 100K)

args = sys.argv[1:]
sample = [json.loads(l) for l in open(args[0])]
sep = args.index("--") if "--" in args else len(args)
llm_args, dm_args = args[1:sep], args[sep + 1:]
idx = {a["id"]: i for i, a in enumerate(sample)}
Y = np.array([[k in a["labels"] for k in KEYS] for a in sample], dtype=bool)
RAND = np.array([a["stratum"] == "random" for a in sample])


def prf(pred, y):
    tp = (pred & y).sum(); fp = (pred & ~y).sum(); fn = (~pred & y).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def macro(pred, y):
    vals = [prf(pred[:, j], y[:, j]) for j in range(y.shape[1]) if y[:, j].any()]
    return tuple(float(np.mean([v[i] for v in vals])) for i in range(3))


llm = {}
for a in llm_args:
    name, path = a.split("=", 1)
    recs = {}
    for line in open(path):
        r = json.loads(line)
        if r.get("categories") is not None:
            recs[r["id"]] = r
    llm[name] = recs
dm = {}
for a in dm_args:
    name, path = a.split("=", 1)
    dm[name] = {json.loads(l)["id"]: json.loads(l) for l in open(path) if '"scores"' in l}

common = sorted(set.intersection(*(set(r) for r in list(llm.values()) + list(dm.values()))), key=idx.get)
rows = np.array([idx[i] for i in common])
Yc, Rc = Y[rows], RAND[rows]
PRED = {n: np.array([[k in llm[n][i]["categories"] for k in KEYS] for i in common]) for n in llm}
SC = {n: np.array([dm[n][i]["scores"] for i in common]) for n in dm}

out = []
w = out.append
w(f"評估篇數：{len(common)}（所有模型皆成功回應者）。\n")
w("| 模型 | 樣本 | micro P / R / F1 | macro P / R / F1 | 每篇標籤數 | 空陣列比例 |")
w("|---|---|---|---|---:|---:|")
for n, pred in PRED.items():
    for sub, m in (("全部", np.ones(len(Yc), bool)), ("隨機子集", Rc)):
        p, r, f = prf(pred[m], Yc[m]); mp, mr, mf = macro(pred[m], Yc[m])
        w(f"| {n} | {sub} | {p:.3f} / {r:.3f} / **{f:.3f}** | {mp:.3f} / {mr:.3f} / {mf:.3f} | {pred[m].sum(1).mean():.2f} | {(pred[m].sum(1) == 0).mean():.1%} |")
w("")

# decision models at the threshold that matches the LLM's recall / precision
w("**同等 recall / precision 下的對照**（決策模型掃描單一門檻，找出 recall 或 precision 最接近 LLM 的那一點）：\n")
w("| LLM | LLM P / R | 決策模型 | 同 recall 時的 P（門檻） | 同 precision 時的 R（門檻） |")
w("|---|---|---|---|---|")
grid = np.round(np.arange(0.02, 0.99, 0.01), 2)
for n, pred in PRED.items():
    lp, lr, _ = prf(pred, Yc)
    for d, s in SC.items():
        pts = [(t, *prf(s >= t, Yc)) for t in grid]
        tr = min(pts, key=lambda x: abs(x[2] - lr))
        tp_ = min(pts, key=lambda x: abs(x[1] - lp))
        w(f"| {n} | {lp:.3f} / {lr:.3f} | {d} | {tr[1]:.3f}（{tr[0]:.2f}） | {tp_[2]:.3f}（{tp_[0]:.2f}） |")
w("")

# per label
w("| 類別 | 正例 | " + " | ".join(f"{n} P / R / F1" for n in PRED) + " |")
w("|---|---:|" + "---|" * len(PRED))
for j, k in enumerate(KEYS):
    cells = []
    for n, pred in PRED.items():
        p, r, f = prf(pred[:, j], Yc[:, j])
        cells.append(f"{p:.3f} / {r:.3f} / {f:.3f}")
    w(f"| {KEY2TITLE[k]} | {Yc[:, j].sum()} | " + " | ".join(cells) + " |")
w("")

# cost & latency
w("| 模型 | 每篇 input tokens 平均 / p95 | 每篇 output tokens 平均 / p95 | 每篇成本 | 每 1 萬篇 | 延遲 p50 / p90 / p99 / max | 失敗 |")
w("|---|---:|---:|---:|---:|---|---:|")
for n in llm:
    rs = list(llm[n].values())
    ti = np.array([r["usage"]["input_tokens"] for r in rs]); to = np.array([r["usage"]["output_tokens"] for r in rs])
    lat = np.array([r["latency_s"] for r in rs])
    per = (ti.mean() * PRICE["in"] + to.mean() * PRICE["out"]) / 1e6
    q = np.percentile(lat, [50, 90, 99])
    w(f"| {n} | {ti.mean():.0f} / {np.percentile(ti, 95):.0f} | {to.mean():.0f} / {np.percentile(to, 95):.0f} | ${per:.6f} | ${per * 1e4:.2f} | "
      f"{q[0]:.2f}s / {q[1]:.2f}s / {q[2]:.2f}s / {lat.max():.2f}s | {len(sample) - len(rs)} |")
print("\n".join(out))
