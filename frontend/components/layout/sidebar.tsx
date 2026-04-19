"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  Database,
  LayoutDashboard,
  KeyRound,
  LogOut,
  Sparkles,
  ChevronsUpDown,
  FlaskConical,
  FileText,
  MessageSquareText,
  Boxes,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  soon?: boolean;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    label: "工作台",
    items: [{ href: "/dashboard", label: "概览", icon: LayoutDashboard }],
  },
  {
    label: "资源",
    items: [
      { href: "/providers", label: "Provider", icon: KeyRound },
      { href: "/knowledge-bases", label: "知识库", icon: Database },
      { href: "/vector-dbs", label: "向量库", icon: Boxes },
    ],
  },
  {
    label: "构建",
    items: [
      { href: "/prompts", label: "Prompt", icon: MessageSquareText, soon: true },
      { href: "/agents", label: "Agent", icon: Sparkles, soon: true },
    ],
  },
  {
    label: "评测",
    items: [
      { href: "/datasets", label: "数据集", icon: FileText, soon: true },
      { href: "/evaluations", label: "评测任务", icon: FlaskConical, soon: true },
    ],
  },
];

function initials(value?: string | null) {
  if (!value) return "U";
  const trimmed = value.trim();
  if (!trimmed) return "U";
  const first = trimmed.codePointAt(0);
  if (first === undefined) return "U";
  return String.fromCodePoint(first).toUpperCase();
}

export function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();

  const displayName = session?.user?.name ?? session?.user?.email ?? "未登录";
  const displayEmail = session?.user?.email ?? "";

  return (
    <aside className="relative hidden h-screen w-64 shrink-0 flex-col border-r border-sidebar-border/60 bg-sidebar/70 text-sidebar-foreground backdrop-blur-xl md:flex">
      {/* Vertical gradient accent line on right edge */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 right-0 w-px bg-gradient-to-b from-transparent via-primary/40 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-primary/10 via-primary/3 to-transparent"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-grid-pattern opacity-[0.35] mask-fade-bottom"
      />

      <div className="relative flex h-16 items-center gap-3 px-5">
        <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-fuchsia-500 to-cyan-500 text-white shadow-md animate-pulse-glow">
          <Sparkles className="h-4 w-4 drop-shadow" />
        </div>
        <div className="flex min-w-0 flex-col leading-tight">
          <span className="truncate text-sm font-semibold tracking-tight">
            BuildTest AI
          </span>
          <span className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-[0.14em] text-sidebar-muted-foreground">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </span>
            Online
          </span>
        </div>
      </div>

      <nav className="relative flex-1 overflow-y-auto px-3 py-3">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-5 last:mb-0">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-sidebar-muted-foreground">
              {group.label}
            </div>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = pathname.startsWith(item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href as never}
                      aria-disabled={item.soon}
                      className={cn(
                        "group relative flex items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-sm font-medium transition-all",
                        active
                          ? "bg-gradient-to-r from-primary/10 via-primary/5 to-transparent text-sidebar-accent-foreground shadow-sm ring-1 ring-primary/10"
                          : "text-sidebar-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
                        item.soon && "opacity-60",
                      )}
                    >
                      {active && (
                        <span
                          className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-gradient-to-b from-primary via-fuchsia-500 to-cyan-500"
                          aria-hidden
                        />
                      )}
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          active
                            ? "text-primary"
                            : "text-sidebar-muted-foreground group-hover:text-sidebar-accent-foreground",
                        )}
                      />
                      <span className="truncate">{item.label}</span>
                      {item.soon && (
                        <span className="ml-auto rounded-full border border-sidebar-border/80 bg-sidebar-muted px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider text-sidebar-muted-foreground">
                          Soon
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="relative mx-3 mb-3 overflow-hidden rounded-xl border border-sidebar-border/70 bg-gradient-to-br from-primary/10 via-fuchsia-500/5 to-cyan-500/10 p-3">
        <div
          aria-hidden
          className="pointer-events-none absolute -right-8 -top-8 h-20 w-20 rounded-full bg-gradient-to-br from-fuchsia-500/30 to-transparent blur-2xl"
        />
        <div className="relative flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.12em] text-sidebar-muted-foreground">
          <Sparkles className="h-3 w-3 text-primary" />
          AI Runtime
        </div>
        <div className="relative mt-2 flex items-baseline justify-between">
          <span className="text-sm font-semibold">就绪</span>
          <span className="font-mono text-[10px] text-sidebar-muted-foreground">
            v0.1
          </span>
        </div>
        <div className="relative mt-1 text-[11px] text-sidebar-muted-foreground">
          Provider · 知识库 · 评测 链路正常
        </div>
      </div>

      <div className="relative border-t border-sidebar-border/70 p-3">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-sidebar-accent/60"
            >
              <Avatar className="h-8 w-8 ring-2 ring-primary/20">
                <AvatarFallback className="bg-gradient-to-br from-primary via-fuchsia-500 to-cyan-500 text-white">
                  {initials(displayName)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">
                  {displayName}
                </div>
                {displayEmail && (
                  <div className="truncate text-xs text-sidebar-muted-foreground">
                    {displayEmail}
                  </div>
                )}
              </div>
              <ChevronsUpDown className="h-4 w-4 text-sidebar-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent side="top" align="start" className="w-56">
            <DropdownMenuLabel className="truncate">
              {displayEmail || displayName}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive focus:text-destructive"
              onClick={() => signOut({ callbackUrl: "/login" })}
            >
              <LogOut className="mr-2 h-4 w-4" />
              登出
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </aside>
  );
}
