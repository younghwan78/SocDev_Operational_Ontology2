import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ko } from "../i18n/ko";
import { PortfolioPage } from "../pages/PortfolioPage";

const overview = {
  projects: [
    {
      project: { id: "project_u", name: "Project U", type: "mobile", phase: "mp" },
      milestone_count: 8,
      open_request_count: 3,
      event_count: 20,
      focuses: [],
    },
  ],
  attention: [
    {
      lane: "evidence_blocked",
      lane_ko: "근거 부족",
      ref_id: "req_1",
      ref_collection: "scenario_requests",
      title: "UHD60 EIS 전력 검토",
      description: "누락 근거: 현세대 전력 트레이스",
      project_ids: ["project_u"],
      scenario_ids: ["uhd60_recording_eis_on"],
      suggested_review_roles: ["pm"],
      source_refs: [],
    },
  ],
  matrix: [
    {
      scenario_id: "uhd60_recording_eis_on",
      scenario_name: "UHD60 녹화",
      scenario_group_id: "camera_recording_kpi",
      project_ids: ["project_u"],
      request_count: 2,
      event_count: 5,
      gap_count: 9,
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(overview), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    ),
  );
});

describe("PortfolioPage", () => {
  it("프로젝트 요약·주의 lane·매트릭스를 렌더링한다", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PortfolioPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText("Project U")).toBeInTheDocument();
    expect(screen.getAllByText("근거 부족").length).toBeGreaterThan(0);
    expect(screen.getByText("UHD60 녹화")).toBeInTheDocument();
    expect(screen.getByText(ko.portfolio.title)).toBeInTheDocument();
  });
});
