---
type: Project
title: "CCPRIP — Cofacts Chatbot Platform Resiliency Improvement Plan"
description: "CCPRIP 是 Cofacts 用於規劃與追蹤平台長期改善工作的功能規劃框架，涵蓋維運、社群/溝通與基礎設施三大子類別。"
tags: [cofacts, ccprip, infrastructure, operations, community]
timestamp: "2025-11-25T00:00:00+08:00"
---

## 什麼是 CCPRIP

CCPRIP（**Cofacts Chatbot Platform Resiliency Improvement Plan**）是 Cofacts 用來統整平台長期改善計畫的功能規劃框架。最早於 [20220810](../../src/meetings/2022/20220810.md) 的會議記錄中以「長期方向」的形式出現，正式設計文件存放於 HackMD：https://g0v.hackmd.io/BRsJOevWSbyUMBSZEVVWrA。

CCPRIP 的目標是確保 Cofacts 查核平台在面對惡意使用、流量衝擊與技術債時，仍能維持穩定的服務品質，同時讓社群與內容功能持續演進。每週會議通常會在 CCPRIP 標題下追蹤各子項目的進展。

## 子類別

CCPRIP 下的工作項目以前綴標示所屬類別：

| 前綴 | 全名 | 說明 |
|------|------|------|
| **[Op]** | Operations（維運） | 防止平台被濫用、API 存取管理、自動下架等日常維運工作 |
| **[Comm]** | Community / Communication（社群／溝通） | 內容品質改善、AI 輔助查核、社群工具（如 cofacts.ai）、LLM 分類器等 |
| **[Infra]** | Infrastructure（基礎設施） | 伺服器穩定性、ElasticSearch 升級、部署架構改善、備援計畫等 |

## 重要里程碑（附引用）

### 2022 年：計畫起步

- **2022-08** — CCPRIP 以「長期方向」形式首次出現在會議記錄，連結至正式規劃文件。[20220810](../../src/meetings/2022/20220810.md)
- **2022-11** — 開始討論 Google Cloud 遷移提案（Proposal），正式列入 CCPRIP 議題。[20221109](../../src/meetings/2022/20221109.md)、[20221116](../../src/meetings/2022/20221116.md)
- **2022-12** — 確立三個優先追蹤項目：[Op] Anti-SEO spam、[Op] API client app management、[Comm] crowd-sourced transcript（影片眾包逐字稿）。[20221228](../../src/meetings/2022/20221228.md)

### 2023 年：基礎設施與維運強化

- **2023-01** — [Op] Anti-SEO spam 進入 M2–M4 實作階段；[Op] API client app management 開始朝向棄用 web app 的方向推進。[20230104](../../src/meetings/2023/20230104.md)
- **2023-02** — [Infra] Chatbot stability 列為獨立追蹤項目，分析 chatbot 不穩定成因（concurrency、bull.js/Redis dependency）；[Op] Anti-SEO spam 案例進入審查流程。[20230208](../../src/meetings/2023/20230208.md)

### 2025 年：AI 整合與自動化下架

- **2025-04** — [Op] Automatic takedown 機制上線：整合 OpenAI，透過 GitHub Pull Request 流程讓工程師審核後自動封鎖垃圾用戶。[20250417](../../src/meetings/2025/20250417.md)、[20250421](../../src/meetings/2025/20250421.md)
- **2025-05** — [Comm] cofacts.ai 列為新倡議，規劃 AI 輔助查核回應的工具；[Op] Automatic takedown 因 article 偵測 false positive 過多，暫停 article 偵測功能，改以發文頻率作為判斷依據。[20250512](../../src/meetings/2025/20250512.md)
- **2025-05** — [Op] API access management 推進至 step 2（Cloudflare rate limit 管理）；發現 `cofacts-api.g0v.tw` 等 g0v domain 無法納入 Cloudflare 管理。[20250512](../../src/meetings/2025/20250512.md)
- **2025-06** — [Op] Info security：啟動服務帳號遷移至 `cofacts.tw` email 的計畫，由 Johnson 負責執行。[20250604](../../src/meetings/2025/20250604.md)
- **2025-06** — [Comm] LLM based category classifier：以新 `cofacts/worker` repo（Cloudflare Workflows）實作週期性 LLM 分類，並將 17K 測資匯入 Langfuse dataset 進行實驗。[20250630](../../src/meetings/2025/20250630.md)
- **2025-09** — [Infra] deployment：為 `line-bot-zh`、`collab-server`、`langfuse` 等服務加上 `restart: always`，解決服務不自動重啟的問題（rumors-deploy #36）。[20250901](../../src/meetings/2025/20250901.md)
- **2025-09** — [Infra] 管理 API domain：`cofacts-api.g0v.tw` 303 redirect 設定完成（2025-09-13），所有流量改由 Cloudflare 管理。[20250916](../../src/meetings/2025/20250916.md)
- **2025-09** — [Infra] 移除 nginx：production 與 staging 改用 Cloudflare tunnel 取代 nginx，production 於 2025-09-28 完成切換。[20250930](../../src/meetings/2025/20250930.md)
- **2025-10** — [Infra] 降載計畫明確化：研究 ElasticSearch v9 reindex（支援 vector search）、Linode 遷移至 Compute Engine + Container-optimized OS、url-resolver 重寫。[20251021](../../src/meetings/2025/20251021.md)
- **2025-11** — [Infra] ElasticSearch v9 reindex 研究：直接從 v6 reindex 到 v9 觸發 OOM，需分次轉換；確認兩種 migration 方案（downtime 較長的 snapshot 載入 vs. downtime 較短的雙機切換）。[20251125](../../src/meetings/2025/20251125.md)

## 目前狀態

截至 2025-11 的持續追蹤項目：

- **[Op] 資訊安全**：服務帳號遷移至 cofacts.tw email（由 Johnson 負責，長期待辦中）。
- **[Op/Comm] Analytics**：Opendata article trend 超過 100MB 問題、LINE Bot menu & notification usage 報表損壞，尚未修復。
- **[Comm] cofacts.ai groundness check**：AI 查核出處驗證 agent 實作中，使用 Gemini API URL context；目前整合 Langfuse trace 的技術方案仍在研究。
- **[Comm] LLM based Topic Classifier**：bug 修復與 benchmark 結果持續追蹤中（nonumpa, mrorz 負責）。
- **[Infra] ElasticSearch v9 reindex**：非同步進行，需確認格式相容性與 API/DB code 是否需調整。
- **[Infra] url-resolver 重寫**：設計文件撰寫中（cofacts/worker#2），計畫整合 Gemini API URL context 取代現有 gRPC 架構。
- **[Infra] Linode → Compute Engine 降載**：規劃中，目標搭配 url-resolver 重寫一起進行。
- **[Infra] devops-manual**：`cofacts/devops-manual` 撰寫進行中（mrorz 負責）。
