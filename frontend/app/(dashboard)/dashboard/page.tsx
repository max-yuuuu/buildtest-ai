import Link from "next/link";
import { ArrowUpRight, Database, FlaskConical, KeyRound } from "lucide-react";
import { auth } from "@/lib/auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const stats = [
  {
    label: "Provider",
    value: "—",
    hint: "待接入",
    icon: KeyRound,
  },
  {
    label: "知识库",
    value: "—",
    hint: "Phase 1",
    icon: Database,
  },
  {
    label: "评测任务",
    value: "—",
    hint: "Phase 2",
    icon: FlaskConical,
  },
];

const modules = [
  {
    title: "Provider",
    description: "配置 LLM / Embedding 服务商",
    body: "前往「Provider」页面管理",
    href: "/providers",
    cta: "去配置",
    badge: "可用",
    tone: "default" as const,
  },
  {
    title: "知识库",
    description: "文档上传、切片、向量化",
    body: "Phase 1 开发中",
    href: "/knowledge-bases",
    cta: "预览",
    badge: "开发中",
    tone: "secondary" as const,
  },
  {
    title: "评测",
    description: "Dataset × Prompt × Model",
    body: "Phase 2 规划中",
    href: "#",
    cta: "敬请期待",
    badge: "规划中",
    tone: "outline" as const,
  },
];

export default async function DashboardPage() {
  const session = await auth();
  const displayName =
    session?.user?.name ?? session?.user?.email ?? "用户";

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold tracking-tight">
          欢迎,{displayName}
        </h2>
        <p className="text-sm text-muted-foreground">
          从下方入口开始配置 Provider、构建知识库并准备评测流程。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.label}
                </CardTitle>
                <Icon className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent className="space-y-1">
                <div className="text-3xl font-semibold tracking-tight">
                  {stat.value}
                </div>
                <p className="text-xs text-muted-foreground">{stat.hint}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {modules.map((m) => (
          <Card key={m.title} className="flex flex-col">
            <CardHeader className="space-y-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{m.title}</CardTitle>
                <Badge variant={m.tone}>{m.badge}</Badge>
              </div>
              <CardDescription>{m.description}</CardDescription>
            </CardHeader>
            <CardContent className="flex-1 text-sm text-muted-foreground">
              {m.body}
            </CardContent>
            <CardContent className="pt-0">
              <Button
                asChild
                variant="ghost"
                size="sm"
                className="px-0 text-sm font-medium text-primary hover:bg-transparent hover:underline"
              >
                <Link href={m.href as never}>
                  {m.cta}
                  <ArrowUpRight className="ml-1 h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">快速上手</CardTitle>
          <CardDescription>
            按顺序完成下面三步,即可运行第一次评测。
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm md:grid-cols-3">
          {[
            { step: "01", title: "配置 Provider", desc: "绑定 OpenAI / Anthropic 等服务商" },
            { step: "02", title: "创建知识库", desc: "上传文档,完成切片与向量化" },
            { step: "03", title: "运行评测", desc: "绑定 Dataset × Prompt × Model" },
          ].map((s) => (
            <div
              key={s.step}
              className="rounded-md border bg-muted/30 p-4"
            >
              <div className="text-xs font-semibold text-muted-foreground">
                STEP {s.step}
              </div>
              <div className="mt-1 text-sm font-medium">{s.title}</div>
              <div className="mt-1 text-xs text-muted-foreground">{s.desc}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
