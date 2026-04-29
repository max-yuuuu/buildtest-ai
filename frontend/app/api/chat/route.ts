import { auth } from "@/lib/auth";
import {
  createChatStreamMappingState,
  mapBackendEventToUiMessageChunkSse,
  type BackendEvent,
} from "@/lib/server/chat-stream-mapper";
import { resolveBackendBaseUrl } from "@/lib/server/backend-url";
import { NextRequest, NextResponse } from "next/server";

function xUserNameHeaderValue(name: string | null | undefined): string {
  const utf8 = new TextEncoder().encode(name ?? "");
  let binary = "";
  for (let i = 0; i < utf8.length; i++) binary += String.fromCharCode(utf8[i]!);
  const b64 = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `b64.${b64}`;
}

type UiMessagePart = {
  type?: string;
  text?: string;
};

type UiMessage = {
  role?: string;
  parts?: UiMessagePart[];
};

type ChatRouteRequestBody = {
  mode?: string;
  knowledge_base_ids?: string[];
  messages?: UiMessage[];
};

function extractLatestUserTextMessage(messages: UiMessage[] | undefined): string | null {
  if (!Array.isArray(messages)) return null;

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role !== "user" || !Array.isArray(message.parts)) continue;
    const text = message.parts
      .filter((part) => part?.type === "text" && typeof part.text === "string")
      .map((part) => part.text!.trim())
      .filter(Boolean)
      .join("\n")
      .trim();
    if (text) return text;
  }

  return null;
}


async function* parseSse(reader: ReadableStreamDefaultReader<Uint8Array>): AsyncGenerator<BackendEvent> {
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const dataLine = block
        .split("\n")
        .map((line) => line.trim())
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      const raw = dataLine.slice(5).trim();
      try {
        yield JSON.parse(raw);
      } catch {
        continue;
      }
    }
  }
}

export async function POST(req: NextRequest) {
  const session = await auth();
  if (!session?.user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const backendBaseUrl = await resolveBackendBaseUrl();
  const body = (await req.json()) as ChatRouteRequestBody;
  const message = extractLatestUserTextMessage(body.messages);

  if (!message) {
    return NextResponse.json({ error: "Missing user message" }, { status: 400 });
  }

  const upstream = await fetch(`${backendBaseUrl}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": (session.user as { id?: string }).id ?? "",
      "X-User-Email": session.user.email ?? "",
      "X-User-Name": xUserNameHeaderValue(session.user.name),
    },
    body: JSON.stringify({
      mode: body.mode ?? "quick",
      knowledge_base_ids: body.knowledge_base_ids ?? [],
      message,
    }),
  });

  if (!upstream.ok || !upstream.body) {
    const text = await upstream.text();
    return new NextResponse(text || JSON.stringify({ error: "upstream stream failed" }), {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const reader = upstream.body!.getReader();
      const state = createChatStreamMappingState();
      for await (const event of parseSse(reader)) {
        for (const line of mapBackendEventToUiMessageChunkSse(event, state)) {
          controller.enqueue(encoder.encode(line));
        }
      }
      controller.close();
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "x-vercel-ai-ui-message-stream": "v1",
    },
  });
}
