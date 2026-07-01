---
type: DesignDoc
title: "OCR and AI transcripts"
resource: "https://g0v.hackmd.io/@cofacts/HJr5m00Mh"
tags: [cofacts, design-docs, technical-design]
timestamp: "2025-02-10T19:16:15+08:00"
---

# OCR and AI transcripts

> [!NOTE]
> - Related research: https://g0v.hackmd.io/aJqHn8f5QGuBDLSMH_EinA#OCR
> - Crowd-sourced transcript: https://g0v.hackmd.io/@cofacts/rd/%2FOhGIQzoxR5eF6audQuS_FQ
> - Media manager: https://g0v.hackmd.io/@cofacts/rd/%2FC8dW2cFiR1-N5Z0wcOefuA
> - AI response introduced in: https://g0v.hackmd.io/@cofacts/rd/%2F%40cofacts%2FrknFrmdk3

## Algorithm

We will use `airesponses` index to store the mapping between media entry ID and the AI transcripts, so that:
- AI transcripts of messages not submitted to the database can also be cached and replayed when a media with identical hash is queried
- When article is created, the AI response content will be used to populate article text and crowd transcript.

> [!NOTE]
> We basically selected "After ID is extracted by media manager" in [Metadata extraction](https://g0v.hackmd.io/aJqHn8f5QGuBDLSMH_EinA#When-to-extract)

### Applied tech

In the current phase, we apply the following to different types of user inputs.
- Audio and video: speech-to-text (STT)
  - Don't process the text in the video for the sake of simplicity
- Image: OCR

### The AI responses

- `docId`: `MediaManager` returned ID
- `type`: `AIResponseTypeEnum` value.
    - Add new value: `TRANSCRIPT` for OCR and/or video
- `text`: transcript text from API
- `usage`: not used

### `ListArticle` with `mediaUrl`
When `mediaUrl` is specified:

1. `MediaManager.query()` returns `queryInfo.id`
2. Look up that media hash (queryInfo id) in `articles`
    - `articles.text` may contain crowd-sourced transcripts
    -  If no match, look up that `id` in AI responses
       - If no match, perform AI transcript and write AI response with the `id`
3. Perform `more_like_this` on `articles`' `text` and `hyperlink` fields using the AI reponse's `text`.

In the process above,
- Step 2 is known to be slow if no text is stored in AI response -- may not return within a minute, especially for video.

### `CreateMediaArticle`

1. `mediaManager.insert()` returns `MediaEntry` ID
2. Create article with `MediaEntry` (`createNewMediaArticle`)
3. Look up that ID in AI responses
   - Since LINE bots always `ListArticle` before `CreateMediaArticle`, this step usually can find a AI response
   - If not, perform AI transcript and write the AI response
4. Create a version of "crowd-sourced" transcript with AI transcript
   - This should be the very first version of the transcript

In the process above,

- `CreateMediaArticle` do not need to wait for step 3 and 4.
- Step 3 can start as soon as step 1 returns `MediaEntry`.
- In extremely rare cases, step 4 can finish after some user submits a crowed-sourced transcripts.
    - Maybe consider appending AI transcripts in this case?

## Cost estimation

To get the estimate of max possible cost, we assume an extreme case
- All Video / Audio / Image messages are not cached in AI responses and thus need to invoke the paid APIs.
- All video / audio are 5 minutes in length

The event count for `UserInput / MessageType / <text | image | video | ...>` in LINE bot in 2023/03 are:

![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_2ea8f5437c9e64deb7d6e9330ef1a68f.png)

We does the following estimation with
- 3,800 videos + audios (STT)
- 3,200 images (OCR)

### OCR

> [Previous pricing research](https://g0v.hackmd.io/aJqHn8f5QGuBDLSMH_EinA#OCR)

#### Google cloud vision API
> - Usage: https://cloud.google.com/vision/docs/ocr?hl=zh-tw
>     - Supports [remote image (by URL)](https://cloud.google.com/vision/docs/ocr#detect_text_in_a_remote_image)
> - Pricing: https://cloud.google.com/vision/pricing?hl=zh-tw

Document Text Detection:
- First 1000 units/month are free
- Units 1001 - 5,000,000 / month: $1.5 per 1000 units
- Units 5,000,001 and higher / month: $0.6 per 1000 units

> Each feature applied to an image is a billable unit. For example, if you apply Face Detection and Label Detection to the same image, you are billed for one unit of Label Detection and one unit for Face Detection.

In our case, 1 unit = 1 image. Thus:

- Monthly billable units = all - free tier = `3,200 - 1,000 = 2,200` units
- Total price = `2200 * 1.5 / 1000 = 3.3`.

> [!TIP]
> 3.3 USD / mo

#### Tesseract
Free of charge, but can be limited in our previous experience

- Cannot handle dark background + light text
- Cannot handle vertical text
- Cannot handle hand written text

### STT

#### Whisper API
> - NodeJS API
>     - Supports `fs.createReadStream` https://platform.openai.com/docs/api-reference/audio/create
>     - [Use node-fetch to create readable stream](https://github.com/cofacts/media-manager/blob/main/src/lib/prepareStream.ts#L54)
> - https://openai.com/pricing
>     - $0.006 / minute (rounded to the nearest second)

- Total amount of minutes = `3800 * 5 = 19,000`
- Total price = `19,000 * 0.006 = 114`

> [!TIP]
> 114 USD / mo

#### 自架 Whisper
GPU machine cost 遠大於 Whisper API
https://cloud.google.com/compute/gpus-pricing#tpus

#### Google speech to text
> Usage: https://cloud.google.com/speech-to-text/docs?hl=zh-tw
> Pricing: https://cloud.google.com/speech-to-text/pricing
> By opting in to data logging, you can allow Google to record audio data sent to Speech-to-Text. This data helps Google improve the machine learning models used for speech transcription. Customers who opt in to data logging benefit from lower Speech-to-Text pricing.

##### V1 API
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_ed7e896c5fd4338b6c565c7696a18e25.png)

- Billable minutes = `19,000 - 60 = 18,940`
- Total price = `18,940 * 0.016 = 303.04`

> [!TIP]
> 300 USD / mo

##### V2 API
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_346a2e209275acfa3ef24e7af802c2fa.png)


###### Sync request
- All 19,000 minutes are in first pricing (0.012/min)
- Total price = `19,000 * 0.012 = 228`
- [Max 1min](https://cloud.google.com/speech-to-text/docs/speech-to-text-requests#speech_requests)

###### Async request (dynamic batch)

- Total price = `19,000 * 0.00225 = 42.75`
- Has progress bar https://cloud.google.com/speech-to-text/docs/speech-to-text-requests#async-responses
- Need changing chatbot flow to handle this
    - Reply handle [times-out in 1 min](https://developers.line.biz/en/reference/messaging-api/#send-reply-message-reply-token)
    - Can provide users with "click to check progress" button instead

##### Effectiveness

> 昨天我試了一下 google speech to text v2 (Chirp)
> 影片與 whisper 幻出來的結果：https://cofacts.tw/article/sfTx-IoBAjOeMOklkePx
> 
> 而 Google Chirp 模型的結果如圖
感覺比 Whisper 的 medium model 還差，錯字多到 Elasticsearch 的 bigram 也無法有效 index
> ![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_8ef8a01799cc958ce10fc71430c31294.png)

### Multimodal LLM

#### Gemini Flash 1.5 (Gemini API)

Pricing: https://ai.google.dev/pricing
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_cfc3c5742532cf718fb1c0b3bf850037.png =x400)
- 每張靜止圖 = 258 tokens；影片會[被 File API 處理成每秒一張圖](https://ai.google.dev/gemini-api/docs/prompting_with_media?lang=node#upload-video-file)
- Assume 3,800 5-min videos + audios per month
  - Prompt input: 5 min = 300 seconds = 77,400 tokens < 128K token using USD 0.35/million token rate
  - Each 5-min content costs 77400*0.35/1M = 0.02709 USD; 3800 of them = 102.942 USD / month

> [!TIP]
> 103 USD / mo

#### Gemini Flash 1.5 (Vertex AI)

[Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing#gemini-models)

![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_2a2f1c65edfe7ac9804c3445384b53c4.png)

- Assume 3,800 5-min videos + audios per month
  - Prompt input: 5 min = 300 seconds = 77,400 tokens < 128K token, using USD 0.0001315/second
  - 3800 of 5-min content = 1140000 seconds = 149.91 USD / month
- Occasionally occur [recitation error](https://github.com/google/generative-ai-docs/issues/257)

> [!TIP]
> 150 USD / mo

## Tech detail

### Whisper

- Whisper do support prompts https://platform.openai.com/docs/guides/speech-to-text/prompting
  - Use prompts to specify length of each paragraph, add punchuations
  - Google sheet on prompt engineering: https://docs.google.com/spreadsheets/d/10xfkOZpGJ-9vIvoYziEkD1lZETWMbBLDT-NABdQ8H_g/edit#gid=0
- Whisper hallucination 解方
  - ffmpeg silence removal (但這是用寫死的 loudness 來做) - https://community.openai.com/t/whisper-api-hallucinating-on-empty-sections/93646/5
  - 提及 whisperX 等會用 voice activity detection (VAD) 只取有人聲的前處理： https://github.com/openai/whisper/discussions/1369 ；或用 VAD 的 timestamp 來過濾 Whisper 的結果（回傳 type 為 `verbose_json` 時，會帶有 timestamp）
  - 用 prompt 指定 accent 等等：https://community.openai.com/t/how-to-avoid-hallucinations-in-whisper-transcriptions/125300/17
  - 嘗試設定一些細節參數 (`condition_on_previous_text` , whisper API 調不到) 與計算 chunk size https://github.com/openai/whisper/discussions/679
  - [WhisperDesktop](https://github.com/Const-me/Whisper) 用 "[A simple but efficient real-time voice activity detection algorithm](https://www.researchgate.net/publication/255667085_A_simple_but_efficient_real-time_voice_activity_detection_algorithm)" 
  - Node.JS VADs https://npmtrends.com/@ricky0123/vad-node-vs-node-vad-vs-voice-activity-detection-vs-webrtcvad
      - WebRTC VAD: https://github.com/Snirpo/node-vad (has stream)
      - Another WebRTC VAD https://github.com/serenadeai/webrtcvad
      - silero vad model：https://www.vad.ricky0123.com/docs/node/

#### VAD to reduce hallucination

https://npm.io/search/keyword:vad

##### WebRTC VAD

##### faster-whisper + Silenro VAD

##### Cobra Vad
https://picovoice.ai/blog/voice-activity-detection-in-nodejs/

#### WhisperX on replicate

目標：https://replicate.com/victor-upmeet/whisperx/readme
- 可以設定 prompt 跟很多東西
- 有很多 runs；但仍然會[撞到 cold boot](https://replicate.com/docs/how-does-replicate-work#cold-boots) 會花到 100 秒
    - 例子：https://replicate.com/p/vl35pxlb6qiwz7t2hcrw2ltmri 結果，`start_at` 與 `created_at` 的時間差，就是啟動時間
- 測試：https://docs.google.com/spreadsheets/d/10xfkOZpGJ-9vIvoYziEkD1lZETWMbBLDT-NABdQ8H_g/edit#gid=678820735

#### WhisperX by Ronny Wang
- 可以設定 prompt
- 執行很快，但有時會 queue 4min


### Google cloud speech-to-text

- Only async & batch can be used
    - https://cloud.google.com/speech-to-text/v2/docs/batch-recognize
    - Nede to enable [dynamic batch processing](https://cloud.google.com/speech-to-text/v2/docs/batch-recognize#enable_dynamic_batching_on_batch_recognition)
    - Input file needs to be on GCS
- Can create [recognizer](https://cloud.google.com/speech-to-text/v2/docs/recognizers) and keep reusing
    - Pass [up to 3 languages](https://cloud.google.com/speech-to-text/v2/docs/multiple-languages) in language code
    - Use [model `long`](https://cloud.google.com/speech-to-text/v2/docs/transcription-model) for multi-language
    - Not available in Taiwan; zh-TW [only available in Singapore](https://cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages) (`asia-southeast-1`)
    - [Manually](https://cloud.google.com/speech-to-text/v2/docs/automatic-punctuation) enable punctuations


### Google vision API

Determine confidence level threshold with the following items.

Script: https://colab.research.google.com/drive/1yyMyShq1j3LRX1zdQE-3sLH5fNmTvdmp#scrollTo=lvZwFTLVOo4C&line=32&uniqifier=1

Evaluation: https://docs.google.com/spreadsheets/d/1d7OAVygXwwb3JgjpSKaRrm1bkzUOAapTtebi-I3Na7A/edit#gid=0

- 畫質很差的 LINE 對話截圖
  - https://cofacts.tw/article/IfRSqIoBAjOeMOkl16TM
- 圖表 + 改字
  - https://cofacts.tw/article/___n34ABAAAAAOHv4W_hb-Bu4G7AbuHiIe_h4wHu_AA
- 日文
  - https://cofacts.tw/article/gCktaYkBFLWd9xY2d4N5
- 藝術字照片
  - https://cofacts.tw/article/oM86booBrkRFoI6rAOyG
- 相機照螢幕
  - https://cofacts.tw/article/FfSs_ooBAjOeMOklXOv5
- 手寫大字
  - https://cofacts.tw/article/Y_SG_4oBAjOeMOklJewT
- 照罰單
  - https://cofacts.tw/article/W8_fdYoBrkRFoI6r8PHN

### Google video intelligence
> 2-in-1: transcript + text detection
> https://cloud.google.com/video-intelligence/docs/text-detection

- Pricing: https://cloud.google.com/video-intelligence/pricing?hl=en
- See https://g0v.hackmd.io/aJqHn8f5QGuBDLSMH_EinA#How-to-extract


### Gemini

Gemini 1.5 Flash on Google AI
- 可在 Google AI studio 測試，測試結果很不錯
  - [手動測試](https://docs.google.com/spreadsheets/d/10xfkOZpGJ-9vIvoYziEkD1lZETWMbBLDT-NABdQ8H_g/edit?gid=2073990791#gid=2073990791)、[大量 Prompt engineering](https://docs.google.com/spreadsheets/d/10xfkOZpGJ-9vIvoYziEkD1lZETWMbBLDT-NABdQ8H_g/edit)
  - 同時處理有聲無字、有字無聲影片
  - 無聲影片不會 hallucinate 而是用影片出字
- API: 需用 File API 先行上傳
  - 文件：https://ai.google.dev/gemini-api/docs/vision?lang=node#prompting-video
  - 直接用第三方 URL 放在 contents 裡，會回傳 status 400 "gemini api Invalid or unsupported file uri"
  - Upload with stream: https://github.com/google-gemini/cookbook/blob/cf2dc7a3a851c5f553c2bf9ff884770719ca368d/quickstarts/file-api/sample.js#L18-L29
  - Upload with curl: https://github.com/google-gemini/cookbook/blob/main/quickstarts/file-api/sample.sh
  - media.upload API with GCS parameters https://discuss.ai.google.dev/t/streaming-into-googleaifilemanager/5899/4
  - Multipart upload with blob: https://medium.com/google-cloud/generating-texts-using-files-uploaded-by-gemini-1-5-api-5777f1c902ab#f76c
  - Upload with filename & SDK https://ai.google.dev/gemini-api/docs/vision?lang=node#upload-
- Authentication: 可用 API key 與 [OAuth](https://ai.google.dev/gemini-api/docs/oauth#curl)

Gemini 1.5 Flash on Vertex AI
- [Difference between Gemini API and Vertex AI](https://ai.google.dev/gemini-api/docs/migrate-to-cloud)
- 可用 google cloud storage 作為 file Uri
- Google apps script
  - User access token https://github.com/analyticswithadam/App_Script/blob/main/Gemini_Functions.js
  - Service account key [googleworkspace/apps-script-samples](https://goo.gle/apps-script-ai)

----

#### Gemini Experiments

Test subjects used in unit tests

- [Direct sales](https://cofacts.tw/article/8eYt2pMBYrjt7MSMjQak) 0:36
    - Audio only, human voice
- [Ginger](https://cofacts.tw/article/TvR6AosBAjOeMOklfe-g) 0:53
    - Video: TC subtitle, 橫書 + 直書
    - Audio: Pure music
- [Tiktok](https://cofacts.tw/article/m_S3AosBAjOeMOkls-_a) 0:31
    - Video: SC subtitle, lots of text distractions like screen recording
    - Audio: Probably speech to text

Model selection
- As of 2025 Feb, the only model with API that supports audio + video + text together is Gemini family

---



| Model | Test subject | Time | Token usage |
| -------- | -------- | -------- | ---- |
| gemini-2.0-flash-exp | [Direct sales](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/W-3Nx5QB7AiuTk05XbT2)  | 24s | 1,282 → 96 (∑ 1,378) |
| gemini-2.0-flash-exp | [Ginger](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/XO3Nx5QB7AiuTk05v7Sl)       | 41s | 15,837 → 221 (∑ 16,058) |
| gemini-2.0-flash-exp | [Tiktok](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/Xe3Ox5QB7AiuTk05Y7Tv)       | 37s | 9,347 → 108 (∑ 9,455) |
| gemini-1.5-pro-002 | [Direct sales](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/Z-3hx5QB7AiuTk05WLQ1)  | 43s | 1,282 → 101 (∑ 1,383) |
| gemini-1.5-pro-002 | [Ginger](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/aO3ix5QB7AiuTk05A7Qb)       | 1m 17s | 15,837 → 205 (∑ 16,042) |
| gemini-1.5-pro-002 | [Tiktok](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/ae3jx5QB7AiuTk05MrSY)       | 1m 12s | 9,347 → 94 (∑ 9,441) |
| gemini-1.5-flash-002 | [Direct sales](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/ZO3dx5QB7AiuTk05LbSc)  | 46.23s | 1,282 → 97 (∑ 1,379) |
| gemini-1.5-flash-002 | [Ginger](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/Ze3dx5QB7AiuTk0547Ti)       | 1m 27s | 15,837 → **2,048** (∑ 17,885) Hallucinated |
| gemini-1.5-flash-002 | [Tiktok](https://langfuse.cofacts.tw/project/cm3e6a2190001fdga2ruendgd/traces/Zu3fx5QB7AiuTk05ObQl)       | 1m 6s | 9,347 → 96 (∑ 9,443) |


- 2.0 Experimental 又好又快
  - 但實驗期間 quota 極小 (2 video per minute)
  - ref: https://search.app/gpzFxEqa5rTzLYGA9
- 1.5 Pro 還可以
- 1.5 Flash 耳包（「夜皇酥軟糖」）、會幻聽（鬼打牆直到撞到 max token）

2025/2/10 update:
Gemini 2.0 is generally available; however it's speed is too slow. Comparisons:
https://github.com/cofacts/rumors-api/pull/361#issue-2839000967

## RoadMap

- [ ] Typescript
- [x] Image OCR text in AI response & text
- [x] Image OCR line bot result
- [ ] Other transcripts


## Migration of exisitng media articles

1. Release AI transcript --> lock down number of articles to migrate
2. Get articles that needs migration by filtering open data
3. Collect articles that needs migration in [Google sheet](https://docs.google.com/spreadsheets/d/1ZNNySVATxjGp-L4WJh9MgqzGnEVXaH7QLOKuCoHZ6BU/edit#gid=0)
4. Article ID --> Transcript on [Colab](https://colab.research.google.com/drive/1oorZ1B1XTDV6Ngw0dW4YkaLbumDw8W7p#scrollTo=EJ9mSDWQF6Cd)
    - article ID --> media type & media article
      - Image --> call Google API --> transcript
      - Video, audio --> call Whisper in colab (free XD) --> transcript
    - Store transcript in spreadsheet
5. Write sheet content to DB
   1. Export google sheet contnet
   2. Load them using one-off Node.JS script that calls `writeAITranscript(articleId, text)`
      - The script will write `articles.text`  (for search) and `ydoc` (For collab)
      - We probably don't need `airesponses`

## Time
- Image OCR
    - 15 min 330 articles
    - Total = 16000 --> 12 hrs
