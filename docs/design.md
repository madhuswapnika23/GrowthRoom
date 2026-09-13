# Growth Room — Frontend Design & Integration

## 1. Three-Surface Rationale

The Growth Room interface is structured around three primary vertical surfaces, optimizing for densely packed informational workflows without overwhelming the user:

1. **Sessions Rail (Left, 260px)**: A transient space. Provides quick context switching between conversations. Displays title, timestamp, and a Grounding Badge — a quick heuristic for whether a past session was highly factual or a hallucination/low-confidence fallback.
2. **Conversation Log (Center, fluid)**: The primary interaction space. Structured as a feed. The assistant’s responses are rendered as Markdown briefs (with headers/bullets) for immediate scannability. Grounding meters live *inline* above each assistant message to contextualize that specific answer's reliability before reading.
3. **Right Panel (Right, 340px)**: Deep-dive inspect space. Tabs keep the context clean but switchable:
   - *Artifact*: Renders structured outputs (like an HTML dashboard or a long Markdown essay) separate from the chat flow, preventing the chat from becoming unreasonably long.
   - *Sources*: Inspects the exact podcast transcripts cited by the assistant, maintaining the strict factual constraint of this AI system.
   - *Model*: Developer controls ensuring transparency over the active LLM provider.

## 2. Information Architecture

- **State Management**: Housed entirely in the root `<App />` component. All components are purely presentational, passing events up (`onSend`, `onSelect`, `onDelete`).
- **Data Fetching**: Optimistic UI updates on message send, followed by strict synchronization with the FastAPI backend.

## 3. Responsive Behavior (Mobile)

On screens narrower than 768px, the three-surface layout collapses into a single-column layout via CSS Grid overrides.
- **Top Bar**: Gains a unified 3-icon tab switcher (💬 Chat, 📚 Sources, 📄 Artifact).
- **Navigation**: The Sessions Rail replaces the Chat log entirely when active. Once a session is clicked, it hides itself and shows the Chat. The tab switcher at the top flips the single visible column between the Conversation Log and the deeply inspected Right Panel content.

## 4. State & Error Handling

- **Loading**: Optimistic "typing indicator" animation appears immediately upon sending a message. The input box disables to prevent race condition queuing.
- **Errors (API Key Missing, DB connection, Ollama offline)**: Rendered inline as high-contrast red error banners (`.error-banner`) within the conversation log, rather than obstructive popups. This preserves context.
- **Empty Retrieval**: Handled as a domain state, not a bug. If the LLM generates a response without retrieving sources (or falls below threshold), the Grounding Meter renders in a distinct "Warning/Yellow" state explicitly stating "Not enough source material" and the score forces to 0.

## 5. Security & Accessibility

- **HTML Sandboxing**: All LLM-generated HTML requested via the Artifact Gen skill is rendered within an `<iframe>` lacking `allow-scripts` or `allow-same-origin`. This strictly isolates untrusted HTML, preventing XSS injection while still permitting the user to visualize CSS layouts.
- **Accessibility**: 
  - Semantic HTML (`<main>`, `<aside>`, `<nav>`).
  - ARIA `role="tablist"` and `role="tab"` bindings linking the Right Panel tabs to their respective content panels.
  - Keyboard navigation (`onKeyDown` for Enter-to-send without Shift).
