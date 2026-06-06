"use client";

import useSWR from "swr";
import { fetchAPI, type AnalysisItem, type FlashItem, type NewsItem } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Newspaper, Zap, BarChart3, TrendingUp, TrendingDown, Minus } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function DashboardPage() {
  const { data: newsData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/news?limit=5`,
    fetcher
  );
  const { data: flashData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/flash?limit=10`,
    fetcher
  );
  const { data: analysisData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analysis?limit=10`,
    fetcher
  );

  const news: NewsItem[] = newsData?.items ?? [];
  const flash: FlashItem[] = flashData?.items ?? [];
  const analysis: AnalysisItem[] = analysisData?.items ?? [];

  const positiveCount = analysis.filter((a) => a.sentiment === "positive").length;
  const negativeCount = analysis.filter((a) => a.sentiment === "negative").length;
  const neutralCount = analysis.filter((a) => a.sentiment === "neutral").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Market intelligence overview</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total News</CardTitle>
            <Newspaper className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{newsData?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Flash News</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{flashData?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Analyzed</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{analysisData?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentiment</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 text-sm">
              <span className="text-green-600">{positiveCount} positive</span>
              <span className="text-red-600">{negativeCount} negative</span>
              <span className="text-gray-500">{neutralCount} neutral</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Latest News</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {news.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-lg border p-3 hover:bg-accent transition-colors"
              >
                <p className="font-medium text-sm line-clamp-2">{item.title}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="text-xs">{item.source_name}</Badge>
                  <span className="text-xs text-muted-foreground">{item.language.toUpperCase()}</span>
                </div>
              </a>
            ))}
            {news.length === 0 && (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No news yet. Start the ingestion pipeline.
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Flash News / 快讯</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {flash.map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <p className="text-sm">{item.content}</p>
                <div className="flex items-center gap-2 mt-1">
                  {item.related_symbols?.map((s) => (
                    <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
                  ))}
                  {item.importance > 0 && (
                    <Badge variant={item.importance >= 3 ? "destructive" : "default"} className="text-xs">
                      ★ {item.importance}
                    </Badge>
                  )}
                </div>
              </div>
            ))}
            {flash.length === 0 && (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No flash news yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sentiment Overview / 情绪概览</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            {analysis.slice(0, 9).map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <div className="flex items-center justify-between mb-1">
                  <Badge variant={
                    item.sentiment === "positive" ? "default" :
                    item.sentiment === "negative" ? "destructive" : "secondary"
                  }>
                    {item.sentiment}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {(item.sentiment_score ?? 0).toFixed(2)}
                  </span>
                </div>
                <p className="text-sm line-clamp-2">{item.summary_en || "No summary"}</p>
                {item.summary_zh && (
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{item.summary_zh}</p>
                )}
                <div className="flex flex-wrap gap-1 mt-2">
                  {item.topics?.slice(0, 3).map((t) => (
                    <Badge key={t} variant="outline" className="text-xs">{t}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {analysis.length === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No analysis yet. Start the analysis pipeline.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}