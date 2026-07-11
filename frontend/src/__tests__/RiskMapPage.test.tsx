import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RiskMapPage } from "../pages/RiskMapPage";

const projects = [
  { id: "project_u", name: "Project U", type: "mobile", phase: "mp" },
  { id: "project_v", name: "Project V", type: "mobile", phase: "development" },
];

const basisItem = {
  rule: "open_issue",
  rule_ko: "미해결 이슈",
  ref_id: "issue_u_uhd60_eis_power_gap",
  ref_collection: "issues",
  description: "미해결 이슈 'UHD60 전력 초과' — 증상: 전력 예산 초과",
  source_refs: [],
};

const heatmap = {
  columns: [{ ip_id: "ip_isp", ip_name: "ISP", category: "functional_mm_ip" }],
  rows: [
    {
      scenario_id: "uhd60_recording_eis_on",
      scenario_name: "UHD60 녹화 (EIS)",
      project_ids: ["project_u"],
      overall_grade: "high",
      overall_grade_ko: "높음",
      overall_basis: [basisItem],
      cells: [
        {
          scenario_id: "uhd60_recording_eis_on",
          ip_id: "ip_isp",
          grade: "high",
          grade_ko: "높음",
          basis: [basisItem],
        },
      ],
    },
  ],
  focus: [
    {
      kind: "priority_request",
      kind_ko: "우선 요청 근거 부족",
      ref_id: "req_uhd60_eis_power",
      ref_collection: "scenario_requests",
      title: "UHD60 EIS 전력 검토",
      description: "P1 · 누락 근거 1건: 현세대 전력 트레이스",
      week: 33,
      project_ids: ["project_u"],
      scenario_ids: ["uhd60_recording_eis_on"],
      source_refs: [],
    },
  ],
};

const labels = {
  project_u: "Project U",
  ip_isp: "ISP",
  uhd60_recording_eis_on: "UHD60 녹화 (EIS)",
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: Request) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/v1/projects")) return Promise.resolve(jsonResponse(projects));
      if (url.includes("/api/v1/risk/heatmap")) return Promise.resolve(jsonResponse(heatmap));
      if (url.includes("/api/v1/meta/labels")) return Promise.resolve(jsonResponse(labels));
      if (url.includes("/api/v1/meta/glossary"))
        return Promise.resolve(
          jsonResponse({
            objects: {},
            fields: {},
            enums: {},
            value_labels: { ip_category: { functional_mm_ip: "기능 MM IP" } },
          }),
        );
      return Promise.resolve(jsonResponse([]));
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RiskMapPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RiskMapPage", () => {
  it("heatmap과 이번 주 주목을 렌더링한다", async () => {
    renderPage();
    expect((await screen.findAllByText("UHD60 녹화 (EIS)")).length).toBeGreaterThan(0);
    expect(screen.getByText("ISP")).toBeInTheDocument();
    expect(screen.getByText("UHD60 EIS 전력 검토")).toBeInTheDocument();
    expect(screen.getAllByText("●").length).toBeGreaterThan(0);
    // W2: 열 카테고리 그룹 헤더 — 한국어 라벨, 원문 코드는 hover만.
    expect(await screen.findByText("기능 MM IP")).toBeInTheDocument();
    expect(screen.queryByText("functional_mm_ip")).not.toBeInTheDocument();
  });

  it("셀 클릭 시 근거 패널로 drill-down 한다", async () => {
    renderPage();
    await screen.findAllByText("UHD60 녹화 (EIS)");
    const cellButtons = screen.getAllByRole("button", { name: "●" });
    fireEvent.click(cellButtons[0]);
    expect(screen.getAllByText("미해결 이슈").length).toBeGreaterThan(0);
    expect(
      screen.getByText("미해결 이슈 'UHD60 전력 초과' — 증상: 전력 예산 초과"),
    ).toBeInTheDocument();
  });

  it("내부 ID를 화면 텍스트로 노출하지 않는다 (hover 제외)", async () => {
    renderPage();
    await screen.findAllByText("UHD60 녹화 (EIS)");
    expect(screen.queryByText("uhd60_recording_eis_on")).not.toBeInTheDocument();
    expect(screen.queryByText("ip_isp")).not.toBeInTheDocument();
    expect(screen.queryByText("project_u")).not.toBeInTheDocument();
  });
});
