/**
 * Ask SoC — "과거 과제에서 비슷한 문제가 있었나?" 등 자연어 질의.
 * 흐름: 질문 → 즉시 프리뷰(결정론 카드) → LLM 근거 인용 답변(체인+검증 관문).
 * 답변 본문의 [id] 마커는 각주 칩으로 렌더링되어 우측 카드와 연결된다 (A2).
 * 질의는 로그로 남아 자주 묻는 질문(FAQ)·최근 질문이 된다 (A5).
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type CSSProperties, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchAskFaq,
  fetchAskHistory,
  fetchAskPresets,
  fetchAskPreview,
  postAsk,
  type AskCard,
  type AskResult,
} from "../api/client";
import { Busy } from "../components/Busy";
import { SplitHandle, useSidePanelWidth } from "../components/SplitLayout";
import { ko } from "../i18n/ko";

const t = ko.ask;

const PROVIDER_LABELS: Record<string, string> = {
  claude_cli: ko.advisory.provider_claude,
  openai_compat: ko.advisory.provider_onprem,
  deterministic: ko.advisory.provider_deterministic,
};
const CONFIDENCE_BADGE: Record<string, string> = {
  low: "badge-danger",
  medium: "badge-warn",
  high: "badge-ok",
};
const CONFIDENCE_LABEL: Record<string, string> = {
  low: ko.risk.grade_low,
  medium: ko.risk.grade_medium,
  high: ko.risk.grade_high,
};

// A2 각주 계약 — 백엔드 _inline_citation_ids와 동일한 마커 문법.
const MARKER_RE = /\[([a-z0-9_]+)\]/g;

export function AskPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  // 질문은 URL(?q=)이 단일 소스 — state로 이중화하지 않고 파생한다.
  const question = searchParams.get("q");
  const [draft, setDraft] = useState(question ?? "");
  // URL이 외부에서 바뀌면(뒤로가기/프리셋) draft를 render 중 동기화 (effect 아님).
  const [draftFor, setDraftFor] = useState(question);
  if (question !== draftFor) {
    setDraftFor(question);
    setDraft(question ?? "");
  }
  const [highlighted, setHighlighted] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const sidePanel = useSidePanelWidth("ask-side-width");

  const presets = useQuery({ queryKey: ["ask-presets"], queryFn: fetchAskPresets });
  const faq = useQuery({ queryKey: ["ask-faq"], queryFn: fetchAskFaq });
  const history = useQuery({ queryKey: ["ask-history"], queryFn: fetchAskHistory });
  // A3 두 단계: 프리뷰(결정론, 즉시) 먼저 — LLM 답변을 기다리는 동안 카드를 보여준다.
  const preview = useQuery({
    queryKey: ["ask-preview", question],
    queryFn: () => fetchAskPreview(question!),
    enabled: question !== null,
    staleTime: Infinity,
  });
  const result = useQuery({
    queryKey: ["ask", question],
    queryFn: async () => {
      const answer = await postAsk(question!);
      void queryClient.invalidateQueries({ queryKey: ["ask-history"] });
      void queryClient.invalidateQueries({ queryKey: ["ask-faq"] });
      return answer;
    },
    enabled: question !== null,
    staleTime: Infinity,
  });

  const submit = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setHighlighted(null);
    setSearchParams({ q: trimmed });
  };

  const cards = result.data?.cards ?? preview.data?.cards ?? [];
  const unmatched = result.data?.unmatched_terms ?? preview.data?.unmatched_terms ?? [];
  const selectCitation = (refId: string) => {
    setHighlighted(refId);
    document
      .getElementById(`ask-card-${refId}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      <div className="card">
        <form
          className="ask-form"
          onSubmit={(event) => {
            event.preventDefault();
            submit(draft);
          }}
        >
          <input
            type="text"
            className="ask-input"
            name="question"
            autoFocus
            aria-label={t.placeholder}
            autoComplete="off"
            spellCheck={false}
            value={draft}
            placeholder={t.placeholder}
            onChange={(event) => setDraft(event.target.value)}
          />
          <button
            type="submit"
            className="run-btn"
            disabled={!draft.trim() || result.isFetching}
          >
            {result.isFetching ? t.asking : t.submit}
          </button>
        </form>
        <div className="filter-row">
          <span className="filter-label">{t.presets_label}</span>
          {(presets.data ?? []).map((preset) => (
            <button
              key={preset.id}
              type="button"
              className="chip chip-btn"
              onClick={() => submit(preset.question)}
            >
              {preset.question}
            </button>
          ))}
        </div>
      </div>

      {question === null && (
        <IdleBoards
          faq={faq.data ?? []}
          history={history.data ?? []}
          onAsk={submit}
        />
      )}
      {result.isError && <p className="status-msg">{ko.app.error}</p>}
      {question !== null && !result.isError && (
        <div
          className="risk-layout risk-layout-split"
          style={{ "--side-w": `${sidePanel.width}px` } as CSSProperties}
        >
          <div aria-live="polite">
            {result.data && !result.isFetching ? (
              <AskAnswer result={result.data} onCite={selectCitation} />
            ) : (
              <div className="card">
                <h2 className="card-title">{t.answer_title}</h2>
                <Busy message={t.generating} />
                <p className="desc">{t.generating_hint}</p>
              </div>
            )}
          </div>
          <SplitHandle
            width={sidePanel.width}
            onResize={sidePanel.update}
            onReset={sidePanel.reset}
            label={ko.risk.panel_resize}
          />
          <div className="risk-side">
            <div className="card">
              <h2 className="card-title">
                {t.cards_title} ({cards.length})
              </h2>
              {unmatched.length > 0 && (
                <p className="desc">
                  <span className="badge badge-warn">{t.unmatched_label}</span>{" "}
                  {unmatched.join(", ")} — {t.unmatched_hint}
                </p>
              )}
              {cards.length === 0 && preview.isFetching && <Busy message={ko.app.loading} />}
              {cards.length === 0 && !preview.isFetching && (
                <p className="desc">{ko.app.empty}</p>
              )}
              {cards.map((card) => (
                <AskCardRow
                  key={card.ref_id}
                  card={card}
                  cited={(result.data?.citations ?? []).includes(card.ref_id)}
                  highlighted={highlighted === card.ref_id}
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** A5 대기 화면 — 자주 묻는 질문(FAQ)과 최근 질문. 클릭이 곧 재질의. */
function IdleBoards({
  faq,
  history,
  onAsk,
}: {
  faq: { question: string; count: number; last_confidence: string; answer_preview: string }[];
  history: { id: string; question: string; provider: string; created_at: string }[];
  onAsk: (question: string) => void;
}) {
  if (faq.length === 0 && history.length === 0)
    return <p className="status-msg">{t.idle_hint}</p>;
  return (
    <div className="quadrant-grid">
      <div className="card">
        <h2 className="card-title">{t.faq_title}</h2>
        {faq.length === 0 && <p className="desc">{t.faq_empty}</p>}
        {faq.map((entry) => (
          <button
            key={entry.question}
            type="button"
            className="ask-log-row"
            onClick={() => onAsk(entry.question)}
          >
            <span className="head">
              <span className="title">{entry.question}</span>
              <span className="chip-count">×{entry.count}</span>
            </span>
            <span className="desc">{entry.answer_preview}</span>
          </button>
        ))}
      </div>
      <div className="card">
        <h2 className="card-title">{t.history_title}</h2>
        {history.length === 0 && <p className="desc">{t.history_empty}</p>}
        {history.slice(0, 10).map((entry) => (
          <button
            key={entry.id}
            type="button"
            className="ask-log-row"
            onClick={() => onAsk(entry.question)}
          >
            <span className="head">
              <span className="title">{entry.question}</span>
              <span className="desc">
                {PROVIDER_LABELS[entry.provider] ?? entry.provider} ·{" "}
                {entry.created_at.slice(0, 16).replace("T", " ")}
              </span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** A2 — 본문 [id] 마커를 각주 번호 칩으로 렌더링. 클릭=카드 하이라이트. */
function AnswerBody({
  answer,
  cards,
  onCite,
}: {
  answer: string;
  cards: Map<string, AskCard>;
  onCite: (refId: string) => void;
}) {
  const parts: ReactNode[] = [];
  const footnotes = new Map<string, number>();
  let lastIndex = 0;
  for (const match of answer.matchAll(MARKER_RE)) {
    const refId = match[1];
    if (!cards.has(refId)) continue; // 미지 마커는 본문 그대로 (검증 관문이 이미 걸렀음)
    parts.push(answer.slice(lastIndex, match.index));
    if (!footnotes.has(refId)) footnotes.set(refId, footnotes.size + 1);
    const number = footnotes.get(refId)!;
    parts.push(
      <button
        key={`${refId}-${match.index}`}
        type="button"
        className="cite-fn"
        title={cards.get(refId)?.title ?? refId}
        onClick={() => onCite(refId)}
      >
        {number}
      </button>,
    );
    lastIndex = (match.index ?? 0) + match[0].length;
  }
  parts.push(answer.slice(lastIndex));
  return <p className="ask-answer">{parts}</p>;
}

function AskAnswer({
  result,
  onCite,
}: {
  result: AskResult;
  onCite: (refId: string) => void;
}) {
  const cardsById = new Map(result.cards.map((card) => [card.ref_id, card]));
  const providerKind = result.provider === "deterministic" ? "badge-warn" : "badge-ok";
  return (
    <div className="card">
      <div className="head">
        <h2 className="card-title">{t.answer_title}</h2>
        <span className={`badge ${providerKind}`}>
          {PROVIDER_LABELS[result.provider] ?? result.provider}
        </span>
        <span className={`badge ${CONFIDENCE_BADGE[result.confidence] ?? "badge-info"}`}>
          {t.confidence}: {CONFIDENCE_LABEL[result.confidence] ?? result.confidence}
        </span>
        <span className="desc">
          {(result.duration_ms / 1000).toFixed(1)}
          {t.seconds_suffix}
        </span>
      </div>
      <AnswerBody answer={result.answer} cards={cardsById} onCite={onCite} />
      {result.derivation && (
        <p className="desc">
          {t.derivation}: {result.derivation}
        </p>
      )}
      {(result.citations ?? []).length > 0 && (
        <p className="desc">
          {t.citations_label}:{" "}
          {(result.citations ?? []).map((citation) => (
            <button
              key={citation}
              type="button"
              className="chip-link"
              title={citation}
              onClick={() => onCite(citation)}
            >
              {cardsById.get(citation)?.title ?? citation}
            </button>
          ))}
        </p>
      )}
      <p className="desc">
        <span className="badge badge-info">{result.note_ko}</span>
      </p>
      {(result.validation_notes ?? []).length > 0 && (
        <details className="ask-notes">
          <summary>
            {t.validation_notes} ({(result.validation_notes ?? []).length})
          </summary>
          {(result.validation_notes ?? []).map((note, index) => (
            <p key={index} className="desc">
              {note}
            </p>
          ))}
        </details>
      )}
    </div>
  );
}

function AskCardRow({
  card,
  cited,
  highlighted,
}: {
  card: AskCard;
  cited: boolean;
  highlighted: boolean;
}) {
  return (
    <div
      id={`ask-card-${card.ref_id}`}
      className={`list-item ${cited ? "ask-cited" : ""} ${highlighted ? "ask-highlight" : ""}`}
    >
      <div className="head">
        <span className="badge badge-info">{card.collection_ko}</span>
        <span className="title" title={card.ref_id}>
          {card.title}
        </span>
        {card.status_ko && (
          <span
            className={`badge ${
              { danger: "badge-danger", warn: "badge-warn", ok: "badge-ok" }[
                card.status_kind ?? ""
              ] ?? "badge-info"
            }`}
          >
            {card.status_ko}
          </span>
        )}
        {card.collection === "scenarios" && (
          <Link
            to={`/scenarios/${card.ref_id}/overview`}
            className="chip-link"
            title={card.ref_id}
          >
            {t.scenario_link}
          </Link>
        )}
        {card.collection === "issues" && (
          <Link to={`/issues?issue=${card.ref_id}`} className="chip-link" title={card.ref_id}>
            {t.issue_link}
          </Link>
        )}
      </div>
      {card.snippet && <p className="desc">{card.snippet}</p>}
      {(card.matched_terms ?? []).length > 0 && (
        <p className="desc">
          {t.matched_label}: {(card.matched_terms ?? []).join(", ")}
        </p>
      )}
    </div>
  );
}
