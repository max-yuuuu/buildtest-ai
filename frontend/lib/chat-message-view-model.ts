"use client";

type ChatPart = Record<string, unknown> & {
  type?: string;
  text?: string;
  data?: Record<string, unknown>;
};

type ChatMessageLike = {
  id: string;
  role: string;
  parts?: ChatPart[];
};

export type CitationView = {
  id?: string;
  title?: string | null;
  knowledgeBaseId?: string | null;
  snippet?: string | null;
  score?: number | null;
};

export type ChatMessageViewModel = {
  id: string;
  role: string;
  markdownText: string;
  statusText: string | null;
  citations: CitationView[];
  errorText: string | null;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function mapStepToStatus(data: Record<string, unknown>): string | null {
  const kind = asString(data.step_kind) ?? asString(data.name);
  const status = asString(data.status);

  if (kind === "retrieve" && status === "running") return "正在检索知识库...";
  if (kind === "retrieve" && status === "completed") return "已检索到相关内容，正在生成回答...";
  return null;
}

function mapCitation(data: Record<string, unknown>): CitationView {
  return {
    id: asString(data.id) ?? asString(data.citation_id) ?? undefined,
    title: asString(data.title),
    knowledgeBaseId: asString(data.knowledge_base_id),
    snippet: asString(data.snippet),
    score: typeof data.score === "number" ? data.score : null,
  };
}

export function normalizeChatMessage(message: ChatMessageLike): ChatMessageViewModel {
  const parts = Array.isArray(message.parts) ? message.parts : [];
  const markdownText = parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text!.trim())
    .filter(Boolean)
    .join("\n\n");

  const stepParts = parts.filter((part) => part.type === "data-step");
  const statusText =
    stepParts
      .map((part) => asRecord(part.data))
      .filter((part): part is Record<string, unknown> => part !== null)
      .map(mapStepToStatus)
      .find(Boolean) ?? null;

  const citations = parts
    .filter((part) => part.type === "data-citation")
    .map((part) => asRecord(part.data))
    .filter((part): part is Record<string, unknown> => part !== null)
    .map(mapCitation);

  const errorText =
    parts
      .filter((part) => part.type === "data-error")
      .map((part) => asRecord(part.data))
      .filter((part): part is Record<string, unknown> => part !== null)
      .map((part) => asString(part.message))
      .find(Boolean) ?? null;

  return {
    id: message.id,
    role: message.role,
    markdownText,
    statusText,
    citations,
    errorText,
  };
}
