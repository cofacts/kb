# **Authentication Architecture Comparison for Cofacts.ai (SSR)**

[Document link](https://docs.google.com/document/d/1-egmgXg54ehf419M5_BrJwj_TYS4o3s0-NEsQWdz8pM/edit?tab=t.0)

This document outlines four architectural strategies to solve the authentication challenges introduced by the new Server-Side Rendering (SSR) requirements for cofacts.ai while maintaining compatibility with the existing api.cofacts.tw and LINE Bot services.

## **Executive Summary**

| Feature | 1\. Status Quo | 2\. Custom Auth Code Flow | 3\. BFF / Trusted Client | 4\. IDaaS (Firebase/Auth0) |
| :---- | :---- | :---- | :---- | :---- |
| **Primary Auth Handler** | rumors-api | rumors-api | cofacts.ai (SSR) | Third-party Service |
| **SSR Support** | ❌ None | ✅ High (JWT) | ✅ High (Server Session) | ✅ High (ID Token) |
| **Cross-Domain** | ❌ Issues | ✅ Solved | ✅ Solved | ✅ Solved |
| **LINE Bot Impact** | No Change | No Change | No Change | Requires Token Minting |
| **Implementation Effort** | None | Medium | High | High (Refactor) |
| **Security Model** | Cookie-based | Hybrid (Cookie \+ Token) | Server-to-Server Trust | Standard Token Auth |

## **Scenario 1: Status Quo (The Problem)**

The current architecture relies on koa-session2 setting HttpOnly cookies on api.cofacts.tw.

### **Analysis**

* **Login Flow:** User redirects to API \-\> Passport.js handles OAuth \-\> API sets Set-Cookie (api domain) \-\> Redirects back.  
* **Logout Flow:** API clears the cookie.  
* **SSR Request:** **Fails.** The SSR server (running on cofacts.ai server-side) cannot access the browser's cookies set for api.cofacts.tw. It makes requests as an anonymous user.  
* **LINE Bot Request:** Uses Trusted Header (x-user-id) directly.  
* **Code Changes:** N/A.

### **Verdict**

**Untenable.** SSR pages cannot render authenticated content (e.g., "My Profile", "My Article Replies") before hydration, causing layout shift or lack of functionality.

## **Scenario 2: Custom Authorization Code Flow (Recommended for Stability)**

A logical extension of the current system. The API remains the identity provider but adds a mechanism to safely "hand over" the session to the SSR server via a back-channel exchange.

### **Analysis**

* **Login Flow:**  
  1. User logs in via API (Passport.js).  
  2. API redirects back to cofacts.ai with a short-lived, one-time use ?code=....  
  3. SSR Server immediately exchanges this code via a back-channel (POST request) to the API.  
  4. API verifies code, returns a long-lived JWT.  
  5. SSR Server sets its own HttpOnly cookie containing the JWT.  
* **Logout Flow:**  
  1. User clicks logout on Frontend.  
  2. Frontend clears SSR cookie \-\> Calls API Logout endpoint.  
  3. API clears its session cookie AND invalidates the JWT (via lastTokenResetAt in DB or Redis blacklist).  
* **SSR Request:**  
  * Reads JWT from its own cookie.  
  * Attaches Authorization: Bearer \<JWT\> header when calling rumors-api.  
* **LINE Bot Request:** No change (uses existing Trusted Header mechanism).  
* **Code Changes (Medium):**  
  * **API:** Implement code generation/storage (Redis), exchange endpoint, and JWT verification middleware (contextFactory).  
  * **Frontend:** Implement callback route to handle code exchange and cookie setting.

### **Verdict**

**Best balance.** It solves the SSR problem with minimal disruption to the existing database structure or LINE Bot logic.

## **Scenario 3: Social Login Moved to SSR (BFF / Trusted Client)**

cofacts.ai becomes a "Backend for Frontend" (BFF). It handles the complexity of OAuth (using NextAuth.js/Auth.js), while the API becomes a "dumb" resource server that trusts the SSR server.

### **Analysis**

* **Login Flow:**  
  1. User logs in on cofacts.ai (NextAuth handles Google/FB).  
  2. SSR Server obtains the user's Profile (Email, Provider ID).  
  3. Session is maintained entirely on the SSR server side.  
* **Logout Flow:** SSR Server destroys the session.  
* **SSR Request:**  
  * SSR Server calls API using a **Secret Key** (x-app-secret) to prove it is a trusted app.  
  * Passes user identity in headers: x-user-provider, x-user-id, x-user-email.  
  * API performs "lazy migration/lookup": Finds user by Social ID/Email, creates if missing, returns context.  
* **LINE Bot Request:** No change (uses existing Trusted Header mechanism).  
* **Code Changes (High):**  
  * **API:** Refactor contextFactory to parse rich user headers (email/provider) and perform "Find or Create" logic on every request (currently exists in auth.js but needs moving).  
  * **Frontend:** Full implementation of Auth library (NextAuth), management of App Secrets.

### **Verdict**

**Good for microservices.** It decouples authentication from the API. However, x-app-secret becomes a "skeleton key" with high privilege. Requires logic duplication regarding user unification (merging by email) if not careful.

## **Scenario 4: IDaaS (Firebase / Auth0) (The Modern Standard)**

Complete decoupling. Identity is offloaded to a dedicated service. rumors-api becomes a stateless resource server verifying standard tokens.

### **Analysis**

* **Login Flow:**  
  1. Frontend SDK (Client-side) handles login with Firebase/Auth0.  
  2. Returns an ID Token (JWT).  
* **Logout Flow:** Client SDK clears token.  
* **SSR Request:**  
  * Frontend passes Token to SSR (via cookie).  
  * SSR forwards Authorization: Bearer \<Token\> to API.  
  * API verifies Token signature using IDaaS public keys (stateless).  
* **LINE Bot Request (The Challenge):**  
  * **Method:** Bot Server uses IDaaS Admin SDK to **Mint a Custom Token** based on the LINE User ID.  
  * Bot sends this Custom Token to API. API treats it like any other valid user token.  
* **Code Changes (High):**  
  * **API:** Delete all Passport.js code. Implement JWT verification middleware. Implement "Lazy Migration" (map Firebase UID to existing ES Users).  
  * **Frontend:** Switch to Firebase/Auth0 SDK.  
  * **LINE Bot:** Update to mint custom tokens before calling API.

### **Verdict**

**Best Long-term Architecture.** It unifies Web and Bot authentication under a single standard (Token-based). It removes maintenance burden for OAuth flows. However, it requires the most refactoring and careful migration of existing users.

## **Recommendation**

1. **For Least Resistance:** Go with **Scenario 2 (Custom Code Flow)**. It patches the SSR hole securely without forcing a rewrite of the User database logic or the LINE Bot.  
2. **For Future Proofing:** Go with **Scenario 4 (Firebase Auth)**. If the team is willing to undergo a migration effort, this removes authentication logic maintenance from your codebase entirely.
