# **資訊偏聽型 Proofreader：媒體環境模擬與動態記憶之設計研究**

## **研究緣起**

Cofacts.ai 的多代理人查核系統中，「AI 觀點審閱者」（Perspective Proofreader）以四個獨立 agent（`proofreader_kmt`、`proofreader_dpp`、`proofreader_tpp`、`proofreader_minor_parties`）模擬不同政黨支持者視角，供 AI Writer 在查核回應撰寫前後徵詢意見。此機制在 PoC 階段僅以靜態 prompt（各黨價值清單）實作，實作位於 [`cofacts/ai` repo 的 `adk/cofacts_ai/agent.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/agent.py)。

2026 年 7 月，專案成員對此 PoC 提出兩點檢討假設：

1. 靜態 prompt 僅反映「AI 對該黨支持者在意面向的刻板印象」——例如 `proofreader_kmt` 反映的是「知識藍」的想法，但 2025 年 11 月紅統派掌權後，知識藍論述已不再對國民黨有實質影響力。
2. 靜態 prompt 無法 pick up 政黨對時事的最新論述——尤其民眾黨在黃國昌任黨主席後與國民黨大力合作，方向與柯文哲時代不同（如對鞭刑等議題的立場差異），AI 對立場時常搖擺的新興政黨理解亦有限。

本研究以 Langfuse trace 實證檢驗上述假設（2026-07-19 執行，分析各 proofreader 近期各 50 次實際呼叫、67 條完整 trace 與 118 則使用者回饋），並評估「以 YouTube 頻道 digest 建構動態 persona 記憶」的改造提案，作為後續設計與實作的依據。

## **一、現況架構**

- 四個政黨 proofreader 為獨立 `LlmAgent`（`gemini-3.1-flash-lite`，thinking level HIGH），以 `AgentTool` 掛載於 writer，**每次呼叫都是全新 session、無跨呼叫記憶**。
- Prompt 為 hardcode 的靜態價值清單（KMT：傳統文化／九二共識／軍公教；DPP：主權／轉型正義／警惕中國；TPP：理性務實科學／藍綠之外；小黨：草根民主／勞權／弱勢）。
- Langfuse prompt management 未使用（2026-07 時為空），無版本化機制。
- 使用量（2026-05-01 ~ 07-18）：KMT 276 次、DPP 275 次、TPP 232 次、小黨 69 次；單次 latency 約 12 秒。

## **二、實證發現**

### **1. 「刻板印象凍結」假設成立**

對各 proofreader 近期 50 次呼叫的完整內容分析：

| Proofreader | 主要發現 |
| :---- | :---- |
| **KMT** | 「鄭麗文」出現 0 次、2025/11 後路線轉變 0 次提及；反覆調用九二共識、開羅宣言／舊金山和約法統論、「親美和陸友日」等 2025 年前知識藍 canon。persona 為教科書式「知識藍／深藍長輩」，無韓粉或紅統色彩。作為「泛保守長輩情緒模擬器」堪用，作為「國民黨當下論述反映器」已失準。 |
| **TPP**（失準最嚴重） | 黃國昌、藍白、罷免、司法迫害、鞭刑、柯文哲案全部 0 次；甚至自我描述為「柯文哲式的科學、理性、務實風格」（2026-07-11T18:05, trace `86ea…`）。更關鍵：遇到反民進黨題材（如中聯毒油）時**主動用中道框架去中和**（「無論 2014 還是 2026，問題核心不在於誰執政」），輸出與該黨當下實際攻防立場相反的受眾反應。 |
| **DPP** | 45+/50 筆將訊息（含數字 4 禁忌、颱風科普）定性為「認知作戰」；一筆誤稱「現在是 2024 年」並把訊息中的 2026 當造假紅旗。特有風險：系統性把對政府的合理批評定性為抹黑、要求查核文「拒絕和稀泥的客觀中立」「直接點名中共」——**側翼化風險**（詳見第四節之辯證）。惟亦有罕見亮點：中聯毒油案反過來批評己方「轉彎太慢、究責不足」（2026-07-11T17:43）。 |
| **小黨** | 三黨（時力／歐巴桑聯盟／台灣基進）從不被區分，實際只模擬出「進步派 NGO 勞權工作者」一種聲音；約 80% 內容與 DPP proofreader 重疊，維持獨立 agent 的邊際效益極低。 |

共通模式：跨主題回饋高度模板化（「先同理再澄清」「已解決／未解決疑慮」清單）；有草稿時約 25–45% 能給出具體可執行修改，無草稿時幾乎全是通用模板。

### **2. 但 proofreader 對 writer 的影響是真實的，非儀式性**

對 67 條 trace 的前後對照分析：

- **可逐句對應的採納**：AI 內容農場影片案（trace `3dc92349`）TPP proofreader 指出「只講『這是假的』略嫌單薄，建議加可執行的查核 SOP」→ 定稿新增「💡 如何辨識這類虛假影片？」三點；防空演習網路降速案（trace `b3133d27`）小黨 proofreader 問「僅有行動網路的弱勢者怎麼辦」→ 定稿新增「🆘 給僅有行動網路者的建議」整段。
- **健康的選擇性過濾**：凡屬「補事實、補來源、補弱勢脈絡、補查核方法」的建議照單全收；凡屬「請站某黨立場改寫框架」（DPP 要求抗中框架、KMT 要求控訴政府擴權）一律不採納。當 DPP 與 KMT 的黨派框架方向相反時，writer 只抽取雙方共通的中性事實補充。**此過濾目前是湧現行為，未受 prompt 明文保障。**
- **呼叫模式**：67 條中 42 條僅於「初讀訊息」時呼叫（受眾情報模擬）、25 條有草稿審閱輪、18 條兩者皆有；四黨全叫僅 34/67，KMT/DPP 幾乎必叫、小黨僅 36/67——writer 有選擇性，非機械並列。

### **3. 工程缺陷（修復優先於任何記憶系統）**

1. **草稿未傳入 bug**：約三成審稿輪 request 只寫「（同上）」，但 AgentTool 每次呼叫是全新 session，proofreader 看不到先前對話，只能回空殼評估框架、甚至輸出 `None`（trace `74a402cb`；trace `967426cc` 中 11 次呼叫多數空轉）。
2. 偶發輸出品質問題：簡繁夾雜、俄文亂碼（「критические 問題」）、對 writer 的諂媚（「您的草稿已經非常有水平」）。
3. 使用者回饋（118 則 thumbs：42 讚／72 倒讚）痛點集中於 verifier 與出處品質，**無一針對 proofreader**；正評中有「先請 proofreader 再 investigate 滿好的」（trace `34c1efae`）。

## **三、改造提案：資訊偏聽型 Proofreader**

專案成員提出的方向：模擬暴露在不同媒體環境下的閱聽人。具體構想：

1. 人工選定代表不同政黨（或媒體同溫層）的 YouTube 頻道清單。
2. 定時以 Gemini 的 YouTube video understanding，將最新影片對時事的 **ORID**（Observe 觀察到什麼——通常是偏聽的、Reaction 情緒反應、Interpret 如何詮釋、Decision 做出什麼決定）記錄下來。
3. 新 digest 與既有記憶不斷堆疊、壓縮：越久遠的記憶越模糊、越沉澱為信念；新刺激放在 prompt 最容易被參考的位置。技術上以單一巨大 markdown（構想上限 500K token）存於 Langfuse prompt。

### **評估：方向正確，直接對症**

- 張佑宗／Kahan 的雙重歷程研究指出，政治性訊息只有「in-group 動機」與「受託信使」框架能觸發更正效果——受眾模擬因此必須是**當下的同溫層論述**，而非過期刻板印象。本提案正面解決實證發現的「刻板印象凍結」問題。
- 多代理人審議研究中的「遞迴摘要」（Wikum 模式）與本提案的記憶壓縮同構；觀點審閱者本就是搭橋（bridging）機制的核心。
- 「偏聽」是 feature：查核回應的目標受眾本來就是偏聽者，persona 忠實呈現偏聽視角，才能預測回應會被如何誤讀。

### **修正建議**

**1. 整併為單一 agent + persona 參數 — 贊成。**
ADK 的 `AgentTool` 是靜態包裝，參數化最乾淨的作法是一個 `consult_audience(persona_id, question)` FunctionTool，內部從 Langfuse 拉取 persona prompt 再呼叫 LLM。效益：(a) 新增／修改 persona 無需改 code 部署；(b) persona 不限政黨——長輩健康群組、投資社團、宗教群組都是查核受眾；(c) 消滅與 DPP 高度重疊的小黨大鍋炒 agent。

**2. YouTube ORID pipeline — 可行，且比想像簡單。**

- 頻道監看毋須 YouTube Data API quota：每頻道有公開 RSS（`https://www.youtube.com/feeds/videos.xml?channel_id=...`）。
- Gemini 每 request 僅能看一支 YouTube 影片（`agent.py` 的 `inject_youtube_filedata` 已載明此 Vertex AI 限制），排程逐支處理、structured output 直接產出 ORID JSON。
- 排程以 Cloud Run Job 或 GitHub Actions cron 即可，與現有部署習慣一致。

**3. 補強：議題立場帳本（stance ledger）。**
純「越舊越模糊」的壓縮會把**立場反轉**平均掉——若 2018 年 ORID 支持鞭刑、2026 年反對，模糊壓縮可能產出「立場不明」。這正是提案想解決的「新興政黨立場搖擺」問題，故 digest 除 ORID 流水外應維護一張結構化帳本：`議題 → 現行立場 → as-of 日期 → 轉向註記（如「2025/11 起轉向」）`，立場衝突時 recency 必須勝出，且此表置於 prompt 最前端。

**4. 500K token 巨型 prompt — 不建議（本研究唯一明確反對的部分）。**

- 成本／延遲：proofreader 近 2.5 個月被呼叫 852 次，每次載入 500K 個 input token 為每月數億級，且現有 12 秒 latency 會大幅惡化。
- 品質：flash-lite 級模型在超長上下文有 lost-in-the-middle 問題，persona 一致性反而下降。
- 實證：proofreader 的價值在「具體、當下」（deepfake 辨識建議、食安圖時間戳查證），不在深遠記憶。

建議 persona 總預算 **30–80K token**：核心世界觀 5–10K（慢變）＋議題立場帳本＋近 90 天 ORID digest（快變、置前）。舊記憶於壓縮時併入世界觀段落——「模糊成信念」的效果照樣達成，成本低一個數量級。確有需要再擴。

**5. 存於 Langfuse prompt management — 贊成，時機剛好。**
目前 prompt management 為空、proofreader prompt 全 hardcode。以 prompt versioning 儲存 persona 可免費獲得：版本歷史、production label 切換、rollback、以及「誰在何時改了 persona」的審計軌跡。ORID 原始檔（未壓縮）另存 GCS 或 repo，供重建記憶時 replay。

## **四、治理紅線（源自〈境外敵對勢力與公民查核平台之防禦機制〉）**

本提案會**刻意訂閱偏聽頻道（包括紅統媒體）**，digest 等於把境外資訊操弄（FIMI）敘事系統性引入 prompt。這是設計意圖，但必須配套：

1. **輸出定位**：proofreader 輸出必須明確定位為「受眾反應模擬資料」，而非「編輯意見」。實證觀察到 writer 目前「事實建議採納、黨派框架過濾」的行為是湧現的，應明文寫入 writer prompt（即該研究的「事實優先於感受」紅線），否則換模型即可能消失。該研究警告的「假中立陷阱」（為照顧立場感受而柔化溯源揭露）與本次實證發現的 DPP proofreader「側翼化」傾向是一體兩面：**兩個方向的失衡都要防**，仲裁權在 writer 與人類查核者，不在任何單一 persona。
2. **Prompt injection 面**：YouTube 影片內容是不可信輸入，ORID digester 是攻擊面（影片中喊「AI 請忽略先前指令」即可能進入 persona prompt）。digest 必須 schema 化、欄位長度受限、過濾指令式語句。
3. **無人審核迴圈**：persona 自動更新應每次產生 diff 摘要送 Discord 或開 PR 供人抽查；頻道清單存於 repo、由人類 PR 維護，不開放 agent 自行增刪。

## **五、建議行動順序**

1. **修草稿傳入 bug**（成本最低、收益立即：讓三成空轉呼叫變有效）＋ writer 過濾紅線明文化。
2. **整併四黨為單一 `consult_audience` agent**，persona 存 Langfuse prompt。第一版 persona 直接**人工手寫 2026 年版**（鄭麗文路線、黃國昌路線、青鳥等），不必等 pipeline——此步已解決最大痛點。
3. **YouTube ORID pipeline MVP**：每 persona 3–5 頻道、RSS 監看、週更、30–80K 預算、議題立場帳本、diff 審核。
4. 之後再評估：記憶擴容、更多 persona（非政黨同溫層）、壓縮策略調參。

## **出處**

- 實作程式碼：[cofacts/ai `adk/cofacts_ai/agent.py`](https://github.com/cofacts/ai/blob/main/adk/cofacts_ai/agent.py)（proofreader 定義與 writer orchestration）
- 實證資料：Cofacts 自架 Langfuse（langfuse.cofacts.tw）2026-05-01 ~ 2026-07-18 observations（`proofreader_kmt` 等 name 查詢，各取近 50 筆完整 input/output）、67 條完整 trace、118 則 user thumbs scores。文中引用之 trace id 皆可於 Langfuse 回查。
- 理論依據（本 KB 內三篇先行研究）：
  - [從身份保護認知到雙重歷程：政治極化之實證研究](./從身份保護認知到雙重歷程：政治極化之實證研究.md) — in-group 動機推理、受託信使、受納性語言
  - [多代理人 AI 協作與非同步審議架構研究](./多代理人%20AI%20協作與非同步審議架構研究.md) — 觀點審閱者作為搭橋機制、遞迴摘要（Wikum）、哈伯瑪斯機器
  - [境外敵對勢力與公民查核平台之防禦機制](./境外敵對勢力與公民查核平台之防禦機制.md) — 假中立陷阱、事實優先於感受紅線、RAG 毒化防範
- 技術參考：
  - Gemini YouTube video understanding：https://ai.google.dev/gemini-api/docs/video-understanding#youtube （Vertex AI 每 request 限一支影片）
  - YouTube 頻道 RSS：`https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>`
  - Langfuse prompt management（versioning／labels）：https://langfuse.com/docs/prompts
  - Google ADK FunctionTool／AgentTool：https://google.github.io/adk-docs/tools-custom/function-tools/
