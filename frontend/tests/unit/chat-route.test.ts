import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createChatStreamMappingState,
  mapBackendEventToUiMessageChunkSse,
} from "@/lib/server/chat-stream-mapper";

vi.mock("@/lib/auth", () => ({
  auth: vi.fn(async () => ({
    user: { id: "user-1", email: "user@example.com", name: "Test User" },
  })),
}));

vi.mock("@/lib/server/backend-url", () => ({
  resolveBackendBaseUrl: vi.fn(async () => "http://backend.test"),
}));

describe("chat route event mapping", () => {
  it("maps backend start/text-delta/done to ai sdk v6 chunks", () => {
    const state = createChatStreamMappingState();

    const start = mapBackendEventToUiMessageChunkSse({ type: "start", message_id: "msg_1" }, state);
    const delta = mapBackendEventToUiMessageChunkSse(
      { type: "text-delta", message_id: "msg_1", text: "Hello" },
      state,
    );
    const done = mapBackendEventToUiMessageChunkSse({ type: "done", message_id: "msg_1" }, state);

    expect(start).toEqual(['data: {"type":"start","messageId":"msg_1"}\n\n']);
    expect(delta).toEqual([
      'data: {"type":"text-start","id":"msg_1-text"}\n\n',
      'data: {"type":"text-delta","id":"msg_1-text","delta":"Hello"}\n\n',
    ]);
    expect(done).toEqual([
      'data: {"type":"text-end","id":"msg_1-text"}\n\n',
      'data: {"type":"finish"}\n\n',
    ]);
  });

  it("maps tool and data events to structured UI chunks", () => {
    const state = createChatStreamMappingState();
    mapBackendEventToUiMessageChunkSse({ type: "start", message_id: "msg_1" }, state);

    expect(
      mapBackendEventToUiMessageChunkSse(
        {
          type: "tool-call",
          message_id: "msg_1",
          tool_call_id: "tool_1",
          tool_name: "retrieve_knowledge",
          input: { query: "postgres" },
        },
        state,
      ),
    ).toEqual([
      'data: {"type":"tool-input-available","toolCallId":"tool_1","toolName":"retrieve_knowledge","input":{"query":"postgres"}}\n\n',
    ]);

    expect(
      mapBackendEventToUiMessageChunkSse(
        {
          type: "tool-result",
          message_id: "msg_1",
          tool_call_id: "tool_1",
          output: { hit_count: 2 },
        },
        state,
      ),
    ).toEqual([
      'data: {"type":"tool-output-available","toolCallId":"tool_1","output":{"hit_count":2}}\n\n',
    ]);

    expect(mapBackendEventToUiMessageChunkSse({ type: "citation", message_id: "msg_1", citation_id: "c1" }, state))
      .toEqual(['data: {"type":"data-citation","data":{"type":"citation","message_id":"msg_1","citation_id":"c1"}}\n\n']);

    expect(
      mapBackendEventToUiMessageChunkSse(
        { type: "step", message_id: "msg_1", id: "step_think", name: "think", status: "running" },
        state,
      ),
    ).toEqual([
      'data: {"type":"data-step","data":{"type":"step","message_id":"msg_1","id":"step_think","name":"think","status":"running"}}\n\n',
    ]);

    expect(
      mapBackendEventToUiMessageChunkSse(
        { type: "error", message_id: "msg_1", code: "CHAT_INTERNAL_ERROR", message: "boom" },
        state,
      ),
    ).toEqual([
      'data: {"type":"data-error","data":{"type":"error","message_id":"msg_1","code":"CHAT_INTERNAL_ERROR","message":"boom"}}\n\n',
    ]);
  });
});

describe("chat route request shaping", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("maps ai sdk ui-message payload to backend chat request body", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response('data: {"type":"start","message_id":"msg_1"}\n\ndata: {"type":"done","message_id":"msg_1"}\n\n', {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );

    const { POST } = await import("@/app/api/chat/route");
    const req = new Request("http://localhost:3000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "quick",
        knowledge_base_ids: ["18e80c2d-3b57-44eb-b80d-eb543b1996f1"],
        id: "KIycmRdPaztXY5ez",
        messages: [
          {
            id: "DlnAE8V1o5riZEMd",
            role: "user",
            parts: [{ type: "text", text: "元组" }],
          },
        ],
        trigger: "submit-message",
      }),
    });

    const response = await POST(req as never);

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://backend.test/api/v1/chat/stream",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          mode: "quick",
          knowledge_base_ids: ["18e80c2d-3b57-44eb-b80d-eb543b1996f1"],
          message: "元组",
        }),
      }),
    );
  });
});
