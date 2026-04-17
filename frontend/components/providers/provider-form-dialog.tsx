"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useEffect } from "react";
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
});

type FormValues = z.infer<typeof schema>;

interface Props {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  initial?: Provider | null;
}

export function ProviderFormDialog({ open, onOpenChange, initial }: Props) {
  const qc = useQueryClient();
  const isEdit = !!initial;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      provider_type: "openai",
      api_key: "",
      base_url: "",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        name: initial?.name ?? "",
        provider_type: (initial?.provider_type as ProviderType) ?? "openai",
        api_key: "",
        base_url: initial?.base_url ?? "",
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
        };
        if (payload.api_key) update.api_key = payload.api_key;
        return providerApi.update(initial.id, update);
      }
      return providerApi.create(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["providers"] });
      toast.success(isEdit ? "已更新" : "已创建");
      onOpenChange(false);
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

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "保存中..." : "保存"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
