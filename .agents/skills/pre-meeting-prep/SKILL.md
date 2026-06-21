---
name: pre-meeting-prep
description: >-
  準備 Cofacts 每週開會前的摘要：從本地 wiki 找到上次開會日期，抓取 Discord 三個頻道的訊息與 GitHub 活動，
  整理成 Markdown 摘要供貼入會議記錄。Use whenever the user says "幫我準備會議"、"prepare for meeting"、
  "整理上週發生的事"，或在會議開始前要彙整近況時請務必使用此 skill。
---

# Pre-Meeting Prep

從上次開會至今，整理 Cofacts 的重要活動，輸出可直接貼入 HackMD 會議記錄的 Markdown 摘要。

## 環境設定

先從 wiki 根目錄 source .env：

```bash
source .env
```

需要的變數：`HACKMD_API_TOKEN`、`HACKMD_API_URL`、`DISCORD_TOKEN`（若無 `DISCORD_TOKEN` 則略過 Discord 段落）。

## 步驟

### 1. 找到上次開會日期

列出 `src/meetings/` 目錄下所有 `.md` 檔，取最新日期：

```bash
ls src/meetings/**/*.md | sort | tail -2
# 取倒數第二個（最新的才是「上次」），若正在當週開會則取倒數第一個
```

從檔名取出日期（格式 `YYYYMMDD`），換算成 ISO 8601：`YYYY-MM-DD`。

### 2. 抓取 Discord 訊息

使用 Discord REST API，三個頻道各抓最多 100 則：

| 頻道 | 用途 |
|------|------|
| `1060178087947542563` | General |
| `1164454086243012608` | Server alerts |
| `1062999869314322473` | GitHub activities |

**計算 Discord snowflake**（用來篩選上次開會之後的訊息）：

```python
# Python 一行計算：將日期轉為 Discord after snowflake
import datetime
dt = datetime.datetime(YYYY, MM, DD, tzinfo=datetime.timezone.utc)
snowflake = int((dt.timestamp() * 1000 - 1420070400000)) << 22
print(snowflake)
```

```bash
curl -s -H "Authorization: Bot $DISCORD_TOKEN" \
  "https://discord.com/api/v10/channels/CHANNEL_ID/messages?limit=100&after=SNOWFLAKE"
```

從回傳結果中：
- 略過 bot 訊息（`author.bot == true`）
- 略過純表情符號或純 reaction 的訊息
- 若訊息包含 GitHub PR/issue 連結，之後在摘要裡附上連結

### 3. 抓取 GitHub 活動

用 `gh` CLI 搜尋 cofacts org 在上次開會後的 PR 與 issue：

```bash
# 合併的 PR
gh search prs --owner cofacts --merged --merged-after YYYY-MM-DD --limit 50 \
  --json title,url,repository

# 開啟的 issue（新建的）
gh search issues --owner cofacts --created YYYY-MM-DD..$(date +%Y-%m-%d) --limit 50 \
  --json title,url,repository
```

### 4. 整理摘要

產出格式如下（Traditional Chinese），最後包在 Markdown code block 裡方便複製：

````
```markdown
## 上週重點整理（YYYY-MM-DD ～ YYYY-MM-DD）

### GitHub 活動

**cofacts/ai**
- [PR 標題](PR URL)
- [PR 標題](PR URL)

**cofacts/url-resolver**
- [PR 標題](PR URL)

### Discord 重點討論

**General**
> @作者名：訊息內容（僅保留有資訊量的部分）

**Server alerts**
> @作者名：訊息內容
```
````

**整理原則：**
- GitHub：按 repo 分組，每個 PR/issue 一行，附標題與連結
- Discord：以引言（`>`）格式呈現，略去閒聊、略去純表情、保留有資訊量的技術討論或重要通知
- 若某頻道沒有新訊息，整個段落省略
- 摘要語言用繁體中文（標題、小節說明），引言保留原文
