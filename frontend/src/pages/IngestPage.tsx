/**
 * 반입 센터 — CSV/XLSX 업로드 → 기존 ingest 배치 API 호출 (신규 쓰기 API 아님).
 * 거부 행의 한국어 사유·rollback·템플릿 다운로드를 한 화면에서 제공한다.
 * 온톨로지 데이터는 이 경로(반입 배치)로만 진입한다 — CLAUDE.md §6.3.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  fetchIngestBatches,
  fetchIngestMappings,
  fetchIngestQuarantine,
  getActor,
  rollbackIngestBatch,
  setActor,
  uploadIngestFile,
  type IngestColumnSpec,
  type IngestMappingInfo,
  type IngestQualityReport,
  type IngestReport,
  type QuarantineEntry,
} from "../api/client";
import { ErrorState } from "../components/ErrorState";
import { formatDateTime } from "../lib/format";
import { ko } from "../i18n/ko";

const t = ko.ingest;

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

/** 보류 행 수정용 CSV — 원본 열 값 그대로 + 사유 열. 고쳐서 그대로 재반입하면
 * 같은 id의 보류 행이 자동 해소된다 (사유 열은 반입 시 무시됨). */
export function downloadQuarantineCsv(
  mapping: IngestMappingInfo,
  entries: QuarantineEntry[],
) {
  const columns = [...mapping.columns];
  const lines = [
    [...columns, "거부 사유"].map(csvCell).join(","),
    ...entries.map((entry) =>
      [...columns.map((column) => entry.row_data[column] ?? ""), entry.reason]
        .map(csvCell)
        .join(","),
    ),
  ];
  const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${mapping.name}_quarantine.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** 거부 행 사유 CSV — 큐레이션 루프 1단계: 원본에서 해당 행을 고쳐 재반입한다. */
export function downloadRejectedCsv(report: IngestReport) {
  const lines = [
    [t.row_suffix, "사유"].map(csvCell).join(","),
    ...(report.rejected_rows ?? []).map((row) =>
      [String(row.row_number), row.reason].map(csvCell).join(","),
    ),
  ];
  const blob = new Blob(["﻿" + lines.join("\r\n") + "\r\n"], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${report.batch.filename}_rejected.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function QualitySection({ quality }: { quality: IngestQualityReport }) {
  return (
    <div>
      <p className="subhead">{t.quality_title}</p>
      {quality.linkage_total > 0 && (
        <p className="desc">
          {t.linkage}:{" "}
          <b>
            {quality.linkage_connected}/{quality.linkage_total}
          </b>
          {quality.linkage_connected < quality.linkage_total && <> — {t.linkage_note}</>}
        </p>
      )}
      {(quality.unlabeled_values ?? []).map((line) => (
        <p key={line} className="desc">
          <span className="badge badge-warn">{t.unlabeled}</span> {line}
        </p>
      ))}
      {(quality.missing_ref_warnings ?? []).map((line) => (
        <p key={line} className="desc">
          <span className="badge badge-warn">{t.missing_ref}</span> {line}
        </p>
      ))}
    </div>
  );
}

export function downloadTemplateCsv(mapping: IngestMappingInfo) {
  const header = mapping.columns.map(csvCell).join(",");
  const blob = new Blob(["﻿" + header + "\r\n"], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${mapping.name}_template.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

const SPEC_KIND_LABEL: Record<string, string> = {
  text: t.spec_kind_text,
  int: t.spec_kind_int,
  bool: t.spec_kind_bool,
  list: t.spec_kind_list,
};

/** R2 — 열 스펙 한 행: 필수/형식/허용값·참조를 사람이 채울 수 있는 언어로. */
function SpecRow({ spec }: { spec: IngestColumnSpec }) {
  const kind =
    spec.kind === "list" && spec.separator
      ? `${t.spec_kind_list} (${t.spec_list_sep} '${spec.separator}')`
      : (SPEC_KIND_LABEL[spec.kind] ?? spec.kind);
  const allowed = (spec.allowed_values ?? []).join(", ");
  const parts = [
    allowed,
    spec.ref_collection ? `${t.spec_ref_prefix} ${spec.ref_collection}` : "",
  ].filter(Boolean);
  return (
    <tr>
      <th title={spec.field_path}>{spec.column}</th>
      <td>
        {spec.required ? (
          <span className="badge badge-danger">{t.spec_required_yes}</span>
        ) : (
          t.spec_required_no
        )}
      </td>
      <td>{kind}</td>
      <td>{parts.length > 0 ? parts.join(" · ") : t.spec_free_text}</td>
    </tr>
  );
}

export function IngestPage() {
  const queryClient = useQueryClient();
  const mappings = useQuery({ queryKey: ["ingest-mappings"], queryFn: fetchIngestMappings });
  const batches = useQuery({ queryKey: ["ingest-batches"], queryFn: fetchIngestBatches });
  const quarantine = useQuery({
    queryKey: ["ingest-quarantine"],
    queryFn: fetchIngestQuarantine,
  });
  const [mappingName, setMappingName] = useState<string>("");
  const [report, setReport] = useState<IngestReport | null>(null);
  // R4: 행위자 이름 — localStorage 유지, 모든 요청 헤더에 자동 첨부.
  const [actorDraft, setActorDraft] = useState(() => getActor() ?? "");
  const fileRef = useRef<HTMLInputElement>(null);

  const selected =
    mappings.data?.find((m) => m.name === mappingName) ?? mappings.data?.[0] ?? null;

  const upload = useMutation({
    // R3: dryRun=true면 검사만 실행 — 서버는 리포트만 계산하고 아무것도 쓰지 않는다.
    mutationFn: async (dryRun: boolean) => {
      const file = fileRef.current?.files?.[0];
      if (!file || !selected) throw new Error(t.file_required);
      return uploadIngestFile(file, selected.name, { dryRun });
    },
    onSuccess: (result) => {
      setReport(result);
      if (!result.dry_run) {
        void queryClient.invalidateQueries({ queryKey: ["ingest-batches"] });
        void queryClient.invalidateQueries({ queryKey: ["ingest-quarantine"] });
      }
    },
  });

  const rollback = useMutation({
    mutationFn: rollbackIngestBatch,
    onSuccess: () => {
      setReport(null);
      void queryClient.invalidateQueries({ queryKey: ["ingest-batches"] });
      void queryClient.invalidateQueries({ queryKey: ["ingest-quarantine"] });
    },
  });

  if (mappings.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (mappings.isError)
    return <ErrorState error={mappings.error} onRetry={() => void mappings.refetch()} />;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      <div className="card">
        <h2 className="card-title">{t.upload_section}</h2>
        <p className="section-note">{t.flow_note}</p>
        <div className="filter-row">
          <label className="filter-label" htmlFor="ingest-mapping">
            {t.mapping_label}
          </label>
          <select
            id="ingest-mapping"
            value={selected?.name ?? ""}
            onChange={(event) => setMappingName(event.target.value)}
          >
            {(mappings.data ?? []).map((mapping) => (
              <option key={mapping.name} value={mapping.name}>
                {mapping.label_ko}
              </option>
            ))}
          </select>
          <label className="filter-label" htmlFor="ingest-file">
            {t.file_label}
          </label>
          <input id="ingest-file" ref={fileRef} type="file" accept=".csv,.xlsx" />
          <label className="filter-label" htmlFor="ingest-actor">
            {t.actor_label}
          </label>
          <input
            id="ingest-actor"
            type="text"
            className="search-input"
            value={actorDraft}
            placeholder={t.actor_placeholder}
            onChange={(event) => {
              setActorDraft(event.target.value);
              setActor(event.target.value);
            }}
          />
          {/* R3: 검사만 실행 → 결과 확인 → 반입 실행 2단계 */}
          <button
            type="button"
            className="chip chip-btn"
            disabled={upload.isPending}
            onClick={() => upload.mutate(true)}
          >
            {upload.isPending ? t.dry_checking : t.run_dry}
          </button>
          <button
            type="button"
            className="primary-btn"
            disabled={upload.isPending}
            onClick={() => upload.mutate(false)}
          >
            {upload.isPending ? t.uploading : t.run_upload}
          </button>
          {selected && (
            <button
              type="button"
              className="link-btn"
              onClick={() => downloadTemplateCsv(selected)}
            >
              {t.download_template}
            </button>
          )}
        </div>
        {selected && (
          <p className="desc">
            {t.required_columns}: {selected.required_columns.join(", ")}
          </p>
        )}
        {/* R2: 열 스펙 — 허용값·형식을 화면에서 보고 채우게 한다 (거부-루프 예방) */}
        {selected && (selected.column_specs ?? []).length > 0 && (
          <details>
            <summary className="card-subtitle">{t.spec_title}</summary>
            <p className="section-note">{t.spec_note}</p>
            <div className="heatmap-scroll">
              <table className="heatmap">
                <thead>
                  <tr>
                    <th>{t.spec_col_column}</th>
                    <th>{t.spec_col_required}</th>
                    <th>{t.spec_col_kind}</th>
                    <th>{t.spec_col_allowed}</th>
                  </tr>
                </thead>
                <tbody>
                  {(selected.column_specs ?? []).map((spec) => (
                    <SpecRow key={spec.column} spec={spec} />
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        {upload.isError && (
          <p className="status-msg" role="alert">
            {(upload.error as Error).message}
          </p>
        )}
        {report && (
          <div aria-live="polite">
            {report.dry_run && (
              <p className="section-note rca-banner">
                🔍 {t.dry_run_badge} — {t.dry_run_hint}
              </p>
            )}
            <p className="desc">
              <span className="badge badge-ok">
                {t.accepted} {report.batch.accepted_count}
              </span>{" "}
              <span className="badge badge-info">
                {t.updated} {report.batch.updated_count ?? 0}
              </span>{" "}
              <span className="badge badge-info">
                {t.unchanged} {report.batch.unchanged_count ?? 0}
              </span>{" "}
              <span
                className={`badge ${report.batch.rejected_count > 0 ? "badge-danger" : "badge-info"}`}
              >
                {t.rejected} {report.batch.rejected_count}
              </span>{" "}
              <span className="chip" title={report.batch.id}>
                {report.batch.filename}
              </span>
            </p>
            {report.quality && <QualitySection quality={report.quality} />}
            {(report.rejected_rows ?? []).length > 0 && (
              <button
                type="button"
                className="link-btn"
                onClick={() => downloadRejectedCsv(report)}
              >
                {t.download_rejected}
              </button>
            )}
            {(report.rejected_rows ?? []).map((row) => (
              <p key={row.row_number} className="desc rca-alert">
                {row.row_number}
                {t.row_suffix}: {row.reason}
              </p>
            ))}
          </div>
        )}
      </div>

      {/* J1 2단계: 큐레이션 대기열 — 거부 행 보류 풀. 수정용 CSV로 내려받아 고쳐
          재반입하면 같은 id의 보류 행이 자동 해소된다. */}
      {(quarantine.data ?? []).length > 0 && (
        <div className="card">
          <div className="head">
            <h2 className="card-title">
              {t.quarantine_title} ({(quarantine.data ?? []).length})
            </h2>
            <span className="badge badge-warn">{t.quarantine_note}</span>
          </div>
          {(mappings.data ?? [])
            .map((mapping) => ({
              mapping,
              entries: (quarantine.data ?? []).filter(
                (entry) => entry.mapping_name === mapping.name,
              ),
            }))
            .filter(({ entries }) => entries.length > 0)
            .map(({ mapping, entries }) => (
              <div key={mapping.name} className="list-item">
                <div className="head">
                  <span className="title">{mapping.label_ko}</span>
                  <span className="chip-count">{entries.length}</span>
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => downloadQuarantineCsv(mapping, entries)}
                  >
                    {t.quarantine_download}
                  </button>
                </div>
                {entries.slice(0, 5).map((entry) => (
                  <p key={entry.id} className="desc" title={entry.batch_id}>
                    <span className="badge badge-warn">
                      {entry.row_number}
                      {t.row_suffix}
                    </span>{" "}
                    {entry.object_id ? `${entry.object_id} — ` : ""}
                    {entry.reason}
                  </p>
                ))}
                {entries.length > 5 && (
                  <p className="section-note">
                    +{entries.length - 5} {t.quarantine_more}
                  </p>
                )}
              </div>
            ))}
        </div>
      )}

      <div className="card">
        <h2 className="card-title">{t.history}</h2>
        {(batches.data ?? []).length === 0 && <p className="section-note">{ko.app.empty}</p>}
        {(batches.data ?? []).map((batch) => {
          const mappingLabel =
            mappings.data?.find((m) => m.name === batch.mapping_name)?.label_ko ??
            batch.mapping_name;
          return (
            <div key={batch.id} className="list-item">
              <div className="head">
                <span
                  className={`badge ${batch.status === "completed" ? "badge-ok" : "badge-warn"}`}
                >
                  {batch.status === "completed" ? t.status_completed : t.status_rolled_back}
                </span>
                <span className="title" title={batch.id}>
                  {batch.filename}
                </span>
                <span className="chip" title={batch.mapping_name}>
                  {mappingLabel}
                </span>
                {batch.actor && (
                  <span className="chip" title={t.actor_label}>
                    {batch.actor}
                  </span>
                )}
                <span className="desc">
                  {t.accepted} {batch.accepted_count} · {t.updated} {batch.updated_count ?? 0}{" "}
                  · {t.unchanged} {batch.unchanged_count ?? 0} · {t.rejected}{" "}
                  {batch.rejected_count}
                </span>
                <span className="desc" title={batch.created_at}>
                  {formatDateTime(batch.created_at)}
                </span>
                {batch.status === "completed" && (
                  <button
                    type="button"
                    className="link-btn"
                    disabled={rollback.isPending}
                    onClick={() => rollback.mutate(batch.id)}
                  >
                    {t.rollback}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
