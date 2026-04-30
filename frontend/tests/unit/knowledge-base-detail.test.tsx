import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import KnowledgeBaseDetailPage from "@/app/(dashboard)/knowledge-bases/[id]/page";
import { knowledgeBaseApi } from "@/lib/api";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "kb-1" }),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe("KnowledgeBaseDetailPage", () => {
  it("展示排队中状态并渲染检索策略快照", async () => {
    vi.spyOn(knowledgeBaseApi, "get").mockResolvedValue({
      id: "kb-1",
      user_id: "u1",
      name: "KB",
      description: null,
      vector_db_config_id: "v1",
      collection_name: "c1",
      embedding_model_id: "m1",
      embedding_dimension: 4,
      chunk_size: 200,
      chunk_overlap: 20,
      retrieval_top_k: 5,
      retrieval_similarity_threshold: 0.4,
      retrieval_config: {},
      document_count: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    vi.spyOn(knowledgeBaseApi, "listDocuments").mockResolvedValue([
      {
        id: "doc-queued",
        knowledge_base_id: "kb-1",
        file_name: "queued.txt",
        file_type: "txt",
        file_size: 12,
        status: "queued",
        chunk_count: 0,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(knowledgeBaseApi, "retrieve").mockResolvedValue({
      strategy_id: "naive.v1",
      retrieval_params: { top_k: 5, similarity_threshold: 0.4 },
      hits: [
        {
          knowledge_base_id: "kb-1",
          document_id: "doc-queued",
          chunk_index: 0,
          text: "hello",
          score: 0.9,
          source: { page: 1 },
        },
      ],
    });

    render(
      <QueryClientProvider client={new QueryClient()}>
        <KnowledgeBaseDetailPage />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("排队中")).toBeInTheDocument());
    fireEvent.change(screen.getByPlaceholderText("输入查询,例如:『产品的退款流程是什么?』"), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "检索" }));

    await waitFor(() => {
      expect(screen.getByText(/策略: naive\.v1/)).toBeInTheDocument();
      expect(screen.getByText(/参数快照/)).toBeInTheDocument();
    });
  });

  it("文档状态会从排队中刷新到已完成", async () => {
    vi.spyOn(knowledgeBaseApi, "get").mockResolvedValue({
      id: "kb-1",
      user_id: "u1",
      name: "KB",
      description: null,
      vector_db_config_id: "v1",
      collection_name: "c1",
      embedding_model_id: "m1",
      embedding_dimension: 4,
      chunk_size: 200,
      chunk_overlap: 20,
      retrieval_top_k: 5,
      retrieval_similarity_threshold: 0.4,
      retrieval_config: {},
      document_count: 1,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    const listSpy = vi.spyOn(knowledgeBaseApi, "listDocuments");
    listSpy
      .mockResolvedValueOnce([
        {
          id: "doc-1",
          knowledge_base_id: "kb-1",
          file_name: "a.txt",
          file_type: "txt",
          file_size: 12,
          status: "queued",
          chunk_count: 0,
          error_message: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ])
      .mockResolvedValue([
        {
          id: "doc-1",
          knowledge_base_id: "kb-1",
          file_name: "a.txt",
          file_type: "txt",
          file_size: 12,
          status: "completed",
          chunk_count: 2,
          error_message: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ]);

    render(
      <QueryClientProvider client={new QueryClient()}>
        <KnowledgeBaseDetailPage />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("排队中")).toBeInTheDocument(), {
      timeout: 2000,
    });
    await waitFor(() => expect(screen.getByText("已完成")).toBeInTheDocument(), {
      timeout: 5000,
    });
  });

  it("仅 completed 文档可查看分块", async () => {
    vi.spyOn(knowledgeBaseApi, "get").mockResolvedValue({
      id: "kb-1",
      user_id: "u1",
      name: "KB",
      description: null,
      vector_db_config_id: "v1",
      collection_name: "c1",
      embedding_model_id: "m1",
      embedding_dimension: 4,
      chunk_size: 200,
      chunk_overlap: 20,
      retrieval_top_k: 5,
      retrieval_similarity_threshold: 0.4,
      retrieval_config: {},
      document_count: 2,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    vi.spyOn(knowledgeBaseApi, "listDocuments").mockResolvedValue([
      {
        id: "doc-completed",
        knowledge_base_id: "kb-1",
        file_name: "ok.txt",
        file_type: "txt",
        file_size: 12,
        status: "completed",
        chunk_count: 1,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
      {
        id: "doc-processing",
        knowledge_base_id: "kb-1",
        file_name: "doing.txt",
        file_type: "txt",
        file_size: 12,
        status: "processing",
        chunk_count: 0,
        error_message: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <KnowledgeBaseDetailPage />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("已完成")).toBeInTheDocument(), {
      timeout: 2000,
    });
    await waitFor(() => expect(screen.getAllByText("查看分块").length).toBe(2), {
      timeout: 2000,
    });
    const links = screen.getAllByRole("link", { name: "查看分块" });
    expect(links[0]).toHaveAttribute("href", "/knowledge-bases/kb-1/documents/doc-completed/chunks");
    const disabledButton = screen.getByRole("button", { name: "查看分块" });
    expect(disabledButton).toBeDisabled();
  });
});
