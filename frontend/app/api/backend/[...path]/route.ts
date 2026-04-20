import { auth } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://backend:8000";

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

  const path = pathParts.join("/");
  const url = `${BACKEND_URL}/api/v1/${path}${req.nextUrl.search}`;

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

  const upstream = await fetch(url, {
    method: req.method,
    headers,
    body,
  });

  const nullBodyStatus = upstream.status === 204 || upstream.status === 205 || upstream.status === 304;
  const data = nullBodyStatus ? null : await upstream.text();
  return new NextResponse(data, {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
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
