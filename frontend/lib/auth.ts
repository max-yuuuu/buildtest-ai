import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
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
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      applyStableUserId(token, account);
      if (user && !token.id) {
        token.id = user.id;
        token.sub = user.id;
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
