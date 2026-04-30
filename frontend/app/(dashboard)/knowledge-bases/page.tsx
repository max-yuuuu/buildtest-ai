"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Boxes,
  CircleDashed,
  Database,
  FileText,
  Layers,
  MoreHorizontal,
  Plus,
  Sparkles,
  Upload,
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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { knowledgeBaseApi, modelApi, providerApi, vectorDbApi } from "@/lib/api";
import type { KnowledgeBase, Model, Provider, VectorDbConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

const KB_GRADIENTS = [
  { bar: "from-cyan-400 via-sky-500 to-indigo-500", ring: "ring-sky-500/20" },
  { bar: "from-violet-400 via-purple-500 to-fuchsia-500", ring: "ring-violet-500/20" },
  { bar: "from-emerald-400 via-teal-500 to-cyan-500", ring: "ring-emerald-500/20" },
  { bar: "from-rose-400 via-pink-500 to-fuchsia-500", ring: "ring-rose-500/20" },
  { bar: "from-amber-400 via-orange-500 to-rose-500", ring: "ring-amber-500/20" },
];

function pickGradient(id: string) {
  let sum = 0;
  for (let i = 0; i < id.length; i++) sum = (sum + id.charCodeAt(i)) % 9973;
  return KB_GRADIENTS[sum % KB_GRADIENTS.length];
}

function getMultimodalSummary(kb: KnowledgeBase) {
  const retrievalConfig = (kb.retrieval_config ?? {}) as Record<string, unknown>;
  const multimodal = (retrievalConfig.multimodal_ingestion ?? {}) as Record<string, unknown>;
  return {
    ocrModelId:
      typeof multimodal.ocr_model_id === "string" ? multimodal.ocr_model_id : null,
    parseMode:
      typeof multimodal.parse_mode === "string" ? multimodal.parse_mode : "auto",
    languages: Array.isArray(multimodal.languages)
      ? multimodal.languages.filter((v): v is string => typeof v === "string")
      : [],
    enableVlm: Boolean(multimodal.enable_vlm),
  };
}

export default function KnowledgeBasesPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleting, setDeleting] = useState<KnowledgeBase | null>(null);
  const [name, setName] = useState("");
  const [vectorDbId, setVectorDbId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [embeddingModelId, setEmbeddingModelId] = useState("");
  const [ocrModelId, setOcrModelId] = useState("");

  const { data: kbs, isLoading, error } = useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: knowledgeBaseApi.list,
  });
  const { data: vectorDbs } = useQuery({
    queryKey: ["vector-dbs"],
    queryFn: vectorDbApi.list,
  });
  const { data: providers } = useQuery({
    queryKey: ["providers"],
    queryFn: providerApi.list,
  });
  const { data: models } = useQuery({
    queryKey: ["kb-models", providerId],
    queryFn: () => modelApi.list(providerId),
    enabled: !!providerId,
  });

  const usableVectorDbs = useMemo(
    () =>
      (vectorDbs ?? []).filter(
        (v: VectorDbConfig) =>
          v.db_type === "postgres_pgvector" || v.db_type === "qdrant",
      ),
    [vectorDbs],
  );
  const embeddingModels = useMemo(
    () => (models ?? []).filter((m: Model) => m.model_type === "embedding"),
    [models],
  );
  const ocrModels = useMemo(
    () => (models ?? []).filter((m: Model) => m.model_type === "ocr"),
    [models],
  );
  const activeProviders = useMemo(
    () => (providers ?? []).filter((p: Provider) => p.is_active),
    [providers],
  );

  const total = kbs?.length ?? 0;
  const docTotal = useMemo(
    () => (kbs ?? []).reduce((acc, kb) => acc + (kb.document_count ?? 0), 0),
    [kbs],
  );
  const vectorDbUsed = useMemo(() => {
    const set = new Set<string>();
    for (const kb of kbs ?? []) set.add(kb.vector_db_config_id);
    return set.size;
  }, [kbs]);

  const createMutation = useMutation({
    mutationFn: () =>
      knowledgeBaseApi.create({
        name: name.trim(),
        vector_db_config_id: vectorDbId,
        embedding_model_id: embeddingModelId,
        retrieval_similarity_threshold: 0.4,
        retrieval_config: {
          multimodal_ingestion: {
            ocr_model_id: ocrModelId || null,
          },
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("知识库已创建");
      setCreateOpen(false);
      setName("");
      setVectorDbId("");
      setProviderId("");
      setEmbeddingModelId("");
      setOcrModelId("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => knowledgeBaseApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("已删除");
      setDeleting(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openCreate = () => {
    setCreateOpen(true);
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
              Knowledge Bases
            </div>
            <h2 className="text-3xl font-semibold tracking-tight text-ai-gradient">
              知识库管理
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              绑定向量库与 Embedding 模型,上传文档自动切块向量化,
              为 RAG 与评测任务提供可追溯的检索入口。
            </p>
          </div>
          <Button size="lg" onClick={openCreate} className="shadow-sm">
            <Plus className="mr-2 h-4 w-4" />
            新建知识库
          </Button>
        </div>

        <div className="relative mt-6 grid gap-3 sm:grid-cols-3">
          <StatTile
            label="知识库总数"
            value={total}
            hint="已创建的知识库"
            icon={<Database className="h-4 w-4" />}
            accent="bg-primary/10 text-primary"
          />
          <StatTile
            label="文档总数"
            value={docTotal}
            hint="累计入库文档"
            icon={<FileText className="h-4 w-4" />}
            accent="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
          />
          <StatTile
            label="向量库"
            value={vectorDbUsed}
            hint="被引用的存储后端"
            icon={<Layers className="h-4 w-4" />}
            accent="bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
          />
        </div>
      </div>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>新建知识库</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-1">
            <div className="space-y-2">
              <Label htmlFor="kb-name">名称</Label>
              <Input
                id="kb-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如:产品手册"
              />
            </div>
            <div className="space-y-2">
              <Label>向量库配置</Label>
              <Select value={vectorDbId} onValueChange={setVectorDbId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择已保存的向量库" />
                </SelectTrigger>
                <SelectContent>
                  {usableVectorDbs.map((v: VectorDbConfig) => (
                    <SelectItem key={v.id} value={v.id}>
                      {v.name} ({v.db_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Provider</Label>
              <Select value={providerId} onValueChange={setProviderId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择 Provider" />
                </SelectTrigger>
                <SelectContent>
                  {activeProviders.map((p: Provider) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Embedding 模型</Label>
              <Select
                value={embeddingModelId}
                onValueChange={setEmbeddingModelId}
                disabled={!providerId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择已登记的 embedding 模型" />
                </SelectTrigger>
                <SelectContent>
                  {embeddingModels.map((m: Model) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.model_id}({m.vector_dimension} 维)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>OCR 模型 <span className="text-xs text-muted-foreground">(可选)</span></Label>
              <Select
                value={ocrModelId}
                onValueChange={setOcrModelId}
                disabled={!providerId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择已登记的 OCR 模型" />
                </SelectTrigger>
                <SelectContent>
                  {ocrModels.map((m: Model) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.model_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button
              disabled={
                !name.trim() ||
                !vectorDbId ||
                !embeddingModelId ||
                createMutation.isPending
              }
              onClick={() => createMutation.mutate()}
            >
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* List */}
      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <div>
            <h3 className="text-base font-semibold tracking-tight">
              所有知识库
            </h3>
            <p className="text-xs text-muted-foreground">
              点击卡片进入详情,管理文档与试检索
            </p>
          </div>
          {kbs && kbs.length > 0 && (
            <span className="text-xs text-muted-foreground">
              共 {total} 项 · {docTotal} 文档
            </span>
          )}
        </div>

        {isLoading && <KbGridSkeleton />}

        {error && (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-sm text-destructive">
            加载失败:{(error as Error).message}
          </div>
        )}

        {kbs && kbs.length === 0 && <EmptyState onCreate={openCreate} />}

        {kbs && kbs.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {kbs.map((kb) => (
              <KnowledgeBaseCard
                key={kb.id}
                kb={kb}
                onDelete={() => setDeleting(kb)}
              />
            ))}
            <AddKbCard onClick={openCreate} />
          </div>
        )}
      </section>

      <AlertDialog
        open={!!deleting}
        onOpenChange={(v: boolean) => !v && setDeleting(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库?</AlertDialogTitle>
            <AlertDialogDescription>
              将软删除知识库 “{deleting?.name}” 及其文档索引,操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleting && deleteMutation.mutate(deleting.id)}
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
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
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

function KnowledgeBaseCard({
  kb,
  onDelete,
}: {
  kb: KnowledgeBase;
  onDelete: () => void;
}) {
  const meta = pickGradient(kb.id);
  const multimodal = getMultimodalSummary(kb);
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border bg-card transition-all",
        "hover:-translate-y-0.5 hover:shadow-lg hover:ring-1",
        meta.ring,
      )}
    >
      <div className={cn("h-1 w-full bg-gradient-to-r", meta.bar)} />

      <Link
        href={`/knowledge-bases/${kb.id}`}
        className="absolute inset-0 z-10"
        aria-label={`查看 ${kb.name}`}
      />

      <div className="relative space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm",
                meta.bar,
              )}
            >
              <Database className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">{kb.name}</p>
              <p className="text-xs text-muted-foreground">
                {kb.embedding_dimension} 维 · chunk {kb.chunk_size}
              </p>
            </div>
          </div>

          <div className="relative z-20">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 transition-opacity group-hover:opacity-100 data-[state=open]:opacity-100"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                <DropdownMenuItem asChild>
                  <Link href={`/knowledge-bases/${kb.id}`}>管理文档</Link>
                </DropdownMenuItem>
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
        </div>

        <div className="space-y-2">
          <Row icon={<Boxes className="h-3.5 w-3.5" />} label="collection">
            <code className="truncate font-mono text-xs text-foreground/80">
              {kb.collection_name}
            </code>
          </Row>
          <Row icon={<FileText className="h-3.5 w-3.5" />} label="检索">
            <span className="text-xs text-muted-foreground">
              top_k {kb.retrieval_top_k} · 阈值{" "}
              {kb.retrieval_similarity_threshold}
            </span>
          </Row>
          <Row icon={<Sparkles className="h-3.5 w-3.5" />} label="多模态">
            <span className="text-xs text-muted-foreground">
              OCR {multimodal.ocrModelId ? "已配置" : "未配置"} ·
              模式 {multimodal.parseMode}
              {multimodal.languages.length > 0
                ? ` · ${multimodal.languages.join("/")}`
                : ""}
              {multimodal.enableVlm ? " · VLM 开" : ""}
            </span>
          </Row>
        </div>

        <div className="flex items-center justify-between border-t pt-3">
          <Badge
            variant="secondary"
            className="gap-1.5 bg-primary/10 text-primary hover:bg-primary/15"
          >
            <FileText className="h-3 w-3" />
            {kb.document_count} 文档
          </Badge>
          <span className="inline-flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
            <Upload className="h-3.5 w-3.5" />
            管理文档
            <ArrowRight className="h-3 w-3" />
          </span>
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

function AddKbCard({ onClick }: { onClick: () => void }) {
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
      <span className="font-medium">新建知识库</span>
      <span className="text-xs text-muted-foreground/80">
        向量库 + Embedding 模型
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
        还没有创建任何知识库
      </h3>
      <p className="relative mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
        创建一个知识库,就能上传文档、向量化并在评测任务里用起来。
      </p>
      <Button onClick={onCreate} className="relative mt-6">
        <Plus className="mr-2 h-4 w-4" />
        创建第一个知识库
      </Button>
    </div>
  );
}

function KbGridSkeleton() {
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
