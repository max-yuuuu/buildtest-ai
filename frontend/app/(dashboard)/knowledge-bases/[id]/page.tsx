"use client";

import type { ChangeEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Search } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import type { Route } from "next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { knowledgeBaseApi } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function KnowledgeBaseDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const qc = useQueryClient();
  const formInit = useRef(false);

  const { data: kb, isLoading } = useQuery({
    queryKey: ["knowledge-bases", id],
    queryFn: () => knowledgeBaseApi.get(id),
  });
  const { data: docs } = useQuery({
    queryKey: ["knowledge-bases", id, "documents"],
    queryFn: () => knowledgeBaseApi.listDocuments(id),
  });

  const [name, setName] = useState("");
  const [chunkSize, setChunkSize] = useState("");
  const [chunkOverlap, setChunkOverlap] = useState("");
  const [topK, setTopK] = useState("");
  const [threshold, setThreshold] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<
    { document_id: string; chunk_index: number; text: string; score: number }[]
  >([]);

  useEffect(() => {
    formInit.current = false;
  }, [id]);

  useEffect(() => {
    if (!kb || formInit.current) return;
    formInit.current = true;
    setName(kb.name);
    setChunkSize(String(kb.chunk_size));
    setChunkOverlap(String(kb.chunk_overlap));
    setTopK(String(kb.retrieval_top_k));
    setThreshold(String(kb.retrieval_similarity_threshold));
  }, [kb]);

  const updateMutation = useMutation({
    mutationFn: () =>
      knowledgeBaseApi.update(id, {
        name: name.trim(),
        chunk_size: Number(chunkSize),
        chunk_overlap: Number(chunkOverlap),
        retrieval_top_k: Number(topK),
        retrieval_similarity_threshold: Number(threshold),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("已保存");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => knowledgeBaseApi.uploadDocument(id, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id, "documents"] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases", id] });
      qc.invalidateQueries({ queryKey: ["knowledge-bases"] });
      toast.success("上传完成");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const retrieveMutation = useMutation({
    mutationFn: () => knowledgeBaseApi.retrieve(id, { query: query.trim() }),
    onSuccess: (res) => {
      setHits(res.hits);
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
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading || !kb) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        {isLoading ? "加载中…" : "未找到知识库"}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-4 lg:p-6">
      <div>
        <Button variant="ghost" size="sm" asChild className="mb-2 -ml-2 gap-1">
          <Link href={"/knowledge-bases" as Route}>
            <ArrowLeft className="h-4 w-4" />
            返回列表
          </Link>
        </Button>
        <h1 className="text-xl font-semibold">{kb.name}</h1>
        <p className="mt-1 font-mono text-xs text-muted-foreground">{kb.collection_name}</p>
      </div>

      <section className="space-y-3 rounded-xl border border-border/60 bg-card/30 p-4">
        <h2 className="text-sm font-medium">基础与切块</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <Label>名称</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>向量维度（只读）</Label>
            <Input readOnly value={String(kb.embedding_dimension)} />
          </div>
          <div className="space-y-1">
            <Label>chunk_size</Label>
            <Input value={chunkSize} onChange={(e) => setChunkSize(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>chunk_overlap</Label>
            <Input value={chunkOverlap} onChange={(e) => setChunkOverlap(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>默认 top_k</Label>
            <Input value={topK} onChange={(e) => setTopK(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label>默认相似度阈值</Label>
            <Input value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          </div>
        </div>
        <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
          保存设置
        </Button>
      </section>

      <section className="space-y-3 rounded-xl border border-border/60 bg-card/30 p-4">
        <h2 className="text-sm font-medium">文档</h2>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            type="file"
            className="max-w-xs cursor-pointer"
            onChange={(e: ChangeEvent<HTMLInputElement>) => {
              const f = e.target.files?.[0];
              if (f) uploadMutation.mutate(f);
              e.target.value = "";
            }}
          />
          <span className="text-xs text-muted-foreground">支持 txt / md / pdf / docx</span>
        </div>
        <ul className="divide-y divide-border/50 rounded-lg border border-border/50">
          {(docs ?? []).map((d) => (
            <li key={d.id} className="flex items-center gap-2 px-3 py-2 text-sm">
              <span className="min-w-0 flex-1 truncate">{d.file_name}</span>
              <span className="text-muted-foreground">{d.status}</span>
              <span className="text-muted-foreground">{d.chunk_count} 块</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => deleteDocMutation.mutate(d.id)}
                disabled={deleteDocMutation.isPending}
              >
                删除
              </Button>
            </li>
          ))}
          {!docs?.length && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">暂无文档</li>
          )}
        </ul>
      </section>

      <section className="space-y-3 rounded-xl border border-border/60 bg-card/30 p-4">
        <h2 className="text-sm font-medium">试检索</h2>
        <textarea
          className={cn(
            "flex min-h-[88px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          )}
          placeholder="输入查询…"
          value={query}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setQuery(e.target.value)}
          rows={3}
        />
        <Button
          className="gap-2"
          onClick={() => retrieveMutation.mutate()}
          disabled={!query.trim() || retrieveMutation.isPending}
        >
          <Search className="h-4 w-4" />
          检索
        </Button>
        {hits.length > 0 && (
          <ul className="space-y-2 pt-2">
            {hits.map((h, i) => (
              <li
                key={`${h.document_id}-${h.chunk_index}-${i}`}
                className="rounded-lg border border-border/50 bg-background/50 p-3 text-sm"
              >
                <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                  <span>文档 {h.document_id.slice(0, 8)}…</span>
                  <span>分数 {h.score.toFixed(4)}</span>
                </div>
                <p className="whitespace-pre-wrap text-foreground/90">{h.text}</p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
