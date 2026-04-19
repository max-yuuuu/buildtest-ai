"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Boxes,
  CheckCircle2,
  CircleDashed,
  Database,
  Link2,
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
import { vectorDbApi } from "@/lib/api";
import type { VectorDbConfig, VectorDbType } from "@/lib/types";
import { VectorDbFormDialog } from "@/components/vector-dbs/vector-db-form-dialog";
import { cn } from "@/lib/utils";
import {
  getVectorDbCatalogEntry,
  VECTOR_DB_CATALOG,
} from "@/lib/vector-db-catalog";

const TYPE_STYLE: Record<
  VectorDbType,
  { label: string; gradient: string; ring: string; initial: string }
> = {
  postgres_pgvector: {
    label: "PostgreSQL",
    gradient: "from-sky-400 via-blue-600 to-indigo-600",
    ring: "ring-blue-500/20",
    initial: "PG",
  },
  qdrant: {
    label: "Qdrant",
    gradient: "from-red-400 via-rose-500 to-orange-500",
    ring: "ring-rose-500/20",
    initial: "QD",
  },
  milvus: {
    label: "Milvus",
    gradient: "from-violet-400 via-purple-600 to-fuchsia-600",
    ring: "ring-violet-500/20",
    initial: "MV",
  },
  weaviate: {
    label: "Weaviate",
    gradient: "from-teal-400 via-cyan-500 to-emerald-600",
    ring: "ring-teal-500/20",
    initial: "WV",
  },
  pinecone: {
    label: "Pinecone",
    gradient: "from-lime-400 via-green-500 to-emerald-600",
    ring: "ring-lime-500/20",
    initial: "PC",
  },
  chroma: {
    label: "Chroma",
    gradient: "from-amber-400 via-yellow-500 to-orange-500",
    ring: "ring-amber-500/20",
    initial: "CH",
  },
};

export default function VectorDbsPage() {
  const qc = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<VectorDbConfig | null>(null);
  const [deleting, setDeleting] = useState<VectorDbConfig | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["vector-dbs"],
    queryFn: vectorDbApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => vectorDbApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["vector-dbs"] });
      toast.success("已删除");
      setDeleting(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      vectorDbApi.update(id, { is_active }),
    onSuccess: (_, { is_active }) => {
      qc.invalidateQueries({ queryKey: ["vector-dbs"] });
      toast.success(is_active ? "已启用" : "已停用");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => vectorDbApi.test(id),
    onSuccess: (r) => {
      if (r.ok) {
        toast.success(`连通性 OK（${r.latency_ms}ms）`);
      } else {
        toast.warning(`测试未通过：${r.message}`);
      }
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
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-5 lg:p-6 ring-ai">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-noise opacity-[0.04] mix-blend-overlay"
        />
        <div
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-gradient-to-br from-primary/20 via-cyan-500/10 to-transparent blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-20 -left-10 h-48 w-48 rounded-full bg-gradient-to-tr from-fuchsia-500/10 via-primary/10 to-transparent blur-3xl"
          aria-hidden
        />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Vector Stores
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-ai-gradient">
              向量库连接
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              配置 pgvector、Qdrant 等向量存储。连接串与密钥加密落库，与 Provider
              管理同一套安全策略。
            </p>
          </div>
          <Button size="lg" onClick={openCreate} className="shadow-sm">
            <Plus className="mr-2 h-4 w-4" />
            新建连接
          </Button>
        </div>

        <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
          <StatTile
            label="总数"
            value={total}
            hint="已保存配置"
            icon={<Database className="h-4 w-4" />}
            accent="bg-primary/10 text-primary"
          />
          <StatTile
            label="启用中"
            value={active}
            hint="可被知识库引用"
            icon={<CheckCircle2 className="h-4 w-4" />}
            accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          />
          <StatTile
            label="停用"
            value={inactive}
            hint="暂不参与检索"
            icon={<PauseCircle className="h-4 w-4" />}
            accent="bg-muted text-muted-foreground"
          />
        </div>
      </div>

      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-baseline sm:justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">
              类型说明（选型参考）
            </h3>
            <p className="text-xs text-muted-foreground">
              与附录 A.15 / <code className="text-[11px]">vector-db-catalog.ts</code>{" "}
              同步
            </p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {VECTOR_DB_CATALOG.map((c) => (
            <div
              key={c.id}
              className="rounded-xl border bg-card/60 p-4 text-xs backdrop-blur-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-semibold text-sm">{c.name}</span>
                {!c.connectorAvailable && (
                  <Badge variant="outline" className="text-[10px]">
                    即将支持
                  </Badge>
                )}
              </div>
              <p className="mt-1 text-muted-foreground">{c.tagline}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">
              所有连接
            </h3>
            <p className="text-xs text-muted-foreground">
              卡片菜单可测试连通、编辑或删除
            </p>
          </div>
          {data && data.length > 0 && (
            <span className="text-xs text-muted-foreground">
              共 {total} 项 · {active} 启用
            </span>
          )}
        </div>

        {isLoading && <VectorDbGridSkeleton />}

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
            加载失败：{(error as Error).message}
          </div>
        )}

        {data && data.length === 0 && <EmptyState onCreate={openCreate} />}

        {data && data.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.map((row) => (
              <VectorDbCard
                key={row.id}
                row={row}
                togglePending={
                  toggleActiveMutation.isPending &&
                  toggleActiveMutation.variables?.id === row.id
                }
                testPending={
                  testMutation.isPending && testMutation.variables === row.id
                }
                onEdit={() => {
                  setEditing(row);
                  setFormOpen(true);
                }}
                onToggleActive={() =>
                  toggleActiveMutation.mutate({
                    id: row.id,
                    is_active: !row.is_active,
                  })
                }
                onTest={() => testMutation.mutate(row.id)}
                onDelete={() => setDeleting(row)}
              />
            ))}
            <AddVectorDbCard onClick={openCreate} />
          </div>
        )}
      </section>

      <VectorDbFormDialog
        key={editing?.id ?? "new"}
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
            <AlertDialogTitle>确认删除？</AlertDialogTitle>
            <AlertDialogDescription>
              删除「{deleting?.name}」后，依赖该配置的知识库需重新绑定向量库。
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

function VectorDbCard({
  row,
  togglePending,
  testPending,
  onEdit,
  onToggleActive,
  onTest,
  onDelete,
}: {
  row: VectorDbConfig;
  togglePending?: boolean;
  testPending?: boolean;
  onEdit: () => void;
  onToggleActive: () => void;
  onTest: () => void;
  onDelete: () => void;
}) {
  const meta = TYPE_STYLE[row.db_type];
  const cat = getVectorDbCatalogEntry(row.db_type);
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
              <p className="truncate text-sm font-semibold">{row.name}</p>
              <p className="text-xs text-muted-foreground">
                {cat?.name ?? meta.label}
              </p>
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
              <DropdownMenuItem disabled={testPending} onClick={onTest}>
                测试连接
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onEdit}>编辑</DropdownMenuItem>
              {row.is_active ? (
                <DropdownMenuItem
                  disabled={togglePending}
                  onClick={onToggleActive}
                >
                  停用
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  disabled={togglePending}
                  onClick={onToggleActive}
                >
                  启用
                </DropdownMenuItem>
              )}
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
          <Row
            icon={<Link2 className="h-3.5 w-3.5" />}
            label="连接"
            mono
          >
            {row.connection_string_mask}
          </Row>
          {row.api_key_mask && (
            <Row icon={<Boxes className="h-3.5 w-3.5" />} label="API Key">
              <code className="font-mono text-xs text-foreground/80">
                {row.api_key_mask}
              </code>
            </Row>
          )}
        </div>

        <div className="flex items-center justify-between border-t pt-3">
          {row.is_active ? (
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
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1 text-xs text-primary"
            disabled={testPending}
            onClick={onTest}
          >
            测试连接
          </Button>
        </div>
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  children,
  mono,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        {icon}
      </span>
      <span className="w-14 shrink-0 text-muted-foreground">{label}</span>
      <div
        className={cn(
          "min-w-0 flex-1 truncate",
          mono && "font-mono text-foreground/80",
        )}
      >
        {children}
      </div>
    </div>
  );
}

function AddVectorDbCard({ onClick }: { onClick: () => void }) {
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
      <span className="font-medium">新建向量库连接</span>
      <span className="text-xs text-muted-foreground/80">
        PostgreSQL · Qdrant …
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
        <Database className="h-7 w-7 text-primary" />
      </div>
      <h3 className="relative mt-5 text-base font-semibold">
        还没有向量库连接
      </h3>
      <p className="relative mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
        添加 pgvector 或 Qdrant 后，即可在知识库中绑定检索存储。
      </p>
      <Button onClick={onCreate} className="relative mt-6">
        <Plus className="mr-2 h-4 w-4" />
        创建第一个连接
      </Button>
    </div>
  );
}

function VectorDbGridSkeleton() {
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
