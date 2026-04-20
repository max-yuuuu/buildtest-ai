"use client";

import { useEffect } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { modelApi } from "@/lib/api";
import type { AvailableModel, Model, ModelType } from "@/lib/types";

const schema = z
  .object({
    model_id: z.string().min(1),
    model_type: z.enum(["llm", "embedding"] as const),
    context_window: z
      .string()
      .optional()
      .refine((v) => !v || /^\d+$/.test(v), "必须是正整数")
      .transform((v) => (v ? Number(v) : null)),
    vector_dimension: z
      .string()
      .optional()
      .refine((v) => !v || /^\d+$/.test(v), "必须是正整数")
      .transform((v) => (v ? Number(v) : null)),
    embedding_batch_size: z
      .string()
      .optional()
      .refine((v) => !v || /^\d+$/.test(v), "必须是正整数")
      .transform((v) => (v ? Number(v) : null)),
  })
  .refine(
    (d) =>
      d.model_type !== "embedding" ||
      (typeof d.vector_dimension === "number" && d.vector_dimension > 0),
    {
      path: ["vector_dimension"],
      message: "embedding 模型必填 vector_dimension",
    },
  )
  .superRefine((data, ctx) => {
    if (
      data.model_type === "embedding" &&
      data.embedding_batch_size !== null &&
      (data.embedding_batch_size < 1 || data.embedding_batch_size > 2048)
    ) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["embedding_batch_size"],
        message: "范围为 1–2048",
      });
    }
  });

type FormValues = z.input<typeof schema>;
type FormParsed = z.output<typeof schema>;

function defaultValuesFromProps(
  candidate: AvailableModel | null | undefined,
  editing: Model | null | undefined,
): FormValues {
  if (editing) {
    return {
      model_id: editing.model_id,
      model_type: editing.model_type,
      context_window: editing.context_window?.toString() ?? "",
      vector_dimension: editing.vector_dimension?.toString() ?? "",
      embedding_batch_size: editing.embedding_batch_size?.toString() ?? "",
    };
  }
  return {
    model_id: candidate?.model_id ?? "",
    model_type: (candidate?.suggested_type ?? "llm") as ModelType,
    context_window: "",
    vector_dimension: "",
    embedding_batch_size: "",
  };
}

interface Props {
  providerId: string;
  /** 传入表示"从可用列表登记",model_id 只读;不传表示"手动登记"。 */
  candidate?: AvailableModel | null;
  /** 传入表示编辑已登记模型。 */
  editing?: Model | null;
  onOpenChange: (v: boolean) => void;
}

export function RegisterModelDialog({
  providerId,
  candidate,
  editing,
  onOpenChange,
}: Props) {
  const qc = useQueryClient();
  const isEdit = !!editing;
  const isManual = !candidate && !editing;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultValuesFromProps(candidate, editing),
  });

  useEffect(() => {
    form.reset(defaultValuesFromProps(candidate, editing));
  }, [candidate, editing, form]);

  const modelType = form.watch("model_type");

  const mutation = useMutation({
    mutationFn: async (values: FormParsed) => {
      const embeddingOnly = values.model_type === "embedding";
      if (isEdit && editing) {
        return modelApi.update(providerId, editing.id, {
          model_type: values.model_type,
          ...(values.model_type === "llm"
            ? { context_window: values.context_window }
            : {
                vector_dimension: values.vector_dimension,
                embedding_batch_size: embeddingOnly
                  ? values.embedding_batch_size
                  : null,
              }),
        });
      }
      return modelApi.create(providerId, {
        model_id: values.model_id,
        model_type: values.model_type,
        context_window: values.context_window,
        vector_dimension: values.vector_dimension,
        embedding_batch_size: embeddingOnly
          ? values.embedding_batch_size
          : null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models", providerId] });
      qc.invalidateQueries({ queryKey: ["models-available", providerId] });
      toast.success(isEdit ? "已保存" : "已登记");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {isEdit
              ? "编辑模型"
              : isManual
                ? "手动登记模型"
                : "登记模型"}
          </DialogTitle>
          <DialogDescription>
            {isEdit ? (
              "修改已登记模型的参数。"
            ) : isManual ? (
              "当上游 /models 未返回目标模型时(如百炼 embedding),在此手动录入 model_id。"
            ) : (
              "把上游模型登记到本地,知识库 / 评测任务才能绑定。"
            )}{" "}
            embedding 模型必须提供向量维度;单次向量化条数可填{" "}
            <span className="font-mono">embedding_batch_size</span>
            (可选,1–2048,留空用默认)。
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit((v) =>
            mutation.mutate(v as unknown as FormParsed),
          )}
          className="space-y-4"
        >
          <div className="space-y-1">
            <Label htmlFor="model_id">model_id</Label>
            <Input
              id="model_id"
              readOnly={!isManual}
              placeholder={isManual ? "如 text-embedding-v4" : undefined}
              className="font-mono text-xs"
              {...form.register("model_id")}
            />
            {form.formState.errors.model_id && (
              <p className="text-xs text-destructive">
                {form.formState.errors.model_id.message as string}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>类型</Label>
            <Select
              value={form.watch("model_type")}
              onValueChange={(v: string) =>
                form.setValue("model_type", v as ModelType)
              }
              disabled={isEdit}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="llm">llm（对话 / 生成）</SelectItem>
                <SelectItem value="embedding">embedding（向量化）</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {modelType === "llm" ? (
            <div className="space-y-1">
              <Label htmlFor="context_window">
                context_window{" "}
                <span className="text-xs text-muted-foreground">(可选)</span>
              </Label>
              <Input
                id="context_window"
                type="number"
                min={1}
                placeholder="如 128000"
                {...form.register("context_window")}
              />
            </div>
          ) : (
            <>
              <div className="space-y-1">
                <Label htmlFor="vector_dimension">
                  vector_dimension{" "}
                  <span className="text-xs text-destructive">*</span>
                </Label>
                <Input
                  id="vector_dimension"
                  type="number"
                  min={1}
                  placeholder="如 1536 / 3072"
                  {...form.register("vector_dimension")}
                />
                {form.formState.errors.vector_dimension && (
                  <p className="text-xs text-destructive">
                    {form.formState.errors.vector_dimension.message as string}
                  </p>
                )}
              </div>
              <div className="space-y-1">
                <Label htmlFor="embedding_batch_size">
                  embedding_batch_size{" "}
                  <span className="text-xs text-muted-foreground">(可选)</span>
                </Label>
                <Input
                  id="embedding_batch_size"
                  type="number"
                  min={1}
                  max={2048}
                  placeholder="如 10；留空则使用服务端默认"
                  {...form.register("embedding_batch_size")}
                />
                {form.formState.errors.embedding_batch_size && (
                  <p className="text-xs text-destructive">
                    {
                      form.formState.errors.embedding_batch_size
                        .message as string
                    }
                  </p>
                )}
              </div>
            </>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending
                ? isEdit
                  ? "保存中..."
                  : "登记中..."
                : isEdit
                  ? "保存"
                  : "登记"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
