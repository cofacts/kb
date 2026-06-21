---
name: post-meeting-summarize
description: >-
  Cofacts 每週開會結束後的收尾流程：產生會議標題、整理 action items（可建 GitHub issue）、
  把本次會議內容存入 wiki，並以下週待辦事項更新同一份 HackMD 會議記錄。
  Use when the user says "會議結束了"、"meeting ended"、"幫我收尾"、"summarize the meeting"，
  或任何開完會要整理記錄時請務必使用此 skill。
---

# Post-Meeting Summarize

開完會後的四步驟收尾：產生標題 → 整理 action items → 存入 wiki → 更新 HackMD 成下週模板。

## 環境設定

先從 wiki 根目錄 source .env：

```bash
source .env
```

需要的變數：`HACKMD_API_TOKEN`、`HACKMD_API_URL`、`MEETING_NOTE_ID`（本週開會用的 HackMD note ID）。

## 步驟

### 步驟 1：讀取目前會議記錄

```bash
curl -s -H "Authorization: Bearer $HACKMD_API_TOKEN" \
  "$HACKMD_API_URL/notes/$MEETING_NOTE_ID"
```

從回傳 JSON 取出 `content`（Markdown 全文）和 `publishedAt`（或從內文第一行的 `# YYYYMMDD 會議記錄` 取得日期）。

### 步驟 2：產生會議標題

標題格式：`<i>MMDD</i> Title1, Title2, ...`

**方法：**
1. 解析會議記錄中各 `##` 小節的標題與重點
2. 每個小節濃縮成 2–5 個字的關鍵詞（可參考 wiki `src/meetings/` 目錄裡過去的標題風格）
3. 以逗號連接，前綴加上 `<i>MMDD</i>`

**範例：**
若小節有 API bug 修復、影片轉錄實驗、CCPRIP 自動下架、Langfuse 設定、MyGoPen 連結問題、小聚籌備，則：
```
<i>0317</i> API bug修復、影片轉錄實驗、CCPRIP自動下架功能、Langfuse設定、MyGoPen連結問題、小聚籌備
```

產出標題後呈現給使用者確認，確認後用於步驟 4 更新 `src/meetings/index.md`。

### 步驟 3：整理 Action Items 並建 GitHub Issues

從會議記錄中找出所有 actionable items（checklist 項目、討論中提到要做的事）。

對於**需要開 GitHub issue 的項目**：
- 草擬 issue 標題與說明（body）
- 呈現給使用者確認，例如：
  ```
  準備建立 GitHub Issue：
  Repo: cofacts/ai
  標題: 自動為 session 命名
  內容: 在 session 結束後，用 LLM 自動生成有意義的標題。
  
  確認建立？(y/n)
  ```
- 使用者確認後執行：
  ```bash
  gh issue create --repo cofacts/REPO --title "標題" --body "內容"
  ```

### 步驟 4：將會議記錄存入 wiki

從會議日期（`YYYYMMDD`）決定存放路徑：`src/meetings/YYYY/YYYYMMDD.md`

建立檔案，frontmatter 格式如下：

```markdown
---
type: Meeting
title: "YYYYMMDD 會議記錄"
resource: "https://g0v.hackmd.io/@mrorz/NOTE_ID"
tags: [cofacts, meeting]
timestamp: "YYYY-MM-DDT20:00:00+08:00"
---

（此處貼上 HackMD 的完整 Markdown 內容）
```

其中 `NOTE_ID` 用 `$MEETING_NOTE_ID`。

存檔後，同步在 `src/meetings/index.md` 的當年度區塊（`## YYYY`）頂端新增一行：

```
- [MMDD Title1、Title2、...](./YYYY/YYYYMMDD.md)
```

### 步驟 5：以下週模板更新 HackMD 會議記錄

從本次記錄中**找出未完成的項目**（`- [ ]` 的 checklist），整理成下週的「上週待辦」清單。

草擬下週模板，結構如下：

```markdown
---
tags: cofacts, 
---

# YYYYMMDD 會議記錄

:::info
- [所有會議記錄](https://g0v.hackmd.io/@cofacts/meetings/x232chPbTfGgNL_Q0f47rQ)
- NPO Hub 出席：
- 線上出席：
- https://meet.google.com/mrz-dgrd-pri
:::

## 上週待辦

（從本次未完成事項移入，格式沿用 - [ ] / - [x]）

## General

## ...（其他本週預計討論的 sections）
```

**呈現草稿給使用者確認後**，再執行更新：

```bash
curl -s -X PATCH \
  -H "Authorization: Bearer $HACKMD_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$HACKMD_API_URL/notes/$MEETING_NOTE_ID" \
  -d "$(jq -n --arg content "$NEXT_WEEK_CONTENT" '{content: $content}')"
```

### 最後輸出

完成後列出本次執行的摘要：
- 步驟 4 存入的檔案路徑
- `src/meetings/index.md` 更新後的條目
- HackMD 已更新為下週（YYYYMMDD）模板
