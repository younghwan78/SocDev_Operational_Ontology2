import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchEvidence, fetchIngestBatches, fetchProjects } from "../api/client";
import { SourceBadge } from "../components/SourceBadge";
import { ko } from "../i18n/ko";

const t = ko.evidence;

const AVAILABILITY_BADGE: Record<string, string> = {
  available: "badge-ok",
  partial: "badge-warn",
  missing: "badge-danger",
  planned: "badge-info",
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
  const batches = useQuery({ queryKey: ["ingest-batches"], queryFn: fetchIngestBatches });

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
          >
            {option}
          </button>
        ))}
      </div>

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
              <span className={`badge ${AVAILABILITY_BADGE[entry.availability] ?? "badge-info"}`}>
                {entry.availability}
              </span>
              <span className="title">{entry.title}</span>
              {entry.is_measurement && <span className="badge badge-ok">{t.measurement}</span>}
              {entry.is_prediction && <span className="badge badge-warn">{t.prediction}</span>}
              <span className="chip">{entry.project_id}</span>
            </div>
            <p className="desc">
              {t.limitation}: {entry.known_limitation} · {t.source_system}: {entry.source_system}
            </p>
            <p className="desc">
              <Link to={`/scenarios/${entry.scenario_id}/overview`} className="chip-link">
                {t.scenario_link}: {entry.scenario_id}
              </Link>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
