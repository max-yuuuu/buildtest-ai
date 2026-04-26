import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

    await waitFor(() => expect(screen.getAllByText("查看分块").length).toBe(2));
    const links = screen.getAllByRole("link", { name: "查看分块" });
    expect(links[0]).toHaveAttribute("href", "/knowledge-bases/kb-1/documents/doc-completed/chunks");
    const disabledButton = screen.getByRole("button", { name: "查看分块" });
    expect(disabledButton).toBeDisabled();
  });
});
