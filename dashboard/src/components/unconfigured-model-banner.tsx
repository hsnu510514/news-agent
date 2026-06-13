"use client";

import React from "react";
import useSWR from "swr";
import Link from "next/link";
import { AlertTriangle, ArrowRight } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ModelsResponse {
  allocations: {
    LLM_CLASSIFY_MODEL: string;
    LLM_SUMMARIZE_MODEL: string;
    LLM_ANALYSIS_MODEL: string;
    LLM_RELEVANCE_MODEL: string;
    LLM_EMBED_MODEL: string;
  };
}

export function UnconfiguredModelBanner() {
  const { data, error } = useSWR<ModelsResponse>(
    `${API_BASE}/api/system/models`,
    fetcher
  );

  if (error || !data || !data.allocations) {
    return null;
  }

  const {
    LLM_CLASSIFY_MODEL,
    LLM_SUMMARIZE_MODEL,
    LLM_ANALYSIS_MODEL,
    LLM_RELEVANCE_MODEL,
    LLM_EMBED_MODEL,
  } = data.allocations;

  const isUnconfigured =
    !LLM_CLASSIFY_MODEL ||
    !LLM_SUMMARIZE_MODEL ||
    !LLM_ANALYSIS_MODEL ||
    !LLM_RELEVANCE_MODEL ||
    !LLM_EMBED_MODEL;

  if (!isUnconfigured) {
    return null;
  }

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 mb-6 border border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-500 rounded-xl shadow-sm animate-in fade-in duration-200">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10 shrink-0">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-500" />
        </div>
        <div className="flex flex-col gap-0.5">
          <h4 className="text-sm font-semibold tracking-tight">Model configurations are incomplete</h4>
          <p className="text-xs text-muted-foreground leading-normal">
            Please configure your model allocations to enable ingestion, relevance filtering, and deep analysis.
          </p>
        </div>
      </div>
      <Link
        href="/settings"
        className="flex items-center gap-1.5 self-stretch sm:self-auto justify-center rounded-lg bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold px-3.5 py-2 transition-all duration-200 shadow-sm shadow-amber-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500 hover:scale-[1.02] active:scale-[0.98]"
      >
        Configure Models
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}
