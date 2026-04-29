"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import type { Route } from "next";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { knowledgeBaseApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export default function DocumentChunksPage() {
  const params = useParams();
  const kbId = params.id as string;
  const docId = params.docId as string;
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);

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
  const selectedChunk =
    data.items.find((item) => item.id === selectedChunkId) ??
    data.items[0] ??
    null;
  const selectedSource = selectedChunk?.source ?? {};
  const pageAssetUrl = selectedSource.page_image_path
    ? knowledgeBaseApi.getReplayAssetUrl(kbId, docId, selectedSource.page_image_path)
    : null;
  const cropAssetUrl = selectedSource.crop_image_path
    ? knowledgeBaseApi.getReplayAssetUrl(kbId, docId, selectedSource.crop_image_path)
    : null;
  const bbox = selectedSource.bbox_norm;

  return (
    <div className="flex h-[calc(100dvh-5.5rem)] flex-col gap-4 overflow-hidden p-4 lg:p-5">
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
        <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-5">
          <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border bg-card lg:col-span-3">
            <div className="min-h-0 flex-1 overflow-auto">
              <table className="w-full caption-bottom text-sm">
                <TableHeader className="text-xs">
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">Chunk #</TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">预览文本</TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">字符长度</TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">Token 长度</TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">页码</TableHead>
                    <TableHead className="sticky top-0 z-10 h-10 bg-card py-2">章节</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((item) => (
                    <TableRow
                      key={item.id}
                      className={`cursor-pointer align-top ${
                        selectedChunk?.id === item.id ? "bg-primary/5 hover:bg-primary/10" : ""
                      }`}
                      onClick={() => setSelectedChunkId(item.id)}
                    >
                      <TableCell className="py-2.5">{item.chunk_index}</TableCell>
                      <TableCell className="max-w-xl truncate py-2.5" title={item.preview_text ?? ""}>
                        {item.preview_text ?? "（无预览）"}
                      </TableCell>
                      <TableCell className="py-2.5">{item.char_length ?? "-"}</TableCell>
                      <TableCell className="py-2.5">{item.token_length ?? "-"}</TableCell>
                      <TableCell className="py-2.5">{String(item.source?.page ?? "-")}</TableCell>
                      <TableCell className="py-2.5">{String(item.source?.section ?? "-")}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </table>
            </div>
          </div>

          <div className="flex min-h-0 flex-col gap-3 rounded-xl border bg-card p-3 lg:col-span-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium">回放面板</h3>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoom((v) => Math.max(0.5, Number((v - 0.1).toFixed(2))))}
                >
                  -
                </Button>
                <span className="w-10 text-center text-xs">{Math.round(zoom * 100)}%</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoom((v) => Math.min(2, Number((v + 0.1).toFixed(2))))}
                >
                  +
                </Button>
              </div>
            </div>

            <div className="text-xs text-muted-foreground">
              block_type: {selectedSource.block_type ?? "-"} · modality:{" "}
              {selectedSource.modality ?? "-"} · generator: {selectedSource.generator?.impl ?? "-"}
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-3">
              <div className="min-h-0 flex-1 overflow-auto rounded border bg-muted/20 p-2">
                {pageAssetUrl ? (
                  <div className="relative inline-block" style={{ transform: `scale(${zoom})`, transformOrigin: "top left" }}>
                    <img
                      src={pageAssetUrl}
                      alt="page replay"
                      className="h-auto max-w-full rounded"
                    />
                    {bbox ? (
                      <div
                        className="pointer-events-none absolute border-2 border-red-500"
                        style={{
                          left: `${bbox.x0 * 100}%`,
                          top: `${bbox.y0 * 100}%`,
                          width: `${Math.max(0, bbox.x1 - bbox.x0) * 100}%`,
                          height: `${Math.max(0, bbox.y1 - bbox.y0) * 100}%`,
                        }}
                      />
                    ) : null}
                  </div>
                ) : (
                  <div className="flex h-full min-h-48 items-center justify-center rounded border border-dashed bg-muted/10 p-4 text-xs text-muted-foreground">
                    当前 chunk 无 page_image 资源
                  </div>
                )}
              </div>

              <div className="shrink-0 space-y-2">
                <div className="text-xs font-medium">Crop 预览</div>
                <div className="h-44 overflow-auto rounded border bg-muted/20 p-2">
                  {cropAssetUrl ? (
                    <img src={cropAssetUrl} alt="crop replay" className="h-auto w-full object-contain" />
                  ) : (
                    <div className="flex h-full items-center justify-center rounded border border-dashed bg-muted/10 p-3 text-xs text-muted-foreground">
                      当前 chunk 无 crop_image 资源
                    </div>
                  )}
                </div>
              </div>

              <div className="shrink-0 space-y-1 text-xs">
                <div className="font-medium">多模态字段</div>
                <div className="h-28 overflow-auto rounded bg-muted/40 p-2 text-muted-foreground">
                  {(selectedChunk?.preview_text ?? "").slice(0, 300) || "无 OCR/caption/table_md/latex 展示内容"}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}

      <div className="flex shrink-0 items-center justify-between text-xs text-muted-foreground">
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
