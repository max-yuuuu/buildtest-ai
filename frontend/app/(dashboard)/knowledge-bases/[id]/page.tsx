"use client";

import type { ChangeEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CheckCircle2,
  CircleDashed,
  FileText,
  Loader2,
  RotateCcw,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  Eye,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { knowledgeBaseApi, modelApi, providerApi } from "@/lib/api";
import type { KbDocument, Model, Provider, RetrieveResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type DocStatus = "pending" | "queued" | "processing" | "completed" | "failed";

function getMultimodalConfig(kb: {
  retrieval_config?: Record<string, unknown>;
}) {
  const retrievalConfig = (kb.retrieval_config ?? {}) as Record<string, unknown>;
  const multimodal = (retrievalConfig.multimodal_ingestion ?? {}) as Record<string, unknown>;
  return {
    ocrModelId:
      typeof multimodal.ocr_model_id === "string" ? multimodal.ocr_model_id : "",
    parseMode:
      typeof multimodal.parse_mode === "string" ? multimodal.parse_mode : "auto",
    languages: Array.isArray(multimodal.languages)
      ? multimodal.languages.filter((v): v is string => typeof v === "string")
      : [],
    enableVlm: Boolean(multimodal.enable_vlm),
  };
}

export default function KnowledgeBaseDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const qc = useQueryClient();
  const formInit = useRef(false);
  const ocrProviderInit = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const failedToastSentRef = useRef<Set<string>>(new Set());

  const { data: kb, isLoading } = useQuery({
    queryKey: ["knowledge-bases", id],
    queryFn: () => knowledgeBaseApi.get(id),
  });
  const { data: providers } = useQuery({
    queryKey: ["providers"],
    queryFn: providerApi.list,
  });
  const { data: docs } = useQuery({
    queryKey: ["knowledge-bases", id, "documents"],
    queryFn: () => knowledgeBaseApi.listDocuments(id),
    refetchInterval: (query) => {
      const items = query.state.data as KbDocument[] | undefined;
      if (!items || items.length === 0) return false;
      const hasRunning = items.some((d) =>
        ["pending", "queued", "processing"].includes(d.status),
      );
      return hasRunning ? 2000 : false;
    },
    refetchIntervalInBackground: true,
  });
  const [providerId, setProviderId] = useState("");
  const [ocrModelId, setOcrModelId] = useState("");
  const { data: models } = useQuery({
    queryKey: ["kb-detail-models", providerId],
    queryFn: () => modelApi.list(providerId),
    enabled: !!providerId,
  });

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [chunkSize, setChunkSize] = useState("");
  const [chunkOverlap, setChunkOverlap] = useState("");
  const [topK, setTopK] = useState("");
  const [threshold, setThreshold] = useState("");
  const [query, setQuery] = useState("");
  const [deletingDoc, setDeletingDoc] = useState<KbDocument | null>(null);
  const [retryingDocId, setRetryingDocId] = useState<string | null>(null);
  const [retrieveResult, setRetrieveResult] = useState<RetrieveResponse | null>(null);

  useEffect(() => {
    formInit.current = false;
    ocrProviderInit.current = false;
  }, [id]);

  useEffect(() => {
    if (!kb || formInit.current) return;
    const multimodal = getMultimodalConfig(kb);
    formInit.current = true;
    setName(kb.name);
    setDescription(kb.description ?? "");
    setChunkSize(String(kb.chunk_size));
    setChunkOverlap(String(kb.chunk_overlap));
    setTopK(String(kb.retrieval_top_k));
    setThreshold(String(kb.retrieval_similarity_threshold));
    setOcrModelId(multimodal.ocrModelId);
  }, [kb]);

  // 回填 OCR Provider：UI 里 OCR 模型下拉框依赖 providerId 过滤模型列表，
  // 而后端只在 retrieval_config 里保存 ocr_model_id（provider 可从 model.provider_id 派生）。
  useEffect(() => {
    if (!kb || !providers) return;
    if (providerId) return; // 已回填/已手动选择
    if (ocrProviderInit.current) return;

    const desiredOcrModelId = getMultimodalConfig(kb).ocrModelId;
    if (!desiredOcrModelId) return;

    ocrProviderInit.current = true;
    (async () => {
      try {
        const active = (providers ?? []).filter((p: Provider) => p.is_active);
        const found = await Promise.all(
          active.map(async (p: Provider) => {
            const ms = await modelApi.list(p.id);
            return { provider: p, models: ms };
          }),
        ).then((all) =>
          all.find((x) => x.models.some((m: Model) => m.id === desiredOcrModelId)),
        );

        if (found) setProviderId(found.provider.id);
      } catch {
        ocrProviderInit.current = false;
      }
    })();
  }, [kb, providers, providerId]);

  useEffect(() => {
    if (!docs) return;
    for (const d of docs) {
      const toastKey = `${d.id}:${d.updated_at}`;
      if (d.status === "failed" && d.error_message && !failedToastSentRef.current.has(toastKey)) {
        failedToastSentRef.current.add(toastKey);
        toast.error(`文档「${d.file_name}」入库失败：${d.error_message}`);
      }
    }
  }, [docs]);

  const updateMutation = useMutation({
    mutationFn: () => {
      const baseRetrievalConfig = (kb?.retrieval_config ?? {}) as Record<string, unknown>;
      const existingMultimodal =
        (baseRetrievalConfig.multimodal_ingestion as Record<string, unknown> | undefined) ?? {};
      return knowledgeBaseApi.update(id, {
        name: name.trim(),
        description: description.trim() || null,
        chunk_size: Number(chunkSize),
        chunk_overlap: Number(chunkOverlap),
        retrieval_top_k: Number(topK),
        retrieval_similarity_threshold: Number(threshold),
        retrieval_config: {
          ...baseRetrievalConfig,
          multimodal_ingestion: {
            ...existingMultimodal,
            ocr_model_id: ocrModelId || null,
          },
        },
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("已保存");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const uploadMutation = useMutation({
    mutationFn: (files: File[]) => knowledgeBaseApi.uploadDocuments(id, files),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id, "documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success(`${res.created_count} 个文件上传成功，文档已进入入库队列`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const retrieveMutation = useMutation({
    mutationFn: () => knowledgeBaseApi.retrieve(id, { query: query.trim() }),
    onSuccess: (res) => {
      setRetrieveResult(res);
      toast.success(`命中 ${res.hits.length} 条`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteDocMutation = useMutation({
    mutationFn: (docId: string) => knowledgeBaseApi.deleteDocument(id, docId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id, "documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      toast.success("已删除文档");
      setDeletingDoc(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const retryDocMutation = useMutation({
    mutationFn: async (docId: string) => {
      setRetryingDocId(docId);
      return knowledgeBaseApi.retryDocumentIngestion(id, docId);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id, "documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      toast.success("已重新加入入库队列");
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setRetryingDocId(null),
  });

  if (isLoading || !kb) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        {isLoading ? "加载中…" : "未找到知识库"}
      </div>
    );
  }

  const triggerUpload = () => fileInputRef.current?.click();
  const activeProviders = (providers ?? []).filter((p: Provider) => p.is_active);
  const ocrModels = (models ?? []).filter((m: Model) => m.model_type === "ocr");
  const multimodalConfig = getMultimodalConfig(kb);
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) uploadMutation.mutate(Array.from(files));
    e.target.value = "";
  };

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-background via-background to-muted/40 p-5 lg:p-6">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-gradient-to-br from-primary/20 via-fuchsia-500/10 to-transparent blur-3xl"
        />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <Link
              href="/knowledge-bases"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              返回知识库列表
            </Link>
            <h2 className="text-2xl font-semibold tracking-tight">
              {kb.name}
              <span className="ml-2 font-mono text-xs font-normal text-muted-foreground">
                {kb.collection_name}
              </span>
            </h2>
            <p className="max-w-2xl text-sm text-muted-foreground">
              维度 {kb.embedding_dimension} · chunk {kb.chunk_size}/
              {kb.chunk_overlap} · 默认 top_k {kb.retrieval_top_k} ·
              阈值 {kb.retrieval_similarity_threshold}
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="outline">
                OCR: {multimodalConfig.ocrModelId ? "已配置" : "未配置"}
              </Badge>
              <Badge variant="outline">Parse: {multimodalConfig.parseMode}</Badge>
              {multimodalConfig.languages.length > 0 && (
                <Badge variant="outline">
                  语言: {multimodalConfig.languages.join("/")}
                </Badge>
              )}
              <Badge variant="outline">
                VLM: {multimodalConfig.enableVlm ? "开启" : "关闭"}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={triggerUpload} disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              上传文档
            </Button>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          hidden
          multiple
          onChange={handleFileChange}
          accept=".txt,.md,.pdf,.doc,.docx,.xlsx"
        />
      </div>

      {/* Basics */}
      <section className="space-y-3">
        <SectionHeader
          icon={<Settings2 className="h-4 w-4 text-muted-foreground" />}
          title="基础与切块"
          hint="修改后点击「保存」,新配置对后续上传与检索生效"
        />
        <div className="rounded-xl border bg-card p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>名称</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>向量维度(只读)</Label>
              <Input readOnly value={String(kb.embedding_dimension)} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>描述</Label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="简短说明这个知识库的用途"
              />
            </div>
            <div className="space-y-1.5">
              <Label>chunk_size</Label>
              <Input
                value={chunkSize}
                onChange={(e) => setChunkSize(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>chunk_overlap</Label>
              <Input
                value={chunkOverlap}
                onChange={(e) => setChunkOverlap(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>默认 top_k</Label>
              <Input value={topK} onChange={(e) => setTopK(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>默认相似度阈值</Label>
              <Input
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder="0.0 - 1.0（建议先从 0.4 开始）"
              />
            </div>
            <div className="space-y-1.5">
              <Label>OCR Provider</Label>
              <Select value={providerId} onValueChange={setProviderId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择 Provider（可选）" />
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
            <div className="space-y-1.5">
              <Label>OCR 模型</Label>
              <Select value={ocrModelId} onValueChange={setOcrModelId} disabled={!providerId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择 OCR 模型（可选）" />
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
          <div className="mt-5 flex justify-end">
            <Button
              onClick={() => updateMutation.mutate()}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              保存设置
            </Button>
          </div>
        </div>
      </section>

      {/* Documents */}
      <section className="space-y-3">
        <SectionHeader
          icon={<FileText className="h-4 w-4 text-muted-foreground" />}
          title="文档"
          hint="支持 txt / md / pdf / doc / docx / xlsx;上传后自动切块并向量化"
          count={docs?.length}
          action={
            <Button size="sm" variant="outline" onClick={triggerUpload}>
              <Upload className="mr-1 h-3.5 w-3.5" />
              上传文档
            </Button>
          }
        />

        {!docs ? (
          <ListSkeleton />
        ) : docs.length === 0 ? (
          <button
            type="button"
            onClick={triggerUpload}
            className={cn(
              "group flex w-full flex-col items-center justify-center gap-2 rounded-xl",
              "border-2 border-dashed border-border bg-muted/20 px-6 py-10 text-sm text-muted-foreground",
              "transition-all hover:border-primary/50 hover:bg-primary/5 hover:text-primary",
            )}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-dashed transition-colors group-hover:border-primary/50 group-hover:bg-primary/10">
              <Upload className="h-5 w-5" />
            </div>
            <span className="font-medium">点击上传第一份文档</span>
            <span className="text-xs text-muted-foreground/80">
              txt · md · pdf · doc · docx · xlsx
            </span>
          </button>
        ) : (
          <div className="overflow-hidden rounded-xl border bg-card">
            <div className="overflow-auto">
              <table className="w-full caption-bottom text-sm">
                <TableHeader className="text-xs">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">
                      文件名
                    </TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">
                      状态
                    </TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">
                      切块
                    </TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">
                      大小
                    </TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2 text-right">
                      操作
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                {docs.map((d) => (
                  <TableRow
                    key={d.id}
                    className="transition-colors hover:bg-muted/30"
                  >
                    <TableCell className="py-2.5">
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                        <span className="truncate">{d.file_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="py-2.5">
                      <StatusBadge status={d.status as DocStatus} />
                      {d.error_message && (
                        <p
                          className="mt-1 max-w-xs whitespace-pre-wrap break-words text-xs text-destructive/90"
                          title={d.error_message}
                        >
                          {d.error_message}
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="py-2.5 text-xs text-muted-foreground">
                      {d.chunk_count} 块
                    </TableCell>
                    <TableCell className="py-2.5 text-xs text-muted-foreground">
                      {formatSize(d.file_size)}
                    </TableCell>
                    <TableCell className="py-2.5 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {d.status === "failed" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => retryDocMutation.mutate(d.id)}
                            disabled={retryDocMutation.isPending}
                            className="h-7"
                          >
                            {retryingDocId === d.id ? (
                              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <RotateCcw className="mr-1 h-3.5 w-3.5" />
                            )}
                            重试
                          </Button>
                        )}
                        {d.status === "completed" ? (
                          <Button asChild variant="ghost" size="sm" className="h-7">
                            <Link
                              href={`/knowledge-bases/${id}/documents/${d.id}/chunks`}
                            >
                              <Eye className="mr-1 h-3.5 w-3.5" />
                              查看分块
                            </Link>
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled
                            className="h-7"
                            title="文档处理中，暂不可查看"
                          >
                            <Eye className="mr-1 h-3.5 w-3.5" />
                            查看分块
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeletingDoc(d)}
                          className="h-7 text-destructive hover:text-destructive"
                        >
                          <Trash2 className="mr-1 h-3.5 w-3.5" />
                          删除
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                </TableBody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Retrieve */}
      <section className="space-y-3">
        <SectionHeader
          icon={<Sparkles className="h-4 w-4 text-muted-foreground" />}
          title="试检索"
          hint="验证切块与 embedding 效果,命中结果含 chunk 原文与分数"
          count={retrieveResult?.hits.length ? retrieveResult.hits.length : undefined}
        />
        <div className="rounded-xl border bg-card p-5">
          <textarea
            className={cn(
              "flex min-h-[88px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
              "ring-offset-background placeholder:text-muted-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            )}
            placeholder="输入查询,例如:『产品的退款流程是什么?』"
            value={query}
            onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
              setQuery(e.target.value)
            }
            rows={3}
          />
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              使用默认 top_k {kb.retrieval_top_k} · 阈值{" "}
              {kb.retrieval_similarity_threshold}
            </span>
            <Button
              onClick={() => retrieveMutation.mutate()}
              disabled={!query.trim() || retrieveMutation.isPending}
            >
              {retrieveMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              检索
            </Button>
          </div>
        </div>
        {retrieveResult && retrieveResult.hits.length > 0 && (
          <div className="space-y-2">
            {(retrieveResult.strategy_id || retrieveResult.retrieval_params) && (
              <div className="rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
                策略: {retrieveResult.strategy_id ?? "-"} · 参数快照:{" "}
                {JSON.stringify(retrieveResult.retrieval_params ?? {})}
              </div>
            )}
            {retrieveResult.hits.map((h, i) => (
              <div
                key={`${h.document_id}-${h.chunk_index}-${i}`}
                className="rounded-lg border bg-card p-4 text-sm"
              >
                <div className="mb-2 flex items-center justify-between text-xs">
                  <span className="inline-flex items-center gap-1.5 font-mono text-muted-foreground">
                    <FileText className="h-3 w-3" />
                    {h.document_id.slice(0, 8)}… · chunk {h.chunk_index}
                  </span>
                  <Badge
                    variant="outline"
                    className="font-mono text-[10px] tabular-nums"
                  >
                    {h.score.toFixed(4)}
                  </Badge>
                </div>
                <p className="whitespace-pre-wrap text-foreground/90">
                  {h.text}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <AlertDialog
        open={!!deletingDoc}
        onOpenChange={(v: boolean) => !v && setDeletingDoc(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除文档?</AlertDialogTitle>
            <AlertDialogDescription>
              将删除 “{deletingDoc?.file_name}” 及其所有向量块,操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() =>
                deletingDoc && deleteDocMutation.mutate(deletingDoc.id)
              }
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  hint,
  count,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  hint: string;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div>
        <h3 className="inline-flex items-center gap-2 text-base font-semibold tracking-tight">
          {icon}
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

function StatusBadge({ status }: { status: DocStatus }) {
  const map: Record<
    DocStatus,
    { label: string; className: string; icon: React.ReactNode }
  > = {
    pending: {
      label: "等待",
      className: "bg-muted text-muted-foreground",
      icon: <CircleDashed className="h-3 w-3" />,
    },
    queued: {
      label: "排队中",
      className: "bg-muted text-muted-foreground",
      icon: <CircleDashed className="h-3 w-3" />,
    },
    processing: {
      label: "处理中",
      className:
        "bg-amber-500/10 text-amber-600 dark:text-amber-400",
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
    },
    completed: {
      label: "已完成",
      className:
        "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
      icon: <CheckCircle2 className="h-3 w-3" />,
    },
    failed: {
      label: "失败",
      className: "bg-destructive/10 text-destructive",
      icon: <XCircle className="h-3 w-3" />,
    },
  };
  const m = map[status] ?? map.pending;
  return (
    <Badge
      variant="outline"
      className={cn("gap-1 border-transparent text-[11px]", m.className)}
    >
      {m.icon}
      {m.label}
    </Badge>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 3 }).map((_, i) => (
        <div
          key={i}
          className="h-12 animate-pulse rounded-lg border bg-card"
        />
      ))}
    </div>
  );
}

function formatSize(bytes: number | null): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes;
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}
