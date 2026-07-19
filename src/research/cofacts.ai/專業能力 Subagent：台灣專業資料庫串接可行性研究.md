# **專業能力 Subagent：台灣專業資料庫串接可行性研究**

## **研究緣起**

Cofacts.ai 的查核流程中，Writer 與 Investigator 經常遇到需要**專業知識庫**才能妥善回應的訊息類型：法規解釋（「新法上路後～會被罰」類謠言）、詐騙案例比對（假投資網站、冒名詐騙）、食藥安全（保健食品療效）、疫情數字、地震氣象謠言等。這類查證目前只能仰賴 Google Search，受制於搜尋排序品質，且正是〈境外敵對勢力與公民查核平台之防禦機制〉指出的 RAG 毒化攻擊面——搜尋結果可能已被對抗性內容農場污染。

2026 年 7 月，專案成員提出「專業能力 proofreader」構想：為 writer 與 investigator 分憂解勞，提供需要特別串接 API 才能使用的專業知識庫（法規資料庫、165 反詐儀表板的詐騙案例等），並提出待決問題：**應該寫成 skill 給 investigator 用，還是獨立 subagent？**

本研究（2026-07-19）逐一查證候選台灣資料源的 API 可用性、梳理 Google ADK 的工具掛載選項，並給出架構建議。

> **查證方法限制**：查證當時執行環境的 WebFetch 對多數外部網站被 egress policy 阻擋，資料源細節多以 WebSearch 多方交叉比對取得（部分輔以 GitHub raw 文件直接驗證），**實作前應對 Tier 1 各資料源實際呼叫一次**，確認金鑰需求與欄位格式。

## **一、定位澄清：這不是 proofreader，是兩個場景共用一組工具**

「專業能力 proofreader」實際上涵蓋兩種角色：

1. **查證期的專業檢索**（investigator 側）：「這個投資網站在 165 黑名單嗎？」「某法條現行條文是什麼？」
2. **審稿期的專業審查**（proofreader 側）：「草稿引用的法條號碼與構成要件對不對？」「詐騙手法分類用語是否符合 165 的官方分類？」

兩者用同一組資料庫工具即可支撐，差別只在呼叫時機與問法。因此不必為「審查」另建 agent——一個具備工具的專家 agent 兩個場景都能服務。

## **二、架構決策：獨立 subagent（AgentTool），而非 investigator 的工具**

**決定性理由是 ADK 的硬限制**（`agent.py` 註解已載明）：built-in tools（`google_search`、`url_context`）不能與 function calling tools 混用於同一 agent。Investigator 用了 `google_search`，故無法再掛任何自訂 API 工具。剩餘選項比較：

| 選項 | 評估 |
| :---- | :---- |
| 工具直接掛 writer | 可行但不佳：writer 的 prompt 與工具清單已很長，每加一個資料庫工具都稀釋其注意力；且 writer 不該學各資料庫的查詢細節。 |
| **獨立 `domain_specialist` subagent（建議）** | 照 investigator／verifier 的既有 `AgentTool` 模式：一個 `LlmAgent`（gemini flash 級即可）掛全部專業資料庫工具，writer 用自然語言描述需求（「幫我查這個網址是否為已列管詐騙網站」），它自選工具、整理結果回傳 `{content, sources}`。 |
| 按領域拆多個專家 agent | 現階段過度設計。等工具數膨脹（>10~15 個）或單一 agent 的工具選擇明顯出錯時再拆。 |

**MCP 的取捨**：ADK 2.5 的 `McpToolset` 已支援 stdio 與 Streamable HTTP，但現階段**不建議上 MCP**——多一層 server 維運。等這批工具需要跨專案共用（chatbot、rumors-api、其他 agent 系統）時，再收斂成一個 MCP server，屆時以 `McpToolset` 掛回 ADK 的遷移成本很低。

**實作模式**（依工具性質二選一）：

- **FunctionTool**：照 `tools.py` 現有 httpx 模式手寫 Python function（docstring 即工具說明）。適合靜態清單類（法規 XML、165 CSV、食藥闢謠）——可自控快取、下載排程與比對邏輯。
- **OpenAPIToolset**：餵 Swagger/OpenAPI spec 自動生成整組 `RestApiTool`。適合有官方 Swagger 的氣象署、環境部、疾管署 CKAN，一行接一整組端點。

## **三、資料源盤點（2026-07 查證）**

### **Tier 1：立即可接（免金鑰或單一免費金鑰，靜態檔案／簡單 REST）**

| 資料源 | 內容與接法 | 備註 |
| :---- | :---- | :---- |
| **165 遭停止解析涉詐網站** | [data.gov.tw/dataset/176455](https://data.gov.tw/dataset/176455)，免金鑰 CSV，不定期更新（2026-01 上架）。排程同步後做網址比對工具。 | 舊「假投資(博弈)網站」清單（dataset/160055）已被本資料集取代；**詐騙 LINE ID dataset（78432）已於 2024/11 下架**，需資料須正式行文刑事局。165dashboard.tw 本身無文件化 API，不建議爬。另 g0v [Open165 提案](https://g0v.hackmd.io/@mrorz/open165-proposal)（mrorz 發起）有現成資料清洗脈絡，宜先內部討論合作。 |
| **Google Fact Check Tools API** | [claimSearch endpoint](https://developers.google.com/fact-check/tools/api)，免費 Google Cloud API key。 | TFC 與 MyGoPen **均無自家公開 API**，但都有 ClaimReview 標記並被 Google 收錄——一支 API 同時涵蓋兩家（含 rating、url、日期），是接查核報告 CP 值最高的路，免自建爬蟲。 |
| **全國法規資料庫** | 免金鑰。兩條路：(a) [data.gov.tw 全量 XML](https://data.gov.tw/dataset/18289)（週更）下載建本地索引／向量庫；(b) 官方 Open API（Swagger：`law.moj.gov.tw/api/swagger`）依法規名稱即時查詢。 | 不含地方自治條例與部分行政規則。社群工具 [mojLawSplit](https://github.com/kong0107/mojLawSplit) 已有逐條 JSON 可參考。165 詐騙＋法規是查核最常用的兩把刀。 |
| **食藥闢謠專區** | 站台 RSS（`fda.gov.tw/tc/rss.aspx`）訂閱新公告＋ [data.gov.tw/dataset/17148](https://data.gov.tw/dataset/17148) 作歷史目錄；全文需回爬公告頁。 | 食安謠言最權威來源；公告頻率不高，快取成本低。 |

### **Tier 2：標準 REST API，email 註冊即得免費金鑰**

| 資料源 | 內容與接法 |
| :---- | :---- |
| **中央氣象署** | [opendata.cwa.gov.tw](https://opendata.cwa.gov.tw/dist/opendata-swagger.html)，REST＋Swagger。地震報告 `E-A0015`（顯著有感）／`E-A0016`（小區域）即時發布——反駁「地震預測」「地震雲」類謠言的第一手數據。 |
| **環境部空品** | [data.moenv.gov.tw](https://data.moenv.gov.tw/) API v2（如 `aqx_p_432` AQI），每小時更新，金鑰 5000 次/日。 |
| **疾管署** | [data.cdc.gov.tw](https://data.cdc.gov.tw/) CKAN 平台（OAS 3.0，目錄 `od.cdc.gov.tw/cdc/Ckan01.json`），法定傳染病統計每日更新、一般讀取免金鑰；闢謠專區僅網頁需爬。 |

三者皆有 Swagger → 用 `OpenAPIToolset` 自動生成最省工。

### **Tier 3：暫緩（取得成本高或非即時工具性質）**

| 資料源 | 狀況 |
| :---- | :---- |
| **司法院裁判書** | 新版平台需會員帳密換 Bearer Token（效期僅 6 小時，部分服務僅凌晨 00:00–06:00 開放）；舊版 `JList`/`JDoc` 免金鑰但僅保留近期異動、月包 zip 已暫停。要長期歷史裁判庫需自建夜間排程 pipeline，工程量大。建議第二階段，先評估查核場景是否真需裁判全文。 |
| **中選會／政治獻金** | 中選會（[data.cec.gov.tw](https://data.cec.gov.tw/)）為 CSV 下載無 API、選後 7 日更新；監察院政治獻金平台（[ardata.cy.gov.tw](https://ardata.cy.gov.tw/)）僅網頁查詢＋CSV 匯出、無 API 需爬。平時用途低，選舉季價值高。 |
| **IORG／台灣民主實驗室** | **均無可程式存取的「認知戰論述特徵庫」API**。IORG 有 GitHub（`LINE-rumor-clustering` 等 repo）；DTL 的 [China Index](https://china-index.io/) 有 GitHub JSON 但屬宏觀國別指標、約 1–2 年更新。定位為**離線 RAG 背景語料**（敘事分類參考），不是即時查詢工具。〈境外敵對勢力〉研究建議的「認知戰論述特徵庫比對」需以此為基礎另行建置。 |
| **data.gov.tw 其他** | 公司登記（經濟部，查「某公司是否存在」類謠言）、犯罪統計（警政署季更）、CPI（主計總處月更）等可依需求隨時加掛，平台介接模式同 Tier 1。 |

## **四、與防禦機制研究的呼應**

〈境外敵對勢力與公民查核平台之防禦機制〉建議建立「可信資訊白名單」，使 AI 調查員在國安、詐騙、健康等高風險領域不必盲信搜尋排序。本研究的 Tier 1／Tier 2 資料源正是該白名單的具體實作：**官方結構化資料 → 專家 subagent → writer**，繞過可能被對抗性樣本污染的開放網路檢索。查核回應引用這些來源時，出處可信度也直接提升（實證顯示使用者負評正集中於出處品質）。

## **五、建議實作路徑**

1. **MVP（1–2 天）**：建 `domain_specialist` `LlmAgent`＋`AgentTool` 掛入 writer；先接兩個工具——165 涉詐網站比對（CSV 排程同步）＋ Google Fact Check claimSearch。這兩個對日常查核命中率最高。
2. **第二批**：全國法規查詢（XML 本地索引或 Open API）＋食藥闢謠。
3. **第三批**：氣象署／環境部／疾管署以 `OpenAPIToolset` 接入。
4. **觀察指標**：在 Langfuse 上追蹤 domain_specialist 的呼叫率與其結果被引用進 `draft_factcheck_response` 的比率，決定是否值得投資 Tier 3（裁判書 pipeline）。
5. **遠期**：工具需跨專案共用時收斂為 MCP server（ADK `McpToolset` 以 Streamable HTTP 掛回）。

## **出處**

- 架構背景：[cofacts/ai `adk/cofacts_ai/agent.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/agent.py)（built-in tool 與 function tool 不可混用之註解、AgentTool 模式）、[`tools.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/tools.py)（現有 httpx FunctionTool 模式）
- 本 KB 先行研究：[境外敵對勢力與公民查核平台之防禦機制](./境外敵對勢力與公民查核平台之防禦機制.md)（可信資訊白名單、RAG 毒化）、[資訊偏聽型 Proofreader：媒體環境模擬與動態記憶之設計研究](./資訊偏聽型%20Proofreader：媒體環境模擬與動態記憶之設計研究.md)（同次檢討的姊妹篇；user feedback 痛點實證）
- 資料源（查證於 2026-07-19，詳細 URL 見文中表格）：data.gov.tw（165／法規／食藥／選舉等 dataset）、Google Fact Check Tools API、opendata.cwa.gov.tw、data.moenv.gov.tw、data.cdc.gov.tw、opendata.judicial.gov.tw、ardata.cy.gov.tw、github.com/iorg-tw、github.com/doublethinklab、g0v Open165 提案
- Google ADK（v2.5.0，2026-07）：[FunctionTool](https://google.github.io/adk-docs/tools-custom/function-tools/)、[OpenAPIToolset](https://google.github.io/adk-docs/tools-custom/openapi-tools/)、[MCP tools](https://google.github.io/adk-docs/tools-custom/mcp-tools/)、[Workflows／collaboration](https://google.github.io/adk-docs/workflows/collaboration/)
