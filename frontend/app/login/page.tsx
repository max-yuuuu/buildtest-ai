"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import {
  Database,
  FlaskConical,
  Github,
  KeyRound,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { authApi } from "@/lib/api";

type Mode = "login" | "register";

function EmailAuthForm({ callbackUrl }: { callbackUrl: string }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    if (cooldown <= 0) return;
    timerRef.current = setInterval(() => {
      setCooldown((c) => {
        if (c <= 1) {
          clearInterval(timerRef.current);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [cooldown]);

  const handleCheckEmail = useCallback(async () => {
    if (!email || !email.includes("@")) return;
    try {
      const res = await authApi.checkEmail(email);
      setMode(res.registered ? "login" : "register");
    } catch {
      // ignore check errors
    }
  }, [email]);

  const handleSendCode = async () => {
    if (!email) return;
    setError("");
    setLoading(true);
    try {
      await authApi.sendCode(email);
      setCodeSent(true);
      setCooldown(60);
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送验证码失败");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "register") {
        await authApi.register({ email, code, password, name: name || undefined });
      }
      // Login (or auto-login after register)
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
        callbackUrl,
      });
      if (result?.error) {
        setError(mode === "register" ? "注册成功但自动登录失败，请手动登录" : "邮箱或密码错误");
      } else if (result?.url) {
        window.location.href = result.url;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Mode tabs */}
      <div className="flex rounded-lg border border-border/60 bg-muted/30 p-0.5">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError("");
          }}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mode === "login"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          登录
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("register");
            setError("");
          }}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mode === "register"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          注册
        </button>
      </div>

      {/* Email */}
      <div className="space-y-1.5">
        <Label htmlFor="email" className="text-xs">
          邮箱
        </Label>
        <Input
          id="email"
          type="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={handleCheckEmail}
          required
          className="h-9"
        />
      </div>

      {/* Register-only fields */}
      {mode === "register" && (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="code" className="text-xs">
              验证码
            </Label>
            <div className="flex gap-2">
              <Input
                id="code"
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="6 位数字"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                required
                className="h-9 flex-1"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleSendCode}
                disabled={loading || cooldown > 0}
                className="h-9 shrink-0 text-xs"
              >
                {cooldown > 0 ? `${cooldown}s` : codeSent ? "重新发送" : "发送验证码"}
              </Button>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="name" className="text-xs">
              用户名 <span className="text-muted-foreground">(可选)</span>
            </Label>
            <Input
              id="name"
              type="text"
              placeholder="你的名字"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9"
            />
          </div>
        </>
      )}

      {/* Password */}
      <div className="space-y-1.5">
        <Label htmlFor="password" className="text-xs">
          密码
        </Label>
        <Input
          id="password"
          type="password"
          placeholder={mode === "register" ? "至少 8 位，包含字母和数字" : "输入密码"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={mode === "register" ? 8 : undefined}
          className="h-9"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      {/* Submit */}
      <Button type="submit" className="h-9 w-full text-sm" disabled={loading}>
        {loading ? "处理中…" : mode === "register" ? "注册" : "登录"}
      </Button>
    </form>
  );
}

function OAuthButtons() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/providers";
  const oauthClass =
    "h-11 w-full rounded-xl border-border/80 bg-background/70 font-medium backdrop-blur-sm transition-all hover:border-primary/35 hover:bg-accent/40 hover:shadow-sm";
  return (
    <div className="space-y-3">
      <Button
        className={oauthClass}
        variant="outline"
        onClick={() => signIn("github", { callbackUrl })}
      >
        <Github className="mr-2 h-4 w-4" />
        使用 GitHub 登录
      </Button>
      <Button
        className={oauthClass}
        variant="outline"
        onClick={() => signIn("google", { callbackUrl })}
      >
        <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" aria-hidden>
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

const highlights = [
  {
    icon: KeyRound,
    label: "Provider 加密托管",
    iconBg: "bg-gradient-to-br from-emerald-400 via-teal-500 to-cyan-500",
  },
  {
    icon: Database,
    label: "知识库与向量检索",
    iconBg: "bg-gradient-to-br from-sky-400 via-blue-500 to-indigo-500",
  },
  {
    icon: FlaskConical,
    label: "评测任务可追溯",
    iconBg: "bg-gradient-to-br from-violet-400 via-fuchsia-500 to-pink-500",
  },
] as const;

function LoginContent() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/providers";

  return (
    <div className="w-full max-w-[17rem] space-y-8 lg:max-w-none">
      <div className="flex items-center gap-3 lg:hidden">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-fuchsia-500 to-cyan-500 text-white shadow-md animate-pulse-glow">
          <Sparkles className="h-4 w-4 drop-shadow" aria-hidden />
        </div>
        <div>
          <p className="text-base font-semibold tracking-tight">
            BuildTest AI
          </p>
          <p className="text-xs text-muted-foreground">
            RAG / Agent 开发 · 评测 · 迭代
          </p>
        </div>
      </div>

      <div className="relative space-y-7">
        <div className="space-y-2 text-center lg:text-left">
          <h1 className="text-2xl font-semibold tracking-tight text-ai-gradient sm:text-[1.6rem]">
            登录到工作台
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            使用邮箱注册登录，或通过第三方账号快速登录。
          </p>
        </div>

        {/* Email auth form */}
        <EmailAuthForm callbackUrl={callbackUrl} />

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border/60" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-background px-2 text-muted-foreground">
              或
            </span>
          </div>
        </div>

        {/* OAuth buttons */}
        <OAuthButtons />

        <p className="text-center text-xs leading-relaxed text-muted-foreground lg:text-left">
          登录即表示同意{" "}
          <span className="cursor-default underline underline-offset-4">
            服务条款
          </span>{" "}
          与{" "}
          <span className="cursor-default underline underline-offset-4">
            隐私政策
          </span>
          。
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen min-w-0 bg-background lg:grid-cols-[minmax(0,1fr)_40rem]">
      {/* 左侧：深色品牌区（大屏）——渐变底 + 细网格 + 光晕，避免纯黑平板感 */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-10 text-zinc-50 lg:flex">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-gradient-to-b from-zinc-800/25 via-transparent to-black/50"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-[0.11] mask-radial-fade"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.08] mix-blend-overlay"
        />
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.65]"
          style={{
            backgroundImage:
              "radial-gradient(ellipse 100% 80% at 0% 0%, rgba(99,102,241,0.22), transparent 55%), radial-gradient(ellipse 90% 70% at 100% 100%, rgba(14,165,233,0.18), transparent 50%), radial-gradient(circle at 50% 40%, rgba(250,250,250,0.03), transparent 45%)",
          }}
          aria-hidden
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="animate-aurora absolute -right-32 top-1/4 h-72 w-72 rounded-full bg-gradient-to-br from-fuchsia-500/25 via-violet-500/15 to-transparent blur-3xl" />
          <div
            className="animate-aurora absolute bottom-1/4 -left-24 h-64 w-64 rounded-full bg-gradient-to-tr from-cyan-500/25 via-emerald-500/12 to-transparent blur-3xl"
            style={{ animationDelay: "4s" }}
          />
        </div>
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-white/25 to-transparent"
        />

        <div className="relative flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-white/20 via-fuchsia-400/30 to-cyan-400/25 text-white shadow-lg ring-1 ring-white/10 animate-pulse-glow">
            <Sparkles className="h-5 w-5 drop-shadow" aria-hidden />
          </div>
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="text-lg font-semibold tracking-tight">
              BuildTest AI
            </span>
            <span className="mt-0.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-400">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              Online
            </span>
          </div>
        </div>

        <div className="relative flex flex-1 flex-col justify-center py-12">
          <ul className="max-w-sm space-y-3">
            {highlights.map((item) => {
              const Icon = item.icon;
              return (
                <li
                  key={item.label}
                  className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 backdrop-blur-sm"
                >
                  <div
                    className={cn(
                      "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white shadow-md",
                      item.iconBg,
                    )}
                  >
                    <Icon className="h-4 w-4" aria-hidden />
                  </div>
                  <span className="text-sm text-zinc-300">{item.label}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="relative space-y-3">
          <p className="text-xl font-medium leading-relaxed text-zinc-50">
            让 AI 应用从「能跑起来」走到「敢上线」。
          </p>
          <p className="text-sm leading-relaxed text-zinc-400">
            面向 RAG / Agent 的开发 · 评测 · 迭代一体化平台。统一管理 Provider、知识库、Prompt
            版本与评测结果。
          </p>
        </div>
      </aside>

      {/* 右侧：浅色工作台背景，表单无卡片容器 */}
      <section className="relative flex min-w-0 flex-col overflow-hidden">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-dot-pattern mask-fade-bottom opacity-60"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.05] mix-blend-overlay"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 overflow-hidden"
        >
          <div className="animate-aurora absolute -right-32 -top-32 h-[22rem] w-[22rem] rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/12 to-transparent blur-3xl" />
          <div
            className="animate-aurora absolute -bottom-28 -left-20 h-[20rem] w-[20rem] rounded-full bg-gradient-to-tr from-cyan-500/15 via-emerald-500/10 to-transparent blur-3xl"
            style={{ animationDelay: "3s" }}
          />
        </div>

        <div className="relative flex flex-1 flex-col items-center justify-center px-6 py-16 sm:px-10 sm:py-20 lg:px-32 lg:py-28">
          <Suspense
            fallback={
              <div className="py-2 text-center text-sm text-muted-foreground lg:text-left">
                加载中…
              </div>
            }
          >
            <LoginContent />
          </Suspense>
        </div>
      </section>
    </main>
  );
}
