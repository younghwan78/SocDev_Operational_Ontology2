import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ko } from "../i18n/ko";
import { IssueAnalysisPage } from "../pages/IssueAnalysisPage";

const projects = [{ id: "project_u", name: "Project U", type: "mobile", phase: "mp" }];

const issues = [
  {
    issue_id: "issue_isp_hdr_latency_closed_unverified_u",
    title: "HDR 경로 지연 (검증 없이 종결)",
    issue_type: "latency_regression",
    status: "closed",
    project_id: "project_u",
    confidence: "medium",
    scenario_ids: ["uhd60_recording_eis_on"],
    verification: "no_tests",
    verification_ko: "검증 테스트 없음",
    closed_without_verification: true,
  },
];

const chain = {
  issue_id: "issue_isp_hdr_latency_closed_unverified_u",
  title: "HDR 경로 지연 (검증 없이 종결)",
  issue_type: "latency_regression",
  status: "closed",
  project_id: "project_u",
  confidence: "medium",
  verification: "no_tests",
  verification_ko: "검증 테스트 없음",
  closed_without_verification: true,
  alert_ko: "이슈가 종결 상태이지만 검증 테스트가 없습니다",
  nodes: [
    {
      step: "symptom",
      step_ko: "증상",
      badge: "green",
      badge_reason_ko: "근거 1건 연결",
      items: [
        {
          title: "HDR 경로 지연 (검증 없이 종결)",
          description: "HDR 켜면 프리뷰 지연 초과",
          ref_id: "issue_isp_hdr_latency_closed_unverified_u",
          ref_collection: "issues",
          badge: null,
          source_refs: [],
        },
      ],
    },
    {
      step: "impact",
      step_ko: "영향 범위",
      badge: "green",
      badge_reason_ko: "영향 시나리오/IP가 기록됨",
      items: [
        {
          title: "UHD60 녹화 (EIS)",
          description: "영향 시나리오",
          ref_id: "uhd60_recording_eis_on",
          ref_collection: "scenarios",
          badge: null,
          source_refs: [],
        },
      ],
    },
    { step: "root_cause", step_ko: "원인", badge: "yellow", badge_reason_ko: "원인이 후보 단계", items: [] },
    { step: "action", step_ko: "조치", badge: "green", badge_reason_ko: "조치가 기록됨", items: [] },
    {
      step: "verification",
      step_ko: "검증 테스트",
      badge: "red",
      badge_reason_ko: "검증 테스트 없음 — 해결 여부를 확인할 수 없음",
      items: [],
    },
    { step: "residual_risk", step_ko: "잔존 리스크", badge: "yellow", badge_reason_ko: "잔존 리스크 미기록", items: [] },
    { step: "lesson", step_ko: "재사용 교훈", badge: "yellow", badge_reason_ko: "재사용 교훈 미기록", items: [] },
  ],
};

const labels = { project_u: "Project U" };

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
      if (url.includes("/rca")) return jsonResponse(chain);
      if (url.includes("/api/v1/issues")) return jsonResponse(issues);
      if (url.includes("/api/v1/projects")) return jsonResponse(projects);
      if (url.includes("/api/v1/meta/labels")) return jsonResponse(labels);
      return jsonResponse([]);
    }),
  );
});

function renderPage(initialEntry = "/issues") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <IssueAnalysisPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("IssueAnalysisPage", () => {
  it("이슈 목록에 검증 상태 뱃지를 표시한다", async () => {
    renderPage();
    expect(await screen.findByText("HDR 경로 지연 (검증 없이 종결)")).toBeInTheDocument();
    expect(screen.getAllByText("검증 테스트 없음").length).toBeGreaterThan(0);
  });

  it("이슈 선택 시 7단 RCA 체인과 경고를 렌더링한다", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("HDR 경로 지연 (검증 없이 종결)"));
    expect(await screen.findByText(/이슈가 종결 상태이지만 검증 테스트가 없습니다/)).toBeInTheDocument();
    for (const step of ["증상", "영향 범위", "원인", "조치", "검증 테스트", "잔존 리스크", "재사용 교훈"]) {
      expect(screen.getAllByText(step).length).toBeGreaterThan(0);
    }
    expect(
      screen.getByText("검증 테스트 없음 — 해결 여부를 확인할 수 없음"),
    ).toBeInTheDocument();
    expect(screen.getByText(ko.issues.scenario_link)).toBeInTheDocument();
  });

  it("내부 ID를 화면 텍스트로 노출하지 않는다 (hover 제외)", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("HDR 경로 지연 (검증 없이 종결)"));
    await screen.findByText(/이슈가 종결 상태이지만/);
    expect(screen.queryByText("issue_isp_hdr_latency_closed_unverified_u")).not.toBeInTheDocument();
    expect(screen.queryByText("uhd60_recording_eis_on")).not.toBeInTheDocument();
    expect(screen.queryByText("project_u")).not.toBeInTheDocument();
  });
});

describe("URL=상태 재현", () => {
  it("?q= 로 진입하면 검색 입력과 목록 필터가 재현된다", async () => {
    renderPage("/issues?q=없는검색어");
    const input = (await screen.findByLabelText("검색")) as HTMLInputElement;
    expect(input.value).toBe("없는검색어");
    expect(screen.queryByText("HDR 경로 지연 (검증 없이 종결)")).not.toBeInTheDocument();
  });
});
