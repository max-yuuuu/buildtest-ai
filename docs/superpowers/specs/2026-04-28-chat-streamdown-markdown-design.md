# Chat Streamdown Markdown Rendering Design

## Background

The current `frontend/app/(dashboard)/chat/page.tsx` renders `UIMessage.parts` almost directly. This causes backend stream metadata such as `data-step`, `tool-*`, and raw citation payloads to appear as JSON blocks in the main conversation area.

That output is useful for debugging, but it is a poor default reading experience. The page should instead behave like mainstream chat products:

- assistant answers are the primary content
- stream progress is visible but lightweight
- citations are shown as sources, not raw JSON
- internal tool and step details do not interrupt reading

This change introduces streaming markdown rendering with `streamdown` and related plugins while keeping the existing `useChat` + BFF stream protocol intact.

## Goal

Adopt a cleaner assistant message presentation for `http://localhost:3000/chat`:

1. Render assistant text as streaming markdown.
2. Support enhanced code block rendering.
3. Support Mermaid fenced blocks with graceful fallback.
4. Show lightweight generation status instead of raw step JSON.
5. Show citations in a dedicated sources section.
6. Hide raw tool and step payloads from the default reading experience.

## Non-Goals

- No redesign of the backend event protocol.
- No full debug sidebar or developer console UI in this change.
- No history/session architecture changes.
- No rich text editor for the prompt input.
- No citation deep-link system into source documents.

## Chosen Approach

We will use a view-model layer between `UIMessage.parts` and the page UI.

Instead of rendering each part directly in `page.tsx`, the frontend will:

1. Normalize each `UIMessage` into a chat-specific display model.
2. Render assistant text through `streamdown`.
3. Derive a short human-readable status line from `data-step`.
4. Extract citations into a separate sources block.
5. Suppress raw `tool-*` and `data-step` content from the primary message body.

This is an incremental frontend-only presentation refactor. It improves UX without forcing a protocol rewrite.

## UX Design

### Message Information Hierarchy

Each assistant message is split into four logical layers:

1. **Body**
   - The main answer content.
   - Rendered as markdown through `streamdown`.
   - This is the only always-visible content block.

2. **Status**
   - A subtle one-line progress indicator.
   - Examples:
     - `正在检索知识库...`
     - `已检索到相关内容，正在生成回答...`
   - Displayed in muted styling and de-emphasized once answer text is streaming steadily.

3. **Sources**
   - A dedicated citations area below the answer.
   - Shows structured source cards instead of JSON.
   - Initially collapsed or visually compact.

4. **Hidden raw metadata**
   - `data-step`
   - `tool-*`
   - raw low-level transport details
   - These remain available in the message data model but are not rendered by default.

### User-Facing Behavior

- User messages remain simple right-aligned bubbles.
- Assistant messages become wider, more readable content blocks.
- Markdown content streams progressively.
- Citations appear as a separate section after or alongside the completed response.
- Errors are displayed as human-readable feedback cards, not raw JSON dumps.

## Frontend Architecture

### New Display Model Layer

Add a normalization utility that converts raw `UIMessage.parts` into a stable view model for rendering.

Proposed output shape:

```ts
type CitationView = {
  id?: string;
  title?: string | null;
  knowledgeBaseId?: string | null;
  snippet?: string | null;
  score?: number | null;
};

type ChatMessageViewModel = {
  id: string;
  role: "user" | "assistant" | string;
  markdownText: string;
  statusText: string | null;
  citations: CitationView[];
  errorText: string | null;
};
```

The exact field names can vary, but the design requires a clear separation between renderable body content and auxiliary metadata.

### Component Boundaries

Recommended file split:

- `frontend/app/(dashboard)/chat/page.tsx`
  - page shell, form submission, `useChat`, list rendering
- `frontend/lib/chat-message-view-model.ts`
  - normalize `UIMessage.parts` into a display model
- `frontend/components/chat/assistant-markdown-message.tsx`
  - render assistant body with `streamdown`
- `frontend/components/chat/chat-status-line.tsx`
  - render muted progress copy
- `frontend/components/chat/chat-citation-list.tsx`
  - render source cards or a compact collapsible sources block

This keeps `page.tsx` from becoming a mixed protocol/UI/parser file.

## Streamdown Integration

### Dependencies

Add:

- `streamdown`
- `@streamdown/code`
- `@streamdown/mermaid`

### Integration Boundary

`streamdown` is used only for assistant markdown body rendering.

It is not responsible for:

- overall chat layout
- step/tool presentation rules
- source card layout
- form/input behavior

That boundary is important because the current problem is partly a protocol-to-UI mapping issue, not only a markdown rendering issue.

### Markdown Rendering Rules

- Concatenate assistant `text` parts into a single markdown string.
- Feed that string into the assistant markdown renderer.
- Preserve streaming updates as the text grows.
- Ensure layout remains stable while content is still incomplete.

## Code Blocks and Mermaid

### Code Block Experience

The goal is not IDE-like functionality; the goal is a stable reading experience during streaming.

Requirements:

- fenced code blocks render clearly
- partial streaming code blocks do not cause excessive layout thrash
- long blocks remain readable and visually distinct
- code styling is consistent with the existing dashboard theme

### Mermaid Support

Mermaid support applies only to fenced `mermaid` blocks.

Fallback behavior is mandatory:

- if Mermaid rendering succeeds, show the diagram
- if Mermaid rendering fails, render the raw fenced block as a normal code block
- a Mermaid failure must not break the rest of the assistant message

## Status Derivation

`data-step` parts should be mapped into short human-readable status text.

Suggested mapping:

- retrieve running -> `正在检索知识库...`
- retrieve completed and no visible answer yet -> `已检索到相关内容，正在生成回答...`
- answer already streaming -> status can be hidden or shown in a weaker muted style

The design does not require full fidelity to every backend step event. It requires a stable and friendly status abstraction.

## Citation Presentation

`data-citation` parts should be extracted and rendered in a dedicated sources block rather than inline JSON.

Each source item should support:

- source title
- related knowledge base identifier or badge when available
- optional snippet if the event payload contains one
- optional weak score display if needed later

The initial UI may be compact:

- `引用来源 2`
- expand to reveal structured source cards

If snippet data is absent in the current transport payload, the first version may render title + KB badge only.

## Error Handling

`data-error` should not render as a raw `pre` block.

Instead:

- convert it to a concise error card
- use human-readable copy
- keep styling visually distinct but not noisy

If both answer text and an error exist, the UI should prefer preserving any answer text already streamed and show the error as a secondary alert.

## Testing Strategy

### View-Model Tests

Add focused tests for the normalization layer:

- combines assistant `text` parts into `markdownText`
- turns `data-step` into `statusText`
- extracts citations into `citations[]`
- suppresses raw tool payloads from the primary rendered body

### UI Tests

Update chat page tests so they assert:

- assistant markdown text is rendered
- citation JSON is no longer rendered directly
- tool raw output is hidden by default
- lightweight status copy appears when step data exists

### Resilience Tests

Cover graceful fallback behavior:

- Mermaid block render failure falls back to code block output
- malformed auxiliary data does not break the assistant message render

## Risks and Mitigations

### Risk: Streamdown conflicts with current AI SDK message flow

Mitigation:
- keep `useChat` unchanged
- integrate only at assistant body rendering level
- normalize parts first, render second

### Risk: Mermaid rendering breaks streaming stability

Mitigation:
- scope Mermaid only to fenced blocks
- require fallback to plain code blocks

### Risk: Existing tests are tightly coupled to raw JSON rendering

Mitigation:
- replace low-value raw rendering assertions with view-model and user-visible output assertions

## Implementation Outline

1. Add frontend dependencies.
2. Create a message normalization utility for `UIMessage.parts`.
3. Extract assistant message rendering into dedicated components.
4. Integrate `streamdown` for assistant markdown.
5. Add code block and Mermaid plugin wiring with fallback handling.
6. Replace raw citation rendering with a sources section.
7. Replace raw step rendering with lightweight status text.
8. Update unit tests around message normalization and page rendering.

## Open Decisions Resolved

- **Chosen scope:** enhanced markdown streaming with code and Mermaid support
- **Chosen process visibility:** lightweight status only
- **Chosen architecture:** frontend view-model layer plus dedicated rendering components
- **Chosen rollout style:** incremental UI refactor without backend protocol redesign
