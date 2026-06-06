"use client";

import React, { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Settings,
  Power,
  Play,
  Save,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertTriangle,
  Activity,
  Calendar,
} from "lucide-react";

interface Job {
  id: str;
  name: str;
  enabled: bool;
  trigger_type: str;
  schedule_value: str;
  last_run_time: str | null;
  last_run_status: str | null;
  last_run_message: str | null;
  next_run_time: str | null;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function JobCard({ job, onRefresh }: { job: Job; onRefresh: () => void }) {
  const [enabled, setEnabled] = useState(job.enabled);
  const [triggerType, setTriggerType] = useState(job.trigger_type);
  const [scheduleValue, setScheduleValue] = useState(job.schedule_value);
  
  const [isSaving, setIsSaving] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const [showError, setShowError] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const handleSave = async () => {
    setIsSaving(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/scheduler/jobs/${job.id}/config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          enabled,
          trigger_type: triggerType,
          schedule_value: scheduleValue,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Failed to save configuration");
      }

      setStatusMessage({ text: "Schedule updated successfully!", type: "success" });
      onRefresh();
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to save settings", type: "error" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTrigger = async () => {
    setIsTriggering(true);
    setStatusMessage(null);
    try {
      const res = await fetch(`${API_BASE}/api/scheduler/jobs/${job.id}/trigger`, {
        method: "POST",
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to trigger job");
      }

      setStatusMessage({ text: "Job triggered manually in background!", type: "success" });
      // Poll/refresh status after a short delay
      setTimeout(onRefresh, 1500);
    } catch (err: any) {
      setStatusMessage({ text: err.message || "Failed to trigger run", type: "error" });
    } finally {
      setIsTriggering(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Never";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const getStatusBadge = () => {
    if (!job.last_run_status) {
      return <Badge variant="secondary" className="bg-muted text-muted-foreground">Never Run</Badge>;
    }
    if (job.last_run_status === "success") {
      return (
        <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 gap-1">
          <CheckCircle2 className="h-3 w-3" /> Success
        </Badge>
      );
    }
    return (
      <Badge variant="destructive" className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20 gap-1 cursor-pointer" onClick={() => setShowError(!showError)}>
        <XCircle className="h-3 w-3" /> Failed
      </Badge>
    );
  };

  const isScheduleDirty = enabled !== job.enabled || triggerType !== job.trigger_type || scheduleValue !== job.schedule_value;

  return (
    <Card className="flex flex-col h-full border-border bg-card shadow-sm hover:shadow transition-shadow">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-semibold leading-none">{job.name}</CardTitle>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEnabled(!enabled)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                enabled ? "bg-primary" : "bg-input"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out ${
                  enabled ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
            <span className="text-xs text-muted-foreground font-medium">
              {enabled ? "Active" : "Paused"}
            </span>
          </div>
        </div>
        <CardDescription className="text-xs font-mono select-all text-muted-foreground mt-1">ID: {job.id}</CardDescription>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col gap-4">
        {/* Configuration settings */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">Trigger Type</label>
            <select
              value={triggerType}
              onChange={(e) => setTriggerType(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            >
              <option value="interval">Interval (Numeric)</option>
              <option value="cron">Cron (Expression)</option>
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              {triggerType === "interval" 
                ? (job.id === "earnings" || job.id === "macro" ? "Interval (Hours)" : "Interval (Minutes)")
                : "Cron Expression"}
            </label>
            <Input
              value={scheduleValue}
              onChange={(e) => setScheduleValue(e.target.value)}
              placeholder={triggerType === "interval" ? "30" : "*/15 * * * *"}
              className="h-9 text-sm"
            />
          </div>
        </div>

        {/* Execution Metadata */}
        <div className="rounded-lg bg-muted/30 p-3 space-y-2 text-xs border border-muted-foreground/10 mt-auto">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground flex items-center gap-1"><Activity className="h-3 w-3" /> Last Run:</span>
            <span className="font-medium">{formatDate(job.last_run_time)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground flex items-center gap-1"><Clock className="h-3 w-3" /> Next Run:</span>
            <span className="font-medium">{job.enabled ? formatDate(job.next_run_time) : "Disabled"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground flex items-center gap-1"><Power className="h-3 w-3" /> Status:</span>
            {getStatusBadge()}
          </div>
        </div>

        {/* Traceback detail wrapper on failure */}
        {showError && job.last_run_message && (
          <div className="rounded-md bg-rose-500/5 border border-rose-500/10 p-3 text-[11px] font-mono text-rose-500 max-h-40 overflow-y-auto leading-normal">
            <p className="font-semibold mb-1">Execution Traceback:</p>
            <pre className="whitespace-pre-wrap">{job.last_run_message}</pre>
          </div>
        )}

        {/* Inline success/error feedback */}
        {statusMessage && (
          <div className={`flex items-center gap-1.5 p-2 rounded text-xs ${
            statusMessage.type === "success" 
              ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" 
              : "bg-rose-500/10 text-rose-500 border border-rose-500/20"
          }`}>
            {statusMessage.type === "error" && <AlertTriangle className="h-3.5 w-3.5 shrink-0" />}
            <span>{statusMessage.text}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2 pt-2 border-t border-border mt-2">
          <Button
            onClick={handleTrigger}
            disabled={isTriggering}
            variant="outline"
            className="flex-1 text-xs gap-1.5 h-8"
          >
            {isTriggering ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            Run Now
          </Button>

          <Button
            onClick={handleSave}
            disabled={isSaving || !isScheduleDirty}
            className="flex-1 text-xs gap-1.5 h-8"
          >
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3 w-3" />
            )}
            Save Schedule
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SettingsPage() {
  const { data: jobs, error, mutate } = useSWR<Job[]>(`${API_BASE}/api/scheduler/jobs`, fetcher);

  const handleRefresh = () => {
    mutate();
  };

  const handleTriggerAll = async () => {
    if (!jobs) return;
    for (const job of jobs) {
      if (job.enabled) {
        await fetch(`${API_BASE}/api/scheduler/jobs/${job.id}/trigger`, { method: "POST" });
      }
    }
    mutate();
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Settings className="h-6 w-6 text-primary" /> Settings & Ingestion Scheduler
          </h1>
          <p className="text-muted-foreground">
            Configure dynamic intervals, cron expressions, and manually trigger pipelines.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh} className="text-xs h-9">
            Refresh Status
          </Button>
          <Button size="sm" onClick={handleTriggerAll} className="text-xs h-9 gap-1.5">
            <Play className="h-3.5 w-3.5" /> Trigger All Active
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">Failed to load scheduler jobs</p>
            <p className="text-xs opacity-90">Please ensure the backend FastAPI service is running.</p>
          </div>
        </div>
      )}

      {!jobs && !error && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {jobs && (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} onRefresh={handleRefresh} />
          ))}
        </div>
      )}
    </div>
  );
}
