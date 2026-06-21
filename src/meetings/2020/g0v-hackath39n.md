---
type: Meeting
title: "Cofacts Hackath39n 協作頁面"
resource: "https://g0v.hackmd.io/@mrorz/B1oRgyNjL"
tags: [cofacts, meeting]
timestamp: "2020-01-01T20:00:00+08:00"
---

---
tags: cofacts
---

Cofacts Hackath39n 協作頁面
=====

:::info
- g0v slack channel：`#cofacts`
- 🤝 實體地點：[Workis 工作是](https://goo.gl/maps/sooT5GW3greUnmtp9)
- [Proposal slides]()
- Chatroom https://meet.jothon.online/meet/channel/g0v-hackath39n/49
- 食物
:::

## Cofacts／闢謠做功德 :pencil: 

🙋 **小組長**：比鄰 @bil
💼 **今日任務**：參與 cofacts.g0v.tw/articles 資料庫編輯。
🙏 **徵求**：會上網查證訊息的人


跟新網站當好朋友
0523 特別任務：幫訊息按大拇哥：https://cofacts.g0v.tw/hoax-for-you
每則網路上的轉傳訊息，點進去後在左下角有大拇哥。(要點淺色的喔，深色的看起來很吸引人但那是不能點的詐騙按鈕，不對他不是按鈕)
向上的大姆哥表示回得還行
向下的大姆哥表示回得真爛
目標是有累積很多篇向上的大拇哥！！！！＝Ｄ

向上的大姆哥不用填理由，可以直接送出。(向下的要喔XD因為想要改進)


本日的Cofacts好朋友：
4000 
Ann 
Lin
Mg Lee 
afrazhao
nonumpa 
RR
MrOrz 
Bil
nobody

詳見 [**編輯入口**](http://beta.hackfoldr.org/cofacts/https%253A%252F%252Fhackmd.io%252Fs%252FSyMRyrfEl)。

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

- bil: 圈圈可以不用寫理由可能要明示一下
- nonumpa + bil:
  - upvote, downvote 會按到帶有數字的那個 ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_3900b6ed1d723662432c49adc62cf6b1.png)
  - nonumpa 表示 youtube ~~也是按有數字的那個~~ 只有一個 thumb up/down，所以不會按錯 ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_dbf598177fddc16e084505647cb8660f.png)

- mg:
  - related article 應該要可以點
    - mrorz: 對這是 bug
  - 他覺得右邊 sidebar 應該要有類似的回應可以用，是正確的嗎
    - bil:
      - 因為他第一眼左邊看到謠言，會以為右邊是回應，結果不是
      - 對編輯來說「其他謠言」可能沒有那麼重要
      - 不能點 + 搜尋也不能用，造成挫折（implementation not complete yet）
    - mrorz: 過去最下面才會有的 related article 放到右邊之後，可能會令人感到困惑其用途。我覺得可以觀察看看
  - 一開始進去的時候會不知道要怎麼找需要回應的文章
- bil
  - ~~Copy button 現在不會複製 reference~~ 誤會一場，是因為要多按一個 copy
  - I wanna know 按鈕是假的
    - mrorz: 那個按鈕應該也是個誤會，mockup 其實沒有
  - 現在不知道還有幾則沒回過、總共多少篇
    - mrorz: 會把總共多少篇放去 community builder
  - 無法知道特定主題的有幾篇
  - 希望把沒回過的放前面
    - mrorz: 應該可以提供「最少回應」排序選項，讓有興趣
  - 搜尋頁面也不會說有幾篇
    - 無法一眼即知包含「OOO」的文章有幾篇
    - bil: 這搭配只有「Load More」的 pagination，會讓使用者覺得 never end，看不到「盡頭」。
  - Infinite load 會無法分享 list page
    - 過去 list page 可以分享某一頁的 URL，其他人點進去時順序也會一致，可以說「請看第幾個」
      - orz: 因為以前 URL 會帶 cursor 所以就算有新的，也不會影響第幾個
    - 希望每一項上面會有數字，讓使用者知道看到哪裡了
      - orz: 數字（幾樓）比較常見於討論串，不過我們的每個文章順序可以換。
  - 點進文章之後出來會迷路
    - bil: 現在沒有「已讀」，點進去之後會忘記看到哪裡
    - orz: google image 一樣是 infinite load，不過會 highlight 最近選的項目。gmail 也會 highlight 剛才開的信。 ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_84dbf60327466a67edec8085de1391e1.png)
      - 最左邊藍色框框提示現在項目或剛才點開的信
      - 「上一頁」「下一頁」pagination 無法跳頁
      - 會提示共有幾頁
      - 整體較 compact 所以一次可以看比較多項目（不過在 mobile 上、一行可顯露的字比較少時，也會加高每個 item 增加露出資訊）

- mrorz
  - 搜尋時，排序是用時間而不是 relevance
    ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_460b52cb8103296179e9e0b80ec78b5e.png)
    

- nonumpa
    - url preview 太長，把[頁面](https://cofacts.g0v.tw/article/2oatyknm1fidc)撐爆了
    - 以登入狀態瀏覽有`回應`的文章，往下 scroll 的時候，會先看到`新增回應`的欄位，再往下才會看到`回應`。
        看到`新增回應`的欄位第一個直覺是沒有`回應`了（應該是被大部分網站訓練成這樣了），不知道大家會不會這麼覺得？
        - 也許把`新增回應`的欄位先縮小成一行，在有`回應`的時候，`回應`不會因為展開的`新增回應`欄位被擠出使用者瀏覽範圍
        - 或是直接把`回應`跟`新增回應`對調
        ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_9a34a5454278cfdfcb598ca59845c350.png)
        - 沒有登入的時候，往下 scroll 會馬上看到`回應`，不會有這個問題
        - orz: 正式版本是要點擊「新增回應」按鈕，才會展開編輯區塊～現在這個暫行版還沒有做到這個機制。
            > okok[name=nonumpa]
