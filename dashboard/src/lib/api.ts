const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchAPI<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`/api${path}`, API_BASE);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v);
    });
  }
  const res = await fetch(url.toString(), { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export type NewsItem = {
  id: string;
  title: string;
  title_zh: string | null;
  url: string;
  source_type: string;
  source_name: string;
  language: string;
  summary: string | null;
  published_at: string | null;
  fetched_at: string;
  analysis?: AnalysisItem | null;
};

export type AnalysisItem = {
  id: string;
  article_id: string | null;
  urgency: string | null;
  sentiment: string | null;
  sentiment_score: number | null;
  topics: string[] | null;
  companies_mentioned: string[] | null;
  summary_en: string | null;
  summary_zh: string | null;
  impact_assessment: string | null;
  analyzed_at: string;
};

export type MarketWireItem = {
  id: string;
  content: string;
  language: string;
  importance: number;
  related_symbols: string[] | null;
  published_at: string | null;
  source_type: string;
};

export type EarningsItem = {
  id: string;
  ticker: string;
  company_name: string | null;
  period: string | null;
  fiscal_year: number | null;
  revenue: number | null;
  net_income?: number | null;
  eps: number | null;
  eps_estimate: number | null;
  revenue_estimate?: number | null;
  report_date: string | null;
};

export type MacroItem = {
  id: string;
  indicator_code: string;
  indicator_name: string;
  country: string;
  value: number | null;
  unit: string | null;
  period: string;
  previous_value: number | null;
  timestamp: string;
};

export type PaginatedResponse<T> = {
  total: number;
  offset: number;
  limit: number;
  items: T[];
};

export type SentimentColor = "positive" | "negative" | "neutral" | "mixed";

export function getSentimentColor(sentiment: string | null): SentimentColor {
  if (!sentiment) return "neutral";
  return sentiment as SentimentColor;
}

export function getUrgencyBadge(urgency: string | null): { label: string; variant: "default" | "secondary" | "destructive" | "outline" } {
  switch (urgency) {
    case "flash":
      return { label: "7x24", variant: "destructive" };
    case "high":
      return { label: "High", variant: "default" };
    case "medium":
      return { label: "Medium", variant: "secondary" };
    case "low":
      return { label: "Low", variant: "outline" };
    default:
      return { label: "N/A", variant: "outline" };
  }
}

export type AlertItem = {
  id: string;
  subject_name: string;
  dimension_name: string;
  summary_en: string;
  summary_zh: string;
  last_updated_at: string;
  recent_fact: string | null;
  recent_fact_zh: string | null;
};

export type DailyBriefingItem = {
  id: string;
  summary_en: string;
  summary_zh: string;
  key_takeaways_en: string[] | null;
  key_takeaways_zh: string[] | null;
  generated_at: string;
};

export type SubjectItem = {
  id: string;
  name: string;
  type: "ticker" | "macro" | "theme";
  tags: string[] | null;
};

export type InsightFactSourceArticle = {
  id: string;
  title: string;
  title_zh: string | null;
  url: string;
  source_name: string;
};

export type InsightFactItem = {
  id: string;
  bullet_text_en: string;
  bullet_text_zh: string;
  created_at: string;
  source_article: InsightFactSourceArticle | null;
};

export type InsightItem = {
  id: string;
  dimension_name: string;
  summary_en: string;
  summary_zh: string;
  urgency: string;
  sentiment: string;
  tags: string[] | null;
  last_updated_at: string;
  subject: SubjectItem;
  facts: InsightFactItem[];
};