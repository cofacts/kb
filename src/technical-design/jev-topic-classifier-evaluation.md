---
type: DesignDoc
title: "以 Jev 實作 Cofacts Topic Classifier 之可行性評估"
tags: [cofacts, design-docs, technical-design, ai, classifier]
timestamp: "2026-10-12T21:00:00+08:00"
---

# 以 Jev 實作 Cofacts Topic Classifier 之可行性評估

> [!NOTE]
> 本文評估 Cloudflare Workers AI 上的第三方模型 [`typesafe/jev`](https://developers.cloudflare.com/ai/models/typesafe/jev/)
> 是否適合作為 Cofacts article category（topic label）分類器的推論引擎，
> 並討論其成本、context 限制，以及在 `CreateArticle` / `CreateMediaArticle` 上掛載的實作方式。
>
> 本文由 Claude Code 依據 kb 內既有會議記錄與 repo 程式碼整理。
> §1~§6 為實測前的調查與估算；**§7 為以 ground truth 1,000 篇實測、比較 7 個分類方案的結果**
> （Jev、Clef、clef-flash 三個決策模型搭配兩種題目寫法，以及 Claude Haiku 5.5 直接輸出分類清單）。
> §8 結論與 §9 待確認事項已依實測更新。

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
  - **實測更新**：不需另行啟用，但要先在 AI Gateway 儲值 credits（unified billing）才能呼叫，見 §7.8。

## 4. 成本估算

### 4.1 Jev 的單價

> [!NOTE]
> **實測更新（2026-10）**：[Jev 模型頁](https://developers.cloudflare.com/ai/models/typesafe/jev/)現已列出
> Input $0.042 / M、Output $0.00 / M、Cached input $0.00 / M，與下表一致；
> 實測每篇 input 約 4,049 tokens、output 固定 416 tokens（免費），見 §7.8。
>
> 以下為原始記錄：單價為 mrorz 口頭提供，撰寫當時無法獨立驗證：
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
   **實測更新：不適用。** Jev 走 AI Gateway unified billing，必須先儲值 credits；
   未儲值時呼叫失敗，而同帳號的 Workers AI 自家模型（Clef）正常。見 §7.8。
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

## 7. 實測結果：分類方案比較

> [!NOTE]
> 實測於 2026-10-11 ~ 10-12 進行。本節所有表格可在
> [`jev-topic-classifier-evaluation/`](jev-topic-classifier-evaluation/) 以 `report.py` 重算
> （`results/` 只含 article ID 與分數或分類清單，不含內文）。

> [!IMPORTANT]
> **TL;DR**
>
> - 比較了 **7 個方案**：三個決策模型（Jev、Clef、clef-flash）搭配兩種題目寫法（題目 A、題目 B），
>   以及讓 Claude Haiku 5.5 直接輸出分類清單（effort low、medium）。
> - **中文準確率可用，但需要門檻把關**：決策模型的逐類 ROC-AUC 平均 0.96~0.97，
>   最好的方案 micro-F1 約 **0.75**。
> - **題目怎麼寫，影響比選哪個模型大**：同一個模型，題目 B 比題目 A 的 micro-F1 高 **0.02~0.07**（顯著）；
>   同樣用題目 B 時，Jev、Clef、Haiku（medium）之間的差距在 **±0.01** 內，不顯著。
> - **LLM 清單做法準確率相當，但不能調門檻**：Haiku 5.5（medium）micro-F1 0.742，與 Jev／Clef 搭題目 B 打平；
>   但它沒有 confidence，只有一個固定的工作點，成本是 Jev 的 3.4 倍，延遲 p50 約 2.6 秒（Jev 0.27 秒）。
> - **量到的 precision 是下限**：ground truth 幾乎都是單標籤；抽查高分誤判，約 3/4 以上其實是合理的標記。
> - **建議：Jev 搭配題目 B**，最便宜、最快、可調門檻。
>   每篇至少要一個標籤時用「分數 ≥ 0.7、最多取前 2 個；都沒過就取最高分 1 個」（F1 0.748）；
>   要高 precision 時逐類訂門檻（隨機子集上 P 0.976 / R 0.630）。
> - **注意**：題目 B 的條件是參考題目 A 在同一份樣本上的誤判寫的，題目 B 的分數可能略為樂觀，
>   正式採用前應在另一份沒看過的樣本上驗證（§7.10）。

### 7.1 實驗設定

**資料**：[cofacts/ground-truth](https://github.com/cofacts/ground-truth) 的 `20211210_17111.zip`
（實際為 gzip 壓縮的 tar，內含 17,111 個 `{id, createdAt, tags, text, url}` JSON）。

- **排除**：帶有以下任一標籤的文章整篇排除，剩 10,384 篇。
  - AI 專用標籤：有意義但不包含在以上標籤（`nT2n7nEBrIRcahlY6QqF`）、無意義（`nj2n7nEBrIRcahlY-gpc`）、只有網址其他資訊不足（`oD2o7nEBrIRcahlYFgpm`）
  - 已停用（🚧）：性少數與愛滋病（`kz3c7XEBrIRcahlYxAp6`）、基本人權問題（`lj2m7nEBrIRcahlY6Ao_`）
- **抽樣 1,000 篇**（固定 seed），所有方案都用同一份：
  1. 先確保每個類別至少有 60 則正例（愛滋病全部只有 6 則），共 687 篇；
  2. 其餘 313 篇從剩下的文章**隨機抽樣**，保留實際分布。
  - 因為稀有類別被刻意補足，全樣本上稀有類別的 precision 會比實際上線時樂觀；
    下文另外列出「隨機抽樣子集」的結果作為較接近實際分布的參考。

**類別**：`ListCategories`（`api.cofacts.tw/graphql`，2026-10-11 抓取，共 21 個）扣掉上述 5 個後的 16 類，
`id`、`title`、`description` 都用原文。

<details><summary>16 個類別、輸出陣列順序與樣本中的正例數</summary>

| i | Category ID | 名稱 | 樣本正例數 |
|---:|---|---|---:|
| 0 | `kj287XEBrIRcahlYvQoS` | 中國政治宣傳 | 68 |
| 1 | `nD2n7nEBrIRcahlYwQoW` | 詐騙 | 60 |
| 2 | `oT2o7nEBrIRcahlYKQoM` | 台灣政治、政黨 | 182 |
| 3 | `covid19` | COVID-19 疫情 | 61 |
| 4 | `medical` | 疾病、醫藥 | 60 |
| 5 | `intl` | 跨國互動 | 60 |
| 6 | `aids` | 愛滋病 | 6 |
| 7 | `lD3h7XEBrIRcahlYeQqS` | 性別議題 | 60 |
| 8 | `lT3h7XEBrIRcahlYugqq` | 保健秘訣、食品安全 | 257 |
| 9 | `lz2n7nEBrIRcahlYDgri` | 農林漁牧政策 | 60 |
| 10 | `mD2n7nEBrIRcahlYLAr7` | 電力、能源 | 60 |
| 11 | `mT2n7nEBrIRcahlYTArI` | 環保、生態 | 60 |
| 12 | `mj2n7nEBrIRcahlYdArf` | 優惠措施、新法規、政策宣導 | 84 |
| 13 | `mz2n7nEBrIRcahlYnQpz` | 科技、資安、隱私 | 60 |
| 14 | `nz2o7nEBrIRcahlYBgqQ` | 商業廣告 | 62 |
| 15 | `oj2o7nEBrIRcahlYRAox` | 連署、集氣、協尋、捐贈 | 60 |

</details>

#### 比較的方案

| 方案 | 做法 | 模型 | 題目 | 輸出 |
|---|---|---|---|---|
| `jev-a` / `jev-b` | 決策模型 | `typesafe/jev`（`jev-1.13.0`） | A / B | 16 個類別各一個 0~1 的機率 |
| `clef-a` / `clef-b` | 決策模型 | `@cf/cloudflare/clef`（27B） | A / B | 同上 |
| `clef-flash-a` | 決策模型 | `@cf/cloudflare/clef-flash`（9B） | A | 同上 |
| `haiku-low` / `haiku-medium` | LLM 輸出清單 | Claude Haiku 5.5，effort low / medium | 與 B 相同的資訊 | 所屬類別的 id 清單（可為空） |

- **決策模型**：一篇文章一次呼叫，16 個 `noul`（是／否）問題同時送出，回傳每題的機率；
  門檻與選擇策略由我們事後決定（§7.5）。clef-flash 在題目 A 下就明顯較弱，題目 B 沒有再跑。
- **LLM 輸出清單**：把 16 個分類一次放進 prompt，讓 LLM 直接回答「這則訊息屬於哪些分類」。
  這是「傳統 LLM 做法」的代表；Haiku 5.5 是目前最便宜的 Claude 模型（$0.10 / M input、$0.50 / M output）。

#### 決策模型的題目：A 與 B

兩種題目共用同一個 `state` 與 `instructions`，**只有 `criteria` 不同**。

- `state`：「以下是台灣民眾轉傳到 Cofacts 真的假的（協作查核平台）請求查證的一則訊息：」＋ 文章內文（超過 4,000 字截斷，樣本中僅 1% 文章超過 3,100 字）。
- `instructions`：以「誰會有興趣」為判斷標準，後面接 `ListCategories` 的 description 原文。以中國政治宣傳為例：

```text
這則訊息是否屬於 Cofacts 的「中國政治宣傳」分類？判斷標準是：下列「目標編輯」會不會想看、想查核或想回應這則訊息。

目標編輯：
- 關注中國動態的人或政黨，如台灣基進、時代力量、促統黨、新黨。
- 關注兩岸與資訊戰的學術單位。

兩岸三地、疆獨藏獨相關事件的消息，或來自中國官方的論述、對中國事務全然正面的描述等疑似為大外宣一環的訊息。
```

| | 題目 A（通用判斷條件） | 題目 B（逐類具體條件） |
|---|---|---|
| `criteria.true` | 16 類都是同一句：「訊息落在『X』的範圍，目標編輯會有興趣處理它」 | 每類各自寫出看得到的判斷條件：訊息裡出現什麼、在談什麼才算 |
| `criteria.false` | 16 類都是同一句：「訊息與『X』無關，目標編輯不會特別想處理它」 | 「與 X 無關」；4 類另加**排除條件**（這類訊息屬於別的分類） |
| 每篇 input tokens（Jev 計） | 約 4,049 | 約 4,190（+3%） |

題目 B 的撰寫原則：

1. `true` 寫成具體條件，例如詐騙寫出「付款、繳押金、提供個資或帳號密碼、加陌生帳號、點連結領贈品、假冒政府或企業」。
2. **排除條件只加在分類定義本身就重疊的地方**：疾病醫藥（vs 保健偏方）、COVID-19（vs 紓困振興）、農林漁牧（vs 一般食物話題）、科技資安（vs 只是透過 LINE 傳播）。
3. **不加會和 ground truth 多標籤習慣衝突的排除條件**。ground truth 中「詐騙＋商業廣告」同時出現 264 次、
   「優惠措施＋台灣政治」139 次、「中國政治宣傳＋台灣政治」126 次；要模型二選一，判對了也會被算錯。

<details><summary>題目 B 的 16 類 criteria 全文與撰寫理由</summary>

| 類別 | 符合（`criteria.true`） | 不符合（`criteria.false`） | 排除 | 撰寫理由 |
|---|---|---|:---:|---|
| 中國政治宣傳 | 訊息的重點是中國（含港澳、新疆、西藏）的政治、軍事、統戰或對外宣傳，例如美化中國、宣揚中國強大、貶低台灣或西方、兩岸統獨論述 | 訊息與中國無關，或只是順帶提到中國，主要在談別的事 |  | 只要提到中國就給高分；改成要求「重點是中國」 |
| 詐騙 | 訊息試圖讓人付款、繳押金、提供個資或帳號密碼、加陌生帳號為好友、點連結領取免費貼圖或贈品，或假冒政府、銀行、知名企業 | 訊息沒有上述騙取金錢、個資或點擊的手法 |  | 題目 A 只靠 description「詐騙貼圖、假行銷手法」，太簡略；列出常見手法 |
| 台灣政治、政黨 | 訊息批評或支持台灣的政黨、政治人物、選舉、公投或執政表現，會影響讀者對某個政治立場的觀感 | 訊息與台灣的政黨、政治人物或選舉無關 |  | 寫明「批評或護航」的對象範圍 |
| COVID-19 疫情 | 訊息談 COVID-19（新冠肺炎、武漢肺炎）的病毒、變種、疫苗、篩檢、防疫措施、確診或疫情狀況 | 訊息與 COVID-19 無關；或只是紓困、振興券等與傳染病防治無關的經濟措施（屬於「優惠措施、新法規、政策宣導」） | ✓ | description 原本就註明紓困、振興不屬此類，搬進 criteria |
| 疾病、醫藥 | 訊息談的是傳染病、癌症，或特定藥物、疫苗、醫療器材的效果與風險，醫師或公衛師會想回應 | 訊息與疾病醫藥無關；或只是食療、偏方、養生習慣、日常保健（這些屬於「保健秘訣、食品安全」） | ✓ | 題目 A 最大的錯誤來源：一般保健文章被大量標成此類 |
| 跨國互動 | 訊息的重點是兩個以上國家或國際組織之間的互動，例如外交、貿易戰、軍事對峙、國際援助、各國人民的往來或旅外經驗 | 訊息只談單一國家內部的事，或外國只是背景、不是重點 |  | 只要出現外國就給高分；改成要求「互動是重點」 |
| 愛滋病 | 訊息提到愛滋病、HIV、PrEP 或愛滋感染者 | 訊息與愛滋病無關 |  | 列出關鍵詞 |
| 性別議題 | 訊息談性別平等教育、同性婚姻、LGBT、性別刻板印象、墮胎或身體自主等性別議題 | 訊息與性別議題無關 |  | 補上同婚、墮胎等 ground truth 常見主題 |
| 保健秘訣、食品安全 | 訊息宣稱某種食物、飲食方式、偏方、運動或生活習慣對健康有益或有害，或談食品添加物、食品安全 | 訊息與飲食、養生或食品安全無關 |  | 與「疾病、醫藥」對應地寫清楚本類範圍；未加排除，因為 2021 年以前的藥物文章在 ground truth 多標在本類 |
| 農林漁牧政策 | 訊息談農、林、漁、牧業的生產、產銷、價格、進出口、動植物病蟲害，或相關的政府政策與補助 | 訊息與第一級產業無關；只是一般的食物或料理話題不算 | ✓ | 避免把一般食物話題標成農業 |
| 電力、能源 | 訊息談發電方式（核能、火力、綠電）、電力供應與停電、電價，或能源政策 | 訊息與電力或能源無關 |  | 列出具體主題 |
| 環保、生態 | 訊息的重點是動植物保育、氣候變遷、空氣或水污染、廢棄物，或開發對環境的影響 | 訊息與環境或生態無關 |  | 列出具體主題；未排除能源，因為 ground truth 中火力發電空污常兩類都標 |
| 優惠措施、新法規、政策宣導 | 訊息說明或誤傳政府（中央或地方）的補助、津貼、優惠、新法規、罰則或公共服務措施 | 訊息與政府的政策措施無關 |  | 寫明是「政府的」措施 |
| 科技、資安、隱私 | 訊息的主題是科技本身，例如 5G、AI、手機或電腦的功能與風險、資訊安全、個資與隱私 | 訊息與科技無關；或只是透過手機、LINE、網路傳播，主題是別的事情 | ✓ | 題目 A 常因為訊息「在 LINE 上傳」或「附網址」就標成科技 |
| 商業廣告 | 訊息是商家（或自稱商家）推廣商品、服務或促銷活動，例如折扣、優惠碼、新品、贈品活動 | 訊息與商品或服務的推廣無關 |  | 列出具體形式；未排除詐騙，因為 ground truth 中兩類共同出現 264 次 |
| 連署、集氣、協尋、捐贈 | 訊息呼籲大家連署、協尋失蹤的人或寵物、捐款捐物、投票、集氣或轉發幫忙 | 訊息沒有這類呼籲 |  | 列出具體形式 |

</details>

> [!WARNING]
> 題目 B 的條件是參考題目 A 在**同一份 1,000 篇樣本**上的誤判（§7.7）寫出來的。
> 雖然條件都是依分類定義改寫、沒有針對個別文章，題目 B 的分數仍可能略為樂觀；
> 正式採用前，應在另一份沒看過的樣本上確認題目 B 的優勢仍在。

#### LLM 輸出清單的 prompt

- 經 Cloudflare 的 Anthropic Messages 相容端點 `POST /accounts/{id}/ai/v1/messages`（模型 id `anthropic/claude-haiku-5.5`）呼叫，
  以 AI Gateway unified billing 扣款，不需要 Anthropic API key。程式用 Anthropic Python SDK，
  `base_url` 指向 `https://api.cloudflare.com/client/v4/accounts/{id}/ai`，`auth_token` 帶 Cloudflare token（`llm_run.py`）。
- 輸出用 **structured outputs**（`output_config.format` 的 JSON schema）限定為 `{"categories": [...]}`，
  陣列元素只能是 16 個 category id 之一。
- 為了公平，prompt 給的資訊和題目 B 相同：每類的名稱、id、description 原文、題目 B 的符合／不符合條件。
- Haiku 5.5 預設開啟 adaptive thinking；effort 分 low 與 medium（預設值）各跑一次。

```text
你是 Cofacts 真的假的（台灣的協作查核平台）的訊息分類員。民眾會把在 LINE 等管道收到、想查證的訊息轉傳給 Cofacts，
你要替每則訊息標上主題分類，讓對該主題有興趣、擅長回應的編輯能找到它。

判斷原則：每個分類都列出了「目標編輯」。一則訊息屬於某分類，是指該分類的目標編輯會想看、想查核或想回應它。
一則訊息可以屬於多個分類，也可以不屬於任何分類（此時回傳空陣列）。只標你有把握的分類。

# 分類

## 疾病、醫藥
id: medical
目標編輯：
- 醫師、護理師
- 公衛師

傳染病、癌症，以及各種藥物的相關傳言與資訊。
符合：訊息談的是傳染病、癌症，或特定藥物、疫苗、醫療器材的效果與風險，醫師或公衛師會想回應
不符合：訊息與疾病醫藥無關；或只是食療、偏方、養生習慣、日常保健（這些屬於「保健秘訣、食品安全」）

……（其餘 15 類同樣格式）
```

user message 與決策模型的 `state` 相同；輸出範例：`{"categories": ["medical", "covid19"]}`。

### 7.2 方案總覽

| 方案 | 做法 | 題目 | 逐類 AUC 平均 | 規則 F1 | 逐類門檻 F1 | P≥0.9 設定（隨機子集）P / R | 每篇標籤數 | 每 1 萬篇 | 延遲 p50 | 可調門檻 |
|---|---|---|---:|---:|---:|---|---:|---:|---:|:---:|
| `jev-a` | Jev（決策模型） | A | 0.969 | 0.698 | 0.721 | 0.967 / 0.649 | 1.46 | $1.70 | 0.28s | ✓ |
| `jev-b` | Jev（決策模型） | B | 0.973 | 0.748 | 0.739 | 0.976 / 0.630 | 1.38 | $1.76 | 0.27s | ✓ |
| `clef-a` | Clef（決策模型） | A | 0.967 | 0.680 | 0.702 | 0.960 / 0.683 | 1.39 | $8.21 | 0.47s | ✓ |
| `clef-b` | Clef（決策模型） | B | 0.974 | 0.750 | 0.750 | 0.953 / 0.633 | 1.38 | $8.49 | 0.46s | ✓ |
| `clef-flash-a` | clef-flash（決策模型） | A | 0.959 | 0.671 | 0.684 | 0.942 / 0.658 | 1.40 | $1.30 | 0.78s | ✓ |
| `haiku-low` | Claude Haiku 5.5（effort low）（LLM 輸出清單） | B 的條件 | — | 0.724（清單） | — | — | 1.64 | $5.29 | 1.87s | ✗ |
| `haiku-medium` | Claude Haiku 5.5（effort medium）（LLM 輸出清單） | B 的條件 | — | 0.742（清單） | — | — | 1.54 | $5.91 | 2.55s | ✗ |

欄位說明：

- **規則 F1**：決策模型套用「分數 ≥ 0.7、最多取前 2 個；都沒過則取最高 1 個」的 micro-F1（每篇至少一個標籤）；LLM 為清單本身的 micro-F1。
- **逐類門檻 F1**：每類各自找最佳門檻（5-fold cross validation，避免在同一批資料上調參的樂觀偏差）。
- **P≥0.9 設定**：每類找出 precision ≥ 0.9 的最低門檻（同樣 CV），在接近實際分布的隨機子集上量到的 precision / recall。
- **延遲 p50**：8 併發下的單次請求延遲。

**方案之間的差距是否顯著**（全樣本 micro-F1，paired bootstrap 1,000 次）：

| 比較 | 差距（micro-F1） | 95% CI | 顯著 |
|---|---:|---|:---:|
| `jev-a`（規則） − `clef-a`（規則） | +0.018 | [+0.002, +0.032] | ✓ |
| `jev-a`（逐類門檻 max F1） − `clef-a`（逐類門檻 max F1） | +0.019 | [+0.005, +0.034] | ✓ |
| `jev-a`（逐類門檻 P≥0.9） − `clef-a`（逐類門檻 P≥0.9） | -0.035 | [-0.053, -0.017] | ✓ |
| `jev-b`（規則） − `clef-b`（規則） | -0.002 | [-0.015, +0.012] |  |
| `jev-b`（逐類門檻 max F1） − `clef-b`（逐類門檻 max F1） | -0.011 | [-0.024, +0.004] |  |
| `jev-b`（逐類門檻 P≥0.9） − `clef-b`（逐類門檻 P≥0.9） | +0.005 | [-0.015, +0.024] |  |
| `jev-b`（規則） − `jev-a`（規則） | +0.050 | [+0.036, +0.063] | ✓ |
| `jev-b`（逐類門檻 max F1） − `jev-a`（逐類門檻 max F1） | +0.018 | [+0.007, +0.029] | ✓ |
| `jev-b`（逐類門檻 P≥0.9） − `jev-a`（逐類門檻 P≥0.9） | -0.006 | [-0.020, +0.007] |  |
| `clef-b`（規則） − `clef-a`（規則） | +0.070 | [+0.055, +0.084] | ✓ |
| `clef-b`（逐類門檻 max F1） − `clef-a`（逐類門檻 max F1） | +0.048 | [+0.036, +0.060] | ✓ |
| `clef-b`（逐類門檻 P≥0.9） − `clef-a`（逐類門檻 P≥0.9） | -0.046 | [-0.061, -0.030] | ✓ |
| `haiku-medium`（清單） − `jev-b`（規則） | -0.006 | [-0.021, +0.009] |  |
| `haiku-medium`（清單） − `jev-b`（逐類門檻 max F1） | +0.002 | [-0.013, +0.018] |  |
| `haiku-medium`（清單） − `clef-b`（規則） | -0.008 | [-0.024, +0.006] |  |
| `haiku-medium`（清單） − `clef-b`（逐類門檻 max F1） | -0.009 | [-0.022, +0.007] |  |
| `haiku-low`（清單） − `jev-b`（規則） | -0.024 | [-0.041, -0.008] | ✓ |
| `haiku-low`（清單） − `jev-b`（逐類門檻 max F1） | -0.016 | [-0.031, -0.001] | ✓ |
| `haiku-low`（清單） − `clef-b`（規則） | -0.026 | [-0.040, -0.010] | ✓ |
| `haiku-low`（清單） − `clef-b`（逐類門檻 max F1） | -0.027 | [-0.041, -0.010] | ✓ |

讀法：

- **同一個模型，題目 B 都比題目 A 好**：規則 F1 +0.05~0.07、逐類門檻 +0.02~0.05，皆顯著。
  唯一例外是「precision ≥ 0.9」設定，原因見 §7.7（主要是 ground truth 漏標）。
- **同一種題目，模型之間差距小**：題目 A 時 Jev 與 Clef 互有勝負（±0.02~0.035）；
  **題目 B 時 Jev 與 Clef 已無顯著差異**。
- **Haiku 5.5（medium）與題目 B 的決策模型打平**；effort low 則顯著略差約 0.02。

### 7.3 不同 confidence 門檻的 Precision / Recall / F1

僅適用於決策模型（LLM 清單沒有 confidence）。所有類別共用同一個門檻，分數 ≥ 門檻即視為標上該類。
Micro＝把所有 (文章, 類別) 配對攤平計算；Macro＝每類各算再平均（稀有類別與大類別等權）。

| 門檻 | `jev-a` micro P / R / F1 | `jev-b` micro P / R / F1 | `clef-a` micro P / R / F1 | `clef-b` micro P / R / F1 | `clef-flash-a` micro P / R / F1 |
|---:|---|---|---|---|---|
| 0.1 | 0.281 / 0.984 / **0.437** | 0.332 / 0.970 / **0.495** | 0.332 / 0.978 / **0.496** | 0.265 / 0.982 / **0.417** | 0.282 / 0.971 / **0.437** |
| 0.2 | 0.380 / 0.950 / **0.542** | 0.426 / 0.935 / **0.586** | 0.452 / 0.933 / **0.609** | 0.399 / 0.957 / **0.563** | 0.383 / 0.921 / **0.541** |
| 0.3 | 0.448 / 0.924 / **0.604** | 0.491 / 0.911 / **0.638** | 0.520 / 0.878 / **0.653** | 0.482 / 0.919 / **0.632** | 0.462 / 0.873 / **0.604** |
| 0.4 | 0.498 / 0.887 / **0.638** | 0.546 / 0.877 / **0.673** | 0.568 / 0.832 / **0.675** | 0.546 / 0.880 / **0.674** | 0.519 / 0.821 / **0.636** |
| 0.5 | 0.554 / 0.837 / **0.667** | 0.598 / 0.840 / **0.699** | 0.603 / 0.779 / **0.680** | 0.598 / 0.842 / **0.700** | 0.569 / 0.771 / **0.655** |
| 0.6 | 0.591 / 0.787 / **0.675** | 0.652 / 0.799 / **0.718** | 0.627 / 0.719 / **0.670** | 0.651 / 0.802 / **0.719** | 0.614 / 0.721 / **0.663** |
| 0.7 | 0.637 / 0.724 / **0.678** | 0.698 / 0.759 / **0.727** | 0.653 / 0.654 / **0.654** | 0.699 / 0.769 / **0.732** | 0.633 / 0.644 / **0.639** |
| 0.8 | 0.696 / 0.629 / **0.661** | 0.741 / 0.681 / **0.710** | 0.685 / 0.549 / **0.610** | 0.730 / 0.694 / **0.711** | 0.670 / 0.546 / **0.602** |
| 0.9 | 0.760 / 0.405 / **0.528** | 0.802 / 0.523 / **0.633** | 0.747 / 0.344 / **0.471** | 0.778 / 0.565 / **0.655** | 0.703 / 0.374 / **0.488** |
| 0.95 | 0.776 / 0.187 / **0.302** | 0.866 / 0.333 / **0.481** | 0.809 / 0.144 / **0.245** | 0.826 / 0.351 / **0.492** | 0.745 / 0.209 / **0.326** |

<details><summary>Macro P / R / F1</summary>

| 門檻 | `jev-a` macro P / R / F1 | `jev-b` macro P / R / F1 | `clef-a` macro P / R / F1 | `clef-b` macro P / R / F1 | `clef-flash-a` macro P / R / F1 |
|---:|---|---|---|---|---|
| 0.1 | 0.293 / 0.984 / **0.433** | 0.338 / 0.972 / **0.484** | 0.330 / 0.977 / **0.481** | 0.320 / 0.986 / **0.460** | 0.324 / 0.969 / **0.461** |
| 0.2 | 0.391 / 0.956 / **0.537** | 0.427 / 0.944 / **0.572** | 0.500 / 0.933 / **0.633** | 0.443 / 0.959 / **0.586** | 0.432 / 0.914 / **0.560** |
| 0.3 | 0.466 / 0.930 / **0.602** | 0.488 / 0.923 / **0.623** | 0.582 / 0.871 / **0.679** | 0.525 / 0.920 / **0.649** | 0.521 / 0.864 / **0.619** |
| 0.4 | 0.526 / 0.893 / **0.638** | 0.555 / 0.888 / **0.668** | 0.658 / 0.824 / **0.707** | 0.576 / 0.881 / **0.680** | 0.590 / 0.808 / **0.641** |
| 0.5 | 0.598 / 0.845 / **0.677** | 0.606 / 0.850 / **0.692** | 0.713 / 0.767 / **0.707** | 0.625 / 0.840 / **0.697** | 0.654 / 0.756 / **0.659** |
| 0.6 | 0.632 / 0.795 / **0.680** | 0.654 / 0.808 / **0.706** | 0.750 / 0.699 / **0.681** | 0.671 / 0.800 / **0.709** | 0.718 / 0.704 / **0.662** |
| 0.7 | 0.685 / 0.728 / **0.677** | 0.703 / 0.767 / **0.713** | 0.797 / 0.621 / **0.638** | 0.724 / 0.762 / **0.718** | 0.759 / 0.629 / **0.624** |
| 0.8 | 0.766 / 0.635 / **0.658** | 0.746 / 0.689 / **0.690** | 0.833 / 0.516 / **0.557** | 0.762 / 0.678 / **0.681** | 0.808 / 0.538 / **0.573** |
| 0.9 | 0.854 / 0.415 / **0.485** | 0.817 / 0.526 / **0.592** | 0.805 / 0.277 / **0.347** | 0.842 / 0.569 / **0.619** | 0.789 / 0.348 / **0.419** |
| 0.95 | 0.721 / 0.177 / **0.248** | 0.912 / 0.344 / **0.437** | 0.585 / 0.117 / **0.161** | 0.876 / 0.352 / **0.436** | 0.710 / 0.179 / **0.240** |

</details>

觀察：

- **題目 A 下，各模型的分數尺度不同**：Jev 的最佳單一門檻在 0.6~0.7，Clef 在 0.4~0.5，不能共用門檻。
- **題目 B 下，Jev 與 Clef 的分數尺度變得接近**，同一個門檻（例如 0.7）對兩者都接近最佳。
- **題目 B 讓模型更果斷**：分數集中在兩端，所以在 0.7~0.9 這段，precision 與 recall 同時比題目 A 高
  （例如 Clef 在 0.8 時，題目 A 為 P 0.685 / R 0.549，題目 B 為 P 0.730 / R 0.694）。

### 7.4 排序品質與校準

| 方案 | Top-1 命中率 | Top-3 至少命中 1 個 | 逐類 ROC-AUC 平均 | 分數 > 0.5 的類別數（每篇） |
|---|---:|---:|---:|---:|
| `jev-a` | 0.743 | 0.962 | 0.969 | 1.89 |
| `jev-b` | 0.790 | 0.966 | 0.973 | 1.75 |
| `clef-a` | 0.723 | 0.971 | 0.967 | 1.63 |
| `clef-b` | 0.784 | 0.968 | 0.974 | 1.77 |
| `clef-flash-a` | 0.730 | 0.957 | 0.959 | 1.71 |

（ground truth 平均每篇 1.26 個標籤）

| 分數區間 | `jev-a` 筆數 / 平均分數 / 實際正例率 | `jev-b` 筆數 / 平均分數 / 實際正例率 | `clef-a` 筆數 / 平均分數 / 實際正例率 | `clef-b` 筆數 / 平均分數 / 實際正例率 | `clef-flash-a` 筆數 / 平均分數 / 實際正例率 |
|---|---|---|---|---|---|
| [0, 0.1) | 11587 / 0.03 / 0.00 | 12321 / 0.03 / 0.00 | 12291 / 0.03 / 0.00 | 11332 / 0.05 / 0.00 | 11654 / 0.02 / 0.00 |
| [0.1, 0.3) | 1817 / 0.17 / 0.04 | 1341 / 0.17 / 0.06 | 1581 / 0.17 / 0.08 | 2264 / 0.17 / 0.03 | 1966 / 0.18 / 0.06 |
| [0.3, 0.5) | 694 / 0.39 / 0.16 | 569 / 0.39 / 0.16 | 499 / 0.39 / 0.25 | 631 / 0.39 / 0.15 | 674 / 0.39 / 0.19 |
| [0.5, 0.7) | 470 / 0.60 / 0.30 | 400 / 0.59 / 0.26 | 368 / 0.60 / 0.43 | 386 / 0.59 / 0.24 | 423 / 0.60 / 0.38 |
| [0.7, 0.9) | 761 / 0.81 / 0.53 | 547 / 0.81 / 0.54 | 681 / 0.82 / 0.57 | 472 / 0.81 / 0.54 | 613 / 0.81 / 0.56 |
| [0.9, 1.0) | 671 / 0.94 / 0.76 | 822 / 0.95 / 0.80 | 580 / 0.94 / 0.75 | 915 / 0.95 / 0.78 | 670 / 0.95 / 0.70 |

- Top-3 至少命中一個正確分類的比率都在 96~97%，排序能力很好；題目 B 主要提升 Top-1。
- **以 ground truth 衡量，所有決策模型都「過度自信」**：分數 0.6 的配對實際只有 24~43% 是正例。
- 但校準表同樣受 ground truth 漏標影響（§7.7）。若高分誤判中約 3/4 其實正確，[0.9, 1.0) 區間的真實正例率可能達 0.9 以上。
  **「calibrated」的宣稱在 Cofacts 資料上無法直接驗證，需先補齊多標籤的 ground truth**；
  實務上不要把 `noul` 直接當機率解讀，門檻一律逐類從資料校準（§5）。

### 7.5 最終結果選擇策略

決策模型可以用不同策略把 16 個機率轉成最終標籤；LLM 清單只有一種結果，列在每張表的最後當作參照。
逐類門檻以 **5-fold cross validation** 計算。括號內為平均每篇輸出的標籤數（ground truth 為 1.26）。

**全部樣本**（括號內為平均每篇標籤數）

| 策略 | `jev-a` P / R / F1 | `jev-b` P / R / F1 | `clef-a` P / R / F1 | `clef-b` P / R / F1 | `clef-flash-a` P / R / F1 |
|---|---|---|---|---|---|
| 分數 ≥ 0.5 | 0.554 / 0.837 / **0.667** (1.90) | 0.598 / 0.840 / **0.699** (1.77) | 0.603 / 0.779 / **0.680** (1.63) | 0.598 / 0.842 / **0.700** (1.77) | 0.569 / 0.771 / **0.655** (1.71) |
| 分數 ≥ 0.7 | 0.637 / 0.724 / **0.678** (1.43) | 0.698 / 0.759 / **0.727** (1.37) | 0.653 / 0.654 / **0.654** (1.26) | 0.699 / 0.769 / **0.732** (1.39) | 0.633 / 0.644 / **0.639** (1.28) |
| 分數 ≥ 0.8 | 0.696 / 0.629 / **0.661** (1.14) | 0.741 / 0.681 / **0.710** (1.16) | 0.685 / 0.549 / **0.610** (1.01) | 0.730 / 0.694 / **0.711** (1.20) | 0.670 / 0.546 / **0.602** (1.03) |
| 分數 ≥ 0.9 | 0.760 / 0.405 / **0.528** (0.67) | 0.802 / 0.523 / **0.633** (0.82) | 0.747 / 0.344 / **0.471** (0.58) | 0.778 / 0.565 / **0.655** (0.92) | 0.703 / 0.374 / **0.488** (0.67) |
| 分數 ≥ 0.5，最多取前 2 | 0.613 / 0.783 / **0.688** (1.61) | 0.672 / 0.798 / **0.730** (1.50) | 0.619 / 0.751 / **0.679** (1.53) | 0.664 / 0.808 / **0.729** (1.53) | 0.614 / 0.740 / **0.671** (1.52) |
| 分數 ≥ 0.5，最多取前 3 | 0.567 / 0.825 / **0.672** (1.83) | 0.617 / 0.831 / **0.708** (1.70) | 0.604 / 0.774 / **0.678** (1.61) | 0.609 / 0.834 / **0.704** (1.73) | 0.576 / 0.767 / **0.658** (1.68) |
| 分數 ≥ 0.7，最多取前 2 | 0.659 / 0.699 / **0.679** (1.34) | 0.734 / 0.733 / **0.734** (1.26) | 0.660 / 0.647 / **0.653** (1.24) | 0.732 / 0.749 / **0.741** (1.29) | 0.653 / 0.639 / **0.646** (1.23) |
| 分數 ≥ 0.7，最多取前 3 | 0.641 / 0.721 / **0.679** (1.42) | 0.704 / 0.755 / **0.728** (1.35) | 0.654 / 0.653 / **0.653** (1.26) | 0.704 / 0.763 / **0.732** (1.37) | 0.634 / 0.644 / **0.639** (1.28) |
| **分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個** | 0.651 / 0.752 / **0.698** (1.46) | 0.716 / 0.783 / **0.748** (1.38) | 0.649 / 0.715 / **0.680** (1.39) | 0.717 / 0.787 / **0.750** (1.38) | 0.639 / 0.707 / **0.671** (1.40) |
| 只取最高分 1 個 | 0.743 / 0.590 / **0.658** (1.00) | 0.791 / 0.628 / **0.700** (1.00) | 0.723 / 0.574 / **0.640** (1.00) | 0.784 / 0.622 / **0.694** (1.00) | 0.730 / 0.579 / **0.646** (1.00) |
| **逐類門檻（max F1, CV）** | 0.668 / 0.783 / **0.721** (1.48) | 0.693 / 0.793 / **0.739** (1.44) | 0.637 / 0.783 / **0.702** (1.55) | 0.717 / 0.787 / **0.750** (1.38) | 0.624 / 0.758 / **0.684** (1.53) |
| **逐類門檻（precision ≥ 0.9, CV）** | 0.879 / 0.421 / **0.569** (0.60) | 0.873 / 0.415 / **0.563** (0.60) | 0.886 / 0.458 / **0.604** (0.65) | 0.883 / 0.408 / **0.558** (0.58) | 0.877 / 0.429 / **0.576** (0.62) |
| *`haiku-low` 輸出的清單（固定，不分策略）* | 0.639 / 0.834 / **0.724** (1.64) |  |  |  |  |
| *`haiku-medium` 輸出的清單（固定，不分策略）* | 0.673 / 0.825 / **0.742** (1.54) |  |  |  |  |

**隨機抽樣子集**（括號內為平均每篇標籤數）

| 策略 | `jev-a` P / R / F1 | `jev-b` P / R / F1 | `clef-a` P / R / F1 | `clef-b` P / R / F1 | `clef-flash-a` P / R / F1 |
|---|---|---|---|---|---|
| 分數 ≥ 0.5 | 0.530 / 0.856 / **0.655** (1.65) | 0.622 / 0.837 / **0.714** (1.37) | 0.560 / 0.868 / **0.681** (1.58) | 0.661 / 0.900 / **0.762** (1.39) | 0.518 / 0.881 / **0.653** (1.73) |
| 分數 ≥ 0.7 | 0.617 / 0.768 / **0.684** (1.27) | 0.769 / 0.774 / **0.772** (1.03) | 0.609 / 0.799 / **0.691** (1.34) | 0.802 / 0.837 / **0.819** (1.06) | 0.558 / 0.781 / **0.651** (1.42) |
| 分數 ≥ 0.8 | 0.660 / 0.693 / **0.676** (1.07) | 0.814 / 0.712 / **0.759** (0.89) | 0.630 / 0.693 / **0.660** (1.12) | 0.859 / 0.799 / **0.828** (0.95) | 0.590 / 0.690 / **0.636** (1.19) |
| 分數 ≥ 0.9 | 0.734 / 0.476 / **0.578** (0.66) | 0.894 / 0.608 / **0.724** (0.69) | 0.741 / 0.511 / **0.605** (0.70) | 0.913 / 0.627 / **0.743** (0.70) | 0.625 / 0.517 / **0.566** (0.84) |
| 分數 ≥ 0.5，最多取前 2 | 0.558 / 0.843 / **0.672** (1.54) | 0.665 / 0.828 / **0.737** (1.27) | 0.578 / 0.868 / **0.694** (1.53) | 0.692 / 0.887 / **0.777** (1.31) | 0.576 / 0.865 / **0.692** (1.53) |
| 分數 ≥ 0.5，最多取前 3 | 0.535 / 0.856 / **0.659** (1.63) | 0.631 / 0.837 / **0.720** (1.35) | 0.561 / 0.868 / **0.681** (1.58) | 0.664 / 0.900 / **0.764** (1.38) | 0.526 / 0.881 / **0.659** (1.71) |
| 分數 ≥ 0.7，最多取前 2 | 0.621 / 0.765 / **0.685** (1.26) | 0.771 / 0.771 / **0.771** (1.02) | 0.613 / 0.799 / **0.694** (1.33) | 0.809 / 0.837 / **0.823** (1.05) | 0.591 / 0.771 / **0.669** (1.33) |
| 分數 ≥ 0.7，最多取前 3 | 0.619 / 0.768 / **0.685** (1.27) | 0.769 / 0.774 / **0.772** (1.03) | 0.609 / 0.799 / **0.691** (1.34) | 0.802 / 0.837 / **0.819** (1.06) | 0.560 / 0.781 / **0.652** (1.42) |
| **分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個** | 0.617 / 0.828 / **0.707** (1.37) | 0.750 / 0.846 / **0.795** (1.15) | 0.603 / 0.843 / **0.703** (1.42) | 0.790 / 0.875 / **0.830** (1.13) | 0.603 / 0.862 / **0.710** (1.46) |
| 只取最高分 1 個 | 0.725 / 0.712 / **0.718** (1.00) | 0.834 / 0.818 / **0.826** (1.00) | 0.712 / 0.699 / **0.706** (1.00) | 0.866 / 0.850 / **0.858** (1.00) | 0.751 / 0.737 / **0.744** (1.00) |
| **逐類門檻（max F1, CV）** | 0.773 / 0.853 / **0.811** (1.12) | 0.808 / 0.856 / **0.831** (1.08) | 0.605 / 0.875 / **0.715** (1.47) | 0.821 / 0.865 / **0.843** (1.07) | 0.594 / 0.859 / **0.703** (1.47) |
| **逐類門檻（precision ≥ 0.9, CV）** | 0.967 / 0.649 / **0.777** (0.68) | 0.976 / 0.630 / **0.766** (0.66) | 0.960 / 0.683 / **0.799** (0.73) | 0.953 / 0.633 / **0.761** (0.68) | 0.942 / 0.658 / **0.775** (0.71) |
| *`haiku-low` 輸出的清單（固定，不分策略）* | 0.659 / 0.884 / **0.755** (1.37) |  |  |  |  |
| *`haiku-medium` 輸出的清單（固定，不分策略）* | 0.716 / 0.900 / **0.797** (1.28) |  |  |  |  |

**在相同 recall 下比較 precision**（決策模型掃描單一門檻，取 recall 最接近 Haiku 清單的點）：

| LLM 清單 | P / R | `jev-a` 同 recall 的 P（門檻） | `jev-b` 同 recall 的 P（門檻） | `clef-a` 同 recall 的 P（門檻） | `clef-b` 同 recall 的 P（門檻） | `clef-flash-a` 同 recall 的 P（門檻） |
|---|---|---|---|---|---|---|
| `haiku-low` | 0.639 / 0.834 | 0.557（0.51） | 0.611（0.52） | 0.568（0.40） | 0.621（0.54） | 0.499（0.37） |
| `haiku-medium` | 0.673 / 0.825 | 0.566（0.53） | 0.619（0.54） | 0.572（0.41） | 0.626（0.55） | 0.513（0.39） |

Haiku 的清單在同樣 recall 下，precision 比題目 B 的決策模型高約 0.03~0.05，比題目 A 高約 0.08~0.1；
但決策模型可以沿著曲線移動到任何想要的 precision / recall，清單則只能改 prompt 重跑。

**建議策略：**

1. **上線預設：逐類門檻，以 precision ≥ 0.9 為約束**，取該約束下 recall 最大的門檻（§5）。
   - 隨機子集上：`jev-b` P 0.976 / R 0.630、`jev-a` P 0.967 / R 0.649，平均每篇約 0.6 個標籤。
   - 達不到 precision 0.9 的類別（§7.6 表格中的「—」）**先不自動標記**，留給人工。
   - 因為 ground truth 漏標，實際 precision 應高於表上數字。
2. **每篇至少要一個標籤時**（例如供編輯篩選、之後會人工確認）：
   **「分數 ≥ 0.7、最多取前 2 個；都沒過門檻就取最高分 1 個」**，不需逐類調參。
   題目 B 下 Jev、Clef 都約 0.75；題目 A 下 Clef 的門檻要降到 0.5~0.6 才接近最佳。
3. **「最多取前 3 個」的上限幾乎沒有作用**：分數 ≥ 0.7 的類別本來就很少超過 3 個；改成「最多 2 個」才有實質影響。
4. 逐類門檻在隨機子集上的 F1 可達 0.83~0.84，但 313 篇裡稀有類別的正例只有個位數，**變異很大，不宜當作預期值**。

### 7.6 逐類表現

各類 F1：決策模型取該類 max-F1 門檻（在整個樣本上找，樂觀估計）；LLM 為清單的固定結果。

| 類別 | 正例 | `jev-a` | `jev-b` | `clef-a` | `clef-b` | `clef-flash-a` | `haiku-low` | `haiku-medium` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 中國政治宣傳 | 68 | 0.654 | 0.679 | 0.658 | 0.667 | 0.581 | 0.606 | 0.642 |
| 詐騙 | 60 | 0.642 | 0.731 | 0.657 | 0.772 | 0.559 | 0.675 | 0.703 |
| 台灣政治、政黨 | 182 | 0.796 | 0.809 | 0.786 | 0.800 | 0.773 | 0.780 | 0.784 |
| COVID-19 疫情 | 61 | 0.725 | 0.720 | 0.771 | 0.730 | 0.726 | 0.707 | 0.725 |
| 疾病、醫藥 | 60 | 0.516 | 0.615 | 0.299 | 0.662 | 0.325 | 0.453 | 0.475 |
| 跨國互動 | 60 | 0.673 | 0.715 | 0.672 | 0.648 | 0.658 | 0.652 | 0.672 |
| 愛滋病 | 6 | 1.000 | 0.923 | 1.000 | 1.000 | 1.000 | 0.800 | 0.750 |
| 性別議題 | 60 | 0.937 | 0.935 | 0.937 | 0.929 | 0.944 | 0.908 | 0.913 |
| 保健秘訣、食品安全 | 257 | 0.864 | 0.854 | 0.888 | 0.884 | 0.886 | 0.860 | 0.883 |
| 農林漁牧政策 | 60 | 0.780 | 0.768 | 0.790 | 0.768 | 0.738 | 0.694 | 0.750 |
| 電力、能源 | 60 | 0.847 | 0.860 | 0.818 | 0.816 | 0.792 | 0.810 | 0.810 |
| 環保、生態 | 60 | 0.682 | 0.730 | 0.752 | 0.767 | 0.748 | 0.744 | 0.750 |
| 優惠措施、新法規、政策宣導 | 84 | 0.530 | 0.540 | 0.571 | 0.576 | 0.534 | 0.600 | 0.589 |
| 科技、資安、隱私 | 60 | 0.705 | 0.762 | 0.792 | 0.774 | 0.781 | 0.700 | 0.750 |
| 商業廣告 | 62 | 0.654 | 0.667 | 0.672 | 0.681 | 0.604 | 0.671 | 0.667 |
| 連署、集氣、協尋、捐贈 | 60 | 0.848 | 0.835 | 0.859 | 0.803 | 0.835 | 0.705 | 0.697 |

各類別大致分成三群，決策模型的各方案都一致（Haiku 在連署集氣、農林漁牧較弱）：

| 表現 | 類別 | 說明 |
|---|---|---|
| **好**（F1 約 0.8 以上） | 性別議題、保健秘訣、電力能源、連署集氣、愛滋病（僅 6 例） | 主題詞彙明確 |
| **中**（F1 約 0.6~0.8） | 台灣政治、農林漁牧、科技資安、環保生態、COVID-19、跨國互動、中國政治宣傳、商業廣告、詐騙 | 與鄰近類別邊界模糊（§7.7） |
| **差**（F1 約 0.3~0.6） | 疾病醫藥、優惠措施／新法規／政策宣導 | 前者是定義與 ground truth 不一致，後者是範圍太廣 |

題目 A 與 B 的差異集中在預期的類別：

- **疾病、醫藥**：Clef 0.299 → 0.662、Jev 0.516 → 0.615（題目 B 加了「偏方、養生屬於保健」的排除條件）。
  Haiku 即使拿到同樣的條件，F1 也只有 0.45~0.48，說明這一類的主要瓶頸在 ground truth（見 §7.7）。
- **詐騙**：+0.09~0.12（題目 B 列出具體手法）。
- **科技資安**（Jev +0.06）、**環保生態**（Jev +0.05）也有進步。
- 少數類別在題目 B 略降，例如 Clef 的連署集氣（−0.06）。題目 B 的連署條件列了「投票、轉發幫忙」，可能把一般「請轉發」的訊息也算進來，下一輪可收窄。

<details><summary><code>jev-a</code> 逐類 P / R / F1</summary>

| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |
|---|---:|---:|---|---|---|
| 中國政治宣傳 | 68 | 0.962 | 0.653 / 0.471 / 0.547 | 0.35 → 0.571 / 0.765 / 0.654 | 0.87 → 0.118 |
| 詐騙 | 60 | 0.967 | 0.454 / 0.900 / 0.603 | 0.60 → 0.515 / 0.850 / 0.642 | — |
| 台灣政治、政黨 | 182 | 0.966 | 0.665 / 0.929 / 0.775 | 0.68 → 0.727 / 0.879 / 0.796 | 0.93 → 0.412 |
| COVID-19 疫情 | 61 | 0.982 | 0.569 / 0.951 / 0.712 | 0.58 → 0.586 / 0.951 / 0.725 | — |
| 疾病、醫藥 | 60 | 0.925 | 0.178 / 0.967 / 0.301 | 0.96 → 0.485 / 0.550 / 0.516 | — |
| 跨國互動 | 60 | 0.969 | 0.397 / 0.900 / 0.551 | 0.77 → 0.740 / 0.617 / 0.673 | — |
| 愛滋病 | 6 | 1.000 | 0.600 / 1.000 / 0.750 | 0.88 → 1.000 / 1.000 / 1.000 | 0.88 → 1.000 |
| 性別議題 | 60 | 0.991 | 0.808 / 0.983 / 0.887 | 0.69 → 0.894 / 0.983 / 0.937 | 0.86 → 0.950 |
| 保健秘訣、食品安全 | 257 | 0.973 | 0.881 / 0.833 / 0.856 | 0.47 → 0.876 / 0.852 / 0.864 | 0.66 → 0.778 |
| 農林漁牧政策 | 60 | 0.987 | 0.780 / 0.767 / 0.773 | 0.51 → 0.793 / 0.767 / 0.780 | 0.74 → 0.517 |
| 電力、能源 | 60 | 0.993 | 0.779 / 0.883 / 0.828 | 0.61 → 0.862 / 0.833 / 0.847 | 0.72 → 0.767 |
| 環保、生態 | 60 | 0.966 | 0.536 / 0.867 / 0.662 | 0.69 → 0.625 / 0.750 / 0.682 | — |
| 優惠措施、新法規、政策宣導 | 84 | 0.909 | 0.495 / 0.536 / 0.514 | 0.41 → 0.435 / 0.679 / 0.530 | 0.85 → 0.310 |
| 科技、資安、隱私 | 60 | 0.966 | 0.485 / 0.817 / 0.609 | 0.77 → 0.822 / 0.617 / 0.705 | 0.85 → 0.517 |
| 商業廣告 | 62 | 0.960 | 0.477 / 0.839 / 0.608 | 0.56 → 0.549 / 0.806 / 0.654 | 0.89 → 0.145 |
| 連署、集氣、協尋、捐贈 | 60 | 0.992 | 0.815 / 0.883 / 0.848 | 0.49 → 0.815 / 0.883 / 0.848 | 0.70 → 0.750 |

</details>

<details><summary><code>jev-b</code> 逐類 P / R / F1</summary>

| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |
|---|---:|---:|---|---|---|
| 中國政治宣傳 | 68 | 0.971 | 0.625 / 0.515 / 0.565 | 0.31 → 0.602 / 0.779 / 0.679 | 0.92 → 0.088 |
| 詐騙 | 60 | 0.978 | 0.534 / 0.917 / 0.675 | 0.71 → 0.662 / 0.817 / 0.731 | 0.95 → 0.150 |
| 台灣政治、政黨 | 182 | 0.968 | 0.680 / 0.923 / 0.783 | 0.70 → 0.738 / 0.896 / 0.809 | 0.96 → 0.412 |
| COVID-19 疫情 | 61 | 0.983 | 0.574 / 0.951 / 0.716 | 0.78 → 0.607 / 0.885 / 0.720 | — |
| 疾病、醫藥 | 60 | 0.955 | 0.257 / 0.917 / 0.401 | 0.93 → 0.571 / 0.667 / 0.615 | — |
| 跨國互動 | 60 | 0.969 | 0.477 / 0.867 / 0.615 | 0.71 → 0.698 / 0.733 / 0.715 | — |
| 愛滋病 | 6 | 1.000 | 0.600 / 1.000 / 0.750 | 0.91 → 0.857 / 1.000 / 0.923 | 0.94 → 0.833 |
| 性別議題 | 60 | 0.991 | 0.831 / 0.983 / 0.901 | 0.87 → 0.906 / 0.967 / 0.935 | 0.87 → 0.967 |
| 保健秘訣、食品安全 | 257 | 0.971 | 0.886 / 0.817 / 0.850 | 0.45 → 0.877 / 0.833 / 0.854 | 0.82 → 0.685 |
| 農林漁牧政策 | 60 | 0.986 | 0.635 / 0.783 / 0.701 | 0.66 → 0.827 / 0.717 / 0.768 | 0.83 → 0.483 |
| 電力、能源 | 60 | 0.995 | 0.815 / 0.883 / 0.848 | 0.57 → 0.852 / 0.867 / 0.860 | 0.70 → 0.783 |
| 環保、生態 | 60 | 0.963 | 0.593 / 0.850 / 0.699 | 0.63 → 0.649 / 0.833 / 0.730 | 0.95 → 0.150 |
| 優惠措施、新法規、政策宣導 | 84 | 0.916 | 0.466 / 0.643 / 0.540 | 0.50 → 0.466 / 0.643 / 0.540 | 0.92 → 0.250 |
| 科技、資安、隱私 | 60 | 0.974 | 0.697 / 0.767 / 0.730 | 0.66 → 0.889 / 0.667 / 0.762 | 0.73 → 0.633 |
| 商業廣告 | 62 | 0.962 | 0.481 / 0.839 / 0.612 | 0.70 → 0.605 / 0.742 / 0.667 | 0.95 → 0.161 |
| 連署、集氣、協尋、捐贈 | 60 | 0.989 | 0.538 / 0.950 / 0.687 | 0.88 → 0.873 / 0.800 / 0.835 | 0.92 → 0.650 |

</details>

<details><summary><code>clef-a</code> 逐類 P / R / F1</summary>

| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |
|---|---:|---:|---|---|---|
| 中國政治宣傳 | 68 | 0.963 | 0.660 / 0.485 / 0.559 | 0.35 → 0.615 / 0.706 / 0.658 | 0.88 → 0.088 |
| 詐騙 | 60 | 0.967 | 0.413 / 0.950 / 0.576 | 0.80 → 0.595 / 0.733 / 0.657 | — |
| 台灣政治、政黨 | 182 | 0.965 | 0.650 / 0.918 / 0.761 | 0.82 → 0.786 / 0.786 / 0.786 | 0.95 → 0.418 |
| COVID-19 疫情 | 61 | 0.985 | 0.574 / 0.951 / 0.716 | 0.91 → 0.684 / 0.885 / 0.771 | — |
| 疾病、醫藥 | 60 | 0.839 | 0.162 / 0.917 / 0.276 | 0.77 → 0.187 / 0.750 / 0.299 | — |
| 跨國互動 | 60 | 0.969 | 0.786 / 0.550 / 0.647 | 0.35 → 0.646 / 0.700 / 0.672 | 0.82 → 0.067 |
| 愛滋病 | 6 | 1.000 | 1.000 / 1.000 / 1.000 | 0.43 → 1.000 / 1.000 / 1.000 | 0.43 → 1.000 |
| 性別議題 | 60 | 0.988 | 0.892 / 0.967 / 0.928 | 0.39 → 0.894 / 0.983 / 0.937 | 0.65 → 0.950 |
| 保健秘訣、食品安全 | 257 | 0.980 | 0.885 / 0.872 / 0.878 | 0.32 → 0.851 / 0.930 / 0.888 | 0.59 → 0.844 |
| 農林漁牧政策 | 60 | 0.982 | 0.833 / 0.667 / 0.741 | 0.38 → 0.797 / 0.783 / 0.790 | 0.65 → 0.467 |
| 電力、能源 | 60 | 0.987 | 0.789 / 0.750 / 0.769 | 0.67 → 0.900 / 0.750 / 0.818 | 0.67 → 0.750 |
| 環保、生態 | 60 | 0.972 | 0.765 / 0.650 / 0.703 | 0.42 → 0.723 / 0.783 / 0.752 | 0.74 → 0.350 |
| 優惠措施、新法規、政策宣導 | 84 | 0.920 | 0.679 / 0.429 / 0.526 | 0.37 → 0.629 / 0.524 / 0.571 | 0.70 → 0.274 |
| 科技、資安、隱私 | 60 | 0.978 | 0.818 / 0.750 / 0.783 | 0.56 → 0.913 / 0.700 / 0.792 | 0.56 → 0.700 |
| 商業廣告 | 62 | 0.978 | 0.685 / 0.597 / 0.638 | 0.43 → 0.652 / 0.694 / 0.672 | 0.62 → 0.452 |
| 連署、集氣、協尋、捐贈 | 60 | 0.994 | 0.817 / 0.817 / 0.817 | 0.38 → 0.809 / 0.917 / 0.859 | 0.77 → 0.650 |

</details>

<details><summary><code>clef-b</code> 逐類 P / R / F1</summary>

| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |
|---|---:|---:|---|---|---|
| 中國政治宣傳 | 68 | 0.959 | 0.702 / 0.588 / 0.640 | 0.32 → 0.600 / 0.750 / 0.667 | — |
| 詐騙 | 60 | 0.983 | 0.496 / 0.967 / 0.655 | 0.92 → 0.815 / 0.733 / 0.772 | — |
| 台灣政治、政黨 | 182 | 0.965 | 0.592 / 0.951 / 0.730 | 0.94 → 0.821 / 0.780 / 0.800 | 0.98 → 0.264 |
| COVID-19 疫情 | 61 | 0.982 | 0.563 / 0.951 / 0.707 | 0.70 → 0.592 / 0.951 / 0.730 | — |
| 疾病、醫藥 | 60 | 0.956 | 0.258 / 0.917 / 0.403 | 0.93 → 0.603 / 0.733 / 0.662 | — |
| 跨國互動 | 60 | 0.967 | 0.577 / 0.683 / 0.626 | 0.45 → 0.561 / 0.767 / 0.648 | — |
| 愛滋病 | 6 | 1.000 | 0.667 / 1.000 / 0.800 | 0.84 → 1.000 / 1.000 / 1.000 | 0.84 → 1.000 |
| 性別議題 | 60 | 0.986 | 0.855 / 0.983 / 0.915 | 0.59 → 0.881 / 0.983 / 0.929 | 0.85 → 0.933 |
| 保健秘訣、食品安全 | 257 | 0.974 | 0.881 / 0.868 / 0.875 | 0.33 → 0.866 / 0.903 / 0.884 | 0.68 → 0.817 |
| 農林漁牧政策 | 60 | 0.978 | 0.712 / 0.783 / 0.746 | 0.69 → 0.827 / 0.717 / 0.768 | 0.89 → 0.383 |
| 電力、能源 | 60 | 0.992 | 0.708 / 0.850 / 0.773 | 0.56 → 0.785 / 0.850 / 0.816 | 0.87 → 0.667 |
| 環保、生態 | 60 | 0.973 | 0.676 / 0.833 / 0.746 | 0.67 → 0.767 / 0.767 / 0.767 | 0.84 → 0.533 |
| 優惠措施、新法規、政策宣導 | 84 | 0.929 | 0.495 / 0.619 / 0.550 | 0.57 → 0.570 / 0.583 / 0.576 | 0.87 → 0.333 |
| 科技、資安、隱私 | 60 | 0.979 | 0.826 / 0.633 / 0.717 | 0.38 → 0.750 / 0.800 / 0.774 | 0.63 → 0.567 |
| 商業廣告 | 62 | 0.975 | 0.531 / 0.823 / 0.646 | 0.59 → 0.630 / 0.742 / 0.681 | 0.90 → 0.323 |
| 連署、集氣、協尋、捐贈 | 60 | 0.991 | 0.454 / 0.983 / 0.621 | 0.81 → 0.736 / 0.883 / 0.803 | 0.97 → 0.583 |

</details>

<details><summary><code>clef-flash-a</code> 逐類 P / R / F1</summary>

| 類別 | 正例 | AUC | @0.5 P / R / F1 | max F1 門檻 → P / R / F1 | P≥0.9 門檻 → R |
|---|---:|---:|---|---|---|
| 中國政治宣傳 | 68 | 0.942 | 0.512 / 0.647 / 0.571 | 0.52 → 0.537 / 0.632 / 0.581 | — |
| 詐騙 | 60 | 0.935 | 0.276 / 0.900 / 0.422 | 0.90 → 0.569 / 0.550 / 0.559 | — |
| 台灣政治、政黨 | 182 | 0.959 | 0.709 / 0.830 / 0.765 | 0.53 → 0.728 / 0.824 / 0.773 | 0.86 → 0.335 |
| COVID-19 疫情 | 61 | 0.975 | 0.559 / 0.934 / 0.699 | 0.61 → 0.594 / 0.934 / 0.726 | — |
| 疾病、醫藥 | 60 | 0.862 | 0.186 / 0.867 / 0.306 | 0.81 → 0.209 / 0.733 / 0.325 | — |
| 跨國互動 | 60 | 0.966 | 0.867 / 0.217 / 0.347 | 0.17 → 0.558 / 0.800 / 0.658 | 0.51 → 0.217 |
| 愛滋病 | 6 | 1.000 | 0.857 / 1.000 / 0.923 | 0.56 → 1.000 / 1.000 / 1.000 | 0.56 → 1.000 |
| 性別議題 | 60 | 0.985 | 0.907 / 0.817 / 0.860 | 0.23 → 0.908 / 0.983 / 0.944 | 0.23 → 0.983 |
| 保健秘訣、食品安全 | 257 | 0.978 | 0.839 / 0.914 / 0.875 | 0.57 → 0.866 / 0.907 / 0.886 | 0.74 → 0.848 |
| 農林漁牧政策 | 60 | 0.970 | 0.760 / 0.633 / 0.691 | 0.36 → 0.686 / 0.800 / 0.738 | 0.72 → 0.400 |
| 電力、能源 | 60 | 0.978 | 0.759 / 0.733 / 0.746 | 0.71 → 0.913 / 0.700 / 0.792 | 0.71 → 0.700 |
| 環保、生態 | 60 | 0.955 | 0.613 / 0.817 / 0.700 | 0.56 → 0.690 / 0.817 / 0.748 | 0.93 → 0.183 |
| 優惠措施、新法規、政策宣導 | 84 | 0.918 | 0.632 / 0.429 / 0.511 | 0.40 → 0.558 / 0.512 / 0.534 | 0.80 → 0.226 |
| 科技、資安、隱私 | 60 | 0.978 | 0.824 / 0.700 / 0.757 | 0.58 → 0.911 / 0.683 / 0.781 | 0.58 → 0.683 |
| 商業廣告 | 62 | 0.956 | 0.460 / 0.742 / 0.568 | 0.53 → 0.517 / 0.726 / 0.604 | 0.83 → 0.210 |
| 連署、集氣、協尋、捐贈 | 60 | 0.994 | 0.714 / 0.917 / 0.803 | 0.71 → 0.791 / 0.883 / 0.835 | 0.89 → 0.683 |

</details>

<details><summary>Claude Haiku 5.5 逐類 P / R / F1</summary>

| 類別 | 正例 | `haiku-low` P / R / F1 | `haiku-medium` P / R / F1 |
|---|---:|---|---|
| 中國政治宣傳 | 68 | 0.540 / 0.691 / 0.606 | 0.638 / 0.647 / 0.642 |
| 詐騙 | 60 | 0.540 / 0.900 / 0.675 | 0.591 / 0.867 / 0.703 |
| 台灣政治、政黨 | 182 | 0.664 / 0.945 / 0.780 | 0.669 / 0.945 / 0.784 |
| COVID-19 疫情 | 61 | 0.563 / 0.951 / 0.707 | 0.586 / 0.951 / 0.725 |
| 疾病、醫藥 | 60 | 0.316 / 0.800 / 0.453 | 0.341 / 0.783 / 0.475 |
| 跨國互動 | 60 | 0.568 / 0.767 / 0.652 | 0.608 / 0.750 / 0.672 |
| 愛滋病 | 6 | 0.667 / 1.000 / 0.800 | 0.600 / 1.000 / 0.750 |
| 性別議題 | 60 | 0.843 / 0.983 / 0.908 | 0.866 / 0.967 / 0.913 |
| 保健秘訣、食品安全 | 257 | 0.857 / 0.864 / 0.860 | 0.883 / 0.883 / 0.883 |
| 農林漁牧政策 | 60 | 0.595 / 0.833 / 0.694 | 0.706 / 0.800 / 0.750 |
| 電力、能源 | 60 | 0.803 / 0.817 / 0.810 | 0.773 / 0.850 / 0.810 |
| 環保、生態 | 60 | 0.696 / 0.800 / 0.744 | 0.706 / 0.800 / 0.750 |
| 優惠措施、新法規、政策宣導 | 84 | 0.632 / 0.571 / 0.600 | 0.608 / 0.571 / 0.589 |
| 科技、資安、隱私 | 60 | 0.700 / 0.700 / 0.700 | 0.808 / 0.700 / 0.750 |
| 商業廣告 | 62 | 0.603 / 0.758 / 0.671 | 0.672 / 0.661 / 0.667 |
| 連署、集氣、協尋、捐贈 | 60 | 0.573 / 0.917 / 0.705 | 0.576 / 0.883 / 0.697 |

</details>

### 7.7 誤判分析：多數「FP」其實是 ground truth 漏標

Ground truth 有 92.5% 的文章只有一個標籤，但 Cofacts 的分類本來就是多標籤，因此「模型標了、ground truth 沒標」不一定是錯。
我們做了兩次抽查，由 Claude 依 `ListCategories` 定義逐則判斷「該標籤是否合理」（不是人工標記，僅能當作量級參考）：

| 抽查 | 母體 | 抽樣 | 判為合理 |
|---|---|---:|---:|
| ① | `jev-a` 分數 ≥ 0.8 的誤判（共 346 個） | 40 | **31（78%）** |
| ② | `jev-a` 分數 < 0.9、但 `jev-b` 分數 ≥ 0.9 的誤判（共 62 個） | 30 | **28（93%）** |

**抽查 ①**：合理的例子如

- 新冠疫苗陰謀論（ground truth：COVID-19）被標「疾病、醫藥」——`covid19` 的 description 本身就寫「「疾病、醫藥」下的子分類之一」；
- 中美貿易戰、華為晶片（ground truth：中國政治宣傳）被標「跨國互動」；
- 打字賺錢、繳押金的工作（ground truth：商業廣告）被標「詐騙」。

不合理的 9 則全部是「疾病、醫藥」標在一般保健文章上（如「芒果葉治糖尿病」、「夜尿與心梗」），
也就是兩個分類的定義重疊：「保健秘訣」寫「治慢性病等的偏方秘笈」、「疾病、醫藥」寫「癌症，以及各種藥物的相關傳言」。
題目 B 就是針對這點加了排除條件。

**抽查 ②** 解釋了為什麼題目 B 在「precision ≥ 0.9」設定下反而略差：
題目 B 讓模型更果斷，分數 ≥ 0.9 的 (文章, 類別) 配對從約 600 筆增加到 800~900 筆，高分區擠進更多 ground truth 沒標的文章。
抽查這些「題目 B 才給到 0.9 以上」的誤判，30 則中 28 則合理（例如 ECFA 新聞標成台灣政治、PFAS 標成環保、萊克多巴胺標成保健食安，
ground truth 都只標了另一類）。以不完整的 ground truth 衡量時，模型越敢標，precision ≥ 0.9 這條線就越難達到；
**這個數字的差距主要是量測偏差，不代表題目 B 實際上比較不準**。

> [!NOTE]
> 兩次抽查都指出：**§7.2~§7.6 的 precision 都是保守估計**。
> 若要正式訂門檻，ground truth 應先補成多標籤（至少把「子分類 ⇒ 母分類」補齊，例如 `covid19`、`aids` ⇒ `medical`）。

逐類的後續改善方向：

- **疾病、醫藥**：`covid19` / `aids` 是它的子分類，模型照定義會一起標。要嘛 ground truth 補上母分類，要嘛上線時「已標子分類就不再標母分類」。
- **詐騙 vs 商業廣告**：ground truth 中兩類同時出現 264 次，是最大的共現組合；在 ground truth 補齊前，不建議在題目裡強迫二選一。
- **中國政治宣傳**：高分區混入大量「台灣政治」與「跨國互動」文章，各方案不是只能在 recall ≈ 0.1 時達到 precision 0.9，就是完全達不到；上線初期建議不自動標。
- **優惠措施、新法規、政策宣導**：所有方案的 F1 都只有 0.53~0.60，AUC 也最低，範圍太廣，可考慮拆分或縮小定義。

### 7.8 成本

| 方案 | 單價 input / output（USD / M） | 每篇 input tokens 平均 / p95 | 每篇 output tokens | 每篇成本 | 每 1 萬篇 | 重跑 17K | 回填 28 萬篇 |
|---|---|---:|---:|---:|---:|---:|---:|
| `jev-a` | $0.042 / 免費 | 4,049 / 5,033 | 416 | $0.000170 | $1.70 | $2.89 | $47.5 |
| `jev-b` | $0.042 / 免費 | 4,190 / 5,174 | 416 | $0.000176 | $1.76 | $2.99 | $49.1 |
| `clef-a` | $0.24 / 免費 | 3,421 / 4,080 | 0 | $0.000821 | $8.21 | $13.96 | $229.3 |
| `clef-b` | $0.24 / 免費 | 3,536 / 4,195 | 0 | $0.000849 | $8.49 | $14.43 | $237.0 |
| `clef-flash-a` | $0.038 / 免費 | 3,421 / 4,080 | 0 | $0.000130 | $1.30 | $2.21 | $36.3 |
| `haiku-low` | $0.1 / $0.50 | 4,416 / 5,574 | 175 | $0.000529 | $5.29 | $9.00 | $147.8 |
| `haiku-medium` | $0.1 / $0.50 | 4,416 / 5,574 | 298 | $0.000591 | $5.91 | $10.04 | $164.9 |

- 決策模型只收 input token；Haiku 另收 output token（主要是 adaptive thinking），effort medium 的 output 約為 low 的 1.7 倍。
- 本次實驗（所有方案、含延遲量測與試跑）實際花費合計約 **$3.7**。
- **Token 數與 §3.2 / §4.2 的估算吻合**：16 類的題目區約 3,700 tokens（Jev 計）。同一段文字 Jev 計出的 token 比 Clef 多約 18%（tokenizer 不同）。
- Jev 的 output tokens 固定為 416（16 題 × 26），和題目、文章長度無關。
- 以原價計，未計 prompt caching：Haiku 的 system prompt（約 4,200 tokens）每篇相同、理論上適合 cache，
  但即時分類的訊息零星抵達，多數呼叫會落在 cache 的存活時間之外（§4.5）。
- **計費管道不同**（本次實測所見）：
  - Clef 系列是 Cloudflare 自家模型，走 Workers AI 的 neurons 計費（$0.24/M ≈ 21,818 neurons/M，每篇約 75 neurons）。
    若每日 10,000 neurons 免費額度適用，**每天約 134 篇以內免費**。
  - **Jev 與 Haiku 走 AI Gateway 的 unified billing，要先在 AI Gateway 儲值（credits）**；未儲值時 Jev 回傳
    `Insufficient balance; add money to your gateway or use BYOK`，而同一時間同一帳號的 Clef 呼叫正常。
    換言之，**Jev 不吃 Workers AI 的免費 neurons 額度**，§4.1.1「邊際成本可能是 $0」的推論不成立，但金額仍極小（每月 1 萬篇約 $1.8）。
  - unified billing 有共用的 rate limit：Jev 在 8 併發（約 21 req/s）時有約 3% 的請求遇到
    `429 Unified billing rate limit exceeded for this gateway`，同時跑 Haiku 時更頻繁，重試即成功。
    正式上線的即時流量遠低於此，但**補跑 script（§6.5）需要限速**。

### 7.9 單篇延遲

從開發機（經 proxy）呼叫 Cloudflare REST API 的完整來回時間，含網路延遲。
「序列」為 1 併發、隨機子集 200 篇（最接近單篇即時分類的情境，只量了題目 A 與 Haiku low）；「8 併發」為主實驗 1,000 篇。

| 方案 | 情境 | n | 平均 | p50 | p90 | p95 | p99 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `jev-a` | 序列（1 併發） | 200 | 0.30s | 0.28s | 0.35s | 0.46s | 0.72s | 1.02s |
| `jev-a` | 8 併發 | 1,000 | 0.31s | 0.28s | 0.37s | 0.55s | 0.74s | 1.39s |
| `jev-b` | 8 併發 | 1,000 | 0.30s | 0.27s | 0.36s | 0.49s | 0.91s | 1.04s |
| `clef-a` | 序列（1 併發） | 200 | 0.49s | 0.46s | 0.64s | 0.72s | 0.90s | 1.20s |
| `clef-a` | 8 併發 | 1,000 | 0.51s | 0.47s | 0.68s | 0.78s | 1.06s | 1.42s |
| `clef-b` | 8 併發 | 1,000 | 0.49s | 0.46s | 0.64s | 0.69s | 1.00s | 1.37s |
| `clef-flash-a` | 序列（1 併發） | 200 | 0.79s | 0.76s | 0.88s | 0.96s | 1.02s | 1.39s |
| `clef-flash-a` | 8 併發 | 1,000 | 0.83s | 0.78s | 0.92s | 1.02s | 1.50s | 3.33s |
| `haiku-low` | 序列（1 併發） | 200 | 2.07s | 1.87s | 3.23s | 3.76s | 4.65s | 5.88s |
| `haiku-low` | 8 併發 | 1,000 | 2.04s | 1.87s | 3.31s | 3.81s | 4.75s | 7.88s |
| `haiku-medium` | 8 併發 | 1,000 | 2.73s | 2.55s | 3.92s | 4.58s | 5.89s | 8.65s |

| 區間（序列） | `jev-a` | `clef-a` | `clef-flash-a` | `haiku-low` |
|---|---:|---:|---:|---:|
| 0–0.25s | 4% | 0% | 0% | 0% |
| 0.25–0.5s | 92% | 66% | 0% | 0% |
| 0.5–0.75s | 4% | 30% | 45% | 0% |
| 0.75–1s | 0% | 3% | 54% | 6% |
| 1–1.5s | 0% | 1% | 2% | 33% |
| 1.5–2s | 0% | 0% | 0% | 16% |
| 2–3s | 0% | 0% | 0% | 30% |
| 3–5s | 0% | 0% | 0% | 15% |
| ≥ 5s | 0% | 0% | 0% | 1% |

- 決策模型都在 1.5 秒內完成；Haiku 的延遲長尾到 5~8 秒，且與 output（thinking）長度高度相關（相關係數 0.86）。
- 對「射後不理」的掛載方式（§6）而言，五者的延遲都不是問題；但若要同步回應（例如在 LINE bot 對話中即時顯示分類），Jev 明顯較適合。
- 8 併發時延遲幾乎不變，代表這個量級下沒有排隊。
- clef-flash 雖然是較小的模型，實測卻比 Clef 慢，原因不明（可能是部署的硬體或排程不同）。

### 7.10 選型與建議

| 面向 | `jev-b` | `clef-b` | `haiku-medium` |
|---|---|---|---|
| 準確率（規則 F1） | 0.748 | 0.750 | 0.742（固定清單） |
| 可調門檻／逐類門檻 | ✓ | ✓ | ✗ |
| 每 1 萬篇成本 | **$1.76** | $8.49 | $5.91 |
| 延遲 p50 | **0.27s** | 0.46s | 2.55s |
| Context window | 32k | **64k** | 1M |
| 圖片輸入 | ✗ | **✓**（最多 4 張） | ✓ |
| 影片／聲音輸入 | ✗ | ✗（只能截圖當圖片送，見下） | ✗ |
| 計費 | AI Gateway 儲值 | Workers AI neurons（免費額度可能適用） | AI Gateway 儲值 |
| 資料處理 | 第三方（標示 zero data retention） | Cloudflare 自家 | Anthropic（經 Cloudflare） |

- **純文字分類建議 `jev-b`**：準確率與 `clef-b`、`haiku-medium` 打平，最便宜也最快，而且有可調的 confidence。
- **Clef 多了圖片輸入，但對 Cofacts 的實際幫助有限**：Cofacts 的圖片訊息大多是文字截圖，OCR 逐字稿已經涵蓋主要內容；
  影片則只能截圖送入，聲音完全不處理（見下方「Clef 的圖片與影片輸入」）。
- **Haiku 清單**適合「不需要調門檻、要一份清單」的場景，或產生候選標籤再讓人工確認；成本與延遲都不如 Jev。
- **改題目的效益（+0.02~0.07）遠大於換模型（±0.01）**：下一步應優先投資在題目與 ground truth。
- **採用題目 B 之前**：從 10,384 篇中另抽一份沒看過的樣本（例如 500 篇隨機），用 `jev-a`、`jev-b` 各跑一次（約 $0.2），
  確認題目 B 的優勢在新樣本上仍成立。

#### Clef 的圖片與影片輸入

Workers AI 上的 Clef 只開放圖片輸入，**不能直接傳影片，也不處理聲音**（2026-10-12 實測，`clef` 與 `clef-flash` 相同）：

| 輸入方式 | 結果 |
|---|---|
| `images`：base64 data URL | ✓ 文件記載的唯一媒體輸入：最多 4 張，PNG／JPEG／WebP，每張 ≤ 4 MiB、合計 ≤ 8 MiB |
| `videos`：mp4 data URL | ✗ API 認得這個欄位（格式不對會報驗證錯誤），但送合法 mp4 會回傳 `This model accepts images but not audio or video`（code 5012） |
| 聲音 | ✗ 沒有任何輸入欄位 |
| 從影片截 4 張畫面當 `images` 送 | ✓ 可行，見下方測試 |

截圖測試：用 ffmpeg 做兩支 4 秒、640×360 的合成影片，畫面只有一行英文字
（健康偏方「DRINK HOT LEMON WATER / IT KILLS CANCER CELLS」、選舉舞弊「ELECTION WAS RIGGED / THE RULING PARTY CHEATED」），
每秒截 1 張、共 4 張送入，只問「疾病、醫藥」與「政治」兩題：

| 影片 | `clef`：疾病醫藥 / 政治 | `clef-flash`：疾病醫藥 / 政治 |
|---|---:|---:|
| 健康偏方 | 0.96 / 0.02 | 0.92 / 0.01 |
| 選舉舞弊 | 0.02 / 0.95 | 0.01 / 0.92 |

- **成本**：4 張 640×360 的畫面讓 input tokens 從 271 增為 1,166（每張約 224 tokens，文件寫明每張上限 1,024 tokens）。
  每篇多約 900 tokens，`clef` 每篇多約 $0.0002（每 1 萬篇多約 $2.1，約為 `clef-b` 純文字成本的 +25%），`clef-flash` 每篇多約 $0.00003。
- **這個測試只證明 Clef 讀得到畫面上的字**：合成影片的內容就是文字，等同文字截圖，不代表 Clef 看得懂真實影片的畫面。
- **影片的主要內容在聲音裡**，仍需要 rumors-api 現有的 AI 逐字稿。比較實際的做法是「逐字稿 + 2~4 張關鍵畫面」一起送 Clef；
  Jev 只收文字，用不到畫面。
- Clef 在 Hugging Face 上的開放權重版本（Apache-2.0、27B）自架時可以直接收一串影格，但需要大型 GPU，與本案壓低成本的目標相反。
- **尚未用真實影片驗證**，卡在兩件事：
  1. 公開的 Cofacts API 在未登入時，`attachmentUrl`（`ORIGINAL`／`PREVIEW`／`THUMBNAIL`）都回傳 null，需要有權限的帳號或 GCS 讀取權限才能取得影片檔。
  2. 本次的 ground truth（2021 年）全是文字訊息；API 上的 21,427 篇 VIDEO 文章抽查 20 篇都沒有分類，缺少標準答案。


## 8. 結論與建議

1. **決策模型在概念上非常適合這個任務**：N 個 noul 問題直接對應「N 個 category 的信心值」，
   門檻可以事後調整而不必重跑推論，且 `aiModel` / `aiConfidence` 欄位在 rumors-api 已經存在，落地成本極低。
2. **Context window 不是問題**：實測 16 類的題目區約 3,700 tokens（§7.8），
   一般訊息遠低於上限；只有超長影音逐字稿需截斷處理。**不需要分批呼叫**。
3. **成本不是問題**：Jev 搭題目 B 每篇 $0.000176，每月 1 萬篇約 $1.8、回填 28 萬篇約 $49（§7.8）。
   但 Jev 走 AI Gateway 儲值計費，**不在 Workers AI 免費額度內**；仍比 2021 年常駐 GPU host 便宜約 2 個數量級。
4. **中文準確率：可用，但要靠門檻把關**（§7.2）。
   - 決策模型的逐類 AUC 平均 0.96~0.97、Top-3 命中 96~97%；最好的方案 micro-F1 約 0.75。
   - 以 precision ≥ 0.9 逐類訂門檻時，隨機子集上可得 P 約 0.97 / R 約 0.63~0.65。
   - 「疾病、醫藥」與「優惠措施、新法規、政策宣導」表現差，「中國政治宣傳」難以達到高 precision，上線初期應排除自動標記（§7.6、§7.7）。
   - 量到的 precision 是下限：ground truth 幾乎都是單標籤，抽查的高分誤判中 78~93% 其實合理（§7.7）。
5. **題目寫法的影響大於模型選擇**：同一個模型，題目 B（逐類具體條件）比題目 A（通用條件）micro-F1 高 0.02~0.07；
   同樣用題目 B 時，Jev、Clef、Haiku（medium）之間的差距在 ±0.01 內、不顯著（§7.2）。
6. **Jev vs Clef**：題目 B 下準確率打平，Jev 便宜約 5 倍、快約 40%。Clef 多了圖片輸入，但 Cofacts 的圖片多為文字截圖；
   影片不能直接傳、聲音不處理，最多只能「逐字稿 + 4 張截圖」（§7.10）。
7. **LLM 輸出清單可行但不划算**：Claude Haiku 5.5（medium）準確率與題目 B 的決策模型打平，
   但沒有 confidence 可調門檻，成本是 Jev 的 3~3.4 倍，延遲 p50 約 7~9 倍（§7.2、§7.9）。
8. **模型輸出的機率並未在 Cofacts 資料上呈現良好校準**（分數 0.6 實際正例率 24~43%），
   部分原因是 ground truth 漏標；無論如何，門檻都必須逐類從資料校準，不可直接把 `noul` 當機率用（§7.4）。

**建議的下一步：**

1. **在新樣本上驗證題目 B**：題目 B 是參考同一份樣本的誤判寫的（§7.1）。
   另抽一份沒看過的樣本（例如 500 篇隨機），用 `jev-a`、`jev-b` 各跑一次（約 $0.2），確認題目 B 的優勢仍在。
2. **補齊 ground truth 的多標籤**：至少把「子分類 ⇒ 母分類」（`covid19`、`aids` ⇒ `medical`）補上，
   並抽查一批高分誤判由人工確認，才能得到可信的 precision 與校準曲線。
3. **繼續改題目**：收窄「連署、集氣」的條件（題目 B 在 Clef 上略降）、處理「優惠措施」範圍過廣的問題（§7.6）。
   每次調整都用 `report.py` 在同一份樣本上比較，Jev 每輪約 $0.2。
4. **（可選）測 Clef 的「逐字稿 + 關鍵畫面」**：需先取得影片檔的讀取權限並標註約 50~100 篇影片訊息，
   比較「只送逐字稿」與「逐字稿 + 4 張截圖」（§7.10）。若沒有明顯提升，就沒有選 Clef 的理由。
5. 以 `jev-b` 與 §7.5 的逐類門檻（precision ≥ 0.9）為起點，在 rumors-api 實作 `util/jev.ts` + `util/classifyArticle.ts`，
   並補上 per-category 閾值表；達不到 precision 0.9 的類別先不自動標記。
6. 先做 `src/scripts/classifyArticles.ts` 與 `CATEGORY` 型 AIResponse，用 `--dry-run` 在小量 production 資料上驗證；
   補跑 script 需限速以避開 AI Gateway 的 unified billing rate limit（§7.8）。
7. 最後才在 `CreateArticle` / `CreateMediaArticle` 掛上 fire-and-forget 呼叫，
   並記得補 `createArticleCategory` 的 `retry_on_conflict`。
8. 與現行 Gemini 大 prompt 的 A/B（[20250630](../meetings/2025/20250630.md) 訂下的比較基準）沒有另外做，
   但 §7 的 Claude Haiku 5.5 已經是同一類「一個大 prompt 輸出清單」做法的代表；
   若仍要比 Gemini，可沿用 `llm_run.py` 的 prompt 與 `report.py` 的評估方式。

## 9. 待確認事項

- [x] ~~`typesafe/jev` 在 Cofacts 的 Cloudflare 帳號是否已啟用？~~
      → 不需啟用，但需先在 AI Gateway 儲值 credits（2026-10-11 已儲值並實測，§7.8）。
- [x] ~~驗證 §4.1 的單價~~ → 模型頁已列出 $0.042/M input、output 與 cached input 免費；實測 token 用量見 §7.8。
- [x] ~~每日 10,000 Neurons 免費額度是否適用於 third-party partner model？~~
      → 不適用，Jev 走 AI Gateway unified billing（§7.8）。Clef 系列走 Workers AI neurons。
- [x] ~~目前 `ListCategories` 實際有幾個 category？~~
      → 共 21 個：16 個公開分類、3 個 AI 專用、2 個已停用（🚧），見 §7.1。
- [ ] 題目 B 在新樣本上的驗證（§8 下一步 1）。
- [ ] Ground truth 的多標籤補齊（§7.7、§8 下一步 2）。「precision ≥ 0.9」設定的數字也受這點影響。
- [ ] 影片訊息的分類是否值得用到畫面？需要影片檔讀取權限與一批影片訊息的標註（§7.10、§8 下一步 4）。
- [ ] Jev 的資料處理條款（<https://docs.typesafe.ai/legal.md>）是否可接受？模型頁標示 zero data retention。
- [ ] 目前每月新增 article 數（本文以 3,000 / 10,000 兩種情境估算）。
      註：2026-09 的 ES reindex 記錄顯示 `articles` index 共 **279,286** 筆（[20260914](../meetings/2026/20260914.md)），
      但這是累積值，不是流量。
- [ ] 2021 年 BERT GPU host 的實際月費與停用時間點（kb 內未記載）。
- [ ] 2025 年那份一直沒結案的 benchmark 結果是否存在？（可作為對照組）
- [ ] [cofacts/worker](https://github.com/cofacts/worker) repo 與 [worker#3](https://github.com/cofacts/worker/pull/3)、
      [worker#2](https://github.com/cofacts/worker/issues/2) 要關閉 / archive 還是留著？
      （url-resolver 確定維持現有 gRPC 寫法，classifier 改進 rumors-api，worker 已無待辦）
