---
type: DesignDoc
title: "API client management [Obsolete]"
resource: "https://g0v.hackmd.io/@cofacts/BkPJVtwJ2"
tags: [cofacts, design-docs, technical-design]
timestamp: "2023-08-10T02:40:53+08:00"
---

# API client management [Obsolete]

> Research doc:
> https://g0v.hackmd.io/@cofacts/rd/%2F51wwLHgvSUqtBDaP-yAVnA

## Server-server communication

- All HTTP requests should have header `x-app-id` and `x-signature`.
- Each client is assigned an app ID and app secret
- When client sends request:
  - `x-signature` header is calculated by encoding HTTP request body with secret, in the same method by  https://developers.line.biz/en/docs/messaging-api/receiving-messages/#verifying-signatures
    1. Calculate HMAC of the request body (in UTF-8) with secret being the app secret, and hash being SHA-256.
    2. Encode the HMAC value with base64
- When server receives request
  - Retrieve secret using x-app-id
  - calculate signature in the same way

## Client Management

YAML file as a database.
- mounted in `data/` as `clients.yaml`
  - Mounted under an empty folder `data` so that it can be picked up without restarting whole docker
  - Mounting under folder is also how Cloud Run supports file secrets
- Loaded to memory on server startup
- When updated, can gracefully reload pm2 inside docker container


## Other enhancements

### Typescript on rumors-api

### Moving User ID from URL

Currently the API accepts userId on URL, which can be captured by http loggers easily.

We should move it to HTTP header. Although it is not protected by signature, it is easier than providing it in GraphQL HTTP payload -- at least it is doable in GraphQL playground. (signature is hard in playground, though)

### Only creating user on mutations

Currently
- schema stitching will cause lots of HTTP requests in parallel
  - All of which are query, not mutations
  - The automatic account creation logic causes Elasticsearch error when multiple queries wanting to create the very first 

## Progress

