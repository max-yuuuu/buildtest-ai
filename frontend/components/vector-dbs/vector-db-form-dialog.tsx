"use client";

import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { vectorDbApi } from "@/lib/api";
import type { VectorDbConfig, VectorDbType, VectorDbUpdateInput } from "@/lib/types";
import {
  VECTOR_DB_CATALOG,
  type VectorDbTypeId,
} from "@/lib/vector-db-catalog";

const DB_TYPES = [
  "postgres_pgvector",
  "qdrant",
  "milvus",
  "weaviate",
  "pinecone",
  "chroma",
] as const satisfies readonly VectorDbTypeId[];

const schema = z.object({
  name: z.string().min(1, "必填").max(100),
  db_type: z.enum(DB_TYPES),
  connection_string: z.string(),
  api_key: z.string(),
  is_active: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: VectorDbConfig | null;
}

export function VectorDbFormDialog({ open, onOpenChange, initial }: Props) {
  const qc = useQueryClient();
  const isEdit = !!initial;

  const formSchema = useMemo(
    () =>
      schema.superRefine((vals, ctx) => {
        if (!isEdit && vals.connection_string.trim().length === 0) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: "必填",
            path: ["connection_string"],
          });
        }
      }),
    [isEdit],
  );

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      db_type: "postgres_pgvector",
      connection_string: "",
      api_key: "",
      is_active: true,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: initial?.name ?? "",
        db_type: (initial?.db_type as VectorDbType) ?? "postgres_pgvector",
        connection_string: "",
        api_key: "",
        is_active: initial?.is_active ?? true,
      });
    }
  }, [open, initial, form]);

  const selectedType = form.watch("db_type");
  const catalogEntry = VECTOR_DB_CATALOG.find((e) => e.id === selectedType);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (isEdit && initial) {
        const update: VectorDbUpdateInput = {
          name: values.name,
          is_active: values.is_active,
        };
        if (values.connection_string.trim()) {
          update.connection_string = values.connection_string.trim();
        }
        if (values.api_key.trim()) {
          update.api_key = values.api_key.trim();
        }
        return vectorDbApi.update(initial.id, update);
      }
      return vectorDbApi.create({
        name: values.name,
        db_type: values.db_type,
        connection_string: values.connection_string.trim(),
        api_key: values.api_key.trim() || null,
        is_active: values.is_active,
      });
    },
    onSuccess: async () => {
      qc.invalidateQueries({ queryKey: ["vector-dbs"] });
      onOpenChange(false);
      toast.success(isEdit ? "已更新" : "已创建");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "编辑向量库连接" : "新建向量库连接"}
          </DialogTitle>
          <DialogDescription>
            连接串与 API Key 会加密落库；列表仅显示掩码。PostgreSQL 请使用
            pgvector 且已执行{" "}
            <code className="rounded bg-muted px-1 text-xs">
              CREATE EXTENSION vector
            </code>
            。
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
          className="space-y-4"
        >
          <div className="space-y-1">
            <Label htmlFor="vd-name">名称</Label>
            <Input id="vd-name" {...form.register("name")} />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>类型</Label>
            <Select
              value={form.watch("db_type")}
              onValueChange={(v: string) =>
                form.setValue("db_type", v as VectorDbType)
              }
              disabled={isEdit}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VECTOR_DB_CATALOG.map((entry) => (
                  <SelectItem
                    key={entry.id}
                    value={entry.id}
                    disabled={!entry.connectorAvailable}
                  >
                    {entry.name}
                    {!entry.connectorAvailable ? "（即将支持）" : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {catalogEntry && (
              <div className="mt-2 max-h-40 space-y-2 overflow-y-auto rounded-lg border bg-muted/30 p-3 text-xs">
                <p className="text-muted-foreground">{catalogEntry.tagline}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div>
                    <p className="font-medium text-emerald-600 dark:text-emerald-400">
                      优点
                    </p>
                    <ul className="mt-1 list-inside list-disc text-muted-foreground">
                      {catalogEntry.pros.map((t) => (
                        <li key={t}>{t}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-amber-600 dark:text-amber-400">
                      缺点
                    </p>
                    <ul className="mt-1 list-inside list-disc text-muted-foreground">
                      {catalogEntry.cons.map((t) => (
                        <li key={t}>{t}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                <p className="text-muted-foreground">
                  <span className="font-medium text-foreground">适合：</span>
                  {catalogEntry.bestFor}
                </p>
              </div>
            )}
          </div>

          <div className="space-y-1">
            <Label htmlFor="vd-conn">连接串 / Base URL</Label>
            <Input
              id="vd-conn"
              placeholder="postgresql://user:pass@host:5432/db 或 http://localhost:6333"
              autoComplete="off"
              {...form.register("connection_string")}
            />
            {form.formState.errors.connection_string && (
              <p className="text-xs text-destructive">
                {form.formState.errors.connection_string.message}
              </p>
            )}
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                留空则不修改当前连接串（仍显示掩码：{initial?.connection_string_mask}
                ）
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label htmlFor="vd-key">
              API Key（可选，如 Qdrant Cloud）
              {isEdit && (
                <span className="text-xs text-muted-foreground">（留空不修改）</span>
              )}
            </Label>
            <Input
              id="vd-key"
              type="password"
              autoComplete="off"
              placeholder={isEdit ? "留空则不修改" : "无则留空"}
              {...form.register("api_key")}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="vd-active" className="text-sm font-medium">
                启用连接
              </Label>
              <p className="text-xs text-muted-foreground">
                关闭后知识库将不可选用此配置
              </p>
            </div>
            <Switch
              id="vd-active"
              checked={form.watch("is_active")}
              onCheckedChange={(v) => form.setValue("is_active", v)}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "保存中…" : isEdit ? "保存" : "创建"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
