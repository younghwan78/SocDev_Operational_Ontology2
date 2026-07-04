import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ko } from "../i18n/ko";
import { ScenarioListPage } from "../pages/ScenarioListPage";

const scenarios = [
  {
    id: "uhd60_recording_eis_on",
    name: "UHD60 녹화 EIS 검토",
    description: "d",
    domain: "camera_recording",
    scenario_class: "quality_feature",
    scenario_group_id: "camera_recording_kpi",
    primary_kpis: ["power", "ddr_bw"],
    project_relevance: ["project_u"],
  },
];

const projects = [
  { id: "project_u", name: "Project U", type: "mobile", phase: "mp" },
];

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
      if (url.includes("/api/v1/scenarios")) return jsonResponse(scenarios);
      if (url.includes("/api/v1/projects")) return jsonResponse(projects);
      return jsonResponse([]);
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ScenarioListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ScenarioListPage", () => {
  it("시나리오 카드를 렌더링한다", async () => {
    renderPage();
    expect(await screen.findByText("UHD60 녹화 EIS 검토")).toBeInTheDocument();
    expect(screen.getByText(ko.scenario_list.title)).toBeInTheDocument();
    expect(screen.getByText("power")).toBeInTheDocument();
  });

  it("프로젝트 필터 버튼을 렌더링한다", async () => {
    renderPage();
    expect(await screen.findByText("Project U")).toBeInTheDocument();
    expect(screen.getByText(ko.scenario_list.filter_all)).toBeInTheDocument();
  });
});
