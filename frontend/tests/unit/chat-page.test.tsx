import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import ChatPage from "@/app/(dashboard)/chat/page";
import {
  currentMentionQuery,
  extractMentionedKnowledgeBases,
  insertMention,
  stripMentionTokens,
} from "@/lib/chat-mentions";
import { knowledgeBaseApi } from "@/lib/api";

const sendMessageMock = vi.fn();

vi.mock("ai", () => ({
  DefaultChatTransport: class DefaultChatTransport {
    constructor(_options: unknown) {}
  },
}));

vi.mock("@ai-sdk/react", () => ({
  useChat: () => ({
    messages: [
      {
        id: "assistant-1",
        role: "assistant",
        parts: [
          { type: "text", text: "hello" },
          { type: "data-citation", data: { citation_id: "c1" } },
          {
            type: "tool-retrieve_knowledge",
            toolCallId: "tool_1",
            state: "output-available",
            input: { query: "postgres" },
            output: { hit_count: 2 },
          },
        ],
      },
    ],
    sendMessage: sendMessageMock,
    status: "ready",
    error: undefined,
  }),
}));

describe("ChatPage", () => {
  beforeEach(() => {
    sendMessageMock.mockReset();
  });

  it("解析 mentions 并在提交时发送 default + mentioned knowledge_base_ids", async () => {
    vi.spyOn(knowledgeBaseApi, "list").mockResolvedValue([
      {
        id: "kb-default",
        user_id: "u1",
        name: "Postgres",
        description: null,
        vector_db_config_id: "v1",
        collection_name: "c1",
        embedding_model_id: "m1",
        embedding_dimension: 1536,
        chunk_size: 200,
        chunk_overlap: 20,
        retrieval_top_k: 5,
        retrieval_similarity_threshold: 0.4,
        retrieval_config: {},
        document_count: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: "kb-extra",
        user_id: "u1",
        name: "LangGraph",
        description: null,
        vector_db_config_id: "v1",
        collection_name: "c2",
        embedding_model_id: "m1",
        embedding_dimension: 1536,
        chunk_size: 200,
        chunk_overlap: 20,
        retrieval_top_k: 5,
        retrieval_similarity_threshold: 0.4,
        retrieval_config: {},
        document_count: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <ChatPage />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("默认主库: Postgres")).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText("输入问题，或使用 @知识库名 额外绑定多个知识库"), {
      target: { value: "如何设计索引 @LangGraph" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));

    await waitFor(() => {
      expect(sendMessageMock).toHaveBeenCalledWith(
        { text: "如何设计索引" },
        {
          body: {
            mode: "quick",
            knowledge_base_ids: ["kb-default", "kb-extra"],
          },
        },
      );
    });
  });

  it("渲染 text / data / tool parts", async () => {
    vi.spyOn(knowledgeBaseApi, "list").mockResolvedValue([
      {
        id: "kb-default",
        user_id: "u1",
        name: "Postgres",
        description: null,
        vector_db_config_id: "v1",
        collection_name: "c1",
        embedding_model_id: "m1",
        embedding_dimension: 1536,
        chunk_size: 200,
        chunk_overlap: 20,
        retrieval_top_k: 5,
        retrieval_similarity_threshold: 0.4,
        retrieval_config: {},
        document_count: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <ChatPage />
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("hello")).toBeInTheDocument();
      expect(screen.getByText(/citation_id/)).toBeInTheDocument();
      expect(screen.getByText(/Tool tool_1/)).toBeInTheDocument();
      expect(screen.getByText(/output-available/)).toBeInTheDocument();
    });
  });
});

describe("chat mention helpers", () => {
  const kbs = [
    { id: "1", name: "Postgres" },
    { id: "2", name: "LangGraph" },
  ] as const;

  it("extractMentionedKnowledgeBases picks mentioned Kbs once", () => {
    const result = extractMentionedKnowledgeBases("@LangGraph 对比 @Postgres 与 @LangGraph", [...kbs] as never);
    expect(result.map((kb) => kb.id)).toEqual(["2", "1"]);
  });

  it("stripMentionTokens removes inline mentions", () => {
    expect(stripMentionTokens("查询 @LangGraph 和 @Postgres 的区别", [...kbs] as never)).toBe("查询 和 的区别");
  });

  it("currentMentionQuery and insertMention support suggestions", () => {
    expect(currentMentionQuery("hello @Lang")).toBe("Lang");
    expect(insertMention("hello @Lang", "LangGraph")).toBe("hello @LangGraph ");
  });
});
