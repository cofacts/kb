Design: [https://stitch.withgoogle.com/projects/3329376242415119860](https://stitch.withgoogle.com/projects/3329376242415119860) 

[Canvas-like UI](https://docs.copilotkit.ai/langgraph/videos/research-canvas) via CopilotKit coagent  
[Build Agent-Native Apps with LangGraph & CoAgents (tutorial)](https://www.youtube.com/watch?v=0b6BVqPwqA0) 

# **UX 需求**

1. 使用者應該在中間的對話視窗與 AI 對話，對話介面需忠實呈現現在呼叫哪些 tool 與 subagent。

2. 使用者可以在對話途中，用左邊的 sidebar 進行切換。每個 chat session 都應有獨立的 route，如 `/session/<session_id>`。每次切換後，中間的畫面應該要顯示最新的進展，如果 agent 正在處理，也應該接著繼續載入新的結果。  
     
3. 使用者按下「新查核任務」時，會 navigate 到 `/` 或 `/new`，此時畫面中間只有一個輸入框請使用者輸入，類似 gemini 的 landing page。使用者送出 prompt 後，UI 應該要取得新 session 的 session\_id 然後 navigate 到 `/session/<session_id>`。  
     
4. Agent 在對話進行了一陣子、和使用者討論完成後，會開始寫查核回應（包含分類、回應內文與佐證資料）。回應應該寫到右側欄的「回應內文」與「佐證資料」的部分，並標記為新的版本。寫的時候能串流為佳。  
     
5. 使用者也能編輯右側欄，編輯會直接寫入該版本。若繼續對話，agent 也需要知道使用者改了哪裡。  
     
6. 請不要直接 expose ADK API endpoint 到外部的世界，那太危險。UI 應該透過 tanstack start 的 server route 來存取 ADK API。

# **Analysis**

[https://gemini.google.com/share/055b557474b6](https://gemini.google.com/share/055b557474b6)
