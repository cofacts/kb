# **Cofacts Elasticsearch 9 升級與架構評估報告**

本文件基於 Cofacts 正在進行的 **Elasticsearch 9 升級**與未來的 **Hybrid Search (Gemini Embedding 2 \+ TF-IDF)** 規劃，重新評估將 ES 部署於 Elastic Cloud、升級 Linode VPS，以及 **遷移至 Google Compute Engine (GCE)** 的成本與架構效益。

## **1\. 新需求與硬體影響分析 (ES9 \+ Hybrid Search)**

導入 Google 最新發布的 Gemini Embedding 2 原生多模態模型，並在 Elasticsearch 中儲存向量以進行語意搜尋，會對硬體架構產生決定性的影響：

### **1.1 記憶體架構的改變 (HNSW 演算法)**

* 傳統 TF-IDF 主要依賴 JVM Heap (目前設定為 7GB)。  
* **向量搜尋 (Vector Search)** 底層使用 Lucene 的 HNSW Graph，這部分資料**不會**放在 JVM Heap 內，而是極度依賴作業系統的 **OS Page Cache (Off-heap Memory)**。  
* **結論**：未來的機器不僅需要足夠的 JVM Heap，還必須預留相應的 OS 記憶體給向量索引，以避免發生效能瓶頸（Thrashing）或 OOM。

### **1.2 專屬記憶體用量精確試算 (基於 Gemini Embedding 2\)**

參考資料：Cofacts.ai Design Documents \- 混合搜尋架構評估報告

在此架構下的記憶體 (OS Page Cache) 消耗試算如下：

* **單一向量大小**：3,072 維度 × 4 Bytes (Float32) ≈ 12.2 KB。  
* **資料庫總量**：約 100,000 筆多模態資料 (加上影片切割後的區塊)。  
* **純向量儲存與 HNSW 開銷**：**遠低於 2 GB**。

*架構警訊：雖然純向量開銷不到 2GB，但目前 Linode 16GB 機器光是負載現有 7GB JVM Heap、系統底層及其他容器就已頻繁 Swap。系統需要擴充至 32GB 級距，才能確保向量快取能 100% 常駐於實體記憶體中，達到毫秒級檢索。*

## **2\. 方案與每月成本比較**

為解決 Linode **無法開立台灣發票** 的行政痛點，並符合 GCP.md 中 **$250 USD/月** 的預算限制，我們納入 Google Compute Engine (GCE) 作為評估選項。

以目標 **32GB RAM** 的規格為基準，架構的比較如下 (GCP Region 皆為 asia-east1 台灣)：

### **方案 A：遷移至 Elastic Cloud on GCP (維持現有 Linode)**

* **架構**：DB 搬上 Elastic Cloud，App 留 Linode。  
* **月費預估**：$96 (Linode 16GB) \+ $250\~$300 (Elastic Cloud 15GB 級距) \= **$346 \~ $400+ / 月**  
* **結論**：直接觸發 GCP 130% 預算警報，且發票問題只解決了一半 (Linode 依然無發票)。

### **方案 B：垂直升級 Linode (All-in-One 架構)**

* **架構**：升級 Linode rumors 至 32GB，使用 Docker-compose 跑所有服務。  
* **月費預估**：**$192 / 月** (包含 640GB SSD 與高達 16 TB 的免費對外流量)。  
* **結論**：雖然 CP 值極高且絕對不會超支，但 **無法開發票** 的問題依然是致命傷，會增加 OCF 或團隊核銷的行政負擔。

### **方案 C：遷移至 GCE (僅搬遷 API/Bot/DB)**

* **架構**：退租 Linode，開一台 e2-highmem-4 (4 vCPU, 32GB RAM) 的 GCE，主站 rumors-site 維持在 Cloud Run。  
* **月費精算**：約 **\~$174 / 月** (包含運算折扣、250GB SSD 與 API 每月 215GB 的 $26 Egress 費)。  
* **結論**：完美符合 $250 預算並解決發票問題。

### **方案 D：GCE 終極大一統架構 (包含主站 rumors-site) 👑**

* **架構**：將 Cloud Run 上的 rumors-site 也一起搬進上述的 GCE 機器中。GCE 將同時負責 ES9、API、LINE Bot 與 Cofacts 主站的 SSR (Server-Side Rendering)。  
* **網路費計價原則**：Cloud Run 的 Egress 帳單顯示受惠於 Cloudflare 的 Carrier Peering 折扣，流量單價極低（約 $0.04/GB）。將網站搬回 GCE 並同樣透過 Cloudflare Tunnel 傳輸，也可延續此網路費優勢。

| 項目 (GCE asia-east1) | 說明 | 預估月費 (USD) |
| :---- | :---- | :---- |
| **運算資源 (Compute)** | e2-highmem-4 搭配 **1 年期 CUD 折扣**。 | \~$120.00 / 月 |
| **硬碟 (Storage)** | 250 GB pd-balanced (適合 DB 的平衡型 SSD)。 | \~$28.00 / 月 |
| **網路流量 (API)** | API 真實流出 (215GB)，以較保守的牌價估算。 | \~$26.00 / 月 |
| **網路流量 (Site)** | 根據過往 30 天帳單的 Carrier Peering Egress 費用累加。 | \~$14.50 / 月 |
| **GCE 大一統總支出** | **單一機器涵蓋 Cofacts 所有核心服務的總開銷**。 | **\~$188.50 / 月** |
| **💡退租 Cloud Run 省下** | 扣除原 Cloud Run 的 CPU($120)+RAM($4.3)+Req($2.4)。 | **\-$126.70 / 月** |

*財務總結：原先 (Linode $96 \+ Cloud Run $141.2 \= $237.2/月) 的分散架構，合併為 GCE 大一統架構後，整體基礎設施總花費將降至 **\~$188.5/月**！*

## **3\. 預算與營運綜合分析 (方案 D \- 大一統評估)**

### **3.1 資源收斂的巨大成本紅利 (Consolidation Bonus)**

根據 [2026/02-03 的真實 GCP 帳單](https://console.cloud.google.com/billing/017CA0-902C8B-5A26FB/reports;timeRange=LAST_30_DAYS;grouping=GROUP_BY_SKU;products=services%2F152E-C115-5142,services%2F29E7-DA93-CA13?organizationId=273083271964&project=industrious-eye-145611)，目前支付給 Cloud Run 的純運算費用（CPU/Memory/Requests）高達 **$126.7 USD/月**。

將 rumors-site 從 Cloud Run 搬回 GCE 是一個極佳的戰略。因為 e2-highmem-4 擁有 4 顆 vCPU，在應付 ES9 檢索之餘，消化 Next.js SSR 的運算需求游刃滑餘。相當於你們直接**省下這 $126.7 的運算費**，讓整個網站的運營成本趨近於「免費搭便車」。

### **3.2 Carrier Peering 的隱形流量折扣**

帳單明細中出現了 Network Data Transfer Out via Carrier Peering Network，這意味著 GCP 識別到流量是流向 Google 的合作夥伴（如 Cloudflare），因此給予了極低的頻寬費率（約 $0.04/GB，而非標準的 $0.12/GB）。

這保證了未來在 GCE 上使用 Cloudflare Tunnel 暴露服務時，大流量的網路出站費依然在絕對可控、且極度便宜的範圍內。這使得總預算遠低於 GCP 的 $250 天花板。

### **3.3 完美解決行政痛點 (開立發票)**

這是遷移至 GCE 的最大行政誘因。透過目前 GCP.md 中紀錄的帳單管道 (ocf \- ikalatv)，包含集中後的總網路費在內，所有費用都可以開立合規的台灣發票/收據供報帳核銷，徹底解決了 Linode 長期以來的核銷痛點，同時總價也低於 Linode 的同級別方案。

### **3.4 DDoS 防禦與帳單爆表風險評估**

若 Cofacts 網站或 API 遭受 DDoS 攻擊，在目前的「GCE \+ Cloudflare Tunnel」架構下，**因 DDoS 導致 GCP 帳單爆表的風險極低（接近於零）**。其防禦機制與成本隔離原理如下：

1. **實體隔離 (沒有 Public IP)**：由於使用 Cloudflare Tunnel，GCE 機器不對外暴露公開 IP。駭客無法繞過 Cloudflare 直接對 GCP 機器發動網路層級 (L3/L4) 的洪流攻擊（如 SYN Flood、UDP Flood）。這類流量會由 Cloudflare 邊緣節點完全吸收，**GCP 網路費為 $0**。  
2. **應用層攻擊 (L7 HTTP Flood) 與快取阻斷**：如果駭客發動 HTTP Get 請求轟炸：  
   * **被 Cloudflare 阻擋或快取**：根據 DevOps 文件記錄，API 已經設有 managed\_challenge 規則阻擋非人類請求。被 WAF 擋下或由 Cloudflare 直接快取回應的請求，不會產生任何 GCP 出站流量。**GCP 網路費為 $0**。  
   * **穿透攻擊 (Cache-busting)**：這是唯一可能產生費用的情境。如果駭客聰明地構造隨機查詢字串，繞過 WAF 且無法被快取，導致大量請求灌入 GCE。在這種情況下，GCE 的 CPU 通常會先滿載 (CPU 100%)，導致服務變慢或無法回應新的請求，進而形成天然的「流量天花板」。由於 GCP 網路費是算出站傳輸量 (Egress Bytes)，如果 GCE 已經因為 CPU 滿載而無法送出巨大的回應封包，網路費也不會無限制飆升。  
3. **最終防線 (預算警報)**：請確保 GCP 上的 Cofacts-OCF budget 250USD 預算警報功能正常開啟。若遭遇針對 GraphQL 耗費資源的超大型穿透攻擊，GCP 的警報能確保團隊在預算飆升前即時介入（例如在 Cloudflare 啟動 "Under Attack Mode" 或更嚴格的 Rate Limiting）。

### **3.5 COS (Container-Optimized OS) 的技術注意事項**

在架構設計中採用 COS 是非常優秀的安全實踐，但也需要注意與 DevOps 現況的相容性：

* **COS 是 Read-Only 的作業系統**：為了資安，除了特定目錄 (如 /var/lib/docker, /home)，其餘系統根目錄皆無法寫入。  
* **docker-compose 指令的改變**：COS 內建了 docker，但**沒有**內建傳統的獨立 docker-compose 二進制執行檔。根據 DevOps 文件，目前高度依賴 docker-compose 進行重啟或排程。  
* **解決方案**：  
  1. 使用較新的 docker compose CLI 外掛 (若 COS 版本支援)。  
  2. 透過別名 (alias) 執行 Docker 版本的 compose：alias docker-compose='docker run \--rm \-v /var/run/docker.sock:/var/run/docker.sock \-v "$PWD:$PWD" \-w "$PWD" docker/compose:1.29.2'。  
  3. 將設定檔放在 /home/docker/rumors-deploy，確保 volume mount 的路徑位於可寫入的分割區。

## **4\. 結論與建議執行步驟**

考量到發票需求、混合檢索的記憶體依賴，以及收斂雲端資源的**巨大成本紅利（省下 $126 運算費）**，**強烈建議採取方案 D：打造 GCE 大一統架構 (e2-highmem-4) 搭配 1-year CUD，採用 COS 集中託管 ES9、API 與 rumors-site**。

**最佳實踐：漸進式轉移與折扣鎖定**

1. **極低成本概念驗證 (PoC)**：先在 GCP 開啟一台最便宜的 COS 測試機。驗證 COS 資料夾權限設定，以及透過 Cloudflare Tunnel 啟動 docker-compose.yml 的可行性。  
2. **一鍵垂直升級 (Scale Up)**：確認 DevOps 流程能在 COS 上運作後，將機型升級為目標規格（e2-highmem-4）。  
3. **資料轉移與 API 上線**：利用 Vertex AI Batch API 將舊資料導入新版 ES9 並建立多模態向量索引。透過 Cloudflare Tunnel 切換 API 流量至 GCE。  
4. **主站回歸與鎖定折扣**：最後將 rumors-site 部署至該 GCE 的 Docker 中，並在 Cloudflare 上將網站流量導回 Tunnel。觀察 1\~2 週確認系統效能穩定後，購買 **1 年期 CUD** 鎖定長期低價，並正式關閉 Linode 與 Cloud Run 服務。
