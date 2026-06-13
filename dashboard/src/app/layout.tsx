import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { UnconfiguredModelBanner } from "@/components/unconfigured-model-banner";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NewsAgent - AI Investment Research",
  description: "AI-powered investment research agent",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="flex h-screen">
          <Sidebar />
          <main className="flex-1 overflow-auto p-6 bg-background">
            <UnconfiguredModelBanner />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}