import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ko } from "../i18n/ko";
import { AskPage } from "../pages/AskPage";

const presets = [
  { id: "preset_risky_ip", question: "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?" },
  { id: "preset_top_risk", question: "지금 risk가 가장 높은 scenario는 무엇인가?" },
];

const askResult = {
  question: "UHD60 recording에서 현재 가장 위험한 IP는 무엇인가?",
  provider: "deterministic",
  model_name: null,
  answer: "질문과 관련해 수집된 객체 기준의 요약입니다:\n· [시나리오] UHD60 녹화 (EIS) — 위험 등급 높음",
  confidence: "low",
  derivation: "키워드 검색과 결정론 상태 요약으로 구성 (LLM 미개입)",
  citations: ["uhd60_recording_eis_on"],
  cards: [
    {
      ref_id: "uhd60_recording_eis_on",
      collection: "scenarios",
      collection_ko: "시나리오",
      title: "UHD60 녹화 (EIS)",
      snippet: "UHD60 recording scenario for EIS and HDR review.",
      status_ko: "위험 등급 높음 (셀: ip_isp)",
      matched_terms: ["uhd60", "recording"],
    },
    {
      ref_id: "issue_isp_hdr_latency_closed_unverified_u",
      collection: "issues",
      collection_ko: "이슈",
      title: "HDR 경로 지연",
      snippet: "HDR blending latency exceeds preview deadline.",
      status_ko: "상태 closed · 검증 테스트 없음",
      matched_terms: ["hdr"],
    },
  ],
  validation_notes: [],
  duration_ms: 3,
  note_ko: "근거 인용 답변이며 결정이 아닙니다 · 인용은 수집된 객체로 한정",
};

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
      if (url.includes("/api/v1/ask/presets")) return jsonResponse(presets);
      if (url.includes("/api/v1/ask/preview"))
        return jsonResponse({
          question: askResult.question,
          cards: askResult.cards,
          unmatched_terms: [],
        });
      if (url.includes("/api/v1/ask/history")) return jsonResponse([]);
      if (url.includes("/api/v1/ask/faq")) return jsonResponse([]);
      if (url.includes("/api/v1/ask")) return jsonResponse(askResult);
      return jsonResponse([]);
    }),
  );
});

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/ask"]}>
        <AskPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AskPage", () => {
  it("프리셋 질문을 표시하고 클릭 시 답변을 렌더링한다", async () => {
    renderPage();
    const preset = await screen.findByText(presets[0].question);
    fireEvent.click(preset);
    expect(await screen.findByText(/수집된 객체 기준의 요약/)).toBeInTheDocument();
    expect(screen.getByText(new RegExp(ko.advisory.provider_deterministic))).toBeInTheDocument();
    expect(screen.getByText(/관련 객체 \(2\)/)).toBeInTheDocument();
    expect(screen.getAllByText("UHD60 녹화 (EIS)").length).toBeGreaterThan(0);
    expect(screen.getByText(ko.ask.issue_link)).toBeInTheDocument();
  });

  it("입력창 질의도 동작한다", async () => {
    renderPage();
    await screen.findByText(presets[0].question);
    fireEvent.change(screen.getByPlaceholderText(ko.ask.placeholder), {
      target: { value: "ISP power issue" },
    });
    fireEvent.click(screen.getByRole("button", { name: ko.ask.submit }));
    expect(await screen.findByText(/수집된 객체 기준의 요약/)).toBeInTheDocument();
  });

  it("내부 ID를 화면 텍스트로 노출하지 않는다 (hover 제외)", async () => {
    renderPage();
    fireEvent.click(await screen.findByText(presets[0].question));
    await screen.findByText(/수집된 객체 기준의 요약/);
    expect(screen.queryByText("uhd60_recording_eis_on")).not.toBeInTheDocument();
    expect(
      screen.queryByText("issue_isp_hdr_latency_closed_unverified_u"),
    ).not.toBeInTheDocument();
  });
});

describe("A2 인라인 각주 + A5 FAQ", () => {
  it("본문 [id] 마커가 각주 칩으로 렌더링되고 클릭 대상이 된다", async () => {
    const withMarkers = {
      ...askResult,
      provider: "claude_cli",
      answer:
        "UHD60 시나리오가 높음 등급입니다 [uhd60_recording_eis_on]. HDR 이슈 이력도 있습니다 [issue_isp_hdr_latency_closed_unverified_u].",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: Request) => {
        const url = typeof input === "string" ? input : input.url;
        if (url.includes("/ask/presets")) return jsonResponse(presets);
        if (url.includes("/ask/preview"))
          return jsonResponse({ question: "", cards: withMarkers.cards, unmatched_terms: [] });
        if (url.includes("/ask/history")) return jsonResponse([]);
        if (url.includes("/ask/faq")) return jsonResponse([]);
        if (url.includes("/api/v1/ask")) return jsonResponse(withMarkers);
        return jsonResponse([]);
      }),
    );
    renderPage();
    fireEvent.click(await screen.findByText(presets[0].question));
    const fn1 = await screen.findByRole("button", { name: "1" });
    const fn2 = screen.getByRole("button", { name: "2" });
    expect(fn1).toHaveAttribute("title", "UHD60 녹화 (EIS)");
    expect(fn2).toHaveAttribute("title", "HDR 경로 지연");
    // 마커 원문([id])은 화면 텍스트로 노출되지 않는다
    expect(screen.queryByText(/\[uhd60_recording_eis_on\]/)).not.toBeInTheDocument();
  });

  it("대기 화면에 FAQ와 최근 질문이 표시되고 클릭 시 재질의한다", async () => {
    const faq = [
      {
        question: "전력 문제가 반복된 IP는?",
        count: 3,
        last_asked: "2026-07-12T09:00:00+00:00",
        last_confidence: "medium",
        answer_preview: "전력 관련 이슈 요약…",
      },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: Request) => {
        const url = typeof input === "string" ? input : input.url;
        if (url.includes("/ask/presets")) return jsonResponse(presets);
        if (url.includes("/ask/preview"))
          return jsonResponse({ question: "", cards: askResult.cards, unmatched_terms: [] });
        if (url.includes("/ask/history"))
          return jsonResponse([
            {
              id: "ask_1",
              question: "발열 이슈?",
              normalized: "발열 이슈?",
              provider: "deterministic",
              confidence: "low",
              answer: "요약",
              citations: [],
              duration_ms: 5,
              created_at: "2026-07-12T08:00:00+00:00",
            },
          ]);
        if (url.includes("/ask/faq")) return jsonResponse(faq);
        if (url.includes("/api/v1/ask")) return jsonResponse(askResult);
        return jsonResponse([]);
      }),
    );
    renderPage();
    expect(await screen.findByText("전력 문제가 반복된 IP는?")).toBeInTheDocument();
    expect(screen.getByText("×3")).toBeInTheDocument();
    expect(screen.getByText("발열 이슈?")).toBeInTheDocument();
    fireEvent.click(screen.getByText("전력 문제가 반복된 IP는?"));
    expect(await screen.findByText(/수집된 객체 기준의 요약/)).toBeInTheDocument();
  });
});
