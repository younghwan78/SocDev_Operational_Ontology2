// 결정 재진입 CSV 계약 고정 — internal_docs/design/11_decision_reentry.md §2.1.
// backend tests/test_ingest.py::test_decision_csv_template_matches_mapping_contract와 쌍:
// 같은 헤더 리터럴을 양쪽에서 검증해 한쪽 단독 변경을 드러낸다.
import { describe, expect, it } from "vitest";
import type { ReviewPackDocument } from "../api/client";
import { DECISION_CSV_HEADER, toDecisionCsv } from "../pages/ReviewPage";

const CONTRACT_HEADER = [
  "결정 ID",
  "프로젝트 ID",
  "회의 이벤트 ID",
  "시나리오 ID",
  "시나리오",
  "항목종류",
  "진술",
  "근거",
  "근거 유형",
  "신뢰등급",
  "확신도",
  "결정",
  "결정 유형",
  "트레이드오프 요약",
  "미해결 리스크",
  "담당",
  "상태",
];

const doc = {
  pack_id: "pack_x",
  title: "팩",
  purpose: "목적",
  project_ids: ["project_w"],
  scenarios: [
    {
      scenario_id: "scn_a",
      scenario_name: "시나리오 A",
      generated_context: "",
      provenance_note: "",
      evidence_posture: null,
      sections: [
        {
          kind: "risk",
          kind_ko: "위험 근거",
          title: "위험",
          items: [
            {
              statement: "진술1",
              basis: [
                {
                  rule: "open_issue",
                  rule_ko: "미해결 이슈",
                  ref_id: "ev_1",
                  ref_collection: "evidence_catalog",
                  description: "",
                  source_refs: [],
                },
              ],
              suggested_role_ko: null,
              strength_ko: "실측·정합",
            },
            {
              statement: "진술2 (근거 없음 항목)",
              basis: [],
              suggested_role_ko: null,
              strength_ko: null,
            },
          ],
        },
      ],
    },
  ],
  rollup: null,
  provenance_note: "",
} as unknown as ReviewPackDocument;

describe("결정 재진입 CSV 템플릿", () => {
  it("헤더가 설계 11 §2.1 계약과 일치한다", () => {
    expect([...DECISION_CSV_HEADER]).toEqual(CONTRACT_HEADER);
  });

  it("시스템 컬럼을 프리필하고 사람 컬럼은 비운다", () => {
    const lines = toDecisionCsv(doc).split("\r\n");
    expect(lines).toHaveLength(3);
    expect(lines[0]).toBe(CONTRACT_HEADER.map((h) => `"${h}"`).join(","));

    const row1 = lines[1].split(",");
    expect(row1[0]).toBe('"decision_pack_x_r1"'); // 결정 ID 제안
    expect(row1[1]).toBe('"project_w"'); // 단일 프로젝트 팩은 프리필
    expect(row1[2]).toBe('""'); // 회의 이벤트 ID는 사람
    expect(row1[3]).toBe('"scn_a"');
    expect(row1[7]).toBe('"ev_1"');
    expect(row1[8]).toBe('"evidence_catalog"');
    expect(row1[10]).toBe('"medium"'); // 확신도 기본
    expect(row1[11]).toBe('""'); // 결정은 사람

    const row2 = lines[2].split(",");
    expect(row2[0]).toBe('"decision_pack_x_r2"');
    expect(row2[8]).toBe('"review_item"'); // 근거 없는 항목의 기본 근거 유형
  });

  it("다중 프로젝트 팩은 프로젝트 ID를 비워 사람이 채우게 한다", () => {
    const multi = {
      ...doc,
      project_ids: ["project_u", "project_w"],
    } as ReviewPackDocument;
    const row = toDecisionCsv(multi).split("\r\n")[1].split(",");
    expect(row[1]).toBe('""');
  });
});
