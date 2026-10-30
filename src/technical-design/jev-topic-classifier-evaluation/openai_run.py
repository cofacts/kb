"""Run the OpenAI Decisions API (gpt-6-luna) over the sample; one request per article with all 16 predicate questions.

Predicate questions have no criteria field, so criteria.true/false are appended to the instructions
with the same 符合／不符合 wording llm_run.py uses for Haiku. Output format matches run.py.
A refused question scores 0 and its key is listed in "refusals".

usage: OPENAI_API_KEY=... python3 -I openai_run.py <sample.jsonl> <out.jsonl> [concurrency] [limit, 0 = all] [prompt: a|b]
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

URL = "https://api.openai.com/v1/decisions"
MODEL = "gpt-6-luna"
TOKEN = os.environ["OPENAI_API_KEY"]

sample_path, out_path = sys.argv[1], sys.argv[2]
conc = int(sys.argv[3]) if len(sys.argv) > 3 else 8
limit = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != "0" else None
prompt = sys.argv[5] if len(sys.argv) > 5 else "a"


def predicates(prompt):
    qs = build_questions(prompt)
    return [
        {
            "type": "predicate",
            "name": k,
            "instructions": f"{qs[k]['instructions']}\n\n符合：{qs[k]['criteria']['true']}\n不符合：{qs[k]['criteria']['false']}",
        }
        for k in KEYS
    ]


QUESTIONS = predicates(prompt)

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
print(f"openai: {len(todo)} to run ({len(done)} already done)", flush=True)

lock = threading.Lock()
fo = open(out_path, "a")
sess = requests.Session()
sess.headers.update({"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
counter = {"n": 0, "err": 0}


def one(a):
    body = {"model": MODEL, "input": build_state(a["text"]), "questions": QUESTIONS}
    rec = {"id": a["id"], "model": "openai"}
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            resp = sess.post(URL, json=body, timeout=120)
            dt = time.perf_counter() - t0
            j = resp.json()
        except Exception as e:  # network / JSON error
            dt = time.perf_counter() - t0
            j, resp = {"error": {"message": repr(e)}}, None
        ans = {x.get("name"): x for x in j.get("answers") or []}
        if resp is not None and resp.status_code == 200 and all(k in ans for k in KEYS):
            rec.pop("error", None)  # OpenAI error messages name the organization and project
            rec.pop("status", None)
            refused = [k for k in KEYS if ans[k]["type"] == "refusal"]
            rec.update({
                "latency_s": round(dt, 4),
                "attempts": attempt + 1,
                "model_version": j.get("model"),
                "usage": j.get("usage"),
                "scores": [0.0 if k in refused else ans[k]["probability"] for k in KEYS],
            })
            if refused:
                rec["refusals"] = refused
            break
        rec.update({"error": j.get("error") or "missing answers", "status": getattr(resp, "status_code", None),
                    "latency_s": round(dt, 4)})
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
