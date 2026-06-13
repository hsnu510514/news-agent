"use client";

import React, { useState, useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Loader2, Save, AlertTriangle, ShieldCheck, Check, Radio, Globe, Rss, Search, Plus, Trash2 } from "lucide-react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface NewsApiSource {
  id: string;
  name: string;
  description: string;
  url: string;
  category: string;
  language: string;
  country: string;
}

interface NewsApiSourcesResponse {
  sources: NewsApiSource[];
}

interface CustomRssFeed {
  name: string;
  url: string;
  category: string;
  language: string;
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
    LLM_PACING_DELAY: string;
    MAX_ANALYSIS_DURATION_MINUTES: number;
    ANALYSIS_BATCH_SIZE: number;
    NEWSAPI_DOMAINS: string;
    ENABLED_RSS_FEEDS: string;
    CUSTOM_RSS_FEEDS?: string;
    DELETED_RSS_FEEDS?: string;
    ENABLED_COLLECTOR_SOURCES?: string;
  };
  available_models: string[];
  keys: {
    gemini: boolean;
    openai: boolean;
    anthropic: boolean;
    deepseek: boolean;
  };
}

interface CollectorSource {
  name: string;
}

interface CollectorSourcesResponse {
  sources: CollectorSource[];
}


const POPULAR_RSS = [
  "36Kr",
  "华尔街见闻",
  "新浪财经",
  "第一财经",
  "财新网",
  "Bloomberg",
  "CNBC Business",
  "CNBC Markets",
  "FT Markets",
  "Economics - Economist",
];

// Feeds known to have issues (Economist, Caixin, Sina)
const TROUBLED_RSS = [
  "Economics - Economist",
  "财新网",
  "新浪财经"
];

export function PrimarySourcesTab() {
  const { data: modelsData, error: modelsError, mutate: mutateModels } = useSWR<ModelsResponse>(
    `${API_BASE}/api/system/models`,
    fetcher
  );

  const { data: sourcesData } = useSWR<NewsApiSourcesResponse>(
    `${API_BASE}/api/system/newsapi-sources`,
    fetcher
  );

  const { data: collectorSourcesData } = useSWR<CollectorSourcesResponse>(
    `${API_BASE}/api/system/collector-sources`,
    fetcher
  );

  const [newsapiDomains, setNewsapiDomains] = useState("");
  const [enabledRssFeeds, setEnabledRssFeeds] = useState("");
  const [enabledCollectorSources, setEnabledCollectorSources] = useState("");
  const [customRssFeeds, setCustomRssFeeds] = useState<CustomRssFeed[]>([]);
  const [deletedRssFeeds, setDeletedRssFeeds] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const [newsapiSearch, setNewsapiSearch] = useState("");

  // Add RSS Form State
  const [showAddFeedForm, setShowAddFeedForm] = useState(false);
  const [newFeedName, setNewFeedName] = useState("");
  const [newFeedUrl, setNewFeedUrl] = useState("");
  const [newFeedCategory, setNewFeedCategory] = useState("finance");
  const [newFeedLanguage, setNewFeedLanguage] = useState("en");
  const [feedValError, setFeedValError] = useState("");

  // Parse strings to track checkbox states
  const activeDomains = newsapiDomains
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean);

  const activeRss = enabledRssFeeds
    .split(",")
    .map((f) => f.trim().toLowerCase())
    .filter(Boolean);

  const activeCollectorSources = enabledCollectorSources
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);

  const activeDeleted = deletedRssFeeds
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean);

  const visiblePredefinedFeeds = POPULAR_RSS.filter(
    (feed) => !activeDeleted.includes(feed.toLowerCase())
  );

  useEffect(() => {
    if (modelsData?.allocations) {
      setNewsapiDomains(modelsData.allocations.NEWSAPI_DOMAINS || "");
      setEnabledRssFeeds(modelsData.allocations.ENABLED_RSS_FEEDS || "");
      setDeletedRssFeeds(modelsData.allocations.DELETED_RSS_FEEDS || "");
      setEnabledCollectorSources(modelsData.allocations.ENABLED_COLLECTOR_SOURCES || "");
      try {
        const parsed = JSON.parse(modelsData.allocations.CUSTOM_RSS_FEEDS || "[]");
        setCustomRssFeeds(Array.isArray(parsed) ? parsed : []);
      } catch {
        setCustomRssFeeds([]);
      }
    }
  }, [modelsData]);

  const extractDomain = (url: string): string => {
    try {
      if (!url.startsWith("http://") && !url.startsWith("https://")) {
        return url.toLowerCase().trim();
      }
      const u = new URL(url);
      let hostname = u.hostname;
      if (hostname.startsWith("www.")) {
        hostname = hostname.substring(4);
      }
      return hostname.toLowerCase();
    } catch {
      return url
        .replace(/^(https?:\/\/)?(www\.)?/, "")
        .split("/")[0]
        .toLowerCase()
        .trim();
    }
  };

  const handleDomainToggle = (domainOrUrl: string) => {
    const domain = extractDomain(domainOrUrl);
    let updated: string[];
    if (activeDomains.includes(domain)) {
      updated = activeDomains.filter((d) => d !== domain);
    } else {
      updated = [...activeDomains, domain];
    }
    const finalDomains = Array.from(new Set(updated));
    setNewsapiDomains(finalDomains.join(", "));
  };


  const handleRssToggle = (feedName: string) => {
    const nameLower = feedName.toLowerCase();
    const currentList = enabledRssFeeds
      .split(",")
      .map((f) => f.trim())
      .filter(Boolean);
    
    const isCurrentlyActive = currentList.some(f => f.toLowerCase() === nameLower);
    
    let updatedList: string[];
    if (isCurrentlyActive) {
      updatedList = currentList.filter(f => f.toLowerCase() !== nameLower);
    } else {
      const matchedPopular = POPULAR_RSS.find(pr => pr.toLowerCase() === nameLower);
      const matchedCustom = customRssFeeds.find(c => c.name.toLowerCase() === nameLower);
      const feedDisplayName = matchedPopular || (matchedCustom ? matchedCustom.name : feedName);
      
      updatedList = [...currentList, feedDisplayName];
    }
    
    setEnabledRssFeeds(updatedList.join(", "));
  };

  const handleCollectorSourceToggle = (sourceName: string) => {
    const nameLower = sourceName.toLowerCase();
    const currentList = enabledCollectorSources
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    
    const isCurrentlyActive = currentList.some((s) => s.toLowerCase() === nameLower);
    
    let updatedList: string[];
    if (isCurrentlyActive) {
      updatedList = currentList.filter((s) => s.toLowerCase() !== nameLower);
    } else {
      const matchedSource = (collectorSourcesData?.sources || []).find(
        (s) => s.name.toLowerCase() === nameLower
      );
      const displayName = matchedSource ? matchedSource.name : sourceName;
      updatedList = [...currentList, displayName];
    }
    
    setEnabledCollectorSources(updatedList.join(", "));
  };

  const handleAddFeed = (e: React.FormEvent) => {
    e.preventDefault();
    setFeedValError("");
    
    if (!newFeedName.trim() || !newFeedUrl.trim()) {
      setFeedValError("Feed name and URL are required.");
      return;
    }
    
    if (!newFeedUrl.startsWith("http://") && !newFeedUrl.startsWith("https://")) {
      setFeedValError("URL must start with http:// or https://");
      return;
    }
    
    const newFeed: CustomRssFeed = {
      name: newFeedName.trim(),
      url: newFeedUrl.trim(),
      category: newFeedCategory,
      language: newFeedLanguage
    };
    
    const updatedFeeds = [...customRssFeeds, newFeed];
    setCustomRssFeeds(updatedFeeds);
    
    // Automatically enable it
    const currentEnabled = enabledRssFeeds.split(",").map(f => f.trim()).filter(Boolean);
    if (!currentEnabled.some(f => f.toLowerCase() === newFeed.name.toLowerCase())) {
      setEnabledRssFeeds([...currentEnabled, newFeed.name].join(", "));
    }
    
    setNewFeedName("");
    setNewFeedUrl("");
    setNewFeedCategory("finance");
    setNewFeedLanguage("en");
    setShowAddFeedForm(false);
  };

  const handleDeleteCustomFeed = (nameToDelete: string) => {
    const updatedCustom = customRssFeeds.filter(f => f.name !== nameToDelete);
    setCustomRssFeeds(updatedCustom);

    const updatedEnabled = enabledRssFeeds
      .split(",")
      .map(f => f.trim())
      .filter(f => f.toLowerCase() !== nameToDelete.toLowerCase())
      .join(", ");
    setEnabledRssFeeds(updatedEnabled);
  };

  const handleDeletePredefinedFeed = (feedName: string) => {
    const currentDeleted = deletedRssFeeds
      .split(",")
      .map((f) => f.trim())
      .filter(Boolean);
    if (!currentDeleted.some(f => f.toLowerCase() === feedName.toLowerCase())) {
      const updatedDeleted = [...currentDeleted, feedName.toLowerCase()];
      setDeletedRssFeeds(updatedDeleted.join(", "));
    }

    const updatedEnabled = enabledRssFeeds
      .split(",")
      .map((f) => f.trim())
      .filter((f) => f.toLowerCase() !== feedName.toLowerCase())
      .join(", ");
    setEnabledRssFeeds(updatedEnabled);
  };

  const handleSave = async () => {
    if (!modelsData) return;
    setIsSaving(true);
    setStatusMsg(null);

    try {
      const payload = {
        ...modelsData.allocations,
        NEWSAPI_DOMAINS: newsapiDomains
          .split(",")
          .map((d) => d.trim())
          .filter(Boolean)
          .join(","),
        ENABLED_RSS_FEEDS: enabledRssFeeds
          .split(",")
          .map((f) => f.trim())
          .filter(Boolean)
          .join(","),
        CUSTOM_RSS_FEEDS: JSON.stringify(customRssFeeds),
        DELETED_RSS_FEEDS: deletedRssFeeds
          .split(",")
          .map((f) => f.trim())
          .filter(Boolean)
          .join(","),
        ENABLED_COLLECTOR_SOURCES: enabledCollectorSources
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
          .join(","),
      };

      const res = await fetch(`${API_BASE}/api/system/models`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        let errMsg = "Failed to save settings";
        if (typeof data.detail === "string") {
          errMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          errMsg = data.detail.map((e: any) => `${e.loc.join(".")}: ${e.msg}`).join(", ");
        } else if (data.detail && typeof data.detail === "object") {
          errMsg = JSON.stringify(data.detail);
        }
        throw new Error(errMsg);
      }

      setStatusMsg({ text: "Primary sources configuration updated successfully!", type: "success" });
      mutateModels();
    } catch (err: any) {
      setStatusMsg({ text: err.message || "An error occurred while saving settings", type: "error" });
    } finally {
      setIsSaving(false);
    }
  };

  const filteredSources = (sourcesData?.sources || []).filter((source) => {
    const q = newsapiSearch.toLowerCase();
    return (
      source.name.toLowerCase().includes(q) ||
      (source.description && source.description.toLowerCase().includes(q)) ||
      (source.category && source.category.toLowerCase().includes(q))
    );
  });

  if (modelsError) {
    return (
      <div className="rounded-lg bg-rose-500/10 text-rose-500 border border-rose-500/20 p-4 text-sm flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">Failed to load system allocations</p>
          <p className="text-xs opacity-90">Please ensure the backend FastAPI service is running.</p>
        </div>
      </div>
    );
  }

  if (!modelsData) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-border/60 bg-card/50 backdrop-blur-md">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                <Globe className="h-5 w-5 text-primary" /> Primary Source Selection
              </CardTitle>
              <CardDescription>
                Configure which domains NewsAPI queries and which RSS feeds are enabled for ingestion.
              </CardDescription>
            </div>
            <Button
              onClick={handleSave}
              disabled={isSaving}
              size="sm"
              className="gap-1.5 shadow-md shadow-primary/10"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Save className="h-4 w-4" />
              )}
              Save Configuration
            </Button>
          </div>
          {statusMsg && (
            <div
              className={`mt-4 rounded-lg p-3 text-xs flex items-center gap-2 border ${
                statusMsg.type === "success"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                  : "bg-rose-500/10 text-rose-400 border-rose-500/20"
              }`}
            >
              <ShieldCheck className="h-4 w-4 shrink-0" />
              <span>{statusMsg.text}</span>
            </div>
          )}
        </CardHeader>
        <CardContent className="space-y-8">
          {/* NewsAPI Domains Configuration */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground mb-1">
                <Globe className="h-4 w-4 text-sky-400" /> NewsAPI Domain Filter
              </h3>
              <p className="text-xs text-muted-foreground">
                Restrict NewsAPI searches to these domains. If empty, all domains are queried.
              </p>
            </div>

            <div className="relative max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search news agencies..."
                value={newsapiSearch}
                onChange={(e) => setNewsapiSearch(e.target.value)}
                className="pl-9 bg-muted/20 border-border/60 text-sm font-medium focus-visible:ring-primary/30"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-h-[300px] overflow-y-auto pr-1">
              {filteredSources.map((source) => {
                const domain = extractDomain(source.url);
                const active = activeDomains.includes(domain);
                return (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() => handleDomainToggle(source.url)}
                    className={`flex flex-col items-start p-3 rounded-lg border text-left text-xs transition-all duration-200 cursor-pointer ${
                      active
                        ? "bg-primary/10 border-primary text-primary"
                        : "bg-muted/30 border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    }`}
                  >
                    <div className="flex items-center justify-between w-full font-semibold mb-1">
                      <span className="truncate">{source.name}</span>
                      {active && <Check className="h-3.5 w-3.5 text-primary ml-1 shrink-0" />}
                    </div>
                    {source.description && (
                      <p className="text-[10px] text-muted-foreground line-clamp-1 mb-2">
                        {source.description}
                      </p>
                    )}
                    <div className="flex gap-1.5 mt-auto">
                      {source.category && (
                        <Badge variant="outline" className="text-[9px] px-1 py-0 border-border/40 font-medium">
                          {source.category}
                        </Badge>
                      )}
                      {source.language && (
                        <Badge variant="outline" className="text-[9px] px-1 py-0 border-border/40 font-medium uppercase">
                          {source.language}
                        </Badge>
                      )}
                    </div>
                  </button>
                );
              })}
              {filteredSources.length === 0 && (
                <div className="col-span-full py-8 text-center text-xs text-muted-foreground">
                  No news agencies found matching your search.
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-muted-foreground block">
                Custom / Comma-separated Domains:
              </label>
              <Input
                placeholder="e.g. bloomberg.com, reuters.com, wsj.com"
                value={newsapiDomains}
                onChange={(e) => setNewsapiDomains(e.target.value)}
                className="bg-muted/20 border-border/60 text-sm font-medium focus-visible:ring-primary/30"
              />
            </div>
          </div>

          <hr className="border-border/60" />

          {/* RSS Feeds Configuration */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground mb-1">
                <Rss className="h-4 w-4 text-amber-500" /> RSS Feed Ingestion Whitelist
              </h3>
              <p className="text-xs text-muted-foreground">
                Select which RSS feeds to pull articles from. Unchecked feeds are skipped during scheduler execution.
              </p>
            </div>

            {/* Troubled Feeds Warning Banner */}
            <div className="rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 p-3.5 text-xs flex items-start gap-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
              <div>
                <p className="font-semibold text-amber-300">Feed Connection Notices</p>
                <p className="opacity-90 leading-relaxed mt-0.5">
                  The <strong>Economist</strong>, <strong>Caixin (财新网)</strong>, and <strong>Sina (新浪财经)</strong> feeds currently experience periodic timeout or network access limits. If you enable them, please check the system logs in case of fetch failures.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {visiblePredefinedFeeds.map((feed) => {
                const active = activeRss.includes(feed.toLowerCase());
                const isTroubled = TROUBLED_RSS.includes(feed);
                return (
                  <div
                    key={feed}
                    className={`flex items-center justify-between p-3 rounded-lg border text-left text-xs font-semibold transition-all duration-200 relative overflow-hidden ${
                      active
                        ? "bg-primary/10 border-primary text-primary"
                        : "bg-muted/30 border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => handleRssToggle(feed)}
                      className="flex-1 flex items-center justify-between text-left cursor-pointer mr-1.5"
                    >
                      <div className="flex flex-col">
                        <span>{feed}</span>
                        {isTroubled && (
                          <span className="text-[9px] text-amber-500/80 font-medium mt-0.5">Notice</span>
                        )}
                      </div>
                      {active && <Check className="h-3.5 w-3.5 text-primary ml-1 shrink-0" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeletePredefinedFeed(feed)}
                      aria-label={`Delete ${feed}`}
                      className="p-1 text-rose-500 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors cursor-pointer shrink-0"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span className="sr-only">Delete {feed}</span>
                    </button>
                  </div>
                );
              })}
            </div>

            {/* Custom Feeds Section */}
            <div className="space-y-4 pt-4 border-t border-border/40">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-muted-foreground">Custom RSS Feeds</h4>
                {!showAddFeedForm && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setShowAddFeedForm(true)}
                    className="border-dashed border-border/80 hover:border-primary/50 text-[11px] gap-1.5 h-7 font-semibold cursor-pointer"
                  >
                    <Plus className="h-3 w-3 text-muted-foreground" />
                    Add Custom Feed
                  </Button>
                )}
              </div>

              {showAddFeedForm && (
                <form
                  onSubmit={handleAddFeed}
                  className="space-y-4 p-4 rounded-xl border border-border/60 bg-muted/20 backdrop-blur-md max-w-md"
                >
                  <div className="flex items-center justify-between border-b border-border/40 pb-2 mb-2">
                    <span className="text-xs font-bold text-foreground">Add Custom RSS Feed</span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setShowAddFeedForm(false);
                        setFeedValError("");
                      }}
                      className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground cursor-pointer"
                    >
                      Cancel
                    </Button>
                  </div>
                  
                  {feedValError && (
                    <div className="text-[11px] text-rose-400 font-semibold bg-rose-500/10 border border-rose-500/20 px-2.5 py-1.5 rounded-md flex items-center gap-1.5">
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-rose-500" />
                      <span>{feedValError}</span>
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2 space-y-1">
                      <label className="text-[10px] font-semibold text-muted-foreground">Feed Name</label>
                      <Input
                        placeholder="Feed Name"
                        value={newFeedName}
                        onChange={(e) => setNewFeedName(e.target.value)}
                        className="bg-background border-border/60 text-xs focus-visible:ring-primary/30 h-8"
                      />
                    </div>

                    <div className="col-span-2 space-y-1">
                      <label className="text-[10px] font-semibold text-muted-foreground">Feed URL</label>
                      <Input
                        placeholder="Feed URL"
                        value={newFeedUrl}
                        onChange={(e) => setNewFeedUrl(e.target.value)}
                        className="bg-background border-border/60 text-xs focus-visible:ring-primary/30 h-8"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold text-muted-foreground block">Category</label>
                      <select
                        value={newFeedCategory}
                        onChange={(e) => setNewFeedCategory(e.target.value)}
                        className="w-full bg-background border border-border/60 rounded-md p-1.5 text-xs text-foreground focus-visible:ring-primary/30 focus-visible:outline-none h-8"
                      >
                        <option value="finance">Finance</option>
                        <option value="market">Market</option>
                        <option value="macro">Macro</option>
                        <option value="tech_business">Tech / Business</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-semibold text-muted-foreground block">Language</label>
                      <select
                        value={newFeedLanguage}
                        onChange={(e) => setNewFeedLanguage(e.target.value)}
                        className="w-full bg-background border border-border/60 rounded-md p-1.5 text-xs text-foreground focus-visible:ring-primary/30 focus-visible:outline-none h-8"
                      >
                        <option value="en">English (en)</option>
                        <option value="zh">Chinese (zh)</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button type="submit" size="sm" className="h-7 text-[11px] font-semibold px-3 gap-1 cursor-pointer">
                      <Plus className="h-3 w-3" />
                      Add Feed
                    </Button>
                  </div>
                </form>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {customRssFeeds.map((feed) => {
                  const active = activeRss.includes(feed.name.toLowerCase());
                  return (
                    <div
                      key={feed.name}
                      className={`flex items-center justify-between p-3 rounded-lg border text-left text-xs font-semibold transition-all duration-200 relative overflow-hidden ${
                        active
                          ? "bg-primary/10 border-primary text-primary"
                          : "bg-muted/30 border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => handleRssToggle(feed.name)}
                        className="flex-1 flex items-center justify-between text-left cursor-pointer mr-1.5"
                      >
                        <div className="flex flex-col">
                          <span>{feed.name}</span>
                          <span className="text-[9px] text-muted-foreground/80 font-medium uppercase mt-0.5">
                            {feed.category} ({feed.language})
                          </span>
                        </div>
                        {active && <Check className="h-3.5 w-3.5 text-primary ml-1 shrink-0" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteCustomFeed(feed.name)}
                        aria-label={`Delete ${feed.name}`}
                        className="p-1 text-rose-500 hover:text-rose-400 hover:bg-rose-500/10 rounded transition-colors cursor-pointer shrink-0"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        <span className="sr-only">Delete {feed.name}</span>
                      </button>
                    </div>
                  );
                })}
                {customRssFeeds.length === 0 && (
                  <div className="col-span-full py-6 text-center text-xs text-muted-foreground border border-dashed border-border/40 rounded-lg">
                    No custom RSS feeds configured.
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-semibold text-muted-foreground block">
                Custom / Comma-separated Feed Names:
              </label>
              <Input
                placeholder="e.g. 36Kr, Bloomberg, FT Markets"
                value={enabledRssFeeds}
                onChange={(e) => setEnabledRssFeeds(e.target.value)}
                className="bg-muted/20 border-border/60 text-sm font-medium focus-visible:ring-primary/30"
              />
            </div>
          </div>

          <hr className="border-border/60" />

          {/* Collector Ingest Configuration */}
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold flex items-center gap-2 text-foreground mb-1">
                <Radio className="h-4 w-4 text-emerald-500" /> Collector Ingest Sources
              </h3>
              <p className="text-xs text-muted-foreground">
                Select which cloud Collector sources to sync. Toggled feeds are whitelisted and retrieved on schedule.
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
              {(collectorSourcesData?.sources || []).map((source) => {
                const active = activeCollectorSources.includes(source.name.toLowerCase());
                return (
                  <button
                    key={source.name}
                    type="button"
                    onClick={() => handleCollectorSourceToggle(source.name)}
                    className={`flex items-center justify-between p-3 rounded-lg border text-left text-xs font-semibold transition-all duration-200 cursor-pointer ${
                      active
                        ? "bg-primary/10 border-primary text-primary"
                        : "bg-muted/30 border-border/60 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                    }`}
                  >
                    <span className="truncate">{source.name}</span>
                    {active && <Check className="h-3.5 w-3.5 text-primary ml-1 shrink-0" />}
                  </button>
                );
              })}
              {(!collectorSourcesData?.sources || collectorSourcesData.sources.length === 0) && (
                <div className="col-span-full py-6 text-center text-xs text-muted-foreground border border-dashed border-border/40 rounded-lg">
                  No Collector Ingest sources found or failed to load.
                </div>
              )}
            </div>

            <div className="space-y-2 pt-2">
              <label className="text-xs font-semibold text-muted-foreground block">
                Custom / Comma-separated Collector Sources:
              </label>
              <Input
                placeholder="e.g. Bloomberg Markets, TechCrunch"
                value={enabledCollectorSources}
                onChange={(e) => setEnabledCollectorSources(e.target.value)}
                className="bg-muted/20 border-border/60 text-sm font-medium focus-visible:ring-primary/30"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
