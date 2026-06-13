"use client";

import useSWR from "swr";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { X, ExternalLink, Globe, Clock, ShieldAlert, Award } from "lucide-react";
import type { NewsItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function NewsPage() {
  const [language, setLanguage] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [urgency, setUrgency] = useState<string>("");
  const [isAnalyzed, setIsAnalyzed] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [selectedNews, setSelectedNews] = useState<NewsItem | null>(null);
  const limit = 20;

  const params = new URLSearchParams();
  if (language) params.set("language", language);
  if (source) params.set("source_type", source);
  if (urgency) params.set("urgency", urgency);
  if (isAnalyzed) params.set("is_analyzed", isAnalyzed);
  if (search) params.set("search", search);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const { data } = useSWR(`${API}/api/news?${params.toString()}`, fetcher);
  const news: NewsItem[] = data?.items ?? [];
  const total = data?.total ?? 0;

  const getSentimentBadge = (sentiment: string | null) => {
    if (!sentiment) return null;
    switch (sentiment) {
      case "positive":
        return (
          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 font-mono text-[10px]">
            Positive
          </Badge>
        );
      case "negative":
        return (
          <Badge variant="destructive" className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20 font-mono text-[10px]">
            Negative
          </Badge>
        );
      case "mixed":
        return (
          <Badge variant="outline" className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 font-mono text-[10px]">
            Mixed
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="bg-muted text-muted-foreground font-mono text-[10px]">
            Neutral
          </Badge>
        );
    }
  };

  const getUrgencyBadgeLocal = (urgency: string | null) => {
    if (!urgency) return null;
    switch (urgency) {
      case "flash":
        return (
          <Badge variant="destructive" className="bg-red-500/10 text-red-500 hover:bg-red-500/20 border-red-500/20 font-mono text-[10px]">
            7x24
          </Badge>
        );
      case "high":
        return (
          <Badge variant="outline" className="bg-orange-500/10 text-orange-500 hover:bg-orange-500/20 border-orange-500/20 font-mono text-[10px]">
            High
          </Badge>
        );
      case "medium":
        return (
          <Badge variant="outline" className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20 font-mono text-[10px]">
            Medium
          </Badge>
        );
      default:
        return (
          <Badge variant="outline" className="text-muted-foreground font-mono text-[10px]">
            Low
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6 relative">
      <div>
        <h1 className="text-2xl font-bold">News Feed / 新闻</h1>
        <p className="text-muted-foreground">{total} articles total</p>
      </div>

      <div className="flex flex-col gap-4">
        {/* Source Tabs */}
        <div role="tablist" className="flex gap-2 p-1 bg-muted rounded-lg w-fit">
          {[
            { label: "All Sources", value: "" },
            { label: "RSS", value: "rss" },
            { label: "NewsAPI", value: "newsapi" },
            { label: "Collector Ingest", value: "collector" }
          ].map((tab) => (
            <button
              key={tab.value}
              role="tab"
              aria-selected={source === tab.value}
              onClick={() => { setSource(tab.value); setOffset(0); }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                source === tab.value
                  ? "bg-background text-foreground shadow-xs font-bold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Filter Controls */}
        <div className="flex flex-wrap gap-3">
          <Input
            placeholder="Search news..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            className="max-w-xs"
          />
          <select
            value={language}
            onChange={(e) => { setLanguage(e.target.value); setOffset(0); }}
            className="rounded-md border px-3 py-2 text-sm bg-background border-input shadow-xs focus-visible:outline-hidden"
          >
            <option value="">All Languages</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
          <select
            value={isAnalyzed}
            aria-label="Filter Status"
            onChange={(e) => { setIsAnalyzed(e.target.value); setOffset(0); }}
            className="rounded-md border px-3 py-2 text-sm bg-background border-input shadow-xs focus-visible:outline-hidden"
          >
            <option value="">All Statuses</option>
            <option value="true">Analyzed</option>
            <option value="false">Pending</option>
          </select>
          <select
            value={urgency}
            aria-label="Filter Urgency"
            onChange={(e) => { setUrgency(e.target.value); setOffset(0); }}
            className="rounded-md border px-3 py-2 text-sm bg-background border-input shadow-xs focus-visible:outline-hidden"
          >
            <option value="">All Urgencies</option>
            <option value="flash">7x24 / Flash</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div className="border rounded-md overflow-hidden bg-card shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[46%]">Title / 标题</TableHead>
              <TableHead className="w-[8%]">Source / 来源</TableHead>
              <TableHead className="w-[12%]">Pub / 发布时间</TableHead>
              <TableHead className="w-[12%]">Fetch / 抓取时间</TableHead>
              <TableHead className="w-[14%]">Analytics / 见解</TableHead>
              <TableHead className="w-[8%]">Status / 状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {news.map((item) => (
              <TableRow 
                key={item.id} 
                className="cursor-pointer hover:bg-muted/50 transition-colors"
                onClick={() => setSelectedNews(item)}
              >
                <TableCell className="font-medium max-w-[400px] truncate">
                  <a 
                    href={item.url} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="hover:underline block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {item.title}
                  </a>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{item.source_name}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground text-xs">
                  {item.published_at ? new Date(item.published_at).toLocaleString() : "N/A"}
                </TableCell>
                <TableCell className="text-muted-foreground text-xs">
                  {item.fetched_at ? new Date(item.fetched_at).toLocaleString() : "N/A"}
                </TableCell>
                <TableCell>
                  <div className="flex gap-1.5 flex-wrap">
                    {item.analysis ? (
                      <>
                        {getUrgencyBadgeLocal(item.analysis.urgency)}
                        {getSentimentBadge(item.analysis.sentiment)}
                      </>
                    ) : (
                      <span className="text-xs text-muted-foreground italic">Pending analysis</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  {item.analysis ? (
                    <Badge variant="default" className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20">
                      Analyzed
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      Pending
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {news.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No news articles found. Start the ingestion pipeline to fetch news.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {total > limit && (
        <div className="flex justify-center gap-3">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-4 py-2 rounded-md border text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-4 py-2 text-sm text-muted-foreground">
            {offset + 1} - {Math.min(offset + limit, total)} of {total}
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={offset + limit >= total}
            className="px-4 py-2 rounded-md border text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Side Drawer Details Sheet */}
      {selectedNews && (
        <div 
          className="fixed inset-0 z-50 flex justify-end bg-black/55 backdrop-blur-xs transition-opacity"
          onClick={() => setSelectedNews(null)}
        >
          <div 
            className="w-full max-w-lg bg-background h-full shadow-2xl p-6 overflow-y-auto flex flex-col justify-between border-l border-border animate-in slide-in-from-right duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-6">
              {/* Header */}
              <div className="flex items-center justify-between border-b pb-4">
                <h2 className="text-lg font-bold">News Details / 新闻详情</h2>
                <button 
                  onClick={() => setSelectedNews(null)}
                  className="rounded-md p-1 hover:bg-muted transition-colors cursor-pointer"
                  aria-label="Close Details"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Title Section */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Original Title / 原标题</span>
                <h3 className="text-base font-bold leading-snug">{selectedNews.title}</h3>
                
                {selectedNews.title_zh && (
                  <div className="space-y-1 pt-2 border-t border-dashed border-border/60">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Translated Title / 中文标题</span>
                    <h4 className="text-base font-bold text-primary leading-snug">{selectedNews.title_zh}</h4>
                  </div>
                )}
              </div>

              <Separator />

              {/* Meta Info */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Source / 来源</span>
                  <div className="font-semibold flex items-center gap-1.5">
                    <Globe className="h-4 w-4 text-muted-foreground" />
                    {selectedNews.source_name}
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Date / 发布与抓取时间</span>
                  <div className="space-y-1">
                    <div className="font-semibold flex items-center gap-1.5 text-xs text-foreground">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span>Pub: {selectedNews.published_at ? new Date(selectedNews.published_at).toLocaleString() : "N/A"}</span>
                    </div>
                    <div className="font-semibold flex items-center gap-1.5 text-xs text-foreground pl-[22px]">
                      <span>Fetch: {selectedNews.fetched_at ? new Date(selectedNews.fetched_at).toLocaleString() : "N/A"}</span>
                    </div>
                  </div>
                </div>
              </div>

              <Separator />

              {/* Summary / Analysis Result */}
              {selectedNews.analysis ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">Urgency / 紧急度</span>
                      <div>
                        <Badge variant="outline" className="capitalize font-mono">
                          {selectedNews.analysis.urgency || "medium"}
                        </Badge>
                      </div>
                    </div>
                    <div className="space-y-1">
                      <span className="text-xs text-muted-foreground">Sentiment / 情绪倾向</span>
                      <div>
                        <Badge variant="outline" className="capitalize font-mono">
                          {selectedNews.analysis.sentiment || "neutral"}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  {/* Topics and Companies Tags */}
                  <div className="space-y-3">
                    {selectedNews.analysis.topics && selectedNews.analysis.topics.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-xs text-muted-foreground block">Topics / 主题</span>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedNews.analysis.topics.map((t) => (
                            <button
                              key={t}
                              aria-label={`filter-tag-${t}`}
                              onClick={() => {
                                setSearch(t);
                                setOffset(0);
                                setSelectedNews(null);
                              }}
                              className="inline-flex items-center rounded-md border border-border bg-background px-2.5 py-1 text-xs font-semibold hover:bg-accent transition-colors shadow-xs cursor-pointer"
                            >
                              {t}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedNews.analysis.companies_mentioned && selectedNews.analysis.companies_mentioned.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-xs text-muted-foreground block">Companies / 相关公司</span>
                        <div className="flex flex-wrap gap-1.5">
                          {selectedNews.analysis.companies_mentioned.map((c) => (
                            <button
                              key={c}
                              aria-label={`filter-tag-${c}`}
                              onClick={() => {
                                setSearch(c);
                                setOffset(0);
                                setSelectedNews(null);
                              }}
                              className="inline-flex items-center rounded-md border border-border bg-background px-2.5 py-1 text-xs font-semibold hover:bg-accent transition-colors shadow-xs cursor-pointer"
                            >
                              {c}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 pt-2">
                    <div className="space-y-1 p-3 rounded-lg border bg-muted/20">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">English Summary / 英文总结</span>
                      <p className="text-sm leading-relaxed text-foreground/90 font-medium">
                        {selectedNews.analysis.summary_en || selectedNews.title}
                      </p>
                    </div>

                    <div className="space-y-1 p-3 rounded-lg border bg-muted/20">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">Chinese Summary / 中文总结</span>
                      <p className="text-sm leading-relaxed text-foreground/90 font-medium">
                        {selectedNews.analysis.summary_zh || selectedNews.title_zh || "暂无中文总结。"}
                      </p>
                    </div>

                    {selectedNews.analysis.impact_assessment && (
                      <div className="space-y-1 p-3 rounded-lg border bg-muted/20">
                        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider block mb-1">Market Impact / 市场影响评估</span>
                        <p className="text-sm leading-relaxed text-foreground/90 font-medium">
                          {selectedNews.analysis.impact_assessment}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center border border-dashed rounded-lg bg-muted/10 text-muted-foreground space-y-2">
                  <ShieldAlert className="h-8 w-8 mx-auto text-muted-foreground/60" />
                  <p className="text-sm font-medium">No analysis summary available yet.</p>
                  <p className="text-xs">Run the AI analysis pipeline to process this article.</p>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="border-t pt-4 mt-6">
              <a 
                href={selectedNews.url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-1.5 rounded-md bg-primary hover:bg-primary/95 text-primary-foreground font-semibold px-4 py-2.5 text-sm transition-colors shadow-xs cursor-pointer"
              >
                <ExternalLink className="h-4 w-4" />
                Open Source / 打开链接
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}