"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Boxes,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
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
import { modelApi, providerApi } from "@/lib/api";
import type { AvailableModel, Model, ModelType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { RegisterModelDialog } from "@/components/providers/register-model-dialog";

export default function ProviderModelsPage() {
  const params = useParams<{ id: string }>();
  const providerId = params.id;
  const qc = useQueryClient();

  const [registering, setRegistering] = useState<AvailableModel | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [deleting, setDeleting] = useState<Model | null>(null);
  const [testing, setTesting] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [typeFilter, setTypeFilter] = useState<
    "all" | ModelType | "unknown"
  >("all");

  const providerQ = useQuery({
    queryKey: ["provider", providerId],
    queryFn: () => providerApi.get(providerId),
  });

  const availableQ = useQuery({
    queryKey: ["models-available", providerId],
    queryFn: () => modelApi.listAvailable(providerId),
    retry: false,
  });

  const registeredQ = useQuery({
    queryKey: ["models", providerId],
    queryFn: () => modelApi.list(providerId),
  });

  const deleteMutation = useMutation({
    mutationFn: (modelPk: string) => modelApi.delete(providerId, modelPk),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models", providerId] });
      qc.invalidateQueries({ queryKey: ["models-available", providerId] });
      toast.success("已取消登记");
      setDeleting(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const runTest = async () => {
    setTesting(true);
    try {
      const result = await providerApi.test(providerId);
      if (result.ok) {
        toast.success(`连通性 OK (${result.latency_ms}ms)`);
      } else {
        toast.warning(`连通性失败:${result.message}`);
      }
      availableQ.refetch();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setTesting(false);
    }
  };

  const provider = providerQ.data;
  const probeFailed = availableQ.isError;

  const filteredAvailable = useMemo(() => {
    const list = availableQ.data ?? [];
    const kw = keyword.trim().toLowerCase();
    return list.filter((m) => {
      if (kw && !m.model_id.toLowerCase().includes(kw)) return false;
      if (typeFilter === "all") return true;
      if (typeFilter === "unknown") return !m.suggested_type;
      return m.suggested_type === typeFilter;
    });
  }, [availableQ.data, keyword, typeFilter]);

  const typeCounts = useMemo(() => {
    const list = availableQ.data ?? [];
    const c = { all: list.length, llm: 0, embedding: 0, unknown: 0 };
    for (const m of list) {
      if (m.suggested_type === "llm") c.llm += 1;
      else if (m.suggested_type === "embedding") c.embedding += 1;
      else c.unknown += 1;
    }
    return c;
  }, [availableQ.data]);

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-5 lg:p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/10 to-transparent blur-3xl"
        />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <Link
              href="/providers"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回 Provider 列表
            </Link>
            <h2 className="text-2xl font-semibold tracking-tight">
              {provider ? provider.name : "加载中…"}
              <span className="ml-2 font-mono text-xs font-normal text-muted-foreground uppercase">
                {provider?.provider_type}
              </span>
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              从上游拉取的可用模型。登记后可在知识库 / 评测任务中绑定;
              embedding 模型需补 <code className="font-mono">vector_dimension</code>。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={runTest} disabled={testing}>
              {testing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Zap className="mr-2 h-4 w-4" />
              )}
              连通性测试
            </Button>
            <Button
              variant="outline"
              onClick={() => availableQ.refetch()}
              disabled={availableQ.isFetching}
            >
              <RefreshCw
                className={cn(
                  "mr-2 h-4 w-4",
                  availableQ.isFetching && "animate-spin",
                )}
              />
              重新拉取
            </Button>
          </div>
        </div>
      </div>

      {/* Available */}
      <section className="space-y-3">
        <SectionHeader
          title="上游可用模型"
          hint="由 GET /models 拉取;已登记的会标灰。上游未列出的模型(如百炼 embedding)可点「手动添加」补录"
          count={probeFailed ? undefined : availableQ.data?.length}
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={() => setManualOpen(true)}
            >
              <Plus className="mr-1 h-3.5 w-3.5" />
              手动添加
            </Button>
          }
        />

        {!probeFailed && (availableQ.data?.length ?? 0) > 0 && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="搜索 model_id…"
                className="pl-8 h-9"
              />
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <FilterChip
                active={typeFilter === "all"}
                onClick={() => setTypeFilter("all")}
                label="全部"
                count={typeCounts.all}
              />
              <FilterChip
                active={typeFilter === "llm"}
                onClick={() => setTypeFilter("llm")}
                label="llm"
                count={typeCounts.llm}
              />
              <FilterChip
                active={typeFilter === "embedding"}
                onClick={() => setTypeFilter("embedding")}
                label="embedding"
                count={typeCounts.embedding}
              />
              <FilterChip
                active={typeFilter === "unknown"}
                onClick={() => setTypeFilter("unknown")}
                label="未知"
                count={typeCounts.unknown}
              />
            </div>
          </div>
        )}

        {probeFailed && (
          <div className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 p-6 text-sm text-amber-900 dark:text-amber-300">
            <div className="font-medium">无法拉取上游模型列表</div>
            <p className="mt-2 text-xs leading-relaxed opacity-90">
              {(availableQ.error as Error)?.message ?? "未知错误"} —— API Key
              或 Base URL 可能有误,可先做连通性测试再重试。也可以点「手动添加」
              直接补录已知 model_id。
            </p>
          </div>
        )}
        {!probeFailed && availableQ.isLoading && <ListSkeleton />}
        {!probeFailed && availableQ.data && availableQ.data.length === 0 && (
          <EmptyHint text="上游未返回任何模型" />
        )}
        {!probeFailed &&
          availableQ.data &&
          availableQ.data.length > 0 &&
          filteredAvailable.length === 0 && (
            <EmptyHint text="没有匹配的模型,试试清空筛选或关键字" />
          )}
        {!probeFailed && filteredAvailable.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {filteredAvailable.map((m) => (
              <AvailableRow
                key={m.model_id}
                item={m}
                onRegister={() => setRegistering(m)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Registered */}
      <section className="space-y-3">
        <SectionHeader
          title="已登记模型"
          hint="知识库 / 评测任务可绑定"
          count={registeredQ.data?.length}
        />
        {registeredQ.isLoading && <ListSkeleton />}
        {registeredQ.data && registeredQ.data.length === 0 && (
          <EmptyHint text="尚未登记任何模型,从上面可用列表点击「登记」开始" />
        )}
        {registeredQ.data && registeredQ.data.length > 0 && (
          <div className="overflow-hidden rounded-xl border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">model_id</th>
                  <th className="px-4 py-2 text-left font-medium">类型</th>
                  <th className="px-4 py-2 text-left font-medium">
                    context / dim
                  </th>
                  <th className="px-4 py-2 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {registeredQ.data.map((m) => (
                  <tr
                    key={m.id}
                    className="border-t transition-colors hover:bg-muted/30"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs">
                      {m.model_id}
                    </td>
                    <td className="px-4 py-2.5">
                      <TypeBadge type={m.model_type} />
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground">
                      {m.model_type === "llm"
                        ? m.context_window
                          ? `ctx ${m.context_window.toLocaleString()}`
                          : "—"
                        : m.vector_dimension
                          ? `dim ${m.vector_dimension}`
                          : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleting(m)}
                        className="h-7 text-destructive hover:text-destructive"
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" />
                        取消登记
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {registering && (
        <RegisterModelDialog
          providerId={providerId}
          candidate={registering}
          onOpenChange={(v) => !v && setRegistering(null)}
        />
      )}

      {manualOpen && (
        <RegisterModelDialog
          providerId={providerId}
          onOpenChange={(v) => !v && setManualOpen(false)}
        />
      )}

      <AlertDialog
        open={!!deleting}
        onOpenChange={(v: boolean) => !v && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>取消登记?</AlertDialogTitle>
            <AlertDialogDescription>
              取消登记 <code className="font-mono">{deleting?.model_id}</code>
              。如果它被知识库或评测任务引用,会删除失败——请先解除引用。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>返回</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleting && deleteMutation.mutate(deleting.id)}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              取消登记
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AvailableRow({
  item,
  onRegister,
}: {
  item: AvailableModel;
  onRegister: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-lg border bg-card px-3 py-2.5 transition-colors",
        item.is_registered
          ? "opacity-60"
          : "hover:border-primary/40 hover:bg-primary/5",
      )}
    >
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-xs">{item.model_id}</p>
        {item.suggested_type && (
          <div className="mt-1">
            <TypeBadge type={item.suggested_type} dim />
          </div>
        )}
      </div>
      {item.is_registered ? (
        <Badge variant="outline" className="gap-1 text-[10px]">
          <CheckCircle2 className="h-3 w-3" />
          已登记
        </Badge>
      ) : (
        <Button size="sm" variant="outline" onClick={onRegister} className="h-7">
          <Plus className="mr-1 h-3.5 w-3.5" />
          登记
        </Button>
      )}
    </div>
  );
}

function SectionHeader({
  title,
  hint,
  count,
  action,
}: {
  title: string;
  hint: string;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div>
        <h3 className="inline-flex items-center gap-2 text-base font-semibold tracking-tight">
          <Boxes className="h-4 w-4 text-muted-foreground" />
          {title}
          {typeof count === "number" && (
            <span className="text-xs font-normal text-muted-foreground">
              ({count})
            </span>
          )}
        </h3>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={count === 0 && !active}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs transition-colors",
        active
          ? "border-primary/60 bg-primary/10 text-primary"
          : "bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground",
        count === 0 && !active && "opacity-40",
      )}
    >
      <span>{label}</span>
      <span className="font-mono text-[10px] opacity-70">{count}</span>
    </button>
  );
}

function TypeBadge({ type, dim }: { type: ModelType; dim?: boolean }) {
  const map = {
    llm: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
    embedding: "bg-cyan-500/10 text-cyan-600 dark:text-cyan-400",
  };
  return (
    <Badge
      variant="outline"
      className={cn("text-[10px] uppercase", map[type], dim && "opacity-80")}
    >
      {type}
    </Badge>
  );
}

function ListSkeleton() {
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="h-14 animate-pulse rounded-lg border bg-card"
        />
      ))}
    </div>
  );
}

function EmptyHint({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed bg-muted/20 p-6 text-center text-xs text-muted-foreground">
      {text}
    </div>
  );
}
