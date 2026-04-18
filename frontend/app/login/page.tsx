"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Github, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

function LoginButtons() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/providers";
  return (
    <div className="space-y-3">
      <Button
        className="w-full"
        variant="outline"
        onClick={() => signIn("github", { callbackUrl })}
      >
        <Github className="mr-2 h-4 w-4" />
        使用 GitHub 登录
      </Button>
      <Button
        className="w-full"
        variant="outline"
        onClick={() => signIn("google", { callbackUrl })}
      >
        <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
          <path
            fill="currentColor"
            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
          />
          <path
            fill="currentColor"
            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
          />
          <path
            fill="currentColor"
            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
          />
          <path
            fill="currentColor"
            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
          />
        </svg>
        使用 Google 登录
      </Button>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-zinc-950 p-10 text-zinc-50 lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 10%, rgba(99,102,241,0.35), transparent 45%), radial-gradient(circle at 80% 90%, rgba(14,165,233,0.25), transparent 50%)",
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-2 text-lg font-semibold">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10 backdrop-blur">
            <Sparkles className="h-5 w-5" />
          </div>
          BuildTest AI
        </div>
        <div className="relative space-y-3">
          <p className="text-xl font-medium leading-relaxed">
            让 AI 应用从&ldquo;能跑起来&rdquo;走到&ldquo;敢上线&rdquo;。
          </p>
          <p className="text-sm text-zinc-400">
            面向 RAG / Agent 的开发 · 评测 · 迭代一体化平台。统一管理 Provider、知识库、Prompt 版本与评测结果。
          </p>
        </div>
      </aside>

      <section className="flex items-center justify-center px-4 py-12 sm:px-8">
        <div className="w-full max-w-sm space-y-8">
          <div className="space-y-2 text-center lg:text-left">
            <h1 className="text-2xl font-semibold tracking-tight">
              登录到 BuildTest AI
            </h1>
            <p className="text-sm text-muted-foreground">
              选择第三方账号快速登录,首次登录将自动创建账户。
            </p>
          </div>

          <Suspense
            fallback={
              <div className="text-sm text-muted-foreground">加载中...</div>
            }
          >
            <LoginButtons />
          </Suspense>

          <p className="text-center text-xs text-muted-foreground lg:text-left">
            登录即表示同意 <span className="underline-offset-4">服务条款</span> 与{" "}
            <span className="underline-offset-4">隐私政策</span>。
          </p>
        </div>
      </section>
    </main>
  );
}
