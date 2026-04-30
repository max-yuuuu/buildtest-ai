import { resolveBackendBaseUrl } from "@/lib/server/backend-url";
import { NextRequest, NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

/** JWT 会话 cookie 前缀：NEXTAUTH_URL 为 https 时用 __Secure- 前缀Cookie名 */
function secureCookieForSessionToken(): boolean {
  const url = process.env.NEXTAUTH_URL;
  if (!url) return false;
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

function jwtSecret(): string | null {
  return process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET ?? null;
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
  const secret = jwtSecret();
  if (!secret) {
    return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
  }

  /** 仅解码会话 JWT，避免每条 BFF 请求走完整 auth()/session（开发期明显拖慢并行 API） */
  const token = await getToken({
    req,
    secret,
    secureCookie: secureCookieForSessionToken(),
  });
  const rawId = (token as { id?: string } | null)?.id ?? token?.sub ?? "";
  const userId = typeof rawId === "string" && rawId !== "" ? rawId : "";
  if (!token || !userId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const backendBaseUrl = await resolveBackendBaseUrl();
  const path = pathParts.join("/");
  const url = `${backendBaseUrl}/api/v1/${path}${req.nextUrl.search}`;

  const body = ["GET", "HEAD"].includes(req.method)
    ? undefined
    : await req.arrayBuffer();

  const headers: Record<string, string> = {
    "X-User-Id": userId,
    "X-User-Email": (token.email as string | undefined) ?? "",
    "X-User-Name": xUserNameHeaderValue(token.name as string | null | undefined),
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
