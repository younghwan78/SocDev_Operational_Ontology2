// 접근성 smoke (U3) — 질문 화면 렌더 후 axe serious/critical 위반 0을 게이트로.
// jsdom 한계(색 대비 등 미검출)는 수동 점검으로 보완한다 — 설계 13 §P1-D.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import axe from "axe-core";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AskPage } from "../pages/AskPage";
import { IngestPage } from "../pages/IngestPage";
import { IssueAnalysisPage } from "../pages/IssueAnalysisPage";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function stubApi() {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = input instanceof Request ? input.url : String(input);
      if (url.includes("/ask/presets"))
        return jsonResponse([{ id: "p1", question: "테스트 프리셋 질문?" }]);
      if (url.includes("/meta/labels")) return jsonResponse({});
      if (url.includes("/meta/glossary"))
        return jsonResponse({ objects: {}, fields: {}, enums: {}, value_labels: {} });
      if (url.includes("/ingest/mappings"))
        return jsonResponse([
          {
            name: "issues",
            label_ko: "개발 이슈",
            target_collection: "issues",
            columns: ["이슈 ID", "제목"],
            required_columns: ["이슈 ID"],
          },
        ]);
      if (url.includes("/ingest/batches")) return jsonResponse([]);
      if (url.includes("/issues"))
        return jsonResponse([
          {
            issue_id: "i1",
            project_id: "project_u",
            title: "테스트 이슈",
            issue_type: "underrun",
            status: "open",
            verification: "no_tests",
            verification_ko: "검증 테스트 없음",
            closed_without_verification: false,
          },
        ]);
      if (url.includes("/projects"))
        return jsonResponse([{ id: "project_u", name: "Project U" }]);
      return jsonResponse([]);
    }),
  );
}

async function expectNoSeriousViolations(node: ReactNode) {
  stubApi();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container, findAllByText, unmount } = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
  await findAllByText(/./); // 첫 렌더 완료 대기
  const results = await axe.run(container, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } }, // jsdom 미지원
  });
  const serious = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact ?? ""),
  );
  expect(
    serious.map((violation) => `${violation.id}: ${violation.help}`),
  ).toEqual([]);
  unmount();
}

afterEach(() => vi.unstubAllGlobals());

describe("접근성 smoke (serious/critical 0)", () => {
  it("Ask SoC", async () => {
    await expectNoSeriousViolations(<AskPage />);
  });
  it("이슈 분석", async () => {
    await expectNoSeriousViolations(<IssueAnalysisPage />);
  });
  it("데이터 반입", async () => {
    await expectNoSeriousViolations(<IngestPage />);
  });
});
