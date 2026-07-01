---
type: ResearchDoc
title: "Cofacts website 2023"
resource: "https://g0v.hackmd.io/@cofacts/HJ_O1Xhhs"
tags: [cofacts, research]
timestamp: "2023-07-12T21:09:51+08:00"
---

# Cofacts website 2023

## Previous design

Cofacts Next spec
https://g0v.hackmd.io/@NFi0czulSemxCM8RNSlz8Q/HJ8xT3QVU/%2FahtI6xsFRQyxktrIlc1VcQ

### Problem
- Performance issue
  - Reply editor very slow on iOS
  - Server-side CSS-in-JS + Populating Apollo cache then pass to FE, multiple renders on server side
  - Memory leak; need to restart server every hour. Even staging server have RAM exceeded restarts ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_d5e9b948841dd104c25644ada6b03d43.png)
- Lack of tutorial
- Font size is too small for elderly citizens
  - Landing page & impact page is OK
- Exposes full GraphQL API that cannot be guarded by secret tokens

## Ideas
- Design language Material Design 3
  - [BeerCSS](https://www.beercss.com/)
    - like Semantic UI in MD3, has segmented buttons
    - Contains utility like `grid`, `row` and responsive utilities `m`, `l`, etc
    - has some [DOM hack](https://github.com/beercss/beercss/blob/main/src/cdn/beer.ts#L106) though (mutation observer observing body for field labels, etc)
  - [Material Tailwind](https://github.com/creativetimofficial/material-tailwind) ?
  - [Daisy UI](https://daisyui.com/)
    - [No figma files](https://github.com/saadeghi/daisyui/discussions/1027)
    - Similar trend to flowbite
  - [headlessui/react](https://github.com/tailwindlabs/headlessui)
  - ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_dad9333e2d8bcca836793bc29411aa94.png)
- Tech stack
    - Next.JS 13 server components
        - Apollo-client no longer needed; call GraphQL API on server components
        - Use React actions (Alpha) for mutations
        - Login session on Next.js server, Next.JS talking to API using secrets / tokens
        - Can deploy to vercel
    - Google Material Symbol w/ Google font https://developers.google.com/fonts/docs/material_symbols?hl=en
        - CSS animatable fill and weight! Amazing......
        - [Color palette setup](https://m3.material.io/theme-builder#/) is tricky, because
            - It imposes accessibility in tonal palette, so the color is not accurate
            - It uses design tokens in another design token (`m3.sys.*` referring `m3.ref.*`) but Figma does not support this
                - It is set as hex code
                - The tool do support updating all of them, but it alters the color we input, so the whole color looks off


## Navigation

![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_dde503deb41e7d8f71281882a765a5ba.png)

參考 [Twitter Community Note](https://g0v.hackmd.io/@cofacts/rd/%2FoK1F5q4eRV2IhGM-8ULTdQ)：
- 需要幫助（請支援ＸＸ）的放前面
- 從門檻低得到門檻高的，進行門檻低的作業同時也在練習
- list page 雙層結構（第二層為 tab，同一個列表不同排列與過濾）

新 navigation hierarchy
- Community Replies 查核回應
    - Needs your help 請支援評分：尚未有有效回應、自己沒評分過（預設開啟 filter）
    - All 所有回應：預設時間排序，開所有 filter
    - Helpful 好評：網友覺得有用的回應（預設開啟 filter）
- Messages 可疑訊息
    - Needs your help 請支援查證：尚未有回應、且 reply request >= 2
        - 排序：最近一次 reply request 時間。
    - （Needs transcript 請支援逐字稿：reply request >= 2 且無逐字稿）
    - All 所有可疑訊息：預設時間排序，開所有 filter
- Profile 我的頁面 （若有登入） / Login
- Tutorial 使用教學
- (Spacer)
- 關於 Cofacts
- 使用者條款

或參考小聚循序漸進 + FB 排版：
- 查核回應
    - 預設 filter，另外轉換看全部
- 待查訊息
    - 預設 filter，另外轉換看全部
- 其他（頭像與選單） 

## List pages

Section 說明這頁在幹嘛

info
- 回報數 / 回應數
- （今日熱門度、icon）
- 文字：訊息（全寬！字要大！）
- 圖片放左邊、方形 | 以上 info + transcript
- 影片放左邊、方形 | 長度 info + transcript
- 聲音放左邊、方形 | 長度 + 以上 info + transcript

點上面任何地方都可以進到 detail page。

回應列表加上：
- 最新回應
    - 頭像、判斷、時間
    - 文字
- 出處：N 個網站、說明文字
- 「另有 N 則回應，M 人覺得有幫助」

## Detail

參考 Twitter / Facebook
單層 header （title 網傳訊息） + left back button + right action button (if any)

- N 人回報或補充資訊、時間
- 網傳訊息本體
- 熱門狀態
- 回報補充
- 撰寫新查核
- 現有查核回應
