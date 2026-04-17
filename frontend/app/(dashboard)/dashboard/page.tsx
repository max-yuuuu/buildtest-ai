import { auth } from "@/lib/auth";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default async function DashboardPage() {
  const session = await auth();
  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">
          欢迎,{session?.user?.name ?? session?.user?.email ?? "用户"}
        </h1>
        <p className="text-sm text-muted-foreground">
          从左侧菜单开始配置 Provider 和知识库
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Provider</CardTitle>
            <CardDescription>配置 LLM / Embedding 服务商</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            前往「Provider」页面管理
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>知识库</CardTitle>
            <CardDescription>文档上传、切片、向量化</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Phase 1 开发中
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>评测</CardTitle>
            <CardDescription>Dataset × Prompt × Model</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Phase 2 规划中
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
