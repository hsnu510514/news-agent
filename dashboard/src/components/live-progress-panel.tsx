"use client";

import React from "react";
import useSWR from "swr";
import { Loader2, Database, Cpu, Activity, Clock, AlertTriangle } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function LiveProgressPanel() {
  const { data, error } = useSWR(
    `${API_BASE}/api/tasks/analysis-stats`,
    fetcher,
    {
      refreshInterval: (data) => (data?.active_run ? 3000 : 8000), // Poll faster when active
    }
  );

  if (error) {
    return null; // Silent fail if API not ready
  }

  if (!data) {
    return (
      <Card className="border border-border/50 bg-card/40 backdrop-blur-sm shadow-sm p-4 animate-pulse">
        <div className="h-6 bg-muted rounded w-1/3 mb-2"></div>
        <div className="h-2 bg-muted rounded w-full"></div>
      </Card>
    );
  }

  const { total_news, pending_news, active_run, last_failed_run } = data;

  if (active_run) {
    const processed = active_run.processed_count || 0;
    const failed = active_run.failed_count || 0;
    const total = active_run.total_count || 1;
    const percentage = Math.min(100, Math.round(((processed + failed) / total) * 100));

    return (
      <Card className="border border-indigo-500/20 bg-gradient-to-r from-indigo-500/5 to-purple-500/5 dark:from-indigo-500/10 dark:to-purple-500/10 shadow-md backdrop-blur-md relative overflow-hidden transition-all duration-300">
        <CardContent className="p-4 flex flex-col md:flex-row items-center gap-4 justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center h-10 w-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-600 dark:text-indigo-400">
              <Cpu className="h-5 w-5 animate-spin duration-[4s]" />
              <Loader2 className="absolute h-6 w-6 animate-spin text-indigo-500 opacity-60" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5">
                  Active Task: {active_run.task_name}
                </h3>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500 font-bold">
                  {active_run.trigger_type}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Running since: {new Date(active_run.start_time).toLocaleTimeString()}
              </p>
            </div>
          </div>

          <div className="flex-1 max-w-md w-full space-y-1.5">
            <div className="flex justify-between text-xs font-semibold text-foreground/80">
              <span>Processed: {processed} / {total} articles</span>
              {failed > 0 && <span className="text-rose-500 font-bold">Failed: {failed}</span>}
              <span>{percentage}%</span>
            </div>
            <div className="w-full bg-muted/60 dark:bg-muted/30 border border-border/40 rounded-full h-2.5 overflow-hidden">
              <div 
                className="bg-indigo-600 dark:bg-indigo-400 h-full rounded-full transition-all duration-500 ease-out" 
                style={{ width: `${percentage}%` }}
              />
            </div>
            {active_run.message && (
              <p className="text-[10px] text-rose-500/90 font-mono mt-1 leading-normal truncate" title={active_run.message}>
                Warning: {active_run.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2.5 text-right md:border-l pl-4 border-border/80 shrink-0 self-stretch justify-center md:justify-start mt-2 md:mt-0">
            <div>
              <div className="text-xs text-muted-foreground">Backlog: {pending_news} pending</div>
              <div className="text-[10px] text-muted-foreground/80 font-mono">Total articles: {total_news}</div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Idle state
  return (
    <Card className="border border-border/80 bg-card/65 shadow-sm backdrop-blur-sm relative overflow-hidden transition-all duration-300">
      <CardContent className="p-4 flex flex-col gap-3">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-foreground flex items-center gap-2">
                System Idle
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {pending_news > 0 
                  ? `Backlog: ${pending_news} news articles pending analysis` 
                  : "All news analyzed. System up to date."}
              </p>
            </div>
          </div>

          <div className="text-right flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-mono font-medium text-muted-foreground">
              Total News: {total_news}
            </span>
          </div>
        </div>

        {last_failed_run && (
          <div className="flex items-start gap-2.5 p-3 rounded-lg border border-rose-500/15 bg-rose-500/5 text-rose-500 text-xs mt-1">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-bold">Last Analysis Run Failed</span>
                <span className="text-[10px] text-muted-foreground/80 font-mono">
                  {new Date(last_failed_run.start_time).toLocaleString()}
                </span>
              </div>
              <p className="font-mono text-[11px] leading-normal break-all line-clamp-2" title={last_failed_run.message}>
                Reason: {last_failed_run.message || "Unknown error"}
              </p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
