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

const labels = {
  project_u: "Project U",
  uhd60_recording_eis_on: "UHD60 녹화",
  pm: "PM Agent",
};

function jsonResponse(body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.includes("/api/v1/meta/labels")) return jsonResponse(labels);
      if (url.includes("/api/v1/meta/glossary"))
        return jsonResponse({
          objects: {},
          fields: {},
          enums: {},
          value_labels: { role: { pm: "PM" } },
        });
      return jsonResponse(overview);
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <PortfolioPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PortfolioPage", () => {
  it("프로젝트 요약·주의 lane·매트릭스를 렌더링한다", async () => {
    renderPage();
    expect((await screen.findAllByText("Project U")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("근거 부족").length).toBeGreaterThan(0);
    expect(screen.getAllByText("UHD60 녹화").length).toBeGreaterThan(0);
    expect(screen.getByText(ko.portfolio.title)).toBeInTheDocument();
  });

  it("내부 ID를 화면 텍스트로 노출하지 않는다 (hover 제외)", async () => {
    renderPage();
    await screen.findAllByText("Project U");
    // 라벨 로드 완료(=역할 표시명 등장)를 기다린 뒤 ID 부재를 확인한다.
    expect(await screen.findByText(/PM/)).toBeInTheDocument();
    expect(screen.queryByText("project_u")).not.toBeInTheDocument();
    expect(screen.queryByText("uhd60_recording_eis_on")).not.toBeInTheDocument();
    expect(screen.queryByText("req_1")).not.toBeInTheDocument();
  });
});
