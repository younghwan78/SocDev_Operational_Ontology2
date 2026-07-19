/** W2 (설계 22): 출처 지도 링크 커버리지 카드 — 연결률·필드 칩·배치 추이. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SourceMapPage } from "../pages/SourceMapPage";

const sourceMap = {
  collections: [
    {
      collection: "issues",
      collection_ko: "개발 이슈",
      total: 4,
      synthetic: 4,
      imported: 0,
      integrated: 0,
      without_ref: 0,
    },
  ],
  totals: { total: 4, synthetic: 4, imported: 0, integrated: 0, real_data_note: "실데이터 0/4건" },
  links: [
    {
      collection: "issues",
      collection_ko: "개발 이슈",
      total: 4,
      linked: 1,
      fields: [
        { field: "affected_scope.scenarios", field_ko: "영향 시나리오", linked: 1 },
        { field: "verifying_test_ids", field_ko: "검증 테스트", linked: 0 },
      ],
    },
  ],
  link_note_ko: "연결률은 위험 지도·변경 영향이 볼 수 있는 범위의 한계다",
};

const batches = [
  {
    id: "b2",
    filename: "issues_2.csv",
    mapping_name: "issues",
    target_collection: "issues",
    accepted_count: 2,
    rejected_count: 0,
    updated_count: 0,
    unchanged_count: 0,
    status: "completed",
    created_at: "2026-07-18T10:00:00+00:00",
    actor: null,
    linkage_total: 4,
    linkage_connected: 3,
  },
  {
    id: "b1",
    filename: "issues_1.csv",
    mapping_name: "issues",
    target_collection: "issues",
    accepted_count: 2,
    rejected_count: 0,
    updated_count: 0,
    unchanged_count: 0,
    status: "completed",
    created_at: "2026-07-15T10:00:00+00:00",
    actor: null,
    linkage_total: 2,
    linkage_connected: 1,
  },
];

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(map: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: Request) => {
      const url = typeof input === "string" ? input : input.url;
      for (const [needle, body] of Object.entries(map)) {
        if (url.includes(needle)) return Promise.resolve(jsonResponse(body));
      }
      return Promise.resolve(jsonResponse([]));
    }),
  );
}

const linkProposals = {
  issues: [
    {
      issue_id: "iss_orphan",
      issue_title: "ISP 야간 프레임 드랍",
      project_id: "project_u",
      proposals: [
        {
          field: "affected_scope.ip_blocks",
          field_ko: "영향 IP",
          target_id: "ip_isp",
          rule: "ip_alias_token",
          rule_ko: "IP 별칭 토큰",
          basis_note_ko: "제목/증상 토큰 'isp' ↔ IP 별칭/이름",
        },
      ],
    },
  ],
  apply_note_ko: "제안은 결정론 토큰 일치 후보다 — 자동 반영되지 않는다.",
};

beforeEach(() => {
  stubFetch({
    "/api/v1/source-map": sourceMap,
    "/api/v1/ingest/batches": batches,
    "/api/v1/link-proposals": linkProposals,
    "/api/v1/entity-resolution": { aliases: [], unmatched: [] },
    "/api/v1/meta/labels": { ip_isp: "ISP", project_u: "Project U" },
  });
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SourceMapPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SourceMapPage — 링크 커버리지 (W2)", () => {
  it("연결률 카드에 컬렉션 행·필드 칩·기준선 문구를 렌더한다", async () => {
    renderPage();
    expect(await screen.findByText("온톨로지 연결률 (트윈 충실도)")).toBeInTheDocument();
    expect(screen.getByText("1/4 (25%)")).toBeInTheDocument();
    expect(screen.getByText("영향 시나리오 1")).toBeInTheDocument();
    expect(screen.getByText("검증 테스트 0")).toBeInTheDocument();
    expect(screen.getByText(/파일럿 판정 기준선 70%/)).toBeInTheDocument();
  });

  it("배치 추이는 과거→최신 순으로 나열된다", async () => {
    renderPage();
    const trend = await screen.findByText(/최근 배치 연결률/);
    expect(trend.textContent).toContain("issues_1.csv 50% → issues_2.csv 75%");
  });

  // 설계 24: 링크 제안 카드 — 제안 칩 + 근거 hover, 자동 반영 없음 안내.
  it("링크 제안 카드에 이슈·제안 칩·반영 안내를 렌더한다", async () => {
    renderPage();
    expect(await screen.findByText(/링크 제안/)).toBeInTheDocument();
    expect(screen.getByText("ISP 야간 프레임 드랍")).toBeInTheDocument();
    const chip = screen.getByText(/IP 별칭 토큰/);
    expect(chip.getAttribute("title")).toContain("ip_isp");
    expect(screen.getByText(/자동 반영되지 않는다/)).toBeInTheDocument();
  });

  it("제안이 없으면 링크 제안 카드를 렌더하지 않는다", async () => {
    stubFetch({
      "/api/v1/source-map": sourceMap,
      "/api/v1/link-proposals": { issues: [], apply_note_ko: "-" },
      "/api/v1/entity-resolution": { aliases: [], unmatched: [] },
    });
    renderPage();
    await screen.findByText("실데이터 0/4건");
    expect(screen.queryByText(/링크 제안/)).not.toBeInTheDocument();
  });

  it("links가 비면 연결률 카드를 렌더하지 않는다", async () => {
    stubFetch({
      "/api/v1/source-map": { ...sourceMap, links: [] },
      "/api/v1/entity-resolution": { aliases: [], unmatched: [] },
    });
    renderPage();
    await screen.findByText("실데이터 0/4건");
    expect(screen.queryByText("온톨로지 연결률 (트윈 충실도)")).not.toBeInTheDocument();
  });
});
