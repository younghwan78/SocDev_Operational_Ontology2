/** 설계 23: 마일스톤 게이트 섹션 — 배지 3종·근거·빈 게이트 미렌더. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { MilestoneGateReview } from "../api/client";
import { MilestoneGates } from "../pages/ReviewPage";

const gates: MilestoneGateReview[] = [
  {
    milestone_id: "project_w_spec_freeze_q2",
    milestone_title: "Project W specification freeze",
    project_id: "project_w",
    week: 21,
    met: 1,
    not_met: 1,
    not_evaluable: 1,
    criteria: [
      {
        criterion_id: "c1",
        kind: "required_evidence",
        kind_ko: "요구 근거 존재",
        description: "스펙 확정 전 실측 근거 확보",
        verdict: "not_met",
        verdict_ko: "미충족",
        note_ko: "요구 근거 유형 1종 중 1종 누락",
        basis: [
          {
            ref_collection: "evidence_catalog",
            ref_id: "missing:current_project_measurement",
            note_ko: "요구 유형 'current_project_measurement'의 가용(available) 근거 없음",
          },
        ],
      },
      {
        criterion_id: "c2",
        kind: "max_open_issues",
        kind_ko: "미해결 이슈 상한",
        description: "높음 이상 미해결 0건",
        verdict: "met",
        verdict_ko: "충족",
        note_ko: "미해결 0건 / 허용 0건",
        basis: [],
      },
      {
        criterion_id: "c3",
        kind: "future_kind",
        kind_ko: "future_kind",
        description: "미래 기준",
        verdict: "not_evaluable",
        verdict_ko: "판정 불가",
        note_ko: "미등재 기준 유형 'future_kind' — 판정 룰이 없다.",
        basis: [],
      },
    ],
  },
];

describe("MilestoneGates (설계 23)", () => {
  it("판정 배지 3종과 근거 행을 렌더한다", () => {
    render(<MilestoneGates gates={gates} />);
    expect(screen.getByText("마일스톤 게이트")).toBeInTheDocument();
    expect(screen.getByText("Project W specification freeze")).toBeInTheDocument();
    expect(screen.getByText("미충족")).toBeInTheDocument();
    expect(screen.getByText("충족")).toBeInTheDocument();
    expect(screen.getByText("판정 불가")).toBeInTheDocument();
    expect(
      screen.getByText(/가용\(available\) 근거 없음/),
    ).toBeInTheDocument();
    expect(screen.getByText("W21")).toBeInTheDocument();
  });

  it("게이트가 없으면 아무것도 렌더하지 않는다", () => {
    const { container } = render(<MilestoneGates gates={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
