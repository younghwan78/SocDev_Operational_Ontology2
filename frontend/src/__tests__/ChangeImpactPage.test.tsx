import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ko } from "../i18n/ko";
import { ChangeImpactPage } from "../pages/ChangeImpactPage";

const options = {
  ips: [
    {
      ip_id: "ip_isp",
      ip_name: "ISP",
      category: "functional_mm_ip",
      knobs: [{ id: "knob_isp_pixel_mode", name: "pixel_mode", category: "performance_power" }],
      capabilities: [{ id: "cap_isp_csi_pixel_mode_octa", name: "CSI pixel mode Octa", category: "csi_pixel_mode" }],
      modes: ["octa_pixel"],
    },
  ],
};

const result = {
  subject: {
    ip_id: "ip_isp",
    ip_name: "ISP",
    ip_category: "functional_mm_ip",
    knob: {
      knob_id: "knob_isp_pixel_mode",
      name: "pixel_mode",
      category: "performance_power",
      control_domain: "CSIS",
      description: "CSIS 픽셀 모드 제어",
      power_direction: "increase",
      latency_direction: "decrease",
      bandwidth_direction: "increase",
      risk_direction: "mixed",
      affected_kpis: ["ddr_bw"],
      related_scenarios: ["uhd60_recording_eis_on"],
      confidence: "medium",
      source_ref: "ref",
    },
    capability: null,
    mode: null,
    summary: "ISP · knob pixel_mode",
  },
  impacted_scenarios: [
    {
      scenario_id: "uhd60_recording_eis_on",
      scenario_name: "UHD60 녹화 (EIS)",
      project_ids: ["project_u"],
      kpi_ids: ["power"],
      reasons: [
        {
          rule: "knob_related",
          rule_ko: "knob 관련 시나리오",
          ref_id: "knob_isp_pixel_mode",
          ref_collection: "ip_knobs",
          description: "knob 'pixel_mode'의 관련 시나리오로 명시됨",
          source_refs: [],
        },
      ],
    },
  ],
  impacted_kpis: [
    { kpi_id: "ddr_bw", unit: "MB/s", direction: "lower_better", via_knob: true, scenario_ids: [] },
  ],
  chained_ips: [
    {
      rule_id: "dep_isp_pixel_mode_mif",
      ip_id: "sys_mif",
      ip_name: "MIF / Memory",
      direction: "outgoing",
      direction_ko: "선택 IP가 의존 (부하/조건 전파)",
      relationship: "bandwidth_dependency",
      condition: "픽셀 모드가 높을수록 대역폭 수요 증가",
      rationale: "근거 설명",
      confidence: "medium",
      source_ref: "ref",
    },
  ],
  checklist: [
    {
      role_id: "hw_development",
      role_name: "HW Development Agent",
      perspective: "구현 영향 검토 — 개선 필요는 feedback_items로 전달",
      basis: [
        {
          rule: "knob",
          rule_ko: "제어 knob",
          ref_id: "knob_isp_pixel_mode",
          ref_collection: "ip_knobs",
          description: "pixel_mode (CSIS)",
          source_refs: [],
        },
      ],
    },
  ],
  similar_cases: [
    {
      kind: "issue",
      kind_ko: "과거 이슈",
      ref_id: "issue_u_uhd60_eis_power_gap",
      title: "UHD60 EIS 전력 격차",
      status: "synthetic_open",
      why_similar: "같은 IP 'ISP' 영향 범위의 과거 이슈 — 영향 시나리오 1건 겹침",
      scenario_ids: ["uhd60_recording_eis_on"],
      source_refs: [],
    },
  ],
  export_text: "[변경 영향 분석] ISP · knob pixel_mode",
  note_ko: "결정이 아닌 검토 안내입니다 · 수치 점수 없음",
};

const labels = { uhd60_recording_eis_on: "UHD60 녹화 (EIS)", ip_isp: "ISP" };

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
    vi.fn((input: Request) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/v1/change-impact/options")) return jsonResponse(options);
      if (url.includes("/api/v1/change-impact")) return jsonResponse(result);
      if (url.includes("/api/v1/meta/labels")) return jsonResponse(labels);
      return jsonResponse([]);
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ChangeImpactPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function runAnalysis() {
  renderPage();
  const selects = await screen.findAllByRole("combobox");
  fireEvent.change(selects[0], { target: { value: "ip_isp" } });
  fireEvent.click(screen.getByRole("button", { name: ko.change_impact.run }));
  await screen.findByText("ISP · knob pixel_mode");
}

describe("ChangeImpactPage", () => {
  it("IP 선택 후 분석 실행 시 4분면을 렌더링한다", async () => {
    await runAnalysis();
    expect(screen.getByText(/영향 시나리오 \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/영향 KPI \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/연쇄 IP \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/검토 체크리스트/)).toBeInTheDocument();
    expect(screen.getByText("MIF / Memory")).toBeInTheDocument();
    expect(screen.getByText(/feedback_items로 전달/)).toBeInTheDocument();
    expect(screen.getByText("UHD60 EIS 전력 격차")).toBeInTheDocument();
  });

  it("체크리스트 복사 버튼이 export 텍스트를 클립보드에 쓴다", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.assign(navigator, { clipboard: { writeText } });
    await runAnalysis();
    fireEvent.click(screen.getByRole("button", { name: ko.change_impact.copy_checklist }));
    await waitFor(() => expect(screen.getByText(ko.change_impact.copied)).toBeInTheDocument());
    expect(writeText).toHaveBeenCalledWith("[변경 영향 분석] ISP · knob pixel_mode");
  });

  it("내부 ID를 화면 텍스트로 노출하지 않는다 (hover 제외)", async () => {
    await runAnalysis();
    // 라벨 로드 완료(유사 사례 링크가 표시명으로 대체됨)를 기다린 뒤 ID 부재 확인.
    await waitFor(() =>
      expect(screen.getAllByText("UHD60 녹화 (EIS)").length).toBeGreaterThan(1),
    );
    expect(screen.queryByText("ip_isp")).not.toBeInTheDocument();
    expect(screen.queryByText("knob_isp_pixel_mode")).not.toBeInTheDocument();
    expect(screen.queryByText("uhd60_recording_eis_on")).not.toBeInTheDocument();
    expect(screen.queryByText("sys_mif")).not.toBeInTheDocument();
  });
});
