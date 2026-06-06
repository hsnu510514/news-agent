"use client";

import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { FlashItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function FlashPage() {
  const { data } = useSWR(`${API}/api/flash?limit=100`, fetcher);
  const items: FlashItem[] = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Flash News / 快讯</h1>
        <p className="text-muted-foreground">Real-time market updates from jin10 and other sources</p>
      </div>

      <div className="space-y-2">
        {items.map((item) => (
          <Card key={item.id} className={item.importance >= 3 ? "border-red-300 bg-red-50/50 dark:bg-red-950/20" : ""}>
            <CardContent className="p-3 flex items-start gap-3">
              <div className="flex-1">
                <p className="text-sm">{item.content}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="outline" className="text-xs">{item.source_type}</Badge>
                  <Badge variant="secondary" className="text-xs">{item.language.toUpperCase()}</Badge>
                  {item.importance >= 3 && <Badge variant="destructive" className="text-xs">★ {item.importance}</Badge>}
                  {item.importance > 0 && item.importance < 3 && (
                    <Badge variant="default" className="text-xs">{item.importance}</Badge>
                  )}
                  {item.related_symbols?.map((s) => (
                    <Badge key={s} variant="secondary" className="text-xs font-mono">{s}</Badge>
                  ))}
                  {item.published_at && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {new Date(item.published_at).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        {items.length === 0 && (
          <div className="py-12 text-center text-muted-foreground">
            No flash news. Configure jin10 token to start receiving real-time updates.
          </div>
        )}
      </div>
    </div>
  );
}