---
type: Project
title: "LLM 整合"
description: "Cofacts 逐步將 LLM 引入查核流程的設計與研究歷程，從 ChatGPT 使用情境探索到 MCP server 與 Langfuse 可觀測性。"
tags: [cofacts, llm, chatgpt, mcp, langfuse, ai]
timestamp: "2026-09-22T17:01:00+08:00"
---

## 背景

Cofacts 的 LLM 整合分為兩個軸線：
1. **輔助查核者**：讓 AI 協助志工處理未查核的訊息、草擬回應
2. **可觀測性**：追蹤 AI 回應的品質與成本

以下為各階段的設計與研究文件，標注其性質。

## 文件脈絡

### [Research] ChatGPT / LLM 輔助事實查核

[src/research/chatgpt-or-llm-to-aid-fact-checking.md](../../src/research/chatgpt-or-llm-to-aid-fact-checking.md)

探索 LLM 在 Cofacts 流程中可扮演的角色，包括：
- 對尚未查核的訊息點出可疑點、提供 Google 搜尋關鍵字
- 協助志工批評並改寫查核回應（Reply critique）
- 自動分類訊息主題

此研究文件本身為 CCPRIP Community Layer 的一部分，並連結至 ChatGPT integration 設計文件作為實作依據。

### [Design] ChatGPT integration

[src/technical-design/chatgpt-integration.md](../../src/technical-design/chatgpt-integration.md)

上述研究的工程設計文件，說明 ChatGPT 整合的具體實作方式。

### [Design] Topic Classifier：從 BERT 到 LLM

[src/technical-design/jev-topic-classifier-evaluation.md](../../src/technical-design/jev-topic-classifier-evaluation.md)

Article category（主題標籤）自動分類的歷程與 Jev 可行性評估：

- 2021：`rumors-ai-bert` + 若水 ground truth，因需常駐 GPU host 而停用
- 2025：改以 LLM 實作，程式碼在 [cofacts/worker](https://github.com/cofacts/worker) PR #1 / #3，benchmark 未結案、尚未上線
- 2026：評估 Cloudflare Workers AI 的 `typesafe/jev`（每個 category 一題 noul，取得 calibrated 機率後訂 precision-recall gate）；
  同時決定**放棄 cofacts/worker 路線**——classifier 直接做在 rumors-api 的 `CreateArticle` / `CreateMediaArticle`，
  url-resolver 維持現有 gRPC 寫法

### [Design] Langfuse LLM observability

[src/technical-design/langfuse-llm-observability.md](../../src/technical-design/langfuse-llm-observability.md)

部署 Langfuse 於 `langfuse.cofacts.tw`，提供 LLM 呼叫的追蹤與視覺化：
- 每個 git repo 對應一個 Langfuse project
- 帳號限 cofacts.tw email
- rumors-api（AI reply & transcripts）與 takedowns（AI 分類器）已完成整合（DONE）
- rumors-line-bot 整合尚待規劃（TBA）

### [Design] Cofacts MCP Server

[src/technical-design/cofacts-mcp.md](../../src/technical-design/cofacts-mcp.md)

設計 Remote MCP server，讓 AI agent（Claude.ai、Claude Code、Cursor 等）能以真實使用者身份存取 Cofacts API：
- 查核者可在 Claude 對話中搜尋、彙整並提交查核回應
- 採用 OAuth 2.1 + PKCE，不綁定特定 client
- 現況實作：[rumors-api#389](https://github.com/cofacts/rumors-api/pull/389)
