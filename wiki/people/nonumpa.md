---
type: Person
title: "nonumpa"
description: "Cofacts 全端工程師，長期負責基礎設施維運、逐字稿功能、分析報表與安全防禦。"
tags: [cofacts, developer, infra, operations]
timestamp: "2026-06-16T00:00:00+08:00"
---

# nonumpa

## 角色與職責

nonumpa 是 Cofacts 的全端工程師，自 2020 年起持續參與專案開發。主要負責後端 API 功能開發、基礎設施維運與安全監控，並定期出席每週工作會議及線下小聚活動，協助場佈與設備支援（備用 Wi-Fi 機等）。

## 關注領域

- **基礎設施與維運**：研究 Elasticsearch 版本升級（v6 → v9）、Cloud Run 遷移後的穩定性追蹤、Cloudflare 健康檢查調整與 WAF 規則設定、伺服器 swap 與記憶體監控。
- **安全防禦**：偵測垃圾訊息帳號（takedowns）、分析 Cloudflare rate limiting 誤擋問題、調整 Discord 伺服器的反垃圾進入門檻。
- **逐字稿與 LLM 功能**：與 mrorz 合作追蹤 LLM based Topic Classifier 的 bug 修復與 benchmark 結果。
- **身分驗證架構**：為 cofacts.ai SSR 設計自訂 Authorization Code Flow（RS256 JWT + JWKS），並實作 BFF auth（HttpOnly cookie + SSR）。
- **分析報表**：參與 CCPRIP analytics 的 Opendata trend 與 LINE Bot usage 報表問題的追蹤。
- **url-resolver 優化**：對 url-resolver 的優化項目進行 benchmark，並準備 COSCUP 分享內容。

## 活躍時期

nonumpa 最早出現於 [20200513](../../src/meetings/2020/20200513.md) 的會議記錄。自 2025 年下半年起更密集參與每週工作會議，幾乎每次均出席，活躍至今（2026 年 6 月）。

## 代表貢獻（附引用）

### Elasticsearch 升級研究
自 2025 年 Q4 起主導 Elasticsearch 從 v6 遷移至 v9 的研究工作，包含在測試環境升級 Node.js 至 24、分析 breaking changes、撰寫遷移 SOP 文件供 coding agent 執行。

> [20251104](../../src/meetings/2025/20251104.md)：「[Infra] ElasticSearch v9 reindex 研究 [name=nonumpa]」
> [20260317](../../src/meetings/2026/20260317.md)：「migration SOP 文件 (for coding agent to execute migration) [name=nonumpa]」

### 自訂身分驗證流程（rumors-api）
為 cofacts.ai 設計 SSR 所需的 Custom Authorization Code Flow，採用 RS256 演算法產生短效期 code，並在 cofacts/ai 前端實作 BFF auth。

> [20260421](../../src/meetings/2026/20260421.md)：「nonumpa 提出了一個新的身分驗證流程，主要是為 `cofacts.ai` 的 SSR 設計一個客製化的 Authorization Code Flow」（[rumors-api#386](https://github.com/cofacts/rumors-api/pull/386)、[ai#25](https://github.com/cofacts/ai/pull/25)）

### Cloudflare 健康檢查與防火牆調整
主動分析伺服器誤報警報原因，建議調整 Cloudflare Health Check 的 `consecutive_fails` 設定以減少誤報；並在 2026/05/04 攻擊事件後發現 takedown CI 的 `validate-api` 因防火牆誤擋而損壞。

> [20251202](../../src/meetings/2025/20251202.md)：「應該調整看看 Cloudflare 的 alert，要持續一段時間再發 alert [name=nonumpa]」
> [20260616](../../src/meetings/2026/20260616.md)：「我發現 takedown ci 的 validate-api 好像也因為 5/4 防火牆誤擋事件的改動壞了」

### Cloudflare 惡意流量偵測
在 2025 年底發現伺服器日誌中出現異常 Rate limiting rule 觸發記錄，追查到根因為 Node.js 版本升級後 fetch 的 user-agent 字串改變，並提出修正規則條件。

> [20251229](../../src/meetings/2025/20251229.md)：「發現怪 log [name=nonumpa]」、「先改成 does not contain `node` [name=nonumpa]++」

### 垃圾訊息處理（takedowns）
持續審核並關閉 cofacts-takedown bot 產生的垃圾使用者下架 PR，包括 Dubai 相關、泰文垃圾帳號等。

> [20260526](../../src/meetings/2026/20260526.md)、[20260421](../../src/meetings/2026/20260421.md)：多筆 takedowns PR 由 nonumpa review 並關閉。

### Discord 反垃圾設定
啟用 Discord AutoMod 的「Mention Spam」與「Spam Content」預設規則，並調整伺服器驗證等級以提高進入門檻。

> [20260428](../../src/meetings/2026/20260428.md)：「AutoMod 開「Mention Spam」+「Spam Content」(discord 預設規則)」

### Langfuse score 修復（cofacts.ai）
修正 cofacts/ai 中 Langfuse score read fields 的問題。

> [20260526](../../src/meetings/2026/20260526.md)：「nonumpa 建立了一個 Pull request [[codex] Fix Langfuse score read fields](https://github.com/cofacts/ai/pull/67)」
