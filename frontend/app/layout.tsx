import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NativePlanning — 本地生活活动规划",
  description: "一句话生成可执行本地生活计划",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">
        {children}
      </body>
    </html>
  );
}
