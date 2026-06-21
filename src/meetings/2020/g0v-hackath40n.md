---
type: Meeting
title: "Cofacts Hackath40n 協作頁面"
resource: "https://g0v.hackmd.io/@mrorz/S1DC5sNxD"
tags: [cofacts, meeting]
timestamp: "2020-01-01T20:00:00+08:00"
---

---
tags: cofacts
---

Cofacts Hackath40n 協作頁面
=====

:::info
- g0v slack channel：`#cofacts`
- 🤝 地點：大會議室
- [Proposal slides]()
:::


:::success
- 阿爪 [修 bug](https://github.com/cofacts/rumors-site/pull/297/files)
- peter 研究 image matching
- stimim 研究 [youtube scraping](https://cofacts.org/article/39n5zi0t4vlci)
- Sam 神速翻譯 x 4
- https://docs.google.com/document/d/1xwOCZPkkoYJdRxmIeW29-Nqa4PAk8llFMi2FtYh7z4A/edit
- 4000,, uienwt, TJacky, Lin, MrOrz 闢謠
https://cofacts.github.io/community-builder/#/bignum?start=2020-07-25T10%3A00&panels=replied&panels=feedback
:::



## Cofacts／標籤按讚做功德 :pencil: 

🙋 **小組長**：比鄰 @bil
💼 **今日任務**：參與 cofacts.g0v.tw/articles 資料庫編輯。
🙏 **徵求**：會上網查證訊息的人

想跟大家一起來做下面三件事情——

### :one: 回應「等你來查」的訊息
在「等你來查」專欄找到自己有興趣的訊息，進行回應。

https://cofacts.g0v.tw/hoax-for-you

跟新網站當好朋友，有任何問題歡迎提出 :D

### :two: 幫寫得好的回應按讚 :thumbsup: 

最新查核列表：https://cofacts.g0v.tw/replies

每則編輯所寫的回應，點進去後在左下角有大拇哥。
向上的大姆哥 :thumbsup: 表示回得還行
向下的大姆哥 :thumbsdown: 表示回得真爛
目標是有累積很多篇向上的大拇哥！！！！＝Ｄ :thumbsup: :thumbsup: :thumbsup: 

向上的大姆哥不用填理由，可以直接送出。(向下的要喔XD因為想要改進)

### :three: 試用「主題」分類

善用「主題」分類，找到有興趣回應的訊息吧！
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_0c7b068a671c87c6dfd9268756a829e9.png)

:book: 分類列表與定義：https://g0v.hackmd.io/D4KfdMRWS-OmCKd-Fhli2Q

:new: 徵求 Feedback：
    - 分類裡有沒有自己有興趣的主題
    - 目前主題分類的準確度
    - 標記分類的 UI 好不好用

:::info
詳見 [**編輯入口**](http://beta.hackfoldr.org/cofacts/https%253A%252F%252Fhackmd.io%252Fs%252FSyMRyrfEl)。
:::

- - -

## Cofacts／寫 code 做功德 :computer: 

🙋 **小組長**：Johnson @MrOrz
💼 **今日任務**：Good first issues。請見：

- Website (NextJS, ReactJS) https://github.com/cofacts/rumors-site/labels/good%20first%20issue
- LINE bot (NodeJS): https://github.com/cofacts/rumors-line-bot/labels/good%20first%20issue
- API server (NodeJS) https://github.com/cofacts/rumors-api/labels/Good%20first%20issue


🙏 **徵求**：React.js 開發者、Node.JS 開發者

* * *

# 協作區

https://cofacts.org/article/1ukd8kgp0q9f9

> 需要一個搜尋
> 看到 covid-19 --> 超長一個 list 找半天
> 要一起標醫藥的時候真的很遠
> [name=mrorz]
> 我標了十篇 捲來捲去有點累
> 但情境不太一樣
> 如果是編輯的話，查完順手一篇應該還好
>
> 「目標編輯」第一次、第二次是有用的資訊，之後就還好
> 可以把 AI 用的那幾個放到最後面
> github 加 label 時可以打 prefix 過濾
> ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_a95e9ee5b28a6194e91ee8b0c065f9f3.png)
> [name=ggm]
> 有一行的 description
> edit labels 可以看完整列表，我們這裡不能編輯那可能是 show more
> [name=mrorz]
> 
> 還需要：
> Hide obsolete categories
> [name=mrorz]


mrorz
4000 會怎麼使用 Cofacts UI 找訊息呢

4000
可疑訊息按下去
看哪個是 0 就點哪個

mrorz
「等你來答」呢

4000
不知道差異在哪裏

mrorz
(一些解釋)

:::info
「等你來答」分區並不直觀
:::

> 一頁 10 個好少⋯⋯以前更多（25 則）
> [name=mrorz]
> 

4000:
懷念進度條

orz
進度條在手機版
但進度卻要滑鼠移上去

:::info
桌面版的進度條沒實作
:::

4000
想要在文章列表看到網址預覽
看標題就好，不用內文
現在每一個 item 大小覺得可以，但空的地方可以塞標題

---

跟 stimim 討論 youtube 擋住我們的問題
https://cofacts.org/article/39n5zi0t4vlci

stimim:

可以用 `get_video_info` 試試看

player_response=<JSON>

JSON.videoDetails.title, JSON.videoDetails.shortDescription

orz
lambda?

----

4000
現在「等你來答」好像消不完

![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_095b520f8e09468e31968ec08dc2a580.png)