"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetchAPI, type AnalysisItem, type MarketWireItem, type NewsItem, type AlertItem } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Newspaper, Zap, BarChart3, TrendingUp, TrendingDown, Minus, AlertTriangle, X, Database } from "lucide-react";
import { LiveProgressPanel } from "@/components/live-progress-panel";

const fetcher = async (url: string) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Request failed with status ${r.status}`);
  return r.json();
};

export default function DashboardPage() {
  const { data: newsData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/news?limit=5`,
    fetcher
  );
  const { data: marketWireData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/market-wire?limit=10`,
    fetcher
  );
  const { data: analysisData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analysis?limit=10`,
    fetcher
  );
  const { data: alertsData } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/alerts`,
    fetcher
  );
  const { data: briefingData, error: briefingError } = useSWR(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/briefings/latest`,
    fetcher
  );

  const [dismissedAlerts, setDismissedAlerts] = useState<string[]>([]);
  const [briefingLang, setBriefingLang] = useState<"en" | "zh">("en");

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/analysis/search?q=${encodeURIComponent(searchQuery)}`);
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      setSearchResults(data.results ?? []);
    } catch (err: any) {
      setSearchError(err.message || "Failed to query semantic search.");
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    setSearchError(null);
  };

  const news: NewsItem[] = newsData?.items ?? [];
  const marketWires: MarketWireItem[] = marketWireData?.items ?? [];
  const analysis: AnalysisItem[] = analysisData?.items ?? [];
  const alerts: AlertItem[] = alertsData?.alerts ?? [];

  const activeAlerts = alerts.filter((a) => !dismissedAlerts.includes(a.id));

  const positiveCount = analysis.filter((a) => a.sentiment === "positive").length;
  const negativeCount = analysis.filter((a) => a.sentiment === "negative").length;
  const neutralCount = analysis.filter((a) => a.sentiment === "neutral").length;

  return (
    <div className="space-y-6">
      {activeAlerts.length > 0 && (
        <div className="space-y-3">
          {activeAlerts.map((alert) => (
            <div
              key={alert.id}
              className="relative flex gap-4 p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-900 dark:text-red-200 transition-all duration-300"
            >
              <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
              <div className="flex-1 pr-8">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-bold text-sm text-red-600 dark:text-red-400">
                    EMERGENCY ALERT / 紧急警报:
                  </span>
                  <Badge variant="destructive" className="font-mono text-xs uppercase tracking-wide">
                    {alert.subject_name}
                  </Badge>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-500/10 text-red-500">
                    {alert.dimension_name}
                  </span>
                </div>
                <div className="mt-2 text-sm space-y-1">
                  <p className="font-medium">{alert.recent_fact || alert.summary_en}</p>
                  {alert.recent_fact_zh && (
                    <p className="text-xs text-muted-foreground dark:text-red-300/70 border-t border-red-500/10 pt-1 mt-1">
                      {alert.recent_fact_zh}
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setDismissedAlerts([...dismissedAlerts, alert.id])}
                aria-label={`dismiss-alert-${alert.id}`}
                className="absolute top-4 right-4 p-1 rounded-md hover:bg-red-500/10 text-red-500/70 hover:text-red-500 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      <LiveProgressPanel />

      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Market intelligence overview</p>
      </div>

      {/* Semantic Search Component */}
      <Card className="border border-border/80 bg-card/65 shadow-sm backdrop-blur-sm p-4">
        <form onSubmit={handleSearch} className="flex gap-2.5">
          <div className="relative flex-1">
            <input
              type="text"
              placeholder="Search news & insights semantically..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
            {searchResults !== null && (
              <button
                type="button"
                onClick={handleClearSearch}
                aria-label="clear-search"
                className="absolute right-3 top-2.5 text-muted-foreground hover:text-foreground text-xs font-semibold cursor-pointer"
              >
                Clear / 清除
              </button>
            )}
          </div>
          <button
            type="submit"
            aria-label="search-submit"
            disabled={isSearching}
            className="inline-flex items-center justify-center rounded-md text-sm font-semibold h-10 px-4 py-2 bg-primary text-primary-foreground shadow hover:bg-primary/95 transition-all disabled:opacity-50 cursor-pointer"
          >
            {isSearching ? "Searching..." : "Search / 搜索"}
          </button>
        </form>

        {searchError && (
          <p className="text-xs text-red-500 mt-2">{searchError}</p>
        )}

        {searchResults !== null && (
          <div className="mt-4 border-t border-border/50 pt-4 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Semantic Search Results ({searchResults.length})
            </h3>
            {searchResults.length === 0 ? (
              <p className="text-sm text-muted-foreground py-2 italic">No matches found.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {searchResults.map((result) => {
                  const scorePercentage = Math.round(result.score * 100);
                  const isInsight = result.payload.type === "insight";
                  return (
                    <div
                      key={result.id}
                      className="p-3 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/40 transition-colors flex gap-3 items-start"
                    >
                      <div className="mt-0.5 shrink-0">
                        {isInsight ? (
                          <Database className="h-4 w-4 text-indigo-500" />
                        ) : (
                          <Newspaper className="h-4 w-4 text-emerald-500" />
                        )}
                      </div>
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          {isInsight ? (
                            <>
                              <span className="font-semibold text-xs text-indigo-600 dark:text-indigo-400">
                                INSIGHT
                              </span>
                              <Badge variant="outline" className="text-[10px] font-mono py-0 px-1.5">
                                {result.payload.subject}
                              </Badge>
                              <span className="text-[10px] font-semibold text-muted-foreground">
                                {result.payload.dimension_name}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="font-semibold text-xs text-emerald-600 dark:text-emerald-400">
                                ARTICLE
                              </span>
                              <Badge variant="outline" className="text-[10px] py-0 px-1.5">
                                {result.payload.source_name}
                              </Badge>
                              {result.payload.published_at && (
                                <span className="text-[10px] text-muted-foreground">
                                  {new Date(result.payload.published_at).toLocaleDateString()}
                                </span>
                              )}
                            </>
                          )}
                          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-primary/10 text-primary ml-auto shrink-0">
                            {scorePercentage}% match
                          </span>
                        </div>
                        {isInsight ? (
                          <div className="text-sm space-y-1.5">
                            <p className="font-medium text-foreground/95">{result.payload.summary_en}</p>
                            {result.payload.summary_zh && (
                              <p className="text-xs text-muted-foreground border-t border-border/40 pt-1 mt-1">
                                {result.payload.summary_zh}
                              </p>
                            )}
                          </div>
                        ) : (
                          <p className="font-medium text-sm text-foreground/95 leading-normal">
                            {result.payload.title}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* Daily Briefing Widget */}
      <Card className="border border-border/80 bg-card/65 shadow-md backdrop-blur-sm overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-3">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg font-semibold tracking-tight">Daily Briefing / 每日简报</CardTitle>
          </div>
          {briefingData && (
            <div className="flex items-center gap-1.5 p-0.5 rounded-lg border border-border/60 bg-muted/30">
              <button
                onClick={() => setBriefingLang("en")}
                aria-label="switch-lang-en"
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  briefingLang === "en"
                    ? "bg-background text-foreground shadow-sm font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                English
              </button>
              <button
                onClick={() => setBriefingLang("zh")}
                aria-label="switch-lang-zh"
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                  briefingLang === "zh"
                    ? "bg-background text-foreground shadow-sm font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                中文
              </button>
            </div>
          )}
        </CardHeader>
        <CardContent className="p-5">
          {briefingError || !briefingData || !briefingData.summary_en ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No daily briefing available yet.
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-5">
              <div className="md:col-span-3 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-primary/80">
                  {briefingLang === "en" ? "Summary Overview" : "综述概览"}
                </h3>
                <p className="text-sm leading-relaxed font-normal text-foreground/90 bg-muted/15 p-4 rounded-xl border border-border/20">
                  {briefingLang === "en" ? briefingData.summary_en : briefingData.summary_zh}
                </p>
                <p className="text-[10px] text-muted-foreground/80 mt-2 font-mono">
                  {briefingLang === "en" ? "Generated at" : "生成时间"}: {new Date(briefingData.generated_at).toLocaleString()}
                </p>
              </div>
              <div className="md:col-span-2 space-y-3 border-t md:border-t-0 md:border-l border-border/60 pt-4 md:pt-0 md:pl-6">
                <h3 className="text-xs font-bold uppercase tracking-wider text-primary/80">
                  {briefingLang === "en" ? "Key Takeaways" : "核心要点"}
                </h3>
                <ul className="space-y-2.5">
                  {(briefingLang === "en" ? briefingData.key_takeaways_en : briefingData.key_takeaways_zh)?.map((item: string, idx: number) => (
                    <li key={idx} className="flex gap-2.5 items-start text-sm text-foreground/85">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary text-[10px] font-bold mt-0.5">
                        {idx + 1}
                      </span>
                      <span className="leading-snug">{item}</span>
                    </li>
                  ))}
                  {!(briefingLang === "en" ? briefingData.key_takeaways_en : briefingData.key_takeaways_zh)?.length && (
                    <li className="text-xs text-muted-foreground italic">
                      {briefingLang === "en" ? "No takeaways generated." : "暂无核心要点。"}
                    </li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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
            <CardTitle className="text-sm font-medium">Market Wire</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{marketWireData?.total ?? 0}</div>
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
            <CardTitle>Market Wire / 快讯</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {marketWires.map((item) => (
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
            {marketWires.length === 0 && (
              <p className="text-sm text-muted-foreground py-4 text-center">
                No market wires yet.
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