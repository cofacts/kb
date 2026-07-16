---
name: pre-meeting-prep
description: 準備 Cofacts 每週開會前的摘要：從本地 wiki 找到上次開會日期，抓取 Discord 頻道的訊息與 GitHub 活動， 整理成 Markdown 摘要供貼入會議記錄。Use whenever the user says "幫我準備會議"、"prepare for meeting"、 "整理上週發生的事"，或在會議開始前要彙整近況時請務必使用此 skill。
---

# Pre-Meeting Prep

從上次開會至今，整理 Cofacts 的重要活動，輸出可直接貼入 HackMD 會議記錄的 Markdown 摘要。

## 環境設定

需要的環境變數：`DISCORD_TOKEN`（存放在 repo 根目錄 `.env`，可 `source .env` 取得；若無則略過 Discord 段落）。

## 步驟

### 1. 找到上次開會日期

先 `git pull` 確保本地 repo 是最新（會議記錄由 CI 自動 merge，本地容易落後），再列出 `src/meetings/` 目錄下所有 `.md` 檔，取最新日期：

```bash
ls src/meetings/**/*.md | sort | tail -2
# 取倒數第二個（最新的才是「上次」），若正在當週開會則取倒數第一個
```

從檔名取出日期（格式 `YYYYMMDD`），換算成 ISO 8601：`YYYY-MM-DD`。

### 2. 抓取 Discord 訊息（主要來源）

使用 Discord REST API，以下頻道各抓最多 100 則：

| 頻道 ID | 頻道名稱 | 用途 |
|---------|----------|------|
| `1060178087947542563` | general | 一般討論 |
| `1164454086243012608` | alerts | Server 通知 |
| `1062999869314322473` | 程式開發 | GitHub bot embed + 技術討論 |
| `1473244731487158566` | dev | 開發討論 |
| `1488774855141752932` | collab | cofacts.ai 協作討論 |

**計算 Discord snowflake**（用來篩選上次開會之後的訊息）：

```python
import datetime
dt = datetime.datetime(YYYY, MM, DD, tzinfo=datetime.timezone.utc)
snowflake = int((dt.timestamp() * 1000 - 1420070400000)) << 22
print(snowflake)
```

```bash
curl -s -H "Authorization: Bot $DISCORD_TOKEN" \
  "https://discord.com/api/v10/channels/CHANNEL_ID/messages?limit=100&after=SNOWFLAKE"
```

**解析訊息時，兩類都要處理：**

1. **人類訊息**（`author.bot != true`）：取 `content` 欄位，略過純表情符號或空白訊息
2. **GitHub bot embed**（`author.username == "GitHub"`）：取 `embeds[].title` + `embeds[].url`，保留關鍵事件（PR opened/closed/merged、release published），略過純 review comment（URL 包含 `discussion_r`）及 gemini-code-assist bot 訊息

### 3. GitHub 補充（選用）

若有頻道沒接 Discord webhook 的 repo，用 GitHub MCP tool 補查：

```
mcp__github__search_pull_requests: org:cofacts is:pr merged:>=YYYY-MM-DD
```

與 Discord embed 去重（同一 PR 不重複列出）。

### 4. 整理摘要

產出格式如下（Traditional Chinese），最後包在 Markdown code block 裡方便複製：

````
```markdown
## 上週重點整理（YYYY-MM-DD ～ YYYY-MM-DD）

### GitHub 活動

**cofacts/ai**
- [PR 標題](PR URL)（opened / merged YYYY-MM-DD）
- [release/YYYYMMDD](release URL)（released YYYY-MM-DD）

**cofacts/url-resolver**
- [PR 標題](PR URL)

### Discord 重點討論

**general**
> @作者名：訊息內容（僅保留有資訊量的部分）

**alerts**
> @作者名：訊息內容

**程式開發**
> @作者名：訊息內容

**dev**
> @作者名：訊息內容

**collab**
> @作者名：訊息內容
```
````

**整理原則：**
- GitHub 活動：按 repo 分組，每個 PR/release 一行，附標題與連結；標註 opened/merged 與日期
- Discord 人類訊息：以引言（`>`）格式呈現，略去閒聊、純表情，保留技術討論或重要通知
- 若某頻道沒有任何新訊息（包括 bot embed），整個段落省略
- 摘要語言用繁體中文（標題、小節說明），引言保留原文
