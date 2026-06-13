"use client";

import React, { useState } from "react";
import useSWR from "swr";
import {
  History,
  Play,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Clock,
  Database,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TaskRun {
  id: string;
  job_id: string;
  task_name: string;
  trigger_type: string;
  status: string;
  start_time: string;
  end_time: string | null;
  processed_count: number;
  failed_count: number;
  total_count: number;
  message: string | null;
}

interface AnalysisStats {
  total_news: number;
  pending_news: number;
  pending_preprocessing: number;
  pending_analysis: number;
  active_run: TaskRun | null;
  llm_api_status: {
    status: string;
    error_message: string;
    requests_made_today: number;
    estimated_daily_limit: number;
  } | null;
}

function RunningTimer({ startTime }: { startTime: string }) {
  const [elapsed, setElapsed] = useState<string>("");

  React.useEffect(() => {
    const calculate = () => {
      try {
        const diffMs = new Date().getTime() - new Date(startTime).getTime();
        const diffSec = Math.floor(diffMs / 1000);
        if (diffSec < 0) return "0s";
        if (diffSec < 60) return `${diffSec}s`;
        const mins = Math.floor(diffSec / 60);
        const secs = diffSec % 60;
        return `${mins}m ${secs}s`;
      } catch {
        return "-";
      }
    };

    setElapsed(calculate());
    const interval = setInterval(() => {
      setElapsed(calculate());
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime]);

  return <span>{elapsed}</span>;
}

export default function TaskHistoryPage() {
  const [triggeringJob, setTriggeringJob] = useState<string | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [stoppingRunId, setStoppingRunId] = useState<string | null>(null);
  const [pageOffset, setPageOffset] = useState<number>(0);
  const limit = 20;

  const handleStopTask = async (taskRunId: string) => {
    setStoppingRunId(taskRunId);
    try {
      const res = await fetch(`${API_BASE}/api/tasks/${taskRunId}/stop`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error("Failed to stop task");
      }
      mutateStats();
      mutateHistory();
    } catch (err) {
      console.error("Failed to stop task run:", err);
    } finally {
      setStoppingRunId(null);
    }
  };

  // Poll analysis stats every 3s if active task is running, otherwise 8s
  const { data: statsData, mutate: mutateStats } = useSWR<AnalysisStats>(
    `${API_BASE}/api/tasks/analysis-stats`,
    fetcher,
    {
      refreshInterval: (data) => (data?.active_run ? 3000 : 8000),
    }
  );

  // Fetch execution history, polling every 5s if active task is running, otherwise 10s
  const { data: historyDataResponse, error: historyError, mutate: mutateHistory } = useSWR<{
    total: number;
    offset: number;
    limit: number;
    items: TaskRun[];
  }>(
    `${API_BASE}/api/tasks/history?limit=${limit}&offset=${pageOffset}`,
    fetcher,
    {
      refreshInterval: statsData?.active_run ? 3000 : 8000,
    }
  );

  const historyData = historyDataResponse?.items ?? [];
  const totalHistory = historyDataResponse?.total ?? 0;

  const handleTrigger = async (jobId: string, endpoint: string) => {
    setTriggeringJob(jobId);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || `Failed to trigger ${jobId}`);
      }

      // Instantly mutate stats & history to show active state immediately
      mutateStats();
      mutateHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`Failed to trigger run for ${jobId}:`, msg);
    } finally {
      setTriggeringJob(null);
    }
  };

  const handleRefresh = () => {
    mutateStats();
    mutateHistory();
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return "In Progress...";
    try {
      const diffMs = new Date(end).getTime() - new Date(start).getTime();
      const diffSec = Math.floor(diffMs / 1000);
      if (diffSec < 60) return `${diffSec}s`;
      const mins = Math.floor(diffSec / 60);
      const secs = diffSec % 60;
      return `${mins}m ${secs}s`;
    } catch {
      return "-";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "running":
        return (
          <Badge className="bg-indigo-500/10 text-indigo-500 hover:bg-indigo-500/20 border-indigo-500/20 gap-1.5 animate-pulse">
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-500" />
            Running
          </Badge>
        );
      case "success":
        return (
          <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 gap-1">
            <CheckCircle2 className="h-3.5 w-3.5" /> Success
          </Badge>
        );
      case "failed":
        return (
          <Badge variant="destructive" className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20 gap-1">
            <XCircle className="h-3.5 w-3.5" /> Failed
          </Badge>
        );
      case "timeout":
        return (
          <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 gap-1 font-semibold">
            <Clock className="h-3.5 w-3.5" /> Timeout
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const triggerButtons = [
    { id: "rss_news", name: "RSS Ingest", endpoint: "/api/scheduler/jobs/rss_news/trigger" },
    { id: "newsapi", name: "NewsAPI Ingest", endpoint: "/api/scheduler/jobs/newsapi/trigger" },
    { id: "collector_news", name: "Collector Ingest", endpoint: "/api/scheduler/jobs/collector_news/trigger" },
    { id: "earnings", name: "Earnings Data", endpoint: "/api/scheduler/jobs/earnings/trigger" },
    { id: "macro", name: "Macro Indicators", endpoint: "/api/scheduler/jobs/macro/trigger" },
    { id: "preprocessing", name: "Pre-processing", endpoint: "/api/scheduler/jobs/preprocessing/trigger" },
    { id: "analysis", name: "AI Analysis", endpoint: "/api/scheduler/jobs/analysis/trigger" },
    { id: "briefing", name: "Daily Briefing", endpoint: "/api/scheduler/jobs/briefing/trigger" },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-2">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <History className="h-6 w-6 text-primary" /> Task Execution History
          </h1>
          <p className="text-muted-foreground text-sm">
            Monitor real-time pipeline progress, inspect task warnings/timeouts, and trigger runs manually.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} className="h-9 gap-1.5 text-xs">
            <RotateCcw className="h-3.5 w-3.5" /> Refresh Logs
          </Button>
        </div>
      </div>

      {/* Manual Triggers Panel */}
      <Card className="border border-border/80 bg-card/65 shadow-sm backdrop-blur-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4.5 w-4.5 text-primary" /> Manual Execution Triggers
          </CardTitle>
          <CardDescription className="text-xs">
            Start any background news ingestion, analysis, or daily briefing pipeline task immediately.
          </CardDescription>
        </CardHeader>
        <CardContent className="pb-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5">
            {triggerButtons.map((btn) => (
              <Button
                key={btn.id}
                onClick={() => handleTrigger(btn.id, btn.endpoint)}
                disabled={triggeringJob !== null || statsData?.active_run !== null}
                variant="outline"
                className="text-xs justify-start gap-1.5 h-9 font-medium overflow-hidden text-ellipsis whitespace-nowrap"
              >
                {triggeringJob === btn.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0 text-primary" />
                ) : (
                  <Play className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
                <span>{btn.name}</span>
              </Button>
            ))}
          </div>


        </CardContent>
      </Card>

      {/* History Log Table */}
      <Card className="border border-border/80 bg-card/65 shadow-sm backdrop-blur-sm overflow-hidden">
        <CardHeader className="pb-3 border-b border-border/50 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <History className="h-4.5 w-4.5 text-muted-foreground" /> Historical Executions Log
            </CardTitle>
            <CardDescription className="text-xs">
              Review detailed metrics, warnings, and tracebacks for the 50 most recent task runs. Click on failed or timed out tasks to inspect errors.
            </CardDescription>
          </div>
          {statsData && (
            <div className="flex flex-wrap items-center gap-2 md:gap-4 text-[11px] font-medium self-end md:self-center">
              <div className="px-2.5 py-1 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                <span className="font-mono font-bold text-amber-700 dark:text-amber-300 mr-1">{statsData.pending_preprocessing}</span> Pending Pre-processing
              </div>
              <div className="px-2.5 py-1 rounded bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
                <span className="font-mono font-bold text-indigo-700 dark:text-indigo-300 mr-1">{statsData.pending_analysis}</span> Pending Analysis
              </div>
            </div>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {historyError && (
            <div className="p-6 text-center text-xs text-rose-500 border-b border-border">
              <AlertTriangle className="h-6 w-6 text-rose-500 mx-auto mb-2" />
              Failed to load task history logs. Please verify backend FastAPI service is running.
            </div>
          )}
          {!historyData && !historyError && (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          )}
          {historyData && historyData.length === 0 && (
            <div className="text-center py-16 text-sm text-muted-foreground italic">
              No historical task executions recorded in the database.
            </div>
          )}

          {historyData && historyData.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider">
                    <th className="p-4 w-[18%]">Status</th>
                    <th className="p-4 w-[20%]">Task Name</th>
                    <th className="p-4 w-[12%]">Trigger</th>
                    <th className="p-4 w-[18%]">Start Time</th>
                    <th className="p-4 w-[14%]">Duration</th>
                    <th className="p-4 w-[18%]">Progress / Processed</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {historyData.map((run) => {
                    const isFailedOrTimeout = run.status === "failed" || run.status === "timeout";
                    const isExpanded = expandedRunId === run.id;

                    return (
                      <React.Fragment key={run.id}>
                        <tr
                          onClick={() => {
                            if (isFailedOrTimeout) {
                              setExpandedRunId(isExpanded ? null : run.id);
                            }
                          }}
                          className={`hover:bg-muted/10 transition-colors ${
                            isFailedOrTimeout ? "cursor-pointer select-none" : ""
                          }`}
                        >
                          <td className="p-4 font-medium">
                            <div className="flex items-center gap-2">
                              {getStatusBadge(run.status)}
                              {run.status === "running" && (run.job_id === "preprocessing" || run.job_id === "analysis") && (
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleStopTask(run.id);
                                  }}
                                  disabled={stoppingRunId === run.id}
                                  className="h-6 px-2 text-[10px] bg-rose-500 hover:bg-rose-600 text-white font-bold shrink-0 shadow-sm transition-all"
                                >
                                  {stoppingRunId === run.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    "Stop"
                                  )}
                                </Button>
                              )}
                            </div>
                          </td>
                          <td className="p-4 font-semibold text-foreground leading-normal whitespace-pre-wrap break-all">
                            <span>{run.task_name}</span>
                            <span className="block font-mono text-[9px] text-muted-foreground mt-0.5">ID: {run.id}</span>
                          </td>
                          <td className="p-4 capitalize text-muted-foreground font-medium">{run.trigger_type}</td>
                          <td className="p-4 text-muted-foreground font-medium">{formatDate(run.start_time)}</td>
                          <td className="p-4 text-muted-foreground font-medium">
                            {run.status === "running" ? (
                              <span className="flex items-center gap-1 text-indigo-500 font-semibold">
                                <Clock className="h-3.5 w-3.5 animate-spin shrink-0" style={{ animationDuration: "3s" }} />
                                <RunningTimer startTime={run.start_time} />
                              </span>
                            ) : (
                              formatDuration(run.start_time, run.end_time)
                            )}
                          </td>
                          <td className="p-4 text-left font-medium text-foreground">
                            {run.status === "running" ? (
                              <div className="space-y-1.5 w-full max-w-[220px]">
                                <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                                  {run.job_id === "analysis" || run.job_id === "preprocessing" ? (
                                    <>
                                      <span>
                                        Processed: {run.processed_count} / {run.total_count || 1}
                                      </span>
                                      {run.failed_count > 0 && (
                                        <span className="text-rose-500 font-bold">F: {run.failed_count}</span>
                                      )}
                                      <span>
                                        {Math.min(
                                          100,
                                          Math.round(
                                            ((run.processed_count + run.failed_count) /
                                              (run.total_count || 1)) *
                                              100
                                          )
                                        )}
                                        %
                                      </span>
                                    </>
                                  ) : (
                                    <span>Executing...</span>
                                  )}
                                </div>
                                <div className="w-full bg-muted/60 border border-border/40 rounded-full h-1.5 overflow-hidden relative">
                                  {run.job_id === "analysis" || run.job_id === "preprocessing" ? (
                                    <div
                                      className="bg-indigo-600 dark:bg-indigo-400 h-full rounded-full transition-all duration-500 ease-out"
                                      style={{
                                        width: `${Math.min(
                                          100,
                                          Math.round(
                                            ((run.processed_count + run.failed_count) /
                                              (run.total_count || 1)) *
                                              100
                                          )
                                        )}%`,
                                      }}
                                    />
                                  ) : (
                                    <div className="bg-indigo-600 dark:bg-indigo-400 h-full rounded-full animate-loading-slide" />
                                  )}
                                </div>
                              </div>
                            ) : (
                              <span className="font-mono font-bold text-foreground">
                                {run.processed_count} / {run.total_count}
                              </span>
                            )}
                          </td>
                        </tr>

                        {isExpanded && isFailedOrTimeout && run.message && (
                          <tr>
                            <td
                              colSpan={6}
                              className="p-4 bg-muted/30 border-t border-border/80 font-mono text-[10px] leading-relaxed select-text"
                            >
                              <div className="flex items-start gap-2 text-rose-500 font-bold mb-2">
                                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-rose-500" />
                                <span>Task Execution Issue Details / 任务执行问题详情:</span>
                              </div>
                              <pre className="p-3 bg-muted/65 rounded-lg border border-border/60 max-h-80 overflow-y-auto whitespace-pre-wrap font-mono text-muted-foreground">
                                {run.message}
                              </pre>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {totalHistory > limit && (
            <div className="flex justify-center items-center gap-3 py-4 border-t border-border/50">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPageOffset(Math.max(0, pageOffset - limit))}
                disabled={pageOffset === 0}
                className="h-8 text-xs cursor-pointer"
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground font-medium font-mono">
                {pageOffset + 1} - {Math.min(pageOffset + limit, totalHistory)} of {totalHistory}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPageOffset(pageOffset + limit)}
                disabled={pageOffset + limit >= totalHistory}
                className="h-8 text-xs cursor-pointer"
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
