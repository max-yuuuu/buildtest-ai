import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  experimental: {
    /** typedRoutes 与 Turbopack 互斥（Next 15.0），已关闭以默认启用 Turbopack */
    /** 按需编译时减少 lucide 子路径爆炸，缓解 dev 首跳慢 */
    optimizePackageImports: ["lucide-react"],
  },
  output: "standalone",
};

export default nextConfig;
