"use client";

type ChatStatusLineProps = {
  text: string | null;
};

export function ChatStatusLine({ text }: ChatStatusLineProps) {
  if (!text) return null;

  return <p className="text-xs text-muted-foreground">{text}</p>;
}
