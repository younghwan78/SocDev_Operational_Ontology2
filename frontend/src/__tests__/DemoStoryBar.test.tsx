import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { DemoStoryBar } from "../components/DemoStoryBar";
import { ko } from "../i18n/ko";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DemoStoryBar />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("DemoStoryBar", () => {
  it("story 파라미터가 없으면 렌더링하지 않는다", () => {
    renderAt("/");
    expect(screen.queryByText(ko.demo.s1_title)).not.toBeInTheDocument();
  });

  it("장면 1에서 시작해 다음 장면으로 클릭만으로 진행한다", () => {
    renderAt("/?story=1");
    expect(screen.getByText(ko.demo.s1_title)).toBeInTheDocument();
    expect(screen.getByText(ko.demo.s1_desc)).toBeInTheDocument();
    fireEvent.click(screen.getByText(ko.demo.next));
    expect(screen.getByText(ko.demo.s2_title)).toBeInTheDocument();
    fireEvent.click(screen.getByText(ko.demo.next));
    expect(screen.getByText(ko.demo.s3_title)).toBeInTheDocument();
    fireEvent.click(screen.getByText(ko.demo.next));
    expect(screen.getByText(ko.demo.s4_title)).toBeInTheDocument();
  });

  it("마지막 장면의 다음 클릭 시 TAT 요약을 표시한다", () => {
    renderAt("/?story=4");
    fireEvent.click(screen.getByText(ko.demo.next));
    expect(screen.getByText(ko.demo.summary_title)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ko.demo.total))).toBeInTheDocument();
    // 장면 기록이 로그에 남는다 (앱 내 TAT 로그)
    const run = JSON.parse(localStorage.getItem("soc_tat_run") ?? "[]");
    expect(run.length).toBeGreaterThan(0);
    expect(run[run.length - 1].scene).toBe("evidence");
  });
});
