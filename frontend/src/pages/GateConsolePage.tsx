/**
 * 게이트 콘솔(홈) — A0 판정 배너 (설계 26 G1).
 *
 * "다음 게이트를 통과할 수 있는가"에 3초 안에 답한다: 과제별 자동 선택된
 * 게이트의 판정 한 줄 + 지배 요인 + 신뢰도 줄(연결률·반입 신선도).
 * GO/NO-GO 없음 — 판정은 조언이다. 모든 화면은 so-what + now-what으로 끝난다.
 */
import { useQuery } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchGateConsole,
  type GateTimelineEntry,
  type ProjectGateConsole,
} from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { ko } from "../i18n/ko";
import { MilestoneGates } from "./ReviewPage";

const t = ko.gate_console;

export function GateConsolePage() {
  const query = useQuery({ queryKey: ["gate-console"], queryFn: fetchGateConsole });

  if (query.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (query.isError)
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;

  const { reference_week, rule_note_ko } = query.data;
  const projects = query.data.projects ?? [];
  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">
        {t.subtitle} ·{" "}
        {reference_week != null
          ? `${t.reference_week} ${t.week_prefix}${reference_week}`
          : t.reference_week_unknown}{" "}
        · {rule_note_ko}
      </p>
      {projects.length === 0 && <p className="status-msg">{ko.app.empty}</p>}
      {projects.map((project) => (
        <ProjectGateCard
          key={project.project_id}
          project={project}
          referenceWeek={reference_week ?? null}
        />
      ))}
    </div>
  );
}

/** 과제 하나의 A0 배너 — 게이트 전환은 타임라인 칩 클릭(전 게이트 판정을 이미 받음). */
function ProjectGateCard({
  project,
  referenceWeek,
}: {
  project: ProjectGateConsole;
  referenceWeek: number | null;
}) {
  const [milestoneId, setMilestoneId] = useState(project.selected_milestone_id ?? "");
  const reviews = project.reviews ?? [];
  const timeline = project.timeline ?? [];
  const current = reviews.find((r) => r.review.milestone_id === milestoneId) ?? reviews[0];
  const linkPct = Math.round(
    (project.trust.issue_linked / Math.max(project.trust.issue_total, 1)) * 100,
  );

  return (
    <div className="card" data-testid={`gate-card-${project.project_id}`}>
      <div className="head">
        <h2 className="card-title" title={project.project_id}>
          {project.project_name}
        </h2>
        {reviews.length === 0 && <span className="badge badge-warn">{t.unassigned}</span>}
      </div>
      {timeline.length > 0 && (
        <GateTimeline
          timeline={timeline}
          referenceWeek={referenceWeek}
          currentId={current?.review.milestone_id ?? null}
          onSelect={setMilestoneId}
        />
      )}
      <p className="section-note">{project.selection_note_ko}</p>

      {current && (
        <>
          {/* A0 판정 한 줄 — 3초 응답. 색은 상태, 뜻은 문구가 말한다 (색맹 안전). */}
          <p className="desc">
            <span
              className={`badge ${
                current.review.not_met > 0
                  ? "badge-danger"
                  : current.review.not_evaluable > 0
                    ? "badge-warn"
                    : "badge-ok"
              }`}
            >
              {current.review.not_met > 0
                ? t.verdict_blocked
                : current.review.not_evaluable > 0
                  ? t.verdict_unknown
                  : t.verdict_all_met}
            </span>{" "}
            <b>{current.verdict_line_ko}</b>
          </p>

          {/* 신뢰도 줄 — 이 판정이 못 보는 것을 배너 스스로 말한다. */}
          <p className="desc" title={project.trust.note_ko}>
            {t.trust_links} {project.trust.issue_linked}/{project.trust.issue_total} (
            {linkPct}%) ·{" "}
            {project.trust.latest_batch_at
              ? `${t.trust_batch} ${project.trust.latest_batch_at.slice(0, 16).replace("T", " ")}`
              : t.trust_batch_none}
          </p>

          {/* now-what — 막다른 화면 금지 (설계 26 P3). */}
          <div className="chip-row">
            <span className="section-note">{t.now_what}:</span>
            {current.dominant && (
              <Link
                className="link-btn"
                to={`/${current.dominant.drill}?project=${project.project_id}`}
                title={current.dominant.headline_ko}
              >
                {t.drill_dominant} → {current.dominant.headline_ko}
              </Link>
            )}
            <Link className="link-btn" to={`/risk-map?project=${project.project_id}`}>
              {t.drill_risk_map}
            </Link>
            <Link className="link-btn" to="/review">
              {t.drill_review}
            </Link>
          </div>

          {/* 기준별 판정 상세 — 설계 23 게이트 카드 재사용 (드릴 시에만 펼침). */}
          <details>
            <summary className="section-note">{t.criteria_detail}</summary>
            <MilestoneGates gates={[current.review]} />
          </details>
        </>
      )}
    </div>
  );
}

/** 게이트 타임라인 — 주차 순 전 마일스톤 칩 선택기. ● = exit 기준 있는 게이트
 * (판정 색, 클릭 = 배너 전환), ○ = 기준 미정의(판정 대상 아님 — 정직 표기).
 * "현재" 마커는 기준 주차 위치 — 다음 게이트가 어느 쪽인지 눈으로 보인다. */
function GateTimeline({
  timeline,
  referenceWeek,
  currentId,
  onSelect,
}: {
  timeline: GateTimelineEntry[];
  referenceWeek: number | null;
  currentId: string | null;
  onSelect: (milestoneId: string) => void;
}) {
  const dotClass = (entry: GateTimelineEntry) =>
    entry.verdict === "not_met"
      ? "dot-danger"
      : entry.verdict === "not_evaluable"
        ? "dot-warn"
        : entry.verdict === "met"
          ? "dot-ok"
          : "dot-none";
  const chipLabel = (entry: GateTimelineEntry) =>
    `${entry.week != null ? `${t.week_prefix}${entry.week}` : t.week_unknown} ${entry.title}`;
  // 현재 마커 위치: 기준 주차 이상인 첫 주차 칩 앞 — 전부 과거면 맨 뒤.
  const markerBefore =
    referenceWeek != null
      ? timeline.findIndex((e) => e.week != null && e.week >= referenceWeek)
      : -1;
  const trailingMarker =
    referenceWeek != null && markerBefore === -1 && timeline.some((e) => e.week != null);
  const nowChip = (
    <span className="gate-now">
      ▸ {t.now_marker} {t.week_prefix}
      {referenceWeek}
    </span>
  );
  return (
    <div className="chip-row gate-timeline" role="group" aria-label={t.timeline_label}>
      {timeline.map((entry, index) => (
        <Fragment key={entry.milestone_id}>
          {index === markerBefore && nowChip}
          {entry.has_gate ? (
            <button
              type="button"
              className={`chip chip-btn gate-chip${
                entry.milestone_id === currentId ? " active" : ""
              }`}
              aria-pressed={entry.milestone_id === currentId}
              title={entry.verdict_ko ?? undefined}
              onClick={() => onSelect(entry.milestone_id)}
            >
              <span className={`gate-dot ${dotClass(entry)}`} aria-hidden="true" />
              {chipLabel(entry)}
            </button>
          ) : (
            <span className="chip gate-chip gate-chip-ghost" title={t.no_criteria_hint}>
              <span className="gate-dot dot-none" aria-hidden="true" />
              {chipLabel(entry)} · {t.no_criteria}
            </span>
          )}
        </Fragment>
      ))}
      {trailingMarker && nowChip}
    </div>
  );
}
