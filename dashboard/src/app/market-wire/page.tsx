"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Zap } from "lucide-react";
import type { MarketWireItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = async (url: string) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Request failed with status ${r.status}`);
  return r.json();
};

export default function MarketWirePage() {
  const { data, error } = useSWR(`${API}/api/market-wire?limit=100`, fetcher);
  const items: MarketWireItem[] = data?.items ?? [];

  const [languageFilter, setLanguageFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredItems = items.filter((item) => {
    // Language filter
    if (languageFilter && item.language !== languageFilter) return false;
    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const contentMatch = item.content.toLowerCase().includes(q);
      const symbolMatch = item.related_symbols?.some((s) => s.toLowerCase().includes(q)) ?? false;
      return contentMatch || symbolMatch;
    }
    return true;
  });

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Zap className="h-6 w-6 text-primary fill-primary/10" /> Market Wire / 快讯
          </h1>
          <p className="text-muted-foreground">Real-time market updates streamed directly from wire feeds</p>
        </div>

        <div className="flex gap-3 items-center">
          <Input
            placeholder="Search market wires..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-xs h-9 text-xs"
          />
          <select
            value={languageFilter}
            aria-label="filter-language"
            onChange={(e) => setLanguageFilter(e.target.value)}
            className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer"
          >
            <option value="">All Languages</option>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm">
          Failed to load market wires. Please ensure the backend is running.
        </div>
      )}

      <div className="space-y-3">
        {filteredItems.map((item) => (
          <Card
            key={item.id}
            className={`transition-all duration-200 border-border/60 hover:border-border ${
              item.importance >= 3
                ? "border-red-400 bg-red-500/[0.02] dark:border-red-950 dark:bg-red-950/[0.05]"
                : "bg-card/50"
            }`}
          >
            <CardContent className="p-4 flex items-start gap-4">
              <div className="flex-1 space-y-2.5">
                <p className="text-sm font-normal leading-relaxed text-foreground/90">{item.content}</p>
                
                <div className="flex items-center gap-2 flex-wrap text-xs">
                  <Badge variant="outline" className="text-[10px] font-mono uppercase px-1.5 py-0">
                    {item.source_type}
                  </Badge>
                  <Badge variant="secondary" className="text-[10px] uppercase px-1.5 py-0">
                    {item.language}
                  </Badge>
                  
                  {item.importance > 0 && (
                    <Badge
                      variant={item.importance >= 3 ? "destructive" : "default"}
                      className="text-[10px] font-bold px-1.5 py-0"
                    >
                      ★ {item.importance}
                    </Badge>
                  )}
                  
                  {item.related_symbols?.map((s) => (
                    <Badge key={s} variant="outline" className="text-[10px] font-mono px-1.5 py-0 bg-primary/5 text-primary border-primary/20">
                      {s}
                    </Badge>
                  ))}
                  
                  {item.published_at && (
                    <span className="text-[10px] text-muted-foreground ml-auto font-mono">
                      {new Date(item.published_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredItems.length === 0 && !error && (
          <div className="py-16 text-center text-muted-foreground border border-dashed rounded-lg">
            No market wires found matching your search.
          </div>
        )}
      </div>
    </div>
  );
}
