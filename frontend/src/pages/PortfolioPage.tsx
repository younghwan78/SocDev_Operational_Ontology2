import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchPortfolio, type AttentionItem } from "../api/client";
import { ko } from "../i18n/ko";

const t = ko.portfolio;

const LANE_BADGE: Record<string, string> = {
  evidence_blocked: "badge-danger",
  definition_needed: "badge-warn",
  confidence_blocked: "badge-danger",
  propagation_review: "badge-info",
  de_risk_candidate: "badge-warn",
  management_attention: "badge-danger",
};

export function PortfolioPage() {
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: fetchPortfolio });

  if (portfolio.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (portfolio.isError) return <p className="status-msg">{ko.app.error}</p>;

  const { projects, attention, matrix } = portfolio.data;
  const lanes = [...new Set(attention.map((item) => item.lane))];

  return (
    <div>
      <h1>{t.title}</h1>
      <p className="section-note">{t.note}</p>

      <div className="scenario-grid">
        {projects.map((summary) => (
          <div key={summary.project.id} className="card">
            <div className="name">
              {summary.project.name}{" "}
              <span className="badge badge-info">{summary.project.phase}</span>
            </div>
            <dl className="kv">
              <dt>{t.milestones}</dt>
              <dd>{summary.milestone_count}</dd>
              <dt>{t.open_requests}</dt>
              <dd>{summary.open_request_count}</dd>
              <dt>{t.events}</dt>
              <dd>{summary.event_count}</dd>
            </dl>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="card-title">{t.attention_section}</h2>
        {lanes.map((lane) => {
          const items = attention.filter((item) => item.lane === lane);
          return (
            <div key={lane} className="timeline-week">
              <div className="week-label">
                {items[0].lane_ko} ({items.length})
              </div>
              {items.map((item, index) => (
                <AttentionRow key={`${item.ref_id}-${index}`} item={item} />
              ))}
            </div>
          );
        })}
      </div>

      <div className="card">
        <h2 className="card-title">{t.matrix_section}</h2>
        <div className="scenario-grid">
          {matrix.map((cell) => (
            <Link
              key={cell.scenario_id}
              to={`/scenarios/${cell.scenario_id}/overview`}
              className="card scenario-card"
            >
              <div className="name">{cell.scenario_name}</div>
              <div className="chip-row">
                {cell.project_ids.map((projectId) => (
                  <span key={projectId} className="chip">
                    {projectId}
                  </span>
                ))}
              </div>
              <p className="desc">
                {t.matrix_requests} {cell.request_count} · {t.matrix_events} {cell.event_count}{" "}
                ·{" "}
                <span className={cell.gap_count > 0 ? "badge badge-danger" : "badge badge-ok"}>
                  {t.matrix_gaps} {cell.gap_count}
                </span>
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function AttentionRow({ item }: { item: AttentionItem }) {
  return (
    <div className="list-item">
      <div className="head">
        <span className={`badge ${LANE_BADGE[item.lane] ?? "badge-info"}`}>{item.lane_ko}</span>
        <span className="title">{item.title}</span>
        {(item.project_ids ?? []).map((projectId) => (
          <span key={projectId} className="chip">
            {projectId}
          </span>
        ))}
      </div>
      <p className="desc">{item.description}</p>
      {(item.scenario_ids ?? []).length > 0 && (
        <p className="desc">
          {ko.portfolio.related_scenarios}:{" "}
          {(item.scenario_ids ?? []).map((scenarioId) => (
            <Link key={scenarioId} to={`/scenarios/${scenarioId}/overview`} className="chip-link">
              {scenarioId}
            </Link>
          ))}
        </p>
      )}
      {(item.suggested_review_roles ?? []).length > 0 && (
        <p className="desc">
          {ko.portfolio.suggested_roles}: {(item.suggested_review_roles ?? []).join(", ")}
        </p>
      )}
    </div>
  );
}
