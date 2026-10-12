"""LLM baseline: put all 16 categories in one prompt and ask Claude Haiku 5.5 for a list of category ids.

Calls go through Cloudflare's Anthropic Messages-compatible endpoint (billed via AI Gateway unified billing),
using the Anthropic Python SDK with base_url pointed at Cloudflare.

usage: CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_AUTH_TOKEN=... python3 -I llm_run.py <effort: low|medium> <sample.jsonl> <out.jsonl> [concurrency] [limit, 0 = all]
Resumable: articles already in out.jsonl with a parsed answer are skipped.
"""
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import anthropic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from labels import KEYS, LABELS, V2_CRITERIA, build_state  # noqa: E402

ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
MODEL = "anthropic/claude-haiku-5.5"  # Cloudflare's id for claude-haiku-5-5

effort, sample_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
conc = int(sys.argv[4]) if len(sys.argv) > 4 else 8
limit = int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "0" else None

client = anthropic.Anthropic(
    api_key=None,
    auth_token=os.environ["CLOUDFLARE_AUTH_TOKEN"],
    base_url=f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai",
    max_retries=4,
    timeout=120.0,
)


def category_block(cid, title, desc):
    true, false = V2_CRITERIA[cid]
    return f"## {title}\nid: {cid}\n{desc}\n符合：{true}\n不符合：{false}"


SYSTEM = (
    "你是 Cofacts 真的假的（台灣的協作查核平台）的訊息分類員。"
    "民眾會把在 LINE 等管道收到、想查證的訊息轉傳給 Cofacts，你要替每則訊息標上主題分類，"
    "讓對該主題有興趣、擅長回應的編輯能找到它。\n\n"
    "判斷原則：每個分類都列出了「目標編輯」。一則訊息屬於某分類，是指該分類的目標編輯會想看、想查核或想回應它。"
    "一則訊息可以屬於多個分類，也可以不屬於任何分類（此時回傳空陣列）。只標你有把握的分類。\n\n"
    "# 分類\n\n" + "\n\n".join(category_block(*l) for l in LABELS)
)

SCHEMA = {
    "type": "object",
    "properties": {
        "categories": {
            "type": "array",
            "items": {"type": "string", "enum": KEYS},
            "description": "這則訊息所屬分類的 id，依相關程度由高到低排列；都不屬於時為空陣列",
        }
    },
    "required": ["categories"],
    "additionalProperties": False,
}

done = set()
if os.path.exists(out_path):
    for line in open(out_path):
        r = json.loads(line)
        if r.get("categories") is not None:
            done.add(r["id"])

articles = [json.loads(l) for l in open(sample_path)]
if limit:
    articles = articles[:limit]
todo = [a for a in articles if a["id"] not in done]
print(f"haiku-5.5 effort={effort}: {len(todo)} to run ({len(done)} already done)", flush=True)

lock = threading.Lock()
fo = open(out_path, "a")
counter = {"n": 0, "err": 0}


def one(a):
    rec = {"id": a["id"], "model": "claude-haiku-5-5", "effort": effort}
    t0 = time.perf_counter()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            messages=[{"role": "user", "content": build_state(a["text"])}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        rec["latency_s"] = round(time.perf_counter() - t0, 4)
        rec["stop_reason"] = resp.stop_reason
        rec["usage"] = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        if resp.stop_reason == "refusal":
            rec["error"] = "refusal"
        else:
            text = next(b.text for b in resp.content if b.type == "text")
            cats = json.loads(text)["categories"]
            rec["categories"] = [c for c in dict.fromkeys(cats) if c in KEYS]
    except (anthropic.APIStatusError, anthropic.APIConnectionError, StopIteration, json.JSONDecodeError, KeyError) as e:
        rec["latency_s"] = round(time.perf_counter() - t0, 4)
        rec["error"] = f"{type(e).__name__}: {e}"[:500]
    with lock:
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fo.flush()
        counter["n"] += 1
        if "categories" not in rec:
            counter["err"] += 1
        if counter["n"] % 50 == 0:
            print(f"  {counter['n']}/{len(todo)} errors={counter['err']}", flush=True)


t0 = time.time()
with ThreadPoolExecutor(conc) as ex:
    list(ex.map(one, todo))
print(f"done in {time.time()-t0:.1f}s, errors={counter['err']}", flush=True)
