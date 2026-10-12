import json, numpy as np
def load(p): return [json.loads(l) for l in open(p) if '"scores"' in l]
rows = [("jev-a", "results/jev-a.jsonl", "results/latency_jev-a.jsonl"), ("clef-a", "results/clef-a.jsonl", "results/latency_clef-a.jsonl"), ("clef-flash-a", "results/clef-flash-a.jsonl", "results/latency_clef-flash-a.jsonl")]
print("| 模型 | 情境 | n | 平均 | p50 | p90 | p95 | p99 | max | 重試次數 |")
print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for n, main, seq in rows:
    for label, p in (("序列（1 併發）", seq), ("8 併發", main)):
        rs = load(p); l = np.array([r["latency_s"] for r in rs])
        retries = sum(1 for r in rs if r.get("attempts", 1) > 1)
        q = np.percentile(l, [50, 90, 95, 99])
        print(f"| {n} | {label} | {len(l)} | {l.mean():.2f}s | {q[0]:.2f}s | {q[1]:.2f}s | {q[2]:.2f}s | {q[3]:.2f}s | {l.max():.2f}s | {retries} |")
print()
# histogram of sequential latency
edges = [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 99]
print("| 區間 | " + " | ".join(n for n, *_ in rows) + " |")
print("|---|" + "---:|" * len(rows))
data = {n: np.array([r["latency_s"] for r in load(seq)]) for n, _, seq in rows}
for lo, hi in zip(edges[:-1], edges[1:]):
    lab = f"≥ {lo}s" if hi == 99 else f"{lo}–{hi}s"
    print(f"| {lab} | " + " | ".join(f"{((d >= lo) & (d < hi)).mean()*100:.0f}%" for d in data.values()) + " |")
print()
for n, _, seq in rows:
    rs = load(seq); l = np.array([r["latency_s"] for r in rs]); t = np.array([r["usage"]["input_tokens"] for r in rs])
    print(n, "corr(latency, input_tokens)=%.2f" % np.corrcoef(l, t)[0, 1], "tokens range", t.min(), t.max())
