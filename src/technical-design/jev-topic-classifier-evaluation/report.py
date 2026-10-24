"""Print the markdown tables of §7: every approach side by side.

usage: python3 -I report.py <sample.jsonl>
(sample.jsonl as produced by sample.py; results/ must hold the files listed in DECISION / LLM below)
"""
import contextlib
import io
import json
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
SAMPLE = sys.argv[1]

# decision models: one confidence per category
DECISION = {
    "jev-a": ("Jev", "A", 0.042, 0),
    "jev-b": ("Jev", "B", 0.042, 0),
    "clef-a": ("Clef", "A", 0.24, 0),
    "clef-b": ("Clef", "B", 0.24, 0),
    "clef-flash-a": ("clef-flash", "A", 0.038, 0),
    "openai-a": ("OpenAI Decisions", "A", 0.10, 0),
    "openai-b": ("OpenAI Decisions", "B", 0.10, 0),
}
# LLM list: a set of categories, no confidence
LLM = {
    "haiku-low": ("Claude Haiku 5.5（effort low）", "B 的條件", 0.10, 0.50),
    "haiku-medium": ("Claude Haiku 5.5（effort medium）", "B 的條件", 0.10, 0.50),
}
SEQ = {"jev-a": "latency_jev-a.jsonl", "clef-a": "latency_clef-a.jsonl", "clef-flash-a": "latency_clef-flash-a.jsonl",
       "haiku-low": "latency_haiku-low.jsonl", "openai-a": "latency_openai-a.jsonl"}

sys.argv = ["analyze.py", SAMPLE] + [f"{k}=results/{k}.jsonl" for k in DECISION]
with contextlib.redirect_stdout(io.StringIO()):
    import analyze as A  # noqa: E402
from labels import KEY2TITLE, KEYS  # noqa: E402

Y, RAND, ids = A.Yc, A.randc, A.common
ALL = np.ones(len(Y), bool)


def ok_rows(path):
    out = []
    for line in open(path):
        r = json.loads(line)
        if r.get("scores") or r.get("categories") is not None:
            out.append(r)
    return out


LP = {}
for k in LLM:
    rr = {r["id"]: r for r in ok_rows(f"results/{k}.jsonl")}
    LP[k] = np.array([[c in rr[i]["categories"] for c in KEYS] for i in ids])

f3 = lambda x: f"{x:.3f}"  # noqa: E731
STRATS = {
    "rule": ("分數 ≥ 0.7，最多前 2 個；都沒過則取最高 1 個", lambda s: A.strat_top1_fallback(s, 0.7, 2)),
    "plf1": ("逐類門檻（max F1, CV）", lambda s: A.cv_per_label(s, Y)),
    "plp90": ("逐類門檻（precision ≥ 0.9, CV）", lambda s: A.cv_per_label(s, Y, min_precision=0.9)),
}
PRED = {(k, sid): fn(A.P[k]) for k in DECISION for sid, (_, fn) in STRATS.items()}
for k in LLM:
    PRED[(k, "list")] = LP[k]


def cost_lat(k, pin, pout):
    rs = ok_rows(f"results/{k}.jsonl")
    ti = np.array([r["usage"]["input_tokens"] for r in rs]); to = np.array([r["usage"].get("output_tokens", 0) for r in rs])
    lat = np.array([r["latency_s"] for r in rs])
    per = (ti.mean() * pin + to.mean() * pout) / 1e6
    return dict(ti=ti, to=to, lat=lat, per=per)


CL = {k: cost_lat(k, v[2], v[3]) for k, v in {**DECISION, **LLM}.items()}
out = []
w = out.append


def section(title):
    w(f"\n<!-- ===== {title} ===== -->\n")


# ---------- overview ----------
section("overview")
w("| 方案 | 做法 | 題目 | 逐類 AUC 平均 | 規則 F1 | 逐類門檻 F1 | P≥0.9 設定（隨機子集）P / R | 每篇標籤數 | 每 1 萬篇 | 延遲 p50 | 可調門檻 |")
w("|---|---|---|---:|---:|---:|---|---:|---:|---:|:---:|")
for k, (name, prompt, *_rest) in DECISION.items():
    s = A.P[k]
    aucs = np.nanmean([A.auc(s[:, j], Y[:, j]) for j in range(len(KEYS))])
    rule = A.prf(PRED[(k, "rule")], Y)[2]
    pl = A.prf(PRED[(k, "plf1")], Y)[2]
    p9 = A.prf(PRED[(k, "plp90")][RAND], Y[RAND])
    lpa = PRED[(k, "rule")].sum(1).mean()
    w(f"| `{k}` | {name}（決策模型） | {prompt} | {aucs:.3f} | {f3(rule)} | {f3(pl)} | {f3(p9[0])} / {f3(p9[1])} | {lpa:.2f} | "
      f"${CL[k]['per'] * 1e4:.2f} | {np.percentile(CL[k]['lat'], 50):.2f}s | ✓ |")
for k, (name, prompt, *_rest) in LLM.items():
    f = A.prf(LP[k], Y)[2]
    w(f"| `{k}` | {name}（LLM 輸出清單） | {prompt} | — | {f3(f)}（清單） | — | — | {LP[k].sum(1).mean():.2f} | "
      f"${CL[k]['per'] * 1e4:.2f} | {np.percentile(CL[k]['lat'], 50):.2f}s | ✗ |")

# ---------- bootstrap ----------
section("bootstrap")
rng = np.random.default_rng(1)
PAIRS = [
    ("jev-a", "rule", "clef-a", "rule"), ("jev-a", "plf1", "clef-a", "plf1"), ("jev-a", "plp90", "clef-a", "plp90"),
    ("jev-b", "rule", "clef-b", "rule"), ("jev-b", "plf1", "clef-b", "plf1"), ("jev-b", "plp90", "clef-b", "plp90"),
    ("jev-b", "rule", "jev-a", "rule"), ("jev-b", "plf1", "jev-a", "plf1"), ("jev-b", "plp90", "jev-a", "plp90"),
    ("clef-b", "rule", "clef-a", "rule"), ("clef-b", "plf1", "clef-a", "plf1"), ("clef-b", "plp90", "clef-a", "plp90"),
    ("haiku-medium", "list", "jev-b", "rule"), ("haiku-medium", "list", "jev-b", "plf1"),
    ("haiku-medium", "list", "clef-b", "rule"), ("haiku-medium", "list", "clef-b", "plf1"),
    ("haiku-low", "list", "jev-b", "rule"), ("haiku-low", "list", "jev-b", "plf1"),
    ("haiku-low", "list", "clef-b", "rule"), ("haiku-low", "list", "clef-b", "plf1"),
    ("openai-a", "rule", "jev-a", "rule"), ("openai-a", "plf1", "jev-a", "plf1"), ("openai-a", "plp90", "jev-a", "plp90"),
    ("openai-b", "rule", "jev-b", "rule"), ("openai-b", "plf1", "jev-b", "plf1"), ("openai-b", "plp90", "jev-b", "plp90"),
    ("openai-b", "rule", "clef-b", "rule"), ("openai-b", "plf1", "clef-b", "plf1"),
    ("openai-b", "rule", "openai-a", "rule"), ("openai-b", "plf1", "openai-a", "plf1"),
    ("haiku-medium", "list", "openai-b", "rule"), ("haiku-medium", "list", "openai-b", "plf1"),
]
SN = {"rule": "規則", "plf1": "逐類門檻 max F1", "plp90": "逐類門檻 P≥0.9", "list": "清單"}
w("| 比較 | 差距（micro-F1） | 95% CI | 顯著 |")
w("|---|---:|---|:---:|")
for a, sa, b, sb in PAIRS:
    pa, pb = PRED[(a, sa)], PRED[(b, sb)]
    d = []
    for _ in range(1000):
        idx = rng.integers(0, len(Y), len(Y))
        d.append(A.prf(pa[idx], Y[idx])[2] - A.prf(pb[idx], Y[idx])[2])
    full = A.prf(pa, Y)[2] - A.prf(pb, Y)[2]
    lo, hi = np.percentile(d, 2.5), np.percentile(d, 97.5)
    sig = "✓" if lo > 0 or hi < 0 else ""
    w(f"| `{a}`（{SN[sa]}） − `{b}`（{SN[sb]}） | {full:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {sig} |")

# ---------- threshold sweep ----------
section("sweep")
ks = list(DECISION)
for kind in ("micro", "macro"):
    w(f"| 門檻 | " + " | ".join(f"`{k}` {kind} P / R / F1" for k in ks) + " |")
    w("|---:|" + "---|" * len(ks))
    for t in A.THRESHOLDS:
        cells = []
        for k in ks:
            pr = A.strat_global(A.P[k], t)
            p, r, f = A.prf(pr, Y) if kind == "micro" else A.macro(pr, Y)
            cells.append(f"{f3(p)} / {f3(r)} / **{f3(f)}**")
        w(f"| {t} | " + " | ".join(cells) + " |")
    w("")

# ---------- ranking & calibration ----------
section("ranking")
w("| 方案 | Top-1 命中率 | Top-3 至少命中 1 個 | 逐類 ROC-AUC 平均 | 分數 > 0.5 的類別數（每篇） |")
w("|---|---:|---:|---:|---:|")
for k in ks:
    s = A.P[k]
    top1 = Y[np.arange(len(s)), s.argmax(1)].mean()
    top3 = (A.topk_mask(s, 3) & Y).any(1).mean()
    w(f"| `{k}` | {f3(top1)} | {f3(top3)} | {np.nanmean([A.auc(s[:, j], Y[:, j]) for j in range(len(KEYS))]):.3f} | {(s > 0.5).sum(1).mean():.2f} |")
w(f"\n（ground truth 平均每篇 {Y.sum(1).mean():.2f} 個標籤）\n")
bins = [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0001]
w("| 分數區間 | " + " | ".join(f"`{k}` 筆數 / 平均分數 / 實際正例率" for k in ks) + " |")
w("|---|" + "---|" * len(ks))
for lo, hi in zip(bins[:-1], bins[1:]):
    cells = []
    for k in ks:
        s, y = A.P[k].ravel(), Y.ravel()
        m = (s >= lo) & (s < hi)
        cells.append(f"{m.sum()} / {s[m].mean():.2f} / {y[m].mean():.2f}")
    w(f"| [{lo}, {min(hi, 1.0):.1f}) | " + " | ".join(cells) + " |")

# ---------- strategies ----------
section("strategies")
strategy_defs = [
    ("分數 ≥ 0.5", lambda s: A.strat_global(s, 0.5)),
    ("分數 ≥ 0.7", lambda s: A.strat_global(s, 0.7)),
    ("分數 ≥ 0.8", lambda s: A.strat_global(s, 0.8)),
    ("分數 ≥ 0.9", lambda s: A.strat_global(s, 0.9)),
    ("分數 ≥ 0.5，最多取前 2", lambda s: A.strat_global(s, 0.5, 2)),
    ("分數 ≥ 0.5，最多取前 3", lambda s: A.strat_global(s, 0.5, 3)),
    ("分數 ≥ 0.7，最多取前 2", lambda s: A.strat_global(s, 0.7, 2)),
    ("分數 ≥ 0.7，最多取前 3", lambda s: A.strat_global(s, 0.7, 3)),
    ("**分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個**", lambda s: A.strat_top1_fallback(s, 0.7, 2)),
    ("只取最高分 1 個", lambda s: A.topk_mask(s, 1)),
    ("**逐類門檻（max F1, CV）**", lambda s: A.cv_per_label(s, Y)),
    ("**逐類門檻（precision ≥ 0.9, CV）**", lambda s: A.cv_per_label(s, Y, min_precision=0.9)),
]
for sub, mask in (("全部樣本", ALL), ("隨機抽樣子集", RAND)):
    w(f"**{sub}**（括號內為平均每篇標籤數）\n")
    w("| 策略 | " + " | ".join(f"`{k}` P / R / F1" for k in ks) + " |")
    w("|---|" + "---|" * len(ks))
    for name, fn in strategy_defs:
        cells = []
        for k in ks:
            pr = fn(A.P[k])
            p, r, f = A.prf(pr[mask], Y[mask])
            cells.append(f"{f3(p)} / {f3(r)} / **{f3(f)}** ({pr[mask].sum(1).mean():.2f})")
        w(f"| {name} | " + " | ".join(cells) + " |")
    for k, (name, *_r) in LLM.items():
        p, r, f = A.prf(LP[k][mask], Y[mask])
        w(f"| *`{k}` 輸出的清單（固定，不分策略）* | " + f"{f3(p)} / {f3(r)} / **{f3(f)}** ({LP[k][mask].sum(1).mean():.2f})" + " | " * (len(ks) - 1) + " |")
    w("")

# same recall comparison
section("same-recall")
grid = np.round(np.arange(0.02, 0.99, 0.01), 2)
w("| LLM 清單 | P / R | " + " | ".join(f"`{k}` 同 recall 的 P（門檻）" for k in ks) + " |")
w("|---|---|" + "---|" * len(ks))
for k in LLM:
    lp, lr, _ = A.prf(LP[k], Y)
    cells = []
    for d in ks:
        pts = [(t, *A.prf(A.P[d] >= t, Y)) for t in grid]
        tr = min(pts, key=lambda x: abs(x[2] - lr))
        cells.append(f"{f3(tr[1])}（{tr[0]:.2f}）")
    w(f"| `{k}` | {f3(lp)} / {f3(lr)} | " + " | ".join(cells) + " |")

# ---------- per label ----------
section("per-label overview")
w("各類 F1：決策模型取該類 max-F1 門檻（在整個樣本上找，樂觀估計）；LLM 為清單的固定結果。\n")
w("| 類別 | 正例 | " + " | ".join(f"`{k}`" for k in ks) + " | " + " | ".join(f"`{k}`" for k in LLM) + " |")
w("|---|---:|" + "---:|" * (len(ks) + len(LLM)))
TH = {k: A.fit_per_label(A.P[k], Y) for k in ks}
TH9 = {k: A.fit_per_label(A.P[k], Y, 0.9) for k in ks}
for j, c in enumerate(KEYS):
    cells = [f3(A.prf(A.P[k][:, j] >= TH[k][j], Y[:, j])[2]) for k in ks] + [f3(A.prf(LP[k][:, j], Y[:, j])[2]) for k in LLM]
    w(f"| {KEY2TITLE[c]} | {Y[:, j].sum()} | " + " | ".join(cells) + " |")

section("per-label details")
for k in ks:
    s = A.P[k]
    w(f"<details><summary><code>{k}</code> 逐類 P / R / F1</summary>\n")
    w("| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |")
    w("|---|---:|---:|---|---|---|")
    for j, c in enumerate(KEYS):
        y = Y[:, j]
        p5 = A.prf(s[:, j] >= 0.5, y); pf = A.prf(s[:, j] >= TH[k][j], y); p9 = A.prf(s[:, j] >= TH9[k][j], y)
        reach = f"{TH9[k][j]:.2f} → {f3(p9[1])}" if p9[0] >= 0.9 else "—"
        w(f"| {KEY2TITLE[c]} | {y.sum()} | {A.auc(s[:, j], y):.3f} | {' / '.join(map(f3, p5))} | {TH[k][j]:.2f} → {' / '.join(map(f3, pf))} | {reach} |")
    w("\n</details>\n")
w("<details><summary>Claude Haiku 5.5 逐類 P / R / F1</summary>\n")
w("| 類別 | 正例 | " + " | ".join(f"`{k}` P / R / F1" for k in LLM) + " |")
w("|---|---:|" + "---|" * len(LLM))
for j, c in enumerate(KEYS):
    w(f"| {KEY2TITLE[c]} | {Y[:, j].sum()} | " + " | ".join(" / ".join(map(f3, A.prf(LP[k][:, j], Y[:, j]))) for k in LLM) + " |")
w("\n</details>\n")

# ---------- cost ----------
section("cost")
w("| 方案 | 單價 input / output（USD / M） | 每篇 input tokens 平均 / p95 | 每篇 output tokens | 每篇成本 | 每 1 萬篇 | 重跑 17K | 回填 28 萬篇 |")
w("|---|---|---:|---:|---:|---:|---:|---:|")
for k, v in {**DECISION, **LLM}.items():
    c = CL[k]
    outp = "免費" if v[3] == 0 else f"${v[3]:.2f}"
    w(f"| `{k}` | ${v[2]} / {outp} | {c['ti'].mean():,.0f} / {np.percentile(c['ti'], 95):,.0f} | {c['to'].mean():,.0f} | ${c['per']:.6f} | "
      f"${c['per'] * 1e4:.2f} | ${c['per'] * 17000:.2f} | ${c['per'] * 279286:.1f} |")

# ---------- latency ----------
section("latency")
w("| 方案 | 情境 | n | 平均 | p50 | p90 | p95 | p99 | max |")
w("|---|---|---:|---:|---:|---:|---:|---:|---:|")
for k in {**DECISION, **LLM}:
    for scen, path in (("序列（1 併發）", SEQ.get(k)), ("8 併發", f"{k}.jsonl")):
        if not path:
            continue
        lat = np.array([r["latency_s"] for r in ok_rows(f"results/{path}")])
        q = np.percentile(lat, [50, 90, 95, 99])
        w(f"| `{k}` | {scen} | {len(lat):,} | {lat.mean():.2f}s | {q[0]:.2f}s | {q[1]:.2f}s | {q[2]:.2f}s | {q[3]:.2f}s | {lat.max():.2f}s |")
w("")
edges = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, np.inf]
seq = {k: np.array([r["latency_s"] for r in ok_rows(f"results/{p}")]) for k, p in SEQ.items()}
w("| 區間（序列） | " + " | ".join(f"`{k}`" for k in seq) + " |")
w("|---|" + "---:|" * len(seq))
for lo, hi in zip(edges[:-1], edges[1:]):
    lab = f"≥ {lo:g}s" if hi == np.inf else f"{lo:g}–{hi:g}s"
    w(f"| {lab} | " + " | ".join(f"{((v >= lo) & (v < hi)).mean():.0%}" for v in seq.values()) + " |")

# ---------- §7.12 OpenAI Decisions ----------


def rank_tied(x):
    """1-based ranks; tied values share the average of their ranks."""
    _, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    first = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    return (first + (cnt + 1) / 2)[inv]


def auc_tied(s, y):
    """ROC-AUC like A.auc, but tied scores share their rank (A.auc breaks ties by position)."""
    pos, neg = s[y], s[~y]
    if not len(pos) or not len(neg):
        return np.nan
    ranks = rank_tied(np.concatenate([pos, neg]))
    return (ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


section("openai: score spread")
w("| 方案 | 逐類 AUC 平均（analyze.auc） | 逐類 AUC 平均（同分取平均排名） | 分數 ≤ 0.01 或 ≥ 0.99 的比例 | 分數在 0.1~0.9 的比例 |")
w("|---|---:|---:|---:|---:|")
for k in ("jev-a", "jev-b", "clef-a", "clef-b", "openai-a", "openai-b"):
    s = A.P[k]
    aucs = [np.nanmean([fn(s[:, j], Y[:, j]) for j in range(len(KEYS))]) for fn in (A.auc, auc_tied)]
    w(f"| `{k}` | {aucs[0]:.3f} | {aucs[1]:.3f} | {((s <= 0.01) | (s >= 0.99)).mean():.1%} | {((s > 0.1) & (s < 0.9)).mean():.1%} |")

section("openai: uniform 0.75")
# §7.11: one threshold of 0.75 for every category, no cap on the number of labels
w("| 方案 | 全樣本 P / R / F1 | 隨機子集 P / R / F1 | 每篇標籤數 | 沒有任何標籤的文章 |")
w("|---|---|---|---:|---:|")
for k in ("jev-b", "clef-b", "openai-b", "openai-a"):
    p = A.P[k] >= 0.75
    w(f"| `{k}` | {' / '.join(map(f3, A.prf(p, Y)))} | {' / '.join(map(f3, A.prf(p[RAND], Y[RAND])))} | "
      f"{p.sum(1).mean():.2f} | {(~p.any(1)).mean():.1%} |")

section("openai: confident false positives")
# score >= 0.9 on a category the ground truth does not have
w("| 方案 | 負例分數 ≥ 0.9 的比例 | 類別 | 誤判篇數 | 這些文章的 ground truth（前 3） |")
w("|---|---:|---|---:|---|")
for k in ("jev-b", "clef-b", "openai-b"):
    s = A.P[k]
    for c in ("medical", "intl"):
        j = KEYS.index(c)
        fp = (s[:, j] >= 0.9) & ~Y[:, j]
        truth = Y[fp].sum(0)
        top = ", ".join(f"{KEY2TITLE[KEYS[i]]} {truth[i]}" for i in np.argsort(-truth)[:3] if truth[i])
        w(f"| `{k}` | {(s[~Y] >= 0.9).mean():.2%} | {KEY2TITLE[c]} | {fp.sum()} | {top} |")
w("")
for k in ("jev-b", "openai-b"):
    s = A.P[k]
    fp = PRED[(k, "rule")] & ~Y
    srt = -np.sort(-s, 1)
    tie = ((srt[:, 1] >= 0.7) & (srt[:, 2] == srt[:, 1])).sum()
    w(f"- `{k}` 規則策略的誤判 {fp.sum()} 個，分數 ≥ 0.9 佔 {(s[fp] >= 0.9).mean():.1%}、≥ 0.99 佔 {(s[fp] >= 0.99).mean():.1%}；"
      f"「最多取前 2 個」切在同分中間的文章 {tie} 篇")

section("openai: spot check")
# (article, category) pairs not in ground truth that one model scores >= 0.9 and the other < 0.5; §7.12 judges the sample
O, J = A.P["openai-b"], A.P["jev-b"]


def only(hi, lo):
    return [(i, j) for i in range(len(Y)) for j in range(len(KEYS)) if hi[i, j] >= 0.9 and lo[i, j] < 0.5 and not Y[i, j]]


pop = only(O, J)
w(f"OpenAI ≥ 0.9、Jev < 0.5、ground truth 沒標：{len(pop)} 個；反方向：{len(only(J, O))} 個。抽查 30 個（seed 20261023）：\n")
w("| # | 文章 ID | 類別 | `openai-b` | `jev-b` | ground truth |")
w("|---:|---|---|---:|---:|---|")
for n, (i, j) in enumerate(random.Random(20261023).sample(pop, 30), 1):
    truth = "／".join(KEY2TITLE[KEYS[t]] for t in np.flatnonzero(Y[i]))
    w(f"| {n} | `{ids[i]}` | {KEY2TITLE[KEYS[j]]} | {O[i, j]:.2f} | {J[i, j]:.2f} | {truth} |")

section("openai: run stats")
for k in ("openai-a", "openai-b"):
    rs = ok_rows(f"results/{k}.jsonl")
    ref = [r for r in rs if r.get("refusals")]
    lat1 = [r["latency_s"] for r in rs if r["attempts"] == 1]
    latn = [r["latency_s"] for r in rs if r["attempts"] > 1]
    w(f"- `{k}`：拒答 {len(ref)} 篇 {sum(len(r['refusals']) for r in ref)} 題；需要重送的文章 {len(latn) / len(rs):.1%}；"
      f"延遲中位數：一次成功 {np.median(lat1):.2f}s、需要重送 {np.median(latn):.2f}s")
us = [r["usage"] for k in ("openai-a", "openai-b", "latency_openai-a") for r in ok_rows(f"results/{k}.jsonl")]
tin = sum(u["input_tokens"] for u in us)
cached = sum((u.get("input_tokens_details") or {}).get("cached_tokens", 0) for u in us)
w(f"- 結果檔內的 OpenAI 呼叫合計 {tin:,} input tokens（${tin * DECISION['openai-a'][2] / 1e6:.2f}），其中 cache {cached / tin:.1%}")

print("\n".join(out))
