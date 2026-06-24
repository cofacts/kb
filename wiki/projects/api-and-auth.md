---
type: Project
title: "API 存取與驗證"
description: "Cofacts API 驗證機制的演進歷程：從早期登入政策討論、server-to-server HMAC 方案（已廢棄），到 API 存取管理研究與 TypeScript 型別化。"
tags: [cofacts, api, auth, typescript]
timestamp: "2026-06-25T00:00:00+08:00"
---

## 背景

Cofacts API 的驗證與存取控制經歷了數個階段，部分設計已廢棄，部分仍在規劃中。以下文件各自代表不同時期的思考。

## 文件脈絡

### [Research → 已決議] 回應登入討論

[src/research/login-method.md](../../src/research/login-method.md)（2017 年）

Cofacts 早期討論：使用者是否需要登入才能提交查核回應。
比較了兩個方案：
- **方案 1**：登入後才能回應，作者才能修改
- **方案 2**：匿名提交，登入後可修改他人回應（Wikipedia 模式）

**決議採方案 1**（登入必要，作者限定修改）。這是已落地的早期產品決定。

### [Design, Obsolete] API client management

[src/technical-design/api-client-management.md](../../src/technical-design/api-client-management.md)（已廢棄）

設計以 `x-app-id` + HMAC-SHA256 簽名的 server-to-server 驗證機制，以 YAML 檔管理用戶端清單。此文件標題已標注 **Obsolete**，代表該方案已被取代或未完整落地。

### [Research] API 存取管理

[src/research/api-access-management.md](../../src/research/api-access-management.md)（2025 年）

研究如何限制 Cofacts API 僅供已知服務使用，防止匿名請求耗盡伺服器資源。列出現有 1st party 用戶端（rumors-site、rumors-line-bot 等）及潛在接入方式。屬 CCPRIP [Op] 範疇的研究，尚無對應設計文件。

### [Design] TypeScript 導入

[src/technical-design/typescript-adoption.md](../../src/technical-design/typescript-adoption.md)（2023 年）

為 rumors-site 與 rumors-line-bot 導入 TypeScript，策略是以 GraphQL codegen 為資料流建立型別，優先從密集使用 API 的頁面與 handler 著手。rumors-site 的 GraphQL codegen 已完成（PR #500）。
