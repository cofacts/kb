---
type: DesignDoc
title: "影音（VIDEO / AUDIO）thumbnail 與 preview 產生流程"
resource: "https://github.com/cofacts/kb/blob/main/src/technical-design/video-audio-thumbnail-preview.md"
tags: [cofacts, design-docs, technical-design, rumors-api, multimedia]
timestamp: "2026-11-13T20:00:00+08:00"
---

# 影音（VIDEO / AUDIO）thumbnail 與 preview 產生流程

> [!NOTE]
> **狀態：初稿（2026-11-10），2026-11-13 補充查證並改為方案 A 優先，待審查定案。** 對應 [rumors-api#326](https://github.com/cofacts/rumors-api/issues/326)（[Cofacts.ai (nDX) project](https://github.com/orgs/cofacts/projects/12)，第三階段）。審查定案前不寫實作程式碼。
>
> 本文所有數字標明來源。沒有親眼看到、或查不到的內容，一律標為「**待確認**」，並在 §11 列出誰能回答。

## 1. 背景與目標

`Article.attachmentUrl` 目前只有 IMAGE 有 `THUMBNAIL` 與 `PREVIEW` 變體。VIDEO 與 AUDIO 只有 original，而 original 只給登入的網站使用者。因此未登入時，文章列表中的影片與聲音訊息沒有任何圖可以顯示。cofacts.ai 的列表頁票 [cofacts/ai#183](https://github.com/cofacts/ai/issues/183) 已把這件事排除在範圍外，並寫明 #326 完成前，未登入時列表中的影片只能顯示「尚未登入」。

本文要決定四件事：

1. 用哪個方案產生 thumbnail 與 preview（§4）。
2. thumbnail 與 preview 的尺寸、格式與型態（§5）。
3. 未登入者能拿到什麼，不能拿到什麼（§6）。
4. 成本與既有檔案的補產（backfill）策略（§8、§9）。

**限制：不得在 rumors-api 的 API server 內用 ffmpeg 轉檔。** 這個做法已評估並放棄，原因是 CPU 飆高（[rumors-api#334 的關閉說明](https://github.com/cofacts/rumors-api/pull/334)：「After testing, we conclude that this adds too much load to the server and should not be merged.」）。

**不在範圍：** 網站前端 UI、LINE bot 的程式修改、影片逐字稿與內容分析。

**受影響但不用改程式的 client：** LINE bot。它已經會查詢 VIDEO 與 AUDIO 的 `THUMBNAIL` 與 `PREVIEW`，rumors-api 一開始回傳 URL，聊天室與 LIFF 的呈現就會跟著改變（§2.6）。因此本文的規格必須同時符合 LINE 的限制。

## 2. 現況（已查證）

### 2.1 `attachmentUrl` 的行為

程式碼：[`src/graphql/models/Article.js`](https://github.com/cofacts/rumors-api/blob/9f1cde8/src/graphql/models/Article.js)（master `9f1cde8`，2026-10-30）。

- `variant` 參數有 `ORIGINAL`、`PREVIEW`、`THUMBNAIL`。
- 只有 `articleType === 'IMAGE'` 會對應到 `webp600w`（preview）與 `jpg240h`（thumbnail）。VIDEO 與 AUDIO 會落到 `original`。
- `original` 只在 `user.appId === 'WEBSITE'` 時回傳，其他情況回傳 `null`。
- 回傳的是 GCS V4 signed URL，有效期限進位到「從現在起 1 天後的當日零時」，讓同一天內的 URL 穩定、方便快取。這裡的零時是 UTC，即台灣時間早上 8 點（`Math.ceil(Date.now() / 86400000)`）。
- resolver 不檢查變體檔案是否存在，只負責簽名。

**線上實測（2026-11-10，匿名呼叫 `https://api.cofacts.tw/graphql`）：**

| 查詢 | 結果 |
| --- | --- |
| VIDEO 文章的 `attachmentUrl(variant: THUMBNAIL)` | `null` |
| IMAGE 文章的 `attachmentUrl(variant: THUMBNAIL)` | GCS signed URL，路徑形如 `storage.googleapis.com/cofacts-media-collection/production/image/<hash1>/<hash2>/jpg240h?...&Expires=...&Signature=...` |
| IMAGE 文章的 `attachmentUrl(variant: ORIGINAL)` | `null` |

這確認了兩件事。第一，未登入者目前就能拿到 IMAGE 的 thumbnail，所以 VIDEO 與 AUDIO 照同一套機制即可，不用新增權限模型。第二，bucket 名稱是 `cofacts-media-collection`，檔案放在 `production/` 前綴下。

### 2.2 檔案儲存與 media entry 的資料結構

media entry 在 Elasticsearch 與 DB 裡沒有任何紀錄。它是 GCS 上的一個「目錄」，由 [`@cofacts/media-manager`](https://github.com/cofacts/media-manager)（rumors-api 目前使用 `^0.4.0`）管理。

- 路徑：`${GCS_MEDIA_FOLDER}${type}/${hashes.join('/')}/${variant}`。
- 影片與音訊的 `hashes` 只有一層（`getFileIDHash`），所以路徑是 `production/video/<hash>/original`。
- `MediaEntry.id` 是 `video.<hash>`，也就是 `articles.attachmentHash` 的值。`attachmentHash` 是公開的 GraphQL 欄位。
- `MediaEntry.variants` 由列出該目錄下的檔案取得。**變體存不存在，只看 GCS 上有沒有那個檔案。**
- 上傳流程（`insert`）先寫到 `${prefix}temp/<timestamp>/<variant>`，算完 hash 後 `move` 到正式路徑。
- rumors-api 的上傳入口是 [`uploadMedia`（`src/graphql/util.js`）](https://github.com/cofacts/rumors-api/blob/9f1cde8/src/graphql/util.js)。它對 IMAGE 用 `sharp` 在串流中產生 `jpg240h` 與 `webp600w`，對其他類型只存 `original`。上傳完成後會把每個變體的 `cacheControl` 設成 `public, max-age=31536000, immutable`。
- 呼叫端有 `CreateMediaArticle`、`ListArticles` 的 `mediaUrl` 查詢（透過 `getOrUploadMedia`）、`replaceMedia` script。

新流程接在 **GCS 上 `original` 檔案建立完成之後**。rumors-api 的上傳程式不用改。

另外，rumors-api master 目前沒有任何 ffmpeg 或 fluent-ffmpeg 依賴（`package.json` 與 `src/` 中皆無）。#326 內文提到「ffmpeg is already included」是 2024 年的狀態，已過時。

### 2.3 已關閉的 rumors-api#334

[PR #334](https://github.com/cofacts/rumors-api/pull/334)「Video thumbnail」於 2024-12-16 關閉，未 merge。分支 `video-thumbnail` 仍在 origin（head `fb5362c`，12 個 commit，8 個檔案，+128 −20）。也可用 `git fetch origin pull/334/head` 取得。

它的做法，是在 `uploadMedia` 的 `getVariantSettings` 為 `MediaType.video` 回傳兩個變體，每個變體用 `fluent-ffmpeg` 從 HTTP 串流轉檔後直接寫入 GCS：

| 變體名稱 | 內容 | ffmpeg 設定 |
| --- | --- | --- |
| `av1-240p5s`（thumbnail） | 高 240、前 5 秒、2 倍速、無聲 mp4 | `libsvtav1`、`-crf 40`、`setpts=0.5*PTS`、`-movflags dash` |
| `av1-0.75x30s`（preview） | 縮到 75%、前 30 秒、聲音直接複製的 mp4 | `libsvtav1`、`-crf 38`、`-movflags dash` |

另外 `Article.attachmentUrl` 改成以 `${articleType}_${variantArg}` 做 switch。CI 也改成下載含 libsvtav1 的 ffmpeg 建置版本。

從 commit 紀錄可以讀到幾個教訓：

- 5 秒的 thumbnail 在 ffmpeg 讀完整個輸入串流之前就結束，`uploadPromise` 一度無法 resolve（commit `2974baa` 的訊息）。分支最後一個 commit 把 media-manager 升級到 `0.3.1` 以納入相關 patch。
- 它假設輸入是 mp4（`.inputFormat('mp4')`）。
- 編碼器選 SVT-AV1。壓縮率高，編碼也慢，是 CPU 飆高的合理嫌疑，但關閉說明沒有附量測數據（**待確認**）。

本文沿用它的**時間長度設定**（preview 取前 30 秒），不沿用「在 Node 程序內串流轉檔」的結構，也不沿用 AV1。

### 2.4 Penpot 中影音的呈現

來源：Penpot 檔案「Cofacts-2026 (26-10-08)」，以唯讀方式讀取，沒有修改任何東西。我讀的是各 board 的結構與尺寸，沒有逐頁目視確認（整頁匯出超過工具大小上限）。

**列表頁：**

| 位置 | 元件／board | 尺寸 | 圓角 |
| --- | --- | --- | --- |
| 文章列表卡（桌機與手機） | `Content / FactCheckCard`、`Content / DisputedMessage`、`Content / DisputedMessage-Mobile` 內的 `Rectangle 29` | **120 × 120** | 5 |
| 側欄相關訊息 | `MessagePage-1440` 內 `Frame 477` 下的 `image` | 226 × 226 | 5 |

**訊息頁：**

| 位置 | 元件／board | 尺寸 | 圓角 |
| --- | --- | --- | --- |
| 桌機，訊息內容欄 | `MessagePage-1440` 內 `content` 下的 `image 1` | **658 × 815**（欄寬 658） | 10 |
| 手機，原始訊息 | `MessagePage-原始訊息` 內 `image 1` | **303 × 435** | 10 |
| 手機，原始訊息（元件版） | `Content / OriginalMessage-Mobile` 內 `image 1` | 295 × 435 | 10 |

Penpot 中所有圖片位置填的都是同一張示意照片（600 × 815），沒有針對影片或聲音另外設計。

**Penpot 沒有的東西：** 以名稱搜尋 `play`、`播放`、`waveform`、`duration`、`時長`、`gif`、`volume` 等關鍵字沒有命中。只找到 `Doubious Message-1440` 裡的 `Base / Badge` 有「影片」與「語音訊息」兩個文字標籤。換句話說，**播放鈕、時長標示、聲音的呈現方式、preview 是否自動播放與是否靜音，設計稿都沒有**。這些列為待確認（§11），由設計師回答。

### 2.5 規模

| 項目 | 數值 | 來源 |
| --- | --- | --- |
| VIDEO 文章數 | 21,598 | `ListArticles(filter:{articleTypes:[VIDEO]}){totalCount}`，api.cofacts.tw，2026-11-10 |
| AUDIO 文章數 | 324 | 同上 |
| IMAGE 文章數 | 43,253 | 同上 |
| 全部文章數 | 276,893 | 同上 |
| 近 30 天新增 VIDEO／AUDIO | 186／4 | 同上，`createdAt >= 2026-10-11` |
| 近 90 天新增 VIDEO／AUDIO | 600／24 | 同上，`createdAt >= 2026-08-12` |
| 近 365 天新增 VIDEO／AUDIO | 3,968／188 | 同上，`createdAt >= 2025-11-10` |

新增速度約每月 200 到 330 支影片、4 到 16 個音訊。2024 年研究文件寫「9214 video / audio」（[multimedia-support](../research/multimedia-support.md)），現在已是 21,922。

`totalCount` 是否包含已封鎖或已刪除的文章，**待確認**。平均長度與 original 總容量，我沒有權限查，**待確認**（§11）。

### 2.6 LINE bot 的現況

程式碼：[cofacts/rumors-line-bot](https://github.com/cofacts/rumors-line-bot) master（2026-11-13 讀取）。

| 位置 | 查詢的變體 | 有 URL 時的呈現 | 沒有 URL 時 |
| --- | --- | --- | --- |
| 聊天室候選訊息 carousel（`src/webhook/handlers/utils.ts`，`ListArticlesInInitState` 與 `ListArticlesInProcessMedia`，後者含 `[TEXT, IMAGE, AUDIO, VIDEO]`） | `THUMBNAIL` | Flex bubble 的 hero 圖（`type: 'image'`），不看 `articleType` | 不放 hero，內文顯示較多行 |
| LIFF 文章頁（`src/liff/pages/Article.svelte` 與 `components/ArticleCard.svelte`） | `PREVIEW` | VIDEO 用 `<video controls>`，AUDIO 用 `<audio controls>` | 顯示「Preview not supported yet」 |
| LIFF 瀏覽紀錄（`components/ViewedArticle.svelte`） | `THUMBNAIL` | VIDEO 與 AUDIO 一律顯示文字，不受影響 | 同左 |

這代表三件事：

1. rumors-api 一回傳 VIDEO 與 AUDIO 的 URL，LINE bot 不用改程式就會開始顯示。
2. `THUMBNAIL` 會被放進 Flex Message 的 image 元件，必須符合它的限制（§5.1）。
3. Flex Message 是交給 LINE App 繪製的 JSON，無法像網頁的 `<img onerror>` 那樣在載入失敗時換成預設圖。URL 指向不存在的檔案時，聊天室只會出現破圖（§10）。

LINE bot 不是 `WEBSITE` client，所以 LIFF 文章頁本來就拿不到 original，只能用 `PREVIEW`。

### 2.7 #326 的討論脈絡

- [#326](https://github.com/cofacts/rumors-api/issues/326)（mrorz，2023-12）的原文：thumbnail 給「website & LINE bot list page」，preview 給「website detail before login」。需求寫的是「handle video and hopefully audio」。
- mrorz 在 2024-03-11 的留言：「ffmpeg is quite CPU intensive. New proposal is to use Transcoding API + Google cloud function that listens on GCS change.」也就是方案 A 搭配 GCS 事件觸發（§4.1）。
- 2024-03-04 會議記錄（[20240304](../meetings/2024/20240304.md)）討論過 Cloudflare Stream 與 Transcoder 兩條路線，也記下 nonumpa 的顧慮：色情影片在未登入時看不到，但預覽圖被 Google 抓到的機率更大。
- 2022-06-29 會議記錄（[20220629](../meetings/2022/20220629.md)）說明 original 只給登入者的原因之一是 GCS 對外傳輸費用。

## 3. 需求整理

| # | 需求 | 出處 |
| --- | --- | --- |
| R1 | API server 內不得跑 ffmpeg | 合約，#334 關閉原因 |
| R2 | 未登入者可取得 thumbnail 與 preview，不可取得 original | 合約 |
| R3 | 尺寸與型態要配合 Penpot 的列表頁與訊息頁 | 合約 |
| R4 | VIDEO 與 AUDIO 都要有 thumbnail 與 preview | 合約驗收標準 |
| R5 | 既有 21,922 個檔案要補產 | 合約 |
| R6 | 新上傳的檔案要自動產生 | 合約 |
| R7 | 成本要落在審查核定的範圍 | 合約 |

R4 的強度與 #326 原文不同：#326 寫的是「hopefully audio」（§2.7）。合約驗收標準是否要求 AUDIO 的 thumbnail 必須由檔案產生，或回傳固定圖示也可以，**待確認**。R3 之外，thumbnail 也要符合 LINE Flex Message 的限制（§2.6）。

## 4. 方案比較

方案 A 與 B 不跑 ffmpeg，由代管服務轉檔。方案 C 在 Cloud Run 上跑 ffmpeg，符合 R1 的字面要求（不在 API server 內），但沒有處理 #334 的根本顧慮：吃 CPU 的轉檔工作仍要由我們自己維運（§4.5）。

### 4.1 方案 A：Google Transcoder API

- **做法：** 上傳完成後建立一個 Transcoder job。輸入是 `gs://…/video/<hash>/original`，輸出寫回同一個 GCS 目錄。preview 用 job 的剪輯功能輸出 30 秒 SD mp4（計價頁範例 2 說明剪輯後只計輸出長度）。縮圖用 `spriteSheets`。
- **觸發方式有兩種：** rumors-api 在 `onUploadStop` 後直接呼叫 `createJob`（一次 API 呼叫，不吃 CPU，不需要 Cloud Run）；或 GCS 事件經 Eventarc 觸發小函式再呼叫 `createJob`。後者就是 mrorz 在 #326 提出的方向（§2.7）。
- **已知缺口：**
  - 官方 sprite 文件只描述「均勻分佈張數」與「每 n 秒一張」兩種模式，沒有說明單張指定時間點的靜態圖。要拿 poster frame 可能得用 `totalCount = 1` 的 sprite，行為**待確認**（需 PoC）。
  - sprite 依固定時間點取幀，不能像 ffmpeg 的 `thumbnail` 濾鏡那樣挑出代表幀。片頭是黑畫面時，縮圖會是黑的。
  - 輸出檔名由 mux stream 的 `fileName` 與 sprite 的 `filePrefix` 決定，sprite 會在前綴後加上流水號與副檔名。能否產出 media-manager 慣用的無副檔名變體名稱，**待確認**（§5.4）。
  - 官方文件說明可以輸出純音訊，但是否接受純音訊的輸入檔（例如 LINE 上傳的 m4a），**待確認**。不支援時，AUDIO 的 preview 也做不出來。
  - 計價頁沒有說明 sprite 與縮圖是否另外計費（**待確認**）。
  - 沒有把聲音畫成波形圖的功能。AUDIO 的 thumbnail 改為回傳 `null`（§5.2）。

### 4.2 方案 B：Cloudflare Stream

- **做法：** 把 original 複製（上傳）到 Stream，用 Stream 的 on-the-fly thumbnail URL（靜態 jpg 或 gif）與 iframe player。研究文件已寫過這個方案（[multimedia-support](../research/multimedia-support.md#video-summarization-for-thumbnails)）。
- **已知缺口：**
  - 影片必須另外存一份在 Stream（與 GCS 的 original 重複，因為 Vertex 轉錄與 embedding 仍需 `gs://` URI）。
  - 影片設為 `requireSignedURLs` 後，官方文件寫明取用 manifest 或 thumbnail 都要用 token 取代影片 ID。同一種 token 能否限縮成「只能看 thumbnail」，文件沒說（**待確認**）。若不能，匿名使用者拿到的 token 就可能連 original 播放都通。
  - 文件沒有說明 Stream 是否接受純音訊檔（**待確認**）。
  - GIF thumbnail 預設 `duration=5s`、`fps=8`，文件沒有寫出上限。研究文件的筆記說它在請求時即時生成，要數秒，輸出可能到十幾 MB（這是筆記，不是實測數據，**待確認**）。

### 4.3 方案 C：Cloud Run + GCS 事件觸發 + ffmpeg

- **做法：** GCS 在 `production/(video|audio)/*/original` 出現時，經 Eventarc 觸發一個 Cloud Run 服務。服務內以 ffmpeg 產生 thumbnail 與 preview，寫回同一個目錄。濾鏡設定取自 #334（§2.3）。
- **優點：** ffmpeg 一個工具涵蓋所有需求，包含單張 poster frame、依 Penpot 尺寸裁切、聲音波形圖（`showwavespic`）。
- **缺點：** 要自己維護容器映像、ffmpeg 版本、記憶體與逾時設定、觸發器與重試。這延續了 #334 的顧慮：轉檔移出 API server，影響範圍隔離了，但吃 CPU 的工作仍由我們維運。

### 4.4 逐項比較

成本數字的假設與來源見 §8。

| 面向 | A：Transcoder API | B：Cloudflare Stream | C：Cloud Run + ffmpeg |
| --- | --- | --- | --- |
| **成本** | 一次性補產約 US$162（影片）加 US$0.81（音訊）。之後每月約 US$2.5。每支影片 US$0.0075，與原片長度無關（輸出只算 30 秒）。sprite 是否計費待確認 | 每月儲存費，隨總分鐘數計：平均 1／3／5 分鐘分別為 US$110／325／540 每月，且隨新增影片持續上升 | 一次性補產約 US$34／69／206（每支處理 30／60／180 秒的情境）。之後每月約 US$0.5 到 3.3。處理時間待實測 |
| **延遲**（上傳到可用） | job 排隊加轉檔，數分鐘量級（文件未給 SLA，待確認）。互動模式併發上限 20、批次模式 10（每 region） | 上傳加 Stream 轉碼後才有 thumbnail，時間依影片長度，待確認 | Eventarc 派送、冷啟動、ffmpeg 處理，預估 1 到 2 分鐘內（假設，待實測） |
| **維運負擔** | 低。無伺服器、無映像。要管 job 設定、IAM、配額 | 低到中。多一個供應商帳號與計費，要管 API token、signed token、影片同步 | 中。要維護映像、ffmpeg 版本、觸發器、逾時與記憶體、dead-letter 與告警 |
| **與現有 GCP 整合** | 高。輸入輸出都是 GCS，與目前 bucket 結構相容。需啟用 API、授權 service account | 低。資料要離開 GCP。影片在兩邊各一份 | 高。同 bucket、同目錄，與 media-manager 的目錄慣例一致。需要 Cloud Run、Eventarc、Pub/Sub 權限（待確認） |
| **供應商鎖定** | 中。job 設定是 Google 專屬，但產出是 GCS 上的一般檔案，換方案時檔案可沿用 | 高。內容以 Stream 的 video UID 定址，player 與 thumbnail URL 都綁 Cloudflare | 低。ffmpeg 是開源工具，容器可搬到任何地方 |
| **失敗與重試** | job 有狀態（含失敗）可查。重試要自己重新建立 job。失敗行為文件未詳述（待確認）。API 配額：mutation 100 次每分鐘 | 轉碼失敗狀態可由 API 查。重試要重新上傳或重新抓取。細節待確認 | Eventarc 對非 2xx 回應自動重試（細節待確認）。處理程式要冪等，並對壞檔寫失敗標記以停止重試（§7.3） |
| **R1 的根本顧慮（自行維運轉檔）** | 不涉及 | 不涉及 | 仍在，只是移出 API server |
| **所需權限** | Transcoder API 與 IAM。若用 Eventarc 觸發，另需 Eventarc 與 Cloud Run functions | Cloudflare 帳號與 API token | Cloud Run、Eventarc、Pub/Sub、Artifact Registry |
| **能否滿足 R4** | VIDEO 可以。AUDIO 的 preview 待確認（純音訊輸入）。AUDIO 的 thumbnail 無波形，回傳 `null` 由前端顯示圖示 | 待確認（是否支援純音訊） | 是（`showwavespic`） |
| **規格彈性（R3）** | 受 job 設定欄位限制，單張 poster 與輸出檔名待 PoC。取固定時間點，無法避開黑畫面 | 受 Stream 的固定 URL 參數限制 | 完全可控 |

### 4.5 建議

**建議採用方案 A（Google Transcoder API），以 PoC 結果作為採用條件。PoC 未達標，或合約要求 AUDIO 的 thumbnail 必須由檔案產生（§11 #15）時，改採方案 C。不建議方案 B。**

理由：

1. **它直接處理 #334 的根本顧慮。** #334 的問題不只是拖慢 API server，而是吃 CPU 的轉檔工作要由我們自己扛。方案 C 把 ffmpeg 搬到 Cloud Run，隔離了影響範圍，但機器規格、記憶體、逾時、OOM 與壞檔重試仍由我們維運。mrorz 在 #326 面對同一個顧慮時，提的是改用代管的 Transcoder，而不是把 ffmpeg 搬到另一個服務（§2.7）。
2. **需要的權限最少，也不必另外核定。** 由 rumors-api 直接呼叫 `createJob` 時，只需啟用 Transcoder API 並設定 IAM。方案 C 需要 Cloud Run、Eventarc、Pub/Sub、Artifact Registry，而且「在 Cloud Run 上跑 ffmpeg」是否符合 R1 需要審查者確認（§11）。
3. **成本差距可以忽略。** 補產方案 A 約 US$163，方案 C 約 US$34 到 206。之後兩者每月都只有幾美元（§8.6）。
4. **方案 C 的規格優勢對使用者影響小。** C 能做、A 做不到的有兩項：
   - AUDIO 的波形縮圖。120 × 120 的語音波形彼此幾乎一樣，傳達的資訊有限。改為 THUMBNAIL 回傳 `null`，網站顯示聲音圖示，LINE bot 維持純文字（§5.2）。
   - 挑選代表幀。A 只能在固定時間點取幀，片頭是黑畫面時縮圖會是黑的。這影響品質，不影響功能，在 PoC 中統計比例。
5. **鎖定程度相同。** 兩者的產出都是 GCS 上的普通檔案，日後換方案只要改產生端，rumors-api 不用動。

必須先做 PoC，驗收線如下。任何一項不過就改採方案 C（流程見 §7.5）：

- 以 `spriteSheets` 產生單張、高 240 的 JPEG。輸出檔名要能對應到 media-manager 的變體慣例，或能在 resolver 以對照表處理（§5.4）。
- 以 production 的真實 AUDIO 檔為輸入，產生前 30 秒的 m4a。
- 用 20 支涵蓋短片、長片、直式、橫式、無 faststart 的真實 production 影片跑完整流程。全部成功，或失敗的都是壞檔。
- 從帳單確認 sprite 是否另外計費，總成本仍在 §8 的量級。

同一批影片也要統計黑畫面縮圖的比例。比例偏高時，先調整取幀時間點。

**觸發方式**由審查者決定（§11 #16）：

| 方式 | 優點 | 缺點 |
| --- | --- | --- |
| rumors-api 在上傳完成後直接呼叫 `createJob` | 權限最少，不必部署新服務 | 要改上傳流程。呼叫失敗時，由 §9 的 script 定期補上 |
| GCS 事件經 Eventarc 觸發函式，由函式呼叫 `createJob`（mrorz 在 #326 的提議） | 上傳流程不用改，Eventarc 會重試 | 需要 Eventarc 與 Cloud Run functions 的權限，多一個要部署的函式 |

兩種方式都由 §9 的 ensure-variants script 補漏，差別只在新上傳的檔案多快能拿到變體。

## 5. thumbnail 與 preview 規格

以下是依 §2.4 的 Penpot 尺寸提出的**建議值**，不是設計稿已定案的值。與設計稿有落差的地方標為待確認。

### 5.1 VIDEO

| 變體 | 型態 | 規格 | 對應的 Penpot 位置 |
| --- | --- | --- | --- |
| `jpg240h`（THUMBNAIL） | 靜態 JPEG | 高 240 px，等比縮放，不放大，品質比照現有 IMAGE 的 `jpg240h`。由 Transcoder 的 `spriteSheets` 在固定時間點取一幀（起始值 1 秒，影片更短時取第一幀），無法自動避開黑畫面（§4.1） | 列表卡 120 × 120（2 倍螢幕 240 × 240）。前端用 `object-fit: cover` 裁成方形，與 IMAGE 的處理一致 |
| `mp4-600w30s`（PREVIEW） | mp4（H.264 + AAC，moov 在檔頭以便邊下載邊播放） | 取前 30 秒（不足則全長）。寬不超過 600、高不超過 800，等比縮小，不放大。目標檔案大小約 2 MB 以下（假設）。保留聲音，AAC 64 kbps | 訊息頁欄寬 658、手機 303。寬度 600 與 IMAGE 的 `webp600w` 一致 |

**沿用 IMAGE 的 `jpg240h` 名稱**，讓 THUMBNAIL 對 IMAGE 與 VIDEO 的處理邏輯相同。

**THUMBNAIL 必須是 JPEG 或 PNG。** LINE bot 把 `THUMBNAIL` 直接放進 Flex Message 的 image 元件（§2.6）。依 [LINE Messaging API 的 OpenAPI 定義](https://github.com/line/line-openapi/blob/main/messaging-api.yml)（`FlexImage.url`），限制是：HTTPS（TLS 1.2 以上）、JPEG 或 PNG、最大 1024 × 1024 px、最大 10 MB、URL 最長 2,000 字元。`jpg240h` 符合以上全部。現行 signed URL 約 700 字元。日後若要把 THUMBNAIL 改成 webp、GIF 或短片，LINE bot 會壞，必須另開變體。

編碼選 H.264 而不是 #334 的 AV1。LIFF 文章頁會用 `<video>` 直接播放 `PREVIEW`（§2.6），執行環境是 LINE 的內建瀏覽器（iOS 為 WKWebView）。H.264 加 AAC 的 mp4 在 iOS 與 Android 都能直接播放。AV1 需要較新的裝置與系統版本，Cofacts 的使用者有許多舊手機。H.264 檔案較大，但在 §8 的假設下儲存與傳輸成本可以忽略。

編碼參數（rate control 模式、位元率或 CRF 值）在 PoC 中調整。Transcoder 輸出的 mp4 是否預設把 moov 放在檔頭，**待確認**（PoC）。

### 5.2 AUDIO

| 變體 | 型態 | 規格 |
| --- | --- | --- |
| THUMBNAIL | 不產生，resolver 回傳 `null` | 網站顯示聲音圖示。若 §11 #15 確認合約要求由檔案產生，改用方案 C 的 `showwavespic` 波形圖 |
| `m4a-30s`（PREVIEW） | m4a（AAC） | 取前 30 秒，64 kbps 單聲道，由 Transcoder 輸出純音訊。純音訊輸入是否支援，待 PoC（§4.1） |

Penpot 沒有聲音的專屬設計。列表卡 120 × 120 的聲音圖示樣式（圖示加時長，或只用「語音訊息」badge）由設計師決定，不需要後端產生檔案。

LINE 聊天室的候選訊息維持現狀：AUDIO 的 `THUMBNAIL` 是 `null`，所以不放 hero 圖，只顯示文字（§2.6）。`m4a-30s` 由 LIFF 文章頁的 `<audio controls>` 播放。

### 5.3 不採用的型態

| 型態 | 不採用的理由 |
| --- | --- |
| 動態 GIF | 檔案大（研究文件的筆記提到 Cloudflare 的 GIF 可能十幾 MB，未實測），列表頁一次載入多張時負擔過重 |
| sprite sheet | Penpot 沒有時間軸預覽的設計 |
| 5 秒 2 倍速短片當 thumbnail（#334 做法） | 列表卡是 120 × 120 的小圖，靜態圖足夠。短片要多載入與解碼，也沒有設計稿支援動態效果 |

若設計師要求列表卡有動態效果，再於 preview 之外新增變體，不影響本文其他部分。

### 5.4 變體名稱

延續現有命名慣例（`webp600w`、`jpg240h`）：

```
production/video/<hash>/original
production/video/<hash>/jpg240h
production/video/<hash>/mp4-600w30s
production/audio/<hash>/original
production/audio/<hash>/m4a-30s
```

Transcoder 的實際輸出檔名能否與上列一致，**待確認**（PoC）。sprite 一定會在前綴後加上流水號與副檔名。若檔名無法控制，就讓 resolver 以對照表把變體名稱對應到實際檔名（§10），不必另外搬移檔案。

## 6. 存取範圍

### 6.1 規則

| 變體 | 未登入者 | 登入的網站使用者（`appId === 'WEBSITE'`） |
| --- | --- | --- |
| `THUMBNAIL` | 可取得 | 可取得 |
| `PREVIEW` | 可取得 | 可取得 |
| `ORIGINAL` | **不可取得（回傳 `null`）** | 可取得 |

這與 IMAGE 目前的行為相同（§2.1 線上實測）。LINE bot 等非 WEBSITE 的 client 也會拿到 thumbnail 與 preview。這是 #326 原本的需求（thumbnail 給 LINE bot 列表），LINE bot 的程式碼也已經在查詢這兩個變體（§2.6、§2.7）。

### 6.2 儲存位置與 URL 形式

建議**沿用現有做法**：

- **儲存位置：** 與 original 同一個 bucket、同一個目錄（§5.4）。
- **URL 形式：** 與 IMAGE 相同的 GCS V4 signed URL。有效期限進位到 1 天後的當日零時，每個變體各自簽名。
- **權限控制：** 由 `Article.attachmentUrl` resolver 決定要不要簽名。只有 `ORIGINAL` 加上 `appId === 'WEBSITE'` 才會簽 original 的 URL。其他請求拿不到 original 的 URL。

### 6.3 前提：bucket 不開放匿名讀取（已查證）

上述控制只有在 **bucket 本身不開放公開讀取** 時才完整。理由是：

- `attachmentHash` 是公開的 GraphQL 欄位。
- original 的路徑可以直接由它組出來：`production/video/<hash>/original`。
- 如果 bucket 設為 allUsers 可讀，任何人都能不經 API 直接取得 original。

rumors-api 的 `.env.sample` 寫「Make data public」，與 API 回傳 signed URL 的行為矛盾，所以實測確認（2026-11-13）。以 API 取得的真實 `attachmentHash` 組出路徑，不帶簽名直接請求 `storage.googleapis.com/cofacts-media-collection/...`：

| 請求 | 結果 |
| --- | --- |
| IMAGE 的 `original` | 403 |
| IMAGE 的 `jpg240h` | 403 |
| VIDEO 的 `original` | 403 |
| 列出 `production/video/` 前綴 | 403 |

匿名使用者（allUsers）無法讀取，R2 目前已成立。allAuthenticatedUsers 是否有讀取權仍需看 IAM（`gcloud storage buckets get-iam-policy gs://cofacts-media-collection`），風險低，不阻塞實作。

### 6.4 替代方案（不建議在第一版採用）

把 thumbnail 與 preview 另外放在一個公開讀取的 bucket 或前綴，用固定、可被 CDN 快取的 URL，original 留在私有 bucket。好處是 URL 不隨每日簽名變動，CDN 命中率高，也能徹底避免 6.3 的風險。代價是要新增 bucket 與 IAM，media-manager 的單一 bucket 假設也要放寬。

流量大到傳輸成本變得明顯時，再考慮這個方案。以 §8 的估算，目前不需要。

## 7. 流程設計（方案 A）

### 7.1 概念

```
使用者上傳
  → rumors-api：media-manager 寫 temp/…/original，算 hash 後 move 到 production/<video|audio>/<hash>/original
  → 觸發（二擇一，§4.5）
      a. rumors-api 在上傳完成後呼叫 createJob
      b. GCS 事件（object finalize）→ Eventarc → 函式呼叫 createJob
  → 建立 job 前先檢查變體是否已存在，存在就跳過
  → Transcoder job
      輸入：gs://…/production/<video|audio>/<hash>/original
      輸出：同一目錄下的 thumbnail 與 preview
  → rumors-api 的 attachmentUrl 在變體存在時回傳 signed URL
```

幾個細節：

- **job 設定：** VIDEO 是一個 H.264 視訊串流加一個 AAC 音訊串流，mux 成 mp4，以 `editList` 只取前 30 秒，另加一個 `totalCount = 1`、高 240 的 JPEG sprite。AUDIO 只有 AAC 音訊串流，沒有 sprite。實際欄位在 PoC 確定。
- **Transcoder 直接讀寫 `gs://`，不經過我們的機器。** 方案 C 要處理的記憶體、暫存檔與逾時問題在這裡都不存在。Transcoder 的 service agent 需要該 bucket 的讀寫權限（§11 #1）。
- **若採 Eventarc 觸發，事件過濾必須排除 `temp/`。** media-manager 先把檔案寫在 `temp/`，`move` 後才在正式路徑出現。觸發器只比對 `production/(video|audio)/*/original`。Eventarc 路徑比對的語法與支援情況**待確認**。

### 7.2 狀態怎麼記

不新增資料庫欄位。**變體是否存在，以 GCS 上檔案是否存在為準**，與 media-manager 現在的作法一致。好處是補產、重試與日常觸發共用同一套邏輯：「缺哪個變體就補哪個」。

job 的紀錄另外放在 `variant-jobs/<video|audio>/<hash>.json`，內容是 job 名稱、建立時間與最後讀到的狀態。它不放在 `<hash>/` 目錄下，以免被 media-manager 當成變體列出。

### 7.3 失敗與重試

| 情況 | 處理 |
| --- | --- |
| `createJob` 呼叫失敗（網路、配額） | 不影響上傳。由 §9 的 script 定期補建 |
| job 仍在執行 | script 讀到 job 紀錄，且 `jobs.get` 回傳 PENDING 或 RUNNING 時跳過 |
| job 失敗（壞檔、不支援的編碼） | script 讀到 FAILED 時，在 job 紀錄寫入錯誤摘要並標記失敗。之後略過，除非加 `--retry-failed` |
| job 成功但變體不存在 | 視為 bug，寫 log 並告警 |
| 變體尚未產生完成時使用者就請求 | resolver 回傳 `null`，前端顯示 placeholder（§10） |

Transcoder 保留 job 狀態的期限**待確認**。script 的執行間隔必須短於這個期限，否則失敗的 job 會被當成從未建立而一再重建。

### 7.4 觀測

- script 每次執行輸出統計：新建、執行中、成功、失敗、仍缺變體的數量。
- 失敗數與每支 job 的處理時間寫成結構化 log，以 log-based metric 追蹤，供費用監控（交付項目：維運紀錄）。

### 7.5 若改採方案 C

PoC 未達標時，產生端換成 Cloud Run 上的 ffmpeg，其他部分（變體名稱、狀態以 GCS 為準、resolver、§9 的 script）不變：

- GCS 事件經 Eventarc 觸發 Cloud Run 服務（concurrency 1，max instances 設上限以限制花費）。服務以 ffmpeg 產生變體，以「不覆蓋」條件寫回 GCS（`ifGenerationMatch=0`），讓重複送達的事件不會重複寫入。
- ffmpeg 輸入用 signed URL 或 GCS FUSE，不要先下載整檔到 `/tmp`。Cloud Run 的檔案系統是記憶體檔案系統，下載長影片會吃掉記憶體配額。
- THUMBNAIL 改用 ffmpeg 的 `thumbnail` 濾鏡挑代表幀。AUDIO 若需要 thumbnail，用 `showwavespic` 產生波形圖。
- 壞檔寫入失敗標記並回傳 2xx 停止重試。一直失敗的事件送到 Pub/Sub dead-letter topic 並告警。
- 採用前的驗收線：20 支真實影片在 2 vCPU、2 GiB 上，每支處理時間中位數 ≤ 60 秒、p95 ≤ 180 秒，沒有 OOM。

## 8. 成本估算

### 8.1 假設

| # | 假設 | 來源 |
| --- | --- | --- |
| H1 | 既有 VIDEO 21,598、AUDIO 324 | §2.5 |
| H2 | 每月新增約 330 支 VIDEO、16 個 AUDIO（取近 365 天的平均，偏保守） | §2.5 |
| H3 | 平均影片長度未知，以 1／3／5 分鐘三種情境表示。只有方案 B 的儲存費與長度有關 | 假設，**待確認**。1 分鐘取自 2024 研究文件的估算，5 分鐘取自 [OCR 設計文件](ocr-and-ai-transcripts.md) 的上限假設 |
| H4 | preview 檔案約 2 MB、thumbnail 約 20 KB（取上限） | 假設，待 PoC 驗證 |
| H5 | 方案 C 每支處理 30／60／180 秒，2 vCPU、2 GiB | 假設，待 PoC 驗證 |
| H6 | 傳輸以 US$0.12 / GiB 估算 | 官方 Premium Tier 網際網路傳出，到亞洲（韓國與印尼除外），1 GiB 到 1,024 GiB 區間 |
| H7 | 實際請求量（列表曝光、preview 播放次數） | **查不到，待確認**。以單位成本表示，不假設總量 |

### 8.2 單價（官方，2026-11-10 查詢）

| 項目 | 單價 | 來源 |
| --- | --- | --- |
| Transcoder SD（小於 1280 × 720） | US$0.015 / 輸出分鐘 | [Transcoder pricing](https://cloud.google.com/transcoder/pricing) |
| Transcoder 純音訊輸出 | US$0.005 / 輸出分鐘 | 同上 |
| Cloudflare Stream 儲存 | US$5 / 每月每 1,000 分鐘（預付） | [Stream pricing](https://developers.cloudflare.com/stream/pricing/) |
| Cloudflare Stream 播放 | US$1 / 1,000 播放分鐘 | 同上 |
| Cloud Run（依請求計費）CPU | US$0.000024 / vCPU 秒 | [Cloud Run pricing](https://cloud.google.com/run/pricing)，Tier 1（含 asia-east1） |
| Cloud Run（依請求計費）記憶體 | US$0.0000025 / GiB 秒 | 同上 |
| Cloud Run 免費額度（依請求計費） | 每月 180,000 vCPU 秒、360,000 GiB 秒、200 萬次請求，約合 US$5.2 | 同上 |
| GCS Standard 儲存，asia-east1 | 約 US$0.02 / GiB 月（頁面列 US$0.000027397 / GiB 小時） | [Cloud Storage pricing](https://cloud.google.com/storage/pricing)。asia-east1 在頁面中出現在兩個價格群組，需以 SKU 確認（待確認，量級不影響結論） |
| GCS Class A 操作（單一 region） | US$0.005 / 1,000 次 | 同上 |
| 網際網路傳出，到亞洲，1 GiB 到 1,024 GiB | US$0.12 / GiB，每月前 1 GiB 免費 | [Network pricing](https://cloud.google.com/vpc/network-pricing) |

Cloud Run 這裡取依請求計費的單價（比 Job 與依實例計費的 US$0.000018 / vCPU 秒貴），因此是偏高的估計。

### 8.3 轉檔成本

**一次性補產（既有 21,598 VIDEO 加 324 AUDIO）：**

| 方案 | 計算 | 金額 |
| --- | --- | --- |
| A：Transcoder | 21,598 × 0.5 分鐘 × US$0.015 = US$161.99；AUDIO 324 × 0.5 × US$0.005 = US$0.81 | **約 US$163**（sprite 若另計費則更高，待確認）。短於 30 秒的影片計費較少，所以是上限 |
| B：Cloudflare Stream | 無轉檔費（ingest 與 encoding 免費）。儲存費見下 | 儲存費另計 |
| C：Cloud Run | 每支成本 = 秒數 × (2 × 0.000024 + 2 × 0.0000025) = 秒數 × US$0.000053。21,598 支 | 30 秒 US$34；60 秒 US$69；180 秒 US$206。未扣免費額度約 US$5.2 |

**每月新增（約 330 VIDEO 加 16 AUDIO）：**

| 方案 | 金額 |
| --- | --- |
| A | 330 × US$0.0075 + 16 × US$0.0025 = **約 US$2.5** |
| C | 346 × 每支成本 = 30／60／180 秒情境分別約 **US$0.55／1.1／3.3** |

### 8.4 方案 B 的儲存費

儲存費以整個影片庫的總分鐘數計價，每 1,000 分鐘 US$5 每月：

| 平均長度 | 總分鐘數（21,598 支） | 區塊數 | 每月 | 每年 | 每新增 330 支影片，每月再增加 |
| --- | --- | --- | --- | --- | --- |
| 1 分鐘 | 21,598 | 22 | US$110 | US$1,320 | US$1.65 |
| 3 分鐘 | 64,794 | 65 | US$325 | US$3,900 | US$4.95 |
| 5 分鐘 | 107,990 | 108 | US$540 | US$6,480 | US$8.25 |

這是 recurring 費用，AUDIO 若也要存則另外加上。播放費 US$1 / 1,000 分鐘另計。Cloudflare 文件寫明「檢視動畫縮圖不計入播放分鐘」，靜態縮圖是否計費文件未說（待確認）。

### 8.5 儲存與傳輸（三個方案共通，Stream 除外）

| 項目 | 計算 | 金額 |
| --- | --- | --- |
| GCS 儲存（thumbnail 加 preview） | 21,922 個 media entry × 2 MB ≈ 40.8 GiB × US$0.02 | **約 US$0.8 每月** |
| GCS 寫入操作 | 2 個物件 × 21,922 = 43,844 次 Class A × US$0.005 / 1,000 | **約 US$0.22（一次性）** |
| 傳輸：每 1,000 次 preview 播放 | 1,000 × 2 MB ≈ 1.86 GiB × US$0.12 | **約 US$0.22** |
| 傳輸：每 1,000 次 thumbnail 載入 | 1,000 × 20 KB ≈ 0.019 GiB × US$0.12 | **約 US$0.002** |

signed URL 每天換一次簽名，瀏覽器與 CDN 的快取命中會受影響，所以以上是偏高的估計。即使每月有 10 萬次 preview 播放，傳輸費也只有約 US$22。實際請求量待確認（H7）。

### 8.6 總結

| 方案 | 補產（一次性） | 每月固定成本 | 備註 |
| --- | --- | --- | --- |
| A | 約 US$163 | 約 US$3.3（轉檔 2.5 加儲存 0.8） | sprite 是否計費待確認 |
| B | 0 | US$110 到 540 加傳輸 | 持續增加 |
| C | US$34 到 206 | 約 US$1.4 到 4.1（轉檔 0.55 到 3.3 加儲存 0.8） | 處理時間待實測。未計入 Eventarc、Pub/Sub、Artifact Registry 的費用，量級預期很小，待確認 |

## 9. 既有檔案補產（backfill）

### 9.1 做法

寫一支可重複執行的 script「ensure variants」，放在 rumors-api 的 `src/scripts/`，沿用 [`backfillVertexEmbeddings.ts`](https://github.com/cofacts/rumors-api/blob/9f1cde8/src/scripts/migrations/backfillVertexEmbeddings.ts) 的模式（`getAllDocs` scroll、`cli-progress`、`--limit`、`--concurrency`、`--from`、指數退避重試）。

1. 以 scroll 走訪 `articles` 中 `articleType` 為 VIDEO 或 AUDIO 的文件。
2. 對每個 `attachmentHash` 呼叫 `mediaManager.get()`，檢查缺少哪些變體。
3. 讀取該項目的 job 紀錄（§7.2），依 §7.3 的規則更新狀態。執行中或已標記失敗的項目略過。
4. 對其餘缺少變體的項目建立 Transcoder job，並寫入 job 紀錄。
5. 輸出結果 JSONL（新建、略過、成功、失敗），讓失敗項目可以只重跑那一批。

同一支 script 也以排程定期執行（例如每日一次），負責補上日常觸發漏掉的項目，並更新 job 狀態。排程的執行環境**待確認**（§11 #14）。這樣補產、失敗重跑與新上傳共用同一套邏輯，狀態都以 GCS 為準，script 隨時中斷、隨時重跑都安全。

### 9.2 順序與節奏

- **由新到舊**（`createdAt` 降冪）。新文章最常被看到，先補。
- **用批次模式，分批送出。** 批次模式每個 region 同時執行上限 10 個 job，排隊上限 10,000 個（§4.4）。script 依排隊量分批建立 job，不要一次送出 21,922 個。日常上傳若用互動模式，兩者不會互相搶配額（此行為待確認）。
- **先用 `--limit 50` 小批次驗證**設定與輸出，再放大。
- **預估時間**（21,922 項）：

| 每個 job 的處理時間 | 同時 10 個（批次模式） | 同時 20 個（若申請提高配額） |
| --- | --- | --- |
| 1 分鐘 | 約 37 小時 | 約 18 小時 |
| 2 分鐘 | 約 73 小時 | 約 37 小時 |
| 5 分鐘 | 約 183 小時（7.6 天） | 約 91 小時（3.8 天） |

估算式：項目數 × 每個 job 的分鐘數 ÷ 同時執行數。處理時間待 PoC 實測，配額能否提高待確認。

### 9.3 驗收

- script 結束後統計仍缺變體的項目數與標記失敗的數量，附在維運紀錄中。
- 抽樣 50 支，人工確認 thumbnail 與 preview 內容正確（含直式影片、無聲影片、極短影片），並記下黑畫面縮圖的比例。

### 9.4 若改採方案 C

script 的步驟 3 與 4 改為呼叫 Cloud Run 服務（與日常事件觸發使用同一個處理端點），失敗狀態改讀 §7.5 的失敗標記。併發改由 Cloud Run 的 max instances 限制。其餘邏輯不變。

## 10. rumors-api 的變更範圍

主要動 `Article.attachmentUrl` 與周邊。觸發方式若選「rumors-api 直接呼叫」（§4.5），上傳流程也要改。

| 檔案 | 變更 |
| --- | --- |
| `src/util/mediaManager.js` | 新增常數 `VIDEO_THUMBNAIL`、`VIDEO_PREVIEW`、`AUDIO_PREVIEW`，值為 §5.4 的變體名稱，或 Transcoder 的實際輸出檔名（PoC 決定）。AUDIO 沒有 THUMBNAIL |
| 上傳流程（只在選擇直接呼叫時） | VIDEO 與 AUDIO 上傳完成後呼叫 `createJob`，失敗只寫 log，不影響上傳結果。新增 `@google-cloud/video-transcoder` 依賴 |
| `src/graphql/models/Article.js` | `attachmentUrl` 改以 `${articleType}_${variant}` 查表（如同 #334）。`PREVIEW` 與 `THUMBNAIL` 的 GraphQL 描述改成涵蓋 VIDEO 與 AUDIO |
| 同上 | **只在變體檔案存在時才回傳 URL，否則回傳 `null`。** 目前 resolver 不檢查檔案是否存在。VIDEO 與 AUDIO 的變體會晚於 original 才出現，簽出不存在的 URL 會得到 404 |
| 檢查檔案存在的方式 | 用 DataLoader 批次，key 為 `attachmentHash + variant`，並快取結果（存在的結果可長快取，不存在的結果短快取）。GCS 的 metadata 讀取是 Class B 操作，US$0.0004 / 1,000 次。**這項是必要的。** 網站可以用 `<img onerror>` 退回 placeholder，但 LINE bot 的 Flex Message 沒有這種機制，URL 指向不存在的檔案時聊天室會出現破圖（§2.6）。壞檔永遠不會有變體，所以這不只是產生期間的短暫問題 |
| `src/graphql/__tests__`、schema 文件 | 補單元測試，更新 schema 與文件 |
| `src/scripts/` | 新增 §9 的 ensure-variants script |

另外：

- Transcoder job 設定、script 的排程執行環境，以及 Eventarc 函式（若採用）放在哪裡，**待確認**。
- rumors-api 不需要 ffmpeg，CI 也不需要 #334 當時換過的 ffmpeg 建置版本。單元測試 mock GCS 與 Transcoder 的 client，端對端的產生流程在 PoC 與 staging 驗證。

## 11. 待確認事項與風險

下表列出還沒有答案的問題，以及誰能回答。標示「阻塞」的項目，沒有答案就不能進入實作。由誰在何時處理，另以 GitHub issue 追蹤，不記在本文。

| # | 項目 | 為什麼重要 | 誰能回答 | 阻塞 |
| --- | --- | --- | --- | --- |
| 1 | **GCP 權限：** 啟用 Transcoder API、建立 job 的 IAM 角色、Transcoder service agent 對 bucket 的讀寫權限。若用 Eventarc 觸發，另需 Eventarc 與 Cloud Run functions。若改採方案 C，另需 Cloud Run、Eventarc、Pub/Sub、Artifact Registry | 方案 A 的前提。**尚未向 Johnson 確認，本文不假設已具備** | Johnson | 是 |
| 2 | bucket `cofacts-media-collection` 是否公開可讀 | **已查證（2026-11-13）：匿名請求一律 403**，R2 已成立（§6.3）。剩 allAuthenticatedUsers 需看 IAM | 有 GCP IAM 權限的人（Johnson） | 否 |
| 3 | 審查者是否核定「在 Cloud Run 上跑 ffmpeg」 | 只在改採方案 C 時需要。合約只排除 API server 內轉檔，沒有明文允許 Cloud Run | Johnson | 否 |
| 4 | PoC 結果：能否輸出單張 JPEG 縮圖並控制檔名、是否接受純音訊輸入、20 支真實影片的成功率與 job 處理時間、sprite 是否計費、job 狀態保留多久、黑畫面縮圖的比例 | 決定方案 A 能否採用（§4.5 驗收線），以及 §9 的時間 | 方案 A 的 PoC | 是 |
| 5 | bucket 所在的 region | 影響 Transcoder（改採 C 時為 Cloud Run 與 Eventarc）的區域選擇與跨區傳輸費 | 有 GCP 權限的人 | 否 |
| 6 | 既有 VIDEO 與 AUDIO 的平均長度與 `original` 總容量（`gcloud storage du`） | H3 的實際值。只影響方案 B 的成本與 job 處理時間 | 有 GCP 權限的人 | 否 |
| 7 | 實際流量：列表頁曝光、訊息頁 preview 播放次數 | H7。目前只有單位成本 | GA4 或日誌的管理者 | 否 |
| 8 | Penpot 沒有影片與聲音的專屬設計：播放控制、時長標示、聲音（波形或圖示）、preview 是否自動播放與靜音、載入中 placeholder | §5 的規格是依通用圖片位置推出的建議 | 設計師（Penpot 檔案維護者） | 否，但影響 AUDIO 規格 |
| 9 | LINE bot 與其他非 WEBSITE client 取得 thumbnail 與 preview 是否合適 | **已釐清：** #326 原文即要求 thumbnail 給 LINE bot 列表，LINE bot 也已在查詢這兩個變體（§2.6、§2.7） | | 否 |
| 10 | AV1 vs H.264 | **已決定用 H.264**：LIFF 在 LINE 內建瀏覽器以 `<video>` 播放 preview（§5.1）。#334 用 AV1 的理由與 CPU 量測數據沒有留下 | | 否 |
| 11 | `ListArticles` 的 `totalCount` 是否包含已封鎖或已刪除的文章 | §2.5 的檔案量可能略高估 | rumors-api 維護者 | 否 |
| 12 | 若改採方案 C：ffmpeg 在 Cloud Run 的處理時間、記憶體、輸出大小；Eventarc 路徑比對與重試行為 | 方案 C 的可行性（§7.5 驗收線）與 §8 的數字 | 方案 C 的 PoC | 否 |
| 13 | 方案 B 的 token 能否限縮成只能存取 thumbnail、是否支援純音訊、靜態縮圖是否計費 | 方案 B 的存取控制與成本 | 實作者（Cloudflare 文件或試用帳號） | 否 |
| 14 | job 設定、script 的排程執行環境、Eventarc 函式（若採用）放在哪個 repo | 決定部署方式與維運紀錄的位置 | Johnson | 否 |
| 15 | 合約驗收標準是否要求 AUDIO thumbnail 由檔案產生，或前端圖示即可 | #326 原文是「hopefully audio」，與 R4 的強度不同（§3）。若要求由檔案產生，方案 A 做不到，須改採 C | Johnson | 否，但可能改變 §4.5 的結論 |
| 16 | 觸發方式：rumors-api 直接呼叫 `createJob`，或 Eventarc 加函式 | §4.5 的兩種做法，影響上傳流程是否要改與所需權限 | mrorz、Johnson | 否 |

**已辨識的風險：**

- **處理時間或配額不足：** 補產時間會拉長（§9.2）。對策是批次模式分批送出，必要時申請提高配額。
- **壞檔：** LINE 與使用者上傳的影片格式不一。對策是 job 失敗標記與告警（§7.3）。
- **補產的花費：** Transcoder 依輸出分鐘計費，總額上限約 US$163 加上 sprite 費用（§8.3），沒有執行個體數量失控的問題。仍先用 `--limit 50` 驗證設定（§9.2）。
- **黑畫面縮圖：** 固定時間點取幀可能取到片頭黑畫面。對策是在 PoC 與補產抽樣時統計比例，必要時調整取幀時間點。
- **LINE bot 出現破圖：** resolver 若回傳不存在的檔案，Flex Message 無法退回預設圖。對策是 §10 的存在檢查。
- **公開預覽的內容風險：** 未登入者與搜尋引擎都能取得 thumbnail 與 preview。30 秒的 preview 對多數短片而言接近全片，可能包含不當內容（§2.7 nonumpa 的顧慮）。IMAGE 的 thumbnail 與 preview 已有同樣情況，本文沿用現行做法，是否需要額外對策待審查者決定。

## 12. 參考資料

**內部：**

- [Cofacts multimedia support research](../research/multimedia-support.md)（Video summarization for thumbnails、Cloudflare Stream、Google transcoding API 各節）
- [Cofacts media manager implementation](media-manager.md)
- [OCR and AI transcripts](ocr-and-ai-transcripts.md)
- [rumors-api#326](https://github.com/cofacts/rumors-api/issues/326)
- [rumors-api#334](https://github.com/cofacts/rumors-api/pull/334)（分支 `video-thumbnail`，head `fb5362c`）
- [cofacts/ai#183](https://github.com/cofacts/ai/issues/183)（Phase 3 / Track 1 列表、篩選與搜尋）
- [Cofacts.ai (nDX) project](https://github.com/orgs/cofacts/projects/12)
- [rumors-line-bot](https://github.com/cofacts/rumors-line-bot)：`src/webhook/handlers/utils.ts`、`src/liff/pages/Article.svelte`、`src/liff/components/ArticleCard.svelte`、`src/liff/components/ViewedArticle.svelte`
- 會議記錄：[20220629](../meetings/2022/20220629.md)（GCS 圖片對外）、[20240304](../meetings/2024/20240304.md)（Thumbnails for video and audio）

**官方文件與定價（2026-11-10 查詢）：**

- [Transcoder API pricing](https://cloud.google.com/transcoder/pricing)
- [Transcoder API quotas](https://docs.cloud.google.com/transcoder/quotas)
- [Transcoder API：產生 sprite sheet](https://docs.cloud.google.com/transcoder/docs/how-to/generate-spritesheet)
- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Cloud Storage pricing](https://cloud.google.com/storage/pricing)
- [Network pricing](https://cloud.google.com/vpc/network-pricing)
- [Cloudflare Stream pricing](https://developers.cloudflare.com/stream/pricing/)
- [Cloudflare Stream：thumbnails](https://developers.cloudflare.com/stream/viewing-videos/displaying-thumbnails/)
- [Cloudflare Stream：signed URLs](https://developers.cloudflare.com/stream/viewing-videos/securing-your-stream/)
- [LINE Messaging API OpenAPI 定義](https://github.com/line/line-openapi/blob/main/messaging-api.yml)（`FlexImage`，2026-11-13 查詢）
