import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import DashboardPage from "./page";

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  global.fetch = mockFetch;
  mockFetch.mockReset();
});

describe("Dashboard Page - Slice 1 (Emergency Alerts)", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the emergency alerts banner when active alerts are present and handles dismissal", async () => {
    // Setup fetch mock responses
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/alerts")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              alerts: [
                {
                  id: "alert-1",
                  subject_name: "Federal Reserve",
                  dimension_name: "Interest Rates",
                  summary_en: "Fed hikes rates by 50bps unexpectedly.",
                  summary_zh: "美联储意外加息50个基点。",
                  last_updated_at: "2026-06-07T02:00:00Z",
                  recent_fact: "Rate hike announced in unscheduled meeting.",
                  recent_fact_zh: "在非例行会议上宣布加息。",
                },
              ],
            }),
        });
      }
      // Return empty defaults for other API calls to prevent crashing
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <DashboardPage />
      </SWRConfig>
    );

    // Check if the Emergency Alert is displayed
    const alertSubject = await screen.findByText(/Federal Reserve/i);
    expect(alertSubject).toBeInTheDocument();
    expect(screen.getByText(/Interest Rates/i)).toBeInTheDocument();
    expect(screen.getByText(/Rate hike announced in unscheduled meeting./i)).toBeInTheDocument();
    expect(screen.getByText(/在非例行会议上宣布加息。/i)).toBeInTheDocument();

    // Verify it is dismissible
    const dismissButton = screen.getByRole("button", { name: /dismiss-alert-alert-1/i });
    expect(dismissButton).toBeInTheDocument();

    fireEvent.click(dismissButton);

    // After clicking dismiss, the alert subject should no longer be in the document
    await waitFor(() => {
      expect(screen.queryByText(/Federal Reserve/i)).not.toBeInTheDocument();
    });
  });

  it("does not render the banner when there are no active alerts", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ alerts: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <DashboardPage />
      </SWRConfig>
    );

    // Wait a brief moment to ensure fetch resolved
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.queryByText(/Federal Reserve/i)).not.toBeInTheDocument();
  });
});

describe("Dashboard Page - Slice 2 (Daily Briefing)", () => {
  const mockBriefing = {
    id: "briefing-123",
    summary_en: "Global markets remained stable today with tech stocks leading the gains.",
    summary_zh: "全球市场今天保持稳定，科技股领涨。",
    key_takeaways_en: [
      "Fed kept interest rates unchanged as expected.",
      "Crude oil prices fell due to inventory build.",
    ],
    key_takeaways_zh: [
      "美联储按预期维持利率不变。",
      "由于库存增加，原油价格下跌。",
    ],
    generated_at: "2026-06-07T07:00:00Z",
  };

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the latest daily briefing and allows bilingual toggling", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/briefings/latest")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockBriefing),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <DashboardPage />
      </SWRConfig>
    );

    // Should see Daily Briefing header
    expect(await screen.findByText(/Daily Briefing/i)).toBeInTheDocument();

    // English should be the default language
    expect(screen.getByText(mockBriefing.summary_en)).toBeInTheDocument();
    expect(screen.getByText(mockBriefing.key_takeaways_en[0])).toBeInTheDocument();
    expect(screen.getByText(mockBriefing.key_takeaways_en[1])).toBeInTheDocument();

    // Chinese text should NOT be present yet
    expect(screen.queryByText(mockBriefing.summary_zh)).not.toBeInTheDocument();
    expect(screen.queryByText(mockBriefing.key_takeaways_zh[0])).not.toBeInTheDocument();

    // Toggle to Chinese
    const zhButton = screen.getByRole("button", { name: /switch-lang-zh/i });
    expect(zhButton).toBeInTheDocument();
    fireEvent.click(zhButton);

    // Chinese text should now be displayed
    await waitFor(() => {
      expect(screen.getByText(mockBriefing.summary_zh)).toBeInTheDocument();
    });
    expect(screen.getByText(mockBriefing.key_takeaways_zh[0])).toBeInTheDocument();
    expect(screen.getByText(mockBriefing.key_takeaways_zh[1])).toBeInTheDocument();

    // English text should now be hidden
    expect(screen.queryByText(mockBriefing.summary_en)).not.toBeInTheDocument();
    expect(screen.queryByText(mockBriefing.key_takeaways_en[0])).not.toBeInTheDocument();
  });

  it("handles missing daily briefings gracefully", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/briefings/latest")) {
        return Promise.resolve({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: "No briefings found" }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <DashboardPage />
      </SWRConfig>
    );

    // Wait a brief moment to ensure fetch resolved
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(await screen.findByText(/No daily briefing available yet/i)).toBeInTheDocument();
  });
});

describe("Dashboard Page - Slice 3 (Semantic Search)", () => {
  const mockSearchResults = {
    query: "inflation",
    results: [
      {
        id: "art-1",
        score: 0.89,
        payload: {
          type: "article",
          title: "US inflation hits new highs",
          source_name: "Financial Times",
          language: "en",
          published_at: "2026-06-07T08:00:00Z",
        },
      },
      {
        id: "ins-1",
        score: 0.85,
        payload: {
          type: "insight",
          subject: "US Economy",
          dimension_name: "Inflation",
          summary_en: "Inflationary pressures are building up.",
          summary_zh: "通胀压力正在积聚。",
          tags: ["economy", "inflation"],
        },
      },
    ],
  };

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("performs semantic search and renders matching results", async () => {
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/api/analysis/search")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSearchResults),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ total: 0, items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <DashboardPage />
      </SWRConfig>
    );

    // Get search input
    const searchInput = screen.getByPlaceholderText(/search news & insights semantically/i);
    expect(searchInput).toBeInTheDocument();

    // Type query
    fireEvent.change(searchInput, { target: { value: "inflation" } });

    // Submit search (press enter or click search button)
    const searchButton = screen.getByRole("button", { name: /search-submit/i });
    expect(searchButton).toBeInTheDocument();
    fireEvent.click(searchButton);

    // Should query API and show results
    const FTResult = await screen.findByText(/US inflation hits new highs/i);
    expect(FTResult).toBeInTheDocument();
    expect(screen.getByText(/Financial Times/i)).toBeInTheDocument();

    // Should show Insight result
    expect(screen.getByText(/US Economy/i)).toBeInTheDocument();
    expect(screen.getByText(/Inflationary pressures are building up./i)).toBeInTheDocument();
    expect(screen.getByText(/通胀压力正在积聚。/i)).toBeInTheDocument();

    // Can clear results
    const clearButton = screen.getByRole("button", { name: /clear-search/i });
    expect(clearButton).toBeInTheDocument();
    fireEvent.click(clearButton);

    // Results should disappear
    await waitFor(() => {
      expect(screen.queryByText(/US inflation hits new highs/i)).not.toBeInTheDocument();
    });
  });
});



