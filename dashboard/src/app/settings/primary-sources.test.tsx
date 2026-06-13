import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import { PrimarySourcesTab } from "./primary-sources-tab";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  global.fetch = mockFetch;
  mockFetch.mockReset();
  vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PrimarySourcesTab Component", () => {
  const mockModels = {
    allocations: {
      LLM_CLASSIFY_MODEL: "gemini/gemini-2.0-flash",
      LLM_SUMMARIZE_MODEL: "gemini/gemma-4-26b-a4b-it",
      LLM_ANALYSIS_MODEL: "gemini/gemma-4-31b-it",
      LLM_RELEVANCE_MODEL: "gemini/gemini-3.1-flash-lite",
      LLM_EMBED_MODEL: "gemini/gemini-embedding-2",
      LLM_EMBED_FALLBACK_MODEL: "gemini/gemini-embedding-001",
      LLM_LIGHTWEIGHT_FALLBACK_MODEL: "gemini/gemini-3.1-flash-lite",
      LLM_REASONING_FALLBACK_MODEL: "gemini/gemma-4-31b-it",
      DAILY_SPEND_LIMIT: 5.00,
      LLM_PACING_DELAY: "auto",
      MAX_ANALYSIS_DURATION_MINUTES: 25,
      ANALYSIS_BATCH_SIZE: 20,
      NEWSAPI_DOMAINS: "bloomberg.com,reuters.com",
      ENABLED_RSS_FEEDS: "36Kr,Bloomberg,FT Markets"
    },
    available_models: [
      "gemini/gemini-2.0-flash",
      "gemini/gemma-4-31b-it",
    ]
  };

  const mockNewsApiSources = {
    sources: [
      {
        id: "bloomberg",
        name: "Bloomberg",
        description: "Bloomberg description",
        url: "https://www.bloomberg.com",
        category: "business",
        language: "en",
        country: "us"
      },
      {
        id: "reuters",
        name: "Reuters",
        description: "Reuters description",
        url: "https://www.reuters.com",
        category: "general",
        language: "en",
        country: "us"
      },
      {
        id: "wsj",
        name: "The Wall Street Journal",
        description: "WSJ description",
        url: "https://www.wsj.com",
        category: "business",
        language: "en",
        country: "us"
      }
    ]
  };

  const setupMocks = () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModels),
        });
      }
      if (url.includes("/api/system/newsapi-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockNewsApiSources),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  };

  it("renders selection buttons and custom text inputs", async () => {
    setupMocks();

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // Verify Title
    expect(await screen.findByText(/Primary Source Selection/i)).toBeInTheDocument();
    
    // Verify NewsAPI Domain Filter section is present
    expect(screen.getByText(/NewsAPI Domain Filter/i)).toBeInTheDocument();

    // Check custom domains input has existing value
    const customDomainsInput = await screen.findByPlaceholderText(/e\.g\. bloomberg\.com/i) as HTMLInputElement;
    expect(customDomainsInput.value).toBe("bloomberg.com,reuters.com");

    // Check custom RSS feeds input has existing value
    const customRssInput = screen.getByPlaceholderText(/e\.g\. 36Kr/i) as HTMLInputElement;
    expect(customRssInput.value).toBe("36Kr,Bloomberg,FT Markets");
  });

  it("calls API with updated payload when form is saved", async () => {
    setupMocks();

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // Wait for content to render
    const saveBtn = await screen.findByRole("button", { name: /Save Configuration/i });
    expect(saveBtn).toBeInTheDocument();

    const customDomainsInput = await screen.findByPlaceholderText(/e\.g\. bloomberg\.com/i) as HTMLInputElement;
    
    // Update domain input
    fireEvent.change(customDomainsInput, { target: { value: "bloomberg.com, reuters.com, wsj.com" } });
    
    mockFetch.mockImplementation((url: string, options: any) => {
      if (url.includes("/api/system/models") && options?.method === "PUT") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "success", message: "Model allocations updated successfully." })
        });
      }
      if (url.includes("/api/system/newsapi-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockNewsApiSources),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockModels),
      });
    });

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"NEWSAPI_DOMAINS":"bloomberg.com,reuters.com,wsj.com"'),
        })
      );
    });
  });

  it("handles dynamic NewsAPI sources searching, filtering, and toggling", async () => {
    setupMocks();

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // 1. Verify that dynamic NewsAPI sources are displayed
    expect(await screen.findByText("Bloomberg description", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Reuters")).toBeInTheDocument();
    expect(screen.getByText("The Wall Street Journal")).toBeInTheDocument();

    // 2. Locate search input and search for "Reuters"
    const searchInput = screen.getByPlaceholderText(/Search news agencies/i);
    fireEvent.change(searchInput, { target: { value: "reuters" } });

    // 3. Verify search filter works
    expect(screen.queryByText("Bloomberg description")).not.toBeInTheDocument();
    expect(screen.getByText("Reuters")).toBeInTheDocument();

    // 4. Toggle the Reuters source (currently active, should toggle off)
    const reutersBtn = screen.getByRole("button", { name: /Reuters/i });
    fireEvent.click(reutersBtn);

    // 5. Clear search to see others
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.getByText("Bloomberg description")).toBeInTheDocument();

    // 6. Save configuration and verify that only bloomberg.com remains (reuters.com was removed)
    const saveBtn = screen.getByRole("button", { name: /Save Configuration/i });
    
    mockFetch.mockImplementation((url: string, options: any) => {
      if (url.includes("/api/system/models") && options?.method === "PUT") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "success" })
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"NEWSAPI_DOMAINS":"bloomberg.com"'),
        })
      );
    });
  });

  it("handles dynamic RSS feeds listing, adding, validation, and deletion", async () => {
    const mockModelsWithCustom = {
      ...mockModels,
      allocations: {
        ...mockModels.allocations,
        CUSTOM_RSS_FEEDS: JSON.stringify([
          {
            name: "CustomFeed1",
            url: "https://custom1.com/rss",
            category: "finance",
            language: "en"
          }
        ]),
        ENABLED_RSS_FEEDS: "36Kr,Bloomberg,FT Markets,CustomFeed1"
      }
    };

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModelsWithCustom),
        });
      }
      if (url.includes("/api/system/newsapi-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockNewsApiSources),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // 2. Verify that custom and predefined RSS feeds are displayed
    expect(await screen.findByText("36Kr", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("CustomFeed1")).toBeInTheDocument();

    // 3. Click "Add Custom Feed" button/toggle to reveal the form
    const addBtn = screen.getByRole("button", { name: /Add Custom Feed/i });
    fireEvent.click(addBtn);

    // 4. Fill in the form with invalid URL and try to add
    const nameInput = screen.getByPlaceholderText(/Feed Name/i);
    const urlInput = screen.getByPlaceholderText(/Feed URL/i);
    const saveFeedBtn = screen.getByRole("button", { name: /Add Feed/i });

    fireEvent.change(nameInput, { target: { value: "InvalidFeed" } });
    fireEvent.change(urlInput, { target: { value: "invalid-url" } });
    fireEvent.click(saveFeedBtn);

    // Verify validation message
    expect(screen.getByText(/URL must start with http:\/\/ or https:\/\//i)).toBeInTheDocument();

    // 5. Fill in valid URL and add it
    fireEvent.change(urlInput, { target: { value: "https://validurl.com/rss" } });
    fireEvent.click(saveFeedBtn);

    // Verify it is added to the list
    expect(await screen.findByText("InvalidFeed")).toBeInTheDocument();

    // 6. Delete the "CustomFeed1" feed
    const deleteBtn = screen.getByRole("button", { name: /Delete CustomFeed1/i });
    fireEvent.click(deleteBtn);
    expect(screen.queryByText("CustomFeed1")).not.toBeInTheDocument();

    // 7. Save config and verify PUT payload
    const saveConfigBtn = screen.getByRole("button", { name: /Save Configuration/i });
    
    mockFetch.mockImplementation((url: string, options: any) => {
      if (url.includes("/api/system/models") && options?.method === "PUT") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "success" })
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    fireEvent.click(saveConfigBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"CUSTOM_RSS_FEEDS"'),
        })
      );
    });
  });

  it("handles deletion of predefined RSS feeds", async () => {
    const mockModelsWithCustom = {
      ...mockModels,
      allocations: {
        ...mockModels.allocations,
        CUSTOM_RSS_FEEDS: "[]",
        ENABLED_RSS_FEEDS: "36Kr,Bloomberg",
        DELETED_RSS_FEEDS: ""
      }
    };

    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModelsWithCustom),
        });
      }
      if (url.includes("/api/system/newsapi-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockNewsApiSources),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // Verify 36Kr is displayed
    expect(await screen.findByText("36Kr", {}, { timeout: 3000 })).toBeInTheDocument();

    // Click Delete 36Kr button
    const deleteBtn = screen.getByRole("button", { name: /Delete 36Kr/i });
    fireEvent.click(deleteBtn);

    // Verify 36Kr is gone
    expect(screen.queryByText("36Kr")).not.toBeInTheDocument();

    // Save and verify PUT payload
    const saveConfigBtn = screen.getByRole("button", { name: /Save Configuration/i });
    
    mockFetch.mockImplementation((url: string, options: any) => {
      if (url.includes("/api/system/models") && options?.method === "PUT") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: "success" })
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    fireEvent.click(saveConfigBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"DELETED_RSS_FEEDS":"36kr"'),
        })
      );
    });
  });

  it("handles Collector Ingest sources checklist and saving", async () => {
    const mockModelsWithCollector = {
      ...mockModels,
      allocations: {
        ...mockModels.allocations,
        ENABLED_COLLECTOR_SOURCES: "Bloomberg Markets"
      }
    };

    const mockCollectorSources = {
      sources: [
        { name: "Bloomberg Markets" },
        { name: "TechCrunch" }
      ]
    };

    mockFetch.mockImplementation((url: string, options: any) => {
      if (url.includes("/api/system/models")) {
        if (options?.method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ status: "success" })
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModelsWithCollector),
        });
      }
      if (url.includes("/api/system/newsapi-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockNewsApiSources),
        });
      }
      if (url.includes("/api/system/collector-sources")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockCollectorSources),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <PrimarySourcesTab />
      </SWRConfig>
    );

    // Verify Collector Ingest section and sources are rendered
    expect(await screen.findByText(/Collector Ingest Sources/i)).toBeInTheDocument();
    expect(await screen.findByText("Bloomberg Markets")).toBeInTheDocument();
    expect(screen.getByText("TechCrunch")).toBeInTheDocument();

    // Toggle TechCrunch to enable it
    const techCrunchBtn = screen.getByRole("button", { name: /TechCrunch/i });
    fireEvent.click(techCrunchBtn);

    // Save and verify PUT payload includes "Bloomberg Markets,TechCrunch" or similar
    const saveConfigBtn = screen.getByRole("button", { name: /Save Configuration/i });
    fireEvent.click(saveConfigBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"ENABLED_COLLECTOR_SOURCES":"Bloomberg Markets,TechCrunch"'),
        })
      );
    });
  });
});
