import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import NewsPage from "./page";

// Mock global fetch
const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  global.fetch = mockFetch;
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("News Page - Slice 1 (Status Indicator & Basic Feed Table)", () => {
  const mockNewsData = {
    total: 2,
    offset: 0,
    limit: 20,
    items: [
      {
        id: "art-analyzed",
        title: "NVDA Earnings Soar",
        title_zh: "英伟达收益飙升",
        url: "https://test.com/nvda",
        source_type: "rss",
        source_name: "Reuters",
        language: "en",
        summary: "Nvidia reports record breaking earnings.",
        published_at: "2026-06-08T12:00:00Z",
        fetched_at: "2026-06-08T13:00:00Z",
        analysis: {
          id: "analysis-123",
          urgency: "high",
          sentiment: "positive",
          sentiment_score: 0.9,
          topics: ["Earnings", "AI"],
          companies_mentioned: ["NVDA"],
          summary_en: "Nvidia earnings soar.",
          summary_zh: "英伟达收益飙升。",
          impact_assessment: "High impact.",
          llm_model: "pipeline",
          analyzed_at: "2026-06-08T12:05:00Z"
        }
      },
      {
        id: "art-pending",
        title: "Federal Reserve Meeting Scheduled",
        title_zh: null,
        url: "https://test.com/fed",
        source_type: "rss",
        source_name: "Bloomberg",
        language: "en",
        summary: "Federal Reserve officials scheduled a meeting next week.",
        published_at: "2026-06-08T14:00:00Z",
        fetched_at: "2026-06-08T15:00:00Z",
        analysis: null
      }
    ]
  };

  it("renders a news table with headers and displays correct status badges", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockNewsData),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <NewsPage />
      </SWRConfig>
    );

    // Verify page title and summary total count
    expect(await screen.findByText(/News Feed \/ 新闻/i)).toBeInTheDocument();
    expect(screen.getByText(/2 articles total/i)).toBeInTheDocument();

    // Verify table structure
    const table = screen.getByRole("table");
    expect(table).toBeInTheDocument();

    // Verify table headers
    expect(screen.getByText("Title / 标题")).toBeInTheDocument();
    expect(screen.getByText("Source / 来源")).toBeInTheDocument();
    expect(screen.getByText("Pub / 发布时间")).toBeInTheDocument();
    expect(screen.getByText("Fetch / 抓取时间")).toBeInTheDocument();
    expect(screen.getByText("Status / 状态")).toBeInTheDocument();

    // Verify rows rendered
    expect(screen.getByText("NVDA Earnings Soar")).toBeInTheDocument();
    expect(screen.getByText("Federal Reserve Meeting Scheduled")).toBeInTheDocument();

    // Verify Analyzed status badge
    const analyzedBadges = screen.getAllByText("Analyzed");
    expect(analyzedBadges.length).toBeGreaterThan(0);

    // Verify Pending status badge
    const pendingBadges = screen.getAllByText("Pending");
    expect(pendingBadges.length).toBeGreaterThan(0);

    // Verify both pub date and fetch date are displayed in table
    const pubDateStr = new Date("2026-06-08T12:00:00Z").toLocaleString();
    const fetchDateStr = new Date("2026-06-08T13:00:00Z").toLocaleString();
    expect(screen.getAllByText(pubDateStr).length).toBeGreaterThan(0);
    expect(screen.getAllByText(fetchDateStr).length).toBeGreaterThan(0);
  });

  it("opens details drawer on row click and displays bilingual summaries", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockNewsData),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <NewsPage />
      </SWRConfig>
    );

    // Wait for news to load
    const titleCell = await screen.findByText("NVDA Earnings Soar");
    expect(titleCell).toBeInTheDocument();

    // Click on the row (or the cell containing the title) to open drawer
    fireEvent.click(titleCell.parentElement!);

    // Verify drawer details are displayed
    expect(await screen.findByText("News Details / 新闻详情")).toBeInTheDocument();
    expect(screen.getByText("英伟达收益飙升")).toBeInTheDocument(); // Translated title
    expect(screen.getByText("Nvidia earnings soar.")).toBeInTheDocument(); // English summary
    expect(screen.getByText("英伟达收益飙升。")).toBeInTheDocument(); // Chinese summary
    expect(screen.getByText("High impact.")).toBeInTheDocument(); // Impact assessment
    expect(screen.getByText("Open Source / 打开链接")).toBeInTheDocument(); // Open URL button

    // Verify both pub date and fetch date are displayed in drawer details
    const pubDateStr = new Date("2026-06-08T12:00:00Z").toLocaleString();
    const fetchDateStr = new Date("2026-06-08T13:00:00Z").toLocaleString();
    expect(screen.getByText(new RegExp(`Pub:[\\s\\S]*${pubDateStr.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')}`))).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`Fetch:[\\s\\S]*${fetchDateStr.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&')}`))).toBeInTheDocument();
  });

  it("updates API query parameters on tab and filter selection", async () => {
    mockFetch.mockImplementation((url: string) => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockNewsData),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <NewsPage />
      </SWRConfig>
    );

    // Wait for news to load
    await screen.findByText("NVDA Earnings Soar");

    // Click RSS tab
    const rssTabButton = screen.getByRole("tab", { name: /RSS/i });
    expect(rssTabButton).toBeInTheDocument();
    fireEvent.click(rssTabButton);

    // Verify fetch was called with source_type=rss
    await waitFor(() => {
      const fetchCalls = mockFetch.mock.calls.map(([url]) => url);
      const hasRssCall = fetchCalls.some((url) => url.includes("source_type=rss"));
      expect(hasRssCall).toBe(true);
    });

    // Click Collector Ingest tab
    const collectorTabButton = screen.getByRole("tab", { name: /Collector Ingest/i });
    expect(collectorTabButton).toBeInTheDocument();
    fireEvent.click(collectorTabButton);

    // Verify fetch was called with source_type=collector
    await waitFor(() => {
      const fetchCalls = mockFetch.mock.calls.map(([url]) => url);
      const hasCollectorCall = fetchCalls.some((url) => url.includes("source_type=collector"));
      expect(hasCollectorCall).toBe(true);
    });

    // Change status filter to Analyzed
    const statusSelect = screen.getByLabelText("Filter Status");
    expect(statusSelect).toBeInTheDocument();
    fireEvent.change(statusSelect, { target: { value: "true" } });

    // Verify fetch was called with is_analyzed=true
    await waitFor(() => {
      const fetchCalls = mockFetch.mock.calls.map(([url]) => url);
      const hasAnalyzedCall = fetchCalls.some((url) => url.includes("is_analyzed=true"));
      expect(hasAnalyzedCall).toBe(true);
    });

    // Change urgency filter to High
    const urgencySelect = screen.getByLabelText("Filter Urgency");
    expect(urgencySelect).toBeInTheDocument();
    fireEvent.change(urgencySelect, { target: { value: "high" } });

    // Verify fetch was called with urgency=high
    await waitFor(() => {
      const fetchCalls = mockFetch.mock.calls.map(([url]) => url);
      const hasUrgencyCall = fetchCalls.some((url) => url.includes("urgency=high"));
      expect(hasUrgencyCall).toBe(true);
    });
  });

  it("clicks a company badge in the details drawer to auto-populate the search filter and close the drawer", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockNewsData),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <NewsPage />
      </SWRConfig>
    );

    // Wait for news to load
    const titleCell = await screen.findByText("NVDA Earnings Soar");
    expect(titleCell).toBeInTheDocument();

    // Click on the row to open drawer
    fireEvent.click(titleCell.parentElement!);

    // Verify drawer is open
    expect(await screen.findByText("News Details / 新闻详情")).toBeInTheDocument();

    // Find company badge "NVDA" in drawer and click it
    const companyBadge = screen.getByRole("button", { name: /filter-tag-NVDA/i });
    expect(companyBadge).toBeInTheDocument();
    fireEvent.click(companyBadge);

    // Verify search input is updated to "NVDA"
    const searchInput = screen.getByPlaceholderText("Search news...") as HTMLInputElement;
    expect(searchInput.value).toBe("NVDA");

    // Verify fetch was triggered with search=NVDA
    await waitFor(() => {
      const fetchCalls = mockFetch.mock.calls.map(([url]) => url);
      const hasSearchCall = fetchCalls.some((url) => url.includes("search=NVDA"));
      expect(hasSearchCall).toBe(true);
    });

    // Verify drawer is closed
    await waitFor(() => {
      expect(screen.queryByText("News Details / 新闻详情")).not.toBeInTheDocument();
    });
  });
});
