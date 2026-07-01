---
type: Project
title: "多媒體與文字轉錄"
description: "Cofacts 支援圖片、音訊、影片訊息的研究與設計歷程，從感知雜湊檢索研究到 OCR/STT 轉錄設計與群眾外包文字編輯。"
tags: [cofacts, multimedia, ocr, transcript, media]
timestamp: "2026-06-25T00:00:00+08:00"
---

## 背景

LINE 訊息不只有文字，Cofacts 需要支援圖片、影片、音訊的查核。這條線從早期的檢索技術研究，逐步演進為 OCR/STT 自動轉錄與群眾外包編輯的完整設計。

## 文件脈絡

### [Research] 多媒體支援研究

[src/research/multimedia-support.md](../../src/research/multimedia-support.md)（2024 年）

研究多媒體訊息的兩大技術面向：
- **檔案檢索**：以感知雜湊（perceptual hash）命名檔案，查詢時直接比對雜湊值找相同媒體
- **影片相似度搜尋**：研究大規模影片檢索技術（perceptual hash、vector search）

此為研究文件，探索技術可行性，後續是否直接對應到設計文件中的方案尚不確定。

### [Design] OCR 與 AI 轉錄

[src/technical-design/ocr-and-ai-transcripts.md](../../src/technical-design/ocr-and-ai-transcripts.md)（2025 年）

設計以 `airesponses` index 快取媒體 ID 與 AI 轉錄結果的對應：
- 音訊／影片：語音轉文字（STT）
- 圖片：OCR

當文章建立時，AI 轉錄結果會寫入文章的 `text` 欄位與群眾外包轉錄初稿。rumors-api 整合已完成（參見 [Langfuse observability](llm-integration.md)）。

### [Design] 群眾外包轉錄

[src/technical-design/crowd-sourced-transcript.md](../../src/technical-design/crowd-sourced-transcript.md)（2024 年）

設計以 Yjs（Y doc）+ Hocuspocus 實現的協作式文字轉錄編輯器：
- AI 轉錄作為初稿，使用者可在 rumors-site 上直接編輯
- 支援版本歷史，可 rollback（防破壞）
- `text` 欄位即時同步以支援全文搜尋與相似文章比對

建立在 OCR/AI 轉錄設計之上，兩份設計文件互相引用。
