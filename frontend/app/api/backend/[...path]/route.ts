import { auth } from "@/lib/auth";
import { resolveBackendBaseUrl } from "@/lib/server/backend-url";
import { NextRequest, NextResponse } from "next/server";

/** HTTP fetch Headers 值必须是 Latin-1；OAuth 显示名可能含中文，用 Base64URL(UTF-8) 透传。 */
function xUserNameHeaderValue(name: string | null | undefined): string {
  const utf8 = new TextEncoder().encode(name ?? "");
  let binary = "";
  for (let i = 0; i < utf8.length; i++) binary += String.fromCharCode(utf8[i]!);
  const b64 = btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return `b64.${b64}`;
}

/** 不需要登录即可访问的路径前缀（认证相关端点）。 */
const PUBLIC_PATHS = new Set(["auth"]);

async function proxy(req: NextRequest, pathParts: string[]) {
  const isPublic = pathParts.length > 0 && PUBLIC_PATHS.has(pathParts[0]!);

  const session = await auth();
  if (!isPublic && !session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendBaseUrl = await resolveBackendBaseUrl();
  const path = pathParts.join("/");
  const url = `${backendBaseUrl}/api/v1/${path}${req.nextUrl.search}`;

  const body = ["GET", "HEAD"].includes(req.method)
    ? undefined
    : await req.arrayBuffer();

  const headers: Record<string, string> = {};
  if (session?.user) {
    headers["X-User-Id"] = (session.user as { id?: string }).id ?? "";
    headers["X-User-Email"] = session.user.email ?? "";
    headers["X-User-Name"] = xUserNameHeaderValue(session.user.name);
  }
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
