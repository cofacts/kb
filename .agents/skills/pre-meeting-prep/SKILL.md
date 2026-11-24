---
name: pre-meeting-prep
description: 準備 Cofacts 每週開會前的議程：讀當週 HackMD 會議記錄，彙整上次開會後的 Discord、GitHub 與（若有）使用者的 Claude session，依 HackMD 既有章節排好，確認後寫回 HackMD。Use whenever the user says "幫我準備會議"、"準備今天的會議"、"prepare for meeting"、"整理上週發生的事"，或在會議開始前要彙整近況時請務必使用此 skill。
---

# Pre-Meeting Prep

目標：產出一份「照當週 HackMD 章節排好」的議程，讓使用者直接貼上或由你寫回 HackMD。來源越多越好，但最後要收斂成會議上要講、要決定的事，不是活動流水帳。

## 環境

需要 `DISCORD_TOKEN`、`HACKMD_API_TOKEN`、`HACKMD_API_URL`、`MEETING_NOTE_ID`。先看環境變數（雲端 session 通常已設好），沒有的再從 repo 根目錄的 `.env` 載入（`[ -f .env ] && set -a && . ./.env && set +a`）。缺哪個就略過對應來源，最後說明略過了什麼。

## 步驟

### 1. 讀當週 HackMD 與上次會議

- `GET $HACKMD_API_URL/notes/$MEETING_NOTE_ID`，記下 `content` 與 `lastChangedAt`。章節（上週待辦、General、cofacts.ai…）就是輸出骨架。
- 上次會議：`git fetch origin main` 後 `git ls-tree --name-only origin/main src/meetings/YYYY/ | grep -E '/[0-9]{8}\.md$' | sort | tail -1`（本地分支常落後；檔名有非日期的如 `g0v-hackath*.md`，要濾掉）。讀它的 TODO 與待辦，用來對照「上週待辦」的進度、回答「某人上週有哪些 task」。

### 2. 收集來源（上次會議日之後）

**Discord**（`Authorization: Bot $DISCORD_TOKEN`，用 snowflake `after=` 篩日期）：

| 頻道 ID | 名稱 |
|---------|------|
| `1060178087947542563` | general |
| `1164454086243012608` | alerts |
| `1062999869314322473` | 程式開發（GitHub bot embed） |
| `1473244731487158566` | dev |
| `1488774855141752932` | collab |

- 每次最多 100 則；程式開發一週常超過，要用 `after=<最後一則 id>` 翻頁到底。
- 人類訊息取 `content`；GitHub embed 取 `title`、`url`、`author.name`（PR 作者，用來把 PR 分給負責人）。略過 `discussion_r` review comment 與 bot review。
- 同一個 PR 有 opened 又 closed 就視為已處理；開了又關的 issue（已搬走）跳過。

**GitHub**：Discord 沒涵蓋的 repo 才補查。

**使用者的 Claude session**（有 `mcp__claude-code-remote__list_sessions` 才做；使用者有 Dash 等儀表板也可參考，但以即時 list 為準）：
- `list_sessions(mine: true)`，取上次會議後有更新的；依 `parent_session_id` 把子 session 併到父 session 底下，一棵樹＝一個議題。
- 看 `post_turn_summary` 的 `needs_action`／`recent_action`；需要細節時 `list_events(kinds: ["result"])` 只讀結論文字（事件夾帶大量統計，別整包讀）。`get_session` 的 `external_metadata.artifacts` 有該 session 發布的 artifact 連結。
- 只接受受信任裝置的 session 讀不到，在輸出中註明，不要猜內容。

### 3. 依 HackMD 章節編排

- **上週待辦**：不改原文，只在項目下補 `- --> 進度` 一行；細節多的寫「細節下收（章節名）」再放到對應章節。
- 各章節用 h3 分議題。每個議題：一句現況 → 相關 PR／artifact 連結 → **要決定的事**（列選項與建議）。
- 有人負責一串 PR 時（例如 Lance、Yutin），拉成「### 人名：主題」，會議上會留時間給他們報告。
- 個人小待辦、self-review 的細節、純通知類訊息省略；只出現在個人信箱、儀表板的私人事項不放。
- **會議記錄是公開的**：資安事項不寫漏洞類型、受影響 API、回報者、修法，只寫「收到新回報，會後私下討論」加 private repo（如 cofacts/devops）的連結。

### 4. 確認後寫回

先把完整草稿給使用者看，依回饋修改。使用者同意後：
1. 再 GET 一次，`lastChangedAt` 有變就先合併別人的修改，不要直接覆蓋。
2. `PATCH $HACKMD_API_URL/teams/cofacts/notes/$MEETING_NOTE_ID`，body `{"content": ...}`（team note，個人 endpoint 會 403）。
3. 讀回來比對確認。
