/** W1 (설계 22): 결정 리플레이 링크 — 캡처 이전은 링크 미생성, 워터마크는 asof로 배선. */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { DecisionWatermark } from "../api/client";
import { DecisionReplayLinks, replayAsOfValue } from "../pages/ReviewPage";

function renderLinks(watermark: DecisionWatermark) {
  return render(
    <MemoryRouter>
      <DecisionReplayLinks watermark={watermark} />
    </MemoryRouter>,
  );
}

describe("DecisionReplayLinks", () => {
  it("캡처 이전 결정은 배지만 보이고 리플레이 링크를 만들지 않는다", () => {
    renderLinks({
      decision_id: "dec_e",
      project_id: "project_u",
      recorded_at: null,
      batch_id: null,
      source: "precapture",
      note_ko: "캡처 이전 결정 — 버전 로그가 없어 당시 상태를 재생할 수 없다.",
    });
    expect(screen.getByText("캡처 이전 결정")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("워터마크가 있으면 당시/비교 링크가 asof 파라미터로 배선된다", () => {
    renderLinks({
      decision_id: "dec_a",
      project_id: "project_u",
      recorded_at: "2026-07-14T09:12:00+00:00",
      batch_id: "batch_1",
      source: "version_log",
      note_ko: "버전 로그 첫 기록 시각.",
    });
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    const replayHref = decodeURIComponent(links[0].getAttribute("href") ?? "");
    expect(replayHref).toContain("project=project_u");
    expect(replayHref).toMatch(/asof=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/);
    const diffHref = decodeURIComponent(links[1].getAttribute("href") ?? "");
    expect(diffHref).toContain("asofb=");
  });

  it("초 단위 워터마크는 분으로 올림한다 — 결정 자신의 배치가 재생에 포함", () => {
    const rounded = replayAsOfValue("2026-07-14T09:12:37+00:00");
    const exact = replayAsOfValue("2026-07-14T09:12:00+00:00");
    // 내림이면 두 값이 같아진다 — 올림은 정확히 1분 뒤.
    expect(new Date(rounded).getTime() - new Date(exact).getTime()).toBe(60_000);
  });
});
