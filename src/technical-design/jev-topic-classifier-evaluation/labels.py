"""Label set for the experiment, loaded verbatim from Cofacts ListCategories (categories.json).

categories.json is fetched with:
  curl https://api.cofacts.tw/graphql -H 'Content-Type: application/json' -H 'x-app-id: RUMORS_SITE' \
    -d '{"query":"{ListCategories(first:100){totalCount edges{node{id title description}}}}"}'

Excluded: AI-only labels (有意義但不包含在以上標籤 / 無意義 / 只有網址其他資訊不足) and
deprecated 🚧 labels (性少數與愛滋病、基本人權問題).
"""
import json
import os

EXCLUDED_IDS = {
    "nT2n7nEBrIRcahlY6QqF",  # 有意義但不包含在以上標籤
    "nj2n7nEBrIRcahlY-gpc",  # 無意義
    "oD2o7nEBrIRcahlYFgpm",  # 只有網址其他資訊不足
}
DEPRECATED_IDS = {
    "kz3c7XEBrIRcahlYxAp6",  # 性少數與愛滋病 🚧
    "lj2m7nEBrIRcahlY6Ao_",  # 基本人權問題 🚧
}

_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "categories.json")
_nodes = [e["node"] for e in json.load(open(_path))["data"]["ListCategories"]["edges"]]

# (category id, title, description) in ListCategories order; the id doubles as question key
LABELS = [
    (n["id"], n["title"].replace("🆕", "").strip(), n["description"].strip())
    for n in _nodes
    if n["id"] not in EXCLUDED_IDS | DEPRECATED_IDS
]

KEYS = [l[0] for l in LABELS]
ID2KEY = {k: k for k in KEYS}
KEY2TITLE = {l[0]: l[1] for l in LABELS}


def build_questions():
    """One noul question per category, judged by stakeholder interest (誰會有興趣)."""
    qs = {}
    for cid, title, desc in LABELS:
        qs[cid] = {
            "type": "noul",
            "instructions": (
                f"這則訊息是否屬於 Cofacts 的「{title}」分類？"
                f"判斷標準是：下列「目標編輯」會不會想看、想查核或想回應這則訊息。\n\n{desc}"
            ),
            "criteria": {
                "true": f"訊息落在「{title}」的範圍，目標編輯會有興趣處理它",
                "false": f"訊息與「{title}」無關，目標編輯不會特別想處理它",
            },
        }
    return qs


STATE_PREFIX = "以下是台灣民眾轉傳到 Cofacts 真的假的（協作查核平台）請求查證的一則訊息：\n\n"
MAX_CHARS = 4000


def build_state(text):
    text = (text or "").strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "……（以下截斷）"
    return STATE_PREFIX + text
