"use client";

import { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  CircleDashed,
  Globe,
  KeyRound,
  MoreHorizontal,
  PauseCircle,
  Plus,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { providerApi } from "@/lib/api";
import type { Provider, ProviderType } from "@/lib/types";
import { ProviderFormDialog } from "@/components/providers/provider-form-dialog";
import { cn } from "@/lib/utils";

const PROVIDER_META: Record<
  ProviderType,
  { label: string; gradient: string; ring: string; initial: string }
> = {
  openai: {
    label: "OpenAI",
    gradient: "from-emerald-400 via-teal-500 to-cyan-500",
    ring: "ring-emerald-500/20",
    initial: "AI",
  },
  anthropic: {
    label: "Anthropic",
    gradient: "from-orange-400 via-amber-500 to-rose-500",
    ring: "ring-orange-500/20",
    initial: "AN",
  },
  azure: {
    label: "Azure OpenAI",
    gradient: "from-sky-400 via-blue-500 to-indigo-500",
    ring: "ring-sky-500/20",
    initial: "AZ",
  },
  zhipu: {
    label: "智谱 GLM",
    gradient: "from-violet-400 via-purple-500 to-fuchsia-500",
    ring: "ring-violet-500/20",
    initial: "ZP",
  },
  qwen: {
    label: "通义千问",
    gradient: "from-rose-400 via-pink-500 to-purple-500",
    ring: "ring-rose-500/20",
    initial: "QW",
  },
};

export default function ProvidersPage() {
  const qc = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Provider | null>(null);
  const [deleting, setDeleting] = useState<Provider | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["providers"],
    queryFn: providerApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => providerApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      toast.success("已删除");
      setDeleting(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const total = data?.length ?? 0;
  const active = data?.filter((p) => p.is_active).length ?? 0;
  const inactive = Math.max(0, total - active);

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-5 lg:p-6 ring-ai">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.04] mix-blend-overlay"
        />
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/10 to-transparent blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-20 -left-10 h-48 w-48 rounded-full bg-gradient-to-tr from-cyan-500/10 via-emerald-500/10 to-transparent blur-3xl"
          aria-hidden
        />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Model Providers
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-ai-gradient">
              Provider 管理
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              统一接入 LLM / Embedding 服务商。API Key 使用 Fernet 对称加密落库,
              前端仅展示掩码,保障密钥安全。
            </p>
          </div>
          <Button size="lg" onClick={openCreate} className="shadow-sm">
            <Plus className="mr-2 h-4 w-4" />
            新建 Provider
          </Button>
        </div>

        <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
          <StatTile
            label="总数"
            value={total}
            hint="已配置 Provider"
            icon={<KeyRound className="h-4 w-4" />}
            accent="bg-primary/10 text-primary"
          />
          <StatTile
            label="启用中"
            value={active}
            hint="模型与知识库可用"
            icon={<CheckCircle2 className="h-4 w-4" />}
            accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          />
          <StatTile
            label="停用"
            value={inactive}
            hint="暂不参与调用"
            icon={<PauseCircle className="h-4 w-4" />}
            accent="bg-muted text-muted-foreground"
          />
        </div>
      </div>

      {/* List */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">
              所有 Provider
            </h3>
            <p className="text-xs text-muted-foreground">
              点击卡片右上角可编辑或删除
            </p>
          </div>
          {data && data.length > 0 && (
            <span className="text-xs text-muted-foreground">
              共 {total} 项 · {active} 启用
            </span>
          )}
        </div>

        {isLoading && <ProviderGridSkeleton />}

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
            加载失败:{(error as Error).message}
          </div>
        )}

        {data && data.length === 0 && <EmptyState onCreate={openCreate} />}

        {data && data.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.map((p) => (
              <ProviderCard
                key={p.id}
                provider={p}
                onEdit={() => {
                  setEditing(p);
                  setFormOpen(true);
                }}
                onDelete={() => setDeleting(p)}
              />
            ))}
            <AddProviderCard onClick={openCreate} />
          </div>
        )}
      </section>

      <ProviderFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        initial={editing}
      />

      <AlertDialog
        open={!!deleting}
        onOpenChange={(v: boolean) => !v && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除?</AlertDialogTitle>
            <AlertDialogDescription>
              删除 Provider “{deleting?.name}” 后,依赖它的模型将无法使用。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleting && deleteMutation.mutate(deleting.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function StatTile({
  label,
  value,
  hint,
  icon,
  accent,
}: {
  label: string;
  value: number;
  hint: string;
  icon: React.ReactNode;
  accent: string;
}) {
  return (
    <div className="rounded-xl border bg-card/60 p-4 backdrop-blur-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">
          {label}
        </span>
        <span
          className={cn(
            "flex h-7 w-7 items-center justify-center rounded-lg",
            accent,
          )}
        >
          {icon}
        </span>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-3xl font-semibold tracking-tight tabular-nums">
          {value}
        </span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
    </div>
  );
}

function ProviderCard({
  provider,
  onEdit,
  onDelete,
}: {
  provider: Provider;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const meta = PROVIDER_META[provider.provider_type];
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border bg-card transition-all",
        "hover:-translate-y-0.5 hover:shadow-lg hover:ring-1",
        meta.ring,
      )}
    >
      <div className={cn("h-1 w-full bg-gradient-to-r", meta.gradient)} />

      <div className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-sm font-semibold text-white shadow-sm",
                meta.gradient,
              )}
            >
              {meta.initial}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{provider.name}</p>
              <p className="text-xs text-muted-foreground">{meta.label}</p>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100 data-[state=open]:opacity-100"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/providers/${provider.id}/models` as Route}>
                  管理模型
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onEdit}>编辑</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={onDelete}
              >
                删除
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="space-y-2">
          <Row icon={<KeyRound className="h-3.5 w-3.5" />} label="API Key">
            <code className="font-mono text-xs text-foreground/80">
              {provider.api_key_mask}
            </code>
          </Row>
          <Row icon={<Globe className="h-3.5 w-3.5" />} label="Base URL">
            <span className="truncate text-xs text-muted-foreground">
              {provider.base_url ?? "默认"}
            </span>
          </Row>
        </div>

        <div className="flex items-center justify-between border-t pt-3">
          {provider.is_active ? (
            <Badge
              variant="secondary"
              className="gap-1.5 bg-emerald-500/10 text-emerald-600 hover:bg-emerald-500/15 dark:text-emerald-400"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              启用中
            </Badge>
          ) : (
            <Badge variant="outline" className="gap-1.5 text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/50" />
              已停用
            </Badge>
          )}
          <Link
            href={`/providers/${provider.id}/models` as Route}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            <Boxes className="h-3.5 w-3.5" />
            管理模型
          </Link>
        </div>
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="w-16 shrink-0 text-muted-foreground">{label}</span>
      <div className="min-w-0 flex-1 truncate">{children}</div>
    </div>
  );
}

function AddProviderCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex min-h-[200px] flex-col items-center justify-center gap-2 rounded-xl",
        "border-2 border-dashed border-border bg-muted/20 p-6 text-sm text-muted-foreground",
        "transition-all hover:border-primary/50 hover:bg-primary/5 hover:text-primary",
      )}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-dashed transition-colors group-hover:border-primary/50 group-hover:bg-primary/10">
        <Plus className="h-5 w-5" />
      </div>
      <span className="font-medium">接入新 Provider</span>
      <span className="text-xs text-muted-foreground/80">
        OpenAI · Anthropic · Azure · 智谱 · 通义
      </span>
    </button>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border bg-card p-12 text-center">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-primary/5 to-transparent"
        aria-hidden
      />
      <div className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 via-fuchsia-500/10 to-cyan-500/20">
        <KeyRound className="h-7 w-7 text-primary" />
      </div>
      <h3 className="relative mt-5 text-base font-semibold">
        还没有配置任何 Provider
      </h3>
      <p className="relative mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
        接入一个 LLM / Embedding 服务商,就能开始构建知识库与评测任务。
      </p>
      <Button onClick={onCreate} className="relative mt-6">
        <Plus className="mr-2 h-4 w-4" />
        接入第一个 Provider
      </Button>
    </div>
  );
}

function ProviderGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="flex min-h-[200px] flex-col gap-4 rounded-xl border bg-card p-5"
        >
          <div className="flex items-center gap-3">
            <div className="h-11 w-11 animate-pulse rounded-xl bg-muted" />
            <div className="space-y-2">
              <div className="h-3 w-24 animate-pulse rounded bg-muted" />
              <div className="h-2.5 w-16 animate-pulse rounded bg-muted/70" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full animate-pulse rounded bg-muted/70" />
            <div className="h-3 w-2/3 animate-pulse rounded bg-muted/70" />
          </div>
          <div className="mt-auto flex items-center gap-2 pt-2">
            <CircleDashed className="h-3.5 w-3.5 text-muted-foreground/40" />
            <span className="text-xs text-muted-foreground/60">加载中…</span>
          </div>
        </div>
      ))}
    </div>
  );
}
