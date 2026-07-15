import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchKPISeries, type ScenarioAnalysis } from "../../api/client";
import { useLabels } from "../../hooks/useLabels";
import { useValueLabels } from "../../hooks/useValueLabels";
import { ko } from "../../i18n/ko";

const t = ko.scenario_detail;

const GAP_BADGE: Record<string, string> = {
  missing_evidence: "badge-danger",
  unavailable_catalog: "badge-warn",
  required_evidence_open: "badge-warn",
  confidence_blocked: "badge-danger",
};

export function OverviewTab({ analysis }: { analysis: ScenarioAnalysis }) {
  const { scenario } = analysis;
  const label = useLabels();
  const valueLabel = useValueLabels();
  return (
    <div>
      <div className="card">
        <h2 className="card-title">{t.section_basic}</h2>
        <dl className="kv">
          <dt>{t.description}</dt>
          <dd>{scenario.description}</dd>
          <dt>{t.domain}</dt>
          <dd>{scenario.domain}</dd>
          <dt>{t.scenario_class}</dt>
          <dd>{scenario.scenario_class}</dd>
          <dt>{t.group}</dt>
          <dd>{analysis.scenario_group?.name ?? scenario.scenario_group_id}</dd>
          <dt>{t.projects}</dt>
          <dd>
            <span className="chip-row">
              {(scenario.project_relevance ?? []).map((projectId) => (
                <span key={projectId} className="chip" title={projectId}>
                  {label(projectId)}
                </span>
              ))}
            </span>
          </dd>
        </dl>
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_gaps}</h2>
        {analysis.evidence_gaps.length === 0 ? (
          <p className="section-note">{t.gap_none}</p>
        ) : (
          analysis.evidence_gaps.map((gap, index) => (
            <div key={`${gap.ref_id}-${index}`} className="list-item">
              <div className="head">
                <span className={`badge ${GAP_BADGE[gap.kind] ?? "badge-info"}`}>
                  {gap.kind_ko}
                </span>
                <span className="id">{gap.ref_id}</span>
              </div>
              <p className="desc">{gap.description}</p>
            </div>
          ))
        )}
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_kpi}</h2>
        <div className="chip-row">
          {analysis.kpis.map((kpi) => (
            <span key={kpi.id} className="chip">
              {kpi.id} ({kpi.unit}, {kpi.direction})
            </span>
          ))}
        </div>
      </div>

      {analysis.kpis.length > 0 && (
        <KPISeriesSection
          scenarioId={scenario.id}
          kpiIds={analysis.kpis.map((kpi) => kpi.id)}
        />
      )}

      <div className="card">
        <h2 className="card-title">{t.section_ip}</h2>
        <div className="chip-row">
          {(scenario.uses_ip_blocks ?? []).map((ipId) => (
            <span key={ipId} className="chip" title={ipId}>
              {label(ipId)}
            </span>
          ))}
          {(scenario.depends_on_system_blocks ?? []).map((blockId) => (
            <span key={blockId} className="chip" title={blockId}>
              {label(blockId)}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_requests}</h2>
        {analysis.requests.map((request) => (
          <div key={request.id} className="list-item">
            <div className="head">
              <span className="badge badge-info" title={request.priority}>
                {valueLabel("request_priority", request.priority)}
              </span>
              <span className="title">{request.title}</span>
            </div>
            <p className="desc">
              {t.request_week}: {ko.scenario_detail.week_prefix}
              {request.requested_week} · {t.request_status}:{" "}
              <span title={request.status}>{valueLabel("request_status", request.status)}</span> ·{" "}
              {t.confidence}: {request.confidence}
            </p>
          </div>
        ))}
      </div>

      {analysis.issues.length > 0 && (
        <div className="card">
          <h2 className="card-title">{t.section_issues}</h2>
          {analysis.issues.map((issue) => (
            <div key={issue.id} className="list-item">
              <div className="head">
                <span className="badge badge-danger" title={issue.issue_type}>
                  {valueLabel("issue_type", issue.issue_type)}
                </span>
                <span className="title">{issue.title}</span>
                <span className="badge badge-info" title={issue.status}>
                  {valueLabel("issue_status", issue.status)}
                </span>
              </div>
              <p className="desc">{issue.symptom}</p>
            </div>
          ))}
        </div>
      )}

      {analysis.variants.length > 0 && (
        <div className="card">
          <h2 className="card-title">{t.section_variants}</h2>
          <div className="chip-row">
            {analysis.variants.map((variant) => (
              <span key={variant.id} className="chip">
                {variant.id} ({variant.mode})
              </span>
            ))}
          </div>
        </div>
      )}

      {(analysis.measurement_evidence.length > 0 ||
        analysis.measurement_requirements.length > 0) && (
        <div className="card">
          <h2 className="card-title">{t.section_measurements}</h2>
          {analysis.measurement_evidence.map((item) => (
            <div key={item.id} className="list-item">
              <div className="head">
                <span className="badge badge-ok">{t.measurement_evidence}</span>
                <span className="title">{item.title}</span>
              </div>
              <p className="desc">{item.qualitative_result}</p>
            </div>
          ))}
          {analysis.measurement_requirements.map((item) => (
            <div key={item.id} className="list-item">
              <div className="head">
                <span className="badge badge-warn">{t.measurement_requirements}</span>
                <span className="title">{item.title}</span>
              </div>
              <p className="desc">{item.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const TREND_BADGE: Record<string, string> = {
  improved: "badge-ok",
  worsened: "badge-danger",
};

/** P3 KPI 시계열 — 주차×프로젝트 표 + 추세 사실 서술 (수치 점수 아님). */
function KPISeriesSection({
  scenarioId,
  kpiIds,
}: {
  scenarioId: string;
  kpiIds: string[];
}) {
  const label = useLabels();
  const valueLabel = useValueLabels();
  const [selected, setSelected] = useState(kpiIds[0]);
  const kpiId = kpiIds.includes(selected) ? selected : kpiIds[0];
  const series = useQuery({
    queryKey: ["kpi-series", kpiId, scenarioId],
    queryFn: () => fetchKPISeries(kpiId, scenarioId),
    enabled: Boolean(kpiId),
  });

  const data = series.data;
  const projects = data?.series ?? [];
  const weeks = [...new Set(projects.flatMap((s) => s.points.map((p) => p.week)))].sort(
    (a, b) => a - b,
  );

  return (
    <div className="card">
      <h2 className="card-title">{t.kpi_series_title}</h2>
      <p className="section-note">{t.kpi_series_note}</p>
      <div className="chip-row">
        {kpiIds.map((id) => (
          <button
            key={id}
            type="button"
            className={`chip chip-btn ${id === kpiId ? "active" : ""}`}
            onClick={() => setSelected(id)}
          >
            {id}
          </button>
        ))}
      </div>
      {series.isPending && <p className="status-msg">{ko.app.loading}</p>}
      {(series.isError || (data && projects.length === 0)) && (
        <p className="desc">{t.kpi_series_empty}</p>
      )}
      {data && projects.length > 0 && (
        <>
          <div className="heatmap-scroll">
            <table className="heatmap">
              <thead>
                <tr>
                  <th>{t.kpi_series_week}</th>
                  {projects.map((project) => (
                    <th key={project.project_id} title={project.project_id}>
                      {label(project.project_id)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weeks.map((week) => (
                  <tr key={week}>
                    <th>W{week}</th>
                    {projects.map((project) => {
                      const point = project.points.find((p) => p.week === week);
                      return (
                        <td
                          key={project.project_id}
                          title={
                            point?.measurement_stage
                              ? `${valueLabel("measurement_stage", point.measurement_stage)} · ${point.observation_id}`
                              : ""
                          }
                        >
                          {point ? `${point.value}${point.unit ?? ""}` : "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {projects.map((project) => (
            <p key={project.project_id} className="desc">
              <span className={`badge ${TREND_BADGE[project.trend] ?? "badge-info"}`}>
                {t.kpi_series_trend}: {project.trend_ko}
              </span>{" "}
              {label(project.project_id)} — {project.trend_note_ko}
            </p>
          ))}
        </>
      )}
    </div>
  );
}
