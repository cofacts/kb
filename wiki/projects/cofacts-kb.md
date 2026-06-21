---
type: Project
title: "cofacts/kb — Cofacts 知識庫"
description: "以 OKF 格式維護的 Cofacts 知識庫，將散落在 HackMD 會議記錄與 Google Docs 的知識整合為 Git repo，供 LLM agent 與人類查閱。"
tags: [cofacts, kb, wiki, okf, llm]
timestamp: "2026-06-22T20:00:00+08:00"
---

# cofacts/kb — Cofacts 知識庫

## 背景與動機

Cofacts 長期以來的知識分散於多個系統：
- `cofacts.tw/hack`：各種 notes、規則
- `g0v.hackmd.io/@cofacts/meetings`：歷屆會議記錄（2017 年迄今）
- `g0v.hackmd.io/@cofacts/rd/`：R&D 文件
- Google Docs：cofacts.ai design doc 等

主要痛點：
1. 很難找過去的決策脈絡（記者採訪前需要大量人工整理）
2. 很難寫新東西：寫在哪、HackMD MCP 只能一次編輯整個大檔案

## 架構決策

**2026/6/16** 會議決定建立本 repo（`cofacts/kb`），採用 [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) 規範：
- 開會時仍用 HackMD 共同編輯（維持即時協作體驗）
- 開完會後，會議記錄透過 skill 存入 `src/meetings/YYYY/YYYYMMDD.md`，並由 LLM agent 更新 `wiki/` 層
- HackMD 只保留單一「本週文件」，開完會後換成空白模板，供下週使用
- Visibility：全公開（與原始資料相同層級）；私密內容可另存 private repo（如 devops）

## 結構

```
src/meetings/YYYY/YYYYMMDD.md   # Layer 1：原始會議記錄（唯讀）
wiki/                            # Layer 2：LLM agent 維護的概念頁
  people/     # 貢獻者
  projects/   # 主題性專案
  activities/ # 定期活動（小聚、大松）
  index.md
```

## 來源

[20260616](../../src/meetings/2026/20260616.md)
