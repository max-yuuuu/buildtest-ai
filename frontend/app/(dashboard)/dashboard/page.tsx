"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  CheckCircle2,
  CircleDashed,
  Database,
  FlaskConical,
  KeyRound,
  Rocket,
  Sparkles,
} from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { knowledgeBaseApi, providerApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const modules = [
  {
    title: "Provider",
    description: "配置 LLM / Embedding 服务商",
    body: "接入 OpenAI、Anthropic、Azure、智谱、通义等,统一由 Fernet 加密托管 API Key。",
    href: "/providers",
    cta: "去配置",
    badge: "可用",
    tone: "default" as const,
    gradient: "from-emerald-400 via-teal-500 to-cyan-500",
    icon: KeyRound,
    status: "ready" as const,
  },
  {
    title: "知识库",
    description: "文档上传、切片、向量化",
    body: "上传文档并关联 embedding 模型,Celery 异步入库后可用于检索与评测。",
    href: "/knowledge-bases",
    cta: "去管理",
    badge: "可用",
    tone: "default" as const,
    gradient: "from-sky-400 via-blue-500 to-indigo-500",
    icon: Database,
    status: "ready" as const,
  },
  {
    title: "评测",
    description: "Dataset × Prompt × Model",
    body: "绑定四要素跑批评测,输出 Bad Case、版本对比与完整血缘链路。",
    href: "#",
    cta: "敬请期待",
    badge: "规划中",
    tone: "outline" as const,
    gradient: "from-violet-400 via-fuchsia-500 to-pink-500",
    icon: FlaskConical,
    status: "planned" as const,
  },
];

export default function DashboardPage() {
  const { data: session } = useSession();
  const { data: providers = [] } = useQuery({
    queryKey: ["providers"],
    queryFn: providerApi.list,
  });
  const { data: knowledgeBases = [] } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: knowledgeBaseApi.list,
  });
  const displayName = session?.user?.name ?? session?.user?.email ?? "开发者";
  const providerCount = providers.length;
  const activeProviderCount = providers.filter((p) => p.is_active).length;
  const knowledgeBaseCount = knowledgeBases.length;
  const documentTotal = useMemo(
    () =>
      knowledgeBases.reduce(
        (total, kb) => total + (kb.document_count ?? 0),
        0,
      ),
    [knowledgeBases],
  );

  const stats = [
    {
      label: "Provider",
      value: providerCount,
      hint: `${activeProviderCount} 个启用`,
      icon: KeyRound,
      accent: "bg-primary/10 text-primary",
    },
    {
      label: "知识库",
      value: knowledgeBaseCount,
      hint: `${documentTotal} 份文档`,
      icon: Database,
      accent: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    },
    {
      label: "评测任务",
      value: 0,
      hint: "Phase 2 即将上线",
      icon: FlaskConical,
      accent: "bg-fuchsia-500/10 text-fuchsia-600 dark:text-fuchsia-400",
    },
  ];

  const steps = [
    {
      step: "01",
      title: "配置 Provider",
      desc: "绑定 OpenAI / Anthropic 等服务商,密钥加密托管",
      icon: KeyRound,
      done: providerCount > 0,
    },
    {
      step: "02",
      title: "创建知识库",
      desc: "上传文档,完成切片与向量化",
      icon: Database,
      done: knowledgeBaseCount > 0,
    },
    {
      step: "03",
      title: "运行评测",
      desc: "绑定 Dataset × Prompt × Model,输出 Bad Case",
      icon: FlaskConical,
      done: false,
    },
  ];

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-5 lg:p-6 ring-ai">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.04] mix-blend-overlay"
        />
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/10 to-transparent blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-24 -left-10 h-56 w-56 rounded-full bg-gradient-to-tr from-cyan-500/10 via-emerald-500/10 to-transparent blur-3xl"
          aria-hidden
        />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Welcome back
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-ai-gradient">
              你好,{displayName}
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              BuildTest AI 帮你把 RAG / Agent 应用从「能跑起来」走到「敢上线」——
              从接入 Provider,到构建知识库,再到完成第一次评测。
            </p>
          </div>
          <Button asChild size="lg" className="shadow-sm">
            <Link href="/knowledge-bases">
              <Rocket className="mr-2 h-4 w-4" />
              进入知识库
            </Link>
          </Button>
        </div>

        <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="rounded-xl border bg-card/60 p-4 backdrop-blur-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted-foreground">
                    {s.label}
                  </span>
                  <span
                    className={cn(
                      "flex h-7 w-7 items-center justify-center rounded-lg",
                      s.accent,
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-semibold tracking-tight tabular-nums">
                    {s.value}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {s.hint}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Modules */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">核心模块</h3>
            <p className="text-xs text-muted-foreground">
              按路线图分阶段上线,点击进入具体页面
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {modules.map((m) => {
            const Icon = m.icon;
            const disabled = m.href === "#";
            return (
              <div
                key={m.title}
                className={cn(
                  "group relative flex flex-col overflow-hidden rounded-xl border bg-card transition-all",
                  !disabled && "hover:-translate-y-0.5 hover:shadow-lg",
                )}
              >
                <div className={cn("h-1 w-full bg-gradient-to-r", m.gradient)} />
                <div className="flex flex-1 flex-col gap-4 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <div
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm",
                        m.gradient,
                      )}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <Badge variant={m.tone} className="capitalize">
                      {m.badge}
                    </Badge>
                  </div>
                  <div>
                    <h4 className="text-base font-semibold">{m.title}</h4>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {m.description}
                    </p>
                  </div>
                  <p className="flex-1 text-sm text-muted-foreground">
                    {m.body}
                  </p>
                  <div className="pt-1">
                    <Button
                      asChild={!disabled}
                      disabled={disabled}
                      variant="ghost"
                      size="sm"
                      className="h-auto px-0 text-sm font-medium text-primary hover:bg-transparent hover:text-primary/80"
                    >
                      {disabled ? (
                        <span>
                          {m.cta}
                          <ArrowUpRight className="ml-1 h-4 w-4" />
                        </span>
                      ) : (
                        <Link href={m.href as never}>
                          {m.cta}
                          <ArrowUpRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                        </Link>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Quick start */}
      <section className="space-y-4">
        <div>
          <h3 className="text-base font-semibold tracking-tight">快速上手</h3>
          <p className="text-xs text-muted-foreground">
            按顺序完成下面三步,即可运行第一次评测
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {steps.map((s, i) => {
            const Icon = s.icon;
            return (
              <div
                key={s.step}
                className="relative overflow-hidden rounded-xl border bg-card p-5"
              >
                <div className="flex items-start justify-between">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    STEP {s.step}
                  </span>
                  {s.done ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <CircleDashed className="h-4 w-4 text-muted-foreground/60" />
                  )}
                </div>
                <div className="mt-4 flex items-center gap-3">
                  <div
                    className={cn(
                      "flex h-9 w-9 items-center justify-center rounded-lg",
                      s.done
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{s.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {s.desc}
                    </div>
                  </div>
                </div>
                {i < steps.length - 1 && (
                  <div
                    className="pointer-events-none absolute right-0 top-1/2 hidden h-px w-4 -translate-y-1/2 bg-gradient-to-r from-border to-transparent md:block"
                    aria-hidden
                  />
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
