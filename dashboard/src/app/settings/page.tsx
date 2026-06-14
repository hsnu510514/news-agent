"use client";

import React, { useState, useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
  Search,
  Plus,
  Edit2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { ModelQuotasTab } from "./model-quotas-tab";
import { PrimarySourcesTab } from "./primary-sources-tab";

interface Job {
  id: string;
  name: string;
  enabled: boolean;
  trigger_type: string;
  schedule_value: string;
  last_run_time: string | null;
  last_run_status: string | null;
  last_run_message: string | null;
  next_run_time: string | null;
  volume_threshold: number | null;
  cooldown_minutes: number;
  in_cooldown: boolean;
  cooldown_remaining_seconds: number;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function JobCard({ 
  job, 
  onRefresh, 
  onViewHistory 
}: { 
  job: Job; 
  onRefresh: () => void; 
  onViewHistory: (jobId: string, jobName: string) => void;
}) {
  const [enabled, setEnabled] = useState(job.enabled);
  const [triggerType, setTriggerType] = useState(job.trigger_type);
  const [scheduleValue, setScheduleValue] = useState(job.schedule_value);
  const [cooldownMinutes, setCooldownMinutes] = useState(job.cooldown_minutes);
  
  const [isSaving, setIsSaving] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const [showError, setShowError] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const [cooldownRemaining, setCooldownRemaining] = useState(job.cooldown_remaining_seconds || 0);

  useEffect(() => {
    setCooldownRemaining(job.cooldown_remaining_seconds || 0);
  }, [job.cooldown_remaining_seconds]);

  useEffect(() => {
    if (cooldownRemaining <= 0) return;
    const interval = setInterval(() => {
      setCooldownRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onRefresh();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldownRemaining, onRefresh]);

  const formatCooldown = (seconds: number) => {
    if (seconds <= 0) return "";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    if (m > 0) {
      return `${m}m ${s}s left`;
    }
    return `${s}s left`;
  };

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
          cooldown_minutes: Number(cooldownMinutes),
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
    if (job.last_run_status === "timeout") {
      return (
        <Badge className="bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 border-amber-500/20 gap-1 cursor-pointer" onClick={() => setShowError(!showError)}>
          <Clock className="h-3 w-3" /> Timeout
        </Badge>
      );
    }
    return (
      <Badge variant="destructive" className="bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20 gap-1 cursor-pointer" onClick={() => setShowError(!showError)}>
        <XCircle className="h-3 w-3" /> Failed
      </Badge>
    );
  };

  const isScheduleDirty = enabled !== job.enabled || 
    triggerType !== job.trigger_type || 
    scheduleValue !== job.schedule_value ||
    Number(cooldownMinutes) !== job.cooldown_minutes;

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

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Cooldown (Minutes)</label>
          <Input
            type="number"
            min="0"
            value={cooldownMinutes}
            onChange={(e) => setCooldownMinutes(Number(e.target.value))}
            className="h-9 text-sm"
          />
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
          {cooldownRemaining > 0 && (
            <div className="flex items-center justify-between text-amber-500 font-medium">
              <span className="text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3 text-amber-500 animate-pulse" /> Cooldown:
              </span>
              <span>{formatCooldown(cooldownRemaining)}</span>
            </div>
          )}
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
        <div className="flex flex-wrap gap-2 pt-2 border-t border-border mt-2">
          <Button
            onClick={handleTrigger}
            disabled={isTriggering}
            variant="outline"
            className="flex-1 text-[11px] px-2 gap-1 h-8 min-w-[70px]"
          >
            {isTriggering ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Play className="h-3 w-3" />
            )}
            Run Now
          </Button>

          <Button
            onClick={() => onViewHistory(job.id, job.name)}
            aria-label={`view-history-${job.id}`}
            variant="outline"
            className="flex-1 text-[11px] px-2 gap-1 h-8 min-w-[80px]"
          >
            History
          </Button>

          <Button
            onClick={handleSave}
            disabled={isSaving || !isScheduleDirty}
            className="flex-1 text-[11px] px-2 gap-1 h-8 min-w-[70px]"
          >
            {isSaving ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Save className="h-3 w-3" />
            )}
            Save
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

interface GlossaryItem {
  id: string;
  term_en: string;
  term_zh: string;
  type: string;
  is_verified: boolean;
}

interface GlossaryResponse {
  items: GlossaryItem[];
}

function GlossaryTab() {
  const { data: glossaryData, error: glossaryError, mutate: mutateGlossary } = useSWR<GlossaryResponse>(
    `${API_BASE}/api/glossary`,
    fetcher
  );

  const [showAddForm, setShowAddForm] = useState(false);
  const [editItemId, setEditItemId] = useState<string | null>(null);
  
  const [enTerm, setEnTerm] = useState("");
  const [zhTerm, setZhTerm] = useState("");
  const [termType, setTermType] = useState("company");
  const [isSubmittingTerm, setIsSubmittingTerm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [glossarySearch, setGlossarySearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;
  
  const [verifyingIds, setVerifyingIds] = useState<Record<string, boolean>>({});

  const handleVerify = async (itemId: string) => {
    setVerifyingIds((prev) => ({ ...prev, [itemId]: true }));
    try {
      const res = await fetch(`${API_BASE}/api/glossary/${itemId}/verify`, {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error("Failed to verify term");
      }
      mutateGlossary();
    } catch (err) {
      console.error(err);
    } finally {
      setVerifyingIds((prev) => ({ ...prev, [itemId]: false }));
    }
  };

  const handleEditClick = (item: GlossaryItem) => {
    setEditItemId(item.id);
    setEnTerm(item.term_en);
    setZhTerm(item.term_zh);
    setTermType(item.type);
    setShowAddForm(true);
    setFormError(null);
  };

  const handleSubmitTerm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enTerm.trim() || !zhTerm.trim()) {
      setFormError("Both English and Chinese terms are required.");
      return;
    }
    setIsSubmittingTerm(true);
    setFormError(null);
    try {
      const url = editItemId 
        ? `${API_BASE}/api/glossary/${editItemId}`
        : `${API_BASE}/api/glossary`;
      const method = editItemId ? "PUT" : "POST";
      
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          term_en: enTerm.trim(),
          term_zh: zhTerm.trim(),
          type: termType,
          is_verified: true,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to submit term");
      }

      mutateGlossary();
      setShowAddForm(false);
      setEditItemId(null);
      setEnTerm("");
      setZhTerm("");
      setTermType("company");
    } catch (err: any) {
      setFormError(err.message || "Failed to save term");
    } finally {
      setIsSubmittingTerm(false);
    }
  };

  const filteredItems = (glossaryData?.items || []).filter((item) => {
    const query = glossarySearch.toLowerCase().trim();
    if (!query) return true;
    return (
      item.term_en.toLowerCase().includes(query) ||
      item.term_zh.toLowerCase().includes(query) ||
      item.type.toLowerCase().includes(query)
    );
  });

  const totalPages = Math.ceil(filteredItems.length / itemsPerPage) || 1;
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedItems = filteredItems.slice(
    (safeCurrentPage - 1) * itemsPerPage,
    safeCurrentPage * itemsPerPage
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search glossary terms..."
            value={glossarySearch}
            onChange={(e) => {
              setGlossarySearch(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-9 h-9"
          />
        </div>

        <Button
          onClick={() => {
            setShowAddForm(!showAddForm);
            setEditItemId(null);
            setEnTerm("");
            setZhTerm("");
            setTermType("company");
            setFormError(null);
          }}
          aria-label="add-term-trigger"
          size="sm"
          className="h-9 gap-1.5 self-start sm:self-auto"
        >
          <Plus className="h-4 w-4" /> Add Term
        </Button>
      </div>

      {showAddForm && (
        <Card className="border border-border bg-card shadow-sm p-5">
          <form onSubmit={handleSubmitTerm} className="space-y-4">
            <h3 className="text-sm font-semibold text-foreground">
              {editItemId ? "Edit Glossary Term" : "Add Glossary Term"}
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">English Term</label>
                <Input
                  value={enTerm}
                  onChange={(e) => setEnTerm(e.target.value)}
                  placeholder="e.g. Nvidia"
                  className="h-9"
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Chinese Term</label>
                <Input
                  value={zhTerm}
                  onChange={(e) => setZhTerm(e.target.value)}
                  placeholder="e.g. 辉达"
                  className="h-9"
                  required
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Type</label>
                <select
                  value={termType}
                  onChange={(e) => setTermType(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <option value="company">Company</option>
                  <option value="theme">Theme</option>
                  <option value="person">Person</option>
                  <option value="concept">Concept</option>
                  <option value="organization">Organization</option>
                </select>
              </div>
            </div>
            {formError && (
              <p className="text-xs text-rose-500 font-medium">{formError}</p>
            )}
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowAddForm(false);
                  setEditItemId(null);
                }}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                aria-label="submit-term"
                size="sm"
                className="h-8 text-xs gap-1.5"
                disabled={isSubmittingTerm || !enTerm.trim() || !zhTerm.trim()}
              >
                {isSubmittingTerm && <Loader2 className="h-3 w-3 animate-spin" />}
                {editItemId ? "Update Term" : "Add Term"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {glossaryError && (
        <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">Failed to load glossary terms</p>
            <p className="text-xs opacity-90">Please ensure the backend FastAPI service is running.</p>
          </div>
        </div>
      )}

      {!glossaryData && !glossaryError && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {glossaryData && (
        <div className="space-y-4">
          <div className="border border-border rounded-lg bg-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/40 text-muted-foreground font-medium text-xs uppercase tracking-wider">
                    <th className="p-4">English Term</th>
                    <th className="p-4">Chinese Translation</th>
                    <th className="p-4">Type</th>
                    <th className="p-4 text-center">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {paginatedItems.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-8 text-center text-muted-foreground">
                        No glossary terms found matching your search.
                      </td>
                    </tr>
                  ) : (
                    paginatedItems.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/10 transition-colors">
                        <td className="p-4 font-medium text-foreground">{item.term_en}</td>
                        <td className="p-4 font-medium text-foreground">{item.term_zh}</td>
                        <td className="p-4">
                          <Badge variant="outline" className="capitalize text-xs font-normal border-border/80 text-muted-foreground">
                            {item.type}
                          </Badge>
                        </td>
                        <td className="p-4 text-center">
                          {item.is_verified ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-500 font-medium">
                              <CheckCircle2 className="h-3.5 w-3.5" /> Verified
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-500 font-medium">
                              <AlertTriangle className="h-3.5 w-3.5" /> Pending
                            </span>
                          )}
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {!item.is_verified && (
                              <Button
                                onClick={() => handleVerify(item.id)}
                                aria-label={`verify-term-${item.id}`}
                                disabled={verifyingIds[item.id]}
                                size="sm"
                                variant="outline"
                                className="h-7 text-[11px] px-2.5 border-emerald-500/20 bg-emerald-500/5 text-emerald-500 hover:bg-emerald-500/15 hover:text-emerald-500"
                              >
                                {verifyingIds[item.id] ? (
                                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                                ) : null}
                                Verify
                              </Button>
                            )}
                            <Button
                              onClick={() => handleEditClick(item)}
                              aria-label={`edit-term-${item.id}`}
                              size="sm"
                              variant="outline"
                              className="h-7 text-[11px] px-2 gap-1"
                            >
                              <Edit2 className="h-3 w-3" /> Edit
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-2 py-1">
              <div className="text-xs text-muted-foreground">
                Showing{" "}
                <span className="font-semibold text-foreground">
                  {(safeCurrentPage - 1) * itemsPerPage + 1}
                </span>{" "}
                to{" "}
                <span className="font-semibold text-foreground">
                  {Math.min(safeCurrentPage * itemsPerPage, filteredItems.length)}
                </span>{" "}
                of{" "}
                <span className="font-semibold text-foreground">
                  {filteredItems.length}
                </span>{" "}
                terms
              </div>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 cursor-pointer"
                  onClick={() => setCurrentPage(1)}
                  disabled={safeCurrentPage === 1}
                  aria-label="first-page"
                >
                  <ChevronsLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 cursor-pointer"
                  onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                  disabled={safeCurrentPage === 1}
                  aria-label="previous-page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>

                <div className="flex items-center gap-1 font-medium text-xs px-2 text-muted-foreground">
                  Page <span className="text-foreground font-semibold">{safeCurrentPage}</span> of{" "}
                  <span className="text-foreground font-semibold">{totalPages}</span>
                </div>

                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 cursor-pointer"
                  onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                  disabled={safeCurrentPage === totalPages}
                  aria-label="next-page"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 cursor-pointer"
                  onClick={() => setCurrentPage(totalPages)}
                  disabled={safeCurrentPage === totalPages}
                  aria-label="last-page"
                >
                  <ChevronsRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function HistoryDrawer({ jobId, jobName, onClose }: { jobId: string; jobName: string; onClose: () => void }) {
  const { data: runs, error } = useSWR<any[]>(
    `${API_BASE}/api/tasks/history?job_id=${jobId}`,
    fetcher
  );

  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return "Running...";
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

  return (
    <>
      <div 
        className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl bg-card border-l border-border shadow-2xl transition-transform duration-300 ease-in-out">
        <div className="flex flex-col w-full h-full p-6 overflow-hidden">
          <div className="flex items-center justify-between border-b pb-4 mb-4">
            <div>
              <h2 className="text-lg font-bold text-foreground">Execution History: {jobName}</h2>
              <p className="text-xs font-mono text-muted-foreground mt-0.5">Job ID: {jobId}</p>
            </div>
            <Button
              onClick={onClose}
              variant="outline"
              size="sm"
              aria-label="close-drawer"
              className="h-8 w-8 p-0"
            >
              <XCircle className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto pr-1 space-y-4">
            {error && (
              <div className="p-4 rounded-lg bg-rose-500/10 text-rose-500 text-xs border border-rose-500/20">
                Failed to load history for this job.
              </div>
            )}
            {!runs && !error && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            )}
            {runs && runs.length === 0 && (
              <div className="text-center py-12 text-sm text-muted-foreground">
                No task executions recorded for this job.
              </div>
            )}
            {runs && runs.length > 0 && (
              <div className="border border-border/80 rounded-lg overflow-hidden bg-muted/10">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider">
                      <th className="p-3">Status</th>
                      <th className="p-3">Trigger</th>
                      <th className="p-3">Start Time</th>
                      <th className="p-3">Duration</th>
                      <th className="p-3 text-right">Processed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {runs.map((run: any) => (
                      <React.Fragment key={run.id}>
                        <tr 
                          onClick={() => run.status === "failed" && setExpandedRunId(expandedRunId === run.id ? null : run.id)}
                          className={`hover:bg-muted/30 transition-colors ${run.status === "failed" ? "cursor-pointer" : ""}`}
                        >
                          <td className="p-3 font-medium">
                            <span className={`inline-flex items-center gap-1 font-semibold ${
                              run.status === "success" ? "text-emerald-500" :
                              run.status === "failed" ? "text-rose-500" : "text-amber-500"
                            }`}>
                              {run.status}
                            </span>
                          </td>
                          <td className="p-3 capitalize text-muted-foreground">{run.trigger_type}</td>
                          <td className="p-3 text-muted-foreground">{formatDate(run.start_time)}</td>
                          <td className="p-3 text-muted-foreground">{formatDuration(run.start_time, run.end_time)}</td>
                          <td className="p-3 text-right font-medium text-foreground">
                            {run.status === "running" ? "-" : `${run.processed_count} / ${run.total_count}`}
                          </td>
                        </tr>
                        {expandedRunId === run.id && run.message && (
                          <tr>
                            <td colSpan={5} className="p-3 bg-rose-500/5 border-t border-rose-500/10 font-mono text-[10px] text-rose-500 leading-normal whitespace-pre-wrap">
                              <div className="font-semibold mb-1">Execution Traceback:</div>
                              <pre className="max-h-60 overflow-y-auto">{run.message}</pre>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
interface MergeModalProps {

  isOpen: boolean;
  onClose: () => void;
  entityType: "subject" | "insight";
  item1: { id: string; label: string; details?: string };
  item2: { id: string; label: string; details?: string };
  onConfirm: (primaryId: string) => Promise<void>;
}

function MergeModal({ isOpen, onClose, entityType, item1, item2, onConfirm }: MergeModalProps) {
  const [selectedId, setSelectedId] = useState<string>(item1.id);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm(selectedId);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/45 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md bg-card border border-border p-6 rounded-lg shadow-2xl space-y-6">
        <div>
          <h2 className="text-lg font-bold text-foreground capitalize">Merge {entityType}s</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Choose which {entityType} to keep as the primary record. The other will be permanently merged and deleted.
          </p>
        </div>

        <div className="space-y-3">
          <label className="text-xs font-semibold text-muted-foreground">Select Primary:</label>
          <div className="space-y-2">
            <button
              type="button"
              onClick={() => setSelectedId(item1.id)}
              className={`w-full text-left p-3 rounded-lg border text-sm transition-all flex flex-col ${
                selectedId === item1.id
                  ? "border-primary bg-primary/5 text-primary"
                  : "border-border hover:bg-muted/30 text-foreground"
              }`}
            >
              <span className="font-semibold">{item1.label}</span>
              {item1.details && <span className="text-[10px] opacity-80 mt-1 line-clamp-2">{item1.details}</span>}
            </button>
            <button
              type="button"
              onClick={() => setSelectedId(item2.id)}
              className={`w-full text-left p-3 rounded-lg border text-sm transition-all flex flex-col ${
                selectedId === item2.id
                  ? "border-primary bg-primary/5 text-primary"
                  : "border-border hover:bg-muted/30 text-foreground"
              }`}
            >
              <span className="font-semibold">{item2.label}</span>
              {item2.details && <span className="text-[10px] opacity-80 mt-1 line-clamp-2">{item2.details}</span>}
            </button>
          </div>
        </div>

        <div className="bg-amber-500/10 text-amber-500 border border-amber-500/20 p-3 rounded-lg text-xs leading-normal">
          <strong>Warning:</strong> This action permanently deletes the secondary {entityType} and moves all associated child records (insights or facts) to the selected primary. This cannot be undone.
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button size="sm" onClick={handleConfirm} disabled={isSubmitting} className="gap-1.5">
            {isSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Confirm Merge
          </Button>
        </div>
      </div>
    </>
  );
}


function DivergenceTab() {
  const { data, error, mutate } = useSWR(`${API_BASE}/api/insights/divergence`, fetcher);
  const [isScanning, setIsScanning] = useState(false);
  const [mergeState, setMergeState] = useState<{
    isOpen: boolean;
    entityType: "subject" | "insight";
    item1: { id: string; label: string; details?: string };
    item2: { id: string; label: string; details?: string };
  } | null>(null);

  const subjects = data?.subjects ?? [];
  const insights = data?.insights ?? [];

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const res = await fetch(`${API_BASE}/api/scheduler/jobs/divergence/trigger`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Failed to trigger scan");
      await new Promise((resolve) => setTimeout(resolve, 2000));
      mutate();
    } catch (err) {
      console.error(err);
    } finally {
      setIsScanning(false);
    }
  };

  const handleResolveIgnore = async (entityType: "subject" | "insight", id1: string, id2: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/insights/divergence/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_type: entityType,
          id1,
          id2,
          action: "ignore",
        }),
      });
      if (!res.ok) throw new Error("Failed to ignore duplicate");
      mutate();
    } catch (err) {
      console.error(err);
    }
  };

  const handleResolveMerge = async (primaryId: string) => {
    if (!mergeState) return;
    try {
      const res = await fetch(`${API_BASE}/api/insights/divergence/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_type: mergeState.entityType,
          id1: mergeState.item1.id,
          id2: mergeState.item2.id,
          action: "merge",
          primary_id: primaryId,
        }),
      });
      if (!res.ok) throw new Error("Failed to merge duplicate");
      mutate();
    } catch (err) {
      console.error(err);
    }
  };

  const handleOpenSubjectMerge = (item: any) => {
    setMergeState({
      isOpen: true,
      entityType: "subject",
      item1: { id: item.id1, label: item.name1 },
      item2: { id: item.id2, label: item.name2 },
    });
  };

  const handleOpenInsightMerge = (item: any) => {
    setMergeState({
      isOpen: true,
      entityType: "insight",
      item1: { id: item.id1, label: item.dim1, details: item.summary1 },
      item2: { id: item.id2, label: item.dim2, details: item.summary2 },
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-card border border-border p-4 rounded-lg shadow-sm">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Trigger Divergence Scan</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Perform a complete name and semantic similarity scan over all subjects and insights.
          </p>
        </div>
        <Button 
          onClick={handleScan} 
          disabled={isScanning} 
          size="sm" 
          className="h-9 gap-1.5"
        >
          {isScanning ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
          {isScanning ? "Scanning..." : "Scan Now"}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold">Failed to load divergence data</p>
            <p className="text-xs opacity-90">Please ensure the backend FastAPI service is running.</p>
          </div>
        </div>
      )}

      {!data && !error && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {data && (
        <div className="space-y-8">
          {/* Duplicate Subjects */}
          <Card className="border border-border bg-card shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold">Potential Duplicate Subjects / 潜在重复主体</CardTitle>
              <CardDescription className="text-xs">
                Subjects of the same type with similar names (Levenshtein similarity &ge; 70%)
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider text-xs">
                      <th className="p-4">Subject 1</th>
                      <th className="p-4">Subject 2</th>
                      <th className="p-4">Type</th>
                      <th className="p-4 text-center">Similarity</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {subjects.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-muted-foreground text-xs">
                          No duplicate subjects detected.
                        </td>
                      </tr>
                    ) : (
                      subjects.map((item: any, idx: number) => (
                        <tr key={idx} className="hover:bg-muted/10 transition-colors text-xs">
                          <td className="p-4 font-semibold text-foreground">{item.name1}</td>
                          <td className="p-4 font-semibold text-foreground">{item.name2}</td>
                          <td className="p-4 capitalize text-muted-foreground">{item.type}</td>
                          <td className="p-4 text-center font-mono font-bold text-amber-500 text-sm">
                            {Math.round(item.similarity * 100)}%
                          </td>
                          <td className="p-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                onClick={() => handleResolveIgnore("subject", item.id1, item.id2)}
                                variant="outline"
                                size="sm"
                                className="h-7 text-[11px] px-2"
                              >
                                Ignore
                              </Button>
                              <Button
                                onClick={() => handleOpenSubjectMerge(item)}
                                size="sm"
                                className="h-7 text-[11px] px-2.5"
                              >
                                Merge
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Duplicate Insights */}
          <Card className="border border-border bg-card shadow-sm">
            <CardHeader>
              <CardTitle className="text-base font-semibold">Potential Duplicate Insights / 潜在重复见解</CardTitle>
              <CardDescription className="text-xs">
                Multiple narrative dimensions under the same subject with similar summaries (Levenshtein similarity &ge; 80%)
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/40 text-muted-foreground font-semibold uppercase tracking-wider text-xs">
                      <th className="p-4">Subject</th>
                      <th className="p-4">Dimension 1</th>
                      <th className="p-4">Dimension 2</th>
                      <th className="p-4 text-center">Similarity</th>
                      <th className="p-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {insights.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-muted-foreground text-xs">
                          No duplicate insights detected.
                        </td>
                      </tr>
                    ) : (
                      insights.map((item: any, idx: number) => (
                        <tr key={idx} className="hover:bg-muted/10 transition-colors text-xs">
                          <td className="p-4 font-bold text-foreground">{item.subject_name}</td>
                          <td className="p-4 text-muted-foreground">
                            <span className="font-semibold text-foreground block">{item.dim1}</span>
                            <span className="text-[10px] line-clamp-1 block text-muted-foreground mt-0.5" title={item.summary1}>
                              {item.summary1}
                            </span>
                          </td>
                          <td className="p-4 text-muted-foreground">
                            <span className="font-semibold text-foreground block">{item.dim2}</span>
                            <span className="text-[10px] line-clamp-1 block text-muted-foreground mt-0.5" title={item.summary2}>
                              {item.summary2}
                            </span>
                          </td>
                          <td className="p-4 text-center font-mono font-bold text-amber-500 text-sm">
                            {Math.round(item.similarity * 100)}%
                          </td>
                          <td className="p-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                onClick={() => handleResolveIgnore("insight", item.id1, item.id2)}
                                variant="outline"
                                size="sm"
                                className="h-7 text-[11px] px-2"
                              >
                                Ignore
                              </Button>
                              <Button
                                onClick={() => handleOpenInsightMerge(item)}
                                size="sm"
                                className="h-7 text-[11px] px-2.5"
                              >
                                Merge
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {mergeState?.isOpen && (
        <MergeModal
          isOpen={mergeState.isOpen}
          onClose={() => setMergeState(null)}
          entityType={mergeState.entityType}
          item1={mergeState.item1}
          item2={mergeState.item2}
          onConfirm={handleResolveMerge}
        />
      )}
    </div>
  );
}



export default function SettingsPage() {
  const { data: jobs, error, mutate } = useSWR<Job[]>(`${API_BASE}/api/scheduler/jobs`, fetcher);
  const [historyJobId, setHistoryJobId] = useState<string | null>(null);
  const [historyJobName, setHistoryJobName] = useState<string | null>(null);

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

      <Tabs defaultValue="scheduler" className="w-full">
        <TabsList className="border-b border-border/60 pb-px mb-4">
          <TabsTrigger value="scheduler">Ingestion Scheduler</TabsTrigger>
          <TabsTrigger value="glossary">Entity Glossary</TabsTrigger>
          <TabsTrigger value="quotas">Model Quotas & Allocation</TabsTrigger>
          <TabsTrigger value="sources">Primary Sources</TabsTrigger>
          <TabsTrigger value="divergence">Divergence Monitor</TabsTrigger>
        </TabsList>

        <TabsContent value="scheduler" className="space-y-6 mt-4">
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
                <JobCard 
                  key={job.id} 
                  job={job} 
                  onRefresh={handleRefresh} 
                  onViewHistory={(id, name) => {
                    setHistoryJobId(id);
                    setHistoryJobName(name);
                  }}
                />
              ))}
            </div>
          )}

          {historyJobId && historyJobName && (
            <HistoryDrawer 
              jobId={historyJobId} 
              jobName={historyJobName} 
              onClose={() => {
                setHistoryJobId(null);
                setHistoryJobName(null);
              }} 
            />
          )}
        </TabsContent>

        <TabsContent value="glossary" className="space-y-6 mt-4">
          <GlossaryTab />
        </TabsContent>

        <TabsContent value="quotas" className="space-y-6 mt-4">
          <ModelQuotasTab />
        </TabsContent>

        <TabsContent value="divergence" className="space-y-6 mt-4">
          <DivergenceTab />
        </TabsContent>

        <TabsContent value="sources" className="space-y-6 mt-4">
          <PrimarySourcesTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
