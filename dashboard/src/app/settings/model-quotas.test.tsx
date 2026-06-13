import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import { ModelQuotasTab } from "./model-quotas-tab";

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

describe("ModelQuotasTab Component", () => {
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
    },
    available_models: [
      "gemini/gemini-2.0-flash",
      "gemini/gemma-4-26b-a4b-it",
      "gemini/gemma-4-31b-it",
      "gemini/gemini-3.1-flash-lite",
      "gemini/gemini-embedding-2",
      "gemini/gemini-embedding-001",
    ],
  };

  const mockQuotas = {
    "gemini/gemini-2.0-flash": {
      rpm: 2,
      tpm: 500,
      rpd: 10,
      status: "healthy",
      error_message: "",
      limits: { rpm: 15, tpm: 1000000, rpd: 1500 },
    },
    "gemini/gemma-4-31b-it": {
      rpm: 0,
      tpm: 0,
      rpd: 0,
      status: "healthy",
      error_message: "",
      limits: { rpm: 15, tpm: null, rpd: 1500 },
    },
  };

  it("renders dropdown selectors and quota status table", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModels),
        });
      }
      if (url.includes("/api/system/quotas")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockQuotas),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ModelQuotasTab />
      </SWRConfig>
    );

    // Verify Title
    expect(await screen.findByText(/Model Allocation Configuration/i)).toBeInTheDocument();
    expect(screen.getByText(/Model Quota/i)).toBeInTheDocument();

    // Verify Dropdowns exist and have selected value
    const classifyLabel = screen.getByText(/Classification Task Model/i);
    expect(classifyLabel).toBeInTheDocument();
    
    // Check that table rows render tracked models
    expect((await screen.findAllByText("gemini-2.0-flash")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("gemma-4-31b-it").length).toBeGreaterThan(0);
    
    // Check limits displayed
    expect(screen.getAllByText(/15/).length).toBeGreaterThan(0);
  });

  it("calls API to save model allocations when form is submitted", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModels),
        });
      }
      if (url.includes("/api/system/quotas")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockQuotas),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ModelQuotasTab />
      </SWRConfig>
    );

    expect(await screen.findByText(/Task Pacing Delay/i)).toBeInTheDocument();
    
    const saveBtn = screen.getByRole("button", { name: /Save Configuration/i });
    expect(saveBtn).toBeInTheDocument();
    
    mockFetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status: "success" })
    }));
    
    fireEvent.click(saveBtn);
    
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining("LLM_CLASSIFY_MODEL"),
        })
      );
    });
  });

  it("renders and saves task pacing delay settings", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModels),
        });
      }
      if (url.includes("/api/system/quotas")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockQuotas),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ModelQuotasTab />
      </SWRConfig>
    );

    // Verify task pacing delay label renders
    expect(await screen.findByText(/Task Pacing Delay/i)).toBeInTheDocument();
    
    // Verify default value select is auto
    const select = screen.getByRole("combobox", { name: /Task Pacing Delay/i }) as HTMLSelectElement;
    expect(select.value).toBe("auto");

    // Change value to custom
    fireEvent.change(select, { target: { value: "custom" } });
    
    // Verify custom number input appears
    const customInput = screen.getByPlaceholderText(/e\.g\. 1\.5/i) as HTMLInputElement;
    expect(customInput).toBeInTheDocument();
    fireEvent.change(customInput, { target: { value: "1.2" } });

    // Submit form and verify PUT payload includes LLM_PACING_DELAY
    const saveBtn = screen.getByRole("button", { name: /Save Configuration/i });
    mockFetch.mockImplementationOnce(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve({ status: "success" })
    }));

    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/system/models"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining('"LLM_PACING_DELAY":"1.2"'),
        })
      );
    });
  });

  it("renders form fields grouped by stage with correct headings", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/system/models")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockModels),
        });
      }
      if (url.includes("/api/system/quotas")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockQuotas),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <ModelQuotasTab />
      </SWRConfig>
    );

    // Verify stage headers are in the document
    expect(await screen.findByText(/Stage 1: Pre-processing Models/i)).toBeInTheDocument();
    expect(screen.getByText(/Stage 2: AI Analysis Models/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Shared: Vector Indexing Service/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Pacing & Safety Controls/i)).toBeInTheDocument();
  });
});

