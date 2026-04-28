import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatCitationList } from "@/components/chat/chat-citation-list";

vi.mock("@streamdown/code", () => ({
  code: {},
}));

vi.mock("@streamdown/mermaid", () => ({
  mermaid: {},
}));

describe("ChatCitationList", () => {
  it("renders minimal source info when snippet is absent", () => {
    render(
      <ChatCitationList
        citations={[
          {
            id: "c1",
            title: null,
            knowledgeBaseId: "kb-1",
            snippet: null,
            score: null,
          },
        ]}
      />,
    );

    expect(screen.getByText("引用来源 1")).toBeInTheDocument();
    expect(screen.getByText("未命名来源")).toBeInTheDocument();
    expect(screen.getByText("kb-1")).toBeInTheDocument();
  });
});

describe("AssistantMarkdownMessage", () => {
  it("falls back to plain code block when Streamdown render fails", async () => {
    vi.resetModules();
    vi.doMock("streamdown", () => ({
      Streamdown: () => {
        throw new Error("mermaid render failed");
      },
    }));

    const { AssistantMarkdownMessage } = await import("@/components/chat/assistant-markdown-message");

    render(<AssistantMarkdownMessage markdown={"```mermaid\ngraph LR\nA-->B\n```"} isStreaming={false} />);

    expect(screen.getByText(/graph LR/)).toBeInTheDocument();
  });
});
