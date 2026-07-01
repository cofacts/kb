---
type: DesignDoc
title: "Langfuse LLM observability"
resource: "https://g0v.hackmd.io/@mrorz/rye37jR-71x"
tags: [cofacts, design-docs, technical-design]
timestamp: "2025-02-03T18:32:51+08:00"
---

# Langfuse LLM observability

> [!NOTE]
> - [Infra proposal](https://g0v.hackmd.io/_e0nyj04SoCzxdM38CzuYQ?both#Langfuse)
> - [Deployment & project plan]( https://g0v.hackmd.io/GxzR0adaS8uNuaP7Vq7pfA?both#Langfuse)

https://langfuse.cofacts.tw
- Only cofacts.tw emails can create account
- Can make trace public to act as discussion material
- Each git repository uses 1 Langfuse project.

## rumors-api

Record AI reply & transcripts.

> [!TIP]
> DONE: https://github.com/cofacts/rumors-api/pull/355


## rumors-line-bot

Use Langfuse to visualize 1-1 conversation between user and Cofacts bot

[TBA]

## Takedowns

- Record AI classifier result
- [Optional] store prompt in Langfuse?

> [!TIP]
> DONE: https://github.com/cofacts/takedowns/pull/138/files
