import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import Credentials from "next-auth/providers/credentials";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";

/**
 * Auth.js v5 在未配置 database adapter 时，OAuth 回调里的 user.id 每次登录都是新的随机 UUID
 *（见 @auth/core getUserAndAccount），会导致 BFF 的 X-User-Id 变化、后端误判为新用户。
 * 使用 provider + providerAccountId（OAuth sub / GitHub id）作为跨会话稳定主键。
 */
function applyStableUserId(token: JWT, account: { provider?: string; providerAccountId?: string } | null | undefined) {
  if (!account?.provider || account.providerAccountId == null || account.providerAccountId === "") {
    return;
  }
  const stable = `${account.provider}:${String(account.providerAccountId)}`;
  token.sub = stable;
  token.id = stable;
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
    }),
    Google({
      clientId: process.env.GOOGLE_ID!,
      clientSecret: process.env.GOOGLE_SECRET!,
    }),
    Credentials({
      name: "credentials",
      credentials: {
        email: { type: "email" },
        password: { type: "password" },
      },
      authorize: async (credentials) => {
        const backendUrl = process.env.BACKEND_URL ?? "http://backend:8000";
        try {
          const res = await fetch(`${backendUrl}/api/v1/auth/verify-password`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials?.email,
              password: credentials?.password,
            }),
          });
          if (!res.ok) return null;
          const user = await res.json();
          if (!user?.id) return null;
          return { id: user.id, email: user.email, name: user.name };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      if (account && account.provider !== "credentials") {
        applyStableUserId(token, account);
      } else if (user) {
        // Credentials: authorize 已返回正确的 id（credentials:email）
        token.sub = user.id;
        token.id = user.id;
      }
      return token;
    },
    async session({ session, token }) {
      const id = (token.id as string | undefined) ?? token.sub;
      if (id) (session.user as { id?: string }).id = id;
      return session;
    },
  },
});
