/**
 * 게이트 콘솔(홈) — A0 판정 배너 (설계 26 G1).
 *
 * "다음 게이트를 통과할 수 있는가"에 3초 안에 답한다: 과제별 자동 선택된
 * 게이트의 판정 한 줄 + 지배 요인 + 신뢰도 줄(연결률·반입 신선도).
 * GO/NO-GO 없음 — 판정은 조언이다. 모든 화면은 so-what + now-what으로 끝난다.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchGateConsole, type ProjectGateConsole } from "../api/client";
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
        <ProjectGateCard key={project.project_id} project={project} />
      ))}
    </div>
  );
}

/** 과제 하나의 A0 배너 — 게이트 드롭다운 전환은 로컬 상태(전 게이트 판정을 이미 받음). */
function ProjectGateCard({ project }: { project: ProjectGateConsole }) {
  const [milestoneId, setMilestoneId] = useState(project.selected_milestone_id ?? "");
  const reviews = project.reviews ?? [];
  const current = reviews.find((r) => r.review.milestone_id === milestoneId) ?? reviews[0];
  const linkPct = Math.round(
    (project.trust.issue_linked / Math.max(project.trust.issue_total, 1)) * 100,
  );
  const selectId = `gate-select-${project.project_id}`;

  return (
    <div className="card" data-testid={`gate-card-${project.project_id}`}>
      <div className="head">
        <h2 className="card-title" title={project.project_id}>
          {project.project_name}
        </h2>
        {reviews.length > 0 ? (
          <>
            <label className="filter-label" htmlFor={selectId}>
              {t.milestone_select}
            </label>
            <select
              id={selectId}
              value={current?.review.milestone_id ?? ""}
              onChange={(e) => setMilestoneId(e.target.value)}
            >
              {reviews.map((r) => (
                <option key={r.review.milestone_id} value={r.review.milestone_id}>
                  {r.review.milestone_title}
                  {r.review.week != null ? ` (${t.week_prefix}${r.review.week})` : ""}
                </option>
              ))}
            </select>
          </>
        ) : (
          <span className="badge badge-warn">{t.unassigned}</span>
        )}
      </div>
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
