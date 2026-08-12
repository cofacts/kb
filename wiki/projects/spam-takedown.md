---
type: Project
title: "垃圾訊息／詐騙集團下架處理"
description: "Cofacts 長期處理博弈廣告、詐騙集團等組織化垃圾帳號的手法演進：從人工辨識到 GitHub PR 下架自動化。"
tags: [cofacts, spam, takedown, moderation, fraud, seo-spam]
timestamp: "2026-08-12T00:00:00+08:00"
---

## 背景

Cofacts 從平台早期就持續有博弈廣告、詐騙集團等組織化帳號來洗版、打廣告或進行「二次詐騙」（假冒 165、反詐騙名義接觸受害者二次行騙）。這條線隨著攻擊手法演進，也逐漸從人工盤點發展成半自動化的下架流程，目前歸在 [CCPRIP](ccprip.md) 的 **[Op] Anti-SEO spam / Automatic takedown** 子項目下持續追蹤。

## 手法演進

### 2019–2021：人工辨識、拆解套路

- **[20190821](../../src/meetings/2019/20190821.md)**：提出辨識規則——`coordinated`（多帳號、註冊時間接近）與 `inauthentic behavior`（洗版內容類似）。
- **[20211229](../../src/meetings/2021/20211229.md)**：把詐騙套路拆解為「**養、套、殺**」三階段（攬客訊息 → 假客服話術 → 騙錢/騙個資），並開始按「是否要使用者付錢」（騙錢 vs 車手/帳號出租）分類處理。
- **[20220105](../../src/meetings/2022/20220105.md)**：「**二次詐騙**」正式成為固定處理類別。

### 2022：Schema 與封鎖機制上線

- [User blocking mechanism](../../src/technical-design/user-blocking-mechanism.md)（[20220131 前後](../../src/meetings/2022/20220112.md)）：`BLOCKED` 狀態上線，封鎖一個 userId 後其所有 `articleReply` / `replyRequest` / feedback 全部隱藏，且對已登出用戶依然有效（cookie 記錄 `isUserBlocked`）。
- [Anti SEO-spam mechanism](../../src/technical-design/anti-seo-spam-mechanism.md)（[20221019 起](../../src/meetings/2022/20221019.md)）：專門對付「拿 Cofacts 文章頁衝 SEO」的廣告／博弈站——文章 block 後對未登入者隱藏內文、頁面加 `noindex`、外部連結加 `rel="ugc"`，避免內容農場或博弈站靠 Cofacts 頁面提升排名。

### 2023：半自動盤點

- **[20230322](../../src/meetings/2023/20230322.md)**：用 Google Sheet 篩「判定之違規樣態＝二次詐騙 AND 處置＝block」拉出 spammer ID 清單，再定期用 API（`ListArticle` / `ListReplyRequest` / `ListReply`）抓這些人最新發文，屬於現行自動化流程的前身。

### 2024–2025：GitHub PR 下架自動化

- [Cofacts spam removal automation](../../src/technical-design/cofacts-spam-removal-automation.md)：現行下架機制。
  - `cofacts/takedowns` repo：每個要下架的 spam user 開一張 PR，記錄 userId 與理由，供多人 review、approve，全程留痕、免 SSH。
  - Admin API（`admin-api.cofacts.tw` / `dev-admin-api.cofacts.tw`）：PR merge 後由 GitHub Action 呼叫 `/moderation/blockedUser` 等 endpoint 執行實際封鎖。
  - **Phase 3 自動偵測**：GitHub Action 排程掃描新回應，用 LLM 判斷是否為「二次詐騙」或性內容，自動開 takedown PR；並用先前 PR 標題過濾已處理過的使用者，避免重複開票。
  - **[20250512](../../src/meetings/2025/20250512.md)**：因 article 偵測 false positive 過多，暫停對文章的自動偵測，改以「發文頻率」作為判斷依據。

### 2026：Discord 入口 + Cloudflare 防護

- **[20260421](../../src/meetings/2026/20260421.md)／[20260428](../../src/meetings/2026/20260428.md)**：Discord 提高進入門檻（AutoMod「Mention Spam」+「Spam Content」規則、驗證等級調至「高」），因為部分垃圾帳號也會滲透社群頻道。
- **[20260428](../../src/meetings/2026/20260428.md)**：抓到分散式 SEO 爬蟲鎖定大量博弈／廣告帳號的 `/user/[id]` 頁面（例如 `86betws`、`be5foodsupplement`）以及 `/search` 端點（Temu 商品 ID、SEO 推廣關鍵字），大量請求打爆 Elasticsearch。處理方式：Cloudflare WAF 對 `/user/*` 與 `/search` 開 **Managed Challenge**（非已知 bot 一律驗證）。

## 目前正在追蹤：博弈廣告集團（2026-08 起）

- **[cofacts/takedowns#310](https://github.com/cofacts/takedowns/issues/310)**（2026-08-01 開票，見 [20260804](../../src/meetings/2026/20260804.md)）：「**廣告帳號透過『假故事包裝＋工具/遊戲連結』洗版查核回應**」——用虛構故事包裝、夾帶工具或遊戲連結（含博弈站）大量洗版回應，是目前仍開著的觀察 issue。
- 同期持續有個別下架 PR（如 [#309](https://github.com/cofacts/takedowns/pull/309)、[#311](https://github.com/cofacts/takedowns/pull/311)），由 nonumpa review、merge。
- 2026-08：Johnson 整理博弈廣告集團與另一詐騙集團的資料（Google Drive），與此 issue 觀察到的模式相符，尚待比對是否為同一批帳號的延伸、並補開對應 takedown PR。

## 處理建議（沿用既有流程）

1. 兩個集團分開標記處理——博弈廣告與詐騙集團的樣態、話術不同，過去也一律分開歸類（詐騙集團走「二次詐騙」分類；廣告／博弈走 SEO-spam / 商業廣告分類）。
2. 把整理好的 userId／文章清單對照 `cofacts/takedowns#310`，判斷是否為同一批帳號的延伸，避免重複開票。
3. 逐一在 `cofacts/takedowns` 開 takedown PR（或交給既有 bot 自動生成），註明判定樣態。
4. 若帳號量大、有洗版特徵（短時間內大量新註冊帳號在多篇文章貼相似連結），評估是否要比照 2026-04-28 的做法，在 Cloudflare 對相關路徑加 Managed Challenge。
