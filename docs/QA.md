# Growth Room - Manual QA Checklist

This document contains a structured checklist for manual visual and behavioral testing of the Growth Room UI/UX. Automated tests cover the backend, but the interaction surface must be validated manually to ensure the implementation matches the PRD requirements.

| Feature Area | Scenario / Action | Expected Result | Pass / Fail |
| :--- | :--- | :--- | :--- |
| **Responsive Layout** | Load app on Mobile device (width < 768px) | The Sessions Rail, Conversation Log, and Right Panel are collapsed into a single column with a mobile tab switcher header. | |
| **Responsive Layout** | Load app on Desktop device (width >= 768px) | The three vertical columns (Rail, Conversation, Output Panel) render side-by-side filling the viewport. | |
| **Sessions Rail** | Click \"New Session\" button | The Conversation Log and Right Panel clear out. A new unnamed session is initiated in state. | |
| **Sessions Rail** | Send first message in a New Session | The API creates the session, generating a Title and snippet from the message. The rail updates to show this new card at the top. | |
| **Sessions Rail** | Scroll through sessions | Sessions are ordered chronologically (newest at top). Grounding Badges display \"High/Med/Low\" accuracy. | |
| **Sessions Rail** | Click a historical session card | The center panel fetches and displays that session's messages. Right tabs load any connected artifacts. | |
| **Conversation** | Send a known query (\"How do I build a growth loop?\") | The user message appears as a quoted header. Assistant response streams or appears formatting Markdown correctly. | |
| **Grounding Meter** | Observe an assistant message with high DB retrieval | The meter above the message shows \"Grounded\" with a green filled meter bar. Citations (e.g. `[1]`) are visible inline. | |
| **Grounding Meter** | Ask \"What is the capital of France?\" (No context available) | The LLM states it lacks context. The Grounding Meter distinctly visually flags \"Not Enough Source Material\". | |
| **Markdown Parsing** | Assistant returns bullet points & bold text | The raw Markdown correctly transforms into HTML elements (`<ul>`, `<li>`, `<strong>`) in the Conversation log. | |
| **Artifact Tab** | Send a prompt generating an Artifact (e.g. \"Write an email sequence\") | The LLM responds. The \"Artifacts\" tab in the right panel becomes active and displays the returned artifact markdown natively. | |
| **HTML Sandbox** | Ask the LLM to output an HTML web widget | The artifact returned is HTML. It renders within the sandboxed `<iframe>` structure (no scripts, isolated styling). | |
| **Sources Tab** | Click the Sources tab after a retrieved answer | The tab shows the exact Episode title, timestamp, and text segment that matching the inline `[1]` citation format. | |
| **Model Info** | Click the Model tab | Shows standard API telemetry (LLM Provider, token usage, latency). | |

## Verification Notes

- To deploy against the cloud fallback mechanism, drop internet connectivity locally or provide an invalid `ANTHROPIC_API_KEY` to verify Ollama fallback engages smoothly during agent generation context.
- DB persistence can be easily tested by refreshing the entire browser window `(Cmd+R)` mid-conversation to confirm context isn't lost.
