# **Cofacts.ai 技術實現路徑報告**

本文件旨在說明 nDX 專案中 **Activity 1 (平台開發)** 與 **Activity 3 (系統整合)** 的具體技術執行策略。

**AI summary**  
This document outlines the technical design for the new Server-Side Rendering (SSR) Web Application, cofacts.ai, which will replace the existing rumors-site (cofacts.tw).

Key Architectural Points:

* Core Architecture: TanStack Start framework utilizing SSR primarily for security and abstraction (Middle-tier/BFF pattern) to prevent API keys from being exposed on the client. Migration will use the Strangler Fig Pattern.  
* Authentication (AuthN): The recommended stable strategy is Scenario 2: Custom Authorization Code Flow, where the SSR server exchanges a short-lived code via a back-channel request for a long-lived JWT, solving the cross-domain/SSR session challenge. Scenario 4 (IDaaS) is noted as the best long-term option.  
* ADK Server AuthN: The priority is User Context Propagation, where the user's session credentials are passed through headers from cofacts.ai to the ADK server and then forwarded by the Tools to the rumors-api, ensuring accurate user permissions.  
* Implementation Phases: The project is divided into three phases: Phase 1 for core infrastructure and AI fact-checking feature development; Phase 2 for implementing the new authentication flow and Header Propagation; and Phase 3 for feature expansion and migration.  
* UX Requirement: The chat interface must clearly display tool/subagent actions, support multi-session management, and allow the AI Agent to stream generated fact-checking responses to a right sidebar that is also editable by the user. Importantly, the ADK API endpoint must be proxied via a server route and not exposed directly to the external world.

## **1\. 核心架構與技術選型 (針對 Activity 1\)**

### **目標**

建立 cofacts.ai 為一具備 SSR 能力的獨立 Web Application，並為未來取代 rumors-site (cofacts.tw) 鋪路。

### **技術堆疊 (Tech Stack)**

* **Framework**: **TanStack Start** (或是同等級具備 Loader/Server Action 機制的現代化框架)。  
* **Deployment**: 需支援可自行部署 (Self-hosted) 的環境 (Docker/Node.js)，以利未來整合。

### **架構設計邏輯**

我們採用 **SSR (Server-Side Rendering)** 的主要目的並非為了 SEO，而是為了 **安全性與架構隱蔽性 (Security & Abstraction)**：

1. **隱藏後端細節 (Middle-tier Pattern)**：  
   * cofacts.ai 的前端用戶端 (Client) **不會** 直接連線到 rumors-api 或 ADK server。  
   * 所有敏感的 API 請求（包含 API Key、ADK 憑證等）都將透過 Webapp 的 **Server Functions (Back-end for Front-end, BFF)** 轉發。  
   * **優勢**：避免 API Key 暴露於瀏覽器端，且能在此層做額外的 Rate Limiting 或資料加工。  
2. **資料預取 (Data Loading)**：  
   * 利用 TanStack Start 的 Loaders 在伺服器端預先抓取資料 (Hydration)，確保首屏載入效能，並解決上述的 API 隱藏需求。  
3. **漸進式遷移策略 (Strangler Fig Pattern)**：  
   * cofacts.ai 上線初期為獨立服務。  
   * 中長期規劃將 cofacts.tw (rumors-site) 的既有頁面（文章列表、查核頁面等）逐步改寫並移植到此新架構中。  
   * **終局狀態**：新架構完全取代舊站，屆時 cofacts.ai 的路由將整併回 cofacts.tw/ai (或直接成為主站)，統一流量入口。

## **2\. 登入系統與身份驗證整合 (針對 Activity 3\)**

Main design doc: See [Authentication](?tab=t.3fmvmgsjjweh)

### **挑戰**

* 舊站 cofacts.tw 使用傳統 Cookie-based session。  
* 新站 cofacts.ai 為 SSR 架構，且初期可能位於不同網域/子網域，加上 Server-side data fetching 需求，無法直接讀取客戶端 Cookie 進行身份驗證。

### **解決方案：Server-side SSO (Authorization Code Flow)**

我們將實作一套能夠支援 SSR 伺服器端身份驗證的單一登入機制。

#### **具體流程 (Scenario 2 實作路徑)**

1. **使用者發起登入**：  
   * 使用者在 cofacts.ai 點擊「登入 (Login with Cofacts)」。  
   * 瀏覽器被導向至 api.cofacts.tw 的授權頁面 (Auth Endpoint)。  
2. **身份確認與授權**：  
   * 使用者在 api.cofacts.tw 完成登入（或已登入）。  
   * api.cofacts.tw 生成一個短效期的 **Authorization Code**。  
   * 瀏覽器帶著這個 Code 被重新導向 (Redirect) 回 cofacts.ai/callback。  
3. **後端通道交換 (Back-channel Token Exchange)**：  
   * **關鍵步驟**：cofacts.ai 的 **Server** 接收到 Code 後，直接從伺服器端向 cofacts.tw 的 API 發送請求 (Back-channel request)。  
   * 以 Code 交換使用者的 **Session Token / User Profile**。  
   * *註：此過程完全在伺服器間進行，Token 不會暴露在 URL 或前端 JS 中。*  
4. **建立新站 Session**：  
   * cofacts.ai 驗證成功後，在自己的網域下設定 HttpOnly Cookie (Session ID)，完成登入。  
   * 後續 cofacts.ai 的 Server Function 即可憑此 Session 代表使用者向 rumors-api 請求資料。

細節請參考 [Authentication](?tab=t.g3d1u3spsaad).

### **2.1 ADK Server 與 Tool 的身份驗證機制**

當 ADK Server 內的 Agent/Tools 需要回頭呼叫 rumors-api (例如：搜尋既有謠言、讀取使用者過往回應) 時，需採用以下驗證策略：

#### **A. 使用者脈絡透通 (User Context Propagation) \- *優先採用***

當 cofacts.ai 呼叫 ADK 進行對話生成時，需將「當前使用者的身份憑證」一併傳遞過去。

* **流程**：  
  1. cofacts.ai (SSR) 從 Session 中取得 user\_id 與 access\_token。  
  2. cofacts.ai 呼叫 ADK API 時，將這些資訊放入 Header (例如 X-Cofacts-User-Id, Authorization)。  
  3. ADK 內部的 Tool 在執行 fetch() 呼叫 rumors-api 時，直接轉發這些 Header。  
* **優點**：權限最為精確，Tool 看到的資料與該使用者在網站上看到的一致（包含私有資料權限）。  
* **缺點**：ADK 需實作 Header 轉發邏輯。

#### **B. 服務識別 (Service Identity) \- *備援/系統級任務***

若 Tool 僅需讀取公開資料（如公開謠言列表），不涉及特定使用者權限。

* **流程**：  
  1. 為 ADK Server 申請一組專用的 APP\_ID 與 APP\_SECRET。  
  2. ADK Tool 呼叫 rumors-api 時，使用這組系統級憑證進行驗證。  
* **優點**：實作簡單，與使用者登入狀態解耦。

## **3\. 執行階段劃分 (Action Items)**

### **Phase 1: 基礎建設 (Activity 1\)**

* 初始化 TanStack Start 專案 repo。  
* UI library according to [子龍 Figma](https://www.figma.com/design/nFFi6c8ennXV8CxeF58Asl/Confact?node-id=0-1&p=f&t=27jepKYsqBCCkD72-0)  
* 實作 Server Function 封裝 ADK server  
* 開發 AI 查核協作功能 (Activity 1 核心業務)。  
* 建立基本的 Chat UI 介面框架  
* Deploy ADK server & [Cofacts.ai](http://Cofacts.ai) 

### **Phase 2: 身份驗證對接 (Activity 3\)**

* **Legacy Side**: 修改 api.cofacts.tw (rumors-api)，新增 OAuth-like 的 Endpoint (/authorize, /token)。  
* **New Side**: 在 cofacts.ai 實作 Callback 路由與 Back-channel 交換邏輯。  
* **ADK Side**: 實作 Header Propagation，讓 ADK Tools 能接收並使用 cofacts.ai 傳來的 User Token 呼叫 API。  
* 驗證 SSR 頁面在登入狀態下，能否正確讀取使用者專屬資訊。

### **Phase 3: 功能擴充與遷移**

* 評估並開始遷移舊站簡單頁面至新架構，測試路由導向。