import type { KnowledgeBase } from "@/lib/types";

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function extractMentionedKnowledgeBases(input: string, kbs: KnowledgeBase[]): KnowledgeBase[] {
  return [...kbs]
    .sort((a, b) => b.name.length - a.name.length)
    .filter((kb) => new RegExp(`(^|\\s)@${escapeRegex(kb.name)}(?=\\s|$)`).test(input));
}

export function stripMentionTokens(input: string, kbs: KnowledgeBase[]): string {
  let cleaned = input;
  for (const kb of [...kbs].sort((a, b) => b.name.length - a.name.length)) {
    cleaned = cleaned.replace(new RegExp(`(^|\\s)@${escapeRegex(kb.name)}(?=\\s|$)`, "g"), " ");
  }
  return cleaned.replace(/\s+/g, " ").trim();
}

export function currentMentionQuery(input: string): string | null {
  const match = input.match(/(?:^|\s)@([^\s@]*)$/);
  return match ? match[1] ?? "" : null;
}

export function insertMention(input: string, kbName: string): string {
  return input.replace(/(?:^|\s)@([^\s@]*)$/, (match) => match.replace(/@([^\s@]*)$/, `@${kbName} `));
}
