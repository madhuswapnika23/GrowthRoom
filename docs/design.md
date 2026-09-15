# Growth Room — Frontend Design Document

> This document describes the actual implemented UI — layouts, states, accessibility choices, and responsive behaviour — as derived from the source code.

---

## 1. Three-Surface Rationale

The interface is divided into three vertical surfaces in a CSS Grid layout (`grid-template-columns: 260px 1fr 340px`).

### Surface 1 — Sessions Rail (left, 260 px fixed)

**Purpose:** Context-switching without losing the current conversation.

The rail shows every past session as a clickable card with:
- Title: the first user message, truncated to 60 characters.
- Timestamp: `created_at` formatted for local display.
- Artifact pill: appears if the session produced at least one artefact.
- Grounding badge: colour-coded average relevance score from the most recent assistant message.

The active session is highlighted with a left amber border (`var(--color-accent)`) and a faint amber background tint.

**Rationale:** Separating session navigation from content prevents the common pattern of losing context when a user wants to start a new question but still needs the current answer visible. The rail is always present on desktop, so switching costs nothing cognitively.

### Surface 2 — Conversation Log (center, fluid)

**Purpose:** The primary interaction and reading surface.

Each assistant message contains:
- A **role label row** with the word "Assistant" and a **skill badge** (`🔍 Grounded Q&A`, `✍️ Ship 30 Essay`, `📄 Artifact Gen`) derived from `skill_used` in the API response. This makes the router's decision visible without consulting logs.
- A **grounding meter** — a 4-pixel bar showing the average chunk similarity score coloured green (confident) or amber (low/empty retrieval). The label changes to "Not enough source material" when `grounding_score < 0.1`.
- The **message content** rendered as Markdown via `react-markdown` (headers, bullets, bold all styled).

User messages are styled differently: larger serif font, muted colour, no background card — they read like editorial queries rather than chat bubbles.

**Preset prompt chips:** On the empty state (no messages), three sample prompts are shown as full-width chip buttons: *Retention Loops (Grounded Q&A)*, *Ship 30 Essay (Product-Market Fit)*, *HTML Dashboard (Artifact UI Generator)*. These trigger `onSend` directly.

**Input bar:** Fixed to the bottom of the conversation log (`position: absolute; bottom: 0`). Textarea accepts multi-line input; Enter sends, Shift+Enter inserts newline. Disabled during loading to prevent message queuing.

**Rationale:** Keeping the conversation readable is critical when responses include Ship 30 essays of 1,000+ words. The skill routes those to the Artifact panel and only shows a one-line confirmation in chat. The grounding meter is inline above the message — before the user reads the answer — so trust signals are never an afterthought.

### Surface 3 — Right Panel (right, 340 px fixed)

**Purpose:** Deep-inspection without cluttering the chat surface.

Three tabs:

| Tab | Content |
|---|---|
| **Artifact** | Rendered artefact (Markdown via `react-markdown` or HTML via sandboxed `<iframe>`) with a Rendered/Source toggle, Copy, and Download button |
| **Sources** | List of cited podcast chunks: episode title, guest, chunk reference, relevance score, YouTube link |
| **Model** | Active LLM provider status, fallback indicator pill, and provider override radio buttons |

**Auto-switching:** When a `POST /chat` response includes a non-null `artifact`, the right panel programmatically switches to the Artifact tab (`useEffect` on the `artifact` prop).

**Session restoration:** When a session is loaded via `GET /sessions/{id}`, the last assistant message's `sources` and `artifact` are extracted and passed to the right panel, so the artefact and citations from a previous session are immediately visible.

**Rationale:** The three-tab design keeps the right panel content width consistent while allowing radically different content types. A user can answer a follow-up question in chat while referring to the sources panel without losing their place.

---

## 2. Information Architecture & Key States

### States

| State | Trigger | UX |
|---|---|---|
| **Empty** | No messages in session | Centered title + subtitle + preset chip buttons |
| **Loading** | `POST /chat` in flight | Typing indicator (3 animated dots) below last message; input disabled |
| **Session loading** | `GET /sessions/{id}` in flight | "Loading session…" spinner in conversation area |
| **Error** | Network failure, 4xx/5xx from API | Inline red error banner (`.error-banner`) below the last message; does not replace the conversation |
| **Low retrieval** | Grounding score < 0.1 | Grounding meter renders in amber with label "Not enough source material" |
| **Fallback active** | `fallback_active: true` from `/model/status` | Model tab pill turns amber with text "Fallback Active" |
| **Artefact present** | `artifact` non-null in response | Right panel auto-switches to Artifact tab; artifact badge shows type |

### Component Data Flow

```
App.jsx (state owner)
├─ sessions[]            → SessionsRail
├─ activeSessionId       → SessionsRail (active highlight)
├─ messages[]            → ConversationLog
├─ activeSources[]       → RightPanel (Sources tab)
├─ activeArtifact        → RightPanel (Artifact tab)
└─ rightTab              → RightPanel (active tab)
```

All events flow upward: `onSend`, `onSelect`, `onDelete`, `onNew`, `onTabChange`. Components hold no application state.

---

## 3. Responsive Behaviour (Mobile)

Breakpoint: `768px` (CSS `@media (max-width: 768px)`).

At mobile widths:
- The CSS Grid collapses to `grid-template-columns: 1fr` (single column).
- All three panels stack to `grid-column: 1 / 2` — only one is visible at a time.
- The header bar gains a 3-button icon switcher: 💬 (chat), 📚 (sources), 📄 (artifact).
- The `mobilePanel` state in `App.jsx` tracks which panel is visible.
- Components receive a `mobileVisible` prop; those not matching `mobilePanel` apply `display: none !important` via `.mobile-hidden`.

**Tab synchronisation:** On mobile, the right panel's `effTab` is forced to match the active `mobilePanel` (`artifact` → "Artifact", `sources` → "Sources"), so the desktop tab state and mobile panel state stay in sync when the user returns to desktop width.

---

## 4. Accessibility

| Concern | Implementation |
|---|---|
| Landmark roles | `<header>`, `<main>` (ConversationLog), `<aside>` (RightPanel), `<nav>` (SessionsRail rail header, RightPanel tabs) |
| Tab panel pattern | Panel tabs use `role="tablist"`, `role="tab"`, `aria-selected`, `aria-labelledby`. Tab panel content has `role="tabpanel"` with `aria-labelledby` pointing to tab ID. |
| Keyboard navigation | Textarea `onKeyDown`: Enter sends, Shift+Enter inserts newline. Tab key navigates between interactive elements natively. |
| Button IDs | Key interactive elements have unique IDs: `#tab-artifact`, `#tab-sources`, `#tab-model`, `#btn-artifact-toggle`. |
| Focus management | No `tabIndex` manipulation; natural DOM order is the focus order. |
| Colour contrast | Body text `#f0ede8` on `#0d0d0d` background — exceeds WCAG AA contrast ratio. Accent amber `#c8a96e` used only for decoration/hover, not as the sole signal carrier. Error state uses both red colour and the word "Error:" in text. |
| Screen reader text | Grounding meter label is visible text (not icon-only). Skill badge has a `title` attribute with the canonical skill name. |

---

## 5. Design Tokens

All design decisions are encoded as CSS custom properties in `index.css`:

```css
--color-bg:              #0d0d0d   /* page background */
--color-surface-1:       #141414   /* panels, cards */
--color-surface-2:       #1c1c1c   /* message bubbles, input */
--color-surface-3:       #242424   /* hover states, badges */
--color-accent:          #c8a96e   /* amber — active tab, highlight */
--color-accent-dim:      #8a6f3f   /* source left-border */
--color-success:         #4caf7d   /* grounding meter (high confidence) */
--color-warning:         #e5a443   /* grounding meter (low / fallback) */
--color-error:           #d94f4f   /* error banner */
--font-sans:   'Inter', system-ui
--font-serif:  'Playfair Display', Georgia   /* used for logo and user messages */
--font-mono:   'JetBrains Mono', 'Fira Code' /* code blocks, source indices */
```

Typography is loaded from Google Fonts via `index.html` `<link>` tags. Fonts include Inter (UI), Playfair Display (editorial heading), and JetBrains Mono (monospace).
