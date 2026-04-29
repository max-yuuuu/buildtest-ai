"use client";

import { Component, type ReactNode } from "react";
import { code } from "@streamdown/code";
import { mermaid } from "@streamdown/mermaid";
import { Streamdown } from "streamdown";

type AssistantMarkdownMessageProps = {
  markdown: string;
  isStreaming: boolean;
};

type StreamdownBoundaryProps = AssistantMarkdownMessageProps & {
  children: ReactNode;
};

type StreamdownBoundaryState = {
  hasError: boolean;
};

class StreamdownBoundary extends Component<StreamdownBoundaryProps, StreamdownBoundaryState> {
  state: StreamdownBoundaryState = { hasError: false };

  static getDerivedStateFromError(): StreamdownBoundaryState {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <pre className="overflow-x-auto rounded-xl border bg-background/70 p-3 text-xs text-foreground">
          <code>{this.props.markdown}</code>
        </pre>
      );
    }

    return this.props.children;
  }
}

export function AssistantMarkdownMessage({ markdown, isStreaming }: AssistantMarkdownMessageProps) {
  if (!markdown) return null;

  return (
    <StreamdownBoundary markdown={markdown} isStreaming={isStreaming}>
      <div className="streamdown prose prose-sm max-w-none text-foreground dark:prose-invert">
        <Streamdown animated isAnimating={isStreaming} plugins={{ code, mermaid }}>
          {markdown}
        </Streamdown>
      </div>
    </StreamdownBoundary>
  );
}
