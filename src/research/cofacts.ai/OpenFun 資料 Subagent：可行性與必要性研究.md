# **OpenFun 資料 Subagent：可行性與必要性研究**

## **研究緣起**

[PR #10](https://github.com/cofacts/kb/pull/10) 的〈[專業能力 Subagent：台灣專業資料庫串接可行性研究](./專業能力%20Subagent：台灣專業資料庫串接可行性研究.md)〉（2026-07）盤點了台灣各專業資料源，並建議做成獨立的 `domain_specialist` AgentTool。該研究逐一評估了 165 涉詐清單、法規資料庫、氣象署、疾管署、司法院裁判書等**個別**資料源，結論是分三階段、每個資料源各寫一個 FunctionTool。

本研究（2026-09-17）改以單一標的重新提問：**[歐噴資料庫（data.openfun.tw）](https://data.openfun.tw/llms.txt)** 是一個把數千個台灣公共資料集收斂成一致 REST 介面、且每個資料集都附 AI 專用 `skill.md` 的聚合平台。七月的研究完全沒有涵蓋它。若改以「一個平台、一把 token」為接入單位，可行性與必要性的計算會不會不同？

具體評估標的是一個 ADK subagent，具備：承接 writer 調查任務並回報計算結果與資料集網址、專用 fetch tool 注入 OpenFun token、接上 code execution 做運算、以「先讀 llms.txt 但改用專用 tool」的轉接 prompt。

> **方法與限制**：本研究所有 API 結果均為 2026-09-17 實際呼叫所得（token 來自執行環境變數）。查核任務樣本取自 cofacts.ai 的 Langfuse（langfuse.cofacts.tw）正式環境 trace。**唯一未能實證的是 Gemini 是否接受 code execution 與 function calling 併用**（本環境無 Gemini 憑證），該項於 §5.2 標示為必須先做的 spike。

---

## **一、歐噴資料庫是什麼**

不是「又一個資料源」，而是一層**資料集聚合與 AI 介面層**：

| 面向 | 實測數字 |
| :---- | :---- |
| 資料集總數 | **3,313**（全部 `access_level: public`） |
| 型態 | `tinydb` 3,262／`api` 40／`bulk` 11 |
| 主題分布 | SEGIS 社經統計 2,698、國家統計 324、戶役政 77、衛福 76、政治 27、TDX 運輸 26、公司稅籍 25、住宅 25、健保 13 |
| `skill.md` 覆蓋率 | 抽樣 25 個 → **25/25（100%）**，中位數 11.8KB ≈ **3,400 tokens** |

關鍵差異在 `skill.md`：它明確寫給 AI 讀，含「這份資料集**能**回答什麼／**不能**回答什麼」、欄位型別與篩選語法、單位警告、以及「遇到問題最多試 2 次就停下來報告，不要自己換語法繼續猜」的行為約束。這正是本案 subagent 所需的 prompt 素材，且由資料提供方維護。

七月研究列為 **Tier 3「暫緩、工程量大」** 的資料源，歐噴已經做完：

- **司法院裁判書**：`elastic-jud-data.api.openfun.dev` 提供 **22,187,807 筆**判決全文的 Elasticsearch 端點（民國 85–115 年），支援 `match_phrase` 與 aggregation。七月研究的評估是「需自建夜間排程 pipeline」。
- **中選會選舉資料**：`tw.gov.cec~txn~candidates-votes` 有 **5,773,865 筆**投開票所層級得票紀錄。七月研究的評估是「CSV 下載無 API」。
- **政治獻金／公職人員財產申報／中央及地方政府預算（民國 90–116 年）／政府採購標案（14,571,343 筆公告）**。

---

## **二、實測：它實際能做到什麼**

九個實際呼叫，全部在本次研究中執行：

| # | 查核情境 | 資料集 | 實測結果 |
| :---- | :---- | :---- | :---- |
| 1 | 公司是否真實登記 | `tw.gov.fia.eip~ref~business-tax` | 台積電 統編 22099131 ✓（全表 174 萬筆） |
| 2 | 「詐騙暴增」 | SEGIS 刑事案件發生件數 | 詐欺背信 2011 年 24,076 件 → 2025 年 **199,640 件**（8.3 倍） |
| 3 | 2018 北市長得票差距 | 中選會候選人＋得票數 | 柯 580,663／丁 577,096，差 **3,567 票（0.252%）**，與史實相符 |
| 4 | 「新住民暴增」 | SEGIS 外籍及大陸配偶 | 2008 年 413,163 → 2022 年 574,652，**+39.1%（年均 2.38%）** |
| 5 | 通膨 | 主計總處 CPI | 逐年年增率，資料至 **2025-12**（新） |
| 6 | 判決檢索 | 司法院 ES | 含「散布謠言」判決 2,676 筆，可按年聚合 |
| 7 | 立院議案／表決 | `ly.govapi.tw/v2` | 議案全文檢索 121,701 筆；表決紀錄可查 |
| 8 | 政府花費 | `budget.openfun.app` | line-item 含單價、數量、**預算書頁碼** |
| 9 | 廠商信用 | `pcc-api.openfun.app` | 拒絕往來廠商清單，資料至 **2026-09-18** |

### **2.1 一個完整的真實查核示範**

Cofacts 文章 `38unny1xofwbi`（陳文茜轉載文）主張：

> 「給台灣70%的人 住30年老房子」

以 `tw.gov.moi.segis~txn~tw-04-301020000g-030007.u01co`（房屋稅籍住宅類數量依屋齡區分）民國 114 年第 4 季（2025Q4）全國 22 縣市資料計算：

```
全國住宅稅籍總數   9,472,834 戶
屋齡 30 年以上     5,539,830 戶 = 58.5%
屋齡 40 年以上     3,601,091 戶 = 38.0%
加權平均屋齡       33.8 年
```

**查核結論：方向正確但數字誇大——實際為 58.5%，非 70%。**

這正是 Cofacts 最需要、而 Google Search 最難產出的那種輸出：一個有明確分母、可引用、可複算的百分比。出處 URL 是決定性的：`https://data.openfun.tw/datasets/tw.gov.moi.segis~txn~tw-04-301020000g-030007.u01co`

---

## **三、必要性：與 cofacts.ai 實際查核任務比對**

這是本研究最關鍵、也是結論最保守的一節。

### **3.1 資料來源與方法**

cofacts.ai 的 Langfuse 有 1,162 筆 trace。**查核標的不在 trace 的 user message**——大量 session 的第一則訊息是 `hi`（健康檢查），或僅一個 `https://cofacts.tw/article/...` 連結。真正的謠言全文在 `get_single_cofacts_article` observation 的 output 裡（共 477 筆該類 observation）。由此還原出**265 篇不重複的 Cofacts 文章**作為分析母體。

| 文章型態 | 篇數 |
| :---- | :---- |
| TEXT | 166 |
| IMAGE | 57 |
| VIDEO | 41 |
| AUDIO | 1 |
| （其中純連結無內文） | 39 |

### **3.2 主題分布（關鍵詞觸及，可複選）**

| 主題 | 篇數 |
| :---- | :---- |
| **醫療健康食藥** | **88** |
| 國際兩岸戰爭 | 65 |
| 其他／未分類 | 64 |
| 政治選舉立院 | 60 |
| 預算稅收採購 | 30 |
| 人口移民 | 22 |
| 治安犯罪詐騙 | 21 |
| 司法判決 | 11 |
| 物價薪資經濟 | 9 |
| 能源環境 | 6 |
| 房價土地 | 3 |

### **3.3 真正的命中率**

主題重疊不等於可回答。進一步篩出「數字 + 台灣統計類名詞相鄰」的文章：**31 篇／265 篇（11.7%）**。逐篇人工判讀這 31 篇後：

- **OpenFun 有任何可貢獻成分：約 13 篇（≈5%）**
- **OpenFun 是最佳可用來源、足以支撐查核結論：約 5–6 篇（≈2%）**

強命中案例（逐篇實查）：

| Cofacts ID | 主張 | 可用資料 |
| :---- | :---- | :---- |
| `38unny1xofwbi` | 「70% 的人住 30 年老房子」「60% 騎機車上下班」 | SEGIS 屋齡（已實測，見 §2.1） |
| `1ewd9v7qn1263` | 「65 歲以上人口持有 413 萬戶住宅，占全台將近一半」 | SEGIS 人口＋住宅 |
| `Qy3Imp4BEY7yIwhpsIuE` | 「越南人來唸大學 每學期補助學費4萬元 每個月生活費給1.5萬」 | 教育統計＋預算 |
| `W_X2uYsBAjOeMOkl_MJ8` | 「200億點餐平台」「生育率世界倒數第一」 | 預算／採購＋SEGIS 出生 |
| `2gbbunopfzts4` | 福懋油脂 1225、泰山 1218、福壽 1219 持股比例 | 上市公司基本資料 |
| `IC1zkJ4BEY7yIwhppX2y`、`qS1SlZ4BEY7yIwhpr4Mo` | 「65 歲健保補助金 3,224 元半年領一次」 | 法規／預算 |

**明確的反證**：大宗謠言型態 OpenFun 幫不上忙。88 篇醫療健康類（喝茶 vs 白開水、音樂治失智降 39%、80 歲七個老坑、黑心食物 top 10）需要的是醫學文獻與食藥署闢謠，不是政府統計。詐騙類多為對話截圖（賀利貸、信託資管帳戶），OpenFun **沒有**詐騙網站／帳號黑名單。政治類多為敘事與人格指控（蔣萬安履歷、蔡英文家族、1949 遷台史觀），不是可查的統計數字。

一個具體的能力邊界案例：`HjBVp6ABEY7yIwhpp5jG`「外勞來台生小孩 享盡台灣福利」。OpenFun **能**給產業及社福外籍勞工人數（2011 年 425,660 → 2024 年 724,805，+70.3%），但 `tw.nhi` 底下 13 個資料集全是**藥品與特材給付品項**，**沒有**外籍人士健保投保與使用統計。也就是說，OpenFun 給得出分母，給不出這則謠言真正爭議的分子。

### **3.4 命中率該怎麼解讀**

5% 不高，但這 5% 的性質值得注意：它們集中在**反移民、世代居住、福利濫用**這類政治後果最重、最容易被情緒帶動、而 Google Search 最弱的題材。這類主張的特徵是「引用一個聽起來像官方統計的數字」，而唯一有效的反駁就是把真正的官方統計算出來。§2.1 的 58.5% vs 70% 就是範例。

反過來說，若目標是提高 cofacts.ai 的整體查核品質，醫療健康（88 篇，佔比最高）的邊際效益遠大於本案。

---

## **四、與 Google Search 的邊際差異**

並非所有 OpenFun 查得到的東西都值得專門接：

| 類型 | Google Search | OpenFun | 邊際價值 |
| :---- | :---- | :---- | :---- |
| 2018 北市長差距 3,567 票 | 輕易命中 | 可算 | **低**（僅增加可驗證性） |
| CPI 年增率 | 輕易命中 | 可查 | **低** |
| 30 年以上屋齡佔比 58.5% | 無單一網頁陳述 | 需自行彙總 22 縣市 | **高** |
| 詐欺案件 2011–2025 完整序列 | 零散於新聞 | 一次算完 | **高** |
| 預算 line-item 含預算書頁碼 | 幾乎不可能 | 直接給 | **高** |
| 判決書逐年聚合 | 不可能 | 一次查詢 | **高** |
| 統編對公司名 | 不穩定 | 權威 | **高** |

**邊際價值集中在「需要跨單位彙總或聯結才得出、沒有任何單一網頁直接陳述」的衍生統計。** 這也正好是 §3.3 那 5% 的形狀。

另有一項與既有架構直接相扣的好處：[〈結構化出處完整性契約〉ADR](https://github.com/cofacts/ai/blob/main/docs/decisions/20260515-agent-source-integrity-contract.md) 記載 writer 曾因出處藏在敘事散文中而**從訓練記憶捏造「看起來比較乾淨」的 URL**。OpenFun 的出處 URL 是由 slug 決定性組成的（`https://data.openfun.tw/datasets/{slug}`），且 search API 的 entity 直接回傳可引用 URL，不經過 Vertex 轉址解析，比 Google grounding 的出處鏈更短也更穩。

---

## **五、技術可行性**

### **5.1 架構定位**

沿用既有 `AgentTool` 模式即可，且**必須**是獨立 subagent：`ai_investigator` 已掛 `google_search`，ADK 的 built-in tool 不能與 function calling tool 同掛一個 agent（`agent.py:764` 註解已載明）。

需注意成本：`ai_writer` 目前已掛 **10 個 tool**、instruction 約 **5,400 tokens**。再加第 11 個 AgentTool 會稀釋其注意力，這點七月研究的顧慮成立。

### **5.2 必須先做的 spike：code execution 與 function tool 能否併用**

這是整個提案唯一的技術不確定點，**本環境無 Gemini 憑證，未能實證**。可確定的是 ADK 端不阻擋：

- `BuiltInCodeExecutor.process_llm_request()` 是把 `types.Tool(code_execution=...)` **append 到 `llm_request.config.tools`**（`code_executors/built_in_code_executor.py`）。
- `code_executor` 是 `LlmAgent` 的**獨立欄位**，不在 `self.tools` 內，因此不經過 `canonical_tools()` 那條把 `google_search`／`VertexAiSearchTool` 自動包成 sub-agent 的 workaround（`agents/llm_agent.py:600`，ADK 1.26.0）。

所以 ADK 會照實送出同時含 `function_declarations` 與 `code_execution` 的 request，**能不能用取決於 Gemini 端是否接受**。實作第一步就該用 10 行 script 打一次真實 API 驗證。

若 Gemini 拒絕，有兩條乾淨的退路，都不影響本案價值：

1. **把運算搬進 tool**：多數彙總其實用不到 code execution——OpenFun 的 `/agg` 端點原生支援 `group_by` 與 `sum/avg/min/max`，立院 API 有 `agg` 參數，判決書是 Elasticsearch aggregation。§2.1 的屋齡計算可以寫成一個參數化的 Python function tool。
2. **拆成兩個 agent**：fetcher（function tool）＋ analyst（code executor），由 writer 或一個 SequentialAgent 串接。

### **5.3 其他元件皆已就緒**

- **Artifact**：`SaveFilesAsArtifactsPlugin` 已掛在 `App`，`artifact_service_uri` 已指向 GCS，`tool_context.save_artifact()` 已在 `agent.py:723` 使用中。存 `skill.md` 與下載資料進 artifact 沒有新工程。
- **`{content, sources}` 契約**：subagent 自行組出 sources 即可，不需要 grounding metadata，反而比 investigator 那條路單純。
- **stateless 呼叫**：AgentTool 每次呼叫都是全新單訊息 session（見 `writer_citations.py`），subagent 拿到的只有 writer 那一個 `request` 字串——prompt 要自足。

### **5.4 fetch tool 必須支援多 host**

**不能只允許 `data.openfun.tw`**。實測到的 base URL 至少五個：

```
data.openfun.tw/api/v1          # tinydb records / agg / search
ly.govapi.tw/v2                 # 立法院
budget.openfun.app/api          # 政府預算
pcc-api.openfun.app/api         # 政府採購
elastic-jud-data.api.openfun.dev # 司法院判決書（raw Elasticsearch）
```

token 對後四者的作用是解除流量限制（判決書則是必要認證）。tool 應以 **allowlist** 管控，而非開放任意 URL——後者等同給 agent 一個通用 SSRF 出口。

---

## **六、風險清單（全部為實測發現）**

按嚴重性排序：

1. **未知篩選欄位被靜默忽略（最嚴重）**
   `?不存在欄位=abc` 回傳 `total=1,738,008`（**全表**），沒有任何錯誤或警告。中文欄位名（`營業地址.縣市`、`行政區層級`）很容易拼錯，一旦拼錯，agent 會拿到全表並可能把它當成「篩選後的答案」。
   **對策**：prompt 強制要求先用回傳的 `schema` 驗證欄位名，並回報所下的篩選條件與 `total`，由 writer 與人類複核。

2. **零值假資料**
   SEGIS 外籍配偶資料集的 2019-12 記錄**存在**，但所有數值欄位都是 `0`（2018-12 = 541,409、2020-12 = 561,636）。天真的 agent 會產出「新住民在 2019 年歸零」或「年減 100%」——對查核平台是災難級錯誤。
   **對策**：時間序列必須做連續性檢查，全零期間視為缺漏而非事實。

3. **平均值不可加總**
   §2.1 的 `住宅平均屋齡` 若直接加總 22 縣市會得到 775.5「年」。必須以戶數加權（正解 33.8 年）。

4. **資料新鮮度落差極大**
   採購 2026-09、CPI 2025-12、刑案 2025、外籍勞工 2024、SEGIS 外籍配偶**僅到 2022**。查核回應必須標注資料期別，否則會用四年前的數字回答今天的謠言。

5. **官方文件本身有誤**
   `llms.txt` 的範例把統編 `04541302` 標為「台灣積體電路製造股份有限公司」，實查為**鴻海精密工業**（台積電為 `22099131`）。轉接 prompt 若要求 LLM「先讀 llms.txt」，就會把這個錯誤讀進脈絡。
   **對策**：prompt 明確聲明文件中的範例值僅供語法參考，任何事實一律以實際查詢結果為準。

6. **搜尋對用詞敏感**
   `q=移工` 回傳的是刑案嫌疑犯、實價登錄、爆竹煙火取締等雜訊；`q=外籍勞工`（官方用語）才命中。`q=全民健康保險` → 0 個資料集，`q=健保` → 20 個。
   **對策**：prompt 要求以官方正式用語檢索，並在失敗時換官方同義詞重試。

7. **欄位命名不一致**
   部分 SEGIS 資料集用語意欄位（`VN_CNT`＝越南配偶數），部分用不透明的 `FLD01`–`FLD71`，標籤只存在於回傳的 `schema` 裡。agent 必讀 schema，不可望文生義。

8. **無可觀測的 rate limit**：回應不含任何 `RateLimit` header，正式上線前需與歐噴確認配額。

**良性的一面**：失敗模式很乾淨——查無資料是 `total: 0, records: []`（不會給近似結果），錯 slug 是 HTTP 404 `{"error":"Dataset not found"}`，無 token 是 HTTP 401。不存在「看起來像有資料其實是瞎編」的中間狀態，這對防幻覺有利。

---

## **七、結論與建議**

### **可行性：高。** 
資料在、介面一致、認證單一、`skill.md` 100% 覆蓋且本來就寫給 AI 讀、ADK 既有的 AgentTool／artifact 基礎設施可直接沿用、出處 URL 比現行 Google grounding 更穩。唯一待驗的是 code execution 與 function tool 併用（§5.2），且有兩條不影響價值的退路。

### **必要性：有限但真實。**
以 265 篇實際 Cofacts 文章為母體，OpenFun 有貢獻成分者約 **5%**，能獨力支撐查核結論者約 **2%**。cofacts.ai 的實際流量由醫療健康（88/265）、國際兩岸敘事、詐騙截圖主導，這些 OpenFun 都幫不上忙。

**因此不建議照提案原樣做成一個功能齊備的「OpenFun 專家 subagent」**——為 2–5% 的命中率掛上第 11 個 tool、養一套多 host fetch 與八項風險的 prompt 紀律，投資報酬率不成比例。

### **建議：先做最小驗證，用真實命中率決定是否擴建**

1. **第一步（半天）**：spike Gemini 是否接受 code execution ＋ function calling。結果決定後續形狀，不決定要不要做。

2. **第二步（1–2 天）：做一個窄的 `tw_stats` FunctionTool，直接掛在 writer 上，先不做 subagent。**
   只包三件事：`search`（找資料集）、`records`、`agg`，全部限定 `data.openfun.tw`。不接 code execution、不接立院／判決書／預算。把 §6 的 1、2、3、5 四項風險寫進 docstring 與回傳值（例如回傳中一律附上實際套用的篩選條件與 `total`，偵測到全零期間就主動標示）。
   理由：在命中率只有 5% 的前提下，先付一個 tool 的注意力成本，比先付一個 subagent 的架構成本合理；而 AgentTool 的 stateless 特性也意味著 subagent 無法從對話脈絡受益，它的優勢主要在隔離 prompt，現階段還不需要。

3. **第三步：在 Langfuse 觀察**——這個 tool 的呼叫率、成功率，以及結果被引用進 `draft_factcheck_response` 的比率。七月研究已建議過同一個觀察指標。

4. **達標才擴建**：若引用率證實這條路有用，再升級為獨立 subagent，並依序接入判決書（`elastic-jud-data`）與預算（`budget.openfun.app`）——這兩個的邊際價值在 §4 表中最高，且是七月研究判定「工程量大而暫緩」、如今已被歐噴做掉的部分。

5. **與七月研究的關係**：本研究不取代它。165 涉詐清單、食藥闢謠、Google Fact Check Tools API 這三項對應到 cofacts.ai 最大宗的詐騙與醫療健康流量，**OpenFun 完全沒有涵蓋**，其優先序應在本案之上。歐噴補的是「政府統計與登記」這一塊，而那一塊在 Cofacts 的實際流量中是少數。

### **值得另外討論的一件事**

歐噴的 `skill.md` 模式（資料提供方維護 AI 使用說明，含「能／不能回答什麼」與行為約束）本身是個值得借鏡的介面設計。若 Cofacts 未來要把自己的資料開放給其他 AI agent 使用，這是現成的範本。

---

## **出處**

- **OpenFun API**：[llms.txt](https://data.openfun.tw/llms.txt)、[api-docs.md](https://data.openfun.tw/api-docs.md)，及各資料集 `skill.md`。所有數據均為 2026-09-17 實際呼叫所得。
- **查核任務樣本**：Langfuse（langfuse.cofacts.tw）專案 `cofacts.ai` 之 traces 與 observations，2026-09-17 取樣，共 1,162 筆 trace／477 筆 `get_single_cofacts_article` observation／265 篇不重複 Cofacts 文章。
- **架構背景**：[cofacts/ai `adk/cofacts_ai/agent.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/agent.py)、[`writer_citations.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/writer_citations.py)、[結構化出處完整性契約 ADR](https://github.com/cofacts/ai/blob/main/docs/decisions/20260515-agent-source-integrity-contract.md)
- **ADK 1.26.0 原始碼**：`agents/llm_agent.py`（built-in tool 包裝 workaround）、`code_executors/built_in_code_executor.py`（code execution 注入方式）
- **本 KB 先行研究**：[專業能力 Subagent：台灣專業資料庫串接可行性研究](./專業能力%20Subagent：台灣專業資料庫串接可行性研究.md)（[PR #10](https://github.com/cofacts/kb/pull/10)）、[境外敵對勢力與公民查核平台之防禦機制](./境外敵對勢力與公民查核平台之防禦機制.md)
