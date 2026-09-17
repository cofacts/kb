# 中央社 MCP 專業 Subagent：可行性與必要性評估

> **結論先講**：值得整合，但**不要用中央社的查核鏈工具**（`fact-check-guide` / `review` / `publish`），只用**基礎查詢工具**；也**不要掛在 writer 或 investigator 上**，而是做成獨立的 `cna_researcher` AgentTool。
>
> 整合的主要理由不是「查得到更多資料」，而是「**查得到的出處真的存在**」——Langfuse 負評中 62% 是出處類問題，單項第一名是「提供不存在的出處」。

---

## 一、研究緣起

[專業能力 Subagent：台灣專業資料庫串接可行性研究](./專業能力%20Subagent：台灣專業資料庫串接可行性研究.md)（PR #10）提出以獨立 `domain_specialist` AgentTool 串接台灣專業資料庫，並建議「現階段不上 MCP」。[中央社 CNA MCP 觀察報告](./中央社%20CNA%20MCP%20觀察報告.md)（PR #25）則從 MCP 實作角度觀察中央社的 15 個工具。

本研究（2026-09-17）接續兩者，回答一個更具體的問題：**把中央社 MCP 做成一個專業 ADK subagent，可行嗎？必要嗎？** 這個 subagent 的設想是：承接 writer 的調查任務，可存取中央社 MCP，回報查證結果與中央社報導／圖片網址供 writer 撰寫查核回應。

與 PR #10 的差別在於：中央社 MCP 是**已經存在、已經可用**的外部服務，不需要 Cofacts 自建與維運 server，因此 PR #10「不上 MCP 是為了省下 server 維運」的理由在這個案例上不成立。

## 二、方法

**過往查核任務**取自 Langfuse（`langfuse.cofacts.tw`，production 環境）：

| 資料 | 數量 | 區間 |
| :---- | :---- | :---- |
| `invocation [cofacts_ai]` traces | 1,162 | 2026-02-24 ~ 2026-09-16 |
| 對話 session | 630（456 個單輪） | 同上 |
| `draft_factcheck_response` 工具呼叫 | 612 次（去重後 534 則相異查核） | 同上 |
| `investigator` 工具呼叫 | 885 次 | 同上 |
| `user-thumbs` 評分 | 276（👍146 / 👎124 / 中立 6） | 同上 |

**中央社 MCP** 則是實際呼叫測試：本研究共發出 15 次工具呼叫，涵蓋 `fact-check-guide`、`fact-check-review`、`cna-news-qsearch`（8 次）、`cna-news-single`、`cna-photo-search`、`cna-translation-lookup`、`o-info-search`（4 次），查詢內容全部取自上述 Langfuse 真實查核任務。

> **限制**：`cna-news-latest-newslist`、`cna-news-latest-category`、`cna-word-map` 與四個 `render-*` 視覺化工具未實測；`fact-check-publish` 沿用 PR #25 的實測結論未重複呼叫。
>
> 「相異查核」沒有精確數字：資料裡沒有 message ID，只能推估。以回覆前 100 字機械去重得 **534 則**；以語意分群（同一則謠言在不同日被不同使用者送出視為不同查核、連續重試視為同一則）人工推估得 **約 360 則（±10%）**。本文一律採用 534 這個較保守（分母較大）的數字，因此所有百分比都是**低估**。題型分布為關鍵字啟發式分類（優先序取第一命中），僅供量級參考。

## 三、過往查核任務的樣貌

### 3.1 題型分布（534 則相異查核）

| 題型 | 佔比 | 中央社可用性 |
| :---- | :---- | :---- |
| 政治／政策／法規 | 27% | **高**——官方說法、首長發言、政策公告有逐日報導 |
| 健康／醫療／食安 | 26% | **中**——機制類無解，但食安事件、研究報導、政府澄清有 |
| 詐騙／投資 | 11% | **低**——需要 165 清單類結構化資料，新聞只有個案 |
| 國際／外交 | 8% | **高**——但**譯名是硬門檻**，見 4.1 |
| 人物言論／生平 | 5% | **高**——發言有逐日紀錄；生平細節不一定 |
| 歷史／文史 | 2% | **低**——中央社新聞僅回溯至 1990 年 |
| 生活常識／交通 | 2% | **低**——長尾在地資訊不是新聞題材 |
| 社會／災害／治安 | 1%* | **高**——官方傷亡數字與應變時序完整 |
| 其他／未分類 | 12% | — |

\* 關鍵字優先序會把同時命中多類的題目歸到排序較前的類別，因此**災害類（實際約 5%）與歷史文史類（實際約 9%）被明顯低估**，政治類則被高估。以語意分群人工推估的另一份分類得到：健康 25%、政治 19%、生活交通 12%、歷史 9%、詐騙 8%、國際 8%、名人 6%、災害 5%。兩份分類在「哪幾類佔大宗」上一致，細部佔比請以量級看待。

### 3.2 出處分布（這是關鍵）

534 則查核平均引用 **3.8 個網域**。其中：

- **42% 引用了 `.gov.tw` 政府網站**
- **14% 引用了 TFC 或 MyGoPen**
- **10% 引用了 `cna.com.tw` 或 `focustaiwan.tw`**（`cna.com.tw` 以 73 次呼叫計為全站第 4 大來源，僅次於維基百科、自由時報、英文維基）

換句話說，**中央社已經是 cofacts.ai 事實上的主要來源之一，只是目前透過 Google Search 間接取得**。而 `o-info-search` 的三個資料庫（政府公開資料、事實查核中心、中央社訊息平台）正好覆蓋前兩項——**cofacts.ai 最常引用的兩類出處，中央社 MCP 都有結構化的直接管道**。

逐案檢視引用了中央社的那些查核，會發現它們**幾乎全部集中在政治／政策（中聯油脂食安究責、ALTIUS 無人機軍購、城鎮韌性演習、光復節修法、AI 新十大建設）、國際（川普台海訪談，經 focustaiwan.tw）與名人（李昌鈺逝世）**，而健康偏方、詐騙腳本、歷史詮釋這三類**幾乎是零**。這是行為證據，不是預測——3.1 那張表的可用性評級，實際引用行為已經先驗證過一輪了。

另一個角度：以「有沒有任何權威出處（政府／學術／查核機構／主流媒體）」來看，**74 則（14%）完全沒有**，只靠部落格、內容農場、維基或單一社群平台。這是出處品質確實有缺口的證據；但逐案看，**中央社只能修好其中一部分**——例如「長榮巴黎酒店旗幟爭議、陸委會回應」只引用了 `voacantonese.com`，中央社必定有逐日報導；反之「數字 4 忌諱起源」（5 次重複出現，只有 wiki 與利基部落格）、二二八死亡人數、RT 烏克蘭認知作戰系列，中央社大多幫不上忙。

### 3.3 使用者負評的真正痛點

276 則 `user-thumbs` 的勾選理由（可複選）：

| 負評理由 | 次數 | | 好評理由 | 次數 |
| :---- | ---: | :--- | :---- | ---: |
| **提供不存在的出處** | 18 | | 出處精準 | 43 |
| 沒抓到重點 | 16 | | 具有說服力 | 43 |
| **出處摘要錯誤** | 15 | | 語氣適合 | 37 |
| **回應文字與出處不符** | 15 | | 篇幅適中 | 21 |
| 資訊錯誤或過時 | 10 | | | |
| **出處不足** | 9 | | | |
| 篇幅過長 | 7 | | | |

**出處類負評合計 57 次，佔全部負評勾選（91 次）的 62%**；好評第一名也是「出處精準」。出處品質是使用者滿意度的主軸。

負評的自由文字更具體，例如：

> 「Verifier 被輸入四個錯的網址（都點不進去），結果 verifier 幻覺說支持。……最奇怪的是 mygopen 連結原本是正確的 `https://www.mygopen.com/2023/06/honey.html` 在這裡變成壞的 `https://www.mygopen.com/2023/06/honey-metal.html`」

> 「我翻找 Things Chinese 這本書，裡面根本沒說 Four is an unlucky number 那句話。」

> 「『heho.com.tw/archives/378892 醫學專業網站：龍葵鹼中毒症狀與處理建議』是錯的，裡面沒有中毒症狀」

這些不是「查不到」的問題，是**網址被模型改寫、以及對真實來源的內容作出不實摘要**。`draft_factcheck_response` 既有的 per-claim source-coverage gate 擋得住「claim 沒有對應 URL」，但擋不住「URL 本身是編的」或「URL 存在但內容不是那樣」。

## 四、中央社 MCP 實測結果

### 4.1 `cna-news-qsearch`：命中率高，但有兩個硬陷阱

| 測試（取自真實查核任務） | 結果 |
| :---- | :---- |
| `蘇丹紅 蝦味先` | **命中**（49 筆）。摘要已含食藥署逐日下架公斤數、涉案公司名、邊境查驗批數 |
| `強冠 葉文祥` | **命中**（134 筆）。**年鑑**回傳一審 20 年→二審 22 年→最高法院定讞的完整結構化時序 |
| `花蓮 堰塞湖 罹難`（2025-09~11） | **命中**（95 筆）。14 死 52 傷 31 失聯、林保署 9/22 紅色警戒、內政部通報時序 |
| `賴清德 萬里` | **部分命中**（473 筆）。老家爭議完整，但沒直接回答「出生年份是否為 1959」 |
| `牛奶 骨折` | **命中但危險**（93 筆）。第一筆就是 2014 年 BMJ 瑞典研究報導——**很可能就是該謠言的源頭**，同時也有 1996/1997 年鼓勵喝牛奶的舊稿 |
| `待機電力 家電` | **弱**（8 筆）。只有 2005–2018 年的泛論節電新聞，沒有逐項瓦數 |
| `國道 測速 取締` | **落空**（49 筆但全部不相關）。無法回答「某公里處是否有測速照相」 |
| `黑松沙士 黃樟素` | **0 筆**。事件在 1984-85 年，早於中央社資料庫的 1990 年起點 |

**陷阱一：譯名。** 查 `盧比奧 國務卿` 只回 5 筆；改查 `盧比歐 國務卿` 回 **1,719 筆**。`cna-translation-lookup` 顯示中央社用「盧比歐」1,100 次、「盧比奧」1 次。關鍵字是嚴格 AND，一字之差就是 344 倍的召回率差距，而且**不會報錯，只會安靜地少給資料**。任何要用這組工具的 agent 都必須先查譯名。

**陷阱二：時效與脈絡。** 牛奶案例顯示中央社檔案裡同時存在謠言的源頭報導與相反立場的舊稿。天真檢索會讓 agent 引用一篇 2014 年的外電當作現況——這正是「資訊錯誤或過時」這類負評（10 次）的來源。

### 4.2 `o-info-search`：本次評估中價值最高的單一工具

三庫合查（政府公開資料／事實查核中心／中央社訊息平台），回傳**全文 + 真實 URL + 查核中心專家結論標籤**。

| 測試 | 結果 |
| :---- | :---- |
| `中配 里長` | TFC 報告（`tag: 錯誤`）+ MyGoPen（`tag: 易誤解`）全文，含中選會 26 人中 19 人選村里長、SynthID 浮水印檢測等細節 |
| `蜂蜜 金屬` | **直接回傳當初被 verifier 竄改的正確網址** `https://www.mygopen.com/2023/06/honey.html`，外加 2026-08 新版 TFC 報告 |
| `馬鈴薯 發芽` | 4 筆高度相關（2 篇 TFC + MyGoPen + 嘉義市政府衛生局），含「龍葵鹼不具傳染性」的專家澄清 |
| `微波爐 致癌` | 4 篇查核報告，涵蓋 2016/2019/2022 三代變體 |

蜂蜜案例是最直接的證據：**這個工具會把那則負評所抱怨的、被幻覺掉的正確網址原封送回來。**

但有兩個必須處理的問題：

1. **循環引用風險**：「事實查核中心」這個 bucket **包含 Cofacts 自己的回應**。`中配 里長` 回了 `https://cofacts.tw/article/qzCHe6ABEY7yIwhpkleZ`（署名「老鶴 認為 含有錯誤訊息」），`微波爐 致癌` 回了 `https://cofacts.tw/article/u8s3jr9rx6zk`（署名「Lin」）。cofacts.ai 若引用這些，等於引用自己的平台當外部佐證。**必須過濾 `cofacts.tw` 網域。**
2. **中央社訊息平台是投稿稿，不是中央社新聞**：`蜂蜜 金屬` 回了「鶯歌光點美學館冬祭慶典」、`中配 里長` 回了「嘉義市長施政 6 周年」。這是付費／投稿的企業與地方政府新聞稿，證據力極低，**不可當成中央社報導引用**。

### 4.3 `cna-news-single`：逐字全文 + 正規 URL

以 `pid` 取單篇全文，回傳的是發稿單位資料庫裡的原文，且日期已正規化（「今天（2024年02月21日）」）。這對 cofacts.ai 的意義是：**中央社來源的 claim 不需要再走 verifier 的 `url_context` 抓取**——文字不是爬來的，是發稿方給的，`url` 欄位也是資料庫欄位而非模型輸出。這正面解決「提供不存在的出處」與「出處摘要錯誤」兩類負評。

### 4.4 `cna-photo-search`：有圖有網址，但授權是紅線

回傳 `image_url`（可直連的 JPG）、`shop_url`、攝影記者姓名與拍攝日期。實測 `光復 淤泥` 得到 72 筆災區現場照。

但 `_meta` 明寫：**「使用中央社照片需注意照片授權，MCP 僅提供瀏覽。」** Cofacts 的查核回應是 CC 授權公開內容，直接嵌入 phototaiwan.com 的圖會有授權問題。**建議只用圖說文字當佐證、以 `shop_url` 當出處連結，不要 hotlink `image_url`。** 圖說本身其實相當有價值——它有攝影記者、日期、地點，是判斷「這張照片是不是被挪用」的權威依據。

（另注意：`cna-news-qsearch` 回傳的影像空間結果**沒有 url 欄位**，只有 `cid`/`title`/`date`/`summary`。要圖片網址必須走 `cna-photo-search`。）

### 4.5 查核鏈三工具：確認是靜態 prompt，且與 cofacts.ai 架構衝突

`fact-check-guide` 無參數、不查任何資料，回傳一份方法論全文。`fact-check-review` 收 `draft` 與 `check_points`，但回傳的是固定的四軸 rubric（PR #25 已實測兩次呼叫逐字相同）。

方法論本身寫得很好，但它**假設中央社 MCP 就是整個對話，而使用者是主編**：

- 「提取完成後，**先把這 3–5 個查核點列給使用者看**」
- 「這份草稿**不顯示給使用者**」
- `fact-check-review` 收尾：「顯示完之後**停下來等使用者回答**……**不得代替使用者判定沒問題**」
- 規定逐字附上警語：「以上內容為 AI 參考中央社報導重新詮釋生成，並非中央社原始報導」
- 標籤規則：「**只有在內容判定為『錯誤』時才標註標籤**」

這四點與 cofacts.ai 直接相斥：cofacts.ai 的 writer 是自主 orchestrator，一輪產出一則回應，沒有「停下來等主編」這個 gate；Cofacts 的分類法是四分類（RUMOR / NOT_RUMOR / OPINIONATED / NOT_ARTICLE），**明確會標示 NOT_RUMOR 與 OPINIONATED**，而 CNA 指引禁止這麼做。

更關鍵的是，**cofacts.ai 已經有一個更強的同類機制**：`draft_factcheck_response` 的 per-claim source-coverage gate 是 Python 驗證，`verifier_confirmed` 不為 true 就直接退回呼叫；`fact-check-review` 只是把 rubric 丟給 LLM 自己遵守。用弱的取代強的沒有道理。

**結論：只接基礎查詢工具（`cna-news-qsearch`、`cna-news-single`、`o-info-search`、`cna-photo-search`、`cna-translation-lookup`、`cna-word-map`），不接 `fact-check-*` 三件組，也不接 `render-*`（Cofacts 有自己的前端）。**

## 五、架構：掛在哪裡？

### 5.1 三個選項

**選項 A：掛在 writer 上。** 技術上可行——writer 目前只有 FunctionTool 與 AgentTool，沒有 ADK built-in tool，因此不受「built-in 不可與 function calling 混用」的限制（`agent.py:764-772`）。但：

- writer 已有 10 個工具與一段很長的 instruction，再加 6 個 MCP 工具會稀釋注意力；
- 4.1 顯示這組工具**需要專門的查詢手藝**（先查譯名、2–3 個名詞實體、日期參數、0 筆時的減詞階梯）。把這些規則塞進 writer 的 prompt，等於要 writer 同時當 orchestrator 和中央社檢索專家；
- writer 每次呼叫都會帶上完整工具定義，成本上升而多數查核用不到。

**選項 B：掛在 investigator 上。** **不可行。** investigator 的唯一工具是 built-in `google_search`（`agent.py:323`），依 ADK 限制無法再掛 function-calling 類工具。要掛就得拿掉 `google_search`，等於廢掉 investigator。

**選項 C：獨立 `cna_researcher` AgentTool。建議採用。**

### 5.2 為什麼是 C

1. **查詢手藝需要專屬 prompt**。譯名陷阱（5 筆 vs 1,719 筆）、嚴格 AND、年鑑日期語意（`date` 是出版版次年不是事件年）、0 筆重試階梯——這些是一整套領域知識，寫進一個小 agent 的 instruction 剛好，寫進 writer 就是噪音。
2. **正好複製既有模式**。investigator（google_search）與 verifier（url_context）已經是「一個 agent 專責一個檢索通道，AgentTool 掛回 writer，`after_model_callback` 產出 `{content, sources}`」。`cna_researcher` 是第三個同型 agent，架構上沒有新概念。
3. **`sources` 可以是真的**。investigator 的 `append_grounding_sources` 要從 grounding chunks 解 vertexaisearch 轉址（`resolve_vertex_redirect`）；`cna_researcher` 的 callback 可以**直接從 MCP 回傳的 JSON `url` / `shop_url` 欄位組 sources**，不經過模型輸出。這是整個提案在工程上最實質的收穫——出處從「模型寫出來的字串」變成「資料庫欄位」。
4. **可以只在需要時啟動**。writer 依題型決定要不要呼叫，健康機制類、長尾詐騙類就不叫。

### 5.3 與 verifier 的關係

建議讓 `cna_researcher` 回傳的 claim **直接標記為可信**，繞過 verifier 的 `url_context` 二次抓取：文字是中央社資料庫的原文，再抓一次網頁只會多一次幻覺機會（多則負評正是 verifier 造成的）。但這牽涉 `draft_factcheck_response` 的 `verifier_confirmed` 契約（`tools.py:542`），屬於 [agent source integrity contract](https://github.com/cofacts/ai/blob/main/docs/decisions/20260515-agent-source-integrity-contract.md) 的變更，**必須另立 ADR**。

保守作法是第一版仍走 verifier，觀察 Langfuse 上 CNA 來源的 verifier 否決率；若接近 0，再提案放行。

## 六、必要性評估：值不值得？

**值得，但理由要說對。**

不值得的理由（要排除的誤解）：

- ❌ 「Google Search 查不到中央社」——查得到，中央社已是第 4 大引用來源。
- ⚠️ 「涵蓋率會提升」——**部分成立但不是主要理由**。確實有 14% 的查核完全沒有權威出處，但逐案檢視，其中多數（民俗傳說、二二八、俄烏認知作戰長文、匿名詐騙腳本）中央社也補不上；能補的是「有台灣新聞點卻只引用了外媒或部落格」那一小類。把涵蓋率當成主要賣點會高估這個提案。

值得的理由：

1. **出處完整性**（最強）。62% 的負評是出處問題，第一名是幻覺網址。MCP 回傳的是資料庫欄位，不是模型輸出。蜂蜜案例已證實可以直接修掉一則實際負評。
2. **`o-info-search` 打中最常用的兩類出處**。42% 的查核引用政府網站、14% 引用 TFC/MyGoPen，這個工具用一支 API 同時覆蓋，而且帶專家結論標籤（`tag`）。PR #10 規劃要接的 Google Fact Check Tools API 與食藥闢謠，這裡有相當程度的重疊——**建議先做這個，再評估 PR #10 的 Tier 1 還缺什麼**。
3. **年鑑是真正的差異化資產**。`強冠 葉文祥` 的年鑑條目是一份寫好的、有時序的案件回顧，開放網路檢索得自己拼。這類「事件全貌」需求在政治與食安題型很常見。
4. **抗 RAG 毒化**。呼應[境外敵對勢力研究](./境外敵對勢力與公民查核平台之防禦機制.md)的「可信資訊白名單」：這是一條繞過搜尋排序、不會被內容農場污染的通道。
5. **成本低**。`mcp` 1.26.0 已經在 `adk/uv.lock` 裡（google-adk 1.26.0 的相依），`McpToolset` 不需要新套件；認證是 endpoint + API key，不必實作 OAuth。

不值得整合的部分要明講：**詐騙投資（11%）、生活常識交通（2%）、歷史文史（2%）這三類中央社基本無解**，仍需 PR #10 的 165 涉詐網站清單與全國法規資料庫。中央社 MCP **不能取代** PR #10 的規劃，是互補。

## 七、建議實作路徑

1. **先做一個 30 分鐘的 spike**：確認 ADK 1.26 的 `McpToolset`（Streamable HTTP）掛上去之後，MCP 工具是否確實被當成 function-calling 工具處理（預期是，但 `agent.py:764-772` 的限制註解只針對 Google built-in，**沒有實測過 MCP，不應假設**）。
2. **建 `cna_researcher` LlmAgent**（gemini flash 級即可），工具只掛 `cna-news-qsearch`、`cna-news-single`、`o-info-search`、`cna-translation-lookup`、`cna-word-map`、`cna-photo-search`。
3. **instruction 必寫的四條**：(a) 遇外文專名先 `cna-translation-lookup`；(b) 關鍵字 2–3 個名詞實體、時間走 `start_date`/`end_date`；(c) 0 筆時依減詞階梯重試，不可直接回報查無；(d) 引用前檢查報導日期，舊稿要標註時間並確認有無後續發展。
4. **`after_model_callback` 從 MCP JSON 欄位組 `{content, sources}`**，並在此層過濾 `cofacts.tw`（循環引用）與 `中央社訊息平台`（投稿稿）兩類結果。
5. **圖片只給 `shop_url` 與圖說文字**，不 hotlink `image_url`。
6. **接上既有機制**：`agent_names.py` 加常數、writer `tools=[]` 加 `AgentTool`、`_EMPTY_RETRY_HINTS`、`_normalized_response`、`writer_citations.py` 的 `_CITING_TOOL_NAMES`、前端 `src/lib/adk.ts` 的 `AllTools`。
7. **Langfuse 觀察指標**：`cna_researcher` 呼叫率、其 sources 被 `draft_factcheck_response` 採用的比率、以及「提供不存在的出處」負評是否下降——這是驗收這個提案的唯一標準。

**需要 ADR**：新增 subagent 屬於 `CLAUDE.md` 明列的「改變 agent contract 或 orchestration」；首次引入 MCP 也是新架構模式；若後續要讓 CNA 來源繞過 verifier，那是第二份 ADR。

## 八、出處

- **Langfuse**（`langfuse.cofacts.tw`，production）：traces / observations / scores API，2026-02-24 ~ 2026-09-16，1,162 traces、612 次 `draft_factcheck_response`、885 次 `investigator`、276 則 `user-thumbs`。
- **中央社 MCP 實測**：本研究 2026-09-17 實際呼叫 15 次，查詢內容全部取自上述 Langfuse 任務。
- **cofacts/ai**：[`adk/cofacts_ai/agent.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/agent.py)（`ai_writer` / `ai_investigator` / `ai_verifier` 的 AgentTool 模式、built-in tool 限制註解 764-772、`append_grounding_sources` 94-153）、[`tools.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/tools.py)（`draft_factcheck_response` 428-587 的 per-claim gate）、[`writer_citations.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/writer_citations.py)、[ADR 20260515 agent source integrity contract](https://github.com/cofacts/ai/blob/main/docs/decisions/20260515-agent-source-integrity-contract.md)、`adk/uv.lock`（google-adk 1.26.0、mcp 1.26.0）。
- **本 KB 先行研究**：[專業能力 Subagent：台灣專業資料庫串接可行性研究](./專業能力%20Subagent：台灣專業資料庫串接可行性研究.md)（PR #10，尚未合併）、[中央社 CNA MCP 觀察報告](./中央社%20CNA%20MCP%20觀察報告.md)（PR #25，尚未合併）、[境外敵對勢力與公民查核平台之防禦機制](./境外敵對勢力與公民查核平台之防禦機制.md)。
