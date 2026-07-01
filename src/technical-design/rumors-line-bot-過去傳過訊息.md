---
type: DesignDoc
title: "rumors-line-bot 過去傳過訊息 implementation"
resource: "https://g0v.hackmd.io/@johnson/H1ttLtQS8"
tags: [cofacts, design-docs, technical-design]
timestamp: "2020-07-10T14:24:53+08:00"
---

---
tags: cofacts
---

# rumors-line-bot 過去傳過訊息 implementation

Past discussion: https://github.com/cofacts/rumors-line-bot/issues/133

## User story

- 作為 **Chatbot 使用者**，我希望 chatbot 可以列出我過去傳過的訊息以及回應的狀況，讓我能在有需要的時候快速翻找。
- 作為 **Chatbot 使用者**，我希望 chatbot 在我傳過的訊息有新回應的時候可以通知我，讓我接收最新的不同意見。

## Task breakdown
1. Chatbot server 需連結至新的資料庫。此資料庫:
    - 記錄每名 chatbot 使用者曾經查詢過哪些 article、哪些有新 reply
    - 記錄每名 chatbot 使用者是否點擊觀看新 reply（列表標上「新 reply 標記」，在使用者點入連結前持續顯示）
    - 紀錄每名 chatbot 使用者曾經接收過哪些 reply 的推播（避免重複推播）
2. Chatbot 提供一個「查詢過的訊息列表」
    - 應使用 LIFF 實作、透過 rich menu 觸發
    - 使用者透過訊息列表點入訊息，需要標記成已讀、消除新 reply 標記
    > 「點入訊息」應該無法直接顯示文章頁面，因為這樣無法送出「有用」或「沒用」。
    > 這可能要回到 chatbot 顯示或者直接在 LIFF 另外實作，才能正常讓使用者送出「有用」或者是「沒用」。
    - 應[重構現有 LIFF 實作](https://github.com/cofacts/rumors-line-bot/issues/144)，套用 server-render 或 client UI library 以利開發
    - 應讓 postback button [往上捲回去的時候仍然可用](https://github.com/cofacts/rumors-line-bot/issues/49)
    - ~~需在 chatbot server 上建立 API server 支援上述列表與操作~~ ~~server-sider render, 實作 CSRF protection~~ 不想 proxy Cofacts API 也想降低 server load 而不走 server-side render，最後作成 GraphQL server + token-based authentication
3. 需實作一 cron job 實作通知，包含：
    - 透過 push API 或 LINE Notify 告知 Chatbot 使用者有新回應。該 notification 的 call-to-action 就是請使用者打開「查詢過的訊息列表」介面。
    - 更新相對應的新 reply 標記（標成未讀）

## 資料庫： mongodb w/ [mLab](https://elements.heroku.com/addons/mongolab)

496MB Free!

## 資料表：`UserArticleLinks`

紀錄每個 bot user 與訊息的羈絆 (?)

- `userId`: ID
- `articleId`: ID
- `createdAt`: timestamp 使用者傳送此訊息、建立此 link 的時間
- `lastViewedAt`: timestamp 使用者上次查看此訊息~~回應~~的時間。
    - 2020/7/4 討論後追加：`UserArticleLink` create 時必會寫入
- ~~`lastRepliedAt`: timestamp Cofacts 資料庫內最新回應的時間，cronjob 或 view 時更新~~ (不用惹)
- ~~`lastPositiveFeedbackRepliedAt`: [timestamp 資料庫內評價為正的最新回應時間](https://g0v-slack-archive.g0v.ronny.tw/index/channel/C2PPMRQGP#ts-1584172124.191900) ，cronjob 或 view 時更新~~ (不用惹)

### 什麼時候會新增一筆 `UserArticleLink`

- 傳訊息、資料庫沒有、填寫理由送出後
- 傳訊息、選擇一則資料庫訊息，但該訊息沒有回應。 (沒填理由也算)
- 傳訊息、選擇一則資料庫訊息，有回應。

> [!NOTE]
> 大小估算：
> 2017~2020 年所有 user selects an article + confirm submit article = (270,018+18,369) ~= 300,000，每個都是一個 user-article link
>
> 粗估每個 document 500byte
> 300,000 * 0.5KB = 150MB

## 資料表：`UserSettings`

一個 LINE bot user 僅會有一筆 UserSetting。

- `userId`
- `allowNewReplyUpdate`：使用者是否允許我們推新回應。預設 true
- `newReplyNotifyToken`：若使用者有設定 LINE Notify，此欄位會存 LINE notify 用的 token。預設為空。

> [!NOTE]
> 大小估算：
> 200byte/record * 200K LINE bot users = 40MB

### 什麼時候會新增一筆 `UserSettings`

使用者加 chatbot 為好友時。

## LINE bot user flow

1. User 點擊 rich menu 選擇看過去訊息 / 收到 notification 並點按
2. LINE bot 跳出全頁 LIFF，展示文章列表：
    - 時間
    - 文章內文節錄（即時從 Cofacts API 抓）
    - 未讀回應數（即時從 Cofacts API 抓回應，然後挑出比 `lastViewedAt` 晚的）+ 未讀標記
3. 點擊文章列表項目，會傳訊息進 Cofacts chatbot，chatbot 列出未讀的回應列表，供使用者點按，進入 `CHOOSING_REPLY` state。若只有一則未讀回應，自動 `skipUser`
    - 此時要更新 corresponding `UserArticleLink` 的 `lastViewedAt`
    - 此設計讓使用者能下接「有用沒用」回應
    - 此設計亦方便使用者轉傳回應

### Implementation detail (2020/5/10)

分成下面三個部分：

#### 1. LIFF <> chatbot GraphQL API 的新認證方式

目前 LIFF 與 chatbot GraphQL 的 authentication，仰賴 chatbot 在 URL 上帶有的自產 JWT，讓 chatbot GraphQL 知道目前是哪個 `userId` 在使用 LIFF，以及是哪個 search session (by `sessionId`) 的按鈕。

可是，新功能「過去傳過訊息」LIFF 會放在 rich menu，URL 裡無法帶有會過期的 JWT；直接不放 exp 或設定過久的 exp 也有些危險，畢竟 JWT 被 chatbot graphql 視為等同密碼的存在，一但 leak 出去，只要 exp 沒到，攻擊者就可以一直用該 JWT 的身份存取 API。

因此，我們會新增一種新的 authentication：LINE ID token 法。

1. LIFF 透過 [liff.getIDToken()](https://developers.line.biz/en/reference/liff/#get-id-token) 拿到 LINE 發的 OpenID ID token
2. LIFF 發 request 到 chatbot GraphQL 時帶有 `Authorization: line ${ID token}` (`line` 是為了與 JWT 使用的 `bearer` 做出區隔的自訂 authentication type)
3. chatbot GraphQL 收到 `line` 開頭的 authorization header 之後，使用 [verify ID token](https://developers.line.biz/en/reference/social-api/#verify-id-token) API 檢查是否正確，並且取用回傳的 user ID (`sub`)。

以上也是 [LINE 官方文件](https://developers.line.biz/en/docs/line-login/take-over-session/#transfer-login-session)中提到的作法。

由於 LINE ID token 必須呼叫 LINE API 才能取得，不會有洩漏的機會，所以比目前 chatbot 自發 JWT 的機制還更安全。不過，目前有些功能仍然需要保留「從 chatbot 傳資料給 LIFF 回到 GraphQL」的機制（如在按鈕上帶當時的 `sessionId`，LIFF 發 request 時也必須帶有該 `sesionId` 回到 GraphQL，且此 `sessionId` 不該在 LIFF 端被竄改） ，chatbot 自發 JWT 依然有不可取代的功能在，故會兩者並行。

不過，使用此種方式，會有下面的限制：

- LINE Developers 的 LIFF scope 設定必須要勾選 openid
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_25d6cd753775a7d5ea75931110150b7f.png)
- LIFF channel 的 provider 必須與 chatbot (messaging API) provider 一致，才能共用 user id。
- Chatbot GraphQL 會多一個與 LINE server 發 API 確認 token 的工。

#### 2. LIFF 顯示文章列表的機制

LIFF 從 chatbot GraphQL 取回的資料將不會帶有訊息文字之類的訊息。整個載入流程會是：

1. LIFF 透過 `myArticleLinks` API 取得要顯示的 article links
2. LIFF 顯示表格、可點選的超連結，文字部分則為 loading 樣態 (類似 https://github.com/zalog/placeholder-loading )

另外，顯示時發送 GA visit event，`utm_source=myArticleLink`, `utm_medium` 從 URL 拿，預設是 `richmenu`。

#### 3. 點擊項目時觸發的東西

點擊表內訊息後，送出「📃 See new replies of `https://cofacts.g0v.tw/article/<articleId>`」 到聊天室，觸發下面動作：

- 開始新 search session（發配新 `sessionId`）
- 未來 ga 的 `utm_source` 為 `myArticleLink`、`utm_medium` 為 `richmenu`
- 從 URL 找出 `articleId`，設定 `selectedArticleId`
- 找出相對應的 `userArticleLink`
- 從 Cofacts API 找出所有回應之後，過濾掉建立時間比 `userArticleLink.lastViewedAt` 早的，使用 flex carousel 列出這些 reply
- 更新 `lastViewedAt` 到現在的時間
- 切換到 `CHOOSING_REPLY` state

> [!NOTE]
> 未來推播實作時，由 push message 觸發的 LIFF URL 應帶有 `utm_medium=push`, 而發送到聊天室的內容也會稍微不同（如換 emoji 為 📌）；chatbot 也使用此 emoji，判斷 utm_medium 之後要設定為何。
>
> 如此方可將「自己從 rich menu 點開 LIFF」的動作，與「看了 push message 之後點進來 LIFF」，跟其他一般查詢（完全不帶有 utm_xxx）分開。

#### 2020/7/10 Update

根據 GA 文件 [traffic source dimensions](https://support.google.com/analytics/answer/1033173) 與 [collect campaign data](https://support.google.com/analytics/answer/1033863)，`utm_source` 應是「導流量到這個網站的來源」、`utm_medium` 則是媒介。

對於 LIFF 裡的網頁來說，source 就是顯示 URL / button 讓使用者進來的流量來源，對這裡來說就是特定的 LINE channel；而媒介則可能是 push messaage 或是 rich menu。因此：
- 若從 rumors-line-bot 的 rich menu 點按進 LIFF：
    - 來源是 Cofacts 的 bot、媒介是 rich menu
    - 故為 `utm_source=rumors-line-bot&utm_medium=richmenu`
- 若是收到 rumors-line-bot 的 push notification：
    - 來源是 Cofacts 的 bot、媒介是 push message
    - 故為 `utm_source=rumors-line-bot&utm_medium=push`。`utm_source` 
- 若收到 LINE notify 的更新：
    - 來源是叫做 LINE notify 的 channel（預設），媒介也是 push message
    - 故為 `utm_source=line-notify&utm_medium=push`
- 未來若有其他地方點了可以打開 LIFF，那應該要使用新的 `utm_source`，並且斟酌打開方式來設計 `utm_medium`。

![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_04aaea5b5442f0426b777244a59dd319.png)


## Cron job 邏輯

1. 從所有 `UserArticleLinks` 找出最大的 `lastRepliedAt` 作為 `lastScannedAt`

3. 去 `ListArticle` API （sort by `lastRepliedAt`）列出所有在 `lastScannedAt` 以後才新建立、且未刪除的 `ArticleReply` 
    - 刪除回應不會被偵測到
    - 編輯審閱時間：去掉最近 12 hr 的 articleReply
     
5. 由 2 整理出 list of unique, updated article ids
6. 從 user <> selected article 關聯表，找出要通知的對象 (list of unique users to update)
7. 比照這些使用者的 `UserSettings`，使用 multicast API & LINE Notify 告知使用者「之前的訊息有回應囉」導引使用者點開 LIFF
8. redis or DB 紀錄這次執行的 timestamp
