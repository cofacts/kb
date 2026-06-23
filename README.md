# Cofacts Knowledge Base

[Cofacts](https://cofacts.tw) 是台灣的開放原始碼事實查核平台，由公民志工社群共同維護。本 repo 是 Cofacts 的機構記憶庫，保存自 2017 年至今的週會記錄，以及從中提煉的結構化知識。

## 我想了解 Cofacts 是什麼

- [Cofacts 網站](https://cofacts.tw) — 查核資料庫與 LINE Bot 入口
- [wiki/projects/](wiki/projects/) — 各項計畫的背景、目標與演進脈絡
- [wiki/people/](wiki/people/) — 核心貢獻者的角色與專注領域
- [wiki/activities/](wiki/activities/) — 定期活動（小聚、大松）的辦理方式

## 我要查找過往記錄

週會記錄從 2017 年起，依年份存放於 `src/meetings/`：

```
src/meetings/
  2017/
  2018/
  ...
  2026/YYYYMMDD.md
```

每份記錄都有 `resource` 欄位，連回 HackMD 原始文件。也可以直接在 GitHub 介面搜尋關鍵字，或用 `git grep`：

```bash
git grep "關鍵字" src/meetings/
```

若某個主題跨越多次會議，`wiki/` 下會有對應的彙整頁面，並列出原始會議記錄的連結。

## 目錄結構

```
src/meetings/YYYY/YYYYMMDD.md   # 原始週會記錄（2017 – 今）
wiki/
  people/                        # 貢獻者
  projects/                      # 計畫與專題
  activities/                    # 定期活動
  index.md
```

`wiki/` 的內容由 AI agent 從會議記錄中提煉，經人工審閱後合入。

## 相關連結

- [Cofacts 網站](https://cofacts.tw)
- [HackMD 歷史會議記錄](https://g0v.hackmd.io/@cofacts/meetings)
- [Cofacts GitHub org](https://github.com/cofacts)

---

> 本 repo 的維護流程與 AI agent 規格：見 [AGENTS.md](AGENTS.md)、[CLAUDE.md](CLAUDE.md)
