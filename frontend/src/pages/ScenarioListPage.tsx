import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchProjects, fetchScenarios } from "../api/client";
import { useLabels } from "../hooks/useLabels";
import { ko } from "../i18n/ko";

export function ScenarioListPage() {
  const [projectFilter, setProjectFilter] = useState<string | undefined>(undefined);
  const label = useLabels();

  const projects = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const scenarios = useQuery({
    queryKey: ["scenarios", projectFilter],
    queryFn: () => fetchScenarios(projectFilter),
  });

  if (scenarios.isPending) return <p className="status-msg">{ko.app.loading}</p>;
  if (scenarios.isError)
    return (
      <p className="status-msg">
        {ko.app.error}{" "}
        <button className="chip-link" onClick={() => scenarios.refetch()}>
          {ko.app.retry}
        </button>
      </p>
    );

  return (
    <div>
      <h1>{ko.scenario_list.title}</h1>
      <div className="filter-row">
        <span className="filter-label">{ko.scenario_list.filter_label}</span>
        <button
          className={`chip chip-btn ${projectFilter === undefined ? "active" : ""}`}
          onClick={() => setProjectFilter(undefined)}
        >
          {ko.scenario_list.filter_all}
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
      </div>
      {scenarios.data.length === 0 ? (
        <p className="status-msg">{ko.app.empty}</p>
      ) : (
        <div className="scenario-grid">
          {scenarios.data.map((scenario) => (
            <Link
              key={scenario.id}
              to={`/scenarios/${scenario.id}/overview`}
              className="card scenario-card"
            >
              <div className="name">{scenario.name}</div>
              <div className="meta" title={scenario.scenario_group_id}>
                {ko.scenario_list.group_prefix}: {label(scenario.scenario_group_id)} ·{" "}
                {scenario.domain}
              </div>
              <div className="chip-row">
                {(scenario.primary_kpis ?? []).slice(0, 5).map((kpi) => (
                  <span key={kpi} className="chip">
                    {kpi}
                  </span>
                ))}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
