import type { ScenarioAnalysis } from "../../api/client";
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
                <span key={projectId} className="chip">
                  {projectId}
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

      <div className="card">
        <h2 className="card-title">{t.section_ip}</h2>
        <div className="chip-row">
          {(scenario.uses_ip_blocks ?? []).map((ipId) => (
            <span key={ipId} className="chip">
              {ipId}
            </span>
          ))}
          {(scenario.depends_on_system_blocks ?? []).map((blockId) => (
            <span key={blockId} className="chip">
              {blockId}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">{t.section_requests}</h2>
        {analysis.requests.map((request) => (
          <div key={request.id} className="list-item">
            <div className="head">
              <span className="badge badge-info">{request.priority}</span>
              <span className="title">{request.title}</span>
            </div>
            <p className="desc">
              {t.request_week}: {ko.scenario_detail.week_prefix}
              {request.requested_week} · {t.request_status}: {request.status} · {t.confidence}:{" "}
              {request.confidence}
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
                <span className="badge badge-danger">{issue.issue_type}</span>
                <span className="title">{issue.title}</span>
                <span className="badge badge-info">{issue.status}</span>
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
