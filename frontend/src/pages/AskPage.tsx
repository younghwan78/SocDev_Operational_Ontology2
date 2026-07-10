/**
 * Ask SoC — "과거 과제에서 비슷한 문제가 있었나?" 등 자연어 질의.
 * 흐름: 질문 → 온톨로지 키워드 검색(결정론) → LLM 근거 인용 답변(체인+검증 관문)
 *       → LLM 미가용 시 검색 결과 요약. 인용 클릭 시 관련 객체 카드로 이동.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  fetchAskPresets,
  postAsk,
  type AskCard,
  type AskResult,
} from "../api/client";
import { Busy } from "../components/Busy";
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

  const presets = useQuery({ queryKey: ["ask-presets"], queryFn: fetchAskPresets });
  const result = useQuery({
    queryKey: ["ask", question],
    queryFn: () => postAsk(question!),
    enabled: question !== null,
    staleTime: Infinity,
  });

  const submit = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    setSearchParams({ q: trimmed });
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

      {question === null && <p className="status-msg">{t.idle_hint}</p>}
      {result.isFetching && <Busy message={t.asking} />}
      {result.isError && <p className="status-msg">{ko.app.error}</p>}
      {question !== null && result.data && !result.isFetching && (
        <div aria-live="polite">
          <AskAnswer result={result.data} />
        </div>
      )}
    </div>
  );
}

function AskAnswer({ result }: { result: AskResult }) {
  const cardsById = new Map(result.cards.map((card) => [card.ref_id, card]));
  return (
    <div>
      <div className="card">
        <div className="head">
          <h2 className="card-title">{t.answer_title}</h2>
          <span className="badge badge-ok">
            {ko.advisory.provider}: {PROVIDER_LABELS[result.provider] ?? result.provider}
          </span>
          <span className={`badge ${CONFIDENCE_BADGE[result.confidence] ?? "badge-info"}`}>
            {t.confidence}: {result.confidence}
          </span>
          <span className="badge badge-info">{result.note_ko}</span>
        </div>
        <p className="ask-answer">{result.answer}</p>
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
                onClick={() =>
                  document
                    .getElementById(`ask-card-${citation}`)
                    ?.scrollIntoView({ behavior: "smooth", block: "center" })
                }
              >
                {cardsById.get(citation)?.title ?? citation}
              </button>
            ))}
          </p>
        )}
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

      <div className="card">
        <h2 className="card-title">
          {t.cards_title} ({result.cards.length})
        </h2>
        {result.cards.length === 0 && <p className="desc">{ko.app.empty}</p>}
        {result.cards.map((card) => (
          <AskCardRow
            key={card.ref_id}
            card={card}
            cited={(result.citations ?? []).includes(card.ref_id)}
          />
        ))}
      </div>
    </div>
  );
}

function AskCardRow({ card, cited }: { card: AskCard; cited: boolean }) {
  return (
    <div id={`ask-card-${card.ref_id}`} className={`list-item ${cited ? "ask-cited" : ""}`}>
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
