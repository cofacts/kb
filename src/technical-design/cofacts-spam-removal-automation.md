---
type: DesignDoc
title: "Cofacts spam removal automation"
resource: "https://g0v.hackmd.io/@cofacts/HJlJCpfZA"
tags: [cofacts, design-docs, technical-design]
timestamp: "2025-04-07T18:58:53+08:00"
---

# Cofacts spam removal automation

> Initially proposed:
> https://g0v.hackmd.io/uefTz4yURImgtem--itaMw?both#Op-%E5%9E%83%E5%9C%BE%E8%A8%8A%E6%81%AF%E5%8F%8D%E5%88%B6

## Purpose

We should be able to deal with simple spam more easily.
- No SSH access needed
- More people can approve and run takedowns
- Approvals are logged and openly accessible

When a spammer comes to Cofacts to post spam, we should be able to:

1. Automatically detect such spam.
2. Automatically generate announcement for both automatically detected and manually reported spam.
3. Approve announcement and command to execute on Github; can require just one approval, and give permission to more people.
4. Can execute the command on the approved and merged PR, with no SSH needed.

## Phases and changes

It is easier if we implement "backwards" -- start with command automation first, then the Github approval part, and put the automatic detection in the last phase.

### Phase 1: Script execution automation

<details>
<summary>Legacy design: Google Pub/sub</summary>

> This design is abandoned in favor of Cloudflare Zero Trust managed APIs.
> See https://g0v.hackmd.io/_e0nyj04SoCzxdM38CzuYQ#Op-%E5%A4%96%E9%83%A8%E6%95%B4%E5%90%88%EF%BC%9AAdmin-API for reason

Target: Can execute block user script (or any other scripts) on Google cloud console.

The UI that submits message
![](https://s3-ap-northeast-1.amazonaws.com/g0v-hackmd-images/uploads/upload_b338a25ef556f910b1f533f57b93c8f6.png)

#### API

- A service that runs along with API server
- Subscribes to pubsub
- Calls scripts as functions

#### Google Pubsub
- Create a pubsub topic just for scripts
- Design message schema
  - Include script name to execute + arguments
- Executes script on google cloud console

</details>


A new OpenAPI server is spinned up to host admin APIs.
- its implementation exists alongside with rumors-api, so that the admin APIs can leverage scripts and util functions in rumors-api
- The APIs are not exposed via nginx; instead, they map to certain domains using Cloudflare Tunnels
  - `dev-admin-api.cofacts.tw` --> `cofacts-api-staging:5500`
  - `admin-api.cofacts.tw` --> `api:5500`

#### API

Implement the following endpoint using feTS & OpenAPI. The path hierarchy is designed for easier management using Cloudflare.

- `/moderation` series: designed for Cofacts automations, including
    - POST `/moderation/blockedUser`: block a user (or update block info). Map to current `blockUser` script.
    - POST `/moderation/article/media`: replace the media of an article. Map to current `replaceMedia` script.
    - POST `/moderation/aiReply`: regenerate AI reply. Map to current `genAIReply` script.
- `/badge` series: reserved for Badge operations (TBA)
- Others: feTS provides `/docs` for Swagger UI, and `/openapi.json` for OpenAPI spec file.

We log all access to the API to console. Fields to be included:
- The invoked endpoint
- `user` - who initiated the request. Can be:
  - email, when [identity-based authentication](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/application-token/#identity-based-authentication) is used
  - [Client ID of the service token](https://developers.cloudflare.com/cloudflare-one/identity/authorization-cookie/application-token/#service-token-authentication)
- request payload

#### Cloudflare Zero Trust

##### Tunnels
`admin-api.cofacts.tw`: production site rumors-admin-api
`dev-admin-api.cofacts.tw`: staging site rumors-admin-api

##### Applications

> When multiple rules are set for a common root path, the more specific rule takes precedence. For example, when setting rules for `dashboard.com/eng` and `dashboard.com/eng/exec` separately, the more specific rule for `dashboard.com/eng/exec` takes precedence, and no rule is inherited from `dashboard.com/eng`. If no separate, specific rule is set for `dashboard.com/eng/exec`, it will inherit any rules set for `dashboard.com/eng`.
>
> [name=[Cloudflare documentation](https://developers.cloudflare.com/cloudflare-one/policies/access/app-paths/#policy-inheritance)]

General rule:
`(dev-)admin-api.cofacts.tw`: Allow all users & any service tokens
- Any emails within specific access groups can access after login
  - They can access `/docs` to read documentation
  - Emails not in whitelist can't even receive login codes
- Can use any service token to get `/openapi.json` to generate types, etc

More specific rules:
- `(dev-)admin-api.cofacts.tw/badge`: Only allow badge manager and Cofacts WG email logins & service tokens
- `(dev-)admin-api.cofacts.tw/moderation`: Only allow Cofacts WG email logins & service tokens

Email logins are included in the policy so that they work in Swagger UI.

##### Access groups

- Cofacts WG email logins: emails ending with `@cofacts.tw`
- Cofacts WG service tokens
- Badge manager email logins: emails ending in TFC and specific white lists
- Badge manager service tokens


### Phase 2: Command template in PR template

#### Command template

> - API: `/path/to/invoke`
> - Body:
>   ```json
>   {...}
>   ```

#### Takedowns Github action

- On PR creation & edit, if the pull request description includes the pattern above, check the API and its body.
- On PR merge, if the pull request description includes the pattern above, call the API with specified body with Cofacts WG service tokens.


### Phase 3: Automatic detection

#### GitHub action
- Use GitHub app to create a takedown pull request if the LLM recognizes a reply as a secondary scam (二次詐騙) or sexual content
- Schduled query reply after `LAST_SCANNED_AT` 
- Filtered out known users that existed in pervious pr by parsing the pr title
- List the 10 more replies written by the suspicious user for the moderator to review and determine if they are a spammer.

<details>
<summary>Outdated design</summary>

#### Google Pubsub
- Create a new Pubsub topic for Cofacts' object creation
- Define schema: object type + inserted doc

#### API
- Publish event on Mutation APIs
  - for creation of reply, article, etc

#### Google cloudrun/cloud function (?)
- Subscribe to the topic & calls cloudrun / cloud function.
- Consume pubsub topics, detect spam and make Github pull requests when necessary.

</details>
