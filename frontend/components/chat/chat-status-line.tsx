"use client";

type ChatStatusLineProps = {
  text: string | null;
};

export function ChatStatusLine({ text }: ChatStatusLineProps) {
  if (!text) return null;

  const isWarning = /失败|error|异常/i.test(text);
  return <p className={isWarning ? "text-xs text-destructive" : "text-xs text-muted-foreground"}>{text}</p>;
}
