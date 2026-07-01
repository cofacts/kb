# **支援 Gemini Embedding 2 與 ES9 混合搜尋架構**

## **1\. 背景與目標 (Background & Objectives)**

根據《[針對 Cofacts 多模態查核資料庫之 Gemini Embedding 2 與 Elasticsearch 9 混合搜尋架構評估報告](?tab=t.tmt65uvfpaek#heading=h.50am5vq07luy)》，結合密集向量搜尋 (Dense Vector Search) 與稀疏關鍵字搜尋 (Sparse Keyword Search, BM25) 的混合搜尋架構能顯著提升檢索準確率。

本設計文件說明如何在 `rumors-api` 中實作此架構。主要目標包含：

1. **模型整合：** 透過 Google Cloud Vertex AI 呼叫 `gemini-embedding-2-preview` 模型。該模型原生支援多模態輸入。  
2. **長影音分段處理：** 針對影片或長音訊，實作分段策略以突破模型的長度限制，單一訊息可能對應多個 Embedding。  
3. **寫入路徑 (Write Path)：** 當新增或更新 Article/Reply 時，將文字或多媒體分段轉換為 Embeddings 陣列，並存入 Elasticsearch 9。  
4. **讀取路徑 (Read Path)：** 在搜尋 API 中，運用 ES9 最新推出的 **Linear Retriever** API，進行多向量 Max Score 比對與 BM25 的線性組合排序。透過參數設計讓客戶端彈性決定是否啟用語意搜尋以節省資源。  
5. **快取機制 (Caching)：** 重用現有基於 `docId` 的 `AIResponses` 架構，快取已生成的 Embedding，避免在搜尋與寫入時重複呼叫 API。  
6. **歷史資料回填 (Backfill)：** 提供腳本為舊有資料補齊 Embeddings。

## **2\. 系統架構變更 (Architecture Changes)**

### **2.1 依賴服務**

* **Google Cloud Vertex AI:** 使用 `gemini-embedding-2-preview` 模型產生向量 (預設維度：3072)。  
* **Elasticsearch 9:** 負責儲存並檢索 `dense_vector`。

### **2.2 Elasticsearch Mapping 更新 (需於 `rumors-db` 同步修改)**

為支援長影音分段產生的**多個 Embedding**，Elasticsearch 的 `articles` 與 `replies` mapping 需有能力儲存向量陣列。此外，`airesponses` mapping 也需擴充以支援快取 Embedding。

**1\. `articles` / `replies` Mapping 更新 (Nested Documents)：** 建議採用 `nested` 架構，精確控制每個分段的 `knn` 查詢，並記錄片段的時間區間以利前端在命中時標示或跳轉播放：

```ts
{
  "properties": {
    "embeddings": {
      "type": "nested",
      "properties": {
        "vector": {
          "type": "dense_vector",
          "dims": 3072,
          "index": true,
          "similarity": "cosine"
        },
        "startOffsetSec": { "type": "integer" },
        "endOffsetSec": { "type": "integer" }
      }
    }
  }
}
```

**2\. `airesponses` Mapping 更新 (Cache Storage)：** 為了避免將龐大的 JSON 陣列直接塞入會被 Tokenize 的 `text` 欄位中，建議在 `airesponses` index 新增不參與全文檢索的物件欄位，專門用來存放快取特徵：

```ts
{
  "properties": {
    "embeddings": {
      "type": "object",
      "enabled": false // 僅作為 Storage 使用，不參與搜尋索引，節省資源
    }
  }
}
```

## **3\. 實作細節與修改範圍 (Implementation Details & Where to Change)**

### **3.1 建立 Embedding Client 與快取封裝 (`createEmbedding`)**

我們將仿照 `createTranscript` 的模式，建立一個 `createEmbedding` 方法。

* **修改 / 新增檔案：**  
  1. `src/graphql/models/AIResponseTypeEnum.js`  
  2. `src/util/vertexAI.ts` (或相應工具檔)  
* **實作重點：**  
  1. **擴充 Enum：** 在 `AIResponseTypeEnum` 新增 `EMBEDDING` 類型。  
  2. **實作核心方法 `createEmbedding(queryInfo, parts, durationSec?)`**：  
     * **Cache Check:** 首先以傳入的 `queryInfo.id` 與類型 `EMBEDDING` 查詢 `airesponses`。若命中快取，直接回傳 `airesponse.embeddings`。  
     * **API Call:** 若無快取，呼叫 Vertex AI SDK `generateEmbeddings`。影片/音訊處理依照 `durationSec` 使用 `startOffsetSec`/`endOffsetSec` 迴圈分段請求。  
     * **Cache Save:** 取得 `number[][]` 後，建立一筆 `AIResponse` 記錄存入 Elasticsearch (欄位為 `type: 'EMBEDDING'`, `docId: id`, `embeddings: <陣列資料>`)。  
     * **Return:** 回傳算好的陣列。

### **3.2 寫入路徑：建立與更新資料 (Mutations)**

將產生的多個 Embeddings 存入 Elasticsearch。由於我們已封裝了 `createEmbedding`，寫入邏輯將非常精簡，且不用擔心與 Search 階段發生重複計算。

* **修改檔案：**  
  * `src/graphql/mutations/CreateArticle.js` (處理純文字)  
  * `src/graphql/mutations/CreateReply.js` (處理純文字)  
  * `src/graphql/mutations/CreateMediaArticle.js` (處理多媒體檔案)  
* **實作重點：**  
  * 準備送入 ES 的 `document` 物件前，呼叫 `await createEmbedding({ id: articleId }, parts, duration)`。  
  * 將回傳的 `number[][]` 轉換為 ES `nested` 欄位所期望的包含時間標記的格式：

```ts
// 假設分段常數為 120 秒
const CHUNK_SEC = 120;

document.embeddings = vectors.map((vec, idx) => ({
  vector: vec,
  startOffsetSec: idx * CHUNK_SEC,
  endOffsetSec: Math.min((idx + 1) * CHUNK_SEC, duration)
}));
```

### **3.3 讀取路徑：支援多片段的 Linear Retriever 混合搜尋 (Queries)**

在 `ListArticles` 中，我們將利用與 `createTranscript` 相同的流程來按需啟動 `createEmbedding`。

* **修改檔案：**  
  * `src/graphql/queries/ListArticles.js`  
  * `src/graphql/queries/ListReplies.js`  
* **實作重點：**  
  * **API 介面變更：** 1\. 在 `ListArticleFilter` 中新增可選參數 `mediaDuration` (Int, 代表媒體長度毫秒數)。 2\. 在 `ListArticleFilter` 中新增 `embedding` 欄位，包含 `shouldCreate` (Boolean)。預設為 `false`。  
  * **按需生成：** 攔截查詢。只有當 `args.filter.embedding.shouldCreate` 為 `true` 時，才啟動語意搜尋：  
    1. 取得或計算 Query 的 Hash (作為 `docId`)。若未傳入 `mediaDuration`，需透過 `fluent-ffmpeg` 在不另存檔案、用 NodeJS stream 的狀況下取得時間長度。  
    2. 呼叫 `createEmbedding({ id: hashId }, parts, duration)` 取得搜尋條件的向量陣列 (`queryVectors`)。這會自動享受到快取的好處。  
  * **ES 查詢建構：** 利用 ES9 的 `retriever` 架構將 BM25 與多片段的向量 Max Score 查詢做線性組合。  
* **GraphQL Query 範例：**

```
query SearchArticles($mediaUrl: String!, $mediaDuration: Int) {
  ListArticles(
    filter: {
      mediaUrl: $mediaUrl
      mediaDuration: $mediaDuration # [選填] 未提供時後端將透過 fluent-ffmpeg 讀取
      embedding: {
        shouldCreate: true # 啟用混合語意搜尋 (且自動觸發 AIResponses 快取)
        similarity: 0.6 # [選填] 排除相似度過低的結果
      }
    }
  ) {
    edges { node { id, text }, score }
  }
}
```

* **ES Retriever 結構範例 (Pseudo-code)：**

```ts
const nestedKnnQueries = queryVectors.map(qv => ({
  nested: {
    path: "embeddings",
    query: {
      knn: {
        field: "embeddings.vector",
        query_vector: qv,
        num_candidates: 100,
        similarity: args.filter.embedding.similarity || 0.6
      }
    },
    score_mode: "max"
  }
}));

const esQuery = {
  retriever: {
    linear: {
      retrievers: [
        {
          retriever: { standard: { query: { match: { text: queryText } } } },
          weight: 0.4 // BM25 的線性權重 W1
        },
        {
          retriever: { standard: { query: { bool: { should: nestedKnnQueries } } } },
          weight: 0.6 // Vector 的線性權重 W2
        }
      ]
    }
  }
};
```

> [!CAUTION]
> The Linear retriever is not available for free version's ES9.


### **3.4 歷史資料回填腳本 (Migration / Backfill Script)**

* **新增檔案：** `src/scripts/migrations/backfillVertexEmbeddings.ts`  
* **實作重點：**  
  * 撈取舊資料，特別針對舊有的 `MediaArticle` 取得其 GCS URI 與 Hash 值 (`docId`)。  
  * 透過 `fluent-ffmpeg` 批次獲取舊影音檔案的 `duration`。  
  * 直接呼叫 `createEmbedding` 產生特徵（會自動被寫入 `AIResponses` 快取中）。  
  * 透過 Bulk API 將取得的陣列以帶有時間標記的 `nested` 格式更新回 `articles` / `replies` ES Index 中。

### **3.5 rumors-site 與 rumors-line-bot 啟用語意搜尋**

在 rumors-site 的搜尋框與 rumors-line-bot 搜尋訊息時，其 ListArticle query 也應該加上 `filter.mediaDuration` 與 `filter.embedding.shouldCreate: true` 。

## **4\. 測試與驗證 (Verification)**

為確保新架構穩定運作，需針對受影響的現有測試進行調整，並新增對應的單元測試與整合測試。

### **4.1 對現有測試的影響 (Impact on Existing Tests)**

* **Mutations (`CreateArticle`, `CreateMediaArticle`, `CreateReply`)：**  
  * 現有的寫入測試 (如 `src/graphql/mutations/__tests__/CreateArticle.js`) 執行時，由於寫入邏輯現在會主動呼叫 `createEmbedding`，若未對 API Client 進行 Mock，將導致測試過程嘗試連線至真實的 Vertex AI 甚至逾時失敗。  
  * **處理方式：** 必須在這些測試檔的最前方新增 `jest.mock()`，模擬 `createEmbedding` (或 `vertexAI` utility) 行為，讓其回傳固定的 mock embedding 陣列，並確保 Elasticsearch Mock Client 能夠接收新的 `embeddings` nested 欄位而不報錯。  
* **Queries (`ListArticles`, `ListReplies`)：**  
  * 現有關於 `filter` 的測試 (如 `src/graphql/queries/__tests__/ListArticles.js`) 預設不會傳遞 `embedding.shouldCreate = true`，因此現有測試行為**應保持不變** (退回傳統 BM25 / Hash 比對)，這正好驗證了向後相容性 (Backward Compatibility)。

### **4.2 新增測試情境 (New Test Cases to Add)**

* **1\. Embedding Utility 測試 (`createEmbedding`)：**  
  * **Cache Hit:** 測試當 `AIResponses` 存在 `EMBEDDING` 類型的資料時，是否直接回傳該特徵且**未**呼叫 Vertex AI API。  
  * **Cache Miss & API Call:** 測試無快取時，是否正確呼叫 Vertex AI 取得陣列，並將結果存入 Elasticsearch `AIResponses` 中。  
  * **Video Chunking Logic:** 模擬一個大於 120 秒的 `durationSec`，驗證程式是否產生了多次對 Vertex AI 的 API 呼叫，且每次的 `startOffsetSec` 與 `endOffsetSec` 皆正確遞增。  
  * **Duration Fallback:** 測試當未提供 `durationSec` 參數時，是否正確呼叫了 `fluent-ffmpeg` 的 mock 函式來獲取媒體長度。  
* **2\. 寫入路徑整合測試 (Mutation Integration)：**  
  * 在 `CreateMediaArticle` 的測試中，新增一組 assert 驗證產生出來送往 ES 的 `document` 物件是否包含了正確結構的 `embeddings` 欄位 (確保 `vector`, `startOffsetSec`, `endOffsetSec` 被正確映射)。  
* **3\. 搜尋路徑整合測試 (Query Integration)：**  
  * 在 `ListArticles.js` 的測試檔中新增 `shouldCreate: true` 的測試案例。  
  * 驗證送往 Elasticsearch 的查詢是否正確被替換為包含 `retriever: { linear: { ... } }` 與 `nested knn` 的混合查詢結構。  
* **4\. 回填腳本測試 (`backfillVertexEmbeddings.ts`)：**  
  * 撰寫針對遷移腳本的測試，確保使用 ES Scroll API 取出的文章可以被正確分批 (Batching)，並轉化為 ES Bulk API 的 `_update` 指令。

## **5\. 潛在風險與考量 (Risks & Considerations)**

1. **AIResponses Index 的成長速度：** 將 Embedding 存入 `airesponses` 後，該 Index 的磁碟使用量會顯著增加。設定 Mapping 時務必針對 `embeddings` 欄位加入 `"enabled": false` 參數，確保 ES 只儲存原始 JSON 資料而不對其建立倒排索引 (Inverted Index)，以大幅節省記憶體與建置時間。  
2. **API 請求數與 Rate Limit (Quota)：** 長影片需要對 Vertex AI 發起多次 API 呼叫。在執行回填腳本或高流量時，必須實作穩健的限速 (Rate Limiting) 與重試機制。  
3. **ES 效能與 Nested Query：** 使用 `nested` 儲存影片片段，會使得 ES 內部 doc 數量倍增，`nested` query 的效能成本較高。需仔細調校 `num_candidates` 以避免過載。  
4. **儲存空間與 MRL 降維：** 預設 3072 維度加上影片分段會造成資料量暴增。建議在呼叫 Vertex AI API 時評估使用 Matryoshka Representation Learning (MRL) 降維至 768 維。

## **6\. 參考文獻 (References)**

* [Linear retriever for hybrid search (Elastic Search Labs Blog)](https://www.elastic.co/search-labs/blog/linear-retriever-hybrid-search)  
* [Elasticsearch REST APIs: Linear retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/linear-retriever)  
* [Vertex AI: Get multimodal embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-multimodal-embeddings?hl=zh-tw)  
* [LINE Messaging API Reference: Webhook event \- Video](https://developers.line.biz/en/reference/messaging-api/#wh-video)  
* [目前 rumors-api 的 createTranscript 實作](https://github.com/cofacts/rumors-api/blob/master/src/graphql/util.js#L972)
