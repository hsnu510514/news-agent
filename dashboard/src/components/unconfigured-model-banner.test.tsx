import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import { UnconfiguredModelBanner } from "./unconfigured-model-banner";

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

describe("UnconfiguredModelBanner Component", () => {
  it("shows a warning banner if any primary model allocations are empty", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            allocations: {
              LLM_CLASSIFY_MODEL: "",
              LLM_SUMMARIZE_MODEL: "ollama/gemma4:12b",
              LLM_ANALYSIS_MODEL: "",
              LLM_RELEVANCE_MODEL: "ollama/gemma4:12b",
              LLM_EMBED_MODEL: "ollama/nomic-embed-text",
            },
          }),
      })
    );

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <UnconfiguredModelBanner />
      </SWRConfig>
    );

    expect(await screen.findByText(/Model configurations are incomplete/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Configure Models/i })).toHaveAttribute("href", "/settings");
  });

  it("does not show a warning banner if all primary model allocations are configured", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            allocations: {
              LLM_CLASSIFY_MODEL: "ollama/gemma4:12b",
              LLM_SUMMARIZE_MODEL: "ollama/gemma4:12b",
              LLM_ANALYSIS_MODEL: "ollama/gemma4:12b",
              LLM_RELEVANCE_MODEL: "ollama/gemma4:12b",
              LLM_EMBED_MODEL: "ollama/nomic-embed-text",
            },
          }),
      })
    );

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <UnconfiguredModelBanner />
      </SWRConfig>
    );

    await waitFor(() => {
      expect(screen.queryByText(/Model configurations are incomplete/i)).not.toBeInTheDocument();
    });
  });
});
