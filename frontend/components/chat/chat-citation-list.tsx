"use client";

import { Badge } from "@/components/ui/badge";
import type { CitationView } from "@/lib/chat-message-view-model";

type ChatCitationListProps = {
  citations: CitationView[];
};

export function ChatCitationList({ citations }: ChatCitationListProps) {
  if (citations.length === 0) return null;

  return (
    <div className="space-y-2 rounded-xl border bg-background/70 p-3">
      <div className="text-xs font-medium text-muted-foreground">引用来源 {citations.length}</div>
      <div className="space-y-2">
        {citations.map((citation, index) => {
          const title = citation.title ?? "未命名来源";
          const knowledgeBaseId = citation.knowledgeBaseId;

          return (
            <div key={citation.id ?? `${title}-${index}`} className="rounded-lg border bg-background px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-medium text-foreground">{title}</div>
                {knowledgeBaseId ? (
                  <Badge variant="secondary" className="font-mono text-[10px]">
                    {knowledgeBaseId}
                  </Badge>
                ) : null}
              </div>
              {citation.snippet ? (
                <p className="mt-1 text-xs text-muted-foreground">{citation.snippet}</p>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
