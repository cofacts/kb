# **Cofacts Elasticsearch v6 至 v9 升級計畫**

本計畫基於 Production GCE 擁有 32GB RAM 的硬體條件，採用「同機雙開並行遷移，後續降載升規」的策略。此方案包含事前將資料同步至 v9 並進行備份，至 Staging 進行驗證，最後於停機期間進行完整資料轉移，確保升級期間資料一致。

## **1\. 記憶體配置策略分析**

| 階段 | ES v6 記憶體 | ES v9 記憶體 | 系統可用與 FS Cache | 狀態說明 |
| :---- | :---- | :---- | :---- | :---- |
| **遷移期間** | Heap: 16GB | Heap: 8GB | \~8GB | 總 Heap 24GB，保留 8GB 給 OS 與 Lucene 快取。短期過渡不會 OOM。 |
| **遷移完畢** | 0GB (Spin down) | Heap: **16GB** | \~16GB | 完美符合 ES 官方「Heap 佔總記憶體 50%」的最佳實踐，效能最大化。 |

**注意**: JVM 的起始記憶體 (Xms) 與最大記憶體 (Xmx) 必須設定為相同數值，以避免 Heap 重新分配造成的效能停頓。

## **2\. 升級執行步驟**

### **Phase 1: 啟動雙節點與記憶體設定 (無停機)**

1. **維持 ES v6 不變**: 確認目前執行中的 v6 維持 `ES_JAVA_OPTS="-Xms16g -Xmx16g"` 繼續提供服務，不需重啟。  
     
2. **啟動 ES v9**: 在 `docker-compose.yml` 中加入 ES v9 的服務，並掛載新的 Volume 與設定 GCS Snapshot 備份外掛所需的 credential (如適用)。

```
elasticsearch-v9:
  image: docker.elastic.co/elasticsearch/elasticsearch:9.x.x # 替換為確切版本
  environment:
    - discovery.type=single-node
    - ES_JAVA_OPTS="-Xms8g -Xmx8g"
    - xpack.security.enabled=false # 依據原本 v6 安全性設定決定是否開啟
  ports:
    - "9209:9200" # 避開 v6 的 9200 port
  volumes:
    - es9data:/usr/share/elasticsearch/data
    - ./volumes/db-plugins/repository-gcs:/usr/share/elasticsearch/plugins/repository-gcs # 掛載外掛或 credential
```

3. 執行 `docker-compose up -d elasticsearch-v9`。

### **Phase 2: 執行 Schema 與第一次 Data Migration (API 正常服務中)**

此階段現有的 `rumors-api` (v6 版本) 維持正常運作，前端與使用者不會感覺到中斷。

1. 進入 `rumors-db` 目錄，確認 `.env` 指向正確的 v9 位置： `ELASTICSEARCH_URL=http://localhost:9209`  
     
2. **建立 v9 Indices (Mappings)**:

```shell
node db/migrations/202602-000-create-v9-indices.js
```

3. **執行第一次 Reindex (預載測試資料)**:

```shell
# 建議在 tmux 或 screen 中執行
bash db/migrations/202602-001-reindex-v6-to-v9.sh
```

### **Phase 2.5: v9 備份與 Staging 測試驗證 (重要)**

因 Elasticsearch v9 不支援直接復原 v6 的備份，在 Staging 測試前必須對 v9 建立獨立快照。

1. **設定 v9 Snapshot Repository (使用全新 Bucket 實體隔離)**: 確認 v9 已安裝 `repository-gcs` plugin。為避免新舊版本互相覆寫導致快照損毀，且方便未來 V6 退役時直接刪除舊 Bucket，**強烈建議在 GCS 建立一個全新的 Bucket (例如 `rumors-db-v9`)**。 建立完成並確認權限後，透過 API 替 V9 註冊專屬的儲存庫：

```shell
curl -X PUT "localhost:9209/_snapshot/gcs" -H 'Content-Type: application/json' -d'
{
  "type": "gcs",
  "settings": {
    "bucket": "rumors-db-v9"
  }
}'
```

2. **對 v9 進行備份**: 針對剛剛建立好 Schema 與第一次 Reindex 的 v9 執行 Snapshot 備份。

```shell
curl -XPUT localhost:9209/_snapshot/gcs/v9-staging-test-snapshot
```

3. **在 Staging 完整測試 (VPS.md)**:  
   - 將 Staging 的 API 升級到使用 V9 client 的程式碼版本。  
   - 將 Staging 的 Elasticsearch Container 換成 v9，並設定指向 GCS 儲存庫。  
   - 在 Staging v9 執行 Restore，把 `v9-staging-test-snapshot` 拉回 Staging。  
   - 於下週二開會時請大家測試 CRUD，確定 V9 Mappings 以及 API 都能正常運作。

### **Phase 3: 停機切換與版本升級 (Cutover Window \- 1至2小時 Downtime)**

當開會測試沒問題後，安排離峰時段進行最後的資料切換。**因為 `reindex-v6-to-v9.sh` 的 `op_type: create` 行為會遺漏既有資料的更新事件，為確保資料 100% 一致無損，停機期間須執行一次完整的 Full Reindex。**

1. **通知社群停機**: 至 **g0v Slack `#cofacts` 頻道**發布停機公告，說明預計 DB 升級維護時間 (1-2 小時)。  
     
2. **停止舊版 API 寫入 (進入 Downtime)**: 停止目前連接 ES v6 的 `rumors-api` 服務，確保不會再有新資料寫入或是舊資料被更新。

```shell
docker-compose stop rumors-api
```

3. **對 v6 做最後備份 (保險起見)**: 保留 V6 的最終完整狀態。  
     
4. **清空先前 Phase 2 同步的 v9 資料**: 清空 v9 目標 Indices，以便重新跑一次乾淨完整的 Full Reindex。 *(例如利用 API `DELETE /*-v9` 砍掉 v9 剛倒完的索引)*  
     
5. **執行最終的 Full Reindex (確保 100% 資料一致)**: 重新執行 Reindex 指令。所有文章與回覆紀錄將在此步驟完全同步至 V9。

```shell
# 確保資料為空後，重新建立 v9 索引表
node db/migrations/202602-000-create-v9-indices.js
# 完整倒灌所有資料
bash db/migrations/202602-001-reindex-v6-to-v9.sh
```

6. **拉取新版 rumors-api 映像檔**: 因為 `docker-compose.yml` 中使用 `latest` tag，**在 pull 之前必須先將目前的 v6 版本打上 tag 備份**，以免發生意外無法 rollback。

```shell
# 1. 先備份目前能存取 v6 正常運作的版本
docker tag cofacts/rumors-api:latest cofacts/rumors-api:v6-backup

# 2. 拉取已支援 ES v9 的最新版本
docker compose pull api
```

7. **DB 服務切換與擴充記憶體 (取代 v6)**: 這段過程會直接在 `docker-compose.yml` 中把 v9 扶正為唯一的資料庫服務，因此不需要去修改 API 的環境變數 (`.env`)，不僅乾淨、無縫，連 Cronjobs 也完全不用修改！  
     
   先同時停止並移除運作中的 v6 與目前的 v9 暫時容器：

```shell
docker compose stop db elasticsearch-v9
docker compose rm db elasticsearch-v9
```

   修改 `docker-compose.yml`：直接覆寫原本 `db` 服務的內容，將其改為 V9 的映像檔與環境變數設定。並將 `elasticsearch-v9` 這個區塊整個刪除。

```
db: # 維持 db 命名能確保與之前的所有服務相容 (API, Cronjobs)
  image: docker.elastic.co/elasticsearch/elasticsearch:9.x.x
  environment:
    - discovery.type=single-node
    - ES_JAVA_OPTS="-Xms16g -Xmx16g" # 直接擴滿 16GB 大記憶體
    - xpack.security.enabled=false
  # ports:
  #   - "9200:9200" # 視需求決定是否開放外部存取
  volumes:
    - es9data:/usr/share/elasticsearch/data # 掛載 v9 的資料與設定檔存放區
    - ./volumes/db-plugins/repository-gcs:/usr/share/elasticsearch/plugins/repository-gcs
```

   以 16GB 的姿態重啟 V9：

```shell
docker compose up -d db
```

   *(可使用 `docker stats` 或 `htop` 確認 v9 佔用足夠的資源)*

   

8. **啟動新版 API 並驗證**: 重啟 API，此時 `rumors-api` 就會透過原生的 `http://db:9200` 順暢連到剛剛扶正的 v9。

```shell
docker compose up -d api
```

   *內部驗證：測試前端網頁/LINE Bot，確認文章搜尋、回報、回覆功能皆正常運作。*

   

9. **宣布重新上線**: 確認一切正常後，至 **g0v Slack `#cofacts` 頻道**發布服務已恢復營運之公告。  
     
10. **🗑️ (選用) 清理 V6 舊資料**: 確認 V9 完全穩定運行數週，不再需 Rollback 時，可清除先前的 V6 Volume (`db-production`) 以釋放硬碟空間。

---

## **緊急退回策略 (Rollback Strategy)**

如果在 Phase 3 升級切換後，發生嚴重 API 不相容或資料庫效能異常，由於 V6 的資料在切換當下被完美保留，且新版資料也不會有衝突，可以依循此步驟以最快速度恢復舊版營運。

1. **緊急通報與停止服務**:  
   - 於 **g0v Slack `#cofacts` 頻道**發布緊急維修延長公告。  
   - 立即停止寫入與服務：`docker compose stop api db`  
2. **退回 API 映像檔版本**: 因為已經打上了救援 Tag (`v6-backup`)，只要將其強制覆寫回 `latest`：

```shell
docker tag cofacts/rumors-api:v6-backup cofacts/rumors-api:latest
```

   *(或者直接去 `docker-compose.yml` 將 API 的 image 暫時改成 `cofacts/rumors-api:v6-backup`)*

   

3. **退回 V6 資料庫設定檔**: 編輯 `docker-compose.yml`，將 `db` 服務的資訊完全改回 V6 的舊有狀態（包含退回 Image 與重新掛載舊有 `db-production` Volume）：

```
db:
  image: docker.elastic.co/elasticsearch/elasticsearch-oss:6.3.2
  environment:
    - "path.repo=/usr/share/elasticsearch/data"
    - "ES_JAVA_OPTS=-Xms16g -Xmx16g"
  volumes:
    - "./volumes/db-production:/usr/share/elasticsearch/data"
    - "./volumes/db-production/elasticsearch.keystore:/usr/share/elasticsearch/config/elasticsearch.keystore"
    - "./volumes/db-plugins/repository-gcs:/usr/share/elasticsearch/plugins/repository-gcs"
  restart: always
  logging:
    driver: gcplogs
    options:
      gcp-meta-id: db
      gcp-project: industrious-eye-145611
```

4. **重啟舊版系統**:  
   - `docker compose up -d db` (確認 V6 成功載入舊有資料)  
   - `docker compose up -d api`  
5. **再次驗證與結案**:  
   - 內部測試網站，確認文章等資料狀態停留在停機維護前的最後一刻。  
   - 於 **g0v Slack `#cofacts` 頻道**發布服務降級修復之公告。

