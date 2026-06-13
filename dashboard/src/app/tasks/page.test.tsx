import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import TaskHistoryPage from "./page";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  global.fetch = mockFetch;
  mockFetch.mockReset();
});

describe("Tasks History Page - Unified UI Tests", () => {
  const mockStats = {
    total_news: 200,
    pending_news: 15,
    pending_preprocessing: 8,
    pending_analysis: 15,
    active_run: {
      id: "run-active-123",
      job_id: "analysis",
      task_name: "AI Analysis",
      trigger_type: "manual",
      status: "running",
      start_time: "2026-06-08T10:00:00Z",
      processed_count: 5,
      failed_count: 1,
      total_count: 10,
      message: null,
    },
    llm_api_status: {
      status: "healthy",
      error_message: null,
      requests_made_today: 120,
      estimated_daily_limit: 1000,
    },
  };

  const mockHistory = [
    {
      id: "run-active-123",
      job_id: "analysis",
      task_name: "AI Analysis",
      trigger_type: "manual",
      status: "running",
      start_time: "2026-06-08T10:00:00Z",
      end_time: null,
      processed_count: 5,
      failed_count: 1,
      total_count: 10,
      message: null,
    },
    {
      id: "run-completed-456",
      job_id: "preprocessing",
      task_name: "News Pre-processing",
      trigger_type: "scheduled",
      status: "success",
      start_time: "2026-06-08T09:00:00Z",
      end_time: "2026-06-08T09:00:45Z",
      processed_count: 12,
      failed_count: 0,
      total_count: 12,
      message: null,
    },
  ];

  beforeEach(() => {
    mockFetch.mockReset();
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders manual trigger buttons including Pre-processing and triggers a job", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/tasks/analysis-stats")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ ...mockStats, active_run: null }),
        });
      }
      if (url.includes("/api/tasks/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 2, offset: 0, limit: 20, items: mockHistory }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <TaskHistoryPage />
      </SWRConfig>
    );

    // Verify trigger buttons render
    expect(await screen.findByRole("button", { name: /Pre-processing/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AI Analysis/i })).toBeInTheDocument();

    // Trigger RSS Ingest
    const rssBtn = screen.getByRole("button", { name: /RSS Ingest/i });
    expect(rssBtn).toBeInTheDocument();

    // Trigger mock trigger action
    mockFetch.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "triggered", job_id: "rss_news" }),
      })
    );

    // Click trigger
    fireEvent.click(rssBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/scheduler/jobs/rss_news/trigger"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("renders stats metadata in the table log header", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/tasks/analysis-stats")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStats),
        });
      }
      if (url.includes("/api/tasks/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 2, offset: 0, limit: 20, items: mockHistory }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <TaskHistoryPage />
      </SWRConfig>
    );

    // Verify stats are rendered inside the header
    expect(await screen.findByText("8")).toBeInTheDocument(); // pending pre-processing
    expect(screen.getByText("15")).toBeInTheDocument(); // pending analysis
  });

  it("renders progress details and a Stop button for running tasks, and clicks stop", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/tasks/analysis-stats")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStats),
        });
      }
      if (url.includes("/api/tasks/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 2, offset: 0, limit: 20, items: mockHistory }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <TaskHistoryPage />
      </SWRConfig>
    );

    // Find progress details in the running row
    expect(await screen.findByText(/Processed: 5 \/ 10/i)).toBeInTheDocument();
    expect(screen.getByText(/F: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/60%/)).toBeInTheDocument(); // Math.round((5+1)/10 * 100) = 60

    // Find and click Stop button
    const stopBtn = screen.getByRole("button", { name: /Stop/i });
    expect(stopBtn).toBeInTheDocument();

    mockFetch.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: "stopped", task_run_id: "run-active-123" }),
      })
    );

    fireEvent.click(stopBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/tasks/run-active-123/stop"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("renders pagination controls and handles page navigation", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/tasks/analysis-stats")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStats),
        });
      }
      if (url.includes("/api/tasks/history")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 25, offset: 0, limit: 20, items: mockHistory }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <TaskHistoryPage />
      </SWRConfig>
    );

    // Verify Previous button is disabled at start
    const prevBtn = await screen.findByRole("button", { name: /Previous/i });
    expect(prevBtn).toBeDisabled();

    // Verify page range indicator displays "1 - 20 of 25"
    expect(screen.getByText(/1 - 20 of 25/i)).toBeInTheDocument();

    // Click Next button
    const nextBtn = screen.getByRole("button", { name: /Next/i });
    expect(nextBtn).not.toBeDisabled();
    
    mockFetch.mockImplementationOnce((url: string) => {
      if (url.includes("/api/tasks/history")) {
        expect(url).toContain("offset=20");
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ total: 25, offset: 20, limit: 20, items: [mockHistory[0]] }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    });

    fireEvent.click(nextBtn);

    // Now Previous button should be enabled, and page range indicator displays "21 - 25 of 25"
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Previous/i })).not.toBeDisabled();
      expect(screen.getByText(/21 - 25 of 25/i)).toBeInTheDocument();
    });
  });
});
