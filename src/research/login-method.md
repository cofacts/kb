---
type: ResearchDoc
title: "【真的假的】回應登入討論紀錄"
resource: "https://hackmd.io/RUhkiEYMSRSAcjUIZ0v4sA"
tags: [cofacts, research]
timestamp: "2017-03-22T16:44:00+08:00"
---

【真的假的】回應登入討論紀錄
======

對於「回應」一篇文章(謠言)
究竟該不該讓使用者登入呢？

## 方案 1：使用者登入後方可回應文章

* 只有作者可以修改 reply
* 修改的目的是避免答案增殖過多，導致找尋資料麻煩
* 謠言的利益相關者無法破壞文章
* 讓小編可以看到自己的回答、快速尋找自己參與的謠言

直接紀錄 reply author 是誰，然後強制只有 author 可以修改，是個最直接而且也最多系統採用的解方。所有的問答網站都是這樣做的。

## 方案 2：無須登入即可回應文章

* 由於不知回應的作者，因此任何人登入之後都可以修改回應。
* 會顯示是誰做了什麼修改，並且要求填寫編輯理由（改錯字、改用詞、修正連結等等）
* 回應有 version，預設顯示最新 version，但有歷史紀錄。可以由任何人隨時 rollback。
* 若發生互相 rollback 的編輯戰，參考 [Wikipedia](https://zh.wikipedia.org/wiki/Wikipedia:%E4%BA%89%E8%AE%BA%E7%9A%84%E8%A7%A3%E5%86%B3) 鎖文並且協調。

核心想法是希望「資料生成」是匿名的，需要鼓勵；而「變更現有資料」因為要變更他人成果，因此要記名並且敘明理由。
方案 2 比較接近 Wikipedia 的協作方式。由於真的假的會呈現正反聲音，不像 Wikipedia entry 只有一份，因此理論上衝突會發生地更少——如果意見真的不合，那就寫另一個回覆，LINE bot 自然就會雙方都呈現。

## 決議

採取**方案 1**。

### 理由

* 採取社群網站登入（facebook, twitter, github）對使用者來說並非難事。
* Wikipedia 雖允許匿名編輯，但亦鼓勵登入。Rollback 等權限要有帳號＋[申請擁有回退權](https://zh.wikipedia.org/wiki/Wikipedia:%E6%AC%8A%E9%99%90%E7%94%B3%E8%AB%8B)後才能使用，並非全然匿名。

### Actionable Item

1. 使用 https://github.com/rkusa/koa-passport 實作登入機制
2. 保護 mutation API（`CreateReplyRequest` 等由手機送出的 API 除外）



## Reference

### Stackoverflow 
http://stackoverflow.com/help/privileges/edit

有足夠聲望的用戶能修改他人的提問以及回應，聲望來自用戶過去回答被他人認同。

官方鼓勵修改以下情境：
- to fix grammatical or spelling mistakes
- to clarify the meaning of a post without changing it
- to correct minor mistakes or add addendums / updates as the post ages
- to add related resources or hyperlinks

不鼓勵 trivial 的小修改。

聲望方面最近有[檢討聲浪](https://buzzorange.com/techorange/2017/03/21/stack-overflow/)。


### Wikipedia
https://zh.wikipedia.org/wiki/Help:%E7%99%BB%E5%BD%95

不需要登入便可編輯，但是還是鼓勵登入，因為可以讓用戶跟編輯者交流，同時也給予監視清單，方便觀察編輯過和感興趣的文章。

## 討論紀錄

```
mrorz 是說我覺得小編回訊息可能可以不用登入耶
也就是說 reply 都是匿名的
只有對 reply 的評分、或者是對 article 送 reply request (敲碗) 或編輯他人 reply 等等要「變動」現有內容（內容、名次等等）是要登入的

[2:01 AM]  
主要是希望鼓勵內容生成，然後在「變動他人生成內容」上墊高一點點門檻

[2:03 AM]  
至於 type switch

[2:04 AM]  
除了 rumor / fact 之外

[2:04 AM]  
還有「非完整文章」
就是如果有人亂傳非完整訊息

[2:04 AM]  
要標成「非完整文章」

[2:12 AM]  
lucien 非完整訊息的定義是什麼呢

[2:12 AM]  
我怎麼不記得之前有這個

[2:13 AM]  
當初設計不是沒有 reply requests 嗎

[2:14 AM]  
同時不能編輯他人的answer

[2:14 AM]  
只能改自己的

[2:15 AM]  
Reply 打分應該是從哪邊呢

[2:15 AM]  
從bot 還是網站？

[2:17 AM]  
謠言機制感覺需要出一個 system design docs ><

[2:33 AM]  
lucien 統一一下產品需求

[10:26 AM]  
mrorz http://beta.hackfoldr.org/rumors/https%253A%252F%252Fhackmd.io%252Fs%252FSyMRyrfEl 非完整訊息 請見「Type」的 ”Don’t use“ (edited)

[10:27 AM]  
是現在就有的這樣

[10:27 AM]  
然後 reply request (敲碗)確實是在 MVP 之外的東西

[10:28 AM]  
至於編輯行為，我看了一下會議記錄
http://beta.hackfoldr.org/rumors/https%253A%252F%252Fhackmd.io%252Fs%252FrJQaJ9wwl

當初好像有點模糊 @@

[10:29 AM]  
因為這個
> 希望「建立新資料」是免登入的，鼓勵大家產製內容；
> 但希望「編輯現有資料」要掛名登入，用以提升破壞的難度。


跟「在登入系統寫好前，送出 answer 後不能透過 UI 來修改」
都沒有寫到「登入系統寫好後，送出 answer 誰能來修改」

[10:29 AM]  
不過登入系統寫好之後，要符合
> 希望「建立新資料」是免登入的，鼓勵大家產製內容；
> 但希望「編輯現有資料」要掛名登入，用以提升破壞的難度。

的精神的話

[10:31 AM]  
那麼就應該是：
1. 在登入系統寫好前，送出 answer 後不能透過 UI 來修改。
2. 在登入系統寫好之後，送出 answer 依然是免登入用以鼓勵內容產製；登入的使用者可以修改任何 answer，但是要掛名登入。 (edited)

[10:32 AM]  
最後 reply 打分也是新的東西
還沒想好要怎麼處理比較好 orz

[10:34 AM]  
http://beta.hackfoldr.org/rumors/https%253A%252F%252Fdocs.google.com%252Fdrawings%252Fd%252F1kStWPVHbzrpSTKu9-EK5TN52Xj7WY7uAiEBa00v6xK4%252Fedit 主要是我在畫 flow diagram 的時候
覺得「您覺得有回答到原本的文章嗎」這個問題如果使用者按了「是」那應該要做個紀錄

[10:40 AM]  
mrorz reply 打分似乎在第一次有討論到基本精神
http://beta.hackfoldr.org/rumors/https%253A%252F%252Fhackmd.io%252Fs%252FrJQaJ9wwl
見「左欄：上面放 rumor，中間放 answer input，下面列出 answers」下面的那塊

[10:41 AM]  
但提到的面向是「如果 answer 太多，要如何選出優劣」 (edited)

[10:42 AM]  
我們當時沒有討論，如果 answer 太少而使用者覺得目前的 answer 都不 ok、希望其他小編可以寫新的更好的 answer 的話，那要如何收集這樣的 feedback 讓小編們知道

[12:06 PM]  
ggm 我貌似想到個問題不知道之前有沒有討論到，就是匿名的 reply，如果他送出之後發現哪裡打錯了是不是就沒辦法改

[12:06 PM]  
只有 admin 可以幫他砍掉了？

[12:06 PM]  
lucien 對

[12:06 PM]  
其實問題是 修改 跟 評分

[12:07 PM]  
ggm 那 … 這件事情要怎麼做 他如果真心要砍掉 其實是要跟 admin 證明說那篇是他發的？

[12:07 PM]  
lucien 登入目的是讓小編可以看到自己的回答

[12:07 PM]  
mrorz 我上面的意思是

[12:07 PM]  
lucien 和快速尋找自己參與的謠言

[12:08 PM]  
mrorz 登入之後，就能修改任何的 reply。

[12:08 PM]  
ggm 噢！

[12:08 PM]  
mrorz 你改別人的也可以

[12:08 PM]  
但就是要記名

[12:08 PM]  
ggm 但是會留下紀錄

[12:08 PM]  
懂！上次好像有講到是我漏了

[12:08 PM]  
mrorz 「快速尋找自己參與的謠言」可以另外用「關注」功能做

[12:09 PM]  
lucien 關注還是要登入吧

[12:09 PM]  
mrorz yes

[12:09 PM]  
關注要登入

[12:09 PM]  
lucien 另外上次說不能直接改不是嗎

[12:09 PM]  
mrorz 對

[12:09 PM]  
lucien 只能寫新答案

[12:09 PM]  
mrorz 我的意思是

[12:09 PM]  
「登入系統還沒做完之前不能改」

[12:10 PM]  
登入系統做完之後我沒有講清楚

[12:10 PM]  
但有討論到
> 希望「建立新資料」是免登入的，鼓勵大家產製內容；
> 但希望「編輯現有資料」要掛名登入，用以提升破壞的難度。


[12:10 PM]  
lucien 那修改的意思是什麼？可以直接改原答案？

[12:10 PM]  
mrorz 這個精神

[12:10 PM]  
是的

[12:10 PM]  
我在想要不要限制修改幅度

[12:10 PM]  
但有點詭異

[12:10 PM]  
總之我會希望這個「修改」的作用

[12:10 PM]  
是在改錯字

[12:10 PM]  
或修正連結

[12:11 PM]  
lucien 我記得是登入作答但是匿名耶

[12:11 PM]  
mrorz 不希望「修改」是整篇重寫

[12:11 PM]  
但我不確定這個限制要怎麼做到

[12:11 PM]  
登入作答嗎

[12:12 PM]  
lucien 現在多個回應會怎麼丟進chatbot呢

[12:12 PM]  
mrorz 那應該是我們討論當時對「匿名」的想像不一樣

[12:12 PM]  
我想像的匿名是連 user id 都不記的那樣

[12:12 PM]  
lucien 如果chatbot端可以整理答案

[12:13 PM]  
mrorz 但你的想像是「不顯示」

[12:13 PM]  
lucien 那多個回復也不需要修改？

[12:13 PM]  
mrorz 「整理答案」具體是指什麼

[12:13 PM]  
修改答案嗎

[12:14 PM]  
lucien 是聚合和總結

[12:14 PM]  
lucien 修改的目的是避免答案增殖過多

mrorz [13 hours ago] 
如果只是 wording 的修改或改錯字，我會希望是「修改」沒錯

mrorz [13 hours ago] 
雖然「修改」跟「蓋新的 answer」界線確實有些模糊
希望記名能提供足夠的門檻

lucien [13 hours ago] 
那修改真的是mutate原資料嗎

mrorz [13 hours ago] 
不過「答案增值過多」這件事情，本身應該要靠
1. `排序方面，希望新的 answer 會排在舊的 answer 之上。因為使用者在寫新 answer 時，會看到舊有的 answer，一般來說新的 answer 應該會改進舊的。`
2. 若排序還不夠 or 造成有人一直洗新 answer，那考慮 upvote/downvote

mrorz [13 hours ago] 
reply 有 versioning

lucien [13 hours ago] 
還是DB新增一筆record

mrorz [13 hours ago] 
http://beta.hackfoldr.org/rumors/http%253A%252F%252Fapi.rumors.hacktabl.org%252F

See `type Reply`
有 versions

mrorz [13 hours ago] 
ReplyVersion 的 text 就是該版本的全文

mrorz [13 hours ago] 
啊，但 `ReplyVersion` 需要 author 欄位
忘記加 QQ (edited)

lucien [13 hours ago] 
Reply 的 version 就是新的贏舊的？

mrorz [13 hours ago] 
yep

mrorz [13 hours ago] 
但紀錄 version 的好處是可以做 rollback

mrorz [13 hours ago] 
我覺得 wikipedia 應該也是靠 rollback 機制讓破壞比復原還要簡單

lucien [13 hours ago] 
Rollback 是怎麼啟動的？

lucien [13 hours ago] 
Voting?

mrorz [13 hours ago] 
wikipedia 是直接按了就 rollback

mrorz [13 hours ago] 
這裡我是希望 rollback 是登入的人就能 rollback

lucien [13 hours ago] 
Wow

lucien [13 hours ago] 
沒有門檻嗎

mrorz [13 hours ago] 
沒有

lucien [13 hours ago] 
感覺會爆炸

mrorz [13 hours ago] 
因為那種互相 rollback 的 pattern 很好辨認

mrorz [13 hours ago] 
他會自動標成爭議

mrorz [13 hours ago] 
然後 wikipedia 管理者就會鎖住文章

lucien [13 hours ago] 
Rollback 的意思是新的會存在？

mrorz [13 hours ago] 
這種文章佔 wikipedia 應該相當少數

mrorz [13 hours ago] 
rollback 應該就是把舊的 version 複製一份變成最新的 version

mrorz [13 hours ago] 
類似 git revert (edited)

lucien [13 hours ago] 
Okay

mrorz [13 hours ago] 
https://zh.wikipedia.org/wiki/Wikipedia:%E4%BA%89%E8%AE%BA%E7%9A%84%E8%A7%A3%E5%86%B3
Wikipedia
Wikipedia:争论的解决
"WP:DR"重定向到这里，你也许是在找Wikipedia:存廢覆核請求。
维基百科是一个社群。這就意味著我们需要一同協作来撰寫百科全书。经常会有很多人共同参与一篇文章的编辑，而有时用户们会对某些条目应该怎么写产生分歧。如果你对一篇文章存在不同看法，请去找到证据支持你的观点，并在这期间停止编辑此条目。
请不要与其他用户发生编辑战；這對解決争议沒有幫助，在改進維基百科上沒有意義。相反，请您遵循这裏列出的方式来解决分歧，以防分歧變為嚴重的争执。 注意：以下的步骤是用于解决兩方或多方的分歧的。纯粹的破坏者、或是屡次公然违背维基百科政策和行为准则的人，将使用加快过程来处理。可能會導致冒犯者被禁封。大多数情况下，如有用户被指出有不当行为，可按以下下面的处理。這並不意味着指出不當行為的用户参与了争议，他们仅代表着维基百科社群。 (21KB)

mrorz [13 hours ago] 
我是不覺得會這麼早發生需要處理編輯戰 / 互相 rollback 的狀況啦

mrorz [13 hours ago] 
但如果真的發生了，或許就是學 wikipedia 鎖文然後把雙方找來找雙方都能接受的編輯吧

mrorz [13 hours ago] 
而且我們與 wikipedia 有一個最重要的差別：

mrorz [13 hours ago] 
wikipedia 的詞條只有一個

mrorz [13 hours ago] 
但 article reply 可以有很多個

mrorz [13 hours ago] 
因此 wikipedia 應該比我們還要更常吵架

mrorz [13 hours ago] 
如果 wikipedia 都採取這麼開放的編輯態度了

mrorz [13 hours ago] 
我不認為擁抱多元、鼓勵寫新內容的我們做不到這種開放的編輯模式。

lucien [13 hours ago] 
謠言的擔憂是他有利益相關

lucien [13 hours ago] 
怕謠言的利益相關者出來破壞

mrorz [13 hours ago] 
如果利益相關人有相反意見，他可以新開 reply。由於 line bot 會用「n 人回報有不實訊息、m 人回報查無不實」來總結 replies，因此他的聲音可以被看到。

mrorz [13 hours ago] 
另外，他開新的 reply，排序也會暫時排在比較上面，何必跟別人搶修改呢……

mrorz [13 hours ago] 
我同意
1. 利害關係人破壞是個 Valid concern
2. 直接紀錄 reply author 是誰，然後強制只有 author 可以修改，是個最直接而且也最多系統採用的解方。

只是我覺得亂改別人解答這件事在自然狀況下應該很少發生，而利害關係人做破壞的當下其行為也會被記錄下來，再看要怎麼在系統上防堵。只有作者才能編輯這件事，會造成其他人不能幫改錯字、阻卻幫修連結等等這類良性的互動。

防弊 v.s. 興利，今晚你選哪一道？ (edited)

mrorz [13 hours ago] 
Stack overflow 好像常看到解答右下角有個小方框寫 edited by xxx. 那個的機制是什麼呢？

mrorz [12 hours ago] 
如果編輯的時候除了本文
還要另外填寫編輯理由（必填）
讓大家能辨認誰是亂改的、讓修改的門檻小幅度上升
這樣是不是就能提升破壞被辨認出來的機會， 同時不減損良善的互動？

---（以上自成一串）---

lucien compose ai 那邊弄臉書比較熟

[12:34 PM]  
所以其實還有 reply detail view

[12:34 PM]  
但如果edit其實也是蓋一個新version答案

[12:35 PM]  
那第一個回覆的人的答案會跟其他人不一樣

[12:35 PM]  
少了作者

[12:36 PM]  
感覺統一會比較好

[12:55 PM]  
mrorz 不要放作者頭像
改成小字「edited by xxx」呢 (edited)

[1:22 PM]  
mrorz 我覺得「reply 紀錄使用者」與「reply 不登入、不記錄使用者」兩個各成一套系統
但整個登入是在 MVP 之外
我晚上的時候紀錄一下  lucien 與我的論點
然後記在 hackmd
之後可以再繼續討論、延伸新的想法
搞不好 lucien 擔心的事情提早發生、或不會發生
到要實做 login system 時候應該能做更好的判斷

```
