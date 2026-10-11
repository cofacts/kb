"""Run one decision model over the sample; one request per article with all 16 noul questions.

usage: CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_AUTH_TOKEN=... python3 -I run.py <model: clef|clef-flash|jev> <sample.jsonl> <out.jsonl> [concurrency] [limit]
Resumable: articles already in out.jsonl with a successful answer are skipped.
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import KEYS, build_questions, build_state  # noqa: E402

ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
TOKEN = os.environ["CLOUDFLARE_AUTH_TOKEN"]
BASE = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run"

model, sample_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
conc = int(sys.argv[4]) if len(sys.argv) > 4 else 8
limit = int(sys.argv[5]) if len(sys.argv) > 5 else None

QUESTIONS = build_questions()


def payload(text):
    state = build_state(text)
    if model in ("clef", "clef-flash"):
        return f"{BASE}/@cf/cloudflare/{model}", {"model": model, "state": state, "questions": QUESTIONS}
    if model == "jev":
        return BASE, {"model": "typesafe/jev", "input": {"state": state, "questions": QUESTIONS}}
    raise SystemExit(f"unknown model {model}")


done = set()
if os.path.exists(out_path):
    for line in open(out_path):
        r = json.loads(line)
        if r.get("scores"):
            done.add(r["id"])

articles = [json.loads(l) for l in open(sample_path)]
if limit:
    articles = articles[:limit]
todo = [a for a in articles if a["id"] not in done]
print(f"{model}: {len(todo)} to run ({len(done)} already done)", flush=True)

lock = threading.Lock()
fo = open(out_path, "a")
sess = requests.Session()
sess.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
counter = {"n": 0, "err": 0}


def one(a):
    url, body = payload(a["text"])
    rec = {"id": a["id"], "model": model}
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            resp = sess.post(url, json=body, timeout=120)
            dt = time.perf_counter() - t0
            j = resp.json()
        except Exception as e:  # network / JSON error
            dt = time.perf_counter() - t0
            j, resp = {"errors": [{"message": repr(e)}]}, None
        res = j.get("result") or {}
        # Jev (third-party, via AI Gateway) wraps the payload: {"state": "Completed", "result": {...}}
        if "state" in res and "answers" not in res:
            if res.get("state") != "Completed":
                j = {"errors": [{"message": f"jev state={res.get('state')}"}]}
            res = res.get("result") or {}
        if resp is not None and resp.status_code == 200 and j.get("success") and "answers" in res:
            ans = res["answers"]
            if attempt:
                rec["retried_after"] = rec.pop("error", None)
                rec.pop("status", None)
            rec.update({
                "latency_s": round(dt, 4),
                "attempts": attempt + 1,
                "model_version": res.get("model"),
                "usage": res.get("usage"),
                "scores": [ans[k]["noul"] for k in KEYS],
            })
            break
        rec.update({"error": j.get("errors"), "status": getattr(resp, "status_code", None), "latency_s": round(dt, 4)})
        if resp is not None and resp.status_code in (400, 401, 403):
            break
        time.sleep(2 ** attempt)
    with lock:
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fo.flush()
        counter["n"] += 1
        if "scores" not in rec:
            counter["err"] += 1
        if counter["n"] % 50 == 0:
            print(f"  {counter['n']}/{len(todo)} errors={counter['err']}", flush=True)


t0 = time.time()
with ThreadPoolExecutor(conc) as ex:
    list(ex.map(one, todo))
print(f"done in {time.time()-t0:.1f}s, errors={counter['err']}", flush=True)
