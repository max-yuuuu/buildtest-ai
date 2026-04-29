"use client";

import { DefaultChatTransport } from "ai";
import { useChat } from "@ai-sdk/react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { knowledgeBaseApi } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  currentMentionQuery,
  extractMentionedKnowledgeBases,
  insertMention,
  stripMentionTokens,
} from "@/lib/chat-mentions";
import { AssistantMarkdownMessage } from "@/components/chat/assistant-markdown-message";
import { ChatCitationList } from "@/components/chat/chat-citation-list";
import { ChatStatusLine } from "@/components/chat/chat-status-line";
import { normalizeChatMessage } from "@/lib/chat-message-view-model";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const { data: kbs = [] } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: knowledgeBaseApi.list,
  });
  const [defaultKbId, setDefaultKbId] = useState<string>("");
  const [input, setInput] = useState("");
  const {
    messages,
    sendMessage,
    status,
    error,
  } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  });

  useEffect(() => {
    if (!defaultKbId && kbs[0]?.id) {
      setDefaultKbId(kbs[0].id);
    }
  }, [defaultKbId, kbs]);

  const mentionedKbs = useMemo(() => extractMentionedKnowledgeBases(input, kbs), [input, kbs]);
  const defaultKb = kbs.find((kb) => kb.id === defaultKbId) ?? null;
  const boundKbs = useMemo(() => {
    const merged = [...(defaultKb ? [defaultKb] : []), ...mentionedKbs];
    return merged.filter((kb, index) => merged.findIndex((item) => item.id === kb.id) === index);
  }, [defaultKb, mentionedKbs]);

  const mentionQuery = currentMentionQuery(input);
  const mentionSuggestions = useMemo(() => {
    if (mentionQuery === null) return [];
    const lowered = mentionQuery.toLowerCase();
    return kbs
      .filter((kb) => kb.id !== defaultKbId)
      .filter((kb) => kb.name.toLowerCase().includes(lowered))
      .slice(0, 6);
  }, [defaultKbId, kbs, mentionQuery]);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!defaultKb) return;

    const cleanedMessage = stripMentionTokens(input, kbs);
    const knowledgeBaseIds = boundKbs.map((kb) => kb.id);
    if (!cleanedMessage || knowledgeBaseIds.length === 0) return;

    sendMessage(
      { text: cleanedMessage },
      {
        body: {
          mode: "quick",
          knowledge_base_ids: knowledgeBaseIds,
        },
      },
    );
    setInput("");
  };

  const isStreaming = status === "submitted" || status === "streaming";

  return (
    <div className="flex h-full min-h-[calc(100vh-80px)] flex-col gap-4 p-4 lg:p-5">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-xl font-semibold">Quick Chat</h2>
            <p className="text-xs text-muted-foreground">
              默认主知识库始终生效；在输入框里使用 `@知识库` 可额外绑定多个知识库。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Select value={defaultKbId} onValueChange={setDefaultKbId}>
              <SelectTrigger className="w-56">
                <SelectValue placeholder="选择默认主知识库" />
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
        </div>
        {defaultKb ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge>默认主库: {defaultKb.name}</Badge>
            {mentionedKbs.map((kb) => (
              <Badge key={kb.id} variant="secondary">
                @{kb.name}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">请先选择默认主知识库后开始对话。</p>
        )}
      </div>

      <div className="flex-1 rounded-xl border bg-background/80 p-4 shadow-sm">
        <div className="flex h-full flex-col gap-3">
          <div className="flex-1 space-y-3 overflow-y-auto pr-1">
            {messages.length === 0 && (
              <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
                先选择默认主知识库，再在输入框中输入问题。若要附加其他知识库，直接输入 `@知识库名`。
              </div>
            )}
            {messages.map((msg) => {
              const id = (msg as { id: string }).id;
              const role = (msg as { role: string }).role;
              const isUser = role === "user";
              const view = normalizeChatMessage(msg as { id: string; role: string; parts?: Record<string, unknown>[] });

              return (
                <div key={id} className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}>
                  {!isUser && (
                    <Avatar className="size-8">
                      <AvatarFallback>AI</AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={cn(
                      "max-w-[75%] space-y-2 rounded-2xl px-3 py-2 text-sm",
                      isUser
                        ? "rounded-br-sm bg-primary text-primary-foreground"
                        : "rounded-bl-sm bg-muted text-foreground",
                    )}
                  >
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground/80">
                      {role === "user" ? "You" : role === "assistant" ? "Assistant" : role}
                    </div>
                    {isUser ? <p>{view.markdownText}</p> : null}
                    {!isUser ? <ChatStatusLine text={view.statusText} /> : null}
                    {!isUser ? <AssistantMarkdownMessage markdown={view.markdownText} isStreaming={isStreaming} /> : null}
                    {!isUser ? <ChatCitationList citations={view.citations} /> : null}
                    {!isUser && view.errorText ? (
                      <div className="rounded-xl border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
                        {view.errorText}
                      </div>
                    ) : null}
                  </div>
                  {isUser && (
                    <Avatar className="size-8">
                      <AvatarFallback>Me</AvatarFallback>
                    </Avatar>
                  )}
                </div>
              );
            })}
          </div>
          {error ? <p className="text-xs text-destructive">{error.message}</p> : null}
        </div>
      </div>

      <form
        onSubmit={onSubmit}
        className="sticky bottom-0 space-y-2 rounded-3xl border bg-background/95 px-3 py-3 shadow-sm backdrop-blur"
      >
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              defaultKb
                ? "输入问题，或使用 @知识库名 额外绑定多个知识库"
                : "请先选择默认主知识库"
            }
            disabled={isStreaming || !defaultKb}
            className="border-0 bg-transparent px-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
          />
          <Button type="submit" size="sm" disabled={isStreaming || !defaultKb}>
            {isStreaming ? "思考中..." : "发送"}
          </Button>
        </div>
        {mentionSuggestions.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {mentionSuggestions.map((kb) => (
              <button
                key={kb.id}
                type="button"
                className="rounded-full border px-2 py-1 text-xs text-muted-foreground transition hover:bg-muted"
                onClick={() => setInput((current) => insertMention(current, kb.name))}
              >
                @{kb.name}
              </button>
            ))}
          </div>
        ) : null}
      </form>
    </div>
  );
}
