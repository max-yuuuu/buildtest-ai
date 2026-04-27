import { auth } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_CANDIDATES = [
  process.env.BACKEND_URL,
  "http://localhost:8000",
  "http://backend:8000",
  "http://host.docker.internal:8000",
].filter((v): v is string => Boolean(v && v.trim() !== ""));

let cachedBackendBaseUrl: string | null = null;

type BackendEvent = Record<string, unknown> & { type?: string };

async function isBackendReachable(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/healthz`, { method: "GET", cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

async function resolveBackendBaseUrl(): Promise<string> {
  if (cachedBackendBaseUrl) return cachedBackendBaseUrl;
  for (const candidate of BACKEND_CANDIDATES) {
    if (await isBackendReachable(candidate)) {
      cachedBackendBaseUrl = candidate;
      return candidate;
    }
  }
  cachedBackendBaseUrl = BACKEND_CANDIDATES[0] ?? "http://localhost:8000";
  return cachedBackendBaseUrl;
}

function xUserNameHeaderValue(name: string | null | undefined): string {
  const utf8 = new TextEncoder().encode(name ?? "");
  let binary = "";
  for (let i = 0; i < utf8.length; i++) binary += String.fromCharCode(utf8[i]!);
  const b64 = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `b64.${b64}`;
}

function mapEvent(evt: BackendEvent): string[] {
  const kind = evt.type;
  if (kind === "token") return [`data: ${JSON.stringify({ type: "text", text: evt.text ?? "" })}\n\n`];
  if (kind === "citation")
    return [`data: ${JSON.stringify({ type: "data-citation", data: evt })}\n\n`];
  if (kind === "step") return [`data: ${JSON.stringify({ type: "data-step", data: evt })}\n\n`];
  if (kind === "error") return [`data: ${JSON.stringify({ type: "data-error", data: evt })}\n\n`];
  if (kind === "start" || kind === "done")
    return [`data: ${JSON.stringify({ type: "data-status", data: evt })}\n\n`];
  return [];
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
  const body = await req.json();
  const upstream = await fetch(`${backendBaseUrl}/api/v1/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": (session.user as { id?: string }).id ?? "",
      "X-User-Email": session.user.email ?? "",
      "X-User-Name": xUserNameHeaderValue(session.user.name),
    },
    body: JSON.stringify(body),
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
      for await (const event of parseSse(reader)) {
        for (const line of mapEvent(event)) controller.enqueue(encoder.encode(line));
        if (event.type === "error") break;
      }
      controller.close();
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
