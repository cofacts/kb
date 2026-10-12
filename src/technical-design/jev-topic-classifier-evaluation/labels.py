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


# Prompt B: concrete true/false criteria per category. Prompt A uses one generic sentence for every category.
# Both share the same instructions and state. Exclusions are added only where category definitions overlap.
SPECIFIC_CRITERIA = {
    "kj287XEBrIRcahlYvQoS": (  # 中國政治宣傳
        "訊息的重點是中國（含港澳、新疆、西藏）的政治、軍事、統戰或對外宣傳，例如美化中國、宣揚中國強大、貶低台灣或西方、兩岸統獨論述",
        "訊息與中國無關，或只是順帶提到中國，主要在談別的事",
    ),
    "nD2n7nEBrIRcahlYwQoW": (  # 詐騙
        "訊息試圖讓人付款、繳押金、提供個資或帳號密碼、加陌生帳號為好友、點連結領取免費貼圖或贈品，或假冒政府、銀行、知名企業",
        "訊息沒有上述騙取金錢、個資或點擊的手法",
    ),
    "oT2o7nEBrIRcahlYKQoM": (  # 台灣政治、政黨
        "訊息批評或支持台灣的政黨、政治人物、選舉、公投或執政表現，會影響讀者對某個政治立場的觀感",
        "訊息與台灣的政黨、政治人物或選舉無關",
    ),
    "covid19": (  # COVID-19 疫情
        "訊息談 COVID-19（新冠肺炎、武漢肺炎）的病毒、變種、疫苗、篩檢、防疫措施、確診或疫情狀況",
        "訊息與 COVID-19 無關；或只是紓困、振興券等與傳染病防治無關的經濟措施（屬於「優惠措施、新法規、政策宣導」）",
    ),
    "medical": (  # 疾病、醫藥
        "訊息談的是傳染病、癌症，或特定藥物、疫苗、醫療器材的效果與風險，醫師或公衛師會想回應",
        "訊息與疾病醫藥無關；或只是食療、偏方、養生習慣、日常保健（這些屬於「保健秘訣、食品安全」）",
    ),
    "intl": (  # 跨國互動
        "訊息的重點是兩個以上國家或國際組織之間的互動，例如外交、貿易戰、軍事對峙、國際援助、各國人民的往來或旅外經驗",
        "訊息只談單一國家內部的事，或外國只是背景、不是重點",
    ),
    "aids": (  # 愛滋病
        "訊息提到愛滋病、HIV、PrEP 或愛滋感染者",
        "訊息與愛滋病無關",
    ),
    "lD3h7XEBrIRcahlYeQqS": (  # 性別議題
        "訊息談性別平等教育、同性婚姻、LGBT、性別刻板印象、墮胎或身體自主等性別議題",
        "訊息與性別議題無關",
    ),
    "lT3h7XEBrIRcahlYugqq": (  # 保健秘訣、食品安全
        "訊息宣稱某種食物、飲食方式、偏方、運動或生活習慣對健康有益或有害，或談食品添加物、食品安全",
        "訊息與飲食、養生或食品安全無關",
    ),
    "lz2n7nEBrIRcahlYDgri": (  # 農林漁牧政策
        "訊息談農、林、漁、牧業的生產、產銷、價格、進出口、動植物病蟲害，或相關的政府政策與補助",
        "訊息與第一級產業無關；只是一般的食物或料理話題不算",
    ),
    "mD2n7nEBrIRcahlYLAr7": (  # 電力、能源
        "訊息談發電方式（核能、火力、綠電）、電力供應與停電、電價，或能源政策",
        "訊息與電力或能源無關",
    ),
    "mT2n7nEBrIRcahlYTArI": (  # 環保、生態
        "訊息的重點是動植物保育、氣候變遷、空氣或水污染、廢棄物，或開發對環境的影響",
        "訊息與環境或生態無關",
    ),
    "mj2n7nEBrIRcahlYdArf": (  # 優惠措施、新法規、政策宣導
        "訊息說明或誤傳政府（中央或地方）的補助、津貼、優惠、新法規、罰則或公共服務措施",
        "訊息與政府的政策措施無關",
    ),
    "mz2n7nEBrIRcahlYnQpz": (  # 科技、資安、隱私
        "訊息的主題是科技本身，例如 5G、AI、手機或電腦的功能與風險、資訊安全、個資與隱私",
        "訊息與科技無關；或只是透過手機、LINE、網路傳播，主題是別的事情",
    ),
    "nz2o7nEBrIRcahlYBgqQ": (  # 商業廣告
        "訊息是商家（或自稱商家）推廣商品、服務或促銷活動，例如折扣、優惠碼、新品、贈品活動",
        "訊息與商品或服務的推廣無關",
    ),
    "oj2o7nEBrIRcahlYRAox": (  # 連署、集氣、協尋、捐贈
        "訊息呼籲大家連署、協尋失蹤的人或寵物、捐款捐物、投票、集氣或轉發幫忙",
        "訊息沒有這類呼籲",
    ),
}


def build_questions(prompt="a"):
    """One noul question per category, judged by stakeholder interest (誰會有興趣).

    prompt "a": generic criteria (the same sentence for every category); "b": SPECIFIC_CRITERIA.
    """
    qs = {}
    for cid, title, desc in LABELS:
        if prompt == "b":
            true, false = SPECIFIC_CRITERIA[cid]
        else:
            true = f"訊息落在「{title}」的範圍，目標編輯會有興趣處理它"
            false = f"訊息與「{title}」無關，目標編輯不會特別想處理它"
        qs[cid] = {
            "type": "noul",
            "instructions": (
                f"這則訊息是否屬於 Cofacts 的「{title}」分類？"
                f"判斷標準是：下列「目標編輯」會不會想看、想查核或想回應這則訊息。\n\n{desc}"
            ),
            "criteria": {"true": true, "false": false},
        }
    return qs


STATE_PREFIX = "以下是台灣民眾轉傳到 Cofacts 真的假的（協作查核平台）請求查證的一則訊息：\n\n"
MAX_CHARS = 4000


def build_state(text):
    text = (text or "").strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "……（以下截斷）"
    return STATE_PREFIX + text
