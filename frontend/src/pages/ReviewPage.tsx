import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  fetchDecisions,
  fetchReviewPack,
  fetchReviewPacks,
  fetchWeeklyIndex,
  fetchWeeklySnapshot,
  uploadIngestFile,
  type IngestReport,
  type ReviewPackDocument,
} from "../api/client";
import { useRef } from "react";
import { PostureChip } from "../components/PostureChip";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
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
  const label = useLabels();
  const valueLabel = useValueLabels();

  const index = useQuery({ queryKey: ["weekly-index"], queryFn: fetchWeeklyIndex });
  const selectedWeek = week ? Number(week) : undefined;
  const snapshot = useQuery({
    queryKey: ["weekly-snapshot", selectedWeek],
    queryFn: () => fetchWeeklySnapshot(selectedWeek!),
    enabled: selectedWeek !== undefined,
  });

  if (index.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (index.isError) return <p className="status-msg">{ko.app.error}</p>;

  const weeks = index.data.weeks;
  const active = selectedWeek ?? weeks[0];

  return (
    <div>
      <h1>{t.title}</h1>

      <ReviewPacksSection />

      <div className="filter-row">
        <span className="filter-label">{t.week_select}</span>
        {weeks.map((w) => (
          <button
            key={w}
            className={`chip chip-btn ${w === active ? "active" : ""}`}
            onClick={() => navigate(`/review/${w}`)}
          >
            {ko.scenario_detail.week_prefix}
            {w}
          </button>
        ))}
      </div>

      {selectedWeek === undefined && weeks.length > 0 && (
        <p className="section-note">
          {t.counts
            .replace("{e}", String(index.data.event_counts[String(active)] ?? 0))
            .replace("{a}", String(index.data.activity_counts[String(active)] ?? 0))
            .replace("{r}", String(index.data.request_counts[String(active)] ?? 0))}
        </p>
      )}

      {snapshot.isPending && selectedWeek !== undefined && (
        <p className="status-msg">{ko.app.loading}</p>
      )}
      {snapshot.data && (
        <div>
          <div className="card">
            <h2 className="card-title">{t.events_section}</h2>
            {snapshot.data.events.length === 0 && <p className="section-note">{ko.app.empty}</p>}
            {snapshot.data.events.map((event) => (
              <div key={event.id} className="list-item">
                <div className="head">
                  <span className="badge badge-info" title={event.severity}>
                    {valueLabel("severity", event.severity)}
                  </span>
                  <span className="title">{event.title}</span>
                  <span className="badge badge-ok" title={event.status}>
                    {valueLabel("event_status", event.status)}
                  </span>
                </div>
                <p className="desc">{event.description}</p>
              </div>
            ))}
          </div>
          <div className="card">
            <h2 className="card-title">{t.activities_section}</h2>
            {snapshot.data.activities.length === 0 && (
              <p className="section-note">{ko.app.empty}</p>
            )}
            {snapshot.data.activities.map((activity) => (
              <div key={activity.id} className="list-item">
                <div className="head">
                  <span className="badge badge-warn" title={activity.role_id}>
                    {label(activity.role_id)}
                  </span>
                  <span className="title">{activity.title}</span>
                </div>
                <p className="desc">{activity.summary}</p>
              </div>
            ))}
          </div>
          <div className="card">
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
  if (doc.isError || !doc.data) return <p className="status-msg">{ko.app.error}</p>;
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
      <div className="chip-row">
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
            <p key={section.kind} className="desc">
              <span className="chip">
                {section.kind_ko} ({section.items.length})
              </span>{" "}
              {section.items[0]?.statement}
              {section.items.length > 1 ? " …" : ""}
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}

function PackDecisions({ projectIds }: { projectIds: string[] }) {
  const decisions = useQuery({ queryKey: ["decisions"], queryFn: () => fetchDecisions() });
  const related = (decisions.data ?? []).filter((decision) =>
    projectIds.includes(decision.project_id),
  );
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
          </div>
          {(decision.supporting_basis ?? []).map((basis, index) => (
            <p key={index} className="desc" title={basis.ref_id}>
              {tp.decision_basis}: {basis.statement}
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}
