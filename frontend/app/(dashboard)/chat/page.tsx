"use client";

import { FormEvent, useMemo, useState } from "react";
import { useChat } from "@ai-sdk/react";
import { useQuery } from "@tanstack/react-query";
import { knowledgeBaseApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type ChatPart = { type?: string; text?: string; data?: Record<string, unknown> };

function collectParts(message: unknown): ChatPart[] {
  const m = message as { parts?: ChatPart[] };
  return Array.isArray(m.parts) ? m.parts : [];
}

export default function ChatPage() {
  const { data: kbs = [] } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: knowledgeBaseApi.list,
  });
  const [kbId, setKbId] = useState<string>("");
  const {
    messages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    error,
  } = useChat({
    api: "/api/chat",
    body: useMemo(() => ({ mode: "quick", knowledge_base_id: kbId || undefined }), [kbId]),
  });

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!kbId) return;
    void handleSubmit(e);
  };

  return (
    <div className="space-y-4 p-4 lg:p-5">
      <div>
        <h2 className="text-xl font-semibold">Quick Chat</h2>
        <p className="text-sm text-muted-foreground">渲染 text + data-citation/data-step/data-error</p>
      </div>

      <div className="flex gap-2">
        <Select value={kbId} onValueChange={setKbId}>
          <SelectTrigger className="w-80">
            <SelectValue placeholder="选择知识库" />
          </SelectTrigger>
          <SelectContent>
            {kbs.map((kb) => (
              <SelectItem key={kb.id} value={kb.id}>
                {kb.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-3 rounded-md border p-3">
        {messages.map((msg) => {
          const parts = collectParts(msg);
          return (
            <div key={(msg as { id: string }).id} className="space-y-2">
              <div className="text-xs text-muted-foreground">{(msg as { role: string }).role}</div>
              {parts
                .filter((p) => p.type === "text")
                .map((p, i) => (
                  <p key={i} className="text-sm">
                    {p.text}
                  </p>
                ))}
              {parts
                .filter((p) => p.type === "data-citation")
                .map((p, i) => (
                  <pre key={`c-${i}`} className="rounded bg-muted p-2 text-xs">
                    {JSON.stringify(p.data, null, 2)}
                  </pre>
                ))}
              {parts
                .filter((p) => p.type === "data-step")
                .map((p, i) => (
                  <pre key={`s-${i}`} className="rounded bg-muted p-2 text-xs">
                    {JSON.stringify(p.data, null, 2)}
                  </pre>
                ))}
              {parts
                .filter((p) => p.type === "data-error")
                .map((p, i) => (
                  <pre key={`e-${i}`} className="rounded border border-destructive/40 bg-destructive/5 p-2 text-xs">
                    {JSON.stringify(p.data, null, 2)}
                  </pre>
                ))}
            </div>
          );
        })}
        {error ? <p className="text-sm text-destructive">{error.message}</p> : null}
      </div>

      <form onSubmit={onSubmit} className="flex gap-2">
        <Input
          value={input}
          onChange={handleInputChange}
          placeholder={kbId ? "输入问题..." : "请先选择知识库"}
          disabled={isLoading || !kbId}
        />
        <Button type="submit" disabled={isLoading || !kbId}>
          发送
        </Button>
      </form>
    </div>
  );
}
