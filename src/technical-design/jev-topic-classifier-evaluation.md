---
type: DesignDoc
title: "以 Jev 實作 Cofacts Topic Classifier 之可行性評估"
tags: [cofacts, design-docs, technical-design, ai, classifier]
timestamp: "2026-09-22T17:01:00+08:00"
---

# 以 Jev 實作 Cofacts Topic Classifier 之可行性評估

> [!NOTE]
> 本文評估 Cloudflare Workers AI 上的第三方模型 [`typesafe/jev`](https://developers.cloudflare.com/ai/models/typesafe/jev/)
> 是否適合作為 Cofacts article category（topic label）分類器的推論引擎，
> 並討論其成本、context 限制，以及在 `CreateArticle` / `CreateMediaArticle` 上掛載的實作方式。
>
> 本文由 Claude Code 依據 kb 內既有會議記錄與 repo 程式碼整理，**尚未經過實測**。
> 文末「待確認事項」列出所有無法在本次調查中查證的數字。

## 1. 歷史脈絡

### 1.1 2018–2020：人工與外包標記

- 分類定義與目標編輯（「誰會想看這則訊息」）記於 [Cofacts 標籤定義](../research/cofacts-標籤定義.md)，
  原始來源為 2020-07 的 [HackMD](https://g0v.hackmd.io/@johnson/ry1K630Jw)。
- 若水（外包標記團隊）產出約 14,908 筆標記資料（`cofacts_labeled_data_14908_20200324`），
  當時**沒有進資料庫**，只存在 Google Drive（見 [20211117](../meetings/2021/20211117.md)）。
- 網站端的 category UI 與 `CreateArticleCategory` 在 2020 上半年陸續上線（[20200701](../meetings/2020/20200701.md)）。

### 1.2 2021：BERT 分類器（rumors-ai-bert）

- 模型：[cofacts/rumors-ai-bert](https://github.com/cofacts/rumors-ai-bert)，
  `GPU_host/model_bert`，由 ggm 維護，打包成 docker image 後由 AI classifier 取用
  （[20211103](../meetings/2021/20211103.md)）。
- 標記寫回時使用特殊 `appId` / `userId`（`RUMORS_AI`），並帶 `aiModel` 欄位。
- 分類調整：新增 `intl`（跨國互動, 118 筆）、`medical`（疾病、醫藥, 177 筆）、
  `covid19`（476 筆，作為「疾病、醫藥」的子分類用 preprocess 處理）；
  拆解「性少數與愛滋病」（287 筆）為「愛滋病」（12 筆）與「性別議題」（241 筆）。
  → **當時每個 category 的訓練樣本數是極度不平衡的（12 ~ 476）**，這點對今天訂 confidence gate 仍然關鍵。
- Ground truth 回饋機制（[Design doc](https://g0v.hackmd.io/EcrdwfZrQOSTGX7yK6nn4w)、
  [rumors-api#265](https://github.com/cofacts/rumors-api/pull/265)、[20211117](../meetings/2021/20211117.md)）：
  1. **Script 1**（今 `src/scripts/genCategoryReview.js`）：撈出指定時間點後、符合規則的 article category，輸出 xlsx 供人工 review。
  2. **人工 review**：在 Google Sheet 上決定是否 adopt。
  3. **Script 2**（今 `src/scripts/genBERTInputArticles.js`）：依 sheet 產出餵給模型的 JSON。
  - Ground truth 基準＝該 article-category 連結的評價「正評 > 負評」；
    AI 標記需先有網友正評才會進 review，人工標記直接進 review。
  - 產出格式：`{ createdAt, hyperlinks, id, reference, tags: [categoryId], text, url }`
  - 資料集後來整理在 [cofacts/ground-truth](https://github.com/cofacts/ground-truth)，**約 17K 筆**。
- **停用原因**：需要常駐 GPU host，成本不划算，之後未再訓練與執行。
  （kb 內僅記錄到 2021-11 的開發活動，2022 之後不再有 rumors-ai 進度；
  停用的確切時間點與當時主機月費未見於 kb，列為待確認。）

### 1.3 2023：LLM 取代 BERT 的最早構想

[chatgpt-or-llm-to-aid-fact-checking.md](../research/chatgpt-or-llm-to-aid-fact-checking.md)
的 *Scenario #3: Topic Categorization*（列為 future work）已提出：

- 把所有 category 放進 prompt
- few-shot：retrieve 相似文章與其 category
- 並自我提醒：**「encoder-based model 理論上會比 decoder-based 的 ChatGPT 更適合這個任務」**

Jev 這種「給定 state + typed questions、回傳 calibrated probability」的評估型模型，
正好落在這個 encoder-like 的定位上。

### 1.4 2025：LLM based Topic Classifier（cofacts/worker）

這條線**已經有設計、也有程式碼，只是還沒上線**：

| 時間 | 進展 |
|------|------|
| [20250623](../meetings/2025/20250623.md) | 討論「一個 classifier 處理一個 category」（N 個二元分類器）的取捨：較耗 token，影片類長 input 會被重複 N 次；o4-mini 表現不錯；決定 input = articleId、output = 打現有 API |
| [20250630](../meetings/2025/20250630.md) | 決定開新 repo [cofacts/worker](https://github.com/cofacts/worker)，用 Cloudflare Workflow 做批次；把 ground-truth 17K 放進 Langfuse dataset 做實驗；比較基準＝ **cost + accuracy + confusion matrix** |
| [20250722](../meetings/2025/20250722.md) | 檢討 [worker#1](https://github.com/cofacts/worker/pull/1) over-engineer；發現分數不對（title emoji 導致 ID 對不到）；「reason 應放在 category 之前才有 CoT 之效」 |
| 2025-07 ~ 2025-11 | 會議 action item「LLM based Topic Classifier: 追蹤 bug 修復與 benchmark 結果」連續掛了約 4 個月，**未見結案的 benchmark 數字** |
| [20251111](../meetings/2025/20251111.md) | 定案實作路徑（見下） |
| [20251202](../meetings/2025/20251202.md) | [worker#3 Url resolver article classifiers](https://github.com/cofacts/worker/pull/3) 開發中 |
| [20251229](../meetings/2025/20251229.md) | 列入 2026 TODO，至今（2026-09）未合併上線 |

[20251111](../meetings/2025/20251111.md) 定下的 classifier 實作路徑，與本次提問的構想幾乎一致：

1. 在 cofacts/worker 建立 category workflow
   - input = article ID；step 1 讀 article、step 2 call LLM、step 3 呼叫 `CreateArticleCategory()`
   - **worker 內可抽換實作**：
     - 1 LLM call 分 N 個 category
     - N LLM calls 的二元分類器
     - N LLM calls 但走 batch
   - 實驗時不要用 batch，用 Langfuse 跑
2. 在 rumors-api create article 時呼叫，**射後不理**

現況實作（[worker#3 `src/workflows/article-classifier.ts`](https://github.com/cofacts/worker/pull/3/files)）是「一個大 prompt」版本：
用 `gemini-3-flash-preview`，透過 GraphQL 取 `GetArticle.text` 與 `ListCategories(first: 50)`，
要求回傳 `{ categoryIds: string[], reasoning: string }`，再逐一呼叫 `CreateArticleCategory`。

### 1.5 2026-09：放棄 cofacts/worker，改為 rumors-api 直接呼叫

本文撰寫時（2026-09）做出的決定：

- **classifier 不走 cofacts/worker**，直接在 rumors-api 的 `CreateArticle` / `CreateMediaArticle` 呼叫 Jev。
- **url-resolver 也不搬去 worker**，維持現狀：rumors-api 透過 gRPC（`URL_RESOLVER_URL`、`src/util/grpc.js`）
  呼叫 [cofacts/url-resolver](https://github.com/cofacts/url-resolver)，並以 `urls` index 作 cache
  （見 `src/util/scrapUrls.js`）。
- 因此 [worker#2](https://github.com/cofacts/worker/issues/2)、[worker#3](https://github.com/cofacts/worker/pull/3)
  的路線整個停用，2025-11 的實作路徑不再採用。

判斷依據：

1. **Jev 不需要 Workers runtime。** `env.AI.run()` 只是 binding 的糖，
   Workers AI 另有 REST endpoint（`POST /accounts/{id}/ai/run` + Bearer token），
   任何 Node 程式都能呼叫。「用 Jev」與「跑在 Cloudflare 上」是兩件事。
2. **當初選 Workflow 的理由消失了。** [20250623](../meetings/2025/20250623.md) 選 Cloudflare Workflow，
   是為了 Gemini / o4-mini 的 **batch API**：要打包檔案、要 polling、要等數分鐘到數小時，
   才需要 durable execution。Jev 是一次同步呼叫、輸出僅數百 token，
   為單一 HTTP request 架 Workflow 不成比例——[20250722](../meetings/2025/20250722.md)
   自己也檢討過「有點 over-engineer，單一 article 要分類會簡單很多」。
3. **Langfuse 已經在 rumors-api 裡**（`langfuse@3.32.0`、`src/util/langfuse.ts`），
   分類器的 trace 可與 AI reply、transcript 放在同一個 project 下比較成本；worker 則要另外接一次。
4. **rumors-api 有地方存原始分數**：既有的 `airesponses` index 與 `createAIResponse()`
   可以存下 Jev 回傳的 N 個機率（見 §6.3），這是 worker 那條路沒有的。

> [!IMPORTANT]
> 本文其餘部分（資料集、confidence gate 校準方式、成本試算）不受這個決定影響——
> 那些都是模型層的問題。改變的只有 §6「掛載方式」。

## 2. 現有可用資產

| 資產 | 位置 | 用途 |
|------|------|------|
| Ground truth 17K | [cofacts/ground-truth](https://github.com/cofacts/ground-truth)，已匯入 Langfuse dataset | 訂 confidence gate、算 PR 曲線 |
| Script 1 / Script 2 | `rumors-api/src/scripts/genCategoryReview.js`、`genBERTInputArticles.js` | 持續從網友 feedback 產生新 ground truth |
| `aiModel` / `aiConfidence` 欄位 | `rumors-api/src/graphql/mutations/CreateArticleCategory.js` | **已存在**，可直接寫入 Jev 的 noul 機率，不需 schema migration |
| Category feedback 機制 | `CreateOrUpdateArticleCategoryFeedback` | 線上持續回收 precision 訊號 |
| Langfuse SDK | `rumors-api` 已裝 `langfuse@3.32.0`、`src/util/langfuse.ts` | 成本 / 準確率比較、線上 trace |
| `airesponses` index + `createAIResponse()` | `rumors-api/src/graphql/util.js` | 存 Jev 回傳的 N 個原始機率 |
| Prompt / 分類定義 | [Cofacts 標籤定義](../research/cofacts-標籤定義.md) | 轉成 noul 問題的 `instructions` / `criteria` |
| 參考實作 | [worker#3 `article-classifier.ts`](https://github.com/cofacts/worker/pull/3/files)（已停用） | GraphQL 取資料與寫回的邏輯可搬 |

## 3. Jev 適配性分析

### 3.1 為什麼 Jev 在概念上比 Gemini JSON 更適合

| 需求 | Gemini「一個大 prompt」現況 | Jev |
|------|------|------|
| 每個 category 一個信心值 | 只回傳 `categoryIds` 陣列，**沒有分數**；要取信心值得另外要求模型自評（未校準） | `noul` 型問題原生回傳 0~1 機率，官方宣稱為 calibrated |
| 調整 precision / recall 平衡 | 只能改 prompt 重跑 | 改 gate 閾值即可，**不必重跑推論** |
| 多標籤（一篇可屬多類） | 可以，但模型傾向少選 | N 個獨立 noul 問題，天然多標籤 |
| 輸出格式穩定性 | responseSchema 約束，仍可能 hallucinate 不存在的 ID | 問題 key 由我方定義，**不可能回傳不存在的 category** |
| 逐 category 的 confusion matrix | 需自行拆 | 直接對每個 noul 分數算 PR 曲線 |

其中「不必重跑推論就能調整閾值」對 Cofacts 特別有價值：
2021 年各 category 樣本數從 12 到 476 不等，**不同 category 幾乎不可能共用同一個閾值**，
逐類調整閾值的能力正是這個任務最需要的。

### 3.2 Context window 試算（32,000 tokens）

Jev 的 context window 為 32,000 tokens。輸入由三部分組成：

1. **Jev 自身的 protocol overhead**：從官方範例的 `usage.input_tokens` 反推，
   2~3 個簡短問題的請求約 380~426 input tokens，扣掉題目本身，
   **baseline 約 300 tokens**。
2. **N 個 noul 問題**：每題含 `instructions` + `criteria.true/false`。
   若沿用 [標籤定義](../research/cofacts-標籤定義.md) 的描述（中文約 60~120 字），
   加上 true/false criteria，每題抓 **150~250 tokens**（中文在多數 tokenizer 約 1 字 ≈ 0.7~1.5 token）。
3. **訊息本文 `state`**。

以 **N = 20**（16 個對外分類 + 「有意義但不包含」「無意義」「只有網址」等 AI-only 分類；
實際數量需以 `ListCategories` 為準）估算：

| 項目 | tokens |
|------|--------|
| protocol overhead | ~300 |
| 20 個 noul 問題 | 3,000 ~ 5,000 |
| **問題區小計** | **~3,300 ~ 5,300** |
| 可留給訊息本文 | **~26,700 ~ 28,700** |

對照 Cofacts 的實際 input：

- 純文字訊息：絕大多數 < 1,000 字 → < 1,500 tokens，**綽綽有餘**。
- 圖片 OCR 逐字稿：通常更短。
- 影音逐字稿：中文口語約每分鐘 200~250 字。
  - 3 分鐘影片 ≈ 700 字 ≈ ~1,000 tokens → 沒問題
  - 30 分鐘影片 ≈ 7,000 字 ≈ ~10,000 tokens → 仍然放得下
  - 60 分鐘以上 ≈ 20,000+ tokens → **接近上限，需處理**

**結論：N=20 的單次呼叫在 32k 內是安全的，唯一風險是超長影音逐字稿。**

處理超長逐字稿，建議優先序：

1. **截斷**：取前 8,000 字 + 後 2,000 字。主題分類通常在開頭即可判定，成本最低。
2. **分段投票**：把逐字稿切成 K 段，每段各跑一次 N 題，取每個 category 的 max 或 mean 機率。
   成本 × K，且會改變機率分布 → **需重新校準閾值**，不建議作為預設。
3. **兩階段**：先用便宜模型做摘要，再把摘要餵給 Jev。多一次呼叫，且摘要會遺失細節。

> [!WARNING]
> 把 N 題拆成多次呼叫（例如每次 5 題）**不會省錢，反而變貴**：
> 訊息本文會被重複送 N/5 次。這正是 [20250623](../meetings/2025/20250623.md) 中
> bil 對「一個 classifier 處理一個 category」的疑慮。
> 只有在「問題區本身塞不下」時才需要拆，而 N=20 顯然沒有這個問題。
> **建議：一篇訊息一次呼叫、N 題一起問。**

### 3.3 Jev 的已知限制與風險

- **第三方模型**：`typesafe/jev` 標示為 Third-party，條款見 <https://docs.typesafe.ai/legal.md>。
  訊息內容會送往第三方，需確認是否符合 Cofacts 的資料政策（Cofacts 訊息本身是公開的 open data，風險相對低，但仍應確認）。
- **中文（繁體／台灣語境）能力未知**：官方範例全為英文客服場景。
  Cofacts 的分類高度依賴台灣在地脈絡（如「農林漁牧政策」「中國影響力」）。**這是最大的未知數，必須實測。**
- **calibrated 是宣稱，不是保證**：仍須用 17K ground truth 自行驗證校準品質
  （reliability diagram：預測機率 0.8 的樣本是否真的有 80% 為正）。
- **模型版本漂移**：回應中的 `model` 欄位（如 `jev-1.13.0`）應寫進 `aiModel`，
  以便日後回溯不同版本的表現。
- 帳號中 `/accounts/{id}/ai/models/search` 查不到 `typesafe/jev`
  （搜尋 `jev`、`typesafe` 皆為空），代表此 partner model 可能需要在 dashboard 另行啟用。**使用前需先確認帳號可用性。**

## 4. 成本估算

### 4.1 Jev 的單價

> [!WARNING]
> **來源待證。** 以下單價為 mrorz 口頭提供，本文無法獨立驗證：
> Cloudflare 官方文件對 `typesafe/jev` 的 Pricing 欄位只寫
> 「[View pricing in the Cloudflare dashboard](https://dash.cloudflare.com/?to=/:account/ai/models/typesafe/jev)」，
> **未列在 [Workers AI pricing 頁](https://developers.cloudflare.com/workers-ai/platform/pricing/) 的任何價目表中**，
> 透過帳號的 models API 也查不到（同 §3.3 末項）。**實作前請在 dashboard 再確認一次。**

| 項目 | 單價 |
|---|---|
| Input tokens | **$0.042 / M tokens** |
| Output tokens | **免費（$0.00）** |

換算成 Workers AI 的計價單位（$0.011 / 1,000 Neurons）：
**$0.042 / M ÷ $0.011 × 1,000 ≈ 3,818 neurons / M input tokens**。

這個價位低於 Workers AI 價目表上所有的 text generation 模型
（最便宜的 `llama-3.2-1b-instruct` 是 $0.027 in / $0.201 out），
考量到 output 免費，**Jev 屬於極低價帶**。

### 4.1.1 免費額度可能覆蓋全部用量

Workers AI **每日前 10,000 Neurons 免費**（Free 與 Paid plan 皆有）。以每篇 4,500 input tokens 計：

| 每月訊息量 | 每日篇數 | 每日 neurons | 是否超出免費額度 |
|---|---|---|---|
| 3,000 篇 | ~100 | ~1,718 | ❌ 未超出 |
| 10,000 篇 | ~333 | ~5,727 | ❌ 未超出 |
| **17,400 篇** | **~580** | **~10,000** | **⚠️ 臨界點** |

> [!IMPORTANT]
> 以 Cofacts 目前的訊息量，**這個功能的邊際成本可能是 $0**，
> 要到每天約 580 篇（每月約 1.7 萬篇）才開始計費。

兩個但書：

1. **免費額度是否適用於 third-party partner model 需確認。**
   Cloudflare 文件明列部分模型「require a paid billing method」（kimi、glm、deepseek 系列），
   Jev 不在該名單上，但它連 pricing 頁都沒列，不能只靠推論。
2. 補跑 script（§6.5）一次掃大量舊訊息時**會瞬間衝破每日額度**，
   這部分要當作付費用量估算（見 §4.3 末）。

### 4.2 每篇訊息的 token 用量

| 項目 | 估計 |
|------|------|
| input（問題區 ~4,000 + 一般訊息本文 ~500） | **~4,500 tokens** |
| output（20 題 noul，每題僅一個機率值） | **~250 tokens** |

以官方範例反推，3 題的 output 為 41~73 tokens，20 題約 200~300 tokens，屬合理外插。

### 4.3 情境成本

因為 output 免費，**成本完全由 input 決定**：4,500 tokens × $0.042/M = **$0.000189 / 篇**。

| 用量 | 篇數 | 成本（不計免費額度） |
|---|---|---|
| 每月 3,000 篇 | 3,000 | **$0.57** |
| 每月 10,000 篇 | 10,000 | **$1.89** |
| 重跑 17K ground truth dataset | 17,000 | **$3.21** |
| 回填全部既有訊息（`articles` index ~279,286 筆） | 279,286 | **$52.8** |

即時分類的部分（前兩列）**大機率落在每日免費額度內**（§4.1.1）。
唯一需要編列預算的是**一次性回填**：把 28 萬筆舊訊息全部分類約 **$53**，
且會連續數日衝破免費額度——建議補跑 script 支援限速，分散到數週執行，或直接接受這筆一次性費用。

> [!NOTE]
> output 免費還有一個設計上的意涵：**增加 category 數量（N）幾乎不增加 output 成本**，
> 成本只隨「問題區的文字長度」成長。
> 因此 criteria 可以寫得詳細一點以換取準確率，不必為了省 token 而寫得太精簡——
> 但仍受 §3.2 的 32k context 限制。

### 4.4 與 2021 年 BERT 主機對比

2021 年的做法需要一台常駐 GPU host 跑 `rumors-ai-bert` 的 docker image。
市面上最便宜的常駐 GPU 執行個體月費也在 **USD 100~500** 量級，
且 GPU 不論有沒有訊息進來都在計費，還要加上維運與重訓練的人力。

> **Jev 方案比 2021 年的自架 GPU 便宜約 3 個數量級**（每月 $0~2 vs $100~500），
> 且成本隨訊息量線性變動、閒置時為零。
> 成本已經完全不是這件事的阻礙——**準確率（特別是中文表現）才是**。

### 4.5 與 Gemini「一個大 prompt」方案的對照

對照組是 [worker#3](https://github.com/cofacts/worker/pull/3) 現行實作：`gemini-3-flash-preview`，
一次 prompt 分辨 N 個 category，輸出 `{ categoryIds, reasoning }`。
單價為 **$0.25 / M input、$1.50 / M output**
（[pricepertoken](https://pricepertoken.com/pricing-page/model/google-gemini-3-flash-preview)、
[BenchLM](https://benchlm.ai/google/api-pricing)，2026-09 查得）。

> [!IMPORTANT]
> **以下一律用原價計算，不計入 context caching。**
> 雖然 category 定義區（~4,000 tokens）每篇都相同、理論上是理想的 cache 前綴，
> 但本設計是「每篇訊息進來就即時分類」，訊息零星抵達，
> 而 implicit cache 的存活時間是分鐘級——**大多數呼叫都會 cache miss**。
> 要讓 cache 生效必須累積一批再一起跑，那就繞回 [20250722](../meetings/2025/20250722.md) 否決掉的 batch 設計。

兩者 input 皆為 ~4,500 tokens（category 區 ~4,000 + 本文 ~500）：

| 方案 | output tokens | 每篇 | 每月 3,000 篇 | 每月 10,000 篇 |
|---|---|---|---|---|
| **Jev**（$0.042 in / 免費 out） | ~250 | **$0.000189** | **$0.57** | **$1.89** |
| Gemini 3 Flash，短 reasoning | ~300 | $0.00158 | $4.7 | $15.8 |
| Gemini 3 Flash，中等 reasoning | ~600 | $0.00203 | $6.1 | $20.3 |
| Gemini 3 Flash + thinking | ~1,500 | $0.00338 | $10.1 | $33.8 |
| Gemini 3 Flash + 較長 thinking | ~3,000 | $0.00563 | $16.9 | $56.3 |

**Jev 比 Gemini 便宜 8~30 倍**（視 Gemini 的 reasoning / thinking 長度而定），
且 Jev 在 Cofacts 的量級下大機率落在免費額度內，而 Gemini 沒有等價的免費額度。

三點觀察：

1. **Gemini 的 input 成本就贏不了**：4,500 × $0.25/M = $0.001125/篇，
   已經是 Jev 全額成本（$0.000189）的 **6 倍**，還沒算 output。
2. **Gemini 的變數在 output，Jev 沒有這個變數**。
   Gemini 從短 reasoning 到開 thinking 差 2.1 倍
   （[20250623](../meetings/2025/20250623.md) 記到「thinking token 會算在 max output token 裡」），
   而且這段 reasoning **不能為了省錢砍掉**——
   [20250722](../meetings/2025/20250722.md) 的結論是「reason 應該放在 category 之前才有 CoT 之效」。
   Jev 的 output 免費，等於這整個變數消失。
3. **但兩者的絕對金額都很小**（每月 $0.6 ~ $56）。
   即使差 30 倍，對 Cofacts 的預算來說仍然是「都付得起」。

而且 Gemini 版本的 reasoning **不能為了省錢而砍掉**——
[20250722](../meetings/2025/20250722.md) 的結論是「reason 應該放在 category 之前才有 CoT 之效」，
那段 output 是刻意要的。

**除了單價，兩者在「調整閾值」上的差異更大：**

| 動作 | Gemini | Jev |
|---|---|---|
| 取得 per-category 信心值 | 只能請模型自評，**未校準**，不適合當 gate | 原生 calibrated，直接可用 |
| 調整一次閾值（對 17K dataset 重跑） | $27 ~ $58 | $3.2，或 **$0**（重掃 `airesponses`，見 §6.3） |

> [!NOTE]
> **結論：Jev 在成本上明顯勝出（便宜 8~30 倍，且可能全在免費額度內），
> 但兩者的絕對金額都小到不足以單獨決定選型。**
> 真正該決定的仍是 **per-category precision / recall**——
> 只是現在「Jev 比較貴」這個可能的反對理由已經排除了。

## 5. Confidence gate 的校準流程

1. **準備資料**：從 [cofacts/ground-truth](https://github.com/cofacts/ground-truth)（17K，已在 Langfuse dataset）
   切出 train/dev/test。注意 [20250722](../meetings/2025/20250722.md) 踩過的坑：
   **title 含 emoji 會導致 ID 對不到**，先確認對齊邏輯。
2. **全量推論**：對 dev set 每篇跑一次 Jev，保存 N 個 noul 分數（不要先套閾值）。
3. **逐 category 畫 PR 曲線**：對每個 category 獨立掃閾值 0.00~1.00。
4. **逐 category 訂閾值**，而非全域單一閾值。建議目標：
   - 因為結果會直接寫進公開資料、且網友會看到，**precision 優先於 recall**。
   - 建議先以 **precision ≥ 0.9** 為硬約束，在此前提下取 recall 最大的閾值。
   - 樣本數過少的 category（如 2021 年的「愛滋病」僅 12 筆）**不應上線自動標記**，
     或把閾值訂得極高（如 0.95）。
5. **校準檢查**：畫 reliability diagram。若 Jev 的機率明顯偏移，
   可加一層 Platt scaling / isotonic regression 再套閾值。
6. **寫回時保留原始分數**：`aiConfidence` 存 noul 原值（不是 0/1），
   `aiModel` 存 `jev-x.y.z`。日後調整閾值時，可用既有資料重算而不必重跑推論。
7. **線上持續驗證**：用 `ArticleCategoryFeedback` 的正負評，
   搭配既有的 Script 1 / Script 2 流程，週期性重算實際 precision，必要時調整閾值。

## 6. 在 rumors-api 掛載的實作草案

### 6.1 掛載點

| Mutation | 檔案 | 分類器可用的文字 |
|---|---|---|
| `CreateArticle` | `src/graphql/mutations/CreateArticle.js` | `text`（args 直接可得） |
| `CreateMediaArticle` | `src/graphql/mutations/CreateMediaArticle.js` | 逐字稿，來自 `getAIResponse({ type: 'TRANSCRIPT' })` 的 `aiResponse.text` |

`CreateArticle` 的 resolver 已有明確的 promise 相依圖（避免對同一 article 平行更新造成
`version_conflict_engine_exception`）。分類是**寫入 `articleCategories` 陣列**，
而 `createArticleCategory` 用的是 painless script update，與 hyperlinks / replyRequest 的更新互斥性需注意
——這也是為什麼**不該把分類塞進 mutation 的 `Promise.all` 等待鏈**。

`CreateMediaArticle` 已有現成範例可循：AI 逐字稿的寫入就是
「失敗只 `console.warn`、不影響 mutation 回傳」的 fire-and-forget 模式。

### 6.2 架構：rumors-api 直接呼叫 Workers AI REST API

```
CreateArticle / CreateMediaArticle
  └─ (fire-and-forget) classifyArticle({ articleId, text })
       ├─ 取 categories（本地 cache，見 6.4）
       ├─ POST https://api.cloudflare.com/client/v4/accounts/{id}/ai/run
       │    { model: 'typesafe/jev', input: { state, questions } }
       ├─ createAIResponse({ type: 'CATEGORY' })  ← 存下 N 個原始機率
       └─ 對每個 noul ≥ 該 category 閾值者：
            createArticleCategory({ articleId, categoryId, user, aiModel, aiConfidence })
```

需要的改動：

1. **`src/util/jev.ts`**：包裝 Workers AI REST 呼叫。
   - 環境變數 `CLOUDFLARE_ACCOUNT_ID`、`CLOUDFLARE_AI_API_TOKEN`
     （`.env.sample` 已有 `CLOUDFLARE_ACCESS_TEAM_DOMAIN` 的前例）。
   - **未設定時整個功能 no-op**，本地開發與 CI 不受影響（比照現有 AI 功能的寫法）。
   - 設定 timeout（建議 30s）與 `AbortController`，不可讓 promise 無限掛著。
   - 用 `src/util/langfuse.ts` 包一層 trace，沿用既有 observability。
2. **`src/util/classifyArticle.ts`**：組 questions、呼叫 Jev、套閾值、寫回。
   - 閾值表（per-category）建議放程式碼常數或設定檔並版本控管，
     每次調整都要能對應到一次 benchmark。
3. **`CreateArticle.js`**：在 `newArticlePromise` resolve 且 `result === 'created'` 時呼叫，
   **不加入最後的 `Promise.all`**——比照既有的 `archiveUrlsFromText(text)` 寫法。
4. **`CreateMediaArticle.js`**：掛在 `writeAITranscript()` 成功之後
   （逐字稿寫入後才有文字可分類），包在既有的 `.catch(e => console.warn(...))` 之內。
5. **`src/scripts/classifyArticles.ts`**（見 6.5）：補跑用的 batch script。

### 6.3 把原始機率存成 `AIResponse`

Jev 每次回傳 N 個機率，但只有超過閾值的會進 `articleCategories`。
**其餘的分數若不留下，日後每次調閾值都得重跑推論**——這會抵銷掉選 Jev 的最大好處。

建議：

- `AIResponseTypeEnum` 新增 `CATEGORY`（現有為 `AI_REPLY`、`TRANSCRIPT`）。
- 用既有的 `createAIResponse()` 把整包 `answers`（N 個 `noul` 值）與 `usage`
  存進 `airesponses` index，`docId` 用 articleId。
- `articleCategories` 只存過閾值的結果，維持 `aiModel` = Jev 回傳的 `model`（如 `jev-1.13.0`）、
  `aiConfidence` = 該題的 noul 原值。

如此一來，調整閾值只要重掃 `airesponses`，不必重跑推論。

> [!NOTE]
> 在 §4.1 的單價下，重跑 17K dataset 只要 $3.2，所以這個設計的理由**不是省錢**，
> 而是：可重現（同一批分數重複比較）、快（不必等數千次 API 呼叫）、
> 以及保留 production 上每篇訊息的完整機率分布供日後分析。

### 6.4 Category 清單的取得

worker 版本是每次分類都打一次 GraphQL `ListCategories(first: 50)`。
在 rumors-api 內不必如此——直接讀 `categories` index 並在 process 內 cache
（categories 幾乎不變動，TTL 設 1 小時即可）。
若 category 有增刪，閾值表也必須跟著更新，因此**建議把「新增 category」視為一次需要重新 benchmark 的變更**。

### 6.5 補跑機制（取代 Workflow 的 durable execution）

放棄 Cloudflare Workflow 後，失去的是自動重試與跨 process 重啟的持久性。
補救方式是一支 script，而**這支 script 本來就必須存在**：
既有訊息（~28 萬筆）、新增的 category、Jev 呼叫失敗的訊息、閾值調整後的重算，都需要它。

- `src/scripts/classifyArticles.ts`
  - 條件：`articleCategories` 中沒有 `aiModel` 符合目前 Jev 版本者
  - 支援 `--from` / `--limit` / `--dry-run`，並用 `getAllDocs` 掃 ES（既有 util）
  - 併發上限（建議 5~10）以避開 Workers AI 的 rate limit
- 以 cron 每日跑一次，即可涵蓋所有 fire-and-forget 漏掉的案例。

> [!NOTE]
> 這是刻意的取捨：用「即時呼叫 + 每日補跑」取代「durable workflow」。
> 對一個結果本來就非即時呈現的功能而言，這個一致性等級足夠。

### 6.6 邊界情況與注意事項

- **`createArticleCategory` 目前沒有 `retry_on_conflict`**
  （`src/graphql/mutations/CreateArticleCategory.js` 的 painless script update）。
  它與 `createOrUpdateReplyRequest`、`updateArticleHyperlinks` 都在更新同一份 article doc，
  射後不理的分類呼叫進來後衝突機率上升。
  **應比照 `writeAITranscript()` 的 `retry_on_conflict: 3` 補上**，否則會出現隨機失敗。
- **媒體訊息去重**：`createNewMediaArticle` 命中相同 `attachmentHash` 時回傳既有 article，
  此時不該重複分類。`CreateArticle` 有 `result === 'created'` 可判斷，**media 端目前沒有，要另外加**。
- **逐字稿失敗**：`aiResponse` 為空時 media article 的 `text` 是空字串，不可送去分類。
- **空文字 / 純網址訊息**：在 `classifyArticle` 內短路（例如 text 長度 < 10），省下呼叫費用。
- **spam / takedown**：`status` 非 `NORMAL` 的訊息不必分類。
- **併發與 rate limit**：尖峰時多篇同時進來需節流（process 內 queue 或 concurrency limit）。
- **不要阻塞 mutation**：LINE bot 使用者在等回應，分類延遲數秒完全可接受。

## 7. 結論與建議

1. **Jev 在概念上非常適合這個任務**：N 個 noul 問題直接對應「N 個 category 的信心值」，
   原生 calibrated 機率讓 precision-recall gate 可以事後調整而不必重跑推論，
   且 `aiModel` / `aiConfidence` 欄位在 rumors-api 已經存在，落地成本極低。
2. **Context window 不是問題**：N=20 的問題區約 3.3k~5.3k tokens，
   一般訊息遠低於上限；只有超長影音逐字稿需截斷處理。**不需要分批呼叫**。
3. **成本不是問題**：Jev 的 input $0.042/M、output 免費，
   每篇僅 $0.000189，Cofacts 的量級**大機率全在每日免費額度內**；
   比 2021 年常駐 GPU host 便宜約 3 個數量級，也比 Gemini 方案便宜 8~30 倍。
   唯一要編預算的是一次性回填 28 萬筆舊訊息（約 $53）。
4. **真正的風險是中文準確率**，完全未知，必須實測。

**建議的下一步（成本很低，因為基礎建設都在）：**

1. 在 Cloudflare dashboard 確認 `typesafe/jev` 在本帳號可用、驗證 §4.1 的單價，
   並確認免費額度是否適用（跑一次小量呼叫看 neurons 怎麼計）。
2. 用 Langfuse 上既有的 17K dataset，跑一次 Jev（N 個 noul）與現行 Gemini 大 prompt 的 A/B，
   比較 **cost、per-category PR 曲線、confusion matrix**——
   這正是 [20250630](../meetings/2025/20250630.md) 訂下的比較基準，指標不必重新發明。
3. 若 Jev 的 per-category precision 在合理 recall 下可達 0.9，
   就在 rumors-api 實作 `util/jev.ts` + `util/classifyArticle.ts`，並補上 per-category 閾值表。
4. 先做 `src/scripts/classifyArticles.ts` 與 `CATEGORY` 型 AIResponse，用 `--dry-run` 在小量 production 資料上驗證。
5. 最後才在 `CreateArticle` / `CreateMediaArticle` 掛上 fire-and-forget 呼叫，
   並記得補 `createArticleCategory` 的 `retry_on_conflict`。

## 8. 待確認事項

- [ ] `typesafe/jev` 在 Cofacts 的 Cloudflare 帳號是否已啟用？（dashboard）
- [ ] **驗證 §4.1 的單價**（$0.042/M input、output 免費）——目前來源為口頭，官方文件與 API 皆查不到。
- [ ] **每日 10,000 Neurons 免費額度是否適用於 third-party partner model？**
      這決定了即時分類是 $0 還是每月 $2（§4.1.1）。
- [ ] 目前 `ListCategories` 實際有幾個 category（本文以 N=20 估算）？其中幾個是 AI-only？
- [ ] 目前每月新增 article 數（本文以 3,000 / 10,000 兩種情境估算）。
      註：2026-09 的 ES reindex 記錄顯示 `articles` index 共 **279,286** 筆（[20260914](../meetings/2026/20260914.md)），
      但這是累積值，不是流量。
- [ ] 2021 年 BERT GPU host 的實際月費與停用時間點（kb 內未記載）。
- [ ] 2025 年那份一直沒結案的 benchmark 結果是否存在？（可作為 Jev 的對照組）
- [ ] [cofacts/worker](https://github.com/cofacts/worker) repo 與 [worker#3](https://github.com/cofacts/worker/pull/3)、
      [worker#2](https://github.com/cofacts/worker/issues/2) 要關閉 / archive 還是留著？
      （url-resolver 確定維持現有 gRPC 寫法，classifier 改進 rumors-api，worker 已無待辦）
- [ ] 第三方模型的資料處理條款是否可接受（<https://docs.typesafe.ai/legal.md>）。
