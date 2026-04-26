import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Header } from "@/components/layout/header";
import { knowledgeBaseApi, notificationApi, providerApi, vectorDbApi } from "@/lib/api";

const pushMock = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/knowledge-bases",
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("next-themes", () => ({
  useTheme: () => ({ resolvedTheme: "light", setTheme: vi.fn() }),
}));

describe("Header notifications", () => {
  it("显示未读计数并渲染通知面板", async () => {
    vi.spyOn(providerApi, "list").mockResolvedValue([]);
    vi.spyOn(knowledgeBaseApi, "list").mockResolvedValue([]);
    vi.spyOn(vectorDbApi, "list").mockResolvedValue([]);
    vi.spyOn(notificationApi, "unreadCount").mockResolvedValue({ unread_count: 2 });
    vi.spyOn(notificationApi, "list").mockResolvedValue({
      page: 1,
      page_size: 8,
      total: 1,
      items: [
        {
          id: "n-1",
          user_id: "u-1",
          event_type: "ingestion_completed",
          level: "success",
          title: "文档处理完成",
          message: "《a.txt》处理完成，可开始检索",
          is_read: false,
          resource_type: "knowledge_base_document",
          resource_id: "d-1",
          knowledge_base_id: "kb-1",
          ingestion_job_id: "j-1",
          action_url: "/knowledge-bases/kb-1/documents/d-1/chunks",
          created_at: new Date().toISOString(),
          read_at: null,
        },
      ],
    });
    vi.spyOn(notificationApi, "markRead").mockResolvedValue({ updated: 1 });

    render(<Header />);

    await waitFor(() => expect(screen.getByText("2")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "通知" }));
    await waitFor(() => expect(screen.getByText("入库通知")).toBeInTheDocument());
    fireEvent.click(screen.getByText("文档处理完成"));

    await waitFor(() =>
      expect(pushMock).toHaveBeenCalledWith("/knowledge-bases/kb-1/documents/d-1/chunks"),
    );
  });
});
