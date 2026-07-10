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
  rollbackIngestBatch,
  uploadIngestFile,
  type IngestMappingInfo,
  type IngestReport,
} from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.ingest;

function csvCell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
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

export function IngestPage() {
  const queryClient = useQueryClient();
  const mappings = useQuery({ queryKey: ["ingest-mappings"], queryFn: fetchIngestMappings });
  const batches = useQuery({ queryKey: ["ingest-batches"], queryFn: fetchIngestBatches });
  const [mappingName, setMappingName] = useState<string>("");
  const [report, setReport] = useState<IngestReport | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const selected =
    mappings.data?.find((m) => m.name === mappingName) ?? mappings.data?.[0] ?? null;

  const upload = useMutation({
    mutationFn: async () => {
      const file = fileRef.current?.files?.[0];
      if (!file || !selected) throw new Error(t.file_required);
      return uploadIngestFile(file, selected.name);
    },
    onSuccess: (result) => {
      setReport(result);
      void queryClient.invalidateQueries({ queryKey: ["ingest-batches"] });
    },
  });

  const rollback = useMutation({
    mutationFn: rollbackIngestBatch,
    onSuccess: () => {
      setReport(null);
      void queryClient.invalidateQueries({ queryKey: ["ingest-batches"] });
    },
  });

  if (mappings.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (mappings.isError) return <p className="status-msg">{ko.app.error}</p>;

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.subtitle}</p>

      <div className="card">
        <h2 className="card-title">{t.upload_section}</h2>
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
          <button
            type="button"
            className="primary-btn"
            disabled={upload.isPending}
            onClick={() => upload.mutate()}
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
        {upload.isError && (
          <p className="status-msg" role="alert">
            {(upload.error as Error).message}
          </p>
        )}
        {report && (
          <div aria-live="polite">
            <p className="desc">
              <span className="badge badge-ok">
                {t.accepted} {report.batch.accepted_count}
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
            {(report.rejected_rows ?? []).map((row) => (
              <p key={row.row_number} className="desc rca-alert">
                {row.row_number}
                {t.row_suffix}: {row.reason}
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t.history}</h2>
        {(batches.data ?? []).length === 0 && <p className="section-note">{ko.app.empty}</p>}
        {(batches.data ?? []).map((batch) => (
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
              <span className="chip">{batch.mapping_name}</span>
              <span className="desc">
                {t.accepted} {batch.accepted_count} · {t.rejected} {batch.rejected_count}
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
        ))}
      </div>
    </div>
  );
}
