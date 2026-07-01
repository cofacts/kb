# **Cofacts `ListArticles` 混合搜尋架構設計**

**(基於 Elasticsearch Free Version)**

## **背景與目標**

Cofacts 的 `ListArticles` API 負責處理使用者回報的可疑訊息，並在資料庫中尋找相似的現有文章。目前系統依賴 Elasticsearch 的 `more_like_this` (MLT) 查詢來進行基於 BM25 演算法的字面相似度搜尋。

為了提升對於「同義詞替換」、「換句話說」等變形訊息的召回率，我們計畫引入 **Gemini Embedding 2** 產生的 Dense Vector，並透過 Elasticsearch 的 `knn` 搜尋來進行語意比對。

**挑戰：** 由於我們使用的是 Elasticsearch 的 **Basic (Free and Open)** 版本，該版本**不支援**進階的 Retriever 功能，如 `Linear Retriever` (線性組合加權) 與內建的 `RRF` (Reciprocal Rank Fusion)。因此，我們無法直接依賴 ES 內部現成的高階演算法來完美融合 BM25 (文字) 與 kNN (向量) 的分數。

**目標：** 本文件旨在探討與設計在 ES Basic 授權限制下，如何將原有的 `more_like_this` 與新的 `knn` 搜尋有效結合，以達到類似 Hybrid Search 的效果，並評估各方案的優缺點。

## **方案一：Retriever 兩階段 \- 先「語意海選」再用「字面」加分 (推薦 ES 內建最佳解 ✨)**

**概念：** 針對長文本（如使用者回報的完整假訊息），此方案利用 ES 8.14+ 引入的 Retriever 框架。第一階段先使用 `knn` (Gemini Embedding) 進行全庫「語意海選」，快速篩選出概念或語境相似的 Top N 篇文章。第二階段再利用 `Rescorer Retriever` (或傳統 `rescore` 區塊)，針對這 N 篇文章執行 `more_like_this` 查詢。如果文章中包含與原查詢高度重疊的關鍵字（如特定人名、地名），則給予額外的分數加成。

**優勢：**

* **抗變形能力強：** Gemini Embedding 作為第一關，能有效抵抗同義詞替換或錯別字，避免因關鍵字未命中而提早被淘汰。  
* **效能優異：** 複雜的 `more_like_this` 查詢僅需對 Top N (例如 200\) 筆結果執行，大幅降低 CPU 負擔。  
* **精準度提升：** 第二階段的 MLT 能確保真正包含關鍵字的文章被推升至排序頂端。

### **1-A. 使用 Retriever 語法 (ES 8.14+ 推薦寫法)**

這是一種結構更現代、模組化的寫法。

```javascript
POST /articles/_search
{
  "retriever": {
    "text_similarity_rescorer": {
      "retriever": {
        "knn": {
          "field": "embeddings",
          "query_vector": [0.1, 0.2, 0.3, ...], // Gemini 產生的向量
          "k": 200,                             // 第一階段保留 200 筆
          "num_candidates": 1000                // kNN 搜尋候選數量
        }
      },
      "rescore_query": {
        "more_like_this": {
          "fields": ["text"],
          "like": "使用者傳來的一大段可疑訊息...",
          "min_term_freq": 1,
          "max_query_terms": 25
        }
      },
      "window_size": 200,                       // 針對前 200 筆重新計分
      "score_mode": "total",                    // 分數合併方式：相加
      "query_weight": 1.0,                      // kNN 原始分數權重
      "rescore_query_weight": 2.0               // MLT 加成分數權重 (需微調)
    }
  },
  "_source": ["id", "text"]
}
```

### **1-B. 使用傳統 Rescore 區塊**

如果 ES 版本較舊 (8.14 以下) 但支援 knn 與 rescore，可使用此寫法。

```javascript
POST /articles/_search
{
  "query": {
    "knn": {
      "field": "embeddings",
      "query_vector": [0.1, 0.2, 0.3, ...],
      "num_candidates": 1000
    }
  },
  "rescore": {
    "window_size": 200,
    "query": {
      "rescore_query": {
        "more_like_this": {
          "fields": ["text"],
          "like": "使用者傳來的一大段可疑訊息...",
          "min_term_freq": 1,
          "max_query_terms": 25
        }
      },
      "query_weight": 1.0,
      "rescore_query_weight": 2.0
    }
  },
  "_source": ["id", "text"]
}
```

## **方案二：使用 `bool > should` 同時查詢 (ES 8.12+ 語法)**

**概念：** 在 ES 8.12+ 中，`knn` 已經可以直接作為標準 `query` 的一部分。我們將 `more_like_this` 和 `knn` 同時放入一個 `bool` 查詢的 `should` 陣列中。這代表 ES 會分別計算文字相似度與向量相似度，並將兩者的分數相加。

**優勢：**

* **架構最單純：** 單一查詢邏輯，一次 Request 聯集 (Union) 所有結果。  
* **無漏網之魚：** 不論是單純字面命中或單純語意命中，都有機會出現在結果中。

**缺點與挑戰：**

* **分數打架嚴重 (Score Normalization Issue)：** `more_like_this` 的 BM25 分數範圍極大（可能從數十到上千），而 kNN 的 Cosine Similarity 轉換後的分數通常較小且有上限。這極易導致 BM25 分數完全壓過 kNN 分數，使得向量搜尋形同虛設。需要耗費大量時間反覆測試與手動微調 `boost` 值。

### **Query 範例**

```javascript
POST /articles/_search
{
  "query": {
    "bool": {
      "should": [
        {
          "more_like_this": {
            "fields": ["text"],
            "like": "使用者傳來的一大段可疑訊息...",
            "min_term_freq": 1,
            "max_query_terms": 25,
            "boost": 0.1  // 極力壓低 BM25 的影響力
          }
        },
        {
          "knn": {
            "field": "embeddings",
            "query_vector": [0.1, 0.2, 0.3, ...],
            "num_candidates": 100,
            "boost": 5.0  // 放大 kNN 的影響力
          }
        }
      ]
    }
  },
  "_source": ["id", "text"]
}
```

## **方案三：應用程式層實作 RRF (Client-side RRF)**

**概念：** 既然 Elasticsearch Free 版不提供自動分數合併機制，且分數正規化 (Normalization) 非常困難，我們將計分邏輯移至 Backend (Node.js 層)。此方案放棄使用絕對分數，改採 **RRF (Reciprocal Rank Fusion，倒數排名融合)** 演算法，僅依賴兩次獨立查詢的「排名」來計算最終得分。

**作法：**

1. 在 Backend 中，使用 `_msearch` 同時對 ES 發出兩個獨立的查詢：一個純 `more_like_this`，一個純 `knn`。  
2. 分別取得兩者的前 N 筆結果（例如各 Top 60）。  
3. 在 Backend 程式碼中套用 RRF 公式：`Score = 1 / (k + rank)` （常數 k 預設通常為 60）。  
4. 將兩份結果依據新算出的 RRF 分數進行合併與排序，回傳給前端。

**優勢：**

* **最穩定可靠：** 完全避開 BM25 與 kNN 分數基準不同的正規化泥淖。  
* **業界標準：** RRF 是目前處理混合搜尋最主流且效果公認良好的演算法。  
* **靈活性高：** 可在 Node.js 中自由調整 RRF 常數 `k`，或加入其他業務邏輯權重。

**缺點：**

* **實作成本：** 需要修改 Backend 查詢邏輯（例如 `src/graphql/dataLoaders/searchResultLoaderFactory.js`），並增加陣列操作的運算。  
* **網路傳輸：** 若需合併大量資料，可能微幅增加 ES 至 Backend 間的傳輸量。

### **Query 範例 (使用 `_msearch`)**

```javascript
POST /articles/_msearch
{}
{"query": {"more_like_this": {"fields": ["text"], "like": "可疑訊息..."}}, "size": 60}
{}
{"query": {"knn": {"field": "embeddings", "query_vector": [0.1, ...], "num_candidates": 100}}, "size": 60}
```

### **Node.js 虛擬碼實作概念**

```javascript
// 假設 ES 回傳的結果
const mltResults = esResponse.responses[0].hits.hits;
const knnResults = esResponse.responses[1].hits.hits;

const k = 60;
const rrfScores = new Map(); // 記錄 documentId 及其 RRF 分數

// 處理 MLT 結果
mltResults.forEach((hit, index) => {
  const rank = index + 1;
  const score = 1 / (k + rank);
  rrfScores.set(hit._id, score);
});

// 處理 kNN 結果
knnResults.forEach((hit, index) => {
  const rank = index + 1;
  const score = 1 / (k + rank);
  
  if (rrfScores.has(hit._id)) {
    // 若該文件在 MLT 也出現，則分數相加
    rrfScores.set(hit._id, rrfScores.get(hit._id) + score);
  } else {
    rrfScores.set(hit._id, score);
  }
});

// 將 Map 轉換回 Array 並依 RRF 分數排序
const finalResults = Array.from(rrfScores.entries())
  .map(([id, score]) => ({ id, score }))
  .sort((a, b) => b.score - a.score);

// 最終可依序撈取對應的文章資料
```

## **總結與建議**

| 方案 | 複雜度 | ES 運算負擔 | 精準度/穩定性 | 推薦情境 |
| ----- | ----- | ----- | ----- | ----- |
| **一：Retriever 兩階段** | 中 | 低 | 高 | **首選 (ES 內建)。** 適合希望盡量由 ES 處理邏輯，且重視效能的情境。 |
| **二：bool should** | 低 | 中 | 低 (分數難調) | 備案。除非確定可以找到完美的 boost 比例，否則不建議。 |
| **三：Client-side RRF** | 高 (需改 Code) | 中 | **最高** | **終極防線。** 若方案一的排序效果不如預期，建議直接改用此方案，穩定性最佳。 |

**下一步建議：** 由於 Cofacts 的查證訊息通常較長，強烈建議先在 Staging 環境實作 **方案一 (先語意海選，再字面加分)**。透過實際的假訊息資料進行 A/B Testing，觀察召回率與排序是否符合預期。若遭遇效能瓶頸或排序異常，再評估切換至 **方案三 (Client-side RRF)**。

