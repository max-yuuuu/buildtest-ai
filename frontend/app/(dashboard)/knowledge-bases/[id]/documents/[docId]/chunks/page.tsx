"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Route } from "next";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { knowledgeBaseApi } from "@/lib/api";
import { Button } from "@/components/ui/button";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function DocumentChunksPage() {
  const params = useParams();
  const kbId = params.id as string;
  const docId = params.docId as string;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const chunksQuery = useQuery({
    queryKey: ["knowledge-bases", kbId, "documents", docId, "chunks", page, pageSize],
    queryFn: () => knowledgeBaseApi.getDocumentChunks(kbId, docId, page, pageSize),
    retry: false,
  });

  const errorText = useMemo(() => {
    const message = chunksQuery.error instanceof Error ? chunksQuery.error.message : "";
    if (message.includes("Document is not ready")) return "文档尚未完成处理，请稍后再试";
    if (message.includes("404")) return "文档不存在或无权限访问";
    return message || "加载分块失败";
  }, [chunksQuery.error]);

  if (chunksQuery.isLoading) {
    return (
      <div className="p-6 text-sm text-muted-foreground">
        <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
        加载分块中...
      </div>
    );
  }

  if (chunksQuery.isError || !chunksQuery.data) {
    return (
      <div className="space-y-4 p-6">
        <p className="text-sm text-destructive">{errorText}</p>
        <Button asChild variant="outline">
          <Link href={`/knowledge-bases/${kbId}` as Route}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回文档列表
          </Link>
        </Button>
      </div>
    );
  }

  const data = chunksQuery.data;
  return (
    <div className="space-y-4 p-4 lg:p-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{data.document.name || "未命名文档"}</h2>
          <p className="text-xs text-muted-foreground">
            状态: {data.document.status} · Chunk 总数: {data.chunk_summary.total_chunks}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href={`/knowledge-bases/${kbId}` as Route}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回文档列表
          </Link>
        </Button>
      </div>

      {data.chunk_summary.total_chunks === 0 ? (
        <div className="rounded-lg border bg-card p-6 text-sm text-muted-foreground">
          暂无可展示分块数据
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border bg-card">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">Chunk #</th>
                <th className="px-4 py-2 text-left font-medium">预览文本</th>
                <th className="px-4 py-2 text-left font-medium">字符长度</th>
                <th className="px-4 py-2 text-left font-medium">Token 长度</th>
                <th className="px-4 py-2 text-left font-medium">页码</th>
                <th className="px-4 py-2 text-left font-medium">章节</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id} className="border-t align-top">
                  <td className="px-4 py-2.5">{item.chunk_index}</td>
                  <td className="max-w-xl truncate px-4 py-2.5" title={item.preview_text ?? ""}>
                    {item.preview_text ?? "（无预览）"}
                  </td>
                  <td className="px-4 py-2.5">{item.char_length ?? "-"}</td>
                  <td className="px-4 py-2.5">{item.token_length ?? "-"}</td>
                  <td className="px-4 py-2.5">{String(item.source?.page ?? "-")}</td>
                  <td className="px-4 py-2.5">{String(item.source?.section ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          第 {data.pagination.page} / {data.pagination.total_pages} 页 · 共 {data.pagination.total} 条
        </span>
        <div className="flex items-center gap-2">
          <span>每页</span>
          <select
            className="rounded border bg-background px-2 py-1"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
          >
            {PAGE_SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
          >
            上一页
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.pagination.total_pages}
            onClick={() => setPage((prev) => prev + 1)}
          >
            下一页
          </Button>
        </div>
      </div>
    </div>
  );
}
