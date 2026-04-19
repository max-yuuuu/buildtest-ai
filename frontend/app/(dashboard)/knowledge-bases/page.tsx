"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import type { Model, Provider, VectorDbConfig } from "@/lib/types";

export default function KnowledgeBasesPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [vectorDbId, setVectorDbId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [embeddingModelId, setEmbeddingModelId] = useState("");

  const { data: kbs, isLoading } = useQuery({
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

  const createMutation = useMutation({
    mutationFn: () =>
      knowledgeBaseApi.create({
        name: name.trim(),
        vector_db_config_id: vectorDbId,
        embedding_model_id: embeddingModelId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("知识库已创建");
      setCreateOpen(false);
      setName("");
      setVectorDbId("");
      setProviderId("");
      setEmbeddingModelId("");
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

  return (
    <div className="space-y-5 p-4 lg:p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">知识库</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            绑定向量库与 Embedding 模型，上传文档并试检索
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          新建
        </Button>
      </div>

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
                placeholder="例如：产品手册"
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
                  {(providers ?? []).map((p: Provider) => (
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
                  <SelectValue placeholder="选择已注册的 embedding 模型" />
                </SelectTrigger>
                <SelectContent>
                  {embeddingModels.map((m: Model) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.model_id}（{m.vector_dimension} 维）
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

      <div className="rounded-xl border border-border/60 bg-card/40 shadow-sm">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-muted-foreground">加载中…</div>
        ) : !kbs?.length ? (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <Database className="h-10 w-10 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">暂无知识库，点击「新建」开始</p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {kbs.map((kb) => (
              <li key={kb.id} className="flex items-center gap-4 px-4 py-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Database className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <Link
                    href={`/knowledge-bases/${kb.id}` as Route}
                    className="font-medium hover:text-primary hover:underline"
                  >
                    {kb.name}
                  </Link>
                  <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-muted-foreground">
                    <span>维度 {kb.embedding_dimension}</span>
                    <span>·</span>
                    <span className="font-mono truncate">{kb.collection_name}</span>
                  </div>
                </div>
                <Badge variant="secondary">{kb.document_count} 文档</Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => setDeleting(kb.id)}
                  aria-label="删除"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <AlertDialog open={!!deleting} onOpenChange={() => setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除知识库？</AlertDialogTitle>
            <AlertDialogDescription>
              将软删除知识库及文档索引，操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleting && deleteMutation.mutate(deleting)}
            >
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
