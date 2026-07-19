import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  fetchActionItems,
  fetchDecisions,
  fetchDecisionWatermarks,
  fetchReviewPack,
  fetchReviewPacks,
  fetchWeeklyIndex,
  fetchWeeklySnapshot,
  uploadIngestFile,
  type DecisionWatermark,
  type IngestReport,
  type MilestoneGateReview,
  type ReviewPackDocument,
} from "../api/client";
import { useRef } from "react";
import { PostureChip } from "../components/PostureChip";
import { useValueLabels } from "../hooks/useValueLabels";
import { ErrorState } from "../components/ErrorState";
import { formatDateTime, toDateTimeLocal } from "../lib/format";
import { ko } from "../i18n/ko";

const t = ko.review;
const tp = ko.review_pack;

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

// 결정 재진입 계약 (internal_docs/design/11_decision_reentry.md §2.1) —
// backend `decisions` 매핑과 쌍. 열 변경 시 backend test_ingest도 함께 갱신한다.
export const DECISION_CSV_HEADER = [
  "결정 ID",
  "프로젝트 ID",
  "회의 이벤트 ID",
  "시나리오 ID",
  "시나리오",
  "항목종류",
  "진술",
  "근거",
  "근거 유형",
  "신뢰등급",
  "확신도",
  "결정",
  "결정 유형",
  "트레이드오프 요약",
  "미해결 리스크",
  "담당",
  "상태",
] as const;

export function toDecisionCsv(doc: ReviewPackDocument): string {
  const rows = [DECISION_CSV_HEADER.map(csvCell).join(",")];
  const projectId = doc.project_ids.length === 1 ? doc.project_ids[0] : "";
  let rowNumber = 0;
  for (const scenario of doc.scenarios) {
    for (const section of scenario.sections) {
      for (const item of section.items) {
        rowNumber += 1;
        rows.push(
          [
            `decision_${doc.pack_id}_r${rowNumber}`,
            projectId,
            "",
            scenario.scenario_id,
            scenario.scenario_name,
            section.kind_ko,
            item.statement,
            item.basis[0]?.ref_id ?? "",
            item.basis[0]?.ref_collection ?? "review_item",
            item.strength_ko ?? "",
            "medium",
            "",
            "",
            "",
            "",
            "",
            "",
          ]
            .map(csvCell)
            .join(","),
        );
      }
    }
  }
  return rows.join("\r\n");
}

export function ReviewPage() {
  const { week } = useParams<{ week: string }>();
  const navigate = useNavigate();
  const valueLabel = useValueLabels();

  const index = useQuery({ queryKey: ["weekly-index"], queryFn: fetchWeeklyIndex });
  const selectedWeek = week ? Number(week) : undefined;
  const [showAllWeeks, setShowAllWeeks] = useState(false);

  // 기본 선택 = 데이터가 있는 최신 주차 — 빈 W1이 아니라 이번 주 리뷰가 먼저 보인다.
  const weeks = index.data?.weeks ?? [];
  const countOf = (w: number) =>
    (index.data?.event_counts[String(w)] ?? 0) +
    (index.data?.activity_counts[String(w)] ?? 0) +
    (index.data?.request_counts[String(w)] ?? 0);
  const latestWithData = [...weeks].reverse().find((w) => countOf(w) > 0) ?? weeks[0];
  const active = selectedWeek ?? latestWithData;
  const snapshot = useQuery({
    queryKey: ["weekly-snapshot", active],
    queryFn: () => fetchWeeklySnapshot(active!),
    enabled: active !== undefined,
  });

  if (index.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (index.isError)
    return <ErrorState error={index.error} onRetry={() => void index.refetch()} />;

  const recentWeeks = showAllWeeks ? weeks : weeks.slice(-8);

  return (
    <div>
      <h1>{t.title}</h1>

      <ReviewPacksSection />

      <div className="filter-row">
        <span className="filter-label">{t.week_select}</span>
        {recentWeeks.map((w) => (
          <button
            key={w}
            className={`chip chip-btn ${w === active ? "active" : ""}`}
            onClick={() => navigate(`/review/${w}`)}
            title={`${ko.scenario_detail.week_prefix}${w}`}
          >
            {ko.scenario_detail.week_prefix}
            {w}
            {countOf(w) > 0 && <span className="chip-count"> {countOf(w)}</span>}
          </button>
        ))}
        {weeks.length > 8 && (
          <button
            type="button"
            className="link-btn"
            onClick={() => setShowAllWeeks((previous) => !previous)}
          >
            {showAllWeeks ? t.weeks_collapse : t.weeks_show_all}
          </button>
        )}
      </div>

      {/* E3 주간 상황판 — 클릭=해당 섹션 이동 */}
      <div className="stat-strip">
        {(
          [
            ["rv-events", t.events_section, index.data.event_counts[String(active)] ?? 0],
            ["rv-activities", t.activities_section, index.data.activity_counts[String(active)] ?? 0],
            ["rv-requests", t.requests_section, index.data.request_counts[String(active)] ?? 0],
          ] as const
        ).map(([id, sectionLabel, count]) => (
          <button
            key={id}
            type="button"
            className="stat"
            onClick={() =>
              document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
          >
            <b>{count}</b>
            <span>{sectionLabel}</span>
          </button>
        ))}
      </div>

      {snapshot.isPending && <p className="status-msg">{ko.app.loading}</p>}
      {snapshot.data && (
        <div>
          <div className="card" id="rv-events">
            <h2 className="card-title">{t.events_section}</h2>
            {snapshot.data.events.length === 0 && <p className="section-note">{ko.app.empty}</p>}
            {snapshot.data.events.map((event) => (
              <div key={event.id} className="list-item">
                <div className="head">
                  {event.severity && (
                    <span className="badge badge-info" title={event.severity}>
                      {valueLabel("severity", event.severity)}
                    </span>
                  )}
                  <span className="title">{event.title}</span>
                  <span className="badge badge-ok" title={event.status}>
                    {valueLabel("event_status", event.status)}
                  </span>
                  {event.schedule_signal &&
                    ["at_risk", "delayed", "window_closing"].includes(
                      event.schedule_signal,
                    ) && (
                      <span className="badge badge-warn" title={event.schedule_signal}>
                        {valueLabel("schedule_signal", event.schedule_signal)}
                      </span>
                    )}
                </div>
                <p className="desc">{event.description}</p>
              </div>
            ))}
          </div>
          <div className="card" id="rv-activities">
            <h2 className="card-title">{t.activities_section}</h2>
            {snapshot.data.activities.length === 0 && (
              <p className="section-note">{ko.app.empty}</p>
            )}
            {snapshot.data.activities.map((activity) => (
              <div key={activity.id} className="list-item">
                <div className="head">
                  <span className="badge badge-warn" title={activity.role_id}>
                    {valueLabel("role", activity.role_id)}
                  </span>
                  <span className="title">{activity.title}</span>
                </div>
                <p className="desc">{activity.summary}</p>
              </div>
            ))}
          </div>
          <div className="card" id="rv-requests">
            <h2 className="card-title">{t.requests_section}</h2>
            {snapshot.data.requests.length === 0 && <p className="section-note">{ko.app.empty}</p>}
            {snapshot.data.requests.map((request) => (
              <div key={request.id} className="list-item">
                <div className="head">
                  <span className="badge badge-danger" title={request.priority}>
                    {valueLabel("request_priority", request.priority)}
                  </span>
                  <span className="title">{request.title}</span>
                  <span className="badge badge-info" title={request.status}>
                    {valueLabel("request_status", request.status)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ReviewPacksSection() {
  const [selected, setSelected] = useState<string | null>(null);
  const packs = useQuery({ queryKey: ["review-packs"], queryFn: fetchReviewPacks });

  if (!packs.data || packs.data.length === 0) return null;

  return (
    <div className="card">
      <h2 className="card-title">{tp.section}</h2>
      <p className="section-note">{tp.hint}</p>
      <div className="filter-row">
        {packs.data.map((pack) => (
          <button
            key={pack.pack_id}
            className={`chip chip-btn ${selected === pack.pack_id ? "active" : ""}`}
            onClick={() => setSelected(selected === pack.pack_id ? null : pack.pack_id)}
            title={pack.purpose}
          >
            {pack.title} ({pack.scenario_ids.length})
          </button>
        ))}
      </div>
      {selected && <ReviewPackDetail packId={selected} />}
    </div>
  );
}

function ReviewPackDetail({ packId }: { packId: string }) {
  const doc = useQuery({
    queryKey: ["review-pack", packId],
    queryFn: () => fetchReviewPack(packId),
  });
  const [copied, setCopied] = useState<string | null>(null);
  const [uploadReport, setUploadReport] = useState<IngestReport | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const uploadDecisions = useMutation({
    mutationFn: async () => {
      const file = fileRef.current?.files?.[0];
      if (!file) throw new Error(ko.ingest.file_required);
      return uploadIngestFile(file, "decisions");
    },
    onSuccess: (result) => {
      setUploadReport(result);
      void queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });

  if (doc.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (doc.isError || !doc.data)
    return <ErrorState error={doc.error} onRetry={() => void doc.refetch()} />;
  const data = doc.data;
  const r = data.rollup;

  const copyCsv = async () => {
    try {
      await navigator.clipboard.writeText(toDecisionCsv(data));
      setCopied(tp.copied);
    } catch {
      setCopied(tp.copy_failed);
    }
  };
  // E3: 파일로 내려받기 — 클립보드보다 엑셀 왕복에 자연스럽다 (BOM 포함).
  const downloadCsv = () => {
    const blob = new Blob(["﻿" + toDecisionCsv(data) + "\r\n"], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${data.pack_id}_decisions.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <p className="desc">{data.purpose}</p>
      <div className="ladder-headline">
        <span>
          {tp.rollup_risk} <b>{r.risk_items}</b>
        </span>
        <span>
          {tp.rollup_issue} <b>{r.issue_items}</b>
        </span>
        <span>
          {tp.rollup_gap} <b>{r.evidence_gap_items}</b>
        </span>
        <span>
          {tp.posture}: {tp.measured} <b>{r.measured}</b> · {tp.predicted} <b>{r.predicted}</b> ·{" "}
          {tp.absent} <b>{r.absent}</b>
        </span>
      </div>
      <MilestoneGates gates={data.gates ?? []} />
      <div className="chip-row">
        <button type="button" className="link-btn" onClick={downloadCsv}>
          {tp.download_csv}
        </button>
        <button type="button" className="link-btn" onClick={copyCsv}>
          {tp.export_csv}
        </button>
        {copied && <span className="badge badge-ok">{copied}</span>}
        <label className="filter-label" htmlFor="decision-csv">
          {tp.upload_decisions}
        </label>
        <input id="decision-csv" ref={fileRef} type="file" accept=".csv,.xlsx" />
        <button
          type="button"
          className="link-btn"
          disabled={uploadDecisions.isPending}
          onClick={() => uploadDecisions.mutate()}
        >
          {uploadDecisions.isPending ? tp.uploading_decisions : tp.upload_decisions}
        </button>
      </div>
      {uploadDecisions.isError && (
        <p className="status-msg" role="alert">
          {(uploadDecisions.error as Error).message}
        </p>
      )}
      {uploadReport && (
        <p className="desc" aria-live="polite">
          <span className="badge badge-ok">
            {ko.ingest.accepted} {uploadReport.batch.accepted_count}
          </span>{" "}
          <span className="badge badge-info">
            {ko.ingest.updated} {uploadReport.batch.updated_count ?? 0}
          </span>{" "}
          <span className="badge badge-info">
            {ko.ingest.unchanged} {uploadReport.batch.unchanged_count ?? 0}
          </span>{" "}
          <span
            className={`badge ${(uploadReport.batch.rejected_count ?? 0) > 0 ? "badge-danger" : "badge-info"}`}
          >
            {ko.ingest.rejected} {uploadReport.batch.rejected_count}
          </span>
        </p>
      )}
      <PackDecisions projectIds={data.project_ids} />
      <span className="badge badge-warn">{data.provenance_note}</span>

      {data.scenarios.map((scenario) => (
        <div key={scenario.scenario_id} className="list-item">
          <div className="head">
            <span className="title">{scenario.scenario_name}</span>
            {scenario.evidence_posture && (
              <PostureChip
                measured={scenario.evidence_posture.measured}
                predicted={scenario.evidence_posture.predicted}
                absent={scenario.evidence_posture.absent}
                note={scenario.evidence_posture.note_ko}
              />
            )}
          </div>
          {scenario.sections.length === 0 && <p className="desc">{tp.empty_sections}</p>}
          {scenario.sections.map((section) => (
            <details key={section.kind} className="pack-section">
              <summary className="desc">
                <span className="chip">
                  {section.kind_ko} ({section.items.length})
                </span>{" "}
                {section.items[0]?.statement}
                {section.items.length > 1 ? " …" : ""}
              </summary>
              {section.items.map((item, index) => (
                <p key={index} className="desc pack-item" title={item.basis[0]?.ref_id ?? ""}>
                  {item.statement}
                  {item.strength_ko && (
                    <span className="badge badge-info"> {item.strength_ko}</span>
                  )}
                </p>
              ))}
            </details>
          ))}
        </div>
      ))}
    </div>
  );
}

// B3 액션 재진입 계약 — backend `action_items` 매핑과 쌍 (결정 CSV와 동일 왕복 패턴).
export const ACTION_CSV_HEADER = [
  "액션 ID",
  "결정 ID",
  "제목",
  "설명",
  "담당 역할",
  "기한 단계",
  "상태",
  "필요 근거",
] as const;

export function toActionCsv(decisions: { id: string }[]): string {
  const rows = [ACTION_CSV_HEADER.map(csvCell).join(",")];
  for (const decision of decisions) {
    rows.push(
      [`act_${decision.id}_a1`, decision.id, "", "", "", "", "open", ""]
        .map(csvCell)
        .join(","),
    );
  }
  return rows.join("\r\n");
}

/** W1 (설계 22): 워터마크 → 위험 지도 asof 파라미터. 입력이 datetime-local(분
 * 정밀도)이라 내림하면 결정 자신의 반입 배치가 재생에서 빠진다 — 올림으로 포함 보장. */
export function replayAsOfValue(recordedAt: string): string {
  const date = new Date(recordedAt);
  if (date.getSeconds() > 0 || date.getMilliseconds() > 0) {
    date.setMinutes(date.getMinutes() + 1, 0, 0);
  }
  return toDateTimeLocal(date);
}

/** W1: 결정 행의 "당시 상태 보기" — 캡처 이전 결정은 링크를 만들지 않는다 (거짓 리플레이 금지). */
export function DecisionReplayLinks({ watermark }: { watermark: DecisionWatermark }) {
  if (!watermark.recorded_at) {
    return (
      <span className="badge badge-warn" title={watermark.note_ko}>
        {tp.decision_precapture}
      </span>
    );
  }
  const asof = replayAsOfValue(watermark.recorded_at);
  const base = `/?project=${encodeURIComponent(watermark.project_id)}&asof=${encodeURIComponent(asof)}`;
  const chipTitle = watermark.batch_id
    ? `${watermark.note_ko} · ${watermark.batch_id}`
    : watermark.note_ko;
  return (
    <>
      <span className="chip" title={chipTitle}>
        {tp.decision_watermark}: {formatDateTime(watermark.recorded_at)}
      </span>
      <Link className="link-btn" to={base}>
        {tp.decision_replay}
      </Link>
      <Link
        className="link-btn"
        to={`${base}&asofb=${encodeURIComponent(toDateTimeLocal(new Date()))}`}
      >
        {tp.decision_diff}
      </Link>
    </>
  );
}

/** 설계 23: 마일스톤 게이트 판정 — exit 기준의 충족/미충족/판정 불가 + 근거.
 * 미충족은 경고색이되 차단이 아니다 — 판정과 근거를 보여줄 뿐이다. */
export function MilestoneGates({ gates }: { gates: MilestoneGateReview[] }) {
  if (gates.length === 0) return null;
  return (
    <div className="card">
      <h3 className="card-title">{tp.gates_section}</h3>
      <p className="section-note">{tp.gates_hint}</p>
      {gates.map((gate) => (
        <div key={gate.milestone_id} className="list-item">
          <div className="head">
            <span className="title" title={gate.milestone_id}>
              {gate.milestone_title}
            </span>
            {gate.week != null && <span className="chip">W{gate.week}</span>}
            <span className="badge badge-ok">
              {tp.gate_count_met} {gate.met}
            </span>
            {gate.not_met > 0 && (
              <span className="badge badge-danger">
                {tp.gate_count_not_met} {gate.not_met}
              </span>
            )}
            {gate.not_evaluable > 0 && (
              <span className="badge badge-warn">
                {tp.gate_count_not_evaluable} {gate.not_evaluable}
              </span>
            )}
          </div>
          {gate.criteria.map((criterion) => (
            <div key={criterion.criterion_id} className="pack-item">
              <p className="desc">
                <span
                  className={`badge ${
                    criterion.verdict === "met"
                      ? "badge-ok"
                      : criterion.verdict === "not_met"
                        ? "badge-danger"
                        : "badge-warn"
                  }`}
                  title={criterion.kind_ko}
                >
                  {criterion.verdict_ko}
                </span>{" "}
                {criterion.description} — {criterion.note_ko}
              </p>
              {(criterion.basis ?? []).map((basis) => (
                <p key={basis.ref_id} className="desc pack-item" title={basis.ref_id}>
                  · {basis.note_ko}
                </p>
              ))}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function PackDecisions({ projectIds }: { projectIds: string[] }) {
  const valueLabel = useValueLabels();
  const queryClient = useQueryClient();
  const decisions = useQuery({ queryKey: ["decisions"], queryFn: () => fetchDecisions() });
  const actions = useQuery({ queryKey: ["action-items"], queryFn: fetchActionItems });
  const watermarks = useQuery({
    queryKey: ["decision-watermarks"],
    queryFn: () => fetchDecisionWatermarks(),
  });
  const [actionReport, setActionReport] = useState<IngestReport | null>(null);
  const actionFileRef = useRef<HTMLInputElement>(null);
  const uploadActions = useMutation({
    mutationFn: async () => {
      const file = actionFileRef.current?.files?.[0];
      if (!file) throw new Error(ko.ingest.file_required);
      return uploadIngestFile(file, "action_items");
    },
    onSuccess: (result) => {
      setActionReport(result);
      void queryClient.invalidateQueries({ queryKey: ["action-items"] });
    },
  });

  const related = (decisions.data ?? []).filter((decision) =>
    projectIds.includes(decision.project_id),
  );
  const watermarkById = new Map(
    (watermarks.data ?? []).map((mark) => [mark.decision_id, mark]),
  );
  const actionsByDecision = new Map<string, typeof actions.data>();
  for (const action of actions.data ?? []) {
    const list = actionsByDecision.get(action.source_decision_id) ?? [];
    list.push(action);
    actionsByDecision.set(action.source_decision_id, list);
  }
  const downloadActionCsv = () => {
    const blob = new Blob(["﻿" + toActionCsv(related) + "\r\n"], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "action_items_template.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <h3 className="card-title">{tp.decisions_section}</h3>
      {related.length === 0 && <p className="section-note">{tp.no_decisions}</p>}
      {related.map((decision) => (
        <div key={decision.id} className="list-item">
          <div className="head">
            <span className="badge badge-info" title={decision.id}>
              {tp.decision_selected}
            </span>
            <span className="title">{decision.selected_option}</span>
            {watermarkById.has(decision.id) && (
              <DecisionReplayLinks watermark={watermarkById.get(decision.id)!} />
            )}
          </div>
          {(decision.supporting_basis ?? []).map((basis, index) => (
            <p key={index} className="desc" title={basis.ref_id}>
              {tp.decision_basis}: {basis.statement}
            </p>
          ))}
          {/* B3: 결정에서 파생된 액션 — 상태·담당·기한 추적 */}
          {(actionsByDecision.get(decision.id) ?? []).map((action) => (
            <p key={action.id} className="desc pack-item" title={action.id}>
              <span
                className={`badge ${
                  action.status === "done"
                    ? "badge-ok"
                    : action.status === "blocked"
                      ? "badge-danger"
                      : "badge-warn"
                }`}
              >
                {valueLabel("action_status", action.status)}
              </span>{" "}
              {action.title} — {valueLabel("role", action.owner_role)} ·{" "}
              {valueLabel("due_phase", action.due_phase)}
            </p>
          ))}
        </div>
      ))}
      {related.length > 0 && (
        <div className="chip-row">
          <button type="button" className="link-btn" onClick={downloadActionCsv}>
            {tp.download_action_csv}
          </button>
          <label className="filter-label" htmlFor="action-csv">
            {tp.upload_actions}
          </label>
          <input id="action-csv" ref={actionFileRef} type="file" accept=".csv,.xlsx" />
          <button
            type="button"
            className="link-btn"
            disabled={uploadActions.isPending}
            onClick={() => uploadActions.mutate()}
          >
            {uploadActions.isPending ? tp.uploading_actions : tp.upload_actions}
          </button>
          {uploadActions.isError && (
            <span className="badge badge-danger" role="alert">
              {(uploadActions.error as Error).message}
            </span>
          )}
          {actionReport && (
            <span className="badge badge-ok" aria-live="polite">
              {ko.ingest.accepted} {actionReport.batch.accepted_count} · {ko.ingest.updated}{" "}
              {actionReport.batch.updated_count ?? 0} · {ko.ingest.rejected}{" "}
              {actionReport.batch.rejected_count}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
