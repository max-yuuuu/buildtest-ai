import { describe, expect, it } from "vitest";
import { normalizeChatMessage } from "@/lib/chat-message-view-model";

describe("normalizeChatMessage", () => {
  it("aggregates assistant parts into markdown, status, citations and error text", () => {
    const view = normalizeChatMessage({
      id: "assistant-1",
      role: "assistant",
      parts: [
        { type: "text", text: "# Title" },
        {
          type: "data-step",
          data: { step_kind: "retrieve", status: "running" },
        },
        {
          type: "data-citation",
          data: {
            id: "c1",
            title: "Postgres Docs",
            knowledge_base_id: "kb-1",
          },
        },
        {
          type: "data-error",
          data: { message: "Partial failure" },
        },
        {
          type: "tool-retrieve_knowledge",
          toolCallId: "tool-1",
          state: "output-available",
          input: { query: "postgres" },
          output: { hit_count: 2 },
        },
      ],
    });

    expect(view.markdownText).toBe("# Title");
    expect(view.statusText).toBe("正在检索知识库...");
    expect(view.citations).toEqual([
      {
        id: "c1",
        title: "Postgres Docs",
        knowledgeBaseId: "kb-1",
        snippet: null,
        score: null,
      },
    ]);
    expect(view.errorText).toBe("Partial failure");
  });

  it("falls back to name when step_kind is absent", () => {
    const view = normalizeChatMessage({
      id: "assistant-2",
      role: "assistant",
      parts: [{ type: "data-step", data: { name: "retrieve", status: "completed" } }],
    });

    expect(view.statusText).toBe("已检索到相关内容，正在生成回答...");
  });
});
