import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { TimelineItem } from "../api/client";
import { TimelineTab } from "../pages/tabs/TimelineTab";

const items: TimelineItem[] = [
  {
    week: 2,
    item_type: "event",
    item_type_ko: "개발 이벤트",
    ref_id: "evt_1",
    title: "패키지 아웃 체크포인트",
    project_id: "project_u",
    severity: "info",
    status: "recorded",
    roles: ["pm"],
  },
  {
    week: 14,
    item_type: "request",
    item_type_ko: "시나리오 요청",
    ref_id: "req_1",
    title: "UHD60 EIS 전력 검토 요청",
    project_id: "project_u",
    severity: null,
    status: "under_review",
    roles: [],
  },
];

const labels = { project_u: "Project U", pm: "PM Agent" };

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(labels), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    ),
  );
});

describe("TimelineTab", () => {
  it("주차별로 그룹핑해 렌더링한다", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <TimelineTab items={items} />
      </QueryClientProvider>,
    );
    expect(screen.getByText("W2")).toBeInTheDocument();
    expect(screen.getByText("W14")).toBeInTheDocument();
    expect(screen.getByText("개발 이벤트")).toBeInTheDocument();
    expect(screen.getByText("시나리오 요청")).toBeInTheDocument();
    expect(screen.getByText("패키지 아웃 체크포인트")).toBeInTheDocument();
    // 내부 ID 숨김 — 라벨 로드 후 role id가 표시명으로 대체된다.
    expect(await screen.findAllByText(/PM Agent/)).not.toHaveLength(0);
    expect(screen.queryByText(/·.*pm(,|$)/)).not.toBeInTheDocument();
  });
});
