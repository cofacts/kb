"""Build the evaluation sample from the 20211210_17111 ground truth.

usage: python3 -I sample.py <json_dir> <out.jsonl> [n_total] [min_per_label]
"""
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import DEPRECATED_IDS, EXCLUDED_IDS, ID2KEY, KEYS  # noqa: E402

json_dir, out = sys.argv[1], sys.argv[2]
n_total = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
min_per = int(sys.argv[4]) if len(sys.argv) > 4 else 60

pool = []
for f in sorted(glob.glob(os.path.join(json_dir, "*.json"))):
    d = json.load(open(f))
    tags = set(d["tags"])
    if tags & (EXCLUDED_IDS | DEPRECATED_IDS):
        continue
    if not (d.get("text") or "").strip():
        continue
    pool.append({"id": d["id"], "text": d["text"], "labels": sorted(ID2KEY[t] for t in tags)})

rng = random.Random(20261011)
rng.shuffle(pool)
chosen, seen = [], set()

def add(a):
    if a["id"] not in seen:
        seen.add(a["id"])
        chosen.append(a | {"stratum": "boost"})

# 1) guarantee min_per positives for every label (rarest first)
counts = {k: sum(k in a["labels"] for a in pool) for k in KEYS}
for k in sorted(KEYS, key=counts.get):
    have = sum(k in a["labels"] for a in chosen)
    for a in pool:
        if have >= min_per:
            break
        if k in a["labels"] and a["id"] not in seen:
            add(a)
            have += 1
n_boost = len(chosen)
# 2) fill the rest uniformly at random (natural distribution)
for a in pool:
    if len(chosen) >= n_total:
        break
    if a["id"] not in seen:
        seen.add(a["id"])
        chosen.append(a | {"stratum": "random"})

with open(out, "w") as fo:
    for a in chosen:
        fo.write(json.dumps(a, ensure_ascii=False) + "\n")
print(f"pool={len(pool)} boost={n_boost} total={len(chosen)}")
for k in KEYS:
    print(k, counts[k], sum(k in a["labels"] for a in chosen))
