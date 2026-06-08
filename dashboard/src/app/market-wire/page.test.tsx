import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import MarketWirePage from "./page";

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("Market Wire Page - Slice 4", () => {
  const mockWires = {
    total: 2,
    items: [
      {
        id: "wire-1",
        content: "Powell indicates rate cuts in Q4.",
        language: "en",
        importance: 4,
        related_symbols: ["SPY", "QQQ"],
        published_at: "2026-06-07T09:00:00Z",
        source_type: "jin10",
      },
      {
        id: "wire-2",
        content: "中国5月出口同比增长10.5%。",
        language: "zh",
        importance: 2,
        related_symbols: ["FXI"],
        published_at: "2026-06-07T08:30:00Z",
        source_type: "akshare",
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

  it("renders a feed of market wires with star ratings and related symbols", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockWires),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <MarketWirePage />
      </SWRConfig>
    );

    // Page title should be there
    expect(await screen.findByText(/Market Wire \/ 快讯/i)).toBeInTheDocument();

    // Verify both items render
    expect(screen.getByText("Powell indicates rate cuts in Q4.")).toBeInTheDocument();
    expect(screen.getByText("中国5月出口同比增长10.5%。")).toBeInTheDocument();

    // Verify star rating is rendered for high importance
    expect(screen.getByText(/★ 4/i)).toBeInTheDocument();

    // Verify related symbols render as tags/badges
    expect(screen.getByText("SPY")).toBeInTheDocument();
    expect(screen.getByText("QQQ")).toBeInTheDocument();
    expect(screen.getByText("FXI")).toBeInTheDocument();
  });

  it("filters items by language and search query", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockWires),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <MarketWirePage />
      </SWRConfig>
    );

    // Wait for feed to render
    expect(await screen.findByText("Powell indicates rate cuts in Q4.")).toBeInTheDocument();

    // Filter by English language
    const langSelect = screen.getByRole("combobox", { name: /filter-language/i });
    fireEvent.change(langSelect, { target: { value: "en" } });

    // Chinese item should disappear, English stays
    await waitFor(() => {
      expect(screen.queryByText("中国5月出口同比增长10.5%。")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Powell indicates rate cuts in Q4.")).toBeInTheDocument();

    // Reset language and filter by search query "中国"
    fireEvent.change(langSelect, { target: { value: "" } });
    const searchInput = screen.getByPlaceholderText(/search market wires/i);
    fireEvent.change(searchInput, { target: { value: "中国" } });

    // English item should disappear, Chinese stays
    await waitFor(() => {
      expect(screen.queryByText("Powell indicates rate cuts in Q4.")).not.toBeInTheDocument();
    });
    expect(screen.getByText("中国5月出口同比增长10.5%。")).toBeInTheDocument();
  });
});
