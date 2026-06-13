/* eslint-disable react-hooks/set-state-in-effect, @typescript-eslint/no-explicit-any */
import React, { useState } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, RefreshCw, Save, RotateCcw, ShieldCheck, Key, DollarSign, Cpu, Clock, Database } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QuotaLimit {
  rpm: number | null;
  tpm: number | null;
  rpd: number | null;
}

interface ModelQuota {
  rpm: number;
  tpm: number;
  rpd: number;
  cost: number;
  prompt_tokens: number;
  completion_tokens: number;
  status: string;
  error_message: string;
  limits: QuotaLimit;
}

interface ModelsResponse {
  allocations: {
    LLM_CLASSIFY_MODEL: string;
    LLM_SUMMARIZE_MODEL: string;
    LLM_ANALYSIS_MODEL: string;
    LLM_RELEVANCE_MODEL: string;
    LLM_EMBED_MODEL: string;
    LLM_EMBED_FALLBACK_MODEL: string;
    LLM_LIGHTWEIGHT_FALLBACK_MODEL: string;
    LLM_REASONING_FALLBACK_MODEL: string;
    DAILY_SPEND_LIMIT: number;
    LLM_PACING_DELAY?: string;
    MAX_ANALYSIS_DURATION_MINUTES?: number;
    ANALYSIS_BATCH_SIZE?: number;
  };
  available_models: string[];
  keys: {
    gemini: boolean;
    openai: boolean;
    anthropic: boolean;
    deepseek: boolean;
  };
}

export function ModelQuotasTab() {
  const [autoRefresh, setAutoRefresh] = useState(false);
  // Fetch quota metrics with conditional auto-refresh interval
  const { data: quotasData, error: quotasError, mutate: mutateQuotas } = useSWR<Record<string, ModelQuota>>(
    `${API_BASE}/api/system/quotas`,
    fetcher,
    { refreshInterval: autoRefresh ? 3000 : 0 }
  );

  // Fetch model allocations
  const { data: modelsData, error: modelsError, mutate: mutateModels } = useSWR<ModelsResponse>(
    `${API_BASE}/api/system/models`,
    fetcher
  );

  // Form states for allocation overrides
  const [classifyModel, setClassifyModel] = useState("");
  const [summarizeModel, setSummarizeModel] = useState("");
  const [analysisModel, setAnalysisModel] = useState("");
  const [relevanceModel, setRelevanceModel] = useState("");
  const [embedModel, setEmbedModel] = useState("");
  const [embedFallbackModel, setEmbedFallbackModel] = useState("");
  const [lightweightFallbackModel, setLightweightFallbackModel] = useState("");
  const [reasoningFallbackModel, setReasoningFallbackModel] = useState("");
  const [dailySpendLimit, setDailySpendLimit] = useState("5.00");
  const [pacingDelay, setPacingDelay] = useState("auto");
  const [maxAnalysisDurationMinutes, setMaxAnalysisDurationMinutes] = useState("25");
  const [analysisBatchSize, setAnalysisBatchSize] = useState("20");

  // States for handling custom text inputs
  const [customClassify, setCustomClassify] = useState("");
  const [customSummarize, setCustomSummarize] = useState("");
  const [customAnalysis, setCustomAnalysis] = useState("");
  const [customRelevance, setCustomRelevance] = useState("");
  const [customEmbed, setCustomEmbed] = useState("");
  const [customEmbedFallback, setCustomEmbedFallback] = useState("");
  const [customLightweightFallback, setCustomLightweightFallback] = useState("");
  const [customReasoningFallback, setCustomReasoningFallback] = useState("");
  const [customPacingDelay, setCustomPacingDelay] = useState("");

  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Initialize form state once models data is loaded
  React.useEffect(() => {
    if (modelsData?.allocations) {
      const { available_models, allocations } = modelsData;
      
      const initSelect = (val: string | undefined, setSelect: (v: string) => void, setCustom: (v: string) => void) => {
        if (!val) {
          setSelect("");
          setCustom("");
          return;
        }
        if (available_models && available_models.includes(val)) {
          setSelect(val);
          setCustom("");
        } else {
          setSelect("custom");
          setCustom(val);
        }
      };

      initSelect(allocations.LLM_CLASSIFY_MODEL, setClassifyModel, setCustomClassify);
      initSelect(allocations.LLM_SUMMARIZE_MODEL, setSummarizeModel, setCustomSummarize);
      initSelect(allocations.LLM_ANALYSIS_MODEL, setAnalysisModel, setCustomAnalysis);
      initSelect(allocations.LLM_RELEVANCE_MODEL, setRelevanceModel, setCustomRelevance);
      initSelect(allocations.LLM_EMBED_MODEL, setEmbedModel, setCustomEmbed);
      initSelect(allocations.LLM_EMBED_FALLBACK_MODEL, setEmbedFallbackModel, setCustomEmbedFallback);
      initSelect(allocations.LLM_LIGHTWEIGHT_FALLBACK_MODEL, setLightweightFallbackModel, setCustomLightweightFallback);
      initSelect(allocations.LLM_REASONING_FALLBACK_MODEL, setReasoningFallbackModel, setCustomReasoningFallback);
      
      if (allocations.DAILY_SPEND_LIMIT !== undefined && allocations.DAILY_SPEND_LIMIT !== null) {
        setDailySpendLimit(allocations.DAILY_SPEND_LIMIT.toFixed(2));
      }

      if (allocations.LLM_PACING_DELAY !== undefined && allocations.LLM_PACING_DELAY !== null) {
        const pacingVal = allocations.LLM_PACING_DELAY;
        if (["auto", "0.0", "2.0", "4.0"].includes(pacingVal)) {
          setPacingDelay(pacingVal);
          setCustomPacingDelay("");
        } else {
          setPacingDelay("custom");
          setCustomPacingDelay(pacingVal);
        }
      } else {
        setPacingDelay("auto");
        setCustomPacingDelay("");
      }

      if (allocations.MAX_ANALYSIS_DURATION_MINUTES !== undefined && allocations.MAX_ANALYSIS_DURATION_MINUTES !== null) {
        setMaxAnalysisDurationMinutes(allocations.MAX_ANALYSIS_DURATION_MINUTES.toString());
      }
      if (allocations.ANALYSIS_BATCH_SIZE !== undefined && allocations.ANALYSIS_BATCH_SIZE !== null) {
        setAnalysisBatchSize(allocations.ANALYSIS_BATCH_SIZE.toString());
      }
    }
  }, [modelsData]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setStatusMsg(null);

    const getFinalVal = (selectVal: string | undefined, customVal: string | undefined) => {
      if (!selectVal) return "";
      return selectVal === "custom" ? (customVal || "").trim() : selectVal;
    };

    const limitVal = parseFloat(dailySpendLimit);
    if (isNaN(limitVal) || limitVal < 0) {
      setStatusMsg({ text: "Daily spend limit must be a positive number.", type: "error" });
      setIsSaving(false);
      return;
    }

    if (pacingDelay === "custom") {
      const parsed = parseFloat(customPacingDelay);
      if (isNaN(parsed) || parsed < 0) {
        setStatusMsg({ text: "Custom pacing delay must be a positive number.", type: "error" });
        setIsSaving(false);
        return;
      }
    }

    const durationVal = parseInt(maxAnalysisDurationMinutes);
    if (isNaN(durationVal) || durationVal <= 0) {
      setStatusMsg({ text: "Max analysis duration must be a positive number.", type: "error" });
      setIsSaving(false);
      return;
    }

    const batchVal = parseInt(analysisBatchSize);
    if (isNaN(batchVal) || batchVal <= 0) {
      setStatusMsg({ text: "Analysis batch size must be a positive number.", type: "error" });
      setIsSaving(false);
      return;
    }

    const modelAllocations = {
      LLM_CLASSIFY_MODEL: getFinalVal(classifyModel, customClassify),
      LLM_SUMMARIZE_MODEL: getFinalVal(summarizeModel, customSummarize),
      LLM_ANALYSIS_MODEL: getFinalVal(analysisModel, customAnalysis),
      LLM_RELEVANCE_MODEL: getFinalVal(relevanceModel, customRelevance),
      LLM_EMBED_MODEL: getFinalVal(embedModel, customEmbed),
      LLM_EMBED_FALLBACK_MODEL: getFinalVal(embedFallbackModel, customEmbedFallback),
      LLM_LIGHTWEIGHT_FALLBACK_MODEL: getFinalVal(lightweightFallbackModel, customLightweightFallback),
      LLM_REASONING_FALLBACK_MODEL: getFinalVal(reasoningFallbackModel, customReasoningFallback),
    };

    if (Object.values(modelAllocations).some(val => val === "" || val === undefined)) {
      setStatusMsg({ text: "All model fields are required.", type: "error" });
      setIsSaving(false);
      return;
    }

    const payload = {
      ...modelsData?.allocations,
      ...modelAllocations,
      DAILY_SPEND_LIMIT: limitVal,
      LLM_PACING_DELAY: pacingDelay === "custom" ? customPacingDelay.trim() : pacingDelay,
      MAX_ANALYSIS_DURATION_MINUTES: durationVal,
      ANALYSIS_BATCH_SIZE: batchVal,
    };

    try {
      const res = await fetch(`${API_BASE}/api/system/models`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        let errMsg = "Failed to update allocations.";
        if (typeof data.detail === "string") {
          errMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          errMsg = data.detail.map((e: any) => `${e.loc.join(".")}: ${e.msg}`).join(", ");
        } else if (data.detail && typeof data.detail === "object") {
          errMsg = JSON.stringify(data.detail);
        }
        throw new Error(errMsg);
      }

      setStatusMsg({ text: "Configurations saved successfully!", type: "success" });
      mutateModels();
      mutateQuotas();
    } catch (err: any) {
      setStatusMsg({ text: err.message || "Failed to save settings.", type: "error" });
    } finally {
      setIsSaving(false);
    }
  };

  const handleResetMetrics = async () => {
    if (!confirm("Are you sure you want to reset all rolling model quota metrics and costs in memory?")) {
      return;
    }
    setIsResetting(true);
    try {
      const res = await fetch(`${API_BASE}/api/system/quotas/reset`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to reset metrics.");
      mutateQuotas();
      alert("In-memory quota and cost metrics have been reset.");
    } catch (err: any) {
      alert(err.message || "Error resetting metrics.");
    } finally {
      setIsResetting(false);
    }
  };

  // Helper to get which tasks are mapped to a specific model name
  const getMappedTasks = (modelName: string) => {
    if (!modelsData?.allocations) return [];
    const tasks: string[] = [];
    const allocs = modelsData.allocations;
    if (allocs.LLM_CLASSIFY_MODEL === modelName) tasks.push("Classification");
    if (allocs.LLM_SUMMARIZE_MODEL === modelName) tasks.push("Summarization");
    if (allocs.LLM_ANALYSIS_MODEL === modelName) tasks.push("Deep Analysis");
    if (allocs.LLM_RELEVANCE_MODEL === modelName) tasks.push("Relevance Filter");
    if (allocs.LLM_EMBED_MODEL === modelName) tasks.push("Primary Embedding");
    if (allocs.LLM_EMBED_FALLBACK_MODEL === modelName) tasks.push("Fallback Embedding");
    if (allocs.LLM_LIGHTWEIGHT_FALLBACK_MODEL === modelName) tasks.push("Lightweight Fallback");
    if (allocs.LLM_REASONING_FALLBACK_MODEL === modelName) tasks.push("Reasoning Fallback");
    return tasks;
  };

  const formatLimitVal = (val: number | null) => {
    if (val === null) return "Unlimited";
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(0)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`;
    return val.toString();
  };

  const formatCurrentVal = (val: number) => {
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(1)}K`;
    return val.toString();
  };

  const getProgressBarColor = (current: number, limit: number | null, status: string) => {
    if (status === "rate_limited" || status === "error") return "bg-rose-500";
    if (!limit) return "bg-slate-400";
    const percent = (current / limit) * 100;
    if (percent >= 90) return "bg-rose-500";
    if (percent >= 70) return "bg-amber-500";
    return "bg-emerald-500";
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "rate_limited":
        return <Badge className="bg-rose-500/10 text-rose-500 border-rose-500/20 hover:bg-rose-500/20">Rate Limited</Badge>;
      case "error":
        return <Badge className="bg-red-500/10 text-red-500 border-red-500/20 hover:bg-red-500/20">Error</Badge>;
      case "healthy":
      default:
        return <Badge className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 hover:bg-emerald-500/20">Healthy</Badge>;
    }
  };

  const availableModels = modelsData?.available_models || [];

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-5">
        
        {/* Model Allocation Card (Form) */}
        <Card className="md:col-span-2 border border-border bg-card shadow-sm h-fit">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" /> Model Allocation Configuration
            </CardTitle>
            <CardDescription className="text-xs">
              Assign specific models to each AI task in the pipeline.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {modelsError && (
              <p className="text-xs text-rose-500 mb-4">Failed to load allocations. Check server status.</p>
            )}
            {!modelsData && !modelsError && (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {modelsData && (
              <form onSubmit={handleSave} className="space-y-4">
                
                {/* News Processing Pipeline Flowchart */}
                <div className="p-4 bg-muted/20 border border-border/80 rounded-xl space-y-4">
                  <div className="text-xs font-bold text-foreground flex items-center gap-1.5 mb-1">
                    <Cpu className="h-4 w-4 text-primary animate-pulse" /> News Processing Pipeline
                  </div>
                  
                  <div className="space-y-4">
                    {/* Stage 1: News Pre-processing */}
                    <div className="p-3 bg-indigo-500/5 dark:bg-indigo-500/10 border-l-4 border-indigo-500 rounded-r-xl space-y-2">
                      <div className="text-[10px] font-extrabold text-indigo-600 dark:text-indigo-400 tracking-wider uppercase flex items-center gap-1">
                        Stage 1: Pre-processing
                      </div>
                      <div className="relative pl-3 border-l border-indigo-500/20 ml-1">
                        <div className="relative group flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground flex items-center gap-2 cursor-help select-none">
                            Relevance Filter
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono font-normal bg-background/50 leading-tight whitespace-nowrap overflow-hidden text-ellipsis max-w-[150px]">
                              {relevanceModel === "custom" ? customRelevance || "Custom" : relevanceModel.replace("gemini/", "").replace("ollama/", "")}
                            </Badge>
                          </span>
                          {/* Hover Tooltip */}
                          <div className="absolute z-30 hidden group-hover:block w-52 p-2 bg-popover border border-border text-popover-foreground text-[11px] font-normal leading-relaxed rounded-lg shadow-lg right-2 -top-1 backdrop-blur-sm">
                            Filters incoming news feeds to keep only Global Affairs, Macro Policy, and Financial News, discarding noise.
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Stage 2: AI Analysis */}
                    <div className="p-3 bg-violet-500/5 dark:bg-violet-500/10 border-l-4 border-violet-500 rounded-r-xl space-y-2.5">
                      <div className="text-[10px] font-extrabold text-violet-600 dark:text-violet-400 tracking-wider uppercase flex items-center gap-1">
                        Stage 2: AI Analysis
                      </div>
                      <div className="relative pl-3 border-l border-violet-500/20 ml-1 space-y-3">
                        
                        {/* Summarization */}
                        <div className="relative group flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground flex items-center gap-2 cursor-help select-none">
                            Summarization
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono font-normal bg-background/50 leading-tight whitespace-nowrap overflow-hidden text-ellipsis max-w-[150px]">
                              {summarizeModel === "custom" ? customSummarize || "Custom" : summarizeModel.replace("gemini/", "").replace("ollama/", "")}
                            </Badge>
                          </span>
                          {/* Hover Tooltip */}
                          <div className="absolute z-30 hidden group-hover:block w-52 p-2 bg-popover border border-border text-popover-foreground text-[11px] font-normal leading-relaxed rounded-lg shadow-lg right-2 -top-1 backdrop-blur-sm">
                            Generates a concise, structured bilingual summary capturing core facts, numbers, and key entities.
                          </div>
                        </div>

                        {/* Classification */}
                        <div className="relative group flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground flex items-center gap-2 cursor-help select-none">
                            Classification
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono font-normal bg-background/50 leading-tight whitespace-nowrap overflow-hidden text-ellipsis max-w-[150px]">
                              {classifyModel === "custom" ? customClassify || "Custom" : classifyModel.replace("gemini/", "").replace("ollama/", "")}
                            </Badge>
                          </span>
                          {/* Hover Tooltip */}
                          <div className="absolute z-30 hidden group-hover:block w-52 p-2 bg-popover border border-border text-popover-foreground text-[11px] font-normal leading-relaxed rounded-lg shadow-lg right-2 -top-1 backdrop-blur-sm">
                            Assigns macro/sector categories, sentiment score (bullish/bearish), and urgency indicators.
                          </div>
                        </div>

                        {/* Deep Analysis */}
                        <div className="relative group flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground flex items-center gap-2 cursor-help select-none">
                            Deep Analysis
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono font-normal bg-background/50 leading-tight whitespace-nowrap overflow-hidden text-ellipsis max-w-[150px]">
                              {analysisModel === "custom" ? customAnalysis || "Custom" : analysisModel.replace("gemini/", "").replace("ollama/", "")}
                            </Badge>
                          </span>
                          {/* Hover Tooltip */}
                          <div className="absolute z-30 hidden group-hover:block w-52 p-2 bg-popover border border-border text-popover-foreground text-[11px] font-normal leading-relaxed rounded-lg shadow-lg right-2 -top-1 backdrop-blur-sm">
                            Extracts deeper context and maps narrative threads or facts into the Insight Vault.
                          </div>
                        </div>

                      </div>
                    </div>

                    {/* Shared Service: Vector Embedding */}
                    <div className="p-3 bg-emerald-500/5 dark:bg-emerald-500/10 border-l-4 border-emerald-500 rounded-r-xl space-y-2">
                      <div className="text-[10px] font-extrabold text-emerald-600 dark:text-emerald-400 tracking-wider uppercase flex items-center gap-1">
                        Shared: Vector Indexing Service
                      </div>
                      <div className="relative pl-3 border-l border-emerald-500/20 ml-1">
                        <div className="relative group flex items-center justify-between">
                          <span className="text-xs font-semibold text-foreground flex items-center gap-2 cursor-help select-none">
                            Primary Embedding
                            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-mono font-normal bg-background/50 leading-tight whitespace-nowrap overflow-hidden text-ellipsis max-w-[150px]">
                              {embedModel === "custom" ? customEmbed || "Custom" : embedModel.replace("gemini/", "").replace("ollama/", "")}
                            </Badge>
                          </span>
                          {/* Hover Tooltip */}
                          <div className="absolute z-30 hidden group-hover:block w-52 p-2 bg-popover border border-border text-popover-foreground text-[11px] font-normal leading-relaxed rounded-lg shadow-lg right-2 -top-1 backdrop-blur-sm">
                            Converts structured insights into semantic vectors using the embedding model for Qdrant storage and retrieval.
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                </div>

                {/* API Key Status Badges */}
                <div className="p-3 bg-muted/30 border border-muted-foreground/10 rounded-lg space-y-2">
                  <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5 mb-1.5">
                    <Key className="h-3.5 w-3.5" /> API Key Status (.env)
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="flex items-center justify-between p-1.5 bg-background rounded border border-border/40">
                      <span className="font-medium">Gemini</span>
                      {modelsData?.keys?.gemini ? (
                        <Badge className="bg-emerald-500/10 text-emerald-500 text-[10px] hover:bg-emerald-500/10 border-none px-1.5 py-0 font-normal">Active</Badge>
                      ) : (
                        <Badge className="bg-muted text-muted-foreground text-[10px] hover:bg-muted border-none px-1.5 py-0 font-normal">Missing</Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between p-1.5 bg-background rounded border border-border/40">
                      <span className="font-medium">OpenAI</span>
                      {modelsData?.keys?.openai ? (
                        <Badge className="bg-emerald-500/10 text-emerald-500 text-[10px] hover:bg-emerald-500/10 border-none px-1.5 py-0 font-normal">Active</Badge>
                      ) : (
                        <Badge className="bg-muted text-muted-foreground text-[10px] hover:bg-muted border-none px-1.5 py-0 font-normal">Missing</Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between p-1.5 bg-background rounded border border-border/40">
                      <span className="font-medium">Anthropic</span>
                      {modelsData?.keys?.anthropic ? (
                        <Badge className="bg-emerald-500/10 text-emerald-500 text-[10px] hover:bg-emerald-500/10 border-none px-1.5 py-0 font-normal">Active</Badge>
                      ) : (
                        <Badge className="bg-muted text-muted-foreground text-[10px] hover:bg-muted border-none px-1.5 py-0 font-normal">Missing</Badge>
                      )}
                    </div>
                    <div className="flex items-center justify-between p-1.5 bg-background rounded border border-border/40">
                      <span className="font-medium">DeepSeek</span>
                      {modelsData?.keys?.deepseek ? (
                        <Badge className="bg-emerald-500/10 text-emerald-500 text-[10px] hover:bg-emerald-500/10 border-none px-1.5 py-0 font-normal">Active</Badge>
                      ) : (
                        <Badge className="bg-muted text-muted-foreground text-[10px] hover:bg-muted border-none px-1.5 py-0 font-normal">Missing</Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Visual Stage Configurations */}
                <div className="border-t border-border/60 pt-4 space-y-4">
                  
                  {/* Stage 1: Pre-processing Models */}
                  <div className="p-3.5 bg-indigo-500/5 dark:bg-indigo-500/10 border-l-4 border-indigo-500 rounded-r-xl space-y-3 shadow-sm">
                    <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wide">
                      Stage 1: Pre-processing Models
                    </div>

                    {/* Relevance Filter Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Relevance Filter Model</label>
                      <select
                        value={relevanceModel}
                        onChange={(e) => setRelevanceModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {relevanceModel === "custom" && (
                        <Input
                          value={customRelevance}
                          onChange={(e) => setCustomRelevance(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Lightweight Fallback Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Lightweight Fallback Model (Cheap Failover)</label>
                      <select
                        value={lightweightFallbackModel}
                        onChange={(e) => setLightweightFallbackModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {lightweightFallbackModel === "custom" && (
                        <Input
                          value={customLightweightFallback}
                          onChange={(e) => setCustomLightweightFallback(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>
                  </div>

                  {/* Stage 2: AI Analysis Models */}
                  <div className="p-3.5 bg-violet-500/5 dark:bg-violet-500/10 border-l-4 border-violet-500 rounded-r-xl space-y-3 shadow-sm">
                    <div className="text-xs font-bold text-violet-600 dark:text-violet-400 uppercase tracking-wide">
                      Stage 2: AI Analysis Models
                    </div>

                    {/* Summarization Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Summarization Task Model</label>
                      <select
                        value={summarizeModel}
                        onChange={(e) => setSummarizeModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {summarizeModel === "custom" && (
                        <Input
                          value={customSummarize}
                          onChange={(e) => setCustomSummarize(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Classification Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Classification Task Model</label>
                      <select
                        value={classifyModel}
                        onChange={(e) => setClassifyModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {classifyModel === "custom" && (
                        <Input
                          value={customClassify}
                          onChange={(e) => setCustomClassify(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Deep Analysis Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Deep Analysis Task Model</label>
                      <select
                        value={analysisModel}
                        onChange={(e) => setAnalysisModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {analysisModel === "custom" && (
                        <Input
                          value={customAnalysis}
                          onChange={(e) => setCustomAnalysis(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Reasoning Fallback Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Reasoning Fallback Model (Powerful Failover)</label>
                      <select
                        value={reasoningFallbackModel}
                        onChange={(e) => setReasoningFallbackModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {reasoningFallbackModel === "custom" && (
                        <Input
                          value={customReasoningFallback}
                          onChange={(e) => setCustomReasoningFallback(e.target.value)}
                          placeholder="e.g. ollama/gemma4:12b"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>
                  </div>

                  {/* Shared: Vector Indexing Service */}
                  <div className="p-3.5 bg-emerald-500/5 dark:bg-emerald-500/10 border-l-4 border-emerald-500 rounded-r-xl space-y-3 shadow-sm">
                    <div className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide">
                      Shared: Vector Indexing Service
                    </div>

                    {/* Primary Embedding Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Primary Embedding Model</label>
                      <select
                        value={embedModel}
                        onChange={(e) => setEmbedModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {embedModel === "custom" && (
                        <Input
                          value={customEmbed}
                          onChange={(e) => setCustomEmbed(e.target.value)}
                          placeholder="e.g. ollama/nomic-embed-text"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Fallback Embedding Model */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground">Fallback Embedding Model</label>
                      <select
                        value={embedFallbackModel}
                        onChange={(e) => setEmbedFallbackModel(e.target.value)}
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {availableModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                        <option value="custom">Custom string...</option>
                      </select>
                      {embedFallbackModel === "custom" && (
                        <Input
                          value={customEmbedFallback}
                          onChange={(e) => setCustomEmbedFallback(e.target.value)}
                          placeholder="e.g. ollama/nomic-embed-text"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>
                  </div>

                  {/* Pacing & Safety Controls */}
                  <div className="p-3.5 bg-muted/20 border-l-4 border-muted rounded-r-xl space-y-3 shadow-sm">
                    <div className="text-xs font-bold text-muted-foreground uppercase tracking-wide">
                      Pacing & Safety Controls
                    </div>

                    {/* Daily Spend Limit */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground flex items-center gap-1 text-amber-500">
                        <DollarSign className="h-3.5 w-3.5" /> Daily API Spend Limit (USD)
                      </label>
                      <Input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={dailySpendLimit}
                        onChange={(e) => setDailySpendLimit(e.target.value)}
                        placeholder="5.00"
                        className="h-9"
                      />
                    </div>

                    {/* Task Pacing Delay */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground flex items-center gap-1 text-primary">
                        <Cpu className="h-3.5 w-3.5" /> Task Pacing Delay
                      </label>
                      <select
                        value={pacingDelay}
                        onChange={(e) => setPacingDelay(e.target.value)}
                        aria-label="Task Pacing Delay"
                        className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        <option value="auto">Auto (Ollama: 0s, Gemini Free: 4s)</option>
                        <option value="0.0">No Delay (0.0s)</option>
                        <option value="2.0">Medium Delay (2.0s)</option>
                        <option value="4.0">Safe Delay (4.0s)</option>
                        <option value="custom">Custom seconds...</option>
                      </select>
                      {pacingDelay === "custom" && (
                        <Input
                          type="number"
                          step="0.1"
                          min="0.0"
                          value={customPacingDelay}
                          onChange={(e) => setCustomPacingDelay(e.target.value)}
                          placeholder="e.g. 1.5"
                          className="h-8 text-xs mt-1.5"
                        />
                      )}
                    </div>

                    {/* Max Analysis Duration */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground flex items-center gap-1 text-primary">
                        <Clock className="h-3.5 w-3.5" /> Max Analysis Duration (Minutes)
                      </label>
                      <Input
                        type="number"
                        min="1"
                        value={maxAnalysisDurationMinutes}
                        onChange={(e) => setMaxAnalysisDurationMinutes(e.target.value)}
                        placeholder="25"
                        className="h-9"
                      />
                    </div>

                    {/* Analysis Batch Size */}
                    <div className="space-y-1">
                      <label className="text-xs font-semibold text-foreground flex items-center gap-1 text-primary">
                        <Database className="h-3.5 w-3.5" /> Analysis Batch Size
                      </label>
                      <Input
                        type="number"
                        min="1"
                        value={analysisBatchSize}
                        onChange={(e) => setAnalysisBatchSize(e.target.value)}
                        placeholder="20"
                        className="h-9"
                      />
                    </div>
                  </div>
                </div>


                {/* Feedback message */}
                {statusMsg && (
                  <div className={`p-2.5 rounded text-xs border ${
                    statusMsg.type === "success" 
                      ? "bg-emerald-500/5 text-emerald-600 border-emerald-500/20" 
                      : "bg-rose-500/5 text-rose-600 border-rose-500/20"
                  }`}>
                    {statusMsg.text}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={isSaving}
                  className="w-full text-xs h-9 gap-1.5 font-bold mt-2"
                >
                  {isSaving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  Save Configuration
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
        
        {/* Real-time Quota Table Card */}
        <Card className="md:col-span-3 border border-border bg-card shadow-sm h-fit">
          <CardHeader className="pb-4 border-b border-border/60 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <RefreshCw className={`h-5 w-5 text-primary ${autoRefresh ? "animate-spin" : ""}`} /> Model Quota & Cost Status
              </CardTitle>
              <CardDescription className="text-xs">
                Real-time rolling RPM/TPM and daily budget tracking matching your configured limits.
              </CardDescription>
            </div>
            
            <div className="flex items-center gap-4 shrink-0">
              <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground select-none cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded border-input text-primary focus:ring-ring h-3.5 w-3.5"
                />
                Auto Refresh (3s)
              </label>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResetMetrics}
                disabled={isResetting}
                className="h-8 text-[11px] gap-1 border-muted-foreground/20 text-muted-foreground hover:text-foreground"
              >
                <RotateCcw className="h-3 w-3" /> Reset
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {quotasError && (
              <p className="text-xs text-rose-500 p-4">Failed to fetch model quota metrics. Check server status.</p>
            )}
            {!quotasData && !quotasError && (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            )}
            {quotasData && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-border bg-muted/20 text-muted-foreground font-semibold uppercase tracking-wider">
                      <th className="p-4 w-[28%]">Model Name</th>
                      <th className="p-4 w-[22%]">Mapped Task</th>
                      <th className="p-4 w-[16%]">RPM / Cost</th>
                      <th className="p-4 w-[16%]">TPM / Prompt Tokens</th>
                      <th className="p-4 w-[18%]">RPD / Completion</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {Object.entries(quotasData).length === 0 ? (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-muted-foreground italic">
                          No models currently tracked. Trigger a job to log metrics.
                        </td>
                      </tr>
                    ) : (
                      Object.entries(quotasData).map(([modelName, quota]) => {
                        const mappedTasks = getMappedTasks(modelName);
                        
                        const isOllama = modelName.startsWith("ollama/");
                        const isPaid = modelName.startsWith("openai/") || modelName.startsWith("anthropic/") || modelName.startsWith("deepseek/") || quota.cost > 0;
                        
                        const rpmLim = quota.limits.rpm;
                        const tpmLim = quota.limits.tpm;
                        const rpdLim = quota.limits.rpd;

                        const rpmVal = quota.rpm;
                        const tpmVal = quota.tpm;
                        const rpdVal = quota.rpd;

                        const rpmPercent = rpmLim ? Math.min(100, (rpmVal / rpmLim) * 100) : 0;
                        const tpmPercent = tpmLim ? Math.min(100, (tpmVal / tpmLim) * 100) : 0;
                        const rpdPercent = rpdLim ? Math.min(100, (rpdVal / rpdLim) * 100) : 0;

                        const limitNum = parseFloat(dailySpendLimit) || 5.00;
                        const budgetPercent = Math.min(100, (quota.cost / limitNum) * 100);

                        return (
                          <tr key={modelName} className="hover:bg-muted/10 transition-colors">
                            
                            {/* Model Name & Status */}
                            <td className="p-4 font-mono font-medium text-foreground leading-normal whitespace-pre-wrap break-all">
                              <div>{modelName.replace("gemini/", "")}</div>
                              <div className="mt-1 flex items-center gap-1.5">
                                {getStatusBadge(quota.status)}
                                {isOllama && <Badge className="bg-blue-500/10 text-blue-500 border-none font-normal text-[10px] px-1 py-0 select-none">Local</Badge>}
                                {isPaid && !isOllama && <Badge className="bg-amber-500/10 text-amber-500 border-none font-normal text-[10px] px-1 py-0 select-none">Paid API</Badge>}
                              </div>
                              {quota.error_message && (
                                <div className="text-[10px] text-rose-500 font-normal mt-1 leading-tight max-w-[200px]">
                                  {quota.error_message}
                                </div>
                              )}
                            </td>

                            {/* Mapped Tasks */}
                            <td className="p-4">
                              {mappedTasks.length === 0 ? (
                                <span className="text-muted-foreground italic">Unassigned</span>
                              ) : (
                                <div className="flex flex-wrap gap-1">
                                  {mappedTasks.map((t) => (
                                    <Badge key={t} variant="secondary" className="text-[10px] py-0 px-1.5 font-normal">
                                      {t}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </td>

                            {/* Column 3: RPM / Cost */}
                            <td className="p-4">
                              {isOllama ? (
                                <div className="flex items-center gap-1 text-muted-foreground font-medium">
                                  <Cpu className="h-3.5 w-3.5" /> Local
                                </div>
                              ) : isPaid ? (
                                <div className="flex flex-col gap-0.5">
                                  <span className="text-[10px] text-muted-foreground">Spent Today</span>
                                  <span className="font-semibold text-amber-500 text-xs">${quota.cost.toFixed(4)}</span>
                                </div>
                              ) : (
                                <>
                                  <div className="flex items-center justify-between text-[11px] mb-1 font-semibold">
                                    <span>{rpmVal}</span>
                                    <span className="text-muted-foreground font-normal">/ {formatLimitVal(rpmLim)}</span>
                                  </div>
                                  {rpmLim ? (
                                    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                      <div
                                        className={`h-full rounded-full transition-all duration-300 ${getProgressBarColor(rpmVal, rpmLim, quota.status)}`}
                                        style={{ width: `${rpmPercent}%` }}
                                      />
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-muted-foreground font-mono italic">Unlimited</div>
                                  )}
                                </>
                              )}
                            </td>

                            {/* Column 4: TPM / Prompt Tokens */}
                            <td className="p-4">
                              {isOllama ? (
                                <div className="text-muted-foreground font-medium">Free</div>
                              ) : isPaid ? (
                                <div className="flex flex-col gap-0.5">
                                  <span className="text-[10px] text-muted-foreground">Prompt (In)</span>
                                  <span className="font-medium font-mono text-[11px]">{formatCurrentVal(quota.prompt_tokens)} tokens</span>
                                </div>
                              ) : (
                                <>
                                  <div className="flex items-center justify-between text-[11px] mb-1 font-semibold">
                                    <span>{formatCurrentVal(tpmVal)}</span>
                                    <span className="text-muted-foreground font-normal">/ {formatLimitVal(tpmLim)}</span>
                                  </div>
                                  {tpmLim ? (
                                    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                      <div
                                        className={`h-full rounded-full transition-all duration-300 ${getProgressBarColor(tpmVal, tpmLim, quota.status)}`}
                                        style={{ width: `${tpmPercent}%` }}
                                      />
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-muted-foreground font-mono italic">Unlimited</div>
                                  )}
                                </>
                              )}
                            </td>

                            {/* Column 5: RPD / Completion Tokens */}
                            <td className="p-4">
                              {isOllama ? (
                                <div className="text-muted-foreground font-medium">Unlimited</div>
                              ) : isPaid ? (
                                <div className="flex flex-col gap-1.5">
                                  <div className="flex flex-col gap-0.5">
                                    <span className="text-[10px] text-muted-foreground">Completion (Out)</span>
                                    <span className="font-medium font-mono text-[11px]">{formatCurrentVal(quota.completion_tokens)} tokens</span>
                                  </div>
                                  <div className="space-y-1">
                                    <div className="flex items-center justify-between text-[9px] text-muted-foreground">
                                      <span>Spent vs Limit</span>
                                      <span className="font-semibold">${quota.cost.toFixed(2)} / ${limitNum.toFixed(2)}</span>
                                    </div>
                                    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                      <div
                                        className={`h-full rounded-full transition-all duration-300 ${quota.cost >= limitNum ? "bg-rose-500" : "bg-amber-500"}`}
                                        style={{ width: `${budgetPercent}%` }}
                                      />
                                    </div>
                                  </div>
                                </div>
                              ) : (
                                <>
                                  <div className="flex items-center justify-between text-[11px] mb-1 font-semibold">
                                    <span>{rpdVal}</span>
                                    <span className="text-muted-foreground font-normal">/ {formatLimitVal(rpdLim)}</span>
                                  </div>
                                  {rpdLim ? (
                                    <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                                      <div
                                        className={`h-full rounded-full transition-all duration-300 ${getProgressBarColor(rpdVal, rpdLim, quota.status)}`}
                                        style={{ width: `${rpdPercent}%` }}
                                      />
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-muted-foreground font-mono italic">Unlimited</div>
                                  )}
                                </>
                              )}
                            </td>

                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

      </div>
    </div>
  );
}
