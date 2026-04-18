"use client";

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
import type { AvailableModel, ModelType } from "@/lib/types";

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
  })
  .refine(
    (d) =>
      d.model_type !== "embedding" ||
      (typeof d.vector_dimension === "number" && d.vector_dimension > 0),
    {
      path: ["vector_dimension"],
      message: "embedding 模型必填 vector_dimension",
    },
  );

type FormValues = z.input<typeof schema>;
type FormParsed = z.output<typeof schema>;

interface Props {
  providerId: string;
  candidate: AvailableModel;
  onOpenChange: (v: boolean) => void;
}

export function RegisterModelDialog({
  providerId,
  candidate,
  onOpenChange,
}: Props) {
  const qc = useQueryClient();

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      model_id: candidate.model_id,
      model_type: (candidate.suggested_type ?? "llm") as ModelType,
      context_window: "",
      vector_dimension: "",
    },
  });

  const modelType = form.watch("model_type");

  const mutation = useMutation({
    mutationFn: (values: FormParsed) =>
      modelApi.create(providerId, {
        model_id: values.model_id,
        model_type: values.model_type,
        context_window: values.context_window,
        vector_dimension: values.vector_dimension,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["models", providerId] });
      qc.invalidateQueries({ queryKey: ["models-available", providerId] });
      toast.success("已登记");
      onOpenChange(false);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>登记模型</DialogTitle>
          <DialogDescription>
            把上游模型登记到本地,知识库 / 评测任务才能绑定。
            embedding 模型必须提供向量维度。
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
              readOnly
              className="font-mono text-xs"
              {...form.register("model_id")}
            />
          </div>

          <div className="space-y-1">
            <Label>类型</Label>
            <Select
              value={form.watch("model_type")}
              onValueChange={(v: string) =>
                form.setValue("model_type", v as ModelType)
              }
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
              {mutation.isPending ? "登记中..." : "登记"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
