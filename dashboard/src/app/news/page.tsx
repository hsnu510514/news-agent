"use client";

import useSWR from "swr";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import type { NewsItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function NewsPage() {
  const [language, setLanguage] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [search, setSearch] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const params = new URLSearchParams();
  if (language) params.set("language", language);
  if (source) params.set("source_type", source);
  if (search) params.set("search", search);
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const { data } = useSWR(`${API}/api/news?${params.toString()}`, fetcher);
  const news: NewsItem[] = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">News Feed / 新闻</h1>
        <p className="text-muted-foreground">{total} articles total</p>
      </div>

      <div className="flex gap-3">
        <Input
          placeholder="Search news..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
          className="max-w-xs"
        />
        <select
          value={language}
          onChange={(e) => { setLanguage(e.target.value); setOffset(0); }}
          className="rounded-md border px-3 py-2 text-sm"
        >
          <option value="">All Languages</option>
          <option value="en">English</option>
          <option value="zh">中文</option>
        </select>
        <select
          value={source}
          onChange={(e) => { setSource(e.target.value); setOffset(0); }}
          className="rounded-md border px-3 py-2 text-sm"
        >
          <option value="">All Sources</option>
          <option value="rss">RSS</option>
          <option value="newsapi">NewsAPI</option>
          <option value="jin10">jin10</option>
        </select>
      </div>

      <div className="space-y-3">
        {news.map((item) => (
          <a
            key={item.id}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="block"
          >
            <Card className="hover:bg-accent/50 transition-colors">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="font-semibold text-sm leading-snug">
                      {item.title_zh && item.language === "zh" ? (
                        <>
                          {item.title_zh}
                          <span className="text-xs text-muted-foreground ml-2">{item.title}</span>
                        </>
                      ) : (
                        item.title
                      )}
                    </h3>
                    {item.summary && (
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{item.summary}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="outline" className="text-xs">{item.source_name}</Badge>
                      <Badge variant="secondary" className="text-xs">{item.language.toUpperCase()}</Badge>
                      {item.published_at && (
                        <span className="text-xs text-muted-foreground">
                          {new Date(item.published_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </a>
        ))}
        {news.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">
            No news articles found. Start the ingestion pipeline to fetch news.
          </div>
        )}
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
    </div>
  );
}