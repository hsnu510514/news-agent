"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Database, TrendingUp, TrendingDown, Minus, Clock, Globe } from "lucide-react";
import { getUrgencyBadge, type InsightItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = async (url: string) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Request failed with status ${r.status}`);
  return r.json();
};

export default function InsightsPage() {
  const { data, error } = useSWR(`${API}/api/insights`, fetcher);
  const items: InsightItem[] = data?.items ?? [];

  const [expandedInsights, setExpandedInsights] = useState<string[]>([]);
  const [briefingLang, setBriefingLang] = useState<"en" | "zh">("en");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const toggleExpand = (id: string) => {
    if (expandedInsights.includes(id)) {
      setExpandedInsights(expandedInsights.filter((x) => x !== id));
    } else {
      setExpandedInsights([...expandedInsights, id]);
    }
  };

  const filteredItems = items.filter((item) => {
    // Subject Type filter
    if (typeFilter && item.subject.type !== typeFilter) return false;
    // Subject Name / Dimension search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const nameMatch = item.subject.name.toLowerCase().includes(q);
      const dimMatch = item.dimension_name.toLowerCase().includes(q);
      const tagMatch = item.tags?.some((t) => t.toLowerCase().includes(q)) ?? false;
      return nameMatch || dimMatch || tagMatch;
    }
    return true;
  });

  const getSentimentBadge = (sentiment: string) => {
    switch (sentiment) {
      case "positive":
        return (
          <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 gap-1 text-[10px]">
            <TrendingUp className="h-3 w-3" /> Positive
          </Badge>
        );
      case "negative":
        return (
          <Badge variant="destructive" className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20 gap-1 text-[10px]">
            <TrendingDown className="h-3 w-3" /> Negative
          </Badge>
        );
      case "mixed":
        return (
          <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 gap-1 text-[10px]">
            <TrendingUp className="h-3 w-3" /> Mixed
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="bg-muted text-muted-foreground gap-1 text-[10px]">
            <Minus className="h-3 w-3" /> Neutral
          </Badge>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6 text-primary fill-primary/10" /> Insight Vault / 见解库
          </h1>
          <p className="text-muted-foreground">AI-synthesized research subjects and narrative dimensions</p>
        </div>

        <div className="flex flex-wrap gap-3 items-center">
          <Input
            placeholder="Search subjects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-[200px] h-9 text-xs"
          />
          <select
            value={typeFilter}
            aria-label="filter-type"
            onChange={(e) => setTypeFilter(e.target.value)}
            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
          >
            <option value="">All Types</option>
            <option value="ticker">Ticker / 股票代码</option>
            <option value="macro">Macro / 宏观</option>
            <option value="theme">Theme / 主题</option>
          </select>

          {items.length > 0 && (
            <div className="flex items-center gap-1 p-0.5 rounded-lg border border-border bg-muted/40 h-9">
              <button
                onClick={() => setBriefingLang("en")}
                aria-label="switch-lang-en"
                className={`px-2.5 py-1 text-[10px] font-semibold rounded-md transition-all cursor-pointer ${
                  briefingLang === "en"
                    ? "bg-background text-foreground shadow-sm font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                EN
              </button>
              <button
                onClick={() => setBriefingLang("zh")}
                aria-label="switch-lang-zh"
                className={`px-2.5 py-1 text-[10px] font-semibold rounded-md transition-all cursor-pointer ${
                  briefingLang === "zh"
                    ? "bg-background text-foreground shadow-sm font-bold"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                中
              </button>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm">
          Failed to load insights. Please ensure the backend FastAPI service is running.
        </div>
      )}

      <div className="space-y-4">
        {filteredItems.map((item) => {
          const isExpanded = expandedInsights.includes(item.id);
          const urgencyInfo = getUrgencyBadge(item.urgency);
          return (
            <Card key={item.id} className="border border-border/80 bg-card/65 shadow-sm overflow-hidden">
              <div className="p-4 flex flex-col sm:flex-row sm:items-start justify-between gap-3 border-b border-border/40">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-base tracking-tight text-foreground">
                      {item.subject.name}
                    </span>
                    <Badge variant="outline" className="text-[10px] font-mono capitalize px-1.5 py-0 bg-primary/[0.03]">
                      {item.subject.type}
                    </Badge>
                    {item.subject.tags?.map((t) => (
                      <Badge key={t} variant="secondary" className="text-[9px] px-1 py-0 bg-muted/60">
                        {t}
                      </Badge>
                    ))}
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center gap-2">
                    <span className="font-semibold text-primary/85">{item.dimension_name}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1 font-mono text-[10px]">
                      <Clock className="h-3 w-3" /> Updated: {new Date(item.last_updated_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2.5 shrink-0 self-end sm:self-start">
                  {getSentimentBadge(item.sentiment)}
                  <Badge variant={urgencyInfo.variant} className="text-[10px]">
                    {urgencyInfo.label}
                  </Badge>
                  <button
                    onClick={() => toggleExpand(item.id)}
                    aria-label={`expand-insight-${item.id}`}
                    className="inline-flex items-center justify-center rounded-md border border-input bg-background h-8 px-3 text-xs font-semibold hover:bg-accent transition-colors shadow-sm cursor-pointer ml-1"
                  >
                    {isExpanded ? "Hide Facts / 隐藏" : "Show Facts / 展开要点"}
                  </button>
                </div>
              </div>

              <CardContent className="p-4 space-y-4">
                <p className="text-sm leading-relaxed text-foreground/90 font-medium bg-muted/[0.08] p-3 rounded-lg border border-border/20">
                  {briefingLang === "en" ? item.summary_en : item.summary_zh}
                </p>

                {isExpanded && (
                  <div className="space-y-3 pt-3 border-t border-border/40 transition-all duration-300">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-primary/80">
                      {briefingLang === "en" ? "Supporting Facts Timeline" : "支撑事实时间线"}
                    </h4>
                    {item.facts && item.facts.length > 0 ? (
                      <div className="space-y-3">
                        {item.facts.map((fact) => (
                          <div
                            key={fact.id}
                            className="text-xs flex gap-3 items-start p-2.5 rounded bg-muted/20 border border-border/30 hover:border-border/60 transition-colors"
                          >
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-mono text-[9px] font-bold mt-0.5">
                              •
                            </span>
                            <div className="flex-1 space-y-1.5">
                              <p className="text-foreground/85 leading-relaxed font-normal">
                                {briefingLang === "en" ? fact.bullet_text_en : fact.bullet_text_zh}
                              </p>
                              {fact.source_article && (
                                <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-muted-foreground/95">
                                  <span className="flex items-center gap-0.5"><Globe className="h-3 w-3" /> Source:</span>
                                  <a
                                    href={fact.source_article.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    aria-label={fact.source_article.source_name}
                                    className="font-semibold text-primary hover:underline"
                                  >
                                    {fact.source_article.source_name}
                                  </a>
                                  <span>—</span>
                                  <span className="italic truncate max-w-sm" title={fact.source_article.title}>
                                    {briefingLang === "en" ? fact.source_article.title : (fact.source_article.title_zh || fact.source_article.title)}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-muted-foreground italic pl-2">
                        {briefingLang === "en" ? "No supporting facts in this dimension yet." : "目前该维度暂无支撑事实。"}
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}

        {filteredItems.length === 0 && !error && (
          <div className="py-16 text-center text-muted-foreground border border-dashed rounded-lg">
            No insights found matching your search criteria.
          </div>
        )}
      </div>
    </div>
  );
}
