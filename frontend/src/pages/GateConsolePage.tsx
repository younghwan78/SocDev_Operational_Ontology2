/**
 * 게이트 콘솔(홈) — A0 판정 배너 (설계 26 G1).
 *
 * "다음 게이트를 통과할 수 있는가"에 3초 안에 답한다: 과제별 자동 선택된
 * 게이트의 판정 한 줄 + 지배 요인 + 신뢰도 줄(연결률·반입 신선도).
 * GO/NO-GO 없음 — 판정은 조언이다. 모든 화면은 so-what + now-what으로 끝난다.
 *
 * 타임라인은 연간 주차 캘린더(W1~W52 고정 축, KPI 차트와 같은 inline SVG) —
 * 마일스톤이 "언제" 있는지 위치로 보이고, 전 마일스톤이 선택 가능하다:
 * 게이트(●)는 판정 배너, 기준 미정의(○)는 마일스톤 정보 + 정직 패널.
 */
import { useQuery } from "@tanstack/react-query";
import { useState, type KeyboardEvent } from "react";
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

/** 과제 하나의 카드 — 캘린더 선택 + 선택 대상에 따라 판정 배너 / 마일스톤 정보. */
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
  const currentReview = reviews.find((r) => r.review.milestone_id === milestoneId);
  const currentEntry = timeline.find((e) => e.milestone_id === milestoneId);
  const linkPct = Math.round(
    (project.trust.issue_linked / Math.max(project.trust.issue_total, 1)) * 100,
  );

  const trustLine = (
    <p className="desc" title={project.trust.note_ko}>
      {t.trust_links} {project.trust.issue_linked}/{project.trust.issue_total} ({linkPct}
      %) ·{" "}
      {project.trust.latest_batch_at
        ? `${t.trust_batch} ${project.trust.latest_batch_at.slice(0, 16).replace("T", " ")}`
        : t.trust_batch_none}
    </p>
  );

  const nowWhat = (
    <div className="chip-row">
      <span className="section-note">{t.now_what}:</span>
      {currentReview?.dominant && (
        <Link
          className="link-btn"
          to={`/${currentReview.dominant.drill}?project=${project.project_id}`}
          title={currentReview.dominant.headline_ko}
        >
          {t.drill_dominant} → {currentReview.dominant.headline_ko}
        </Link>
      )}
      <Link className="link-btn" to={`/risk-map?project=${project.project_id}`}>
        {t.drill_risk_map}
      </Link>
      <Link className="link-btn" to="/review">
        {t.drill_review}
      </Link>
    </div>
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
        <GateCalendar
          timeline={timeline}
          projectName={project.project_name}
          referenceWeek={referenceWeek}
          currentId={milestoneId || null}
          onSelect={setMilestoneId}
        />
      )}
      <p className="section-note">{project.selection_note_ko}</p>

      {currentReview && (
        <>
          {/* A0 판정 한 줄 — 3초 응답. 색은 상태, 뜻은 문구가 말한다 (색맹 안전). */}
          <p className="desc">
            <span
              className={`badge ${
                currentReview.review.not_met > 0
                  ? "badge-danger"
                  : currentReview.review.not_evaluable > 0
                    ? "badge-warn"
                    : "badge-ok"
              }`}
            >
              {currentReview.review.not_met > 0
                ? t.verdict_blocked
                : currentReview.review.not_evaluable > 0
                  ? t.verdict_unknown
                  : t.verdict_all_met}
            </span>{" "}
            <b>{currentReview.verdict_line_ko}</b>
          </p>
          {/* 신뢰도 줄 — 이 판정이 못 보는 것을 배너 스스로 말한다. */}
          {trustLine}
          {/* now-what — 막다른 화면 금지 (설계 26 P3). */}
          {nowWhat}
          {/* 기준별 판정 상세 — 설계 23 게이트 카드 재사용 (드릴 시에만 펼침). */}
          <details>
            <summary className="section-note">{t.criteria_detail}</summary>
            <MilestoneGates gates={[currentReview.review]} />
          </details>
        </>
      )}

      {/* 기준 미정의 마일스톤 선택 — 판정 대신 일정 정보 + 정직 표기. */}
      {!currentReview && currentEntry && (
        <>
          <p className="desc">
            <span className="badge badge-warn">{t.no_criteria}</span>{" "}
            <b>
              {currentEntry.week != null
                ? `${t.week_prefix}${currentEntry.week} `
                : `${t.week_unknown} `}
              {currentEntry.title}
            </b>
            {currentEntry.quarter ? ` · ${currentEntry.quarter}` : ""}
          </p>
          {currentEntry.description && <p className="desc">{currentEntry.description}</p>}
          <p className="section-note">{t.no_criteria_hint}</p>
          {trustLine}
          {nowWhat}
        </>
      )}
    </div>
  );
}

// --- 연간 주차 캘린더 (inline SVG — 라이브러리 없음, KPI 차트와 동일 태도) ---

const CAL_W = 1040;
const CAL_H = 96;
const PAD_X = 24;
const TRACK_Y = 60; // 기준선
const ALT_Y = 36; // 근접 마커의 위 단(겹침 회피)
const YEAR_WEEKS = 52;

function weekX(week: number): number {
  const clamped = Math.min(Math.max(week, 1), YEAR_WEEKS);
  return PAD_X + ((clamped - 1) / (YEAR_WEEKS - 1)) * (CAL_W - PAD_X * 2);
}

function markerAria(entry: GateTimelineEntry): string {
  const when =
    entry.week != null ? `${t.week_prefix}${entry.week}` : t.week_unknown;
  const state = entry.has_gate ? (entry.verdict_ko ?? "") : t.no_criteria;
  return `${when} ${entry.title} — ${state}`;
}

function dotClass(entry: GateTimelineEntry): string {
  if (!entry.has_gate) return "dot-none";
  return entry.verdict === "not_met"
    ? "dot-danger"
    : entry.verdict === "not_evaluable"
      ? "dot-warn"
      : "dot-ok";
}

/** 근접 마커(26px 미만)는 위 단으로, 근접 게이트 라벨(110px 미만)은 한 단 더
 * 위로 번갈아 올린다 — 겹침 회피 (순수 계산). */
function layoutMarkers(
  dated: GateTimelineEntry[],
): { entry: GateTimelineEntry; x: number; y: number; labelY: number }[] {
  let lastX = Number.NEGATIVE_INFINITY;
  let lastRaised = false;
  let lastLabelX = Number.NEGATIVE_INFINITY;
  let lastLabelHigh = false;
  return dated.map((entry) => {
    const x = weekX(entry.week ?? 1);
    const raised = x - lastX < 26 ? !lastRaised : false;
    lastX = x;
    lastRaised = raised;
    const y = raised ? ALT_Y : TRACK_Y;
    let labelHigh = false;
    if (entry.has_gate) {
      labelHigh = x - lastLabelX < 110 ? !lastLabelHigh : false;
      lastLabelX = x;
      lastLabelHigh = labelHigh;
    }
    return { entry, x, y, labelY: labelHigh ? y - 24 : y - 12 };
  });
}

/** 축 가장자리에서 텍스트가 잘리지 않게 anchor를 정한다. */
function edgeAnchor(x: number, margin: number): "start" | "middle" | "end" {
  if (x < margin) return "start";
  if (x + margin > CAL_W) return "end";
  return "middle";
}

/** 라벨 축약 — 마일스톤 제목의 과제명 접두는 카드가 이미 말하므로 떼고, 길면 자른다. */
function shortTitle(title: string, projectName: string): string {
  const stripped = title.startsWith(`${projectName} `)
    ? title.slice(projectName.length + 1)
    : title;
  return stripped.length > 18 ? `${stripped.slice(0, 17)}…` : stripped;
}

/** 연간 캘린더 — 마일스톤이 몇 주차에 있는지 위치로 보인다. 전 마커 클릭 가능. */
function GateCalendar({
  timeline,
  projectName,
  referenceWeek,
  currentId,
  onSelect,
}: {
  timeline: GateTimelineEntry[];
  projectName: string;
  referenceWeek: number | null;
  currentId: string | null;
  onSelect: (milestoneId: string) => void;
}) {
  const dated = timeline.filter((e) => e.week != null);
  const weekless = timeline.filter((e) => e.week == null);
  const positions = layoutMarkers(dated);

  const quarters = [
    { label: "Q1", start: 1 },
    { label: "Q2", start: 14 },
    { label: "Q3", start: 27 },
    { label: "Q4", start: 40 },
  ];
  const refX = referenceWeek != null ? weekX(referenceWeek) : null;
  const refAnchor = refX == null ? "middle" : edgeAnchor(refX, 90);

  const select = (entry: GateTimelineEntry) => () => onSelect(entry.milestone_id);
  const keySelect = (entry: GateTimelineEntry) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(entry.milestone_id);
    }
  };

  return (
    <div className="gate-cal-wrap">
      <svg
        className="gate-cal"
        viewBox={`0 0 ${CAL_W} ${CAL_H}`}
        role="group"
        aria-label={t.timeline_label}
      >
        {/* 분기 눈금 + 주차 라벨 */}
        {quarters.map((q) => (
          <g key={q.label}>
            <line
              className="cal-grid"
              x1={weekX(q.start)}
              x2={weekX(q.start)}
              y1={24}
              y2={TRACK_Y + 8}
            />
            <text className="cal-text" x={weekX(q.start + 6)} y={CAL_H - 6} textAnchor="middle">
              {q.label}
            </text>
            <text className="cal-text" x={weekX(q.start)} y={TRACK_Y + 22} textAnchor="middle">
              {t.week_prefix}
              {q.start}
            </text>
          </g>
        ))}
        <line
          className="cal-grid"
          x1={weekX(YEAR_WEEKS)}
          x2={weekX(YEAR_WEEKS)}
          y1={24}
          y2={TRACK_Y + 8}
        />
        <text className="cal-text" x={weekX(YEAR_WEEKS)} y={TRACK_Y + 22} textAnchor="middle">
          {t.week_prefix}
          {YEAR_WEEKS}
        </text>
        {/* 기준선 */}
        <line className="cal-track" x1={PAD_X} x2={CAL_W - PAD_X} y1={TRACK_Y} y2={TRACK_Y} />
        {/* 현재 주차 — 자동 선택 룰의 기준점이 위치로 보인다 */}
        {refX != null && (
          <g>
            <line className="cal-now-line" x1={refX} x2={refX} y1={16} y2={TRACK_Y + 8} />
            <text className="cal-now-text" x={refX} y={12} textAnchor={refAnchor}>
              ▸ {t.now_marker} {t.week_prefix}
              {referenceWeek}
            </text>
          </g>
        )}
        {/* 마일스톤 마커 — ●=게이트(판정 색) ○=기준 미정의, 전부 선택 가능 */}
        {positions.map(({ entry, x, y, labelY }) => (
          <g
            key={entry.milestone_id}
            className="gate-marker"
            role="button"
            tabIndex={0}
            aria-label={markerAria(entry)}
            aria-pressed={entry.milestone_id === currentId}
            onClick={select(entry)}
            onKeyDown={keySelect(entry)}
          >
            {y !== TRACK_Y && <line className="cal-stem" x1={x} x2={x} y1={y} y2={TRACK_Y} />}
            {entry.milestone_id === currentId && (
              <circle className="cal-ring" cx={x} cy={y} r={11} />
            )}
            <circle className={`cal-dot ${dotClass(entry)}`} cx={x} cy={y} r={6.5} />
            {/* 게이트만 상시 라벨 — 훑어보기 복원 (기준 미정의는 tooltip/클릭). */}
            {entry.has_gate && (
              <text
                className="cal-label"
                x={x}
                y={labelY}
                textAnchor={edgeAnchor(x, 120)}
              >
                {t.week_prefix}
                {entry.week} {shortTitle(entry.title, projectName)}
              </text>
            )}
            <title>{markerAria(entry)}</title>
          </g>
        ))}
      </svg>
      {/* 주차 미상 마일스톤 — 축에 놓을 수 없어 칩으로 (역시 선택 가능) */}
      {weekless.length > 0 && (
        <div className="chip-row">
          {weekless.map((entry) => (
            <button
              key={entry.milestone_id}
              type="button"
              className={`chip chip-btn gate-chip${
                entry.milestone_id === currentId ? " active" : ""
              }`}
              aria-pressed={entry.milestone_id === currentId}
              title={markerAria(entry)}
              onClick={() => onSelect(entry.milestone_id)}
            >
              <span className={`gate-dot ${dotClass(entry)}`} aria-hidden="true" />
              {t.week_unknown} {entry.title}
              {!entry.has_gate && ` · ${t.no_criteria}`}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
