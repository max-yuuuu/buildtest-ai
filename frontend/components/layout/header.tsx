"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { usePathname, useRouter } from "next/navigation";
import {
  Moon,
  Search,
  Sun,
  Command,
  Bell,
  ArrowUpRight,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { knowledgeBaseApi, notificationApi, providerApi, vectorDbApi } from "@/lib/api";
import type { IngestionNotification, KnowledgeBase, Provider, VectorDbConfig } from "@/lib/types";
import { cn } from "@/lib/utils";

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
  "/vector-dbs": {
    title: "向量库",
    description: "pgvector、Qdrant 等连接与连通性测试",
  },
};

function resolveTitle(pathname: string) {
  const exact = pageTitles[pathname];
  if (exact) return exact;
  const prefix = Object.keys(pageTitles).find((key) => pathname.startsWith(key));
  return prefix ? pageTitles[prefix] : { title: "BuildTest AI" };
}

type SearchItem = {
  id: string;
  label: string;
  detail?: string;
  href: string;
  group: "页面" | "Provider" | "知识库" | "向量库";
};

const pageItems: SearchItem[] = [
  { id: "page-dashboard", label: "概览", href: "/dashboard", group: "页面" },
  { id: "page-providers", label: "Provider", href: "/providers", group: "页面" },
  {
    id: "page-knowledge-bases",
    label: "知识库",
    href: "/knowledge-bases",
    group: "页面",
  },
  { id: "page-vector-dbs", label: "向量库", href: "/vector-dbs", group: "页面" },
];

function includesKeyword(...values: Array<string | undefined>) {
  return values
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function formatNotificationTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();
  const { title, description } = resolveTitle(pathname);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const bellPanelRef = useRef<HTMLDivElement>(null);

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasLoadedIndex, setHasLoadedIndex] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [vectorDbs, setVectorDbs] = useState<VectorDbConfig[]>([]);
  const [notifications, setNotifications] = useState<IngestionNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open || hasLoadedIndex) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    void Promise.allSettled([
      providerApi.list(),
      knowledgeBaseApi.list(),
      vectorDbApi.list(),
    ])
      .then((results) => {
        if (cancelled) return;

        const [providerResult, kbResult, vectorDbResult] = results;
        if (providerResult.status === "fulfilled") {
          setProviders(providerResult.value);
        } else {
          setProviders([]);
        }
        if (kbResult.status === "fulfilled") {
          setKnowledgeBases(kbResult.value);
        } else {
          setKnowledgeBases([]);
        }
        if (vectorDbResult.status === "fulfilled") {
          setVectorDbs(vectorDbResult.value);
        } else {
          setVectorDbs([]);
        }

        const allFailed = results.every((result) => result.status === "rejected");
        if (allFailed) {
          setLoadError("搜索索引加载失败，请稍后重试");
        }
        setHasLoadedIndex(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [hasLoadedIndex, open]);

  useEffect(() => {
    const onClickOutside = (event: MouseEvent) => {
      if (
        !panelRef.current?.contains(event.target as Node) &&
        !bellPanelRef.current?.contains(event.target as Node)
      ) {
        setOpen(false);
        setNotificationOpen(false);
      }
    };
    if (open || notificationOpen) {
      window.addEventListener("mousedown", onClickOutside);
    }
    return () => window.removeEventListener("mousedown", onClickOutside);
  }, [notificationOpen, open]);

  const searchItems = useMemo<SearchItem[]>(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const providerItems = providers.map((provider) => ({
      id: `provider-${provider.id}`,
      label: provider.name,
      detail: provider.provider_type,
      href: `/providers/${provider.id}/models`,
      group: "Provider" as const,
    }));
    const kbItems = knowledgeBases.map((kb) => ({
      id: `kb-${kb.id}`,
      label: kb.name,
      detail: kb.description ?? undefined,
      href: `/knowledge-bases/${kb.id}`,
      group: "知识库" as const,
    }));
    const vectorDbItems = vectorDbs.map((vectorDb) => ({
      id: `vector-db-${vectorDb.id}`,
      label: vectorDb.name,
      detail: vectorDb.db_type,
      href: "/vector-dbs",
      group: "向量库" as const,
    }));

    const allItems = [...pageItems, ...providerItems, ...kbItems, ...vectorDbItems];
    if (!normalizedQuery) return allItems.slice(0, 8);
    return allItems.filter((item) =>
      includesKeyword(item.label, item.detail, item.group).includes(normalizedQuery),
    );
  }, [knowledgeBases, providers, query, vectorDbs]);

  const groupedResults = useMemo(() => {
    return searchItems.reduce<Record<string, SearchItem[]>>((acc, item) => {
      if (!acc[item.group]) acc[item.group] = [];
      acc[item.group].push(item);
      return acc;
    }, {});
  }, [searchItems]);

  const visibleItems = useMemo(() => {
    return Object.values(groupedResults).flatMap((items) => items.slice(0, 5));
  }, [groupedResults]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  useEffect(() => {
    if (!open) setActiveIndex(0);
  }, [open]);

  useEffect(() => {
    if (visibleItems.length === 0) {
      setActiveIndex(0);
      return;
    }
    if (activeIndex > visibleItems.length - 1) {
      setActiveIndex(visibleItems.length - 1);
    }
  }, [activeIndex, visibleItems]);

  useEffect(() => {
    if (!open || visibleItems.length === 0) return;
    const activeItem = visibleItems[activeIndex];
    if (!activeItem) return;
    const target = panelRef.current?.querySelector<HTMLButtonElement>(
      `[data-search-id="${activeItem.id}"]`,
    );
    target?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open, visibleItems]);

  const navigateTo = (href: string) => {
    setOpen(false);
    setQuery("");
    setActiveIndex(0);
    router.push(href as never);
  };

  const retryLoadIndex = () => {
    setHasLoadedIndex(false);
    setLoadError(null);
  };

  const loadNotificationList = async () => {
    setNotificationLoading(true);
    setNotificationError(null);
    try {
      const [listResponse, unreadResponse] = await Promise.all([
        notificationApi.list(1, 8),
        notificationApi.unreadCount(),
      ]);
      setNotifications(listResponse.items);
      setUnreadCount(unreadResponse.unread_count);
    } catch {
      setNotificationError("加载失败，点击重试");
    } finally {
      setNotificationLoading(false);
    }
  };

  useEffect(() => {
    void loadNotificationList();
    // TODO: Replace polling with SSE/WebSocket push in a future iteration.
    const timer = window.setInterval(() => {
      void loadNotificationList();
    }, 20000);
    const onVisibilityChange = () => {
      if (!document.hidden) {
        void loadNotificationList();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, []);

  const handleNotificationClick = async (item: IngestionNotification) => {
    setNotificationOpen(false);
    if (!item.is_read) {
      try {
        await notificationApi.markRead([item.id]);
      } catch {
        // Best-effort: navigation should not be blocked by read-state failure.
      }
    }
    void loadNotificationList();
    router.push(item.action_url as never);
  };

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

      <div ref={panelRef} className="relative hidden w-72 lg:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          placeholder="搜索资源、Prompt、评测…"
          className="h-9 rounded-lg border-border/60 bg-muted/40 pl-9 pr-16 text-sm shadow-inner focus-visible:ring-primary/30"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" && visibleItems.length > 0) {
              event.preventDefault();
              setActiveIndex((prev) => (prev + 1) % visibleItems.length);
            }
            if (event.key === "ArrowUp" && visibleItems.length > 0) {
              event.preventDefault();
              setActiveIndex(
                (prev) => (prev - 1 + visibleItems.length) % visibleItems.length,
              );
            }
            if (event.key === "Enter" && visibleItems[activeIndex]) {
              event.preventDefault();
              navigateTo(visibleItems[activeIndex].href);
            }
            if (event.key === "Escape") {
              setOpen(false);
              inputRef.current?.blur();
            }
          }}
        />
        <kbd className="pointer-events-none absolute right-2 top-1/2 flex -translate-y-1/2 items-center gap-0.5 rounded border border-border/70 bg-background/80 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          <Command className="h-3 w-3" />K
        </kbd>
        {open && (
          <div className="absolute left-0 right-0 top-11 z-50 max-h-[26rem] overflow-y-auto rounded-xl border border-border/70 bg-popover/95 p-2 shadow-2xl backdrop-blur">
            {loading && (
              <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                加载搜索索引中...
              </div>
            )}
            {!loading && loadError && (
              <div className="px-2 py-2">
                <div className="text-xs text-muted-foreground">{loadError}</div>
                <button
                  type="button"
                  onClick={retryLoadIndex}
                  className="mt-1 text-xs text-primary hover:underline"
                >
                  重新加载
                </button>
              </div>
            )}
            {!loading && !loadError && searchItems.length === 0 && (
              <div className="px-2 py-2 text-xs text-muted-foreground">
                未找到匹配内容
              </div>
            )}
            {!loading &&
              Object.entries(groupedResults).map(([groupName, items]) => (
                <div key={groupName} className="mb-1.5 last:mb-0">
                  <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
                    {groupName}
                  </div>
                  {items.slice(0, 5).map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => navigateTo(item.href)}
                      data-search-id={item.id}
                      aria-selected={visibleItems[activeIndex]?.id === item.id}
                      onMouseEnter={() => {
                        const index = visibleItems.findIndex(
                          (visibleItem) => visibleItem.id === item.id,
                        );
                        if (index >= 0) setActiveIndex(index);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left",
                        visibleItems[activeIndex]?.id === item.id
                          ? "bg-accent"
                          : "hover:bg-accent",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{item.label}</div>
                        {item.detail && (
                          <div className="truncate text-xs text-muted-foreground">
                            {item.detail}
                          </div>
                        )}
                      </div>
                      <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              ))}
          </div>
        )}
      </div>

      <div ref={bellPanelRef} className="relative">
        <Button
          variant="ghost"
          size="icon"
          aria-label="通知"
          className="relative rounded-lg"
          onClick={() => {
            setNotificationOpen((prev) => !prev);
            if (!notificationOpen) {
              void loadNotificationList();
            }
          }}
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -right-1 -top-1 inline-flex h-5 w-5 items-center justify-center rounded-full bg-fuchsia-500 text-[10px] font-medium leading-none text-white">
              {unreadCount > 99 ? "99" : unreadCount}
            </span>
          )}
        </Button>
        {notificationOpen && (
          <div className="absolute right-0 top-10 z-50 w-96 rounded-xl border border-border/70 bg-popover/95 p-2 shadow-2xl backdrop-blur">
            <div className="mb-1 px-2 py-1 text-xs font-semibold text-foreground">入库通知</div>
            {notificationLoading && (
              <div className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                加载通知中...
              </div>
            )}
            {!notificationLoading && notificationError && (
              <div className="px-2 py-3 text-xs text-muted-foreground">
                {notificationError}
                <button
                  type="button"
                  className="ml-2 text-primary hover:underline"
                  onClick={() => void loadNotificationList()}
                >
                  重试
                </button>
              </div>
            )}
            {!notificationLoading && !notificationError && notifications.length === 0 && (
              <div className="px-2 py-6 text-center text-xs text-muted-foreground">暂无通知</div>
            )}
            {!notificationLoading && !notificationError && notifications.length > 0 && (
              <div className="max-h-80 space-y-1 overflow-y-auto">
                {notifications.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => void handleNotificationClick(item)}
                    className={cn(
                      "w-full rounded-md px-2 py-2 text-left hover:bg-accent",
                      !item.is_read && "bg-primary/5",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-medium">{item.title}</span>
                      <span className="shrink-0 text-[10px] text-muted-foreground">
                        {formatNotificationTime(item.created_at)}
                      </span>
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{item.message}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

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
