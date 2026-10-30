"""Analyze model outputs against ground truth and print GitHub-flavoured markdown.

usage: python3 -I analyze.py <sample.jsonl> <name>=<res.jsonl> [...]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import KEY2TITLE, KEYS  # noqa: E402

PRICE_IN = {"jev": 0.042, "clef": 0.24, "clef-flash": 0.038, "openai": 0.10}  # USD per M input tokens; output free
THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]

sample = [json.loads(l) for l in open(sys.argv[1])]
idx = {a["id"]: i for i, a in enumerate(sample)}
Y = np.array([[k in a["labels"] for k in KEYS] for a in sample], dtype=bool)
is_random = np.array([a["stratum"] == "random" for a in sample])

runs = {}
for arg in sys.argv[2:]:
    name, path = arg.split("=", 1)
    recs = {}
    for line in open(path):
        r = json.loads(line)
        if r.get("scores"):
            recs[r["id"]] = r
    runs[name] = recs

# evaluate on articles every model answered
common = sorted(set.intersection(*(set(r) for r in runs.values())), key=idx.get)
rows = np.array([idx[i] for i in common])
Yc, randc = Y[rows], is_random[rows]
P = {n: np.array([runs[n][i]["scores"] for i in common]) for n in runs}


def prf(pred, y):
    tp = (pred & y).sum()
    fp = (pred & ~y).sum()
    fn = (~pred & y).sum()
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def macro(pred, y):
    vals = [prf(pred[:, j], y[:, j]) for j in range(y.shape[1]) if y[:, j].any()]
    return tuple(np.mean([v[i] for v in vals]) for i in range(3))


def topk_mask(s, k):
    m = np.zeros_like(s, dtype=bool)
    order = np.argsort(-s, axis=1)[:, :k]
    np.put_along_axis(m, order, True, axis=1)
    return m


def strat_global(s, t, k=None):
    pred = s >= t
    if k:
        pred &= topk_mask(s, k)
    return pred


def strat_top1_fallback(s, t, k):
    """>= t capped at top-k; if nothing passes, still take the argmax (always output >=1 label)."""
    pred = strat_global(s, t, k)
    pred |= topk_mask(s, 1) & ~pred.any(axis=1, keepdims=True)
    return pred


def fit_per_label(s, y, min_precision=None):
    """Per-label threshold: max F1, or the lowest threshold with precision >= min_precision."""
    grid = np.round(np.arange(0.05, 0.99, 0.01), 2)
    th = np.full(s.shape[1], 0.99)
    for j in range(s.shape[1]):
        best, best_t = -1, 0.99
        for t in grid:
            p, r, f = prf(s[:, j] >= t, y[:, j])
            if min_precision is None:
                if f > best:
                    best, best_t = f, t
            elif p >= min_precision and (s[:, j] >= t).sum() >= 3:
                best_t = t
                break
        th[j] = best_t
    return th


def cv_per_label(s, y, k=None, min_precision=None, folds=5, seed=0):
    """Out-of-fold predictions with per-label thresholds fitted on the other folds."""
    rng = np.random.default_rng(seed)
    fold = rng.integers(0, folds, len(s))
    pred = np.zeros_like(y)
    for f in range(folds):
        tr, te = fold != f, fold == f
        th = fit_per_label(s[tr], y[tr], min_precision)
        pred[te] = s[te] >= th
        if k:
            pred[te] &= topk_mask(s[te], k)
    return pred


def fmt(x):
    return f"{x:.3f}"


out = []
w = out.append
n_art = len(common)
w(f"評估篇數：**{n_art}**（所有模型皆成功回應者；其中隨機抽樣 {randc.sum()} 篇、補足稀有類別 {n_art - randc.sum()} 篇），"
  f"正例標籤數 {Yc.sum()}，平均每篇 {Yc.sum() / n_art:.2f} 個標籤。\n")

# ---------- 1. global threshold sweep ----------
w("### 單一門檻掃描（所有類別共用同一門檻）\n")
w("Micro = 把所有 (文章, 類別) 配對攤平計算；Macro = 每個類別各算再平均（稀有類別權重與大類別相同）。\n")
w("| 門檻 | " + " | ".join(f"{n} micro P / R / F1" for n in runs) + " |")
w("|---:|" + "---|" * len(runs))
for t in THRESHOLDS:
    cells = []
    for n in runs:
        p, r, f = prf(strat_global(P[n], t), Yc)
        cells.append(f"{fmt(p)} / {fmt(r)} / **{fmt(f)}**")
    w(f"| {t} | " + " | ".join(cells) + " |")
w("")
w("| 門檻 | " + " | ".join(f"{n} macro P / R / F1" for n in runs) + " |")
w("|---:|" + "---|" * len(runs))
for t in THRESHOLDS:
    cells = []
    for n in runs:
        p, r, f = macro(strat_global(P[n], t), Yc)
        cells.append(f"{fmt(p)} / {fmt(r)} / **{fmt(f)}**")
    w(f"| {t} | " + " | ".join(cells) + " |")
w("")

# ---------- 2. ranking quality ----------
w("### 排序品質（與門檻無關）\n")
w("| 模型 | Top-1 命中率 | Top-3 至少命中 1 個 | 平均每篇正例數 vs 平均分數>0.5 個數 | 逐類 ROC-AUC 平均 |")
w("|---|---:|---:|---:|---:|")


def auc(s, y):
    pos, neg = s[y], s[~y]
    if not len(pos) or not len(neg):
        return np.nan
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1
    return (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


for n in runs:
    s = P[n]
    top1 = Yc[np.arange(len(s)), s.argmax(1)].mean()
    top3 = (topk_mask(s, 3) & Yc).any(1).mean()
    aucs = [auc(s[:, j], Yc[:, j]) for j in range(len(KEYS))]
    w(f"| {n} | {fmt(top1)} | {fmt(top3)} | {Yc.sum(1).mean():.2f} vs {(s > 0.5).sum(1).mean():.2f} | {np.nanmean(aucs):.3f} |")
w("")

# ---------- 3. selection strategies ----------
w("### 最終結果選擇策略比較\n")
w("逐類門檻（per-label）以 5-fold cross validation 計算：在其餘 4 折上找門檻、套用在留出的那一折，避免在同一批資料上調參造成的樂觀偏差。\n")
strategies = []
for t in (0.5, 0.7, 0.8, 0.9):
    strategies.append((f"分數 ≥ {t}", lambda s, t=t: strat_global(s, t)))
for t in (0.5, 0.7, 0.8):
    strategies.append((f"分數 ≥ {t}，最多取前 3", lambda s, t=t: strat_global(s, t, 3)))
    strategies.append((f"分數 ≥ {t}，最多取前 2", lambda s, t=t: strat_global(s, t, 2)))
strategies.append(("分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個", lambda s: strat_top1_fallback(s, 0.7, 2)))
strategies.append(("只取最高分 1 個", lambda s: topk_mask(s, 1)))
strategies.append(("逐類門檻（max F1, CV）", None))
strategies.append(("逐類門檻（max F1, CV），最多前 3", "pl3"))
strategies.append(("逐類門檻（precision ≥ 0.9, CV）", "p90"))

best = {}
w("| 策略 | " + " | ".join(f"{n} P / R / F1（每篇標籤數）" for n in runs) + " |")
w("|---|" + "---|" * len(runs))
for name, fn in strategies:
    cells = []
    for n in runs:
        s = P[n]
        if fn is None:
            pred = cv_per_label(s, Yc)
        elif fn == "pl3":
            pred = cv_per_label(s, Yc, k=3)
        elif fn == "p90":
            pred = cv_per_label(s, Yc, min_precision=0.9)
        else:
            pred = fn(s)
        p, r, f = prf(pred, Yc)
        best.setdefault(n, []).append((f, name, pred))
        cells.append(f"{fmt(p)} / {fmt(r)} / **{fmt(f)}** ({pred.sum(1).mean():.2f})")
    w(f"| {name} | " + " | ".join(cells) + " |")
w("")

# natural distribution subset
w("**僅看隨機抽樣子集（接近實際分布）時的表現：**\n")
w("| 策略 | " + " | ".join(f"{n} P / R / F1" for n in runs) + " |")
w("|---|" + "---|" * len(runs))
for i, (name, _fn) in enumerate(strategies):
    cells = []
    for n in runs:
        pred = best[n][i][2]
        p, r, f = prf(pred[randc], Yc[randc])
        cells.append(f"{fmt(p)} / {fmt(r)} / **{fmt(f)}**")
    w(f"| {name} | " + " | ".join(cells) + " |")
w("")

# ---------- 4. per-label ----------
w("### 逐類表現\n")
w("「max F1 門檻」是在整個樣本上找的最佳門檻（樂觀估計，僅供設定參考）；「P≥0.9 門檻」是達到 precision 0.9 的最低門檻（— 表示達不到）。\n")
for n in runs:
    s = P[n]
    th_f1 = fit_per_label(s, Yc)
    th_p9 = fit_per_label(s, Yc, 0.9)
    w(f"<details><summary><b>{n}</b> 逐類 P / R / F1</summary>\n")
    w("| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |")
    w("|---|---:|---:|---|---|---|")
    for j, k in enumerate(KEYS):
        y = Yc[:, j]
        p5 = prf(s[:, j] >= 0.5, y)
        pf = prf(s[:, j] >= th_f1[j], y)
        reach = prf(s[:, j] >= th_p9[j], y)
        p9 = f"{th_p9[j]:.2f} → {fmt(reach[1])}" if reach[0] >= 0.9 else "—"
        w(f"| {KEY2TITLE[k]} | {y.sum()} | {auc(s[:, j], y):.3f} | {' / '.join(map(fmt, p5))} | "
          f"{th_f1[j]:.2f} → {' / '.join(map(fmt, pf))} | {p9} |")
    w("\n</details>\n")

# ---------- 5. calibration ----------
w("### 校準（reliability）\n")
w("把所有 (文章, 類別) 的分數分箱，比較「平均預測分數」與「實際為正例的比例」。完美校準時兩者相等。\n")
bins = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0001]
w("| 分數區間 | " + " | ".join(f"{n} 筆數 / 平均分數 / 實際正例率" for n in runs) + " |")
w("|---|" + "---|" * len(runs))
for lo, hi in zip(bins[:-1], bins[1:]):
    cells = []
    for n in runs:
        s = P[n].ravel()
        y = Yc.ravel()
        m = (s >= lo) & (s < hi)
        cells.append(f"{m.sum()} / {s[m].mean():.2f} / {y[m].mean():.2f}" if m.any() else "0 / – / –")
    w(f"| [{lo}, {min(hi, 1.0):.1f}) | " + " | ".join(cells) + " |")
w("")

# ---------- 6. cost & latency ----------
w("### 成本\n")
w("| 模型 | input 單價 (USD/M) | 每篇 input tokens 平均 / p95 | 每篇 output tokens | 每篇成本 | 每 1,000 篇 | 每月 10,000 篇 | 本次實驗實際花費 |")
w("|---|---:|---:|---:|---:|---:|---:|---:|")
for n in runs:
    toks = np.array([runs[n][i]["usage"]["input_tokens"] for i in runs[n]])
    otoks = np.array([runs[n][i]["usage"].get("output_tokens", 0) for i in runs[n]])
    price = PRICE_IN[n.removesuffix("-a").removesuffix("-b")]
    per = toks.mean() * price / 1e6
    w(f"| {n} | {price} | {toks.mean():.0f} / {np.percentile(toks, 95):.0f} | {otoks.mean():.0f}（免費） | "
      f"${per:.6f} | ${per * 1000:.3f} | ${per * 10000:.2f} | ${toks.sum() * price / 1e6:.3f} |")
w("")

print("\n".join(out))
