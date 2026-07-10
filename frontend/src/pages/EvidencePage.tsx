import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchEvidence,
  fetchEvidenceLadder,
  fetchIngestBatches,
  fetchProjects,
  type EvidenceLadder,
  type EvidenceStrengthItem,
} from "../api/client";
import { SourceBadge } from "../components/SourceBadge";
import { useLabels } from "../hooks/useLabels";
import { useValueLabels } from "../hooks/useValueLabels";
import { ko } from "../i18n/ko";

const t = ko.evidence;
const tl = ko.evidence_ladder;

const AVAILABILITY_BADGE: Record<string, string> = {
  available: "badge-ok",
  partial: "badge-warn",
  missing: "badge-danger",
  planned: "badge-info",
};

const TIER_BADGE: Record<string, string> = {
  measured_direct: "badge-ok",
  measured_analogous: "badge-ok",
  emulated: "badge-info",
  predicted: "badge-warn",
  absent: "badge-danger",
};

const AVAILABILITY_OPTIONS = ["available", "partial", "missing", "planned"];

export function EvidencePage() {
  const [projectFilter, setProjectFilter] = useState<string | undefined>();
  const [availabilityFilter, setAvailabilityFilter] = useState<string | undefined>();

  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const evidence = useQuery({
    queryKey: ["evidence", projectFilter, availabilityFilter],
    queryFn: () => fetchEvidence({ projectId: projectFilter, availability: availabilityFilter }),
  });
  const ladder = useQuery({
    queryKey: ["evidence-ladder", projectFilter],
    queryFn: () => fetchEvidenceLadder({ projectId: projectFilter }),
  });
  const batches = useQuery({ queryKey: ["ingest-batches"], queryFn: fetchIngestBatches });
  const label = useLabels();
  const valueLabel = useValueLabels();

  const strengthById = new Map<string, EvidenceStrengthItem>(
    (ladder.data?.entries ?? []).map((item) => [item.evidence_id, item]),
  );

  if (evidence.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (evidence.isError) return <p className="status-msg">{ko.app.error}</p>;

  return (
    <div>
      <h1>{t.title}</h1>
      <div className="filter-row">
        <span className="filter-label">{ko.scenario_list.filter_label}</span>
        <button
          className={`chip chip-btn ${projectFilter === undefined ? "active" : ""}`}
          onClick={() => setProjectFilter(undefined)}
        >
          {t.filter_all}
        </button>
        {(projects.data ?? []).map((project) => (
          <button
            key={project.id}
            className={`chip chip-btn ${projectFilter === project.id ? "active" : ""}`}
            onClick={() => setProjectFilter(project.id)}
          >
            {project.name}
          </button>
        ))}
        <span className="filter-label">{t.filter_availability}</span>
        <button
          className={`chip chip-btn ${availabilityFilter === undefined ? "active" : ""}`}
          onClick={() => setAvailabilityFilter(undefined)}
        >
          {t.filter_all}
        </button>
        {AVAILABILITY_OPTIONS.map((option) => (
          <button
            key={option}
            className={`chip chip-btn ${availabilityFilter === option ? "active" : ""}`}
            onClick={() => setAvailabilityFilter(option)}
            title={option}
          >
            {valueLabel("availability", option)}
          </button>
        ))}
      </div>

      {ladder.data && <LadderPanel ladder={ladder.data} />}

      {(batches.data ?? []).length > 0 && (
        <div className="card">
          <h2 className="card-title">{ko.ingest.history}</h2>
          {(batches.data ?? []).map((batch) => (
            <div key={batch.id} className="list-item">
              <div className="head">
                <span
                  className={`badge ${batch.status === "completed" ? "badge-ok" : "badge-warn"}`}
                >
                  {batch.status === "completed"
                    ? ko.ingest.status_completed
                    : ko.ingest.status_rolled_back}
                </span>
                <span className="title">{batch.filename}</span>
                <span className="chip">{batch.mapping_name}</span>
              </div>
              <p className="desc">
                {ko.ingest.accepted} {batch.accepted_count} · {ko.ingest.rejected}{" "}
                {batch.rejected_count} · {batch.created_at}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        {evidence.data.length === 0 && <p className="status-msg">{ko.app.empty}</p>}
        {evidence.data.map((entry) => (
          <div key={entry.id} className="list-item">
            <div className="head">
              <SourceBadge origin={entry.source?.origin} />
              {strengthById.get(entry.id) && (
                <span
                  className={`badge ${TIER_BADGE[strengthById.get(entry.id)!.tier] ?? "badge-info"}`}
                  title={strengthById.get(entry.id)!.basis[0]?.description ?? ""}
                >
                  {tl.strength}: {strengthById.get(entry.id)!.tier_ko}
                </span>
              )}
              <span
                className={`badge ${AVAILABILITY_BADGE[entry.availability] ?? "badge-info"}`}
                title={entry.availability}
              >
                {valueLabel("availability", entry.availability)}
              </span>
              <span className="title">{entry.title}</span>
              {entry.is_measurement && <span className="badge badge-ok">{t.measurement}</span>}
              {entry.is_prediction && <span className="badge badge-warn">{t.prediction}</span>}
              <span className="chip" title={entry.project_id}>
                {label(entry.project_id)}
              </span>
            </div>
            <p className="desc">
              {t.limitation}: {entry.known_limitation} · {t.source_system}: {entry.source_system}
            </p>
            <p className="desc">
              <Link
                to={`/scenarios/${entry.scenario_id}/overview`}
                className="chip-link"
                title={entry.scenario_id}
              >
                {t.scenario_link}: {label(entry.scenario_id)}
              </Link>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function LadderPanel({ ladder }: { ladder: EvidenceLadder }) {
  const total = ladder.totals.total;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);
  const shown = ladder.distribution.filter((b) => b.count > 0);
  return (
    <div className="card">
      <h2 className="card-title">{tl.title}</h2>
      <p className="section-note">{tl.subtitle}</p>
      <div className="ladder-headline">
        <span>
          {tl.headline_measured} <b>{ladder.totals.measured}</b> {tl.of_total} {total}
        </span>
        <span>
          {tl.headline_predicted} <b>{ladder.totals.predicted}</b>
        </span>
        <span>
          {tl.headline_absent} <b>{ladder.totals.absent}</b>
        </span>
      </div>
      <div
        className="ladder-track"
        role="img"
        aria-label={shown.map((b) => `${b.tier_ko} ${b.count}`).join(", ")}
      >
        {shown.map((b) => (
          <span
            key={b.tier}
            className={`ladder-seg tier-${b.tier}`}
            style={{ width: `${pct(b.count)}%` }}
            title={`${b.tier_ko} ${b.count}`}
          />
        ))}
      </div>
      <div className="origin-legend">
        {ladder.distribution.map((b) => (
          <span key={b.tier} className="origin-key">
            <span className={`origin-dot tier-${b.tier}`} />
            {b.tier_ko} {b.count}
          </span>
        ))}
      </div>
    </div>
  );
}
