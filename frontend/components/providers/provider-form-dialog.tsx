"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
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
import { providerApi } from "@/lib/api";
import type { Provider, ProviderType } from "@/lib/types";

const PROVIDER_TYPES: ProviderType[] = [
  "openai",
  "anthropic",
  "azure",
  "zhipu",
  "qwen",
];

const schema = z.object({
  name: z.string().min(1, "必填").max(100),
  provider_type: z.enum([
    "openai",
    "anthropic",
    "azure",
    "zhipu",
    "qwen",
  ] as const),
  api_key: z.string().min(1, "必填"),
  base_url: z.string().url().optional().or(z.literal("")),
  is_active: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Provider | null;
}

export function ProviderFormDialog({ open, onOpenChange, initial }: Props) {
  const qc = useQueryClient();
  const router = useRouter();
  const isEdit = !!initial;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      provider_type: "openai",
      api_key: "",
      base_url: "",
      is_active: true,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: initial?.name ?? "",
        provider_type: (initial?.provider_type as ProviderType) ?? "openai",
        api_key: "",
        base_url: initial?.base_url ?? "",
        is_active: initial?.is_active ?? true,
      });
    }
  }, [open, initial, form]);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const payload = {
        ...values,
        base_url: values.base_url || null,
      };
      if (isEdit && initial) {
        const update: Record<string, unknown> = {
          name: payload.name,
          base_url: payload.base_url,
          is_active: payload.is_active,
        };
        if (payload.api_key) update.api_key = payload.api_key;
        const updated = await providerApi.update(initial.id, update);
        return { provider: updated, isCreate: false };
      }
      const created = await providerApi.create(payload);
      return { provider: created, isCreate: true };
    },
    onSuccess: async ({ provider, isCreate }) => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      onOpenChange(false);

      if (!isCreate) {
        toast.success("已更新");
        return;
      }

      // 预检连通性 —— 失败仅给警告,不阻断创建流。
      const probing = toast.loading(`已创建 ${provider.name}，正在预检连通性…`);
      try {
        const result = await providerApi.test(provider.id);
        toast.dismiss(probing);
        if (result.ok) {
          toast.success(
            `连通性 OK（${result.latency_ms}ms）,去登记可用模型`,
          );
        } else {
          toast.warning(
            `Provider 已创建,但连通性预检失败:${result.message}。可稍后到列表页重试。`,
          );
        }
      } catch (err) {
        toast.dismiss(probing);
        toast.warning(
          `Provider 已创建,连通性预检未完成:${(err as Error).message}`,
        );
      }
      router.push(`/providers/${provider.id}/models` as Route);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑 Provider" : "新建 Provider"}</DialogTitle>
          <DialogDescription>
            API Key 会以 Fernet 加密落库,列表中仅显示掩码。
            {!isEdit && " 创建后会自动预检连通性,并跳转去登记可用模型。"}
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
          className="space-y-4"
        >
          <div className="space-y-1">
            <Label htmlFor="name">名称</Label>
            <Input id="name" {...form.register("name")} />
            {form.formState.errors.name && (
              <p className="text-xs text-destructive">
                {form.formState.errors.name.message}
              </p>
            )}
          </div>

          <div className="space-y-1">
            <Label>类型</Label>
            <Select
              value={form.watch("provider_type")}
              onValueChange={(v: string) =>
                form.setValue("provider_type", v as ProviderType)
              }
              disabled={isEdit}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDER_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1">
            <Label htmlFor="api_key">
              API Key {isEdit && <span className="text-xs text-muted-foreground">(留空则不修改)</span>}
            </Label>
            <Input
              id="api_key"
              type="password"
              autoComplete="off"
              {...form.register("api_key", {
                required: isEdit ? false : "必填",
              })}
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="base_url">Base URL(可选)</Label>
            <Input
              id="base_url"
              placeholder="https://api.openai.com/v1"
              {...form.register("base_url")}
            />
            {form.formState.errors.base_url && (
              <p className="text-xs text-destructive">URL 格式不正确</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="space-y-0.5">
              <Label htmlFor="is_active" className="text-sm font-medium">
                启用 Provider
              </Label>
              <p className="text-xs text-muted-foreground">
                关闭后平台将视为此配置停用(仍可编辑与删除)
              </p>
            </div>
            <Switch
              id="is_active"
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
              {mutation.isPending
                ? "保存中..."
                : isEdit
                  ? "保存"
                  : "保存并预检"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
