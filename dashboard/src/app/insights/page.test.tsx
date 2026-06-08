import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { SWRConfig } from "swr";
import InsightsPage from "./page";

const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("Insight Vault Page - Slice 5", () => {
  const mockInsights = {
    items: [
      {
        id: "insight-1",
        dimension_name: "FSD Rollout",
        summary_en: "Tesla has expanded FSD rollout to more users.",
        summary_zh: "特斯拉已向更多用户扩大FSD的推广范围。",
        urgency: "high",
        sentiment: "positive",
        tags: ["ev", "autonomous"],
        last_updated_at: "2026-06-07T09:00:00Z",
        subject: {
          id: "subj-1",
          name: "Tesla (TSLA)",
          type: "ticker",
          tags: ["tech", "automotive"],
        },
        facts: [
          {
            id: "fact-1",
            bullet_text_en: "FSD Beta 12.3 released to all US customers.",
            bullet_text_zh: "FSD Beta 12.3已发布给所有美国客户。",
            created_at: "2026-06-07T08:00:00Z",
            source_article: {
              id: "art-1",
              title: "Tesla expands FSD Beta release",
              title_zh: "特斯拉扩大FSD Beta版发布",
              url: "https://tesla-fsd.example.com",
              source_name: "Electrek",
            },
          },
        ],
      },
      {
        id: "insight-2",
        dimension_name: "Tariff Impact",
        summary_en: "New tariffs on machinery from the EU.",
        summary_zh: "对欧盟机械征收新关税。",
        urgency: "medium",
        sentiment: "negative",
        tags: ["trade", "tariff"],
        last_updated_at: "2026-06-07T08:30:00Z",
        subject: {
          id: "subj-2",
          name: "US Trade Relations",
          type: "macro",
          tags: ["policy", "global-trade"],
        },
        facts: [],
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

  it("renders the list of subjects and insights bilingually and supports details toggling", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockInsights),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <InsightsPage />
      </SWRConfig>
    );

    // Verify Title
    expect(await screen.findByText(/Insight Vault \/ 见解库/i)).toBeInTheDocument();

    // Verify Subjects and Dimensions
    expect(screen.getByText("Tesla (TSLA)")).toBeInTheDocument();
    expect(screen.getByText("FSD Rollout")).toBeInTheDocument();
    expect(screen.getByText("US Trade Relations")).toBeInTheDocument();
    expect(screen.getByText("Tariff Impact")).toBeInTheDocument();

    // English summaries should show by default
    expect(screen.getByText("Tesla has expanded FSD rollout to more users.")).toBeInTheDocument();
    expect(screen.getByText("New tariffs on machinery from the EU.")).toBeInTheDocument();

    // Chinese summaries should not show by default
    expect(screen.queryByText("特斯拉已向更多用户扩大FSD的推广范围。")).not.toBeInTheDocument();

    // Expand accordion for Tesla insight to see facts
    const expandButton = screen.getByRole("button", { name: /expand-insight-insight-1/i });
    expect(expandButton).toBeInTheDocument();
    fireEvent.click(expandButton);

    // Should render English fact by default
    expect(screen.getByText("FSD Beta 12.3 released to all US customers.")).toBeInTheDocument();
    expect(screen.queryByText("FSD Beta 12.3已发布给所有美国客户。")).not.toBeInTheDocument();

    // Toggle language to Chinese
    const zhButton = screen.getByRole("button", { name: /switch-lang-zh/i });
    expect(zhButton).toBeInTheDocument();
    fireEvent.click(zhButton);

    // Chinese summary and fact should now be visible
    await waitFor(() => {
      expect(screen.getByText("特斯拉已向更多用户扩大FSD的推广范围。")).toBeInTheDocument();
    });
    expect(screen.getByText("FSD Beta 12.3已发布给所有美国客户。")).toBeInTheDocument();

    // English should be hidden
    expect(screen.queryByText("Tesla has expanded FSD rollout to more users.")).not.toBeInTheDocument();
    expect(screen.queryByText("FSD Beta 12.3 released to all US customers.")).not.toBeInTheDocument();

    // Link should have Electrek and correct URL
    const sourceLink = screen.getByRole("link", { name: /Electrek/i });
    expect(sourceLink).toBeInTheDocument();
    expect(sourceLink).toHaveAttribute("href", "https://tesla-fsd.example.com");
  });

  it("filters insights by type and search query", async () => {
    mockFetch.mockImplementation(() => {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockInsights),
      });
    });

    render(
      <SWRConfig value={{ provider: () => new Map() }}>
        <InsightsPage />
      </SWRConfig>
    );

    // Wait for render
    expect(await screen.findByText("Tesla (TSLA)")).toBeInTheDocument();

    // Filter by type: macro
    const typeSelect = screen.getByRole("combobox", { name: /filter-type/i });
    fireEvent.change(typeSelect, { target: { value: "macro" } });

    // Tesla (ticker) should disappear, Trade (macro) stays
    await waitFor(() => {
      expect(screen.queryByText("Tesla (TSLA)")).not.toBeInTheDocument();
    });
    expect(screen.getByText("US Trade Relations")).toBeInTheDocument();

    // Clear type and search for "Tesla"
    fireEvent.change(typeSelect, { target: { value: "" } });
    const searchInput = screen.getByPlaceholderText(/search subjects/i);
    fireEvent.change(searchInput, { target: { value: "Tesla" } });

    // Trade should disappear, Tesla stays
    await waitFor(() => {
      expect(screen.queryByText("US Trade Relations")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Tesla (TSLA)")).toBeInTheDocument();
  });
});
