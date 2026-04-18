"use client";

import { useTheme } from "next-themes";
import { usePathname } from "next/navigation";
import { Moon, Search, Sun, Command, Cpu, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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
    <header className="relative z-30 flex h-16 shrink-0 items-center gap-4 border-b border-border/50 bg-background/60 px-6 backdrop-blur-xl">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent"
      />

      <div className="flex min-w-0 flex-1 items-center gap-3">
        <div className="flex min-w-0 flex-col leading-tight">
          <h1 className="truncate text-sm font-semibold tracking-tight">
            {title}
          </h1>
          {description && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </div>

      <div className="hidden items-center gap-1.5 rounded-full border border-primary/20 bg-gradient-to-r from-primary/5 via-fuchsia-500/5 to-cyan-500/5 px-3 py-1 text-[11px] font-medium text-muted-foreground md:inline-flex">
        <Cpu className="h-3.5 w-3.5 text-primary" />
        <span className="text-foreground">GPT-4o</span>
        <span className="mx-0.5 h-3 w-px bg-border" />
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-70" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
        </span>
        <span>就绪</span>
      </div>

      <div className="relative hidden w-72 lg:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="搜索资源、Prompt、评测…"
          className="h-9 rounded-lg border-border/60 bg-muted/40 pl-9 pr-16 text-sm shadow-inner focus-visible:ring-primary/30"
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded border border-border/70 bg-background/80 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          <Command className="h-3 w-3" />K
        </kbd>
      </div>

      <Button
        variant="ghost"
        size="icon"
        aria-label="通知"
        className="relative rounded-lg"
      >
        <Bell className="h-4 w-4" />
        <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-fuchsia-500" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        aria-label="切换主题"
        className="rounded-lg"
        onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      >
        <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
        <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      </Button>
    </header>
  );
}
