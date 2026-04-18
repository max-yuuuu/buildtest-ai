"use client";

import { useTheme } from "next-themes";
import { usePathname } from "next/navigation";
import { Moon, Search, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

const pageTitles: Record<string, { title: string; description?: string }> = {
  "/dashboard": { title: "概览", description: "平台运行状态与快速入口" },
  "/providers": {
    title: "Provider",
    description: "配置 LLM / Embedding 服务商的 API Key",
  },
  "/knowledge-bases": {
    title: "知识库",
    description: "文档上传、切片、向量化",
  },
};

function resolveTitle(pathname: string) {
  const exact = pageTitles[pathname];
  if (exact) return exact;
  const prefix = Object.keys(pageTitles).find((key) => pathname.startsWith(key));
  return prefix ? pageTitles[prefix] : { title: "BuildTest AI" };
}

export function Header() {
  const pathname = usePathname();
  const { setTheme, resolvedTheme } = useTheme();
  const { title, description } = resolveTitle(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-4 border-b border-border/80 bg-background/80 px-6 backdrop-blur">
      <div className="flex min-w-0 flex-1 flex-col">
        <h1 className="truncate text-lg font-semibold leading-none">{title}</h1>
        {description && (
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {description}
          </p>
        )}
      </div>

      <div className="relative hidden w-72 lg:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="搜索 (Ctrl + K)"
          className="h-9 bg-muted/50 pl-9 text-sm"
        />
      </div>

      <Separator orientation="vertical" className="h-6" />

      <Button
        variant="ghost"
        size="icon"
        aria-label="切换主题"
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </Button>
    </header>
  );
}
