import { auth } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_CANDIDATES = [
  process.env.BACKEND_URL,
  "http://localhost:8000",
  "http://backend:8000",
  "http://host.docker.internal:8000",
].filter((v): v is string => Boolean(v && v.trim() !== ""));

let cachedBackendBaseUrl: string | null = null;

async function isBackendReachable(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl}/healthz`, {
      method: "GET",
      cache: "no-store",
    });
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

  // 无法探测时回退第一个候选，保持错误信息稳定且便于排查。
  cachedBackendBaseUrl = BACKEND_CANDIDATES[0] ?? "http://localhost:8000";
  return cachedBackendBaseUrl;
}

/** HTTP fetch Headers 值必须是 Latin-1；OAuth 显示名可能含中文，用 Base64URL(UTF-8) 透传。 */
function xUserNameHeaderValue(name: string | null | undefined): string {
  const utf8 = new TextEncoder().encode(name ?? "");
  let binary = "";
  for (let i = 0; i < utf8.length; i++) binary += String.fromCharCode(utf8[i]!);
  const b64 = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `b64.${b64}`;
}

async function proxy(req: NextRequest, pathParts: string[]) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendBaseUrl = await resolveBackendBaseUrl();
  const path = pathParts.join("/");
  const url = `${backendBaseUrl}/api/v1/${path}${req.nextUrl.search}`;

  const body = ["GET", "HEAD"].includes(req.method)
    ? undefined
    : await req.arrayBuffer();

  const headers: Record<string, string> = {
    "X-User-Id": (session.user as { id?: string }).id ?? "",
    "X-User-Email": session.user.email ?? "",
    "X-User-Name": xUserNameHeaderValue(session.user.name),
  };
  const ct = req.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;

  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: "Backend request failed",
        detail: error instanceof Error ? error.message : String(error),
      },
      { status: 502 },
    );
  }

  const nullBodyStatus = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
  const data = nullBodyStatus ? null : await upstream.arrayBuffer();
  const contentType = upstream.headers.get("content-type") ?? "application/json";
  const contentDisposition = upstream.headers.get("content-disposition");
  return new NextResponse(data, {
    status: upstream.status,
    headers: {
      "Content-Type": contentType,
      ...(contentDisposition ? { "Content-Disposition": contentDisposition } : {}),
    },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function POST(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function PUT(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
export async function DELETE(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return proxy(req, path);
}
