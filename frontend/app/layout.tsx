import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BuildTest AI",
  description: "RAG/Agent 开发 + 评测 + 迭代一体化平台",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
