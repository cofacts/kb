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

> [!IMPORTANT]
> 也就是說，本次要評估的 Jev **不是一個新專案，而是既有 workflow 裡 step 2 的替代實作**。
> 這讓導入成本低很多：資料集、pipeline、寫回機制、實驗場（Langfuse）都已經存在。

## 2. 現有可用資產

| 資產 | 位置 | 用途 |
|------|------|------|
| Ground truth 17K | [cofacts/ground-truth](https://github.com/cofacts/ground-truth)，已匯入 Langfuse dataset | 訂 confidence gate、算 PR 曲線 |
| Script 1 / Script 2 | `rumors-api/src/scripts/genCategoryReview.js`、`genBERTInputArticles.js` | 持續從網友 feedback 產生新 ground truth |
| `aiModel` / `aiConfidence` 欄位 | `rumors-api/src/graphql/mutations/CreateArticleCategory.js` | **已存在**，可直接寫入 Jev 的 noul 機率，不需 schema migration |
| Category feedback 機制 | `CreateOrUpdateArticleCategoryFeedback` | 線上持續回收 precision 訊號 |
| Workflow 骨架 | `cofacts/worker` PR#3 | 直接替換 step 2 |
| Langfuse | `langfuse.cofacts.tw` | 成本 / 準確率比較 |

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

### 4.1 Jev 的單價目前無法查得

Cloudflare 官方文件對 `typesafe/jev` 的 Pricing 欄位只寫
「[View pricing in the Cloudflare dashboard](https://dash.cloudflare.com/?to=/:account/ai/models/typesafe/jev)」，
**未列在 [Workers AI pricing 頁](https://developers.cloudflare.com/workers-ai/platform/pricing/) 的任何價目表中**；
本次也無法透過 API 取得（同 3.3 末項）。
Workers AI 的計價基礎為 **Neurons，$0.011 / 1,000 Neurons，每日前 10,000 Neurons 免費**。

因此以下用**參數化**方式估算，實際單價請由 mrorz 在 dashboard 確認後代入。

### 4.2 每篇訊息的 token 用量

| 項目 | 估計 |
|------|------|
| input（問題區 ~4,000 + 一般訊息本文 ~500） | **~4,500 tokens** |
| output（20 題 noul，每題僅一個機率值） | **~250 tokens** |

以官方範例反推，3 題的 output 為 41~73 tokens，20 題約 200~300 tokens，屬合理外插。

### 4.3 情境成本

用 Workers AI 現有模型的價格帶當上下界（Jev 為結構化評估模型，推測落在中低價帶）：

| 假設單價（in / out per M tokens） | 每篇成本 | 每月 3,000 篇 | 每月 10,000 篇 |
|---|---|---|---|
| $0.10 / $0.30（gemma-4 級距） | $0.00053 | **$1.6** | **$5.3** |
| $0.35 / $0.75（gpt-oss-120b 級距） | $0.00177 | **$5.3** | **$17.7** |
| $0.95 / $4.00（kimi-k2.6 級距，上界） | $0.00528 | **$15.8** | **$52.8** |

即使取最貴的情境，**每月成本在數十美元量級**。

### 4.4 與 2021 年 BERT 主機對比

2021 年的做法需要一台常駐 GPU host 跑 `rumors-ai-bert` 的 docker image。
市面上最便宜的常駐 GPU 執行個體月費也在 **USD 100~500** 量級，
且 GPU 不論有沒有訊息進來都在計費，還要加上維運與重訓練的人力。

> **Jev 方案比 2021 年的自架 GPU 便宜約 1~2 個數量級，且成本隨訊息量線性變動、閒置時為零。**
> 成本已經不是這件事的阻礙——**準確率（特別是中文表現）才是**。

另外，即使 Jev 比現行 `gemini-3-flash-preview` 方案略貴，
「原生 calibrated 機率」帶來的可調閾值能力，通常值這個價差。

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

### 6.2 建議架構：延續既有共識，不要在 rumors-api 直接呼叫 Jev

[20251111](../meetings/2025/20251111.md) 已定案「worker 提供 HTTP endpoint、rumors-api 射後不理」，
建議維持：

```
CreateArticle / CreateMediaArticle
  └─ (fire-and-forget) POST https://worker.../classify  { articleId }
        └─ Cloudflare Workflow: article-classifier
             step 1: GetArticle + ListCategories (GraphQL)
             step 2: env.AI.run('typesafe/jev', { state, questions })   ← 本次評估的替換點
             step 3: 套 per-category 閾值 → CreateArticleCategory(aiModel, aiConfidence)
```

理由：

- 重試、平行化、durable execution 由 Cloudflare Workflow 負責，rumors-api 不必處理。
- category 系列本來就與 API 拆開（2021 的 rumors-ai 即如此，[20250630](../meetings/2025/20250630.md) 也重申）。
- 未來要改成 batch 或換模型，不需動 rumors-api。

rumors-api 端需要的改動很小：

1. 新增 `util/classifyArticle.js`：一個 fire-and-forget 的 POST（帶 Cloudflare Zero Trust service token）。
2. `CreateArticle.js`：在 `newArticlePromise` resolve 後呼叫，**不加入最後的 `Promise.all`**
   （比照 `archiveUrlsFromText(text)` 的既有寫法）。
3. `CreateMediaArticle.js`：在 `writeAITranscript` 成功之後呼叫（逐字稿寫入後才有文字可分類），
   同樣包在既有的 `.catch(e => console.warn(...))` 之內。
4. 環境變數：`CLASSIFIER_WORKER_URL`、service token；未設定時整段 no-op（本地開發／測試不受影響）。

### 6.3 邊界情況

- **媒體訊息去重**：`createNewMediaArticle` 遇到相同 `attachmentHash` 會回傳既有 article，
  此時不該重複分類 → 需要能區分「新建」與「命中既有」（`CreateArticle` 已有 `result === 'created'` 可用，
  media 端需另外判斷）。
- **逐字稿失敗**：`aiResponse` 為空時 media article 的 `text` 為空字串，**不可送去分類**。
- **空文字 / 純網址訊息**：交給「只有網址其他資訊不足」這個既有分類處理，
  或在 worker 端直接短路。
- **spam / takedown**：已被下架的訊息不必分類。
- **不要阻塞 mutation**：LINE bot 的使用者在等回應，分類延遲數秒是可接受的（本來就是事後才顯示）。

## 7. 結論與建議

1. **Jev 在概念上非常適合這個任務**：N 個 noul 問題直接對應「N 個 category 的信心值」，
   原生 calibrated 機率讓 precision-recall gate 可以事後調整而不必重跑推論，
   且 `aiModel` / `aiConfidence` 欄位在 rumors-api 已經存在，落地成本極低。
2. **Context window 不是問題**：N=20 的問題區約 3.3k~5.3k tokens，
   一般訊息遠低於上限；只有超長影音逐字稿需截斷處理。**不需要分批呼叫**。
3. **成本不是問題**：即使取最保守的單價假設，每月也在數十美元以內，
   比 2021 年常駐 GPU host 便宜 1~2 個數量級。
4. **真正的風險是中文準確率**，完全未知，必須實測。

**建議的下一步（成本很低，因為基礎建設都在）：**

1. 在 Cloudflare dashboard 確認 `typesafe/jev` 在本帳號可用，並記下實際單價。
2. 用 Langfuse 上既有的 17K dataset，跑一次 Jev（N 個 noul）與現行 Gemini 大 prompt 的 A/B，
   比較 **cost、per-category PR 曲線、confusion matrix**——
   這正是 [20250630](../meetings/2025/20250630.md) 訂下的比較基準，指標不必重新發明。
3. 若 Jev 的 per-category precision 在合理 recall 下可達 0.9，
   就把 worker#3 的 step 2 換成 Jev，並補上 per-category 閾值表。
4. 最後才在 `CreateArticle` / `CreateMediaArticle` 掛上 fire-and-forget 呼叫。

## 8. 待確認事項

- [ ] `typesafe/jev` 在 Cofacts 的 Cloudflare 帳號是否已啟用？實際單價為何？（dashboard）
- [ ] 目前 `ListCategories` 實際有幾個 category（本文以 N=20 估算）？其中幾個是 AI-only？
- [ ] 目前每月新增 article 數（本文以 3,000 / 10,000 兩種情境估算）。
      註：2026-09 的 ES reindex 記錄顯示 `articles` index 共 **279,286** 筆（[20260914](../meetings/2026/20260914.md)），
      但這是累積值，不是流量。
- [ ] 2021 年 BERT GPU host 的實際月費與停用時間點（kb 內未記載）。
- [ ] [worker#3](https://github.com/cofacts/worker/pull/3) 停在哪裡？2025 年那份一直沒結案的 benchmark 結果是否存在？
- [ ] 第三方模型的資料處理條款是否可接受（<https://docs.typesafe.ai/legal.md>）。
