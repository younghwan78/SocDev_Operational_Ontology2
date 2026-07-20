/** G1 (설계 26): 게이트 콘솔 홈 — A0 판정 배너·게이트 전환·신뢰도 줄·now-what. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GateConsolePage } from "../pages/GateConsolePage";

const review = (milestoneId: string, week: number, notMet: number) => ({
  review: {
    milestone_id: milestoneId,
    milestone_title: `게이트 ${milestoneId}`,
    project_id: "project_u",
    week,
    met: notMet > 0 ? 0 : 1,
    not_met: notMet,
    not_evaluable: 0,
    criteria: [
      {
        criterion_id: "c1",
        kind: "max_open_issues",
        kind_ko: "미해결 이슈 상한",
        description: "미해결 0건",
        verdict: notMet > 0 ? "not_met" : "met",
        verdict_ko: notMet > 0 ? "미충족" : "충족",
        note_ko: notMet > 0 ? "미해결 2건 / 허용 0건" : "미해결 0건 / 허용 0건",
        basis: [],
      },
    ],
  },
  verdict_line_ko:
    notMet > 0 ? "미충족 1/1 — 지배 요인: 미해결 이슈 2건" : "전 기준 충족 1/1",
  dominant:
    notMet > 0
      ? {
          criterion_id: "c1",
          kind: "max_open_issues",
          kind_ko: "미해결 이슈 상한",
          headline_ko: "미해결 이슈 2건",
          drill: "issues",
        }
      : null,
});

const consoleData = {
  reference_week: 15,
  rule_note_ko: "게이트 자동 선택: 기준 주차 이후 최근접 마일스톤.",
  projects: [
    {
      project_id: "project_u",
      project_name: "Project U",
      selected_milestone_id: "ms_next",
      selection_note_ko: "자동 선택: 기준 주차 W15 이후 최근접 게이트 (W20).",
      reviews: [review("ms_next", 20, 1), review("ms_far", 30, 0)],
      trust: {
        issue_total: 4,
        issue_linked: 3,
        latest_batch_at: "2026-07-18T10:00:00+00:00",
        note_ko: "연결률과 반입 시각은 이 판정의 시야 한계다",
      },
    },
    {
      project_id: "project_w",
      project_name: "Project W",
      selected_milestone_id: null,
      selection_note_ko: "게이트 미지정 — exit 기준이 정의된 마일스톤이 없다.",
      reviews: [],
      trust: { issue_total: 0, issue_linked: 0, latest_batch_at: null, note_ko: "-" },
    },
  ],
};

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: Request) => {
      const url = typeof input === "string" ? input : input.url;
      const body = url.includes("/api/v1/gate-console") ? consoleData : [];
      return Promise.resolve(
        new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
}

beforeEach(() => stubFetch());

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GateConsolePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("GateConsolePage (설계 26 G1)", () => {
  it("판정 배너 한 줄 + 지배 요인 + 기준 주차를 보여준다", async () => {
    renderPage();
    expect(
      await screen.findByText("미충족 1/1 — 지배 요인: 미해결 이슈 2건"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/기준 주차 W15/).length).toBeGreaterThan(0);
    // GO/NO-GO 어휘 없음 — 판정은 조언 (설계 23·26).
    expect(screen.queryByText(/NO-GO|GO\b/)).not.toBeInTheDocument();
  });

  it("신뢰도 줄 — 연결률과 최근 반입 시각을 배너가 스스로 말한다", async () => {
    renderPage();
    expect(await screen.findByText(/이슈 연결률 3\/4 \(75%\)/)).toBeInTheDocument();
    expect(screen.getByText(/최근 반입 2026-07-18/)).toBeInTheDocument();
  });

  it("게이트 드롭다운 전환 시 다른 게이트 판정을 보여준다 (재요청 없음)", async () => {
    renderPage();
    await screen.findByText("미충족 1/1 — 지배 요인: 미해결 이슈 2건");
    fireEvent.change(screen.getByLabelText("게이트 선택"), {
      target: { value: "ms_far" },
    });
    expect(screen.getByText("전 기준 충족 1/1")).toBeInTheDocument();
  });

  it("게이트 없는 과제는 '게이트 미지정'으로 정직 표기한다", async () => {
    renderPage();
    expect(await screen.findByText("게이트 미지정")).toBeInTheDocument();
    expect(
      screen.getByText("게이트 미지정 — exit 기준이 정의된 마일스톤이 없다."),
    ).toBeInTheDocument();
  });

  it("now-what 링크 — 지배 요인 드릴과 위험 지도/리뷰 센터로 이어진다", async () => {
    renderPage();
    await screen.findByText("미충족 1/1 — 지배 요인: 미해결 이슈 2건");
    const drill = screen.getByText(/지배 요인부터 보기/);
    expect(drill).toHaveAttribute("href", "/issues?project=project_u");
    expect(screen.getByText("위험 지도에서 보기")).toHaveAttribute(
      "href",
      "/risk-map?project=project_u",
    );
    expect(screen.getByText("리뷰 센터로")).toHaveAttribute("href", "/review");
  });
});
