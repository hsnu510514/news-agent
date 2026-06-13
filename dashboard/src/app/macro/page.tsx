"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { MacroItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MacroPage() {
  const { data } = useSWR(`${API}/api/macro?limit=50`, fetcher);
  const indicators: MacroItem[] = data?.items ?? [];

  const grouped = indicators.reduce<Record<string, MacroItem[]>>((acc, item) => {
    const key = item.country;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Macro Indicators / 宏观数据</h1>
        <p className="text-muted-foreground">Economic indicators and macro data</p>
      </div>

      {Object.entries(grouped).map(([country, items]) => (
        <div key={country}>
          <h2 className="text-lg font-semibold mb-3">
            {country === "US" ? "🇺🇸 United States" : country === "CN" ? "🇨🇳 China" : country}
          </h2>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => {
              const change = (item.value !== null && item.previous_value !== null && item.previous_value !== 0)
                ? ((item.value - item.previous_value) / Math.abs(item.previous_value)) * 100
                : null;
              return (
                <Card key={item.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-sm font-medium">{item.indicator_name}</CardTitle>
                      <Badge variant="outline" className="text-xs">{item.period}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {item.value !== null && item.value !== undefined ? (
                        item.value.toLocaleString(undefined, {
                          minimumFractionDigits: 1,
                          maximumFractionDigits: 2,
                        })
                      ) : (
                        "N/A"
                      )}
                      {item.value !== null && item.value !== undefined && item.unit && (
                        <span className="text-sm font-normal text-muted-foreground ml-1">{item.unit}</span>
                      )}
                    </div>
                    {change !== null && (
                      <p className={`text-sm mt-1 ${change > 0 ? "text-green-600" : change < 0 ? "text-red-600" : "text-gray-500"}`}>
                        {change > 0 ? "↑" : change < 0 ? "↓" : "→"} {Math.abs(change).toFixed(2)}% from previous
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground mt-2">
                      Previous: {item.previous_value?.toLocaleString() ?? "N/A"}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      ))}

      {indicators.length === 0 && (
        <div className="py-12 text-center text-muted-foreground">
          No macro data. Run the macro ingestion pipeline to fetch indicators.
        </div>
      )}
    </div>
  );
}