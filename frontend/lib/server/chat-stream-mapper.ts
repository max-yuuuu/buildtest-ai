export type BackendEvent = Record<string, unknown> & { type?: string };
type UiChunk = Record<string, unknown> & { type: string };

function messageIdOf(evt: BackendEvent, fallback = "msg_fallback"): string {
  const raw = evt.message_id;
  return typeof raw === "string" && raw.length > 0 ? raw : fallback;
}

function toolCallIdOf(evt: BackendEvent): string {
  const raw = evt.tool_call_id;
  return typeof raw === "string" && raw.length > 0 ? raw : "tool_call_fallback";
}

function toSse(chunk: UiChunk): string {
  return `data: ${JSON.stringify(chunk)}\n\n`;
}

export type ChatStreamMappingState = {
  messageId: string | null;
  textId: string | null;
  textStarted: boolean;
};

export function createChatStreamMappingState(): ChatStreamMappingState {
  return {
    messageId: null,
    textId: null,
    textStarted: false,
  };
}

export function mapBackendEventToUiMessageChunkSse(
  evt: BackendEvent,
  state: ChatStreamMappingState,
): string[] {
  const kind = evt.type;
  const chunks: UiChunk[] = [];

  if (kind === "start") {
    state.messageId = messageIdOf(evt);
    state.textId = `${state.messageId}-text`;
    state.textStarted = false;
    chunks.push({ type: "start", messageId: state.messageId });
    return chunks.map(toSse);
  }

  if (!state.messageId) {
    state.messageId = messageIdOf(evt);
    state.textId = `${state.messageId}-text`;
  }

  if (kind === "text-delta") {
    if (!state.textStarted) {
      chunks.push({ type: "text-start", id: state.textId! });
      state.textStarted = true;
    }
    chunks.push({ type: "text-delta", id: state.textId!, delta: String(evt.text ?? "") });
    return chunks.map(toSse);
  }

  if (kind === "citation") {
    chunks.push({ type: "data-citation", data: evt });
    return chunks.map(toSse);
  }

  if (kind === "step") {
    chunks.push({ type: "data-step", data: evt });
    return chunks.map(toSse);
  }

  if (kind === "error") {
    chunks.push({ type: "data-error", data: evt });
    return chunks.map(toSse);
  }

  if (kind === "tool-call") {
    chunks.push({
      type: "tool-input-available",
      toolCallId: toolCallIdOf(evt),
      toolName: String(evt.tool_name ?? "unknown_tool"),
      input: (evt.input as Record<string, unknown> | undefined) ?? {},
    });
    return chunks.map(toSse);
  }

  if (kind === "tool-result") {
    chunks.push({
      type: "tool-output-available",
      toolCallId: toolCallIdOf(evt),
      output: (evt.output as Record<string, unknown> | undefined) ?? {},
    });
    return chunks.map(toSse);
  }

  if (kind === "done") {
    if (state.textStarted) {
      chunks.push({ type: "text-end", id: state.textId! });
    }
    chunks.push({ type: "finish" });
    return chunks.map(toSse);
  }

  return [];
}
