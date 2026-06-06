"use client";

import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { EarningsItem } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

function formatNumber(num: number | null): string {
  if (num === null || num === undefined) return "N/A";
  if (Math.abs(num) >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
  if (Math.abs(num) >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
  return `$${num.toFixed(2)}`;
}

export default function EarningsPage() {
  const { data } = useSWR(`${API}/api/earnings?limit=50`, fetcher);
  const earnings: EarningsItem[] = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Earnings / 财报</h1>
        <p className="text-muted-foreground">Company earnings and financial data</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {earnings.map((item) => {
          const epsSurprise = item.eps && item.eps_estimate
            ? ((item.eps - item.eps_estimate) / Math.abs(item.eps_estimate)) * 100
            : null;
          return (
            <Card key={item.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg font-mono">{item.ticker}</CardTitle>
                  {epsSurprise !== null && (
                    <Badge variant={epsSurprise > 0 ? "default" : "destructive"}>
                      {epsSurprise > 0 ? "+" : ""}{epsSurprise.toFixed(1)}%
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{item.company_name || item.ticker}</p>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">Revenue</span>
                    <p className="font-medium">{formatNumber(item.revenue)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Net Income</span>
                    <p className="font-medium">{formatNumber(item.net_income ?? null)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">EPS</span>
                    <p className="font-medium">{item.eps !== null ? `$${item.eps?.toFixed(2)}` : "N/A"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">EPS Est.</span>
                    <p className="font-medium">{item.eps_estimate !== null ? `$${item.eps_estimate?.toFixed(2)}` : "N/A"}</p>
                  </div>
                </div>
                {item.report_date && (
                  <p className="text-xs text-muted-foreground pt-1">
                    {new Date(item.report_date).toLocaleDateString()} • {item.period || "Annual"}
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {earnings.length === 0 && (
        <div className="py-12 text-center text-muted-foreground">
          No earnings data. Run the earnings ingestion pipeline to fetch data.
        </div>
      )}
    </div>
  );
}