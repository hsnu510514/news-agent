import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import SettingsPage from "./page";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  global.fetch = mockFetch;
  mockFetch.mockReset();
});

describe("Settings Page Tabs - Slice 6", () => {
  const mockJobs = [
    {
      id: "rss_news",
      name: "RSS News Fetch",
      enabled: true,
      trigger_type: "interval",
      schedule_value: "30",
      last_run_time: "2026-06-07T09:00:00Z",
      last_run_status: "success",
      last_run_message: "",
      next_run_time: "2026-06-07T09:30:00Z",
    },
    {
      id: "newsapi",
      name: "NewsAPI Fetch",
      enabled: false,
      trigger_type: "interval",
      schedule_value: "60",
      last_run_time: null,
      last_run_status: null,
      last_run_message: null,
      next_run_time: null,
    },
  ];

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a two-tab interface with scheduler details on Tab 1", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/scheduler/jobs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobs),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <SettingsPage />
      </SWRConfig>
    );

    // Verify page title
    expect(await screen.findByText(/Settings & Ingestion Scheduler/i)).toBeInTheDocument();

    // Verify Tab buttons render
    const schedulerTab = screen.getByRole("tab", { name: /Ingestion Scheduler/i });
    const glossaryTab = screen.getByRole("tab", { name: /Entity Glossary/i });
    expect(schedulerTab).toBeInTheDocument();
    expect(glossaryTab).toBeInTheDocument();

    // Ingestion Scheduler should be active by default and display job names
    expect(screen.getByText("RSS News Fetch")).toBeInTheDocument();
    expect(screen.getByText("NewsAPI Fetch")).toBeInTheDocument();

    // Click on Entity Glossary tab
    fireEvent.click(glossaryTab);

    // Wait and verify we switch tabs
    await waitFor(() => {
      expect(screen.getByRole("tab", { name: /Entity Glossary/i })).toHaveAttribute("data-active", "");
    });
  });

  it("opens the Task History side drawer when 'View History' is clicked", async () => {
    const mockTaskHistory = [
      {
        id: "run-1",
        job_id: "rss_news",
        task_name: "RSS News Fetch",
        trigger_type: "manual",
        status: "success",
        start_time: "2026-06-08T10:00:00Z",
        end_time: "2026-06-08T10:01:15Z",
        processed_count: 5,
        failed_count: 0,
        total_count: 5,
        message: null,
      },
      {
        id: "run-2",
        job_id: "rss_news",
        task_name: "RSS News Fetch",
        trigger_type: "scheduled",
        status: "failed",
        start_time: "2026-06-08T09:00:00Z",
        end_time: "2026-06-08T09:00:10Z",
        processed_count: 0,
        failed_count: 1,
        total_count: 1,
        message: "API Key expired or rate limit hit",
      },
    ];

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/scheduler/jobs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockJobs),
        });
      }
      if (url.includes("/api/tasks/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTaskHistory),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <SettingsPage />
      </SWRConfig>
    );

    // Verify "RSS News Fetch" is visible
    expect(await screen.findByText("RSS News Fetch")).toBeInTheDocument();

    // Click "View History" button on the card (since it has job.id "rss_news")
    const historyBtn = screen.getByRole("button", { name: /view-history-rss_news/i });
    expect(historyBtn).toBeInTheDocument();
    fireEvent.click(historyBtn);

    // Drawer should show task runs
    expect(await screen.findByText("Execution History: RSS News Fetch")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    const failedStatus = screen.getByText("failed");
    expect(failedStatus).toBeInTheDocument();
    expect(screen.getByText("manual")).toBeInTheDocument();
    expect(screen.getByText("scheduled")).toBeInTheDocument();

    // Traceback should not be visible yet
    expect(screen.queryByText("API Key expired or rate limit hit")).not.toBeInTheDocument();

    // Click failed row to expand traceback
    fireEvent.click(failedStatus);
    expect(screen.getByText("API Key expired or rate limit hit")).toBeInTheDocument();

    // Click close drawer
    const closeBtn = screen.getByRole("button", { name: /close-drawer/i });
    expect(closeBtn).toBeInTheDocument();
    fireEvent.click(closeBtn);

    // Drawer should close
    await waitFor(() => {
      expect(screen.queryByText("Execution History: RSS News Fetch")).not.toBeInTheDocument();
    });
  });
});


describe("Entity Glossary Manager - Slice 7", () => {
  const mockGlossary = {
    items: [
      {
        id: "g1",
        term_en: "Apple",
        term_zh: "苹果",
        type: "company",
        is_verified: true,
      },
      {
        id: "g2",
        term_en: "Full Self-Driving",
        term_zh: "全自动驾驶",
        type: "theme",
        is_verified: false,
      },
    ],
  };

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists terms, supports search, handles verification, and addition/edit of terms", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/scheduler/jobs")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
      }
      if (url.includes("/api/glossary")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(mockGlossary) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [] }) });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <SettingsPage />
      </SWRConfig>
    );

    // Switch to Glossary tab
    const glossaryTab = await screen.findByRole("tab", { name: /Entity Glossary/i });
    fireEvent.click(glossaryTab);

    // Verify glossary items load
    expect(await screen.findByText("Apple")).toBeInTheDocument();
    expect(screen.getByText("苹果")).toBeInTheDocument();
    expect(screen.getByText("Full Self-Driving")).toBeInTheDocument();
    expect(screen.getByText("全自动驾驶")).toBeInTheDocument();

    // Verify "Verified" vs "Verify" button for unverified
    expect(screen.getByText("Verified")).toBeInTheDocument();
    const verifyButton = screen.getByRole("button", { name: /verify-term-g2/i });
    expect(verifyButton).toBeInTheDocument();

    // Verify click triggers verify API call
    mockFetch.mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: "verified" }) }));
    fireEvent.click(verifyButton);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/glossary/g2/verify"),
        expect.objectContaining({ method: "POST" })
      );
    });

    // Check Search filter
    const searchInput = screen.getByPlaceholderText(/search glossary terms/i);
    fireEvent.change(searchInput, { target: { value: "Apple" } });
    await waitFor(() => {
      expect(screen.queryByText("Full Self-Driving")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Apple")).toBeInTheDocument();
    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });

    // Verify Addition Form fields and submit
    const addBtn = screen.getByRole("button", { name: /add-term-trigger/i });
    fireEvent.click(addBtn);

    const enInput = screen.getByPlaceholderText(/e.g. Nvidia/i);
    const zhInput = screen.getByPlaceholderText(/e.g. 辉达/i);
    const submitBtn = screen.getByRole("button", { name: /submit-term/i });

    fireEvent.change(enInput, { target: { value: "Tesla" } });
    fireEvent.change(zhInput, { target: { value: "特斯拉" } });

    mockFetch.mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: "created", id: "g3" }) }));
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/glossary"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            term_en: "Tesla",
            term_zh: "特斯拉",
            type: "company",
            is_verified: true,
          }),
        })
      );
    });
  });
});

describe("Settings Page - Live Progress Panel", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the LiveProgressPanel on Settings page", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/scheduler/jobs")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve([]),
        });
      }
      if (url.includes("/api/tasks/analysis-stats")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              total_news: 150,
              pending_news: 12,
              active_run: {
                id: "run-active",
                job_id: "analysis",
                task_name: "AI Analysis",
                trigger_type: "manual",
                status: "running",
                start_time: "2026-06-08T10:00:00Z",
                processed_count: 8,
                failed_count: 2,
                total_count: 20,
                message: null,
              },
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ items: [] }),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <SettingsPage />
      </SWRConfig>
    );

    // Verify progress panel is rendered with active task details
    expect(await screen.findByText(/Active Task: AI Analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/Processed: 8 \/ 20 articles/i)).toBeInTheDocument();
    expect(screen.getByText(/Failed: 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Backlog: 12 pending/i)).toBeInTheDocument();
  });
});


