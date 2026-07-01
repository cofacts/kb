---
type: DesignDoc
title: "ChatGPT integration"
resource: "https://g0v.hackmd.io/@cofacts/rknFrmdk3"
tags: [cofacts, design-docs, technical-design]
timestamp: "2023-04-12T20:33:00+08:00"
---

# ChatGPT integration

Large language models can be helpful to human beings when  they encounter internet hoax.

> [!NOTE]
> This document now only contains implementation detail.
>
> Original use cases and related research has been moved to https://g0v.hackmd.io/@cofacts/rd/%2FmU8qi721RZeAQ9PDfj7XRA

## Scenario #1: point out suspicious points

For scenario #1 identified in the research document, the ChatGPT response on critical thinking of the forwarded messages are called "AI replies".

### Chatbot

When to create AI reply:
- Is text message
- Text length > 20 (?)
- No AI replies yet

Can implement a `getOrCreateAiReply(articleId)` helper function for the following scenarios.

#### After searching a message that has not been replied yet

> https://www.figma.com/proto/1tiXCGut4kNCEkDG9FTza7/LINE-Chat-UI-Template-(Community)?page-id=208%3A844&node-id=302-1236&viewport=294%2C-41%2C0.53&scaling=scale-down

- Not clear that this is AI text
    - 「還沒有人回應唷。在這之前，可以參考以下 ChatGPT 的自動回應。」
    - 「在真人回覆前，AI 媒體識讀小幫手 (ChatGPT) 針對這篇訊息有以下看法。」
    - ✅ 「這篇文章尚待查核，請先不要相信這篇文章。機器人初步分析此篇文章有下列幾點需要特別留意：」[name=cai]
- surrounding text
    - 「請先不要相信這篇文章唷」will show for images / videos, because they don't have AI response
- More calls to action on the quality of this AI-generated content?
    - Thumbs-up / thumbs-down feedback?

#### After submitting a new message to database

(Note: this does not apply if we decide to only generate AI replies for messages with >=2 reply requests.)

> https://www.figma.com/proto/1tiXCGut4kNCEkDG9FTza7/LINE-Chat-UI-Template-(Community)?page-id=208%3A844&node-id=339-1260&viewport=334%2C-393%2C0.53&scaling=scale-down

- Last 5 sentences are identical.

#### After voting a reply as not useful

Nice-to-have

### Site

> https://www.figma.com/file/DvmAQjMJCncuPORWKnljM1/Cofacts-LIFF-and-new-designs?node-id=5133-543&t=sml0QRW7fnGr8xfV-4



Display an extra section when all of the below is satisfied:
- An AI reply is already generated
- No (useful) replies yet

Discussion
- No replies v.s. no useful replies?
- Should we still show the section if there are replies?
  - Should we show them in collapsed state, like the collapsible contribution graph in user profile page?

> [!TIP]
> 2023/3/22 meeting:
> - Pick left design (differentiate user reply & AI reply)
> - Always show ChatGPT section
>   - Collapse when have human reply

### Elasticsearch

- No need to index / search by text
- Need to index by user ID, doc ID, etc.

#### New index: `airesponses`

- Records all AI responses; not limited to AI replies.
- Collect all AI responses in one index to better manage quota.
- May support more use cases in the future.
- Creates one `aiResponse` doc with `status=LOADING`
  - In async scenarios (if there is one), users can poll `aiResponses` to get latest update
- Updates the doc by providing `text`, `usage`, `resolvedAt`.

Fields
- `docType`, `docId`: the target of this response.
  - May be empty for scenario #2
- `text`: AI response
- `userId`, `appId`: the user that generated this content
- `request`: API request body
    - No need to index, just for record.
    - `{type: 'keyword', index: false, doc_values: false}`
- `usage`: API response of token usage
  - `promptTokens`, `completionTokens`, `totalTokens`
- `status`: `LOADING` | `SUCCESS` | `ERROR`
- `createdAt`
- `resolvedAt`

#### New index: `airesponsefeedbacks`

- `aiResponseId`
- `userId`, `appId`: the user giving feedback
- `score`: 1, -1
- `comment`
- `createdAt`, `updatedAt`
- `status`: `NORMAL`, `BLOCKED`

### API

#### New `AIResponse` object type

Exposes the fields in elasticsearch index `airesponses`.

Also:
- `feedbacks`
  - Arg: `statuses`
  - type: `AIResponseFeedback`
- `positiveFeedbackCount`
- `negativeFeedbackCount`

#### New `AIResponseFeedback` object type

Exposes fields in elasticsearch index `airesponsefeedbacks`.

#### New mutation `createAIReply`

Generates new AI response doc that points to an article.

(If we will have other AI responses in the future, use another mutation,)

Inputs
- `articleId`: `String`
- `waitForCompletion`: `Boolean`

Output
`AIResponse` object.

#### New mutation `createOrUpdateAiResponseFeedback`

Inputs
- `aiResponseId`
- `score`
- `comment`

Outputs
`AiResponse` object.

#### New query `ListAIResponses`

- filter by `docType`, `docId`, `userId`, `appId` , `createdAt`, `resolvedAt`, etc
- order by `createdAt`, `resolvedAt`

#### New query `ListAIResponseFeedbacks`

- filter by `docType`, `docId`, `userId`, `appId` , `createdAt`, `resolvedAt`, etc
- order by `createdAt`, `resolvedAt`

#### `Article` object type

- New field `aiReplies`
  - type: `AIResponse`


## Roadmap

### Phase 0: preparation
- [x] Elasticsearch: `airesponses`
- [x] API: `createAIReply`, `AIResponse`, `ListAIResponses`, `Article` object type
- [x] Deploy API with openai token

### Phase 1: AI reply
- [x] Chatbot: `getOrCreateAiReply(articleId)`, no-reply-yet scenario
- [x] Website: display the AI reply

### Phase 2: Feedbacks for the AI reply
- [ ] Elasticsearch: `airesponsefeedbacks`
- [ ] API: `ListAIResponseFeedbacks`, `AIResponseFeedback`
- [ ] Chatbot: Feedback card, feedback LIFF
- [ ] Website: feedback buttons

## Scenario #1 extended: Provide search keywords

> [!WARNING]
> Priority:
> As discussed on 2023/4/12, we will implement keyword first, then feedbacks for AI reply.
> - Evaluation can come later, get BETA version of keywords first [name=bil]

chatbot: https://www.figma.com/proto/1tiXCGut4kNCEkDG9FTza7/LINE-Chat-UI-Template-(Community)?node-id=302-1236&scaling=scale-down&page-id=208%3A844
website: https://www.figma.com/file/DvmAQjMJCncuPORWKnljM1/Cofacts-LIFF-and-new-designs?node-id=5163-546&t=nHTu1xJbgYP5rEao-4
