---
type: Person
title: "mrorz（orz）"
description: "Cofacts 真的假的專案的技術負責人，自 2017 年起主導系統架構設計、後端開發與維運，並長期擔任週會主持人。"
tags: [cofacts, people, developer, tech-lead]
timestamp: "2026-06-16T20:00:00+08:00"
---

# mrorz（orz）

GitHub 帳號為 `MrOrz`，在社群中亦以 `orz` 稱呼。Cofacts 真的假的的創辦成員之一，自 2017 年專案草創期至今持續擔任技術核心角色。

---

## 角色與職責

- **技術負責人（Tech Lead）**：負責系統整體架構決策，包含 API、資料庫、LINE bot、前端網站與基礎設施（infra）。
- **週會主持人**：長期主持每週例行會議，大多數會議記錄均存放於 `@mrorz` HackMD 帳號下。
- **大松坑主**：在多屆 g0v 大松（如 hackath27n、hackath66n 等）擔任開發坑主，招募工程師協作。
- **內容品質制度設計者**：參與制定編輯回報機制（如訊息理由字數下限、回應排序規則等）。
- **法規與授權把關**：參與 CC BY-SA 授權條款、使用者條款、API client app 管理等政策討論。

---

## 關注領域

- **系統架構與維運**：Elasticsearch 版本升級、GCE 遷移、Cloudflare 快取與防火牆設定、GCP Committed Use Discount 規劃。
- **LINE bot 開發**：LIFF 流程、群組功能、多媒體訊息查核（圖片、影片）、AI 逐字稿整合。
- **AI 功能整合**：cofacts.ai 的多 agent 事實查核 pipeline（investigator → verifier → proofreader → writer）、Langfuse 追蹤、prompt 迭代。
- **開放資料與 API 授權**：確保開放資料授權規範完整，管理下游 API 使用者。
- **知識管理**：提出 Cofacts knowledge base（`cofacts/kb`）構想，利用 OKF 格式整合會議記錄與設計文件。

---

## 活躍時期

2017 年至今（持續活躍）。從專案命名（「真的假的」及 Cofacts 英文名稱討論）到 2026 年的 AI 查核工具，均可見其貢獻足跡。

---

## 代表貢獻（附引用）

### 專案奠基與命名

2017 年初在名稱討論中，mrorz 主張「真的假的」的精神在於「閱讀到奇怪轉傳訊息時腦內的第一個聲音」，並偏好 `srsly`、`ForReal` 等口語化英文名，最終支持 `Cofacts` 作為專案英文名稱，並完成 GitHub organization、LINE ID 及 g0v domain 的設定。
來源：[20170401](../../src/meetings/2017/20170401.md)

### 早期 API 與前端架構建立

2017 年 1 月會議的 actionable items 中，mrorz 負責改 API 與 DB 欄位、實作 mutation API、加入 `relatedArticle` GraphQL field、建立 Redux 架構與資料取得機制。
來源：[20170126](../../src/meetings/2017/20170126.md)

### 編輯回報品質機制

2019 年 1 月討論 LIFF 回報機制時，mrorz 提出訊息理由字數下限（15 字以下禁送、15-40 字警語）、禁止理由與訊息完全相同等規則，以提升編輯回報品質。
來源：[20190102](../../src/meetings/2019/20190102.md)

### CC BY-SA 授權與 API 管理

2021 年初推動 CC BY-SA 4.0 授權條款正式化，分網站、chatbot、開放資料三份條款，並規劃 API client app ID 管理機制，確保下游使用者符合授權要求。
來源：[20210120](../../src/meetings/2021/20210120.md)

### 多媒體支援架構設計

2022 年 1 月，mrorz 設計 Phase 0 多媒體支援方案：圖片與文字視為獨立 article，未來（Phase 1）引入 article group 概念，處理「同一文字配不同圖片」的傳播情境。
來源：[20220105](../../src/meetings/2022/20220105.md)

### GCE 遷移與基礎設施優化

2026 年 3 月完成 GCE migration，並在 6 月設定 Cloudflare WAF 規則封鎖商業 SEO 爬蟲、新增 SSR HTML 快取規則，單週將 `site-tw` 對外流量從 12.1 GB 降至 3.1 GB（減少約 74%），並規劃 GCP Committed Use Discount 採購方案。
來源：[20260407](../../src/meetings/2026/20260407.md)、[20260616](../../src/meetings/2026/20260616.md)

### Cofacts knowledge base 構想

2026 年 6 月在週會中提出以 OKF 格式建立 `cofacts/kb` 知識庫，整合 HackMD 會議記錄與設計文件，讓記者採訪前可用 AI 自動彙整近況，並解決過去難以搜尋歷史資料的痛點。
來源：[20260616](../../src/meetings/2026/20260616.md)
