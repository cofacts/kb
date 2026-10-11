---
type: DesignDoc
title: "以 Jev 實作 Cofacts Topic Classifier 之可行性評估"
tags: [cofacts, design-docs, technical-design, ai, classifier]
timestamp: "2026-10-11T23:00:00+08:00"
---

# 以 Jev 實作 Cofacts Topic Classifier 之可行性評估

> [!NOTE]
> 本文評估 Cloudflare Workers AI 上的第三方模型 [`typesafe/jev`](https://developers.cloudflare.com/ai/models/typesafe/jev/)
> 是否適合作為 Cofacts article category（topic label）分類器的推論引擎，
> 並討論其成本、context 限制，以及在 `CreateArticle` / `CreateMediaArticle` 上掛載的實作方式。
>
> 本文由 Claude Code 依據 kb 內既有會議記錄與 repo 程式碼整理。
> §1~§6 為實測前的調查與估算；**§7 為 2026-10-11 以 ground truth 1,000 篇實測 Jev 與 Clef 的結果**，
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
  - **實測更新**：不需另行啟用，但要先在 AI Gateway 儲值 credits（unified billing）才能呼叫，見 §7.7。

## 4. 成本估算

### 4.1 Jev 的單價

> [!NOTE]
> **實測更新（2026-10）**：[Jev 模型頁](https://developers.cloudflare.com/ai/models/typesafe/jev/)現已列出
> Input $0.042 / M、Output $0.00 / M、Cached input $0.00 / M，與下表一致；
> 實測每篇 input 約 4,049 tokens、output 固定 416 tokens（免費），見 §7.7。
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
   未儲值時呼叫失敗，而同帳號的 Workers AI 自家模型（Clef）正常。見 §7.7。
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

## 7. 實測結果：Jev vs Clef（2026-10-11）

> [!IMPORTANT]
> **TL;DR**
>
> - **中文準確率可用，但還不到可以不設門檻就全自動上線的程度。** 三個模型的逐類 ROC-AUC 平均都在 **0.96~0.97**，
>   Top-3 至少命中一個正確分類的比率 **96~97%**，排序能力很好；
>   但單一門檻下 micro-F1 最高只有 **0.68**，逐類門檻（CV）也只有 **0.70~0.72**。
> - **Jev 與 Clef 準確率幾乎打平**：F1 導向的策略 Jev 小贏約 0.02，precision ≥ 0.9 的高精度策略 Clef 小贏約 0.035
>   （皆為 bootstrap 95% CI 顯著但幅度小）。clef-flash 略遜於兩者。
> - **Jev 便宜且快**：每篇 **$0.00017**（Clef 的 1/5）、單篇延遲 p50 **0.28 秒**（Clef 0.46 秒）。
> - **量到的 precision 是下限**：ground truth 92.5% 的文章只有一個標籤；抽查 40 個高分誤判（FP），
>   **約 78%（31/40）其實是合理的標記**，只是 ground truth 沒標。
> - **建議的選擇策略**：逐類門檻，以 precision ≥ 0.9 為目標
>   （在隨機抽樣子集上 Jev P 0.97 / R 0.65、Clef P 0.96 / R 0.68）；
>   若要更高 recall，可用「分數 ≥ 0.7、最多取前 2 個；都沒過門檻就取最高分 1 個」（F1 ≈ 0.70）。

### 7.1 實驗設定

**資料**：[cofacts/ground-truth](https://github.com/cofacts/ground-truth) 的 `20211210_17111.zip`
（實際為 gzip 壓縮的 tar，內含 17,111 個 `{id, createdAt, tags, text, url}` JSON）。

- **排除**：帶有以下任一標籤的文章整篇排除，剩 10,384 篇。
  - AI 專用標籤：有意義但不包含在以上標籤（`nT2n7nEBrIRcahlY6QqF`）、無意義（`nj2n7nEBrIRcahlY-gpc`）、只有網址其他資訊不足（`oD2o7nEBrIRcahlYFgpm`）
  - 已停用（🚧）：性少數與愛滋病（`kz3c7XEBrIRcahlYxAp6`）、基本人權問題（`lj2m7nEBrIRcahlY6Ao_`）
- **抽樣 1,000 篇**（固定 seed）：
  1. 先確保每個類別至少有 60 則正例（愛滋病全部只有 6 則），共 687 篇；
  2. 其餘 313 篇從剩下的文章**隨機抽樣**，保留實際分布。
  - 因為稀有類別被刻意補足，全樣本上稀有類別的 precision 會比實際上線時樂觀；
    下文另外列出「僅隨機抽樣子集」的結果作為較接近實際分布的參考。

**類別定義**：以 `ListCategories`（`api.cofacts.tw/graphql`，2026-10-11 抓取，共 21 個）的
`id`、`title`、`description` **原文**組成題目，扣掉上述 5 個後剩 16 類。

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

**Input / Output**：

- Input：一篇文章**一次呼叫**，16 個 `noul` 問題同時送出。`state` 為
  「以下是台灣民眾轉傳到 Cofacts 真的假的（協作查核平台）請求查證的一則訊息：」＋ 文章內文（超過 4,000 字截斷，樣本中僅 1% 文章超過 3,100 字）。
- Output：長度 16 的陣列，第 i 個元素為第 i 個類別的 `noul` 機率（即 confidence）。
- 題目以「誰會有興趣」（目標編輯）為判斷標準，每題格式如下（以中國政治宣傳為例）：

```json
{
  "type": "noul",
  "instructions": "這則訊息是否屬於 Cofacts 的「中國政治宣傳」分類？判斷標準是：下列「目標編輯」會不會想看、想查核或想回應這則訊息。\n\n目標編輯：\n- 關注中國動態的人或政黨，如台灣基進、時代力量、促統黨、新黨。\n- 關注兩岸與資訊戰的學術單位。\n\n兩岸三地、疆獨藏獨相關事件的消息，或來自中國官方的論述、對中國事務全然正面的描述等疑似為大外宣一環的訊息。",
  "criteria": {
    "true": "訊息落在「中國政治宣傳」的範圍，目標編輯會有興趣處理它",
    "false": "訊息與「中國政治宣傳」無關，目標編輯不會特別想處理它"
  }
}
```

**受測模型**（皆透過 Workers AI REST API 呼叫，Python `requests`，8 併發）：

| 模型 | Endpoint | 回傳版本 | 備註 |
|---|---|---|---|
| `typesafe/jev` | `POST /accounts/{id}/ai/run`，body `{"model":"typesafe/jev","input":{...}}` | `jev-1.13.0` | 第三方模型，走 AI Gateway unified billing；回應多包一層 `{"state":"Completed","result":{...}}` |
| `@cf/cloudflare/clef` | `POST /accounts/{id}/ai/run/@cf/cloudflare/clef`，body `{"model":"clef",...}` | `clef` | 27B，多模態，64k context |
| `@cf/cloudflare/clef-flash` | 同上，`model: "clef-flash"` | `clef-flash` | 9B，24k context；順手一起測 |

三個模型 1,000 篇皆 **0 失敗**。實驗程式與原始分數放在
[`jev-topic-classifier-evaluation/`](jev-topic-classifier-evaluation/)（`results/` 只含 article ID 與分數，不含內文），
可用 `analyze.py` 重算本節所有表格。

### 7.2 不同 confidence 門檻的 Precision / Recall / F1

所有類別共用同一個門檻，分數 ≥ 門檻即視為標上該類。
Micro＝把所有 (文章, 類別) 配對攤平計算；Macro＝每類各算再平均（稀有類別與大類別等權）。

| 門檻 | Jev micro P / R / F1 | Clef micro P / R / F1 | clef-flash micro P / R / F1 |
|---:|---|---|---|
| 0.1 | 0.281 / 0.984 / **0.437** | 0.332 / 0.978 / **0.496** | 0.282 / 0.971 / **0.437** |
| 0.2 | 0.380 / 0.950 / **0.542** | 0.452 / 0.933 / **0.609** | 0.383 / 0.921 / **0.541** |
| 0.3 | 0.448 / 0.924 / **0.604** | 0.520 / 0.878 / **0.653** | 0.462 / 0.873 / **0.604** |
| 0.4 | 0.498 / 0.887 / **0.638** | 0.568 / 0.832 / **0.675** | 0.519 / 0.821 / **0.636** |
| 0.5 | 0.554 / 0.837 / **0.667** | 0.603 / 0.779 / **0.680** | 0.569 / 0.771 / **0.655** |
| 0.6 | 0.591 / 0.787 / **0.675** | 0.627 / 0.719 / **0.670** | 0.614 / 0.721 / **0.663** |
| 0.7 | 0.637 / 0.724 / **0.678** | 0.653 / 0.654 / **0.654** | 0.633 / 0.644 / **0.639** |
| 0.8 | 0.696 / 0.629 / **0.661** | 0.685 / 0.549 / **0.610** | 0.670 / 0.546 / **0.602** |
| 0.9 | 0.760 / 0.405 / **0.528** | 0.747 / 0.344 / **0.471** | 0.703 / 0.374 / **0.488** |
| 0.95 | 0.776 / 0.187 / **0.302** | 0.809 / 0.144 / **0.245** | 0.745 / 0.209 / **0.326** |

<details><summary>Macro P / R / F1</summary>

| 門檻 | Jev macro P / R / F1 | Clef macro P / R / F1 | clef-flash macro P / R / F1 |
|---:|---|---|---|
| 0.1 | 0.293 / 0.984 / **0.433** | 0.330 / 0.977 / **0.481** | 0.324 / 0.969 / **0.461** |
| 0.2 | 0.391 / 0.956 / **0.537** | 0.500 / 0.933 / **0.633** | 0.432 / 0.914 / **0.560** |
| 0.3 | 0.466 / 0.930 / **0.602** | 0.582 / 0.871 / **0.679** | 0.521 / 0.864 / **0.619** |
| 0.4 | 0.526 / 0.893 / **0.638** | 0.658 / 0.824 / **0.707** | 0.590 / 0.808 / **0.641** |
| 0.5 | 0.598 / 0.845 / **0.677** | 0.713 / 0.767 / **0.707** | 0.654 / 0.756 / **0.659** |
| 0.6 | 0.632 / 0.795 / **0.680** | 0.750 / 0.699 / **0.681** | 0.718 / 0.704 / **0.662** |
| 0.7 | 0.685 / 0.728 / **0.677** | 0.797 / 0.621 / **0.638** | 0.759 / 0.629 / **0.624** |
| 0.8 | 0.766 / 0.635 / **0.658** | 0.833 / 0.516 / **0.557** | 0.808 / 0.538 / **0.573** |
| 0.9 | 0.854 / 0.415 / **0.485** | 0.805 / 0.277 / **0.347** | 0.789 / 0.348 / **0.419** |
| 0.95 | 0.721 / 0.177 / **0.248** | 0.585 / 0.117 / **0.161** | 0.710 / 0.179 / **0.240** |

</details>

觀察：

- **Jev 的分數整體偏高**：同樣門檻下 recall 較高、precision 較低，最佳單一門檻落在 **0.6~0.7**；Clef 則在 **0.4~0.5**。
  兩者的分數**不能共用同一組門檻**。
- 單一門檻的 micro-F1 天花板：Jev 0.678、Clef 0.680、clef-flash 0.663。
- 即使門檻拉到 0.95，micro precision 也只到 0.78~0.81——原因見 §7.6，主要是 ground truth 漏標。

### 7.3 排序品質與校準

| 模型 | Top-1 命中率 | Top-3 至少命中 1 個 | 每篇正例數 vs 分數 > 0.5 的個數 | 逐類 ROC-AUC 平均 |
|---|---:|---:|---:|---:|
| Jev | **0.743** | 0.962 | 1.26 vs 1.89 | **0.969** |
| Clef | 0.723 | **0.971** | 1.26 vs 1.63 | 0.967 |
| clef-flash | 0.730 | 0.957 | 1.26 vs 1.71 | 0.959 |

把所有 (文章, 類別) 的分數分箱，比較「平均分數」與「實際為正例的比例」（完美校準時兩者相等）：

| 分數區間 | Jev 筆數 / 平均分數 / 實際正例率 | Clef 筆數 / 平均分數 / 實際正例率 | clef-flash 筆數 / 平均分數 / 實際正例率 |
|---|---|---|---|
| [0, 0.1) | 11587 / 0.03 / 0.00 | 12291 / 0.03 / 0.00 | 11654 / 0.02 / 0.00 |
| [0.1, 0.3) | 1817 / 0.17 / 0.04 | 1581 / 0.17 / 0.08 | 1966 / 0.18 / 0.06 |
| [0.3, 0.5) | 694 / 0.39 / 0.16 | 499 / 0.39 / 0.25 | 674 / 0.39 / 0.19 |
| [0.5, 0.7) | 470 / 0.60 / 0.30 | 368 / 0.60 / 0.43 | 423 / 0.60 / 0.38 |
| [0.7, 0.9) | 761 / 0.81 / 0.53 | 681 / 0.82 / 0.57 | 613 / 0.81 / 0.56 |
| [0.9, 1.0) | 671 / 0.94 / 0.76 | 580 / 0.94 / 0.75 | 670 / 0.95 / 0.70 |

- **以 ground truth 衡量，三個模型都「過度自信」**：分數 0.6 的配對實際只有 30~43% 是正例，Jev 偏差最大。
- 但這張表同樣受 ground truth 漏標影響（§7.6）。若約 3/4 的高分 FP 其實正確，
  [0.9, 1.0) 區間的「真實」正例率可能達 0.9 以上——**「calibrated」的宣稱在 Cofacts 資料上無法直接驗證，需先補齊多標籤的 ground truth**。
- 實務上的意義：**不要把 `noul` 直接當機率解讀，門檻一律逐類從資料校準**（§5 的流程不變）。

### 7.4 最終結果選擇策略

逐類門檻（per-label）以 **5-fold cross validation** 計算：在其餘 4 折找門檻、套用在留出的一折，避免同一批資料上調參的樂觀偏差。
括號內為平均每篇輸出的標籤數（ground truth 為 1.26）。

| 策略 | Jev P / R / F1（標籤數） | Clef P / R / F1（標籤數） | clef-flash P / R / F1（標籤數） |
|---|---|---|---|
| 分數 ≥ 0.5 | 0.554 / 0.837 / **0.667** (1.90) | 0.603 / 0.779 / **0.680** (1.63) | 0.569 / 0.771 / **0.655** (1.71) |
| 分數 ≥ 0.7 | 0.637 / 0.724 / **0.678** (1.43) | 0.653 / 0.654 / **0.654** (1.26) | 0.633 / 0.644 / **0.639** (1.28) |
| 分數 ≥ 0.8 | 0.696 / 0.629 / **0.661** (1.14) | 0.685 / 0.549 / **0.610** (1.01) | 0.670 / 0.546 / **0.602** (1.03) |
| 分數 ≥ 0.9 | 0.760 / 0.405 / **0.528** (0.67) | 0.747 / 0.344 / **0.471** (0.58) | 0.703 / 0.374 / **0.488** (0.67) |
| 分數 ≥ 0.5，最多取前 3 | 0.567 / 0.825 / **0.672** (1.83) | 0.604 / 0.774 / **0.678** (1.61) | 0.576 / 0.767 / **0.658** (1.68) |
| 分數 ≥ 0.5，最多取前 2 | 0.613 / 0.783 / **0.688** (1.61) | 0.619 / 0.751 / **0.679** (1.53) | 0.614 / 0.740 / **0.671** (1.52) |
| 分數 ≥ 0.7，最多取前 3 | 0.641 / 0.721 / **0.679** (1.42) | 0.654 / 0.653 / **0.653** (1.26) | 0.634 / 0.644 / **0.639** (1.28) |
| 分數 ≥ 0.7，最多取前 2 | 0.659 / 0.699 / **0.679** (1.34) | 0.660 / 0.647 / **0.653** (1.24) | 0.653 / 0.639 / **0.646** (1.23) |
| 分數 ≥ 0.8，最多取前 3 | 0.697 / 0.629 / **0.661** (1.14) | 0.685 / 0.549 / **0.610** (1.01) | 0.670 / 0.546 / **0.602** (1.03) |
| 分數 ≥ 0.8，最多取前 2 | 0.705 / 0.618 / **0.659** (1.10) | 0.688 / 0.548 / **0.610** (1.00) | 0.679 / 0.543 / **0.603** (1.01) |
| **分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個** | 0.651 / 0.752 / **0.698** (1.46) | 0.649 / 0.715 / **0.680** (1.39) | 0.639 / 0.707 / **0.671** (1.40) |
| 只取最高分 1 個 | 0.743 / 0.590 / **0.658** (1.00) | 0.723 / 0.574 / **0.640** (1.00) | 0.730 / 0.579 / **0.646** (1.00) |
| **逐類門檻（max F1, CV）** | 0.668 / 0.783 / **0.721** (1.48) | 0.637 / 0.783 / **0.702** (1.55) | 0.624 / 0.758 / **0.684** (1.53) |
| 逐類門檻（max F1, CV），最多前 3 | 0.682 / 0.764 / **0.721** (1.41) | 0.639 / 0.775 / **0.701** (1.53) | 0.635 / 0.747 / **0.686** (1.48) |
| **逐類門檻（precision ≥ 0.9, CV）** | 0.879 / 0.421 / **0.569** (0.60) | 0.886 / 0.458 / **0.604** (0.65) | 0.877 / 0.429 / **0.576** (0.62) |

**僅看隨機抽樣子集（313 篇，接近實際分布）：**

| 策略 | Jev P / R / F1 | Clef P / R / F1 | clef-flash P / R / F1 |
|---|---|---|---|
| 分數 ≥ 0.5 | 0.530 / 0.856 / **0.655** | 0.560 / 0.868 / **0.681** | 0.518 / 0.881 / **0.653** |
| 分數 ≥ 0.7 | 0.617 / 0.768 / **0.684** | 0.609 / 0.799 / **0.691** | 0.558 / 0.781 / **0.651** |
| 分數 ≥ 0.8 | 0.660 / 0.693 / **0.676** | 0.630 / 0.693 / **0.660** | 0.590 / 0.690 / **0.636** |
| 分數 ≥ 0.9 | 0.734 / 0.476 / **0.578** | 0.741 / 0.511 / **0.605** | 0.625 / 0.517 / **0.566** |
| 分數 ≥ 0.5，最多取前 2 | 0.558 / 0.843 / **0.672** | 0.578 / 0.868 / **0.694** | 0.576 / 0.865 / **0.692** |
| 分數 ≥ 0.7，最多取前 2 | 0.621 / 0.765 / **0.685** | 0.613 / 0.799 / **0.694** | 0.591 / 0.771 / **0.669** |
| 分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個 | 0.617 / 0.828 / **0.707** | 0.603 / 0.843 / **0.703** | 0.603 / 0.862 / **0.710** |
| 只取最高分 1 個 | 0.725 / 0.712 / **0.718** | 0.712 / 0.699 / **0.706** | 0.751 / 0.737 / **0.744** |
| 逐類門檻（max F1, CV） | 0.773 / 0.853 / **0.811** | 0.605 / 0.875 / **0.715** | 0.594 / 0.859 / **0.703** |
| 逐類門檻（precision ≥ 0.9, CV） | 0.967 / 0.649 / **0.777** | 0.960 / 0.683 / **0.799** | 0.942 / 0.658 / **0.775** |

**模型間差異是否顯著**（全樣本，paired bootstrap 1,000 次）：

| 策略 | Jev micro-F1 [95% CI] | Clef micro-F1 [95% CI] | clef-flash micro-F1 [95% CI] | Jev − Clef [95% CI] |
|---|---|---|---|---|
| 分數 ≥ 0.7，最多前 2；都沒過則取最高 1 個 | 0.698 [0.678, 0.715] | 0.680 [0.661, 0.698] | 0.671 [0.653, 0.690] | +0.018 [+0.002, +0.032] |
| 逐類門檻（max F1, CV） | 0.721 [0.706, 0.739] | 0.702 [0.686, 0.720] | 0.684 [0.668, 0.701] | +0.019 [+0.005, +0.034] |
| 逐類門檻（precision ≥ 0.9, CV） | 0.569 [0.542, 0.594] | 0.604 [0.579, 0.630] | 0.576 [0.549, 0.601] | −0.035 [−0.053, −0.017] |

**建議策略：**

1. **上線預設：逐類門檻，以 precision ≥ 0.9 為約束、取該約束下 recall 最大的門檻**（即 §5 原本的建議）。
   - 在隨機抽樣子集上：Jev **P 0.967 / R 0.649**、Clef **P 0.960 / R 0.683**，平均每篇約 0.6 個標籤。
   - 達不到 precision 0.9 的類別（見 §7.5 表格中的「—」）**先不自動標記**，留給人工。
   - 因為 ground truth 漏標，實際 precision 應高於表上數字。
2. **若想讓每篇都至少有一個標籤**（例如供編輯篩選用、會再經人工確認）：
   **「分數 ≥ 0.7、最多取前 2 個；都沒過門檻就取最高分 1 個」**。
   不需逐類調參，全樣本 F1 0.70，平均每篇 1.4~1.5 個標籤。注意 Clef 的分數較低，同一規則用在 Clef 時門檻可降到 0.5~0.6。
3. **「取前 3」的上限幾乎沒有作用**：分數 ≥ 0.7 的類別本來就很少超過 3 個；改成「最多 2 個」才有實質影響。
4. 逐類門檻（max F1）在隨機子集上 Jev 達 0.81，但 313 篇裡稀有類別的正例只有個位數，**這個數字變異很大，不宜當作預期值**。

### 7.5 逐類表現

「max F1 門檻」是在整個樣本上找的最佳門檻（樂觀估計，僅供設定初始值參考）；
「P≥0.9 門檻 → R」是達到 precision 0.9 的最低門檻與對應 recall（— 表示達不到）。

<details><summary><b>Jev</b> 逐類 P / R / F1</summary>

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

<details><summary><b>Clef</b> 逐類 P / R / F1</summary>

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

<details><summary><b>clef-flash</b> 逐類 P / R / F1</summary>

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

各類別大致分成三群（三個模型一致）：

| 表現 | 類別 | 說明 |
|---|---|---|
| **好**（F1 約 0.8 以上，皆可達 P 0.9） | 性別議題、保健秘訣、電力能源、連署集氣、愛滋病（僅 6 例） | 主題詞彙明確 |
| **中**（F1 約 0.55~0.8） | 台灣政治、農林漁牧、科技資安、環保生態、COVID-19、跨國互動、中國政治宣傳、商業廣告、詐騙 | 與鄰近類別邊界模糊，見 §7.6 |
| **差**（F1 約 0.3~0.57，三個模型皆低） | 疾病醫藥、優惠措施／新法規／政策宣導 | 前者是定義與 ground truth 不一致，後者是範圍太廣（AUC 最低，0.91） |

### 7.6 誤判分析：多數「FP」其實是 ground truth 漏標

Ground truth 有 92.5% 的文章只有一個標籤，但 Cofacts 的分類本來就是多標籤。
從 Jev 分數 ≥ 0.8 的 346 個 FP 中隨機抽 40 個，由 Claude 逐則判斷「依 `ListCategories` 定義，該標籤是否合理」：

- **31 / 40（78%）合理**，ground truth 漏標。例如：
  - 新冠疫苗陰謀論（GT：COVID-19）被標「疾病、醫藥」——`covid19` 的 description 本身就寫「「疾病、醫藥」下的子分類之一」；
  - 中美貿易戰、華為晶片（GT：中國政治宣傳）被標「跨國互動」；
  - 打字賺錢、繳押金的工作（GT：商業廣告）被標「詐騙」；
  - 宣稱塑膠杯致癌、阿茲海默症新藥（GT：保健秘訣）被標「疾病、醫藥」。
- **9 / 40 不合理**，全部是「疾病、醫藥」標在一般保健文章上（如「芒果葉治糖尿病」、「夜尿與心梗」、「晚飯不吃治百病」）。
  這是兩個類別的定義重疊：「保健秘訣」寫「治慢性病等的偏方秘笈」、「疾病、醫藥」寫「癌症，以及各種藥物的相關傳言」。

> [!NOTE]
> 這 40 則是由 Claude 判讀，不是人工標記，僅能當作量級參考。
> 但它指出：**§7.2~§7.4 的 precision 都是保守估計**；
> 若要正式訂門檻，ground truth 應先補成多標籤（至少把「子分類 ⇒ 母分類」補齊，例如 `covid19`、`aids` ⇒ `medical`）。

逐類的具體改善方向：

- **疾病、醫藥**：
  1. 處理階層關係——`covid19` / `aids` 是它的子分類，模型照定義會一起標。要嘛 ground truth 補上母分類，要嘛上線時「已標子分類就不再標母分類」。
  2. 在 criteria 寫明「食療、偏方、日常保健屬於『保健秘訣、食品安全』」。
- **詐騙 vs 商業廣告**：ground truth 中這兩類同時出現 264 次，是最大的共現組合。可考慮在 criteria 中寫清楚分界（例如「要求先付款／提供個資」⇒ 詐騙）。
- **中國政治宣傳**：高分區混入大量「台灣政治」與「跨國互動」文章，**Jev / Clef 只能在 recall ≈ 0.1 時達到 precision 0.9，clef-flash 則達不到**；上線初期建議不自動標。

### 7.7 成本

| 模型 | input 單價（USD/M） | 每篇 input tokens 平均 / p95 | 每篇 output tokens | 每篇成本 | 每 1,000 篇 | 每月 10,000 篇 | 重跑 17K | 回填 28 萬篇 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Jev** | 0.042 | 4,049 / 5,033 | 416（免費） | **$0.000170** | $0.17 | **$1.70** | $2.9 | $47.5 |
| Clef | 0.24 | 3,421 / 4,080 | 0（免費） | $0.000821 | $0.82 | $8.21 | $14.0 | $229 |
| clef-flash | 0.038 | 3,421 / 4,080 | 0（免費） | $0.000130 | $0.13 | $1.30 | $2.2 | $36.3 |

- 本次實驗（主實驗 1,000 篇＋延遲量測 200 篇＋試跑，每模型約 1,210 次呼叫）實際花費：
  Jev ≈ $0.21、Clef ≈ $0.99、clef-flash ≈ $0.16，**合計約 $1.4**。
- **Token 數與 §3.2 / §4.2 的估算吻合**：16 題的問題區約 3,700 tokens（Jev 計）／3,200 tokens（Clef 計），
  加上一般訊息後每篇約 4,000 tokens。**同一段文字 Jev 計出的 token 比 Clef 多約 18%**（tokenizer 不同），單價比較時要考慮進去。
- **Jev 的 output tokens 固定為 416**（16 題 × 26），和題目、文章長度無關。
- **計費管道不同**（本次實測所見）：
  - Clef 系列是 Cloudflare 自家模型，走 Workers AI 的 neurons 計費（$0.24/M ≈ 21,818 neurons/M，每篇約 75 neurons）。
    若每日 10,000 neurons 免費額度適用，**每天約 134 篇以內免費**。
  - **Jev 走 AI Gateway 的 unified billing，要先在 AI Gateway 儲值（credits）**；未儲值時 Jev 回傳
    `Insufficient balance; add money to your gateway or use BYOK`，而同一時間同一帳號的 Clef 呼叫正常。
    換言之，**Jev 不吃 Workers AI 的免費 neurons 額度**，§4.1.1「邊際成本可能是 $0」的推論不成立，
    但金額本身仍極小（每月 1 萬篇約 $1.7）。
  - Jev 在 8 併發（約 21 req/s）時有 29 / 1,000 次遇到 `429 Unified billing rate limit exceeded for this gateway`，
    重試一次即成功。正式上線的即時流量遠低於此，但**補跑 script（§6.5）需要限速**。

### 7.8 單篇延遲分布

從開發機（經 proxy）呼叫 Cloudflare REST API 的完整 round-trip 時間，含網路延遲。
「序列」為 1 併發、隨機抽樣子集 200 篇（最接近單篇即時分類的情境）；「8 併發」為主實驗 1,000 篇。

| 模型 | 情境 | n | 平均 | p50 | p90 | p95 | p99 | max | 重試次數 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jev | 序列 | 200 | 0.30s | **0.28s** | 0.35s | 0.46s | 0.72s | 1.02s | 0 |
| Jev | 8 併發 | 1000 | 0.31s | 0.28s | 0.37s | 0.55s | 0.74s | 1.39s | 29 |
| Clef | 序列 | 200 | 0.49s | **0.46s** | 0.64s | 0.72s | 0.90s | 1.20s | 0 |
| Clef | 8 併發 | 1000 | 0.51s | 0.47s | 0.68s | 0.78s | 1.06s | 1.42s | 0 |
| clef-flash | 序列 | 200 | 0.79s | **0.76s** | 0.88s | 0.96s | 1.02s | 1.39s | 0 |
| clef-flash | 8 併發 | 1000 | 0.83s | 0.78s | 0.92s | 1.02s | 1.50s | 3.33s | 0 |

序列情境的分布：

| 區間 | Jev | Clef | clef-flash |
|---|---:|---:|---:|
| 0–0.25s | 4% | 0% | 0% |
| 0.25–0.5s | **92%** | **66%** | 0% |
| 0.5–0.75s | 4% | 30% | 45% |
| 0.75–1.0s | 0% | 3% | **54%** |
| 1.0–1.5s | 0% | 1% | 2% |
| ≥ 1.5s | 0% | 0% | 0% |

- 三者都在 **1.5 秒內完成**，對「射後不理」的掛載方式（§6）完全不是問題。
- 8 併發時延遲幾乎不變，代表這個量級下沒有排隊。
- 延遲與 input 長度的相關係數：Jev −0.03、Clef 0.32、clef-flash 0.74——Jev 的延遲幾乎不受文章長度影響。
- clef-flash 雖然是較小的模型，實測卻比 Clef 慢，原因不明（可能是部署的硬體或排程不同）。

### 7.9 小結：選哪個模型？

| 面向 | Jev | Clef | clef-flash |
|---|---|---|---|
| 準確率（F1 導向策略） | **最好**（+0.02） | 次之 | 最差 |
| 準確率（precision ≥ 0.9 策略） | 次之 | **最好**（+0.035） | 次之 |
| 每月 1 萬篇成本 | $1.70 | $8.21 | **$1.30** |
| 延遲 p50 | **0.28s** | 0.46s | 0.76s |
| Context window | 32k | **64k** | 24k |
| 圖片輸入 | ✗ | **✓（最多 4 張）** | ✓ |
| 計費／帳號設定 | 需 AI Gateway 儲值，有 unified billing rate limit | Workers AI neurons（免費額度可能適用） | 同 Clef |
| 資料處理 | 第三方（標示 zero data retention） | Cloudflare 自家 | Cloudflare 自家 |

- **純文字分類：選 Jev**——準確率與 Clef 打平、便宜 5 倍、快 40%。
- **Clef 的獨特價值是圖片輸入**：Cofacts 有大量圖片訊息，Clef 可以直接看圖分類，不必等 OCR／逐字稿。
  這部分本次沒有測，值得另做一輪。
- clef-flash 便宜但準確率與延遲都沒有優勢，不建議。

## 8. 結論與建議

1. **Jev 在概念上非常適合這個任務**：N 個 noul 問題直接對應「N 個 category 的信心值」，
   門檻可以事後調整而不必重跑推論，
   且 `aiModel` / `aiConfidence` 欄位在 rumors-api 已經存在，落地成本極低。
2. **Context window 不是問題**：實測 16 類的問題區約 3,700 tokens（§7.7），
   一般訊息遠低於上限；只有超長影音逐字稿需截斷處理。**不需要分批呼叫**。
3. **成本不是問題**：實測每篇 $0.00017，每月 1 萬篇約 $1.7、回填 28 萬篇約 $48（§7.7）。
   但 Jev 走 AI Gateway 儲值計費，**不在 Workers AI 免費額度內**；仍比 2021 年常駐 GPU host 便宜約 2 個數量級。
4. **中文準確率：可用，但要靠逐類門檻把關**（§7）。
   - 排序能力好（逐類 AUC 平均 0.97、Top-3 命中 96%），單一門檻 micro-F1 約 0.68，逐類門檻約 0.72。
   - 以 precision ≥ 0.9 訂逐類門檻時，在接近實際分布的子集上可得 P 0.97 / R 0.65。
   - 「疾病、醫藥」與「優惠措施、新法規、政策宣導」表現差，「中國政治宣傳」難以達到高 precision，上線初期應排除自動標記。
   - 量到的 precision 是下限：ground truth 幾乎都是單標籤，抽查的高分 FP 中約 78% 其實合理。
5. **Jev vs Clef：純文字打平，Jev 便宜 5 倍、快 40%**；Clef 的優勢在可以直接吃圖片（§7.9）。
6. **模型輸出的機率並未在 Cofacts 資料上呈現良好校準**（分數 0.6 實際正例率 30~43%），
   部分原因是 ground truth 漏標；無論如何，門檻都必須逐類從資料校準，不可直接把 `noul` 當機率用。

**建議的下一步：**

1. **補齊 ground truth 的多標籤**：至少把「子分類 ⇒ 母分類」（`covid19`、`aids` ⇒ `medical`）補上，
   並抽查一批高分 FP 由人工確認，才能得到可信的 precision 與校準曲線。
2. **調整 criteria 後重跑**：釐清「疾病、醫藥 vs 保健秘訣」「詐騙 vs 商業廣告」的分界（§7.6），
   每次調整都用 `analyze.py` 在同一份 1,000 篇樣本上比較。成本每輪約 $0.2。
3. **測 Clef 的圖片輸入**：用圖片訊息（不經 OCR）直接分類，評估是否能取代「先逐字稿再分類」的流程。
4. 以 §7.4 的逐類門檻（precision ≥ 0.9）為起點，在 rumors-api 實作 `util/jev.ts` + `util/classifyArticle.ts`，
   並補上 per-category 閾值表；達不到 precision 0.9 的類別先不自動標記。
5. 先做 `src/scripts/classifyArticles.ts` 與 `CATEGORY` 型 AIResponse，用 `--dry-run` 在小量 production 資料上驗證；
   補跑 script 需限速以避開 AI Gateway 的 unified billing rate limit。
6. 最後才在 `CreateArticle` / `CreateMediaArticle` 掛上 fire-and-forget 呼叫，
   並記得補 `createArticleCategory` 的 `retry_on_conflict`。
7. 與現行 Gemini 大 prompt 的 A/B（[20250630](../meetings/2025/20250630.md) 訂下的比較基準）仍未做；
   可用同一份樣本與 `analyze.py`，只需把 Gemini 輸出轉成同樣的 16 維陣列。

## 9. 待確認事項

- [x] ~~`typesafe/jev` 在 Cofacts 的 Cloudflare 帳號是否已啟用？~~
      → 不需啟用，但需先在 AI Gateway 儲值 credits（2026-10-11 已儲值並實測，§7.7）。
- [x] ~~驗證 §4.1 的單價~~ → 模型頁已列出 $0.042/M input、output 與 cached input 免費；實測 token 用量見 §7.7。
- [x] ~~每日 10,000 Neurons 免費額度是否適用於 third-party partner model？~~
      → 不適用，Jev 走 AI Gateway unified billing（§7.7）。Clef 系列走 Workers AI neurons。
- [x] ~~目前 `ListCategories` 實際有幾個 category？~~
      → 共 21 個：16 個公開分類、3 個 AI 專用、2 個已停用（🚧），見 §7.1。
- [ ] Ground truth 的多標籤補齊（§7.6、§8 下一步 1）。
- [ ] Jev 的資料處理條款（<https://docs.typesafe.ai/legal.md>）是否可接受？模型頁標示 zero data retention。
- [ ] 目前每月新增 article 數（本文以 3,000 / 10,000 兩種情境估算）。
      註：2026-09 的 ES reindex 記錄顯示 `articles` index 共 **279,286** 筆（[20260914](../meetings/2026/20260914.md)），
      但這是累積值，不是流量。
- [ ] 2021 年 BERT GPU host 的實際月費與停用時間點（kb 內未記載）。
- [ ] 2025 年那份一直沒結案的 benchmark 結果是否存在？（可作為 Jev 的對照組）
- [ ] [cofacts/worker](https://github.com/cofacts/worker) repo 與 [worker#3](https://github.com/cofacts/worker/pull/3)、
      [worker#2](https://github.com/cofacts/worker/issues/2) 要關閉 / archive 還是留著？
      （url-resolver 確定維持現有 gRPC 寫法，classifier 改進 rumors-api，worker 已無待辦）
